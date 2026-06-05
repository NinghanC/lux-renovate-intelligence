from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes_documents
from app.api.routes_documents import _is_allowed_source_path
from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR
from app.main import app
from app.models.schemas import UploadResponse


AUTH_HEADERS = {"X-API-Key": "dev-demo-token-change-me"}


def test_document_source_path_allowlist():
    assert _is_allowed_source_path(RAW_PLANNING_DIR / "sample.pdf")
    assert _is_allowed_source_path(RAW_UPLOADS_DIR / "sample.pdf")
    assert not _is_allowed_source_path(Path(__file__))


def test_sources_api_does_not_expose_local_paths():
    response = TestClient(app).get("/api/sources", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()
    assert "local_path" not in response.json()[0]
    assert "checksum_sha256" not in response.json()[0]


def test_upload_document_accepts_file_under_size_limit(monkeypatch):
    captured = {}

    def fake_save_and_chunk_upload(**kwargs):
        captured.update(kwargs)
        return UploadResponse(
            document_id="upload_test",
            source_id="src_upload_test",
            document_type="uploaded",
            source_subtype="other",
            modality="text",
            filename=kwargs["filename"],
            chunks_created=0,
            chunks=[],
        )

    monkeypatch.setattr(routes_documents, "MAX_UPLOAD_BYTES", 32)
    monkeypatch.setattr(routes_documents, "save_and_chunk_upload", fake_save_and_chunk_upload)

    response = TestClient(app).post(
        "/api/documents/upload",
        headers=AUTH_HEADERS,
        data={"commune": "Luxembourg"},
        files={"file": ("sample.txt", b"small upload", "text/plain")},
    )

    assert response.status_code == 200
    assert captured["filename"] == "sample.txt"
    assert captured["content"] == b"small upload"


def test_upload_document_rejects_file_over_size_limit(monkeypatch):
    called = False

    def fake_save_and_chunk_upload(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("Oversized upload should not be saved.")

    monkeypatch.setattr(routes_documents, "MAX_UPLOAD_BYTES", 8)
    monkeypatch.setattr(routes_documents, "save_and_chunk_upload", fake_save_and_chunk_upload)

    response = TestClient(app).post(
        "/api/documents/upload",
        headers=AUTH_HEADERS,
        data={"commune": "Luxembourg"},
        files={"file": ("large.txt", b"0123456789", "text/plain")},
    )

    assert response.status_code == 413
    assert "8 byte limit" in response.json()["detail"]
    assert called is False
