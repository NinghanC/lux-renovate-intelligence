import time
from collections.abc import Awaitable, Callable

import anyio
import httpx

from app.core.config import settings


RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_HTTP_EXCEPTIONS = (httpx.TimeoutException, httpx.NetworkError)


def post_with_retries(
    post: Callable[..., httpx.Response],
    *args,
    max_attempts: int = settings.external_api_max_attempts,
    retry_delay_seconds: float = settings.external_api_retry_delay_seconds,
    **kwargs,
) -> httpx.Response:
    attempts = max(1, max_attempts)
    last_exception: httpx.HTTPError | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = post(*args, **kwargs)
        except RETRYABLE_HTTP_EXCEPTIONS as exc:
            last_exception = exc
            if attempt == attempts:
                raise
            _sleep_before_retry(retry_delay_seconds)
            continue
        if _should_retry_status(response.status_code) and attempt < attempts:
            _sleep_before_retry(retry_delay_seconds)
            continue
        return response
    if last_exception:
        raise last_exception
    raise RuntimeError("External API retry loop ended without a response.")


async def async_post_with_retries(
    post: Callable[..., Awaitable[httpx.Response]],
    *args,
    max_attempts: int = settings.external_api_max_attempts,
    retry_delay_seconds: float = settings.external_api_retry_delay_seconds,
    **kwargs,
) -> httpx.Response:
    attempts = max(1, max_attempts)
    last_exception: httpx.HTTPError | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = await post(*args, **kwargs)
        except RETRYABLE_HTTP_EXCEPTIONS as exc:
            last_exception = exc
            if attempt == attempts:
                raise
            await _async_sleep_before_retry(retry_delay_seconds)
            continue
        if _should_retry_status(response.status_code) and attempt < attempts:
            await _async_sleep_before_retry(retry_delay_seconds)
            continue
        return response
    if last_exception:
        raise last_exception
    raise RuntimeError("External API retry loop ended without a response.")


def _should_retry_status(status_code: int) -> bool:
    return status_code in RETRYABLE_HTTP_STATUS_CODES


def _sleep_before_retry(delay_seconds: float) -> None:
    if delay_seconds > 0:
        time.sleep(delay_seconds)


async def _async_sleep_before_retry(delay_seconds: float) -> None:
    if delay_seconds > 0:
        await anyio.sleep(delay_seconds)
