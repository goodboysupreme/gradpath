from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.providers.base import AnalysisProvider
from app.providers.openrouter import OpenRouterAnalysisProvider

MIN_INTERNAL_TOKEN_LENGTH = 32


def get_analysis_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisProvider:
    return OpenRouterAnalysisProvider(settings)


def require_internal_authentication(
    settings: Annotated[Settings, Depends(get_settings)],
    internal_token: Annotated[
        str | None,
        Header(alias="X-GradPath-Internal-Token"),
    ] = None,
) -> None:
    configured_secret = settings.internal_api_token
    configured_token = (
        configured_secret.get_secret_value().strip() if configured_secret is not None else ""
    )
    if len(configured_token) < MIN_INTERNAL_TOKEN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API authentication is not configured",
        )
    if not compare_digest(internal_token or "", configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal authentication failed",
        )
