from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes_documents import _is_allowed_source_path
from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR
from app.main import app


def test_document_source_path_allowlist():
    assert _is_allowed_source_path(RAW_PLANNING_DIR / "sample.pdf")
    assert _is_allowed_source_path(RAW_UPLOADS_DIR / "sample.pdf")
    assert not _is_allowed_source_path(Path(__file__))


def test_sources_api_does_not_expose_local_paths():
    response = TestClient(app).get("/api/sources")

    assert response.status_code == 200
    assert response.json()
    assert "local_path" not in response.json()[0]
    assert "checksum_sha256" not in response.json()[0]
