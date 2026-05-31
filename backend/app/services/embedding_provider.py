import math
from typing import Any

import httpx

from app.core.config import settings


class EmbeddingProvider:
    """OpenAI-compatible embedding client.

    The provider is intentionally optional: without EMBEDDING_* configuration,
    retrieval falls back to keyword scoring.
    """

    def __init__(
        self,
        api_key: str | None = settings.embedding_api_key,
        base_url: str | None = settings.embedding_base_url,
        model: str | None = settings.embedding_model,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.configured:
            raise RuntimeError("Embedding provider is not configured")
        endpoint = f"{self.base_url}/embeddings"
        payload: dict[str, Any] = {"model": self.model, "input": texts}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=60) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)

