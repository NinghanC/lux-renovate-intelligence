import httpx

from app.services.embedding_provider import EmbeddingProvider


def test_embedding_provider_retries_transient_status(monkeypatch):
    calls = []

    class FakeResponse:
        text = ""

        def __init__(self, status_code: int):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("failed", request=httpx.Request("POST", "https://example.test"), response=httpx.Response(self.status_code))

        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

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

    monkeypatch.setattr("app.services.embedding_provider.httpx.Client", FakeClient)
    provider = EmbeddingProvider(api_key="token", base_url="https://example.test", model="embedding-model")

    assert provider.embed_texts(["hello"]) == [[0.1, 0.2]]
    assert len(calls) == 2
