from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    ConnectedAccount,
    ConnectionStatus,
    ConnectionsResponse,
    DeckGenerationJob,
    DeckGenerationRequest,
    HealthResponse,
    Provider,
    TableauView,
    TableauWorkbook,
)

app = FastAPI(title="Briefly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connections: dict[Provider, ConnectedAccount] = {
    Provider.TABLEAU: ConnectedAccount(provider=Provider.TABLEAU),
    Provider.GOOGLE: ConnectedAccount(provider=Provider.GOOGLE),
}

mock_workbooks: list[TableauWorkbook] = [
    TableauWorkbook(
        id="revenue-dashboard",
        name="Revenue Dashboard",
        views=[
            TableauView(
                id="revenue-growth",
                workbook_id="revenue-dashboard",
                name="Revenue Growth",
                description="Monthly revenue trend for the executive update.",
            ),
            TableauView(
                id="arr-trend",
                workbook_id="revenue-dashboard",
                name="ARR Trend",
                description="Current ARR and recent movement.",
            ),
            TableauView(
                id="pipeline",
                workbook_id="revenue-dashboard",
                name="Pipeline",
                description="Open pipeline for the next reporting period.",
            ),
        ],
    ),
    TableauWorkbook(
        id="customer-health",
        name="Customer Health",
        views=[
            TableauView(
                id="customer-count",
                workbook_id="customer-health",
                name="Customer Count",
                description="Active customer count by segment.",
            ),
            TableauView(
                id="retention",
                workbook_id="customer-health",
                name="Retention",
                description="Retention snapshot for recurring business reviews.",
            ),
        ],
    ),
]

jobs: dict[str, DeckGenerationJob] = {}


def _connect(provider: Provider, display_name: str) -> ConnectedAccount:
    account = ConnectedAccount(
        provider=provider,
        status=ConnectionStatus.CONNECTED,
        display_name=display_name,
        connected_at=datetime.now(timezone.utc),
    )
    connections[provider] = account
    return account


def _all_view_ids() -> set[str]:
    return {view.id for workbook in mock_workbooks for view in workbook.views}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="briefly-api")


@app.get("/api/connections", response_model=ConnectionsResponse)
def get_connections() -> ConnectionsResponse:
    return ConnectionsResponse(
        tableau=connections[Provider.TABLEAU],
        google=connections[Provider.GOOGLE],
    )


@app.post("/api/connections/tableau/mock-connect", response_model=ConnectedAccount)
def mock_connect_tableau() -> ConnectedAccount:
    return _connect(Provider.TABLEAU, "Mock Tableau Workspace")


@app.post("/api/connections/google/mock-connect", response_model=ConnectedAccount)
def mock_connect_google() -> ConnectedAccount:
    return _connect(Provider.GOOGLE, "Mock Google Slides Account")


@app.get("/api/tableau/views", response_model=list[TableauWorkbook])
def list_tableau_views() -> list[TableauWorkbook]:
    return mock_workbooks


@app.post("/api/decks/generate", response_model=DeckGenerationJob)
def generate_deck(request: DeckGenerationRequest) -> DeckGenerationJob:
    if connections[Provider.TABLEAU].status != ConnectionStatus.CONNECTED:
        raise HTTPException(status_code=400, detail="Connect Tableau before generating a deck.")
    if connections[Provider.GOOGLE].status != ConnectionStatus.CONNECTED:
        raise HTTPException(status_code=400, detail="Connect Google before generating a deck.")

    unknown_view_ids = set(request.view_ids) - _all_view_ids()
    if unknown_view_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Tableau view ids: {', '.join(sorted(unknown_view_ids))}",
        )

    job = DeckGenerationJob.create_completed(
        view_ids=request.view_ids,
        slide_count=len(request.view_ids),
    )
    jobs[job.id] = job
    return job


@app.get("/api/jobs/{job_id}", response_model=DeckGenerationJob)
def get_job(job_id: str) -> DeckGenerationJob:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    return job
