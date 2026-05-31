from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import RetrievedEvidence, UploadResponse
from app.services.document_retriever import DocumentRetriever
from app.services.document_upload import save_and_chunk_upload
from app.services.site_resolver import SiteNotFoundError, SiteResolver


router = APIRouter(prefix="/api", tags=["documents"])
resolver = SiteResolver()
retriever = DocumentRetriever()


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    site_id: str | None = Form(default=None),
    commune: str | None = Form(default=None),
) -> UploadResponse:
    try:
        resolved_commune = commune
        if site_id and not resolved_commune:
            resolved_commune = resolver.get_site(site_id).commune
        content = await file.read()
        return save_and_chunk_upload(
            filename=file.filename or "uploaded_document",
            content=content,
            site_id=site_id,
            commune=resolved_commune or "uploaded",
        )
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

