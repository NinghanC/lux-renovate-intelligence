import os
from dataclasses import dataclass

from dotenv import load_dotenv

from app.core.paths import ROOT_DIR


load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "LuxRenovate Intelligence"
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_base_url: str | None = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_model: str | None = os.getenv("LLM_MODEL", "qwen3.6-flash")
    llm_response_format: str | None = os.getenv("LLM_RESPONSE_FORMAT") or None
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
    embedding_api_key: str | None = os.getenv("EMBEDDING_API_KEY")
    embedding_base_url: str | None = os.getenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    embedding_model: str | None = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
    rerank_api_key: str | None = os.getenv("RERANK_API_KEY") or os.getenv("LLM_API_KEY")
    rerank_endpoint: str = os.getenv(
        "RERANK_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    )
    rerank_model: str = os.getenv("RERANK_MODEL", "qwen3-rerank")
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "8"))
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if item.strip()
    )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_api_key and self.embedding_base_url and self.embedding_model)

    @property
    def rerank_configured(self) -> bool:
        return bool(self.rerank_api_key and self.rerank_endpoint and self.rerank_model)


settings = Settings()
