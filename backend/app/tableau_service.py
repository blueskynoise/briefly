import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import Settings
from .config import parse_tableau_url
from .errors import AuthenticationError, IntegrationError
from .models import ConnectedAccount, ConnectionStatus, Provider, TableauConnectionValidateRequest, TableauConnectionValidationResponse, TableauView, TableauWorkbook
from .token_store import DevelopmentTokenStore


class TableauRestClient:
    def __init__(self, api_version: str):
        self.api_version = api_version

    async def sign_in_with_pat(self, request: TableauConnectionValidateRequest) -> TableauConnectionValidationResponse:
        try:
            server_url, _ = parse_tableau_url(request.server_url)
        except ValueError as exc:
            return TableauConnectionValidationResponse(success=False, message=str(exc))
        payload = {
            "credentials": {
                "personalAccessTokenName": request.pat_name,
                "personalAccessTokenSecret": request.pat_secret.get_secret_value(),
                "site": {"contentUrl": request.site_content_url},
            }
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{server_url}/api/{self.api_version}/auth/signin",
                    json=payload,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
        except httpx.RequestError:
            return TableauConnectionValidationResponse(
                success=False,
                message="Could not reach Tableau. Check the server URL and your network access.",
                server_url=server_url,
                site_content_url=request.site_content_url,
            )
        if response.status_code in {401, 403}:
            return TableauConnectionValidationResponse(
                success=False,
                message="Tableau rejected the Personal Access Token or site content URL. Check the PAT name, secret, and site.",
                server_url=server_url,
                site_content_url=request.site_content_url,
            )
        if response.status_code >= 400:
            return TableauConnectionValidationResponse(
                success=False,
                message="Tableau sign-in failed. Check the site content URL and try again.",
                server_url=server_url,
                site_content_url=request.site_content_url,
            )
        try:
            credentials = response.json().get("credentials", {})
            token = credentials.get("token")
            site = credentials.get("site", {})
            user = credentials.get("user", {})
        except ValueError:
            return TableauConnectionValidationResponse(success=False, message="Tableau returned an unexpected response.", server_url=server_url, site_content_url=request.site_content_url)
        if not token or not site.get("id") or not user.get("id"):
            return TableauConnectionValidationResponse(success=False, message="Tableau returned an unexpected sign-in response.", server_url=server_url, site_content_url=request.site_content_url)
        display = user.get("name") or user.get("id")
        site_label = site.get("contentUrl") or request.site_content_url or "Default site"
        return TableauConnectionValidationResponse(success=True, message=f"Connected to Tableau as {display} on {site_label}.", server_url=server_url, site_content_url=request.site_content_url, site_id=site.get("id"), user_id=user.get("id"), display_name=display)

    async def sign_out(self, server_url: str, token: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{server_url.rstrip('/')}/api/{self.api_version}/auth/signout", headers={"X-Tableau-Auth": token})


class TableauService:
    def __init__(self, settings: Settings, token_store: DevelopmentTokenStore):
        self.settings = settings
        self.token_store = token_store
        self.server_url = settings.tableau_server_url.rstrip("/")
        self.rest_client = TableauRestClient(settings.tableau_api_version)

    def is_configured(self) -> bool:
        return all([
            self.server_url,
            self.settings.tableau_client_id,
            self.settings.tableau_client_secret,
        ])

    def get_connection(self) -> ConnectedAccount:
        token = self.token_store.get(Provider.TABLEAU)
        if not token or not token.get("access_token"):
            return ConnectedAccount(provider=Provider.TABLEAU)
        display_name = token.get("site_name") or token.get("user_id") or "Tableau Cloud"
        return ConnectedAccount(
            provider=Provider.TABLEAU,
            status=ConnectionStatus.CONNECTED,
            display_name=display_name,
            connected_at=_parse_datetime(token.get("updated_at")),
        )

    def build_authorization_url(self) -> str:
        if not self.is_configured():
            raise AuthenticationError("Tableau OAuth is not configured. Set Tableau OAuth environment variables first.")
        state = secrets.token_urlsafe(24)
        self.token_store.set(Provider.TABLEAU, {"oauth_state": state})
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.tableau_client_id,
                "redirect_uri": self._redirect_uri(),
                "scope": self.settings.tableau_scopes,
                "state": state,
            }
        )
        return f"{self.settings.tableau_authorization_url}?{query}"

    async def complete_oauth(self, code: str, state: str | None) -> None:
        saved_state = (self.token_store.get(Provider.TABLEAU) or {}).get("oauth_state")
        if not saved_state or state != saved_state:
            raise AuthenticationError("Tableau authentication failed because the OAuth state did not match.")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.settings.tableau_token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri(),
                    "client_id": self.settings.tableau_client_id,
                    "client_secret": self.settings.tableau_client_secret,
                },
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise AuthenticationError("Tableau authentication failed while exchanging the OAuth code.")
        token = response.json()
        token["expires_at"] = _expires_at(token.get("expires_in"))
        await self._populate_tableau_session(token)
        self.token_store.set(Provider.TABLEAU, token)

    async def list_workbooks_with_views(self) -> list[TableauWorkbook]:
        if not self.server_url:
            raise AuthenticationError("Tableau server URL is not configured.")
        token = await self._valid_token()
        site_id = self._site_id(token)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.server_url}/api/{self.settings.tableau_api_version}/sites/{site_id}/workbooks",
                headers=self._headers(token),
                params={"pageSize": 1000},
            )
        if response.status_code == 401:
            raise AuthenticationError("Tableau session expired. Reconnect Tableau and try again.")
        if response.status_code >= 400:
            raise IntegrationError("Could not retrieve Tableau workbooks.")
        workbooks = response.json().get("workbooks", {}).get("workbook", [])
        results: list[TableauWorkbook] = []
        for workbook in workbooks:
            workbook_id = workbook.get("id")
            if not workbook_id:
                continue
            views = await self._list_workbook_views(workbook_id, token)
            results.append(TableauWorkbook(id=workbook_id, name=workbook.get("name", "Untitled workbook"), views=views))
        return results

    async def fetch_view_image(self, view_id: str) -> bytes:
        token = await self._valid_token()
        site_id = self._site_id(token)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.server_url}/api/{self.settings.tableau_api_version}/sites/{site_id}/views/{view_id}/image",
                headers=self._headers(token),
                params={"resolution": "high"},
            )
        if response.status_code == 401:
            raise AuthenticationError("Tableau session expired. Reconnect Tableau and try again.")
        if response.status_code >= 400:
            raise IntegrationError("Could not fetch the Tableau visualization image.")
        return response.content

    async def get_view_lookup(self, view_ids: list[str]) -> dict[str, TableauView]:
        workbooks = await self.list_workbooks_with_views()
        lookup = {view.id: view for workbook in workbooks for view in workbook.views}
        missing = sorted(set(view_ids) - set(lookup))
        if missing:
            raise IntegrationError(f"Missing Tableau views: {', '.join(missing)}")
        return lookup

    async def _list_workbook_views(self, workbook_id: str, token: dict[str, Any]) -> list[TableauView]:
        site_id = self._site_id(token)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.server_url}/api/{self.settings.tableau_api_version}/sites/{site_id}/workbooks/{workbook_id}/views",
                headers=self._headers(token),
                params={"pageSize": 1000},
            )
        if response.status_code >= 400:
            raise IntegrationError("Could not retrieve Tableau views.")
        views = response.json().get("views", {}).get("view", [])
        return [
            TableauView(
                id=view.get("id", ""),
                workbook_id=workbook_id,
                name=view.get("name", "Untitled view"),
                description=view.get("contentUrl") or "Rendered Tableau view",
            )
            for view in views
            if view.get("id")
        ]

    async def _populate_tableau_session(self, token: dict[str, Any]) -> None:
        access_token = token.get("access_token")
        if not access_token:
            raise AuthenticationError("Tableau did not return an access token.")
        if token.get("site_id"):
            return
        # OAuth access tokens for Tableau REST are exchanged for a Tableau credentials token via Sign In.
        payload = {"credentials": {"jwt": access_token, "site": {"contentUrl": self.settings.tableau_site_content_url}}}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.server_url}/api/{self.settings.tableau_api_version}/auth/signin",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        if response.status_code >= 400:
            # Some Tableau OAuth setups return a REST-ready bearer token directly. Keep the token and use bearer auth.
            token["auth_mode"] = "bearer"
            return
        credentials = response.json().get("credentials", {})
        token["tableau_token"] = credentials.get("token")
        token["site_id"] = credentials.get("site", {}).get("id")
        token["site_name"] = credentials.get("site", {}).get("contentUrl") or self.settings.tableau_site_content_url
        token["user_id"] = credentials.get("user", {}).get("id")
        token["auth_mode"] = "x-tableau-auth"

    async def _valid_token(self) -> dict[str, Any]:
        token = self.token_store.get(Provider.TABLEAU)
        if not token or not token.get("access_token"):
            raise AuthenticationError("Connect Tableau before continuing.")
        if _is_expired(token) and token.get("refresh_token"):
            token = await self._refresh_token(token)
        if _is_expired(token):
            raise AuthenticationError("Tableau token expired. Reconnect Tableau and try again.")
        return token

    async def _refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.settings.tableau_token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token["refresh_token"],
                    "client_id": self.settings.tableau_client_id,
                    "client_secret": self.settings.tableau_client_secret,
                },
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise AuthenticationError("Tableau token expired. Reconnect Tableau and try again.")
        refreshed = {**token, **response.json()}
        refreshed["expires_at"] = _expires_at(refreshed.get("expires_in"))
        await self._populate_tableau_session(refreshed)
        self.token_store.set(Provider.TABLEAU, refreshed)
        return refreshed

    def _headers(self, token: dict[str, Any]) -> dict[str, str]:
        if token.get("auth_mode") == "x-tableau-auth" and token.get("tableau_token"):
            return {"X-Tableau-Auth": token["tableau_token"], "Accept": "application/json"}
        return {"Authorization": f"Bearer {token['access_token']}", "Accept": "application/json"}

    def _site_id(self, token: dict[str, Any]) -> str:
        site_id = token.get("site_id")
        if not site_id:
            raise AuthenticationError("Tableau OAuth completed, but no Tableau site id is available.")
        return site_id

    def _redirect_uri(self) -> str:
        return f"{self.settings.app_base_url.rstrip('/')}/auth/tableau/callback"


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
