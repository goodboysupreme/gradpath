from fastapi import APIRouter

from app.api.v1 import analysis, catalog, coverage, documents, job_sources

router = APIRouter()
router.include_router(analysis.router)
router.include_router(catalog.router)
router.include_router(coverage.router)
router.include_router(documents.router)
router.include_router(job_sources.router)
