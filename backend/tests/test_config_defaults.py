from app.core.config import _effective_llm_mock_mode, _env_flag


def test_missing_llm_mock_mode_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("LLM_MOCK_MODE", raising=False)

    assert _env_flag("LLM_MOCK_MODE", "true") is True


def test_mock_provider_forces_effective_mock_mode():
    assert _effective_llm_mock_mode("mock", False) is True


def test_real_provider_can_disable_mock_mode():
    assert _effective_llm_mock_mode("openai_compatible", False) is False
