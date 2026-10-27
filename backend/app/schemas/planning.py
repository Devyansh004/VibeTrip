import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator

from app.schemas.places import PlaceRecommendation
from app.schemas.itinerary import DayItinerary


class TravelPlanRequest(BaseModel):
    """Input payload submitted by user to plan a personalized trip."""

    destination: str = Field(description="Destination city or region")
    start_date: Optional[datetime.date] = Field(default=None, description="Start date of the trip")
    end_date: Optional[datetime.date] = Field(default=None, description="End date of the trip")
    duration_days: Optional[int] = Field(
        default=None, ge=1, le=30, description="Total duration in days"
    )
    travelers: int = Field(default=1, ge=1, le=50, description="Number of travelers")
    budget: Optional[float] = Field(default=None, ge=0, description="Estimated total budget")
    currency: str = Field(default="USD", max_length=5, description="Currency code (e.g. USD, INR, EUR)")
    interests: List[str] = Field(
        default_factory=list, description="Selected interest tags (e.g. cafes, indie music)"
    )
    atmosphere: List[str] = Field(
        default_factory=list, description="Atmospheric preferences (e.g. peaceful, artistic)"
    )
    travel_pace: str = Field(
        default="balanced", description="Desired travel pace: relaxed, balanced, or packed"
    )
    additional_preferences: Optional[str] = Field(
        default=None, max_length=2000, description="Free-text personal vibe description"
    )

    @model_validator(mode="after")
    def validate_dates_and_duration(self) -> "TravelPlanRequest":
        # Normalize and validate destination
        self.destination = self.destination.strip()
        if len(self.destination) < 2:
            raise ValueError("Destination must be at least 2 characters long")

        # Validate travel pace
        valid_paces = {"relaxed", "balanced", "packed"}
        if self.travel_pace.lower() not in valid_paces:
            self.travel_pace = "balanced"

        # Check date and duration consistency
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("End date cannot be earlier than start date")
            calculated_days = (self.end_date - self.start_date).days + 1
            if calculated_days > 30:
                raise ValueError("Trip duration cannot exceed 30 days")
            if self.duration_days and self.duration_days != calculated_days:
                # Harmonize duration_days with the date range
                self.duration_days = calculated_days
            elif not self.duration_days:
                self.duration_days = calculated_days

        if not self.duration_days and not (self.start_date and self.end_date):
            raise ValueError(
                "Either duration_days or both start_date and end_date must be provided"
            )

        return self


class ExtractedPreferences(BaseModel):
    """Structured preferences parsed from free-text and selected options."""
    interests: List[str] = Field(default_factory=list)
    atmosphere: List[str] = Field(default_factory=list)
    travel_pace: str = Field(default="balanced")
    vibe_keywords: List[str] = Field(default_factory=list)
    budget_level: Optional[str] = Field(default=None)


class TravelPlanResponse(BaseModel):
    """Complete personalized travel plan response."""
    trip_id: Optional[str] = Field(default=None, description="Generated or persisted trip ID")
    destination: str = Field(description="Destination location")
    summary: str = Field(description="Personalized travel overview and synthesis")
    preferences: Dict[str, Any] = Field(description="Structured preferences used in generation")
    taste_insights: Optional[Dict[str, Any]] = Field(
        default=None, description="Qloo taste intelligence insights if available"
    )
    recommended_places: List[PlaceRecommendation] = Field(
        default_factory=list, description="Curated places discovered and ranked"
    )
    itinerary: List[DayItinerary] = Field(
        default_factory=list, description="Day-by-day scheduled activities"
    )
    estimated_budget: Optional[Dict[str, Any]] = Field(
        default=None, description="Budget breakdown and cost estimates"
    )
    integration_status: Dict[str, str] = Field(
        description="Execution status for each service (success, failed, skipped, not_configured)"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Any advisory warnings or degradation notices"
    )


class PersonalizePlanRequest(BaseModel):
    """Payload submitted by user to refine or personalize an existing itinerary."""

    instructions: str = Field(
        description="Natural language instruction for refining the itinerary (3 to 1500 chars)"
    )
    selected_place_ids: List[str] = Field(
        default_factory=list,
        description="Place IDs from retrieved recommendations that must be included or prioritized",
    )
    excluded_place_ids: List[str] = Field(
        default_factory=list,
        description="Place IDs that must be excluded or removed from the itinerary",
    )
    current_plan: Optional[TravelPlanResponse] = Field(
        default=None,
        description="Current travel plan object (used in guest mode or stateless updates)",
    )
    trip_id: Optional[str] = Field(
        default=None,
        description="Optional ID of saved trip",
    )

    @model_validator(mode="after")
    def validate_personalization_inputs(self) -> "PersonalizePlanRequest":
        # Normalize instructions
        self.instructions = (self.instructions or "").strip()
        if len(self.instructions) < 3:
            raise ValueError("Instructions must be at least 3 characters long")
        if len(self.instructions) > 1500:
            raise ValueError("Instructions cannot exceed 1500 characters")

        # Clean and deduplicate place IDs
        if len(self.selected_place_ids) > 50:
            raise ValueError("Cannot specify more than 50 selected place IDs")
        if len(self.excluded_place_ids) > 50:
            raise ValueError("Cannot specify more than 50 excluded place IDs")

        cleaned_selected = []
        for pid in self.selected_place_ids:
            if pid and isinstance(pid, str) and pid.strip():
                clean_id = pid.strip()
                if clean_id not in cleaned_selected:
                    cleaned_selected.append(clean_id)
        self.selected_place_ids = cleaned_selected

        cleaned_excluded = []
        for pid in self.excluded_place_ids:
            if pid and isinstance(pid, str) and pid.strip():
                clean_id = pid.strip()
                if clean_id not in cleaned_excluded:
                    cleaned_excluded.append(clean_id)
        self.excluded_place_ids = cleaned_excluded

        # Validate that no place ID is in both selected and excluded lists
        conflicts = set(self.selected_place_ids) & set(self.excluded_place_ids)
        if conflicts:
            raise ValueError(
                f"Conflicting place IDs present in both selected and excluded lists: {sorted(list(conflicts))}"
            )

        # Either current_plan or trip_id must be provided
        if not self.current_plan and not (self.trip_id and self.trip_id.strip()):
            raise ValueError(
                "Either 'current_plan' or a valid 'trip_id' must be provided to personalize an itinerary"
            )

        return self


class TripSaveRequest(BaseModel):
    """Payload to save an itinerary into database."""
    title: Optional[str] = Field(default=None, description="Optional custom title for the trip")
    plan: TravelPlanResponse = Field(description="The validated plan to save")


class TripSummary(BaseModel):
    """Brief trip metadata for listing trips."""
    id: str
    user_id: str
    title: str
    destination: str
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    duration_days: int
    budget: Optional[float] = None
    currency: str = "USD"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TripDetail(TripSummary):
    """Detailed trip payload with full plan data."""
    summary: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    itinerary: List[DayItinerary] = Field(default_factory=list)
    recommendations: List[PlaceRecommendation] = Field(default_factory=list)
    integration_metadata: Dict[str, Any] = Field(default_factory=dict)
