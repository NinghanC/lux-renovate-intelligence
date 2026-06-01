from fastapi import APIRouter, HTTPException

from app.models.schemas import Dossier, DossierGenerateRequest, DossierGenerateResponse
from app.services.document_retriever import DocumentRetriever
from app.services.dossier_generator import DossierGenerator
from app.services.dossier_store import DossierNotFoundError, load_dossier, save_dossier
from app.services.evidence_validator import ValidationFailure
from app.services.llm_provider import LLMConfigurationError, LLMGenerationError
from app.services.planning_ingestion import PlanningIngestionService
from app.services.site_resolver import SiteNotFoundError, SiteResolver
from app.services.source_registry import SourceRegistry
from app.services.taxonomy import load_taxonomy


router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])
resolver = SiteResolver()
retriever = DocumentRetriever()
source_registry = SourceRegistry()
generator = DossierGenerator(source_registry=source_registry)
ingestion = PlanningIngestionService()


DEFAULT_QUERY = (
    "renovation planning constraints existing drawings structural documentation fire safety "
    "building envelope humidity MEP energy hazardous materials accessibility site inspection"
)


@router.post("/generate", response_model=DossierGenerateResponse)
def generate_dossier(request: DossierGenerateRequest) -> DossierGenerateResponse:
    try:
        site_context = resolver.build_context(request.site_id)
        chunks = ingestion.load_generate_chunks(
            commune=site_context.commune,
            site_id=request.site_id,
            include_uploaded_documents=request.include_uploaded_documents,
        )
        retrieved = retriever.retrieve_from_chunks(
            chunks=chunks,
            commune=site_context.commune,
            query=request.query or DEFAULT_QUERY,
            limit=request.max_evidence,
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
        dossier = generator.generate(
            site_context=site_context,
            evidence=retrieved.results,
            taxonomy=load_taxonomy(),
        )
        source_registry.refresh_snapshot()
        save_dossier(dossier)
        return DossierGenerateResponse(dossier=dossier)
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
