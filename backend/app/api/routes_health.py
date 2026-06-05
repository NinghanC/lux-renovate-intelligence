from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_provider": settings.llm_provider,
        "llm_mock_mode": settings.llm_mock_mode,
        "semantic_review_provider": settings.semantic_review_provider,
        "rerank_provider": settings.rerank_provider,
        "ocr_provider": settings.ocr_provider,
        "llm_configured": settings.llm_configured,
        "semantic_review_configured": settings.semantic_review_configured,
        "embedding_configured": settings.embedding_configured,
        "rerank_configured": settings.rerank_configured,
        "ocr_configured": settings.ocr_configured,
        "multilingual_query_terms_enabled": settings.multilingual_query_terms_enabled,
        "llm_model": settings.llm_model,
        "semantic_review_model": settings.semantic_review_model,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "rerank_aws_region": settings.rerank_aws_region if settings.rerank_provider == "aws_bedrock" else None,
        "ocr_model": settings.ocr_model,
        "ocr_aws_region": settings.ocr_aws_region if settings.ocr_provider == "aws_textract" else None,
    }
