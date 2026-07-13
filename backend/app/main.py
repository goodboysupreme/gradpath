from fastapi import FastAPI, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import get_analysis_provider
from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.config import Settings, get_settings
from app.middleware.document_body_limit import (
    DocumentBodyLimitMiddleware,
    RequestBodyLimitMiddleware,
)
from app.providers.base import AnalysisProvider
from app.services.document_executor import DocumentExtractionExecutor
from app.services.documents import MAX_REQUEST_BODY_BYTES
from app.services.job_sources import MAX_NORMALIZATION_BODY_BYTES


async def sanitized_request_validation_error(
    _request: Request,
    _error: Exception,
) -> Response:
    if not isinstance(_error, RequestValidationError):
        raise _error
    if _request.url.path == "/api/v1/job-descriptions/normalize":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Request validation failed"},
            headers={"Cache-Control": "no-store"},
        )
    return await request_validation_exception_handler(_request, _error)


def create_app(
    *,
    settings: Settings | None = None,
    analysis_provider: AnalysisProvider | None = None,
    document_extraction_executor: DocumentExtractionExecutor | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title=active_settings.app_name, version=active_settings.app_version)
    app.add_exception_handler(
        RequestValidationError,
        sanitized_request_validation_error,
    )
    app.state.document_extraction_executor = (
        document_extraction_executor or DocumentExtractionExecutor()
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_middleware(
        DocumentBodyLimitMiddleware,
        path="/api/v1/documents/extract",
        max_body_bytes=MAX_REQUEST_BODY_BYTES,
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        path="/api/v1/job-descriptions/normalize",
        max_body_bytes=MAX_NORMALIZATION_BODY_BYTES,
        detail="Request body exceeds the JD normalization limit",
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
