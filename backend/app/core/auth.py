import secrets

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not settings.api_auth_enabled:
        return
    if not settings.api_auth_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is enabled but API_AUTH_TOKEN is not configured.",
        )

    del request
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key.")
    if not secrets.compare_digest(x_api_key, settings.api_auth_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key.")
