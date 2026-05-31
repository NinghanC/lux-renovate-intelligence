from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_configured": settings.llm_configured,
        "embedding_configured": settings.embedding_configured,
        "rerank_configured": settings.rerank_configured,
        "ocr_configured": settings.ocr_configured,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "ocr_model": settings.ocr_model,
    }
