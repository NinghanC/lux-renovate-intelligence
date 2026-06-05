from app.core.config import _api_auth_token, _effective_llm_mock_mode, _env_flag


def test_missing_llm_mock_mode_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv("LLM_MOCK_MODE", raising=False)

    assert _env_flag("LLM_MOCK_MODE", "true") is True


def test_mock_provider_forces_effective_mock_mode():
    assert _effective_llm_mock_mode("mock", False) is True


def test_real_provider_can_disable_mock_mode():
    assert _effective_llm_mock_mode("openai_compatible", False) is False


def test_missing_api_auth_token_is_unconfigured(monkeypatch):
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)

    assert _api_auth_token() is None


def test_empty_api_auth_token_is_treated_as_unconfigured(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "")

    assert _api_auth_token() is None
