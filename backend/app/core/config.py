import os
from dataclasses import dataclass

from dotenv import load_dotenv

from app.core.paths import ROOT_DIR


load_dotenv(ROOT_DIR / ".env", override=False)


def _llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock")


def _effective_llm_mock_mode(provider: str, configured_mock_mode: bool) -> bool:
    return provider == "mock" or configured_mock_mode


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _llm_base_url() -> str:
    configured = os.getenv("LLM_BASE_URL")
    if configured:
        return configured
    return ""


def _rerank_provider() -> str:
    return os.getenv("RERANK_PROVIDER", "disabled")


def _rerank_model() -> str:
    configured = os.getenv("RERANK_MODEL")
    if configured:
        return configured
    return ""


def _embedding_base_url() -> str:
    configured = os.getenv("EMBEDDING_BASE_URL")
    if configured:
        return configured
    return _llm_base_url()


def _embedding_api_key() -> str | None:
    configured = os.getenv("EMBEDDING_API_KEY")
    if configured:
        return configured
    if _embedding_base_url() == _llm_base_url():
        return os.getenv("LLM_API_KEY")
    return None


def _ocr_provider() -> str:
    return os.getenv("OCR_PROVIDER", "disabled")


def _ocr_model() -> str:
    configured = os.getenv("OCR_MODEL")
    if configured:
        return configured
    if _ocr_provider() == "databricks_vision":
        return os.getenv("DATABRICKS_VISION_MODEL", "")
    return ""


def _ocr_base_url() -> str | None:
    configured = os.getenv("OCR_BASE_URL")
    if configured:
        return configured
    if _ocr_provider() == "databricks_vision":
        return _llm_base_url()
    return None


def _ocr_api_key() -> str | None:
    configured = os.getenv("OCR_API_KEY")
    if configured:
        return configured
    if _ocr_provider() == "databricks_vision":
        return os.getenv("LLM_API_KEY")
    return None


def _semantic_review_provider() -> str:
    return os.getenv("SEMANTIC_REVIEW_PROVIDER", "disabled")


def _semantic_review_base_url() -> str:
    return os.getenv("SEMANTIC_REVIEW_BASE_URL", "")


def _api_auth_token() -> str | None:
    if "API_AUTH_TOKEN" not in os.environ:
        return "dev-demo-token-change-me"
    return os.getenv("API_AUTH_TOKEN") or None


def aws_credentials_available() -> bool:
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return True
    profile = os.getenv("AWS_PROFILE")
    if not profile:
        return False
    try:
        import boto3
    except ImportError:
        return False
    try:
        from botocore.exceptions import BotoCoreError, ProfileNotFound
    except ImportError:
        BotoCoreError = RuntimeError
        ProfileNotFound = RuntimeError
    try:
        return boto3.Session(profile_name=profile).get_credentials() is not None
    except (BotoCoreError, ProfileNotFound):
        return False


@dataclass(frozen=True)
class Settings:
    app_name: str = "Building Mission Readiness Intelligence"
    api_auth_enabled: bool = _env_flag("API_AUTH_ENABLED", "true")
    api_auth_token: str | None = _api_auth_token()
    llm_provider: str = _llm_provider()
    llm_mock_mode: bool = _effective_llm_mock_mode(llm_provider, _env_flag("LLM_MOCK_MODE", "true"))
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_base_url: str | None = _llm_base_url()
    llm_model: str | None = os.getenv("LLM_MODEL") or None
    llm_response_format: str | None = os.getenv("LLM_RESPONSE_FORMAT") or None
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
    external_api_max_attempts: int = int(os.getenv("EXTERNAL_API_MAX_ATTEMPTS", "3"))
    external_api_retry_delay_seconds: float = float(os.getenv("EXTERNAL_API_RETRY_DELAY_SECONDS", "0.25"))
    upload_max_bytes: int = int(os.getenv("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
    semantic_review_provider: str = _semantic_review_provider()
    semantic_review_api_key: str | None = os.getenv("SEMANTIC_REVIEW_API_KEY")
    semantic_review_base_url: str | None = _semantic_review_base_url()
    semantic_review_model: str | None = os.getenv("SEMANTIC_REVIEW_MODEL") or None
    semantic_review_response_format: str | None = os.getenv("SEMANTIC_REVIEW_RESPONSE_FORMAT") or "json_object"
    semantic_review_timeout_seconds: int = int(os.getenv("SEMANTIC_REVIEW_TIMEOUT_SECONDS", "120"))
    embedding_api_key: str | None = _embedding_api_key()
    embedding_base_url: str | None = _embedding_base_url()
    embedding_model: str | None = os.getenv("EMBEDDING_MODEL") or None
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
    rerank_provider: str = _rerank_provider()
    rerank_model: str = _rerank_model()
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "8"))
    rerank_aws_region: str = os.getenv("RERANK_AWS_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "")
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token: str | None = os.getenv("AWS_SESSION_TOKEN")
    ocr_provider: str = _ocr_provider()
    ocr_api_key: str | None = _ocr_api_key()
    ocr_base_url: str | None = _ocr_base_url()
    ocr_model: str | None = _ocr_model()
    ocr_aws_region: str = os.getenv("OCR_AWS_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "")
    ocr_timeout_seconds: int = int(os.getenv("OCR_TIMEOUT_SECONDS", "120"))
    ocr_min_text_chars: int = int(os.getenv("OCR_MIN_TEXT_CHARS", "80"))
    ocr_render_dpi: int = int(os.getenv("OCR_RENDER_DPI", "144"))
    multilingual_query_terms_enabled: bool = os.getenv("MULTILINGUAL_QUERY_TERMS_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    multilingual_query_term_weight: float = float(os.getenv("MULTILINGUAL_QUERY_TERM_WEIGHT", "0.45"))
    keyword_bm25_k1: float = float(os.getenv("KEYWORD_BM25_K1", "1.4"))
    keyword_bm25_b: float = float(os.getenv("KEYWORD_BM25_B", "0.75"))
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if item.strip()
    )
    cors_allow_credentials: bool = _env_flag("CORS_ALLOW_CREDENTIALS", "false")
    cors_methods: tuple[str, ...] = tuple(
        item.strip().upper()
        for item in os.getenv("CORS_METHODS", "GET,POST").split(",")
        if item.strip()
    )
    cors_headers: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_HEADERS", "Content-Type,X-API-Key").split(",")
        if item.strip()
    )

    @property
    def llm_configured(self) -> bool:
        if self.llm_mock_mode or self.llm_provider == "mock":
            return True
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def semantic_review_configured(self) -> bool:
        if self.semantic_review_provider == "disabled":
            return False
        return bool(
            self.semantic_review_api_key
            and self.semantic_review_base_url
            and self.semantic_review_model
        )

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_api_key and self.embedding_base_url and self.embedding_model)

    @property
    def rerank_configured(self) -> bool:
        if self.rerank_provider == "aws_bedrock":
            return bool(self.rerank_model and self.rerank_aws_region and aws_credentials_available())
        return False

    @property
    def ocr_configured(self) -> bool:
        if self.ocr_provider == "aws_textract":
            return bool(self.ocr_aws_region and aws_credentials_available())
        if self.ocr_provider == "databricks_vision":
            return bool(self.ocr_api_key and self.ocr_base_url and self.ocr_model)
        return bool(self.ocr_api_key and self.ocr_base_url and self.ocr_model)


settings = Settings()
