from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


UsageSource = Literal["mock", "provider_reported", "estimated"]
GenerationMode = Literal["mock", "real"]


class TokenUsage(BaseModel):
    generation_mode: GenerationMode
    llm_provider: str
    llm_model: str | None = None
    external_llm_called: bool = False
    request_count: int = 0
    input_tokens_estimated: int = 0
    output_tokens_estimated: int = 0
    total_tokens_estimated: int = 0
    input_tokens_reported: int | None = None
    output_tokens_reported: int | None = None
    total_tokens_reported: int | None = None
    usage_source: UsageSource = "estimated"
    created_at: datetime = Field(default_factory=datetime.utcnow)
