from pathlib import Path

from app.api.routes_documents import _is_allowed_source_path
from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR


def test_document_source_path_allowlist():
    assert _is_allowed_source_path(RAW_PLANNING_DIR / "sample.pdf")
    assert _is_allowed_source_path(RAW_UPLOADS_DIR / "sample.pdf")
    assert not _is_allowed_source_path(Path(__file__))

