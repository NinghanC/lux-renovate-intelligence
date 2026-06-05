from datetime import datetime, timezone
from typing import Any

from app.models.usage import TokenUsage


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def parse_provider_usage(payload: dict[str, Any]) -> dict[str, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {
            "input_tokens_reported": None,
            "output_tokens_reported": None,
            "total_tokens_reported": None,
        }
    input_tokens = _as_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    output_tokens = _as_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    total_tokens = _as_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens_reported": input_tokens,
        "output_tokens_reported": output_tokens,
        "total_tokens_reported": total_tokens,
    }


def build_real_usage(
    *,
    provider: str,
    model: str | None,
    system_prompt: str,
    user_prompt: str,
    response_text: str,
    response_payload: dict[str, Any],
) -> TokenUsage:
    input_estimate = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    output_estimate = estimate_tokens(response_text)
    reported = parse_provider_usage(response_payload)
    has_reported = reported["total_tokens_reported"] is not None
    return TokenUsage(
        generation_mode="real",
        llm_provider=provider,
        llm_model=model,
        external_llm_called=True,
        request_count=1,
        input_tokens_estimated=input_estimate,
        output_tokens_estimated=output_estimate,
        total_tokens_estimated=input_estimate + output_estimate,
        input_tokens_reported=reported["input_tokens_reported"],
        output_tokens_reported=reported["output_tokens_reported"],
        total_tokens_reported=reported["total_tokens_reported"],
        usage_source="provider_reported" if has_reported else "estimated",
        created_at=datetime.now(timezone.utc),
    )


def build_mock_usage() -> TokenUsage:
    return TokenUsage(
        generation_mode="mock",
        llm_provider="mock",
        llm_model="mock",
        external_llm_called=False,
        request_count=0,
        input_tokens_estimated=0,
        output_tokens_estimated=0,
        total_tokens_estimated=0,
        usage_source="mock",
        created_at=datetime.now(timezone.utc),
    )


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
