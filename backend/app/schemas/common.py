"""Common schema definitions for responses, errors, and health checks."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="healthy", description="Overall service status")
    version: str = Field(description="API version")
    environment: str = Field(description="Current running environment")
    integrations: Dict[str, str] = Field(
        description="Configuration and readiness status for each external service"
    )


class APIErrorDetail(BaseModel):
    """Detailed error object conforming to API standard."""
    message: str
    integration: Optional[str] = None
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class APIErrorResponse(BaseModel):
    """Standardized API error response format."""
    error: APIErrorDetail
