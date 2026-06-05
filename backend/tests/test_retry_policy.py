import httpx
import pytest

from app.services.retry_policy import async_post_with_retries, post_with_retries


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_sync_retry_retries_transient_status_then_succeeds():
    calls = []

    def post():
        calls.append("call")
        return FakeResponse(503 if len(calls) == 1 else 200)

    response = post_with_retries(post, max_attempts=2, retry_delay_seconds=0)

    assert response.status_code == 200
    assert len(calls) == 2


def test_sync_retry_does_not_retry_non_transient_status():
    calls = []

    def post():
        calls.append("call")
        return FakeResponse(400)

    response = post_with_retries(post, max_attempts=3, retry_delay_seconds=0)

    assert response.status_code == 400
    assert len(calls) == 1


def test_sync_retry_retries_network_error_then_succeeds():
    calls = []

    def post():
        calls.append("call")
        if len(calls) == 1:
            raise httpx.ConnectError("temporary network error")
        return FakeResponse(200)

    response = post_with_retries(post, max_attempts=2, retry_delay_seconds=0)

    assert response.status_code == 200
    assert len(calls) == 2


@pytest.mark.anyio
async def test_async_retry_retries_transient_status_then_succeeds():
    calls = []

    async def post():
        calls.append("call")
        return FakeResponse(429 if len(calls) == 1 else 200)

    response = await async_post_with_retries(post, max_attempts=2, retry_delay_seconds=0)

    assert response.status_code == 200
    assert len(calls) == 2
