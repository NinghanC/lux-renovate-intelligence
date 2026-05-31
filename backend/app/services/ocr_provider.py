import base64
import re
from typing import Any

import httpx

from app.core.config import settings


class OCRProvider:
    """OpenAI-compatible Qwen OCR client for scanned PDF fallback."""

    def __init__(
        self,
        api_key: str | None = settings.ocr_api_key,
        base_url: str | None = settings.ocr_base_url,
        model: str | None = settings.ocr_model,
        timeout_seconds: int = settings.ocr_timeout_seconds,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def extract_text_from_png(self, image_bytes: bytes) -> str:
        if not self.configured:
            return ""
        endpoint = f"{self.base_url}/chat/completions"
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all readable text from this document page. "
                                "Preserve reading order. Return plain text only."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _plain_text(content)
        except Exception:
            return ""


def _plain_text(content: Any) -> str:
    if isinstance(content, str):
        return _strip_markdown_fence(content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return _strip_markdown_fence("\n".join(parts))
    return ""


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:text)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()
