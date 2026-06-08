import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import Settings
from .errors import AuthenticationError, IntegrationError
from .models import ConnectedAccount, ConnectionStatus, GeneratedDeck, Provider
from .token_store import DevelopmentTokenStore

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SLIDES_API_URL = "https://slides.googleapis.com/v1/presentations"


class GoogleSlidesService:
    def __init__(self, settings: Settings, token_store: DevelopmentTokenStore):
        self.settings = settings
        self.token_store = token_store

    def is_configured(self) -> bool:
        return bool(self.settings.google_client_id and self.settings.google_client_secret)

    def get_connection(self) -> ConnectedAccount:
        token = self.token_store.get(Provider.GOOGLE)
        if not token or not token.get("access_token"):
            return ConnectedAccount(provider=Provider.GOOGLE)
        return ConnectedAccount(
            provider=Provider.GOOGLE,
            status=ConnectionStatus.CONNECTED,
            display_name=token.get("email") or "Google Slides",
            connected_at=_parse_datetime(token.get("updated_at")),
        )

    def build_authorization_url(self) -> str:
        if not self.is_configured():
            raise AuthenticationError("Google OAuth is not configured. Set Google OAuth environment variables first.")
        state = secrets.token_urlsafe(24)
        self.token_store.set(Provider.GOOGLE, {"oauth_state": state})
        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self._redirect_uri(),
                "response_type": "code",
                "scope": self.settings.google_scopes,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def complete_oauth(self, code: str, state: str | None) -> None:
        saved_state = (self.token_store.get(Provider.GOOGLE) or {}).get("oauth_state")
        if not saved_state or state != saved_state:
            raise AuthenticationError("Google authentication failed because the OAuth state did not match.")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": self._redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
        if response.status_code >= 400:
            raise AuthenticationError("Google authentication failed while exchanging the OAuth code.")
        token = response.json()
        token["expires_at"] = _expires_at(token.get("expires_in"))
        token["email"] = await self._fetch_email(token)
        self.token_store.set(Provider.GOOGLE, token)

    async def create_presentation(self, title: str, slides: list[dict[str, str]]) -> GeneratedDeck:
        token = await self._valid_token()
        async with httpx.AsyncClient(timeout=60) as client:
            create_response = await client.post(
                SLIDES_API_URL,
                headers=self._headers(token),
                json={"title": title},
            )
            if create_response.status_code == 401:
                raise AuthenticationError("Google token expired. Reconnect Google and try again.")
            if create_response.status_code >= 400:
                raise IntegrationError("Could not create the Google Slides presentation.")
            presentation = create_response.json()
            presentation_id = presentation["presentationId"]
            requests = self._build_requests(presentation, title, slides)
            update_response = await client.post(
                f"{SLIDES_API_URL}/{presentation_id}:batchUpdate",
                headers=self._headers(token),
                json={"requests": requests},
            )
        if update_response.status_code == 401:
            raise AuthenticationError("Google token expired. Reconnect Google and try again.")
        if update_response.status_code >= 400:
            raise IntegrationError("Could not populate the Google Slides presentation.")
        return GeneratedDeck(
            id=presentation_id,
            title=title,
            url=f"https://docs.google.com/presentation/d/{presentation_id}/edit",
            slide_count=len(slides) + 1,
        )

    def _build_requests(self, presentation: dict[str, Any], title: str, slides: list[dict[str, str]]) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        default_slide_id = (presentation.get("slides") or [{}])[0].get("objectId")
        requests.extend(
            [
                {"createSlide": {"objectId": "briefly_title_slide", "insertionIndex": 0, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
                {"createShape": {"objectId": "briefly_deck_title", "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": "briefly_title_slide", "size": {"width": {"magnitude": 600, "unit": "PT"}, "height": {"magnitude": 80, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 60, "translateY": 180, "unit": "PT"}}}},
                {"insertText": {"objectId": "briefly_deck_title", "text": title}},
                {"updateTextStyle": {"objectId": "briefly_deck_title", "textRange": {"type": "ALL"}, "style": {"fontSize": {"magnitude": 32, "unit": "PT"}, "bold": True}, "fields": "fontSize,bold"}},
            ]
        )
        for index, slide in enumerate(slides, start=1):
            slide_id = f"briefly_view_slide_{index}"
            title_id = f"briefly_view_title_{index}"
            image_id = f"briefly_view_image_{index}"
            requests.extend(
                [
                    {"createSlide": {"objectId": slide_id, "insertionIndex": index, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
                    {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 600, "unit": "PT"}, "height": {"magnitude": 40, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40, "translateY": 24, "unit": "PT"}}}},
                    {"insertText": {"objectId": title_id, "text": slide["title"]}},
                    {"updateTextStyle": {"objectId": title_id, "textRange": {"type": "ALL"}, "style": {"fontSize": {"magnitude": 20, "unit": "PT"}, "bold": True}, "fields": "fontSize,bold"}},
                    {"createImage": {"objectId": image_id, "url": slide["image_url"], "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 640, "unit": "PT"}, "height": {"magnitude": 360, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40, "translateY": 86, "unit": "PT"}}}},
                ]
            )
        if default_slide_id:
            requests.append({"deleteObject": {"objectId": default_slide_id}})
        return requests

    async def _valid_token(self) -> dict[str, Any]:
        token = self.token_store.get(Provider.GOOGLE)
        if not token or not token.get("access_token"):
            raise AuthenticationError("Connect Google before continuing.")
        if _is_expired(token) and token.get("refresh_token"):
            token = await self._refresh_token(token)
        if _is_expired(token):
            raise AuthenticationError("Google token expired. Reconnect Google and try again.")
        return token

    async def _refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": token["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise AuthenticationError("Google token expired. Reconnect Google and try again.")
        refreshed = {**token, **response.json()}
        refreshed["expires_at"] = _expires_at(refreshed.get("expires_in"))
        self.token_store.set(Provider.GOOGLE, refreshed)
        return refreshed

    async def _fetch_email(self, token: dict[str, Any]) -> str | None:
        if "openid" not in self.settings.google_scopes and "userinfo.email" not in self.settings.google_scopes:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(GOOGLE_USERINFO_URL, headers=self._headers(token))
        if response.status_code >= 400:
            return None
        return response.json().get("email")

    def _headers(self, token: dict[str, Any]) -> dict[str, str]:
        return {"Authorization": f"Bearer {token['access_token']}", "Accept": "application/json", "Content-Type": "application/json"}

    def _redirect_uri(self) -> str:
        return f"{self.settings.app_base_url.rstrip('/')}/auth/google/callback"


def _expires_at(expires_in: Any) -> str | None:
    if not expires_in:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in) - 60)).isoformat()


def _is_expired(token: dict[str, Any]) -> bool:
    expires_at = _parse_datetime(token.get("expires_at"))
    return bool(expires_at and expires_at <= datetime.now(timezone.utc))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
