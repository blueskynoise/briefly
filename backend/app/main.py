from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response

from .config import get_settings
from .deck_generation_service import DeckGenerationService
from .errors import AuthenticationError, BrieflyServiceError, IntegrationError
from .google_slides_service import GoogleSlidesService
from .image_store import TemporaryImageStore
from .models import (
    ConnectedAccount,
    ConnectionsResponse,
    DeckGenerationJob,
    DeckGenerationRequest,
    HealthResponse,
    Provider,
    TableauWorkbook,
)
from .tableau_service import TableauService
from .token_store import DevelopmentTokenStore

settings = get_settings()
token_store = DevelopmentTokenStore(settings.token_store_path)
image_store = TemporaryImageStore()
tableau_service = TableauService(settings, token_store)
google_slides_service = GoogleSlidesService(settings, token_store)
deck_generation_service = DeckGenerationService(tableau_service, google_slides_service, image_store, settings)

app = FastAPI(title="Briefly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, DeckGenerationJob] = {}


def _service_error(error: BrieflyServiceError) -> HTTPException:
    status_code = 401 if isinstance(error, AuthenticationError) else 400
    if isinstance(error, IntegrationError):
        status_code = 502
    return HTTPException(status_code=status_code, detail=str(error))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="briefly-api")


@app.get("/api/connections", response_model=ConnectionsResponse)
def get_connections() -> ConnectionsResponse:
    return ConnectionsResponse(
        tableau=tableau_service.get_connection(),
        google=google_slides_service.get_connection(),
    )


@app.get("/auth/tableau")
def auth_tableau() -> RedirectResponse:
    try:
        return RedirectResponse(tableau_service.build_authorization_url())
    except BrieflyServiceError as error:
        raise _service_error(error) from error


@app.get("/auth/tableau/callback")
async def auth_tableau_callback(code: str = Query(default=""), state: str | None = None, error: str | None = None) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=401, detail="Tableau authentication was cancelled or denied.")
    try:
        await tableau_service.complete_oauth(code, state)
    except BrieflyServiceError as exc:
        raise _service_error(exc) from exc
    return RedirectResponse(f"{settings.frontend_base_url.rstrip('/')}?connected=tableau")


@app.get("/auth/google")
def auth_google() -> RedirectResponse:
    try:
        return RedirectResponse(google_slides_service.build_authorization_url())
    except BrieflyServiceError as error:
        raise _service_error(error) from error


@app.get("/auth/google/callback")
async def auth_google_callback(code: str = Query(default=""), state: str | None = None, error: str | None = None) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=401, detail="Google authentication was cancelled or denied.")
    try:
        await google_slides_service.complete_oauth(code, state)
    except BrieflyServiceError as exc:
        raise _service_error(exc) from exc
    return RedirectResponse(f"{settings.frontend_base_url.rstrip('/')}?connected=google")


@app.get("/api/tableau/views", response_model=list[TableauWorkbook])
async def list_tableau_views() -> list[TableauWorkbook]:
    try:
        return await tableau_service.list_workbooks_with_views()
    except BrieflyServiceError as error:
        raise _service_error(error) from error


@app.post("/api/decks/generate", response_model=DeckGenerationJob)
async def generate_deck(request: DeckGenerationRequest) -> DeckGenerationJob:
    try:
        job = await deck_generation_service.generate(request.view_ids)
    except BrieflyServiceError as error:
        job = DeckGenerationJob.create_failed(request.view_ids, str(error))
        jobs[job.id] = job
        raise _service_error(error) from error
    jobs[job.id] = job
    return job


@app.get("/api/jobs/{job_id}", response_model=DeckGenerationJob)
def get_job(job_id: str) -> DeckGenerationJob:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    return job


@app.get("/api/images/{image_id}")
def get_image(image_id: str) -> Response:
    image = image_store.get(image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found or expired.")
    return Response(content=image.content, media_type=image.content_type)
