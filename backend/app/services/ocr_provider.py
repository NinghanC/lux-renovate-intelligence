import base64
import re
from typing import Any

import httpx

from app.core.config import aws_credentials_available, settings


class OCRProvider:
    """OCR fallback for scanned PDF pages.

    OCR is disabled by default for the public demo. Provider-specific adapters
    can be enabled through local environment variables when needed.
    """

    def __init__(
        self,
        provider: str = settings.ocr_provider,
        api_key: str | None = settings.ocr_api_key,
        base_url: str | None = settings.ocr_base_url,
        model: str | None = settings.ocr_model,
        aws_region: str = settings.ocr_aws_region,
        timeout_seconds: int = settings.ocr_timeout_seconds,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.aws_region = aws_region
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        if self.provider == "aws_textract":
            return bool(self.aws_region and aws_credentials_available())
        return bool(self.api_key and self.base_url and self.model)

    def extract_text_from_png(self, image_bytes: bytes) -> str:
        if not self.configured:
            return ""
        if self.provider == "aws_textract":
            return self._extract_text_with_textract(image_bytes)
        return self._extract_text_with_vision_model(image_bytes)

    def _extract_text_with_textract(self, image_bytes: bytes) -> str:
        try:
            import boto3
        except ImportError:
            return ""
        try:
            client = boto3.client("textract", region_name=self.aws_region)
            response = client.detect_document_text(Document={"Bytes": image_bytes})
            return _textract_plain_text(response)
        except Exception:
            return ""

    def _extract_text_with_vision_model(self, image_bytes: bytes) -> str:
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


def _textract_plain_text(response: dict[str, Any]) -> str:
    lines = [
        block.get("Text", "").strip()
        for block in response.get("Blocks", [])
        if block.get("BlockType") == "LINE" and block.get("Text")
    ]
    return "\n".join(line for line in lines if line)


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
