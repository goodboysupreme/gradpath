from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import get_analysis_provider
from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.config import Settings, get_settings
from app.providers.base import AnalysisProvider


def create_app(
    *,
    settings: Settings | None = None,
    analysis_provider: AnalysisProvider | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title=active_settings.app_name, version=active_settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(v1_router, prefix="/api/v1")

    if settings is not None:

        def settings_override() -> Settings:
            return active_settings

        app.dependency_overrides[get_settings] = settings_override

    if analysis_provider is not None:

        def provider_override() -> AnalysisProvider:
            return analysis_provider

        app.dependency_overrides[get_analysis_provider] = provider_override
    return app


app = create_app()
