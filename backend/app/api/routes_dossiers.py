from fastapi import APIRouter, HTTPException

from app.models.schemas import Dossier, DossierGenerateRequest, DossierGenerateResponse
from app.core.config import settings
from app.services.context_evidence import build_context_evidence
from app.services.document_retriever import DocumentRetriever
from app.services.dossier_generator import PROMPT_VERSION, DossierGenerator
from app.services.dossier_store import (
    DossierNotFoundError,
    cache_key_for_signature,
    load_cached_dossier,
    load_dossier,
    save_dossier,
    save_dossier_cache,
)
from app.services.evidence_validator import VALIDATOR_VERSION, ValidationFailure
from app.services.llm_provider import LLMConfigurationError, LLMGenerationError
from app.services.planning_ingestion import PlanningIngestionService
from app.services.geospatial import GeoJsonService
from app.services.readiness_rule_engine import READINESS_RULE_ENGINE_VERSION
from app.services.semantic_reviewer import SEMANTIC_REVIEW_VERSION
from app.services.site_resolver import SiteNotFoundError, SiteResolver
from app.services.source_registry import SourceRegistry
from app.services.taxonomy import TAXONOMY_VERSION, load_taxonomy, taxonomy_fingerprint


router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])
resolver = SiteResolver()
retriever = DocumentRetriever()
source_registry = SourceRegistry()
generator = DossierGenerator(source_registry=source_registry)
ingestion = PlanningIngestionService()
geojson_service = GeoJsonService()


DEFAULT_QUERY = (
    "renovation planning constraints existing drawings structural documentation fire safety "
    "building envelope humidity MEP energy hazardous materials accessibility site inspection"
)

PURPOSE_QUERIES = {
    "planning_context": "PAG PAP zoning planning constraints protected sector setbacks renovation permissions",
    "documentation_gaps": "existing drawings as-built records structural calculations fire safety approvals energy certificate hazardous materials survey",
    "technical_risk": "structural cracks humidity water infiltration MEP electrical heating roof facade hazardous materials old building risk signals",
    "site_inspection": "site inspection checklist basement moisture facade roof MEP fire safety accessibility egress verification",
    "renovation_constraints": "renovation scope constraints permits access logistics building envelope energy accessibility planning restrictions",
}


@router.post("/generate", response_model=DossierGenerateResponse)
def generate_dossier(request: DossierGenerateRequest) -> DossierGenerateResponse:
    try:
        site_context = resolver.build_context(request.site_id)
        cache_signature = build_generate_cache_signature(
            request=request,
            commune=site_context.commune,
        )
        cache_key = cache_key_for_signature(cache_signature)
        if not request.force_refresh:
            cached_dossier = load_cached_dossier(cache_key)
            if cached_dossier is not None:
                return DossierGenerateResponse(dossier=cached_dossier, cache_hit=True)

        chunks = ingestion.load_generate_chunks(
            commune=site_context.commune,
            site_id=request.site_id,
            include_uploaded_documents=request.include_uploaded_documents,
        )
        if request.query:
            retrieved = retriever.retrieve_from_chunks(
                chunks=chunks,
                commune=site_context.commune,
                query=request.query or DEFAULT_QUERY,
                limit=request.max_evidence,
                use_precomputed_embeddings=False,
            )
        else:
            retrieved = retriever.retrieve_for_purposes(
                chunks=chunks,
                commune=site_context.commune,
                purpose_queries=PURPOSE_QUERIES,
                limit_per_purpose=5,
                total_limit=request.max_evidence,
                use_precomputed_embeddings=False,
            )
        if not retrieved.results:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "no_evidence",
                    "detail": "No evidence was retrieved for this site and query.",
                    "hints": retrieved.limitations,
                },
            )
        site_geojson = geojson_service.build_site_geojson(
            site_id=request.site_id,
            coordinates=site_context.coordinates,
        )
        evidence = [
            *retrieved.results,
            *build_context_evidence(site_context, site_geojson),
        ]
        dossier = generator.generate(
            site_context=site_context,
            evidence=evidence,
            taxonomy=load_taxonomy(),
        )
        source_registry.refresh_snapshot()
        save_dossier(dossier)
        save_dossier_cache(cache_key, dossier, cache_signature)
        return DossierGenerateResponse(dossier=dossier, cache_hit=False)
    except SiteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_not_configured",
                "detail": str(exc),
                "hints": [
                    "Create a local .env file from .env.example.",
                    "Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL.",
                    "Embedding settings are optional; keyword retrieval works without them.",
                ],
            },
        ) from exc
    except (LLMGenerationError, ValidationFailure) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{dossier_id}", response_model=Dossier)
def get_dossier(dossier_id: str) -> Dossier:
    try:
        return load_dossier(dossier_id)
    except DossierNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def build_generate_cache_signature(*, request: DossierGenerateRequest, commune: str) -> dict:
    return {
        "cache_version": 3,
        "site_id": request.site_id,
        "commune": commune,
        "query": request.query or None,
        "include_uploaded_documents": request.include_uploaded_documents,
        "max_evidence": request.max_evidence,
        "generation_contract": {
            "prompt_version": PROMPT_VERSION,
            "readiness_rule_engine_version": READINESS_RULE_ENGINE_VERSION,
            "validator_version": VALIDATOR_VERSION,
            "semantic_review_version": SEMANTIC_REVIEW_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "taxonomy_fingerprint": taxonomy_fingerprint(),
        },
        "retrieval": {
            "mode": "custom_query" if request.query else "purpose_based",
            "purpose_queries": PURPOSE_QUERIES if not request.query else None,
            "keyword_bm25_k1": settings.keyword_bm25_k1,
            "keyword_bm25_b": settings.keyword_bm25_b,
            "multilingual_terms_enabled": settings.multilingual_query_terms_enabled,
            "multilingual_term_weight": settings.multilingual_query_term_weight,
        },
        "providers": {
            "llm_provider": settings.llm_provider,
            "llm_mock_mode": settings.llm_mock_mode,
            "llm_base_url": settings.llm_base_url,
            "llm_model": settings.llm_model,
            "llm_response_format": settings.llm_response_format,
            "semantic_review_provider": settings.semantic_review_provider,
            "semantic_review_configured": settings.semantic_review_configured,
            "semantic_review_base_url": settings.semantic_review_base_url,
            "semantic_review_model": settings.semantic_review_model,
            "semantic_review_response_format": settings.semantic_review_response_format,
            "embedding_configured": settings.embedding_configured,
            "embedding_base_url": settings.embedding_base_url,
            "embedding_model": settings.embedding_model,
            "rerank_configured": settings.rerank_configured,
            "rerank_provider": settings.rerank_provider,
            "rerank_model": settings.rerank_model,
            "rerank_top_n": settings.rerank_top_n,
            "ocr_configured": settings.ocr_configured,
            "ocr_provider": settings.ocr_provider,
            "ocr_model": settings.ocr_model,
        },
        "planning_sources": ingestion.planning_signature(commune),
        "uploaded_sources": ingestion.uploaded_signature(
            site_id=request.site_id,
            include_uploaded_documents=request.include_uploaded_documents,
        ),
    }
