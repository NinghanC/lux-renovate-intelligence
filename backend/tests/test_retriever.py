from app.models.schemas import PlanningChunk
from app.services.document_retriever import DocumentRetriever
from app.services.planning_ingestion import PlanningIngestionService


class DisabledEmbeddingProvider:
    configured = False


class DisabledRerankProvider:
    configured = False


def test_keyword_retrieval_returns_planning_evidence():
    chunks = PlanningIngestionService().load_planning_chunks_for_commune("Luxembourg")
    result = DocumentRetriever(
        embedding_provider=DisabledEmbeddingProvider(),
        rerank_provider=DisabledRerankProvider(),
    ).retrieve_from_chunks(
        chunks=chunks,
        commune="Luxembourg",
        query="Laangfur urban planning public space",
        limit=5,
        use_precomputed_embeddings=False,
    )

    assert result.results
    assert result.results[0].chunk_id
    assert result.results[0].page is not None


def test_multilingual_keyword_terms_expand_query():
    chunks = [
        PlanningChunk(
            chunk_id="doc_p001_c001",
            document_id="doc",
            document_name="French fire note",
            document_type="PAG",
            commune="Luxembourg",
            page=1,
            text="Le dossier incendie et evacuation doit etre verifie avant les travaux.",
            source_path="planning.pdf",
        )
    ]

    result = DocumentRetriever(
        embedding_provider=DisabledEmbeddingProvider(),
        rerank_provider=DisabledRerankProvider(),
    ).retrieve_from_chunks(
        chunks=chunks,
        commune="Luxembourg",
        query="fire safety",
        limit=1,
        use_precomputed_embeddings=False,
    )

    assert result.results
    assert "fire_safety_documentation" in result.results[0].supports
