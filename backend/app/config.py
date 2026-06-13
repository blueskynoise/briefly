import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def parse_tableau_url(url: str) -> tuple[str, str]:
    """Return (server_url, site_content_url) parsed from a Tableau URL or origin."""
    raw_url = (url or "").strip()
    if not raw_url:
        raise ValueError("Enter a Tableau server URL or dashboard URL.")
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid Tableau URL, including a Tableau host.")
    server_url = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    searchable = f"{parsed.path}/{parsed.fragment or ''}"
    match = re.search(r"/site/([^/?#]+)", searchable)
    site_content_url = match.group(1).strip("/") if match else ""
    return server_url, site_content_url

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
    tableau_scopes: str = "tableau:content:read tableau:views:download"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_scopes: str = "https://www.googleapis.com/auth/presentations"

    @property
    def tableau_authorization_url(self) -> str:
        return f"{self.tableau_server_url.rstrip('/')}/oauth2/authorize" if self.tableau_server_url else ""

    @property
    def tableau_token_url(self) -> str:
        return f"{self.tableau_server_url.rstrip('/')}/oauth2/token" if self.tableau_server_url else ""

    def __init__(self, **overrides: Any):
        _load_dotenv()
        # TABLEAU_URL is a convenience alternative: paste any dashboard URL and
        # server_url + site_content_url are extracted automatically.
        tableau_url_raw = os.getenv("TABLEAU_URL", "")
        parsed_server, parsed_site = parse_tableau_url(tableau_url_raw) if tableau_url_raw else ("", "")
        values = {
            "app_base_url": os.getenv("APP_BASE_URL", "http://localhost:8000"),
            "frontend_base_url": os.getenv("FRONTEND_BASE_URL", "http://localhost:3000"),
            "token_store_path": Path(os.getenv("TOKEN_STORE_PATH", ".briefly_tokens.json")),
            "tableau_server_url": os.getenv("TABLEAU_SERVER_URL", parsed_server),
            "tableau_site_content_url": os.getenv("TABLEAU_SITE_CONTENT_URL", parsed_site),
            "tableau_api_version": os.getenv("TABLEAU_API_VERSION", "3.25"),
            "tableau_client_id": os.getenv("TABLEAU_CLIENT_ID", ""),
            "tableau_client_secret": os.getenv("TABLEAU_CLIENT_SECRET", ""),
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


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\'").strip('"'))


@lru_cache
def get_settings() -> Settings:
    return Settings()
