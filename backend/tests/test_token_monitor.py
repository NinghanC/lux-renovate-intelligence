from datetime import timezone

from app.models.usage import TokenUsage
from app.services.token_monitor import build_mock_usage, build_real_usage, estimate_tokens, parse_provider_usage


def test_estimate_tokens_uses_simple_character_heuristic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_parse_provider_usage_maps_openai_compatible_fields():
    usage = parse_provider_usage(
        {
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            }
        }
    )

    assert usage == {
        "input_tokens_reported": 12,
        "output_tokens_reported": 8,
        "total_tokens_reported": 20,
    }


def test_build_real_usage_prefers_provider_reported_usage():
    usage = build_real_usage(
        provider="openai_compatible",
        model="demo-model",
        system_prompt="system",
        user_prompt="user",
        response_text='{"ok": true}',
        response_payload={"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
    )

    assert usage.generation_mode == "real"
    assert usage.external_llm_called is True
    assert usage.request_count == 1
    assert usage.total_tokens_reported == 15
    assert usage.usage_source == "provider_reported"


def test_build_real_usage_falls_back_to_estimated_usage():
    usage = build_real_usage(
        provider="openai_compatible",
        model="demo-model",
        system_prompt="system",
        user_prompt="user",
        response_text='{"ok": true}',
        response_payload={},
    )

    assert usage.total_tokens_reported is None
    assert usage.total_tokens_estimated > 0
    assert usage.usage_source == "estimated"


def test_mock_usage_reports_zero_external_tokens():
    usage = build_mock_usage()

    assert usage.generation_mode == "mock"
    assert usage.external_llm_called is False
    assert usage.request_count == 0
    assert usage.total_tokens_estimated == 0
    assert usage.total_tokens_reported is None
    assert usage.usage_source == "mock"


def test_token_usage_default_timestamp_is_timezone_aware_utc():
    usage = TokenUsage(generation_mode="mock", llm_provider="mock")

    assert usage.created_at.tzinfo is not None
    assert usage.created_at.utcoffset() == timezone.utc.utcoffset(usage.created_at)
