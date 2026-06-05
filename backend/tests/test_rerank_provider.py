from app.models.schemas import PlanningChunk
from app.services.rerank_provider import RerankProvider


def test_bedrock_scores_map_indices_to_chunk_ids():
    chunks = [
        PlanningChunk(
            chunk_id="chunk_a",
            document_id="doc",
            document_name="doc",
            document_type="PAG",
            commune="Luxembourg",
            page=1,
            text="planning evidence",
            source_path="doc.pdf",
        ),
        PlanningChunk(
            chunk_id="chunk_b",
            document_id="doc",
            document_name="doc",
            document_type="PAG",
            commune="Luxembourg",
            page=1,
            text="fire safety evidence",
            source_path="doc.pdf",
        ),
    ]

    scores = RerankProvider._bedrock_scores(
        response={"results": [{"index": 1, "relevanceScore": 0.91}, {"index": 0, "relevanceScore": 0.23}]},
        chunks=chunks,
    )

    assert scores == {"chunk_b": 0.91, "chunk_a": 0.23}


def test_bedrock_model_id_becomes_foundation_model_arn():
    provider = RerankProvider(provider="aws_bedrock", model="example-rerank-model", aws_region="test-region-1")

    assert provider._bedrock_model_arn() == "arn:aws:bedrock:test-region-1::foundation-model/example-rerank-model"


def test_bedrock_rerank_requires_resolved_credentials(monkeypatch):
    monkeypatch.setattr("app.services.rerank_provider.aws_credentials_available", lambda: False)
    provider = RerankProvider(provider="aws_bedrock", model="example-rerank-model", aws_region="test-region-1")

    assert not provider.configured
