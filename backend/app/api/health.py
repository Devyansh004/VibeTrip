"""Health check endpoint providing environment readiness and integration statuses."""

from fastapi import APIRouter, Depends
from app.config import Settings, get_settings
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return application health, version, and external service integration statuses."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
        integrations=settings.get_integration_statuses(),
    )
