from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Provider(StrEnum):
    TABLEAU = "tableau"
    GOOGLE = "google"


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConnectedAccount(BaseModel):
    provider: Provider
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    display_name: str | None = None
    connected_at: datetime | None = None


class ConnectionsResponse(BaseModel):
    tableau: ConnectedAccount
    google: ConnectedAccount


class TableauView(BaseModel):
    id: str
    workbook_id: str
    name: str
    description: str


class TableauWorkbook(BaseModel):
    id: str
    name: str
    views: list[TableauView]


class DeckGenerationRequest(BaseModel):
    view_ids: list[str] = Field(min_length=1)


class GeneratedDeck(BaseModel):
    id: str
    title: str
    url: str
    slide_count: int


class DeckGenerationJob(BaseModel):
    id: str
    status: JobStatus
    requested_view_ids: list[str]
    message: str
    generated_deck: GeneratedDeck | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def create_completed(cls, view_ids: list[str], slide_count: int) -> "DeckGenerationJob":
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        deck = GeneratedDeck(
            id=f"deck_{job_id}",
            title="Briefly Executive Update",
            url=f"https://docs.google.com/presentation/d/mock-briefly-{job_id}/edit",
            slide_count=slide_count,
        )
        return cls(
            id=job_id,
            status=JobStatus.COMPLETED,
            requested_view_ids=view_ids,
            message="Your executive-ready deck is ready.",
            generated_deck=deck,
            created_at=now,
            completed_at=now,
        )


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
