from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr, field_validator


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


class TableauConnectionValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"


class TableauConnection(BaseModel):
    id: str
    display_name: str
    server_url: str
    site_content_url: str = ""
    auth_type: Literal["pat"] = "pat"
    pat_name: str
    encrypted_pat_secret: str
    created_at: datetime
    last_validated_at: datetime | None = None
    validation_status: TableauConnectionValidationStatus = TableauConnectionValidationStatus.UNVALIDATED


class TableauConnectionResponse(BaseModel):
    id: str
    display_name: str
    server_url: str
    site_content_url: str = ""
    auth_type: Literal["pat"] = "pat"
    pat_name: str
    created_at: datetime
    last_validated_at: datetime | None = None
    validation_status: TableauConnectionValidationStatus

    @classmethod
    def from_connection(cls, connection: TableauConnection) -> "TableauConnectionResponse":
        return cls(**connection.model_dump(exclude={"encrypted_pat_secret"}))


class TableauConnectionCreateRequest(BaseModel):
    server_url: str
    site_content_url: str = ""
    pat_name: str
    pat_secret: SecretStr
    display_name: str

    @field_validator("server_url", "display_name", "pat_name")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field is required.")
        return value

    @field_validator("site_content_url")
    @classmethod
    def clean_site_content_url(cls, value: str) -> str:
        return value.strip().strip("/")


class TableauConnectionValidateRequest(TableauConnectionCreateRequest):
    pass


class TableauConnectionValidationResponse(BaseModel):
    success: bool
    message: str
    server_url: str | None = None
    site_content_url: str | None = None
    site_id: str | None = None
    user_id: str | None = None
    display_name: str | None = None


class TableauView(BaseModel):
    id: str
    workbook_id: str
    name: str
    description: str = "Rendered Tableau view"


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
    def create_completed(cls, view_ids: list[str], generated_deck: GeneratedDeck) -> "DeckGenerationJob":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid4()),
            status=JobStatus.COMPLETED,
            requested_view_ids=view_ids,
            message="Your Google Slides deck is ready.",
            generated_deck=generated_deck,
            created_at=now,
            completed_at=now,
        )

    @classmethod
    def create_failed(cls, view_ids: list[str], message: str) -> "DeckGenerationJob":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid4()),
            status=JobStatus.FAILED,
            requested_view_ids=view_ids,
            message=message,
            created_at=now,
            completed_at=now,
        )


class TableauUrlParseResult(BaseModel):
    server_url: str
    site_content_url: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
