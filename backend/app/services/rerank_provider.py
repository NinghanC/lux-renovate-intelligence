from typing import Any

from app.core.config import aws_credentials_available, settings
from app.models.schemas import PlanningChunk


class RerankProvider:
    """Optional AWS Bedrock rerank adapter using Cohere Rerank 3.5."""

    def __init__(
        self,
        provider: str = settings.rerank_provider,
        model: str = settings.rerank_model,
        aws_region: str = settings.rerank_aws_region,
    ):
        self.provider = provider
        self.model = model
        self.aws_region = aws_region

    @property
    def configured(self) -> bool:
        if self.provider == "aws_bedrock":
            return bool(self.model and self.aws_region and aws_credentials_available())
        return False

    def rerank(self, *, query: str, chunks: list[PlanningChunk], top_n: int) -> dict[str, float]:
        if not self.configured or not chunks:
            return {}
        if self.provider == "aws_bedrock":
            return self._rerank_bedrock(query=query, chunks=chunks, top_n=top_n)
        return {}

    def _rerank_bedrock(self, *, query: str, chunks: list[PlanningChunk], top_n: int) -> dict[str, float]:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("AWS Bedrock rerank requires boto3. Install project requirements.") from exc

        client = boto3.client("bedrock-agent-runtime", region_name=self.aws_region)
        response = client.rerank(
            queries=[
                {
                    "type": "TEXT",
                    "textQuery": {"text": query},
                }
            ],
            sources=[
                {
                    "type": "INLINE",
                    "inlineDocumentSource": {
                        "type": "TEXT",
                        "textDocument": {"text": chunk.text[:8000]},
                    },
                }
                for chunk in chunks
            ],
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "modelConfiguration": {"modelArn": self._bedrock_model_arn()},
                    "numberOfResults": min(top_n, len(chunks)),
                },
            },
        )
        return self._bedrock_scores(response=response, chunks=chunks)

    def _bedrock_model_arn(self) -> str:
        if self.model.startswith("arn:"):
            return self.model
        return f"arn:aws:bedrock:{self.aws_region}::foundation-model/{self.model}"

    @staticmethod
    def _bedrock_scores(*, response: dict[str, Any], chunks: list[PlanningChunk]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for result in response.get("results", []):
            index = result.get("index")
            score = result.get("relevanceScore", result.get("relevance_score"))
            if isinstance(index, int) and 0 <= index < len(chunks) and score is not None:
                scores[chunks[index].chunk_id] = float(score)
        return scores
