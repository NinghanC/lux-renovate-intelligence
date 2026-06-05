import httpx

from app.services.ocr_provider import OCRProvider, _textract_plain_text


def test_textract_plain_text_keeps_line_order():
    response = {
        "Blocks": [
            {"BlockType": "WORD", "Text": "Ignored"},
            {"BlockType": "LINE", "Text": "First line"},
            {"BlockType": "LINE", "Text": "Second line"},
        ]
    }

    assert _textract_plain_text(response) == "First line\nSecond line"


def test_aws_textract_provider_requires_resolved_credentials(monkeypatch):
    monkeypatch.setattr("app.services.ocr_provider.aws_credentials_available", lambda: True)
    provider = OCRProvider(provider="aws_textract", aws_region="test-region-1")

    assert provider.configured


def test_aws_textract_provider_is_not_configured_without_credentials(monkeypatch):
    monkeypatch.setattr("app.services.ocr_provider.aws_credentials_available", lambda: False)
    provider = OCRProvider(provider="aws_textract", aws_region="test-region-1")

    assert not provider.configured


def test_databricks_vision_provider_requires_model_endpoint_and_key():
    provider = OCRProvider(
        provider="databricks_vision",
        api_key="token",
        base_url="https://example.invalid/openai-compatible",
        model="example-vision-model",
    )

    assert provider.configured


def test_vision_ocr_provider_retries_transient_status(monkeypatch):
    calls = []

    class FakeResponse:
        text = ""

        def __init__(self, status_code: int):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "failed",
                    request=httpx.Request("POST", "https://example.test"),
                    response=httpx.Response(self.status_code),
                )

        def json(self):
            return {"choices": [{"message": {"content": "OCR retry text"}}]}

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def post(self, endpoint, *, json, headers):
            calls.append(endpoint)
            return FakeResponse(503 if len(calls) == 1 else 200)

    monkeypatch.setattr("app.services.ocr_provider.httpx.Client", FakeClient)
    provider = OCRProvider(
        provider="databricks_vision",
        api_key="token",
        base_url="https://example.test",
        model="vision-model",
    )

    assert provider.extract_text_from_png(b"fake-png") == "OCR retry text"
    assert len(calls) == 2
