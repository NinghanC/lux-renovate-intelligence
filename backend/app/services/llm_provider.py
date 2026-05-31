import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.schemas import DossierDraft


class LLMConfigurationError(RuntimeError):
    pass


class LLMGenerationError(RuntimeError):
    pass


class LLMProvider:
    """OpenAI-compatible chat completions client."""

    def __init__(
        self,
        api_key: str | None = settings.llm_api_key,
        base_url: str | None = settings.llm_base_url,
        model: str | None = settings.llm_model,
        response_format: str | None = settings.llm_response_format,
        timeout_seconds: int = settings.llm_timeout_seconds,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.response_format = response_format
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def generate_draft(self, *, system_prompt: str, user_prompt: str) -> DossierDraft:
        if not self.configured:
            raise LLMConfigurationError(
                "LLM is not configured. Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in .env."
            )
        endpoint = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return DossierDraft.model_validate(json.loads(extract_json_object(content)))
        except httpx.HTTPError as exc:
            raise LLMGenerationError(f"LLM request failed: {exc}") from exc
        except (KeyError, json.JSONDecodeError, ValueError) as exc:
            raise LLMGenerationError(f"LLM response was not valid dossier JSON: {exc}") from exc


def extract_json_object(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found in LLM response", stripped, 0)
    return stripped[start : end + 1]
