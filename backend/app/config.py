import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\'").strip('"'))


@dataclass
class Settings:
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    token_store_path: Path = Path(".briefly_tokens.json")

    tableau_server_url: str = ""
    tableau_site_content_url: str = ""
    tableau_api_version: str = "3.25"
    tableau_client_id: str = ""
    tableau_client_secret: str = ""
    tableau_authorization_url: str = ""
    tableau_token_url: str = ""
    tableau_scopes: str = "tableau:content:read tableau:views:download"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_scopes: str = "https://www.googleapis.com/auth/presentations"

    def __init__(self, **overrides: Any):
        _load_dotenv()
        values = {
            "app_base_url": os.getenv("APP_BASE_URL", "http://localhost:8000"),
            "frontend_base_url": os.getenv("FRONTEND_BASE_URL", "http://localhost:3000"),
            "token_store_path": Path(os.getenv("TOKEN_STORE_PATH", ".briefly_tokens.json")),
            "tableau_server_url": os.getenv("TABLEAU_SERVER_URL", ""),
            "tableau_site_content_url": os.getenv("TABLEAU_SITE_CONTENT_URL", ""),
            "tableau_api_version": os.getenv("TABLEAU_API_VERSION", "3.25"),
            "tableau_client_id": os.getenv("TABLEAU_CLIENT_ID", ""),
            "tableau_client_secret": os.getenv("TABLEAU_CLIENT_SECRET", ""),
            "tableau_authorization_url": os.getenv("TABLEAU_AUTHORIZATION_URL", ""),
            "tableau_token_url": os.getenv("TABLEAU_TOKEN_URL", ""),
            "tableau_scopes": os.getenv("TABLEAU_SCOPES", "tableau:content:read tableau:views:download"),
            "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "google_scopes": os.getenv("GOOGLE_SCOPES", "https://www.googleapis.com/auth/presentations"),
        }
        values.update(overrides)
        for key, value in values.items():
            if key == "token_store_path" and not isinstance(value, Path):
                value = Path(value)
            setattr(self, key, value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
