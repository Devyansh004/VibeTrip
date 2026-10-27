"""Unit tests for the planner endpoint and orchestrator workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.places import PlaceRecommendation
from app.services.orchestrator import TravelAgentOrchestrator
from app.dependencies import get_orchestrator


@pytest.mark.asyncio
async def test_planner_endpoint_with_fallback():
    """Verify /api/plan works gracefully even when external APIs are not configured."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "destination": "Jaipur",
            "duration_days": 2,
            "travelers": 1,
            "budget": 5000.0,
            "currency": "INR",
            "interests": ["cafes", "architecture", "photography"],
            "atmosphere": ["peaceful", "artistic"],
            "travel_pace": "relaxed",
            "additional_preferences": "I love indie music and vintage architecture.",
        }
        response = await client.post("/api/plan", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["destination"] == "Jaipur"
        assert len(data["itinerary"]) == 2
        assert "integration_status" in data
        assert "warnings" in data
        assert isinstance(data["warnings"], list)


@pytest.mark.asyncio
async def test_planner_with_mocked_integrations():
    """Verify orchestration correctly links verified places to itinerary activities."""
    mock_orchestrator = MagicMock(spec=TravelAgentOrchestrator)

    mock_place = PlaceRecommendation(
        place_id="mock_place_42",
        name="Indie Arts Cafe",
        category="Catering / Cafe",
        address="12 Hawa Mahal Rd, Jaipur",
        latitude=26.9239,
        longitude=75.8267,
        match_explanation="Aligns with your interest in cafes.",
        data_source="geoapify+qloo",
        is_estimate=False,
    )

    from app.schemas.planning import TravelPlanResponse
    from app.schemas.itinerary import DayItinerary, ItineraryActivity

    mock_response = TravelPlanResponse(
        trip_id="test-trip-uuid",
        destination="Jaipur",
        summary="A custom art-infused retreat in Jaipur.",
        preferences={"interests": ["cafes"], "atmosphere": ["artistic"]},
        taste_insights={"status": "success", "signals_used": ["cafes"]},
        recommended_places=[mock_place],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Artisan Exploration",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1_1",
                        title="Coffee at Indie Arts Cafe",
                        description="Start the morning soaking in local art.",
                        day_number=1,
                        time_label="Morning",
                        place_id="mock_place_42",
                        is_estimate=True,
                    )
                ],
            )
        ],
        integration_status={
            "qloo": "success",
            "groq": "success",
            "geoapify": "success",
        },
        warnings=[],
    )

    mock_orchestrator.plan_trip = AsyncMock(return_value=mock_response)

    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "destination": "Jaipur",
            "duration_days": 1,
            "interests": ["cafes"],
            "atmosphere": ["artistic"],
        }
        res = await client.post("/api/plan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["trip_id"] == "test-trip-uuid"
        assert len(data["recommended_places"]) == 1
        assert data["recommended_places"][0]["place_id"] == "mock_place_42"
        # Confirm grounding: activity references verified mock_place_42
        assert data["itinerary"][0]["activities"][0]["place_id"] == "mock_place_42"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_initial_planning_skips_extract_preferences():
    """Verify that initial trip planning does NOT call GroqService.extract_preferences."""
    from app.services.groq_service import GroqService
    from app.schemas.planning import TravelPlanRequest

    mock_groq = MagicMock(spec=GroqService)
    mock_groq.is_configured = True
    mock_groq.extract_preferences = AsyncMock()
    mock_groq.generate_itinerary = AsyncMock(return_value={
        "summary": "Direct plan without LLM extraction",
        "days": [
            {
                "day_number": 1,
                "theme": "Exploration",
                "activities": [
                    {
                        "activity_id": "act_1_1",
                        "title": "Visit Historic Spot",
                        "place_id": None,
                        "time_label": "Morning",
                    }
                ]
            }
        ]
    })

    orchestrator = TravelAgentOrchestrator(
        groq_service=mock_groq,
    )

    req = TravelPlanRequest(
        destination="Kyoto",
        duration_days=1,
        interests=["temples", "cafes"],
        atmosphere=["peaceful"],
        additional_preferences="Some extra preferences text",
    )

    result = await orchestrator.plan_trip(req)
    assert result.destination == "Kyoto"
    # CRITICAL: extract_preferences must NOT be called in the initial planning workflow
    mock_groq.extract_preferences.assert_not_called()
    assert mock_groq.generate_itinerary.called


@pytest.mark.asyncio
async def test_personalize_endpoint_success():
    """Verify POST /api/plan/personalize returns updated itinerary with mocked Groq output."""
    mock_orchestrator = MagicMock(spec=TravelAgentOrchestrator)

    from app.schemas.planning import TravelPlanResponse
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    from app.schemas.places import PlaceRecommendation

    mock_place = PlaceRecommendation(
        place_id="cafe_1",
        name="Art Cafe",
        category="Catering / Cafe",
    )

    mock_response = TravelPlanResponse(
        trip_id="test-personalized-id",
        destination="Jaipur",
        summary="A personalized art cafe journey.",
        preferences={"interests": ["cafes"]},
        recommended_places=[mock_place],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Cafe Immersion",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1_1",
                        title="Morning Art Cafe",
                        description="Start the morning at Art Cafe",
                        day_number=1,
                        time_label="Morning",
                        place_id="cafe_1",
                    )
                ]
            )
        ],
        integration_status={"groq": "success"},
        warnings=[],
    )

    mock_orchestrator.personalize_trip = AsyncMock(return_value=mock_response)
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "instructions": "Make morning focus on Art Cafe",
            "trip_id": "test-personalized-id",
            "selected_place_ids": ["cafe_1"],
            "excluded_place_ids": [],
        }
        res = await client.post("/api/plan/personalize", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["trip_id"] == "test-personalized-id"
        assert data["itinerary"][0]["activities"][0]["place_id"] == "cafe_1"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_personalize_endpoint_validation_error():
    """Verify POST /api/plan/personalize returns 422 for invalid requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Instruction too short
        payload = {
            "instructions": "no",
            "trip_id": "trip_1",
        }
        res = await client.post("/api/plan/personalize", json=payload)
        assert res.status_code == 422

