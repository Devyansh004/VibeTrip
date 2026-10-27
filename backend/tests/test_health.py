"""Unit tests for the health check endpoint."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify health endpoint returns 200 with sanitized integration statuses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert "integrations" in data
        
        integrations = data["integrations"]
        assert "qloo" in integrations
        assert "groq" in integrations
        assert "geoapify" in integrations
        assert "supabase" not in integrations
        # Verify no secret keys are leaked in health output
        for key, val in integrations.items():
            assert val in ["configured", "not_configured"]


@pytest.mark.asyncio
async def test_frontend_and_docs_endpoints():
    """Verify frontend index.html and FastAPI swagger docs are served properly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check Swagger docs
        docs_res = await client.get("/docs")
        assert docs_res.status_code == 200

        # Check frontend root
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert "VibeTrip" in root_res.text
