from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.core import auth


AUTH_HEADERS = {"X-API-Key": "dev-demo-token-change-me"}


def test_health_is_public():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "LuxRenovate Intelligence",
    }


def test_public_health_does_not_expose_provider_details():
    response = TestClient(app).get("/health")

    payload = response.json()
    assert "llm_provider" not in payload
    assert "llm_model" not in payload
    assert "ocr_provider" not in payload
    assert "ocr_aws_region" not in payload


def test_diagnostics_requires_api_key():
    response = TestClient(app).get("/api/diagnostics")

    assert response.status_code == 401


def test_diagnostics_with_valid_key_exposes_internal_status():
    response = TestClient(app).get("/api/diagnostics", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert "llm_provider" in response.json()
    assert "ocr_provider" in response.json()


def test_api_route_requires_api_key():
    response = TestClient(app).get("/api/sites")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key."


def test_api_route_rejects_wrong_api_key():
    response = TestClient(app).get("/api/sites", headers={"X-API-Key": "wrong"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key."


def test_api_route_accepts_valid_api_key():
    response = TestClient(app).get("/api/sites", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()


def test_enabled_auth_without_token_returns_service_error(monkeypatch):
    monkeypatch.setattr(auth, "settings", SimpleNamespace(api_auth_enabled=True, api_auth_token=None))

    response = TestClient(app).get("/api/sites", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is enabled but API_AUTH_TOKEN is not configured."
