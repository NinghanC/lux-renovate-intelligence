from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes_documents
from app.api.routes_documents import _is_allowed_source_path
from app.core import auth
from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR
from app.main import app
from app.models.schemas import UploadResponse


TEST_API_AUTH_TOKEN = "test-api-token"
auth.settings = type("AuthSettings", (), {"api_auth_enabled": True, "api_auth_token": TEST_API_AUTH_TOKEN})()
AUTH_HEADERS = {"X-API-Key": TEST_API_AUTH_TOKEN}


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


def test_upload_documents_batch_replaces_active_set_once(monkeypatch):
    captured = []

    def fake_save_and_chunk_upload(**kwargs):
        captured.append(kwargs)
        return UploadResponse(
            document_id=f"upload_test_{len(captured)}",
            source_id=f"src_upload_test_{len(captured)}",
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
        "/api/documents/upload-batch",
        headers=AUTH_HEADERS,
        data={"commune": "Luxembourg", "replace_active_documents": "true"},
        files=[
            ("files", ("first.txt", b"first upload", "text/plain")),
            ("files", ("second.txt", b"second upload", "text/plain")),
        ],
    )

    assert response.status_code == 200
    assert [item["filename"] for item in response.json()] == ["first.txt", "second.txt"]
    assert [item["filename"] for item in captured] == ["first.txt", "second.txt"]
    assert [item["replace_active_documents"] for item in captured] == [True, False]


def test_upload_documents_batch_appends_by_default(monkeypatch):
    captured = []

    def fake_save_and_chunk_upload(**kwargs):
        captured.append(kwargs)
        return UploadResponse(
            document_id=f"upload_test_{len(captured)}",
            source_id=f"src_upload_test_{len(captured)}",
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
        "/api/documents/upload-batch",
        headers=AUTH_HEADERS,
        data={"commune": "Luxembourg"},
        files=[
            ("files", ("first.txt", b"first upload", "text/plain")),
            ("files", ("second.txt", b"second upload", "text/plain")),
        ],
    )

    assert response.status_code == 200
    assert [item["replace_active_documents"] for item in captured] == [False, False]


def test_remove_active_document_removes_from_queue(monkeypatch):
    called = {}

    def fake_get_site(site_id):
        called["site_id"] = site_id
        return object()

    monkeypatch.setattr(routes_documents.resolver, "get_site", fake_get_site)
    monkeypatch.setattr(
        routes_documents,
        "remove_active_upload_by_source_id",
        lambda *, site_id, source_id: called.update({"removed_site_id": site_id, "source_id": source_id}) or True,
    )
    monkeypatch.setattr(routes_documents, "list_active_documents", lambda site_id: [])

    response = TestClient(app).delete(
        "/api/documents/active/src_upload_test?site_id=demo_site",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == []
    assert called == {
        "site_id": "demo_site",
        "removed_site_id": "demo_site",
        "source_id": "src_upload_test",
    }


def test_update_active_document_type_updates_queue(monkeypatch):
    called = {}

    def fake_get_site(site_id):
        called["site_id"] = site_id
        return object()

    monkeypatch.setattr(routes_documents.resolver, "get_site", fake_get_site)
    monkeypatch.setattr(
        routes_documents,
        "update_active_upload_subtype",
        lambda *, site_id, source_id, source_subtype: called.update(
            {"updated_site_id": site_id, "source_id": source_id, "source_subtype": source_subtype}
        )
        or True,
    )
    monkeypatch.setattr(routes_documents.source_registry, "refresh_snapshot", lambda: [])
    monkeypatch.setattr(routes_documents, "list_active_documents", lambda site_id: [])

    response = TestClient(app).patch(
        "/api/documents/active/src_upload_test?site_id=demo_site",
        headers=AUTH_HEADERS,
        json={"source_subtype": "drawing_or_plan"},
    )

    assert response.status_code == 200
    assert response.json() == []
    assert called == {
        "site_id": "demo_site",
        "updated_site_id": "demo_site",
        "source_id": "src_upload_test",
        "source_subtype": "drawing_or_plan",
    }


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
