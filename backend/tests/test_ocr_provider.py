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
    provider = OCRProvider(provider="aws_textract", aws_region="us-east-1")

    assert provider.configured


def test_aws_textract_provider_is_not_configured_without_credentials(monkeypatch):
    monkeypatch.setattr("app.services.ocr_provider.aws_credentials_available", lambda: False)
    provider = OCRProvider(provider="aws_textract", aws_region="us-east-1")

    assert not provider.configured


def test_databricks_vision_provider_requires_model_endpoint_and_key():
    provider = OCRProvider(
        provider="databricks_vision",
        api_key="token",
        base_url="https://example.databricks.com/serving-endpoints",
        model="databricks-llama-4-maverick",
    )

    assert provider.configured
