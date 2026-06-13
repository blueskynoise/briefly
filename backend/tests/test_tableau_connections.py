from fastapi.testclient import TestClient

from app.config import parse_tableau_url
from app.main import app, tableau_connection_store, tableau_secret_store
from app.models import TableauConnectionValidationResponse

client = TestClient(app)


def setup_function():
    tableau_connection_store._connections.clear()
    tableau_secret_store._secrets.clear()


def test_tableau_url_site_extraction():
    server_url, site = parse_tableau_url("https://prod-ca-a.online.tableau.com/#/site/sales/views/Dashboard")

    assert server_url == "https://prod-ca-a.online.tableau.com"
    assert site == "sales"


def test_tableau_url_default_site_extraction():
    server_url, site = parse_tableau_url("https://tableau.example.com/views/Dashboard")

    assert server_url == "https://tableau.example.com"
    assert site == ""


def test_create_connection_rejects_missing_required_fields():
    response = client.post(
        "/api/tableau/connections",
        json={"server_url": "https://tableau.example.com", "site_content_url": "", "display_name": "Test", "pat_name": "", "pat_secret": ""},
    )

    assert response.status_code == 422


def test_pat_secret_is_not_returned_and_validation_success(monkeypatch):
    async def fake_sign_in(request):
        return TableauConnectionValidationResponse(success=True, message="Connected to Tableau as user-1 on sales.", server_url=request.server_url, site_content_url=request.site_content_url, site_id="site-1", user_id="user-1", display_name="user-1")

    monkeypatch.setattr("app.main.tableau_rest_client.sign_in_with_pat", fake_sign_in)
    response = client.post(
        "/api/tableau/connections",
        json={"server_url": "https://prod-ca-a.online.tableau.com/#/site/sales/views/Dashboard", "site_content_url": "", "display_name": "Sales", "pat_name": "token", "pat_secret": "super-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["server_url"] == "https://prod-ca-a.online.tableau.com"
    assert body["site_content_url"] == "sales"
    assert "pat_secret" not in body
    assert "encrypted_pat_secret" not in body


def test_validation_failure_with_401_response(monkeypatch):
    class FakeResponse:
        status_code = 401
        def json(self):
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setattr("app.tableau_service.httpx.AsyncClient", FakeClient)
    response = client.post(
        "/api/tableau/connections/validate",
        json={"server_url": "https://tableau.example.com", "site_content_url": "wrong", "display_name": "Test", "pat_name": "token", "pat_secret": "bad"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "rejected" in body["message"]
