import secrets

from fastapi import Header, HTTPException, Query, Request, status

from app.core.config import settings


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = Query(default=None),
) -> None:
    if not settings.api_auth_enabled:
        return
    if not settings.api_auth_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is enabled but API_AUTH_TOKEN is not configured.",
        )

    candidate = x_api_key
    if candidate is None and request.url.path.endswith("/file"):
        candidate = api_key
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key.")
    if not secrets.compare_digest(candidate, settings.api_auth_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key.")
