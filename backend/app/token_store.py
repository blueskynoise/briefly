import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Provider


class DevelopmentTokenStore:
    """Small file-backed token store for local development only."""

    def __init__(self, path: Path):
        self.path = path

    def get(self, provider: Provider) -> dict[str, Any] | None:
        data = self._read_all()
        value = data.get(provider.value)
        return value if isinstance(value, dict) else None

    def set(self, provider: Provider, token_data: dict[str, Any]) -> None:
        data = self._read_all()
        data[provider.value] = {
            **token_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_all(data)

    def _read_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_all(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))
        self.path.chmod(0o600)
