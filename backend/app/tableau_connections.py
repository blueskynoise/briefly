from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from .models import TableauConnection, TableauConnectionCreateRequest, TableauConnectionValidationStatus


class TableauSecretStore(Protocol):
    def store_secret(self, connection_id: str, secret: str) -> str: ...
    def get_secret(self, secret_ref: str) -> str | None: ...
    def delete_secret(self, secret_ref: str) -> None: ...


class InMemoryTableauSecretStore:
    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def store_secret(self, connection_id: str, secret: str) -> str:
        secret_ref = f"tableau-pat:{connection_id}"
        self._secrets[secret_ref] = secret
        return secret_ref

    def get_secret(self, secret_ref: str) -> str | None:
        return self._secrets.get(secret_ref)

    def delete_secret(self, secret_ref: str) -> None:
        self._secrets.pop(secret_ref, None)


class InMemoryTableauConnectionStore:
    def __init__(self, secret_store: TableauSecretStore):
        self.secret_store = secret_store
        self._connections: dict[str, TableauConnection] = {}

    def list_connections(self) -> list[TableauConnection]:
        return list(self._connections.values())

    def get(self, connection_id: str) -> TableauConnection | None:
        return self._connections.get(connection_id)

    def create(self, request: TableauConnectionCreateRequest) -> TableauConnection:
        now = datetime.now(timezone.utc)
        connection_id = str(uuid4())
        secret_ref = self.secret_store.store_secret(connection_id, request.pat_secret.get_secret_value())
        connection = TableauConnection(
            id=connection_id,
            display_name=request.display_name,
            server_url=request.server_url,
            site_content_url=request.site_content_url,
            auth_type="pat",
            pat_name=request.pat_name,
            encrypted_pat_secret=secret_ref,
            created_at=now,
            validation_status=TableauConnectionValidationStatus.UNVALIDATED,
        )
        self._connections[connection.id] = connection
        return connection

    def mark_validated(self, connection_id: str) -> None:
        connection = self._connections.get(connection_id)
        if not connection:
            return
        updated = connection.model_copy(
            update={
                "last_validated_at": datetime.now(timezone.utc),
                "validation_status": TableauConnectionValidationStatus.VALID,
            }
        )
        self._connections[connection_id] = updated

    def delete(self, connection_id: str) -> bool:
        connection = self._connections.pop(connection_id, None)
        if not connection:
            return False
        self.secret_store.delete_secret(connection.encrypted_pat_secret)
        return True
