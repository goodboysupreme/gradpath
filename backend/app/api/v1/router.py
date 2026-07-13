from fastapi import APIRouter

from app.api.v1 import catalog, coverage

router = APIRouter()
router.include_router(catalog.router)
router.include_router(coverage.router)
