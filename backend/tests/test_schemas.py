"""Unit tests for Pydantic request and response schemas."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.schemas.planning import (
    TravelPlanRequest,
    TravelPlanResponse,
    ExtractedPreferences,
    PersonalizePlanRequest,
)
from app.schemas.places import PlaceRecommendation
from app.schemas.itinerary import DayItinerary, ItineraryActivity


def test_valid_plan_request_with_duration():
    """Verify TravelPlanRequest succeeds when valid duration_days is provided."""
    req = TravelPlanRequest(
        destination="Jaipur",
        duration_days=3,
        travelers=2,
        budget=5000.0,
        currency="INR",
        interests=["cafes", "architecture"],
        atmosphere=["artistic", "peaceful"],
        travel_pace="balanced",
    )
    assert req.destination == "Jaipur"
    assert req.duration_days == 3
    assert req.travelers == 2


def test_valid_plan_request_with_dates():
    """Verify TravelPlanRequest calculates duration correctly from date range."""
    req = TravelPlanRequest(
        destination="Kyoto",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 5),
        travelers=1,
    )
    assert req.destination == "Kyoto"
    assert req.duration_days == 5  # April 1 to 5 inclusive is 5 days


def test_invalid_dates_raises_error():
    """Verify TravelPlanRequest rejects end_date earlier than start_date."""
    with pytest.raises(ValidationError):
        TravelPlanRequest(
            destination="Paris",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 5),
        )


def test_missing_dates_and_duration_raises_error():
    """Verify TravelPlanRequest rejects requests without either duration or dates."""
    with pytest.raises(ValidationError):
        TravelPlanRequest(
            destination="Rome",
            travelers=1,
        )


def test_invalid_destination_raises_error():
    """Verify TravelPlanRequest rejects empty or single character destination."""
    with pytest.raises(ValidationError):
        TravelPlanRequest(
            destination=" ",
            duration_days=2,
        )


def test_place_recommendation_schema():
    """Verify PlaceRecommendation default fields and values."""
    place = PlaceRecommendation(
        place_id="geo_123",
        name="Art Cafe",
        category="Catering / Cafe",
        latitude=26.9124,
        longitude=75.7873,
    )
    assert place.place_id == "geo_123"
    assert place.data_source == "geoapify"
    assert place.is_estimate is False


def test_itinerary_activity_schema():
    """Verify ItineraryActivity schema validation."""
    act = ItineraryActivity(
        activity_id="act_1_1",
        title="Morning Tea at Heritage Cafe",
        description="Relaxed start with masala chai.",
        day_number=1,
        estimated_duration_minutes=45,
        estimated_cost=5.0,
        currency="USD",
        is_estimate=True,
    )
    assert act.day_number == 1
    assert act.is_estimate is True


def test_personalize_plan_request_valid_with_trip_id():
    """Verify PersonalizePlanRequest validates with valid instructions and trip_id."""
    req = PersonalizePlanRequest(
        instructions="Keep walking minimal and add an art cafe on day 1",
        trip_id="trip-12345",
        selected_place_ids=["place_1", "place_2"],
        excluded_place_ids=["place_3"],
    )
    assert req.trip_id == "trip-12345"
    assert "walking minimal" in req.instructions
    assert len(req.selected_place_ids) == 2
    assert len(req.excluded_place_ids) == 1


def test_personalize_plan_request_valid_guest_mode():
    """Verify PersonalizePlanRequest validates with current_plan for guest mode."""
    mock_plan = TravelPlanResponse(
        trip_id="guest_1",
        destination="Kyoto",
        summary="A trip to Kyoto",
        preferences={"travel_pace": "balanced"},
        itinerary=[],
        integration_status={},
    )
    req = PersonalizePlanRequest(
        instructions="Focus on peaceful tea houses",
        current_plan=mock_plan,
        selected_place_ids=["geo_tea_house"],
    )
    assert req.current_plan is not None
    assert req.current_plan.destination == "Kyoto"
    assert req.selected_place_ids == ["geo_tea_house"]


def test_personalize_plan_request_short_instruction_rejected():
    """Verify PersonalizePlanRequest rejects instructions with fewer than 3 characters."""
    with pytest.raises(ValidationError):
        PersonalizePlanRequest(
            instructions="hi",
            trip_id="trip-1",
        )


def test_personalize_plan_request_long_instruction_rejected():
    """Verify PersonalizePlanRequest rejects instructions exceeding 1500 characters."""
    with pytest.raises(ValidationError):
        PersonalizePlanRequest(
            instructions="a" * 1501,
            trip_id="trip-1",
        )


def test_personalize_plan_request_conflicting_place_ids_rejected():
    """Verify PersonalizePlanRequest rejects overlapping selected and excluded IDs."""
    with pytest.raises(ValidationError) as exc_info:
        PersonalizePlanRequest(
            instructions="Make it more relaxed",
            trip_id="trip-1",
            selected_place_ids=["place_A", "place_B"],
            excluded_place_ids=["place_B", "place_C"],
        )
    assert "Conflicting place IDs" in str(exc_info.value)


def test_personalize_plan_request_missing_plan_and_id_rejected():
    """Verify PersonalizePlanRequest rejects request when neither current_plan nor trip_id is provided."""
    with pytest.raises(ValidationError):
        PersonalizePlanRequest(
            instructions="Make it more relaxed",
        )


def test_personalize_plan_request_deduplicates_place_ids():
    """Verify PersonalizePlanRequest strips whitespace and deduplicates IDs."""
    req = PersonalizePlanRequest(
        instructions="Include more quiet spots",
        trip_id="trip-1",
        selected_place_ids=[" place_A ", "place_A", "place_B "],
        excluded_place_ids=[" place_C ", "place_C"],
    )
    assert req.selected_place_ids == ["place_A", "place_B"]
    assert req.excluded_place_ids == ["place_C"]

