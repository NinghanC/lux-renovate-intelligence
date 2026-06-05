import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR
from app.models.schemas import RetrievedEvidence, SourceRecordPublic, UploadResponse
from app.services.document_retriever import DocumentRetriever
from app.services.document_upload import save_and_chunk_upload
from app.services.site_resolver import SiteNotFoundError, SiteResolver
from app.services.source_registry import SourceRegistry


router = APIRouter(prefix="/api", tags=["documents"])
resolver = SiteResolver()
retriever = DocumentRetriever()
source_registry = SourceRegistry()
MAX_UPLOAD_BYTES = settings.upload_max_bytes
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


def _is_allowed_source_path(path: Path) -> bool:
    resolved = path.resolve()
    allowed_roots = [RAW_PLANNING_DIR.resolve(), RAW_UPLOADS_DIR.resolve()]
    return any(resolved == root or root in resolved.parents for root in allowed_roots)


async def _read_upload_with_limit(
    file: UploadFile,
    *,
    max_bytes: int | None = None,
    chunk_bytes: int = UPLOAD_READ_CHUNK_BYTES,
) -> bytes:
    limit = MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_bytes)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UploadTooLargeError(f"Upload exceeds the {limit} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    site_id: str | None = Form(default=None),
    commune: str | None = Form(default=None),
    source_subtype: str | None = Form(default=None),
) -> UploadResponse:
    try:
        resolved_commune = commune
        if site_id and not resolved_commune:
            resolved_commune = resolver.get_site(site_id).commune
        content = await _read_upload_with_limit(file)
        return save_and_chunk_upload(
            filename=file.filename or "uploaded_document",
            content=content,
            site_id=site_id,
            commune=resolved_commune or "uploaded",
            source_subtype=source_subtype,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except (ValueError, SiteNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evidence", response_model=RetrievedEvidence)
def retrieve_evidence(
    site_id: str,
    query: str,
    limit: int = 8,
    include_uploaded_documents: bool = True,
) -> RetrievedEvidence:
    try:
        site = resolver.get_site(site_id)
    except SiteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return retriever.retrieve(
        commune=site.commune,
        site_id=site_id,
        query=query,
        limit=limit,
        include_uploaded=include_uploaded_documents,
    )


@router.get("/sources", response_model=list[SourceRecordPublic])
def list_sources(refresh: bool = False) -> list[SourceRecordPublic]:
    sources = source_registry.refresh_snapshot() if refresh else source_registry.list_sources()
    return [SourceRecordPublic.model_validate(source.model_dump()) for source in sources]


@router.get("/sources/{source_id}/file")
def get_source_file(source_id: str) -> FileResponse:
    source = source_registry.get_by_id(source_id)
    if source is None or not source.local_path:
        raise HTTPException(status_code=404, detail="Source file not found for this source.")
    resolved = Path(source.local_path)
    if not _is_allowed_source_path(resolved):
        raise HTTPException(status_code=403, detail="Source file is outside allowed data directories.")
    resolved = resolved.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Source file not found.")
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return FileResponse(
        resolved,
        media_type=media_type,
        filename=resolved.name,
        content_disposition_type="inline",
    )
