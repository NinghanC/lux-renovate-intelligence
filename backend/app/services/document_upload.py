from pathlib import Path
from uuid import uuid4

from app.core.paths import RAW_UPLOADS_DIR
from app.models.schemas import UploadResponse
from app.services.evidence_metadata import modality_for_path, normalize_upload_subtype, write_upload_metadata
from app.services.planning_ingestion import register_active_upload
from app.services.source_registry import source_id_for_document


SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}


def save_and_chunk_upload(
    *,
    filename: str,
    content: bytes,
    site_id: str | None,
    commune: str,
    source_subtype: str | None = None,
    replace_active_documents: bool = False,
) -> UploadResponse:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported upload type '{suffix}'. Use PDF, TXT, or Markdown.")
    document_id = f"upload_{uuid4().hex[:12]}"
    safe_name = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
    resolved_subtype = normalize_upload_subtype(
        source_subtype,
        filename,
        content[:4096].decode("utf-8", errors="ignore"),
    )
    site_prefix = site_id or "global"
    target_path = RAW_UPLOADS_DIR / f"{site_prefix}_{document_id}_{safe_name}"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    source_id = source_id_for_document(f"upload_{target_path.stem}")
    write_upload_metadata(
        target_path,
        {
            "document_id": f"upload_{target_path.stem}",
            "upload_document_id": document_id,
            "source_id": source_id,
            "source_subtype": resolved_subtype,
            "original_filename": filename,
            "site_id": site_id,
            "commune": commune,
            "modality": modality_for_path(target_path),
        },
    )
    register_active_upload(site_id=site_id, path=target_path, replace_active=replace_active_documents)
    return UploadResponse(
        document_id=document_id,
        source_id=source_id,
        document_type="uploaded",
        source_subtype=resolved_subtype,
        modality=modality_for_path(target_path),
        filename=filename,
        chunks_created=0,
        chunks=[],
    )
