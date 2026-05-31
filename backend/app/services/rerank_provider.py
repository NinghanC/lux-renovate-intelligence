import httpx

from app.core.config import settings
from app.models.schemas import PlanningChunk


class RerankProvider:
    """DashScope native rerank adapter.

    Alibaba's text rerank API is not a chat-completions endpoint. It accepts
    one query plus candidate documents and returns relevance scores by index.
    """

    def __init__(
        self,
        api_key: str | None = settings.rerank_api_key,
        endpoint: str = settings.rerank_endpoint,
        model: str = settings.rerank_model,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.endpoint and self.model)

    def rerank(self, *, query: str, chunks: list[PlanningChunk], top_n: int) -> dict[str, float]:
        if not self.configured or not chunks:
            return {}
        payload = {
            "model": self.model,
            "input": {
                "query": query,
                "documents": [chunk.text for chunk in chunks],
            },
            "parameters": {
                "top_n": min(top_n, len(chunks)),
                "return_documents": False,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
        results = response.json().get("output", {}).get("results", [])
        scores: dict[str, float] = {}
        for result in results:
            index = result.get("index")
            if isinstance(index, int) and 0 <= index < len(chunks):
                scores[chunks[index].chunk_id] = float(result.get("relevance_score", 0.0))
        return scores

