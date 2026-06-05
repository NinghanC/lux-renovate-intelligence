from fastapi.testclient import TestClient

from app.main import app


def preflight(*, origin: str, method: str = "POST", headers: str = "Content-Type,X-API-Key"):
    return TestClient(app).options(
        "/api/dossiers/generate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_cors_allows_configured_origin_methods_and_headers():
    response = preflight(origin="http://localhost:5173")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "X-API-Key" in response.headers["access-control-allow-headers"]
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unconfigured_origin():
    response = preflight(origin="https://evil.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_rejects_unconfigured_method():
    response = preflight(origin="http://localhost:5173", method="PUT")

    assert response.status_code == 400


def test_cors_rejects_unconfigured_header():
    response = preflight(origin="http://localhost:5173", headers="Authorization")

    assert response.status_code == 400
