from pathlib import Path
from uuid import uuid4

from app.core.paths import RAW_UPLOADS_DIR
from app.models.schemas import UploadResponse
from app.services.source_registry import source_id_for_document


SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}


def save_and_chunk_upload(
    *,
    filename: str,
    content: bytes,
    site_id: str | None,
    commune: str,
) -> UploadResponse:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported upload type '{suffix}'. Use PDF, TXT, or Markdown.")
    document_id = f"upload_{uuid4().hex[:12]}"
    safe_name = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
    site_prefix = site_id or "global"
    target_path = RAW_UPLOADS_DIR / f"{site_prefix}_{document_id}_{safe_name}"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    return UploadResponse(
        document_id=document_id,
        source_id=source_id_for_document(f"upload_{target_path.stem}"),
        document_type="uploaded",
        filename=filename,
        chunks_created=0,
        chunks=[],
    )
