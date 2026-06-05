from app.models.schemas import PlanningChunk
from app.services.document_retriever import DocumentRetriever
from app.services.planning_ingestion import PlanningIngestionService


class DisabledEmbeddingProvider:
    configured = False


class DisabledRerankProvider:
    configured = False

    def rerank(self, *, query, chunks, top_n):
        return {}


class BuggyEmbeddingProvider:
    configured = True

    def embed_texts(self, texts):
        raise AssertionError("programming bug")


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
    assert result.results[0].source_path is None


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


def test_purpose_based_retrieval_merges_results_and_tracks_purpose():
    chunks = [
        PlanningChunk(
            chunk_id="doc_p001_c001",
            document_id="doc",
            document_name="Planning note",
            document_type="PAG",
            commune="Luxembourg",
            page=1,
            text="Planning constraints and fire safety documents should be verified.",
            source_path="planning.pdf",
        )
    ]

    result = DocumentRetriever(
        embedding_provider=DisabledEmbeddingProvider(),
        rerank_provider=DisabledRerankProvider(),
    ).retrieve_for_purposes(
        chunks=chunks,
        commune="Luxembourg",
        purpose_queries={"planning": "planning constraints", "fire": "fire safety"},
        limit_per_purpose=1,
        total_limit=2,
        use_precomputed_embeddings=False,
    )

    assert len(result.results) == 1
    assert set(result.results[0].metadata["retrieval_purposes"]) == {"planning", "fire"}


def test_embedding_programming_errors_are_not_swallowed():
    chunks = [
        PlanningChunk(
            chunk_id="doc_p001_c001",
            document_id="doc",
            document_name="Planning note",
            document_type="PAG",
            commune="Luxembourg",
            page=1,
            text="Planning constraints.",
            source_path="planning.pdf",
        )
    ]

    try:
        DocumentRetriever(
            embedding_provider=BuggyEmbeddingProvider(),
            rerank_provider=DisabledRerankProvider(),
        ).retrieve_from_chunks(
            chunks=chunks,
            commune="Luxembourg",
            query="planning",
            limit=1,
            use_precomputed_embeddings=False,
        )
    except AssertionError as exc:
        assert "programming bug" in str(exc)
    else:
        raise AssertionError("Programming errors from embedding provider should propagate.")
