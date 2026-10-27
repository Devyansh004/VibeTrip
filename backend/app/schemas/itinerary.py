"""Itinerary activities and day schedule schemas."""

import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ItineraryActivity(BaseModel):
    """Single activity or stop within a day's schedule."""
    activity_id: str = Field(description="Unique activity identifier")
    title: str = Field(description="Activity headline or venue name")
    description: str = Field(description="Description of what to experience or do")
    day_number: int = Field(ge=1, description="Day number of the trip")
    time_label: Optional[str] = Field(default=None, description="Suggested time bracket (e.g. Morning, Afternoon, Evening)")
    place_id: Optional[str] = Field(default=None, description="Referenced place ID if tied to a verified venue")
    estimated_duration_minutes: Optional[int] = Field(default=None, description="Estimated duration in minutes")
    estimated_cost: Optional[float] = Field(default=None, description="Suggested cost estimate")
    currency: str = Field(default="USD", description="Currency code for cost estimate")
    is_estimate: bool = Field(default=True, description="Flag indicating if cost/duration is estimated")


class DayItinerary(BaseModel):
    """Schedule for an individual day of the trip."""
    day_number: int = Field(ge=1, description="Sequential day number (1-indexed)")
    date: Optional[datetime.date] = Field(default=None, description="Specific calendar date if provided")
    theme: str = Field(description="Curated thematic focus for the day")
    activities: List[ItineraryActivity] = Field(default_factory=list, description="Ordered list of activities")
    notes: Optional[str] = Field(default=None, description="Helpful tips or logistics advice for this day")
