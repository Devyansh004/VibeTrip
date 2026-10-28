"""Automated regression and audit test suite covering settings, places, health, and orchestrator."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import Settings, is_valid_credential, get_settings, clear_settings_cache
from app.schemas.places import PlaceRecommendation
from app.schemas.planning import TravelPlanRequest, PersonalizePlanRequest, TravelPlanResponse
from app.schemas.itinerary import DayItinerary, ItineraryActivity
from app.services.geoapify_service import GeoapifyService
from app.services.orchestrator import TravelAgentOrchestrator
from app.dependencies import get_orchestrator, get_geoapify_service


# -----------------------------------------------------------------------------
# 1. Settings & Credential Safety Tests
# -----------------------------------------------------------------------------

def test_credential_validator_rejects_placeholders():
    """Verify placeholder strings and empty keys are never treated as valid credentials."""
    assert not is_valid_credential(None)
    assert not is_valid_credential("")
    assert not is_valid_credential("   ")
    assert not is_valid_credential("your_qloo_hackathon_key_here")
    assert not is_valid_credential("your_geoapify_key_here")
    assert not is_valid_credential("YOUR_GROQ_API_KEY_HERE")
    assert not is_valid_credential("your_api_key_here")
    assert not is_valid_credential("placeholder")
    assert not is_valid_credential("api_key_here")
    assert not is_valid_credential("xxx")
    assert not is_valid_credential("short")  # < 8 chars


def test_credential_validator_accepts_valid_keys():
    """Verify non-placeholder, sufficiently long keys are accepted."""
    assert is_valid_credential("gsk_test_groq_api_key_123456789")
    assert is_valid_credential("3791bd2f2bbe4c70bea1f224d031deb6")
    assert is_valid_credential("hack_6f6bf94aa91a4a3fbd4d689eaaa5d3b97decea51")


def test_settings_placeholder_detection():
    """Verify Settings object flags placeholder keys as not configured."""
    s = Settings(
        qloo_api_key="your_qloo_hackathon_key_here",
        geoapify_api_key="your_geoapify_key_here",
        groq_api_key="your_groq_api_key_here",
    )
    assert not s.is_qloo_configured
    assert not s.is_geoapify_configured
    assert not s.is_groq_configured
    assert s.get_integration_statuses() == {
        "qloo": "not_configured",
        "geoapify": "not_configured",
        "groq": "not_configured",
    }


def test_settings_valid_keys():
    """Verify Settings object flags real keys as configured."""
    s = Settings(
        qloo_api_key="hack_valid_qloo_key_12345",
        geoapify_api_key="geo_valid_places_key_12345",
        groq_api_key="gsk_valid_groq_reasoning_key_12345",
    )
    assert s.is_qloo_configured
    assert s.is_geoapify_configured
    assert s.is_groq_configured
    assert s.get_integration_statuses() == {
        "qloo": "configured",
        "geoapify": "configured",
        "groq": "configured",
    }


def test_clear_settings_cache():
    """Verify clear_settings_cache properly clears the LRU cache."""
    clear_settings_cache()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    clear_settings_cache()


# -----------------------------------------------------------------------------
# 2. Health Endpoint Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_endpoint_contract():
    """Verify /api/health schema and secret safety."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert "integrations" in data
        for service, status_val in data["integrations"].items():
            assert status_val in ("configured", "not_configured")
            # Verify no secret value is leaked
            assert "gsk_" not in status_val
            assert "hack_" not in status_val


# -----------------------------------------------------------------------------
# 3. Places Router Tests (/api/places/search)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_places_search_with_coordinates():
    """Verify /api/places/search works with valid geographic coordinates."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = True
    mock_place = PlaceRecommendation(
        place_id="place_jaipur_1",
        name="Hawa Mahal Cafe",
        category="Catering / Cafe",
        address="Badi Choupad, Jaipur",
        latitude=26.9239,
        longitude=75.8267,
    )
    mock_geo.search_places = AsyncMock(return_value=[mock_place])
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "latitude": 26.9239,
            "longitude": 75.8267,
            "categories": ["catering.cafe"],
            "radius_meters": 3000,
            "limit": 5,
        }
        res = await client.post("/api/places/search", json=payload)
        assert res.status_code == 200
        places = res.json()
        assert len(places) == 1
        assert places[0]["place_id"] == "place_jaipur_1"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_places_search_with_location_string():
    """Verify /api/places/search geocodes location when coordinates are omitted."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = True
    mock_geo.geocode_location = AsyncMock(return_value={
        "latitude": 35.0116,
        "longitude": 135.7681,
        "formatted": "Kyoto, Japan",
    })
    mock_place = PlaceRecommendation(
        place_id="place_kyoto_1",
        name="Kamo River Tea House",
        category="Catering / Cafe",
    )
    mock_geo.search_places = AsyncMock(return_value=[mock_place])
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "location": "Kyoto, Japan",
            "categories": ["catering.cafe"],
        }
        res = await client.post("/api/places/search", json=payload)
        assert res.status_code == 200
        places = res.json()
        assert len(places) == 1
        assert places[0]["place_id"] == "place_kyoto_1"
        assert mock_geo.geocode_location.called

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_places_search_missing_coordinates_and_location():
    """Verify /api/places/search returns 400 when neither coordinates nor location string provided."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = True
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/places/search", json={})
        assert res.status_code == 400
        assert "Either valid coordinates" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_places_search_empty_location_string():
    """Verify /api/places/search returns 400 when location string is empty or whitespace."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = True
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/places/search", json={"location": "   "})
        assert res.status_code == 400
        assert "Either valid coordinates" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_places_search_geocoding_not_found():
    """Verify /api/places/search returns 404 when location string cannot be geocoded."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = True
    mock_geo.geocode_location = AsyncMock(return_value=None)
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/places/search", json={"location": "NonExistentCityXYZ12345"})
        assert res.status_code == 404
        assert "Unable to geocode" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_places_search_unconfigured_service():
    """Verify /api/places/search returns 503 when Geoapify is not configured."""
    mock_geo = MagicMock(spec=GeoapifyService)
    mock_geo.is_configured = False
    app.dependency_overrides[get_geoapify_service] = lambda: mock_geo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/places/search", json={"latitude": 10.0, "longitude": 20.0})
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["status"] == "not_configured"

    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# 4. Orchestrator Cache & Stale Warning Cleansing Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_personalize_cleans_stale_configuration_warnings():
    """Verify personalizing an itinerary cleans up stale unconfigured warnings if services are now active."""
    mock_settings = Settings(
        qloo_api_key="hack_valid_qloo_key_12345",
        geoapify_api_key="geo_valid_places_key_12345",
        groq_api_key="gsk_valid_groq_reasoning_key_12345",
    )
    orchestrator = TravelAgentOrchestrator(settings=mock_settings)

    base_plan = TravelPlanResponse(
        trip_id="trip-123",
        destination="Jaipur",
        summary="Old retreat",
        preferences={"interests": ["cafes"], "atmosphere": ["artistic"]},
        recommended_places=[],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Exploration",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1",
                        title="Morning Walk",
                        description="Walk through local bazaars",
                        day_number=1,
                    )
                ]
            )
        ],
        integration_status={
            "qloo": "not_configured",
            "geoapify": "not_configured",
            "groq": "not_configured",
        },
        warnings=[
            "Qloo API is not configured; taste intelligence insights could not be retrieved.",
            "Geoapify API is not configured; real-world venue coordinates cannot be fetched.",
            "A valid travel advisory note to preserve.",
        ],
    )

    req = PersonalizePlanRequest(
        instructions="Add a coffee stop in the morning",
        current_plan=base_plan,
    )

    # Mock groq.personalize_itinerary to return successful refinement
    orchestrator.groq.personalize_itinerary = AsyncMock(return_value={
        "summary": "Refined coffee retreat",
        "days": [
            {
                "day_number": 1,
                "theme": "Coffee & Exploration",
                "activities": [
                    {
                        "activity_id": "act_1",
                        "title": "Morning Coffee",
                        "description": "Artisan coffee tasting",
                        "day_number": 1,
                    }
                ]
            }
        ]
    })

    result = await orchestrator.personalize_trip(req)
    # Confirm stale warnings are pruned
    assert not any("qloo api is not configured" in w.lower() for w in result.warnings)
    assert not any("geoapify api is not configured" in w.lower() for w in result.warnings)
    # Confirm unrelated advisory note was preserved
    assert any("valid travel advisory note" in w for w in result.warnings)
    # Confirm integration statuses updated
    assert result.integration_status["groq"] == "success"
    assert result.integration_status["qloo"] == "configured"
    assert result.integration_status["geoapify"] == "configured"


@pytest.mark.asyncio
async def test_orchestrator_cache_bypass_on_stale_warning():
    """Verify orchestrator does not reuse a cached plan containing unconfigured warnings if services are active."""
    mock_settings = Settings(
        qloo_api_key="hack_valid_qloo_key_12345",
        geoapify_api_key="geo_valid_places_key_12345",
        groq_api_key="gsk_valid_groq_reasoning_key_12345",
    )
    orchestrator = TravelAgentOrchestrator(settings=mock_settings)
    TravelAgentOrchestrator.clear_cache()

    req = TravelPlanRequest(
        destination="Jaipur",
        duration_days=2,
        interests=["cafes"],
        atmosphere=["peaceful"],
    )

    # Seed cache with an artificially degraded plan containing unconfigured warning
    from app.services.orchestrator import _build_plan_cache_key, _itinerary_cache
    config_state = f"{orchestrator.qloo.is_configured}:{orchestrator.groq.is_configured}:{orchestrator.geoapify.is_configured}"
    cache_key = _build_plan_cache_key(req, config_state)
    _itinerary_cache[cache_key] = TravelPlanResponse(
        destination="Jaipur",
        summary="Stale unconfigured plan",
        preferences={},
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Fallback",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1",
                        title="Walk",
                        description="Walk around",
                        day_number=1,
                    )
                ]
            )
        ],
        integration_status={"qloo": "not_configured"},
        warnings=["Qloo API is not configured; taste intelligence insights could not be retrieved."],
    )

    # Mock the services to return valid live response
    orchestrator.qloo.get_taste_insights = AsyncMock(return_value={"status": "success", "affinity_categories": []})
    orchestrator.geoapify.geocode_location = AsyncMock(return_value={"latitude": 26.9, "longitude": 75.8})
    orchestrator.geoapify.search_places = AsyncMock(return_value=[])
    orchestrator.groq.generate_itinerary = AsyncMock(return_value={
        "summary": "Fresh live plan",
        "days": [
            {
                "day_number": 1,
                "theme": "Live Vibe",
                "activities": [
                    {
                        "activity_id": "act_1",
                        "title": "Live Venue",
                        "description": "Freshly generated",
                        "day_number": 1,
                    }
                ]
            }
        ]
    })

    fresh_result = await orchestrator.plan_trip(req)
    # Should bypass stale cached plan and generate fresh one
    assert fresh_result.summary == "Fresh live plan"
    assert not any("qloo api is not configured" in w.lower() for w in fresh_result.warnings)
