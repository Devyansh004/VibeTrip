"""Place and geospatial schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PlaceRecommendation(BaseModel):
    """Normalized place recommendation schema."""
    place_id: str = Field(description="Unique identifier for the place or venue")
    name: str = Field(description="Display name of the venue or point of interest")
    category: Optional[str] = Field(default=None, description="Primary category or tag")
    address: Optional[str] = Field(default=None, description="Formatted street address")
    latitude: Optional[float] = Field(default=None, description="Geographic latitude")
    longitude: Optional[float] = Field(default=None, description="Geographic longitude")
    description: Optional[str] = Field(default=None, description="Brief description of the place")
    match_explanation: Optional[str] = Field(default=None, description="Reason why this matches user preferences")
    estimated_visit_minutes: Optional[int] = Field(default=None, description="Suggested visit duration in minutes")
    data_source: str = Field(default="geoapify", description="Provenance of this place data")
    is_estimate: bool = Field(default=False, description="Flag indicating if any details are estimated")
    map_url: Optional[str] = Field(default=None, description="Direct URL to view place on map")


class PlaceSearchRequest(BaseModel):
    """Geospatial place search request schema."""
    location: Optional[str] = Field(default=None, description="City or place name to geocode")
    latitude: Optional[float] = Field(default=None, description="Latitude for proximity search")
    longitude: Optional[float] = Field(default=None, description="Longitude for proximity search")
    categories: List[str] = Field(default_factory=list, description="Geoapify categories to search")
    radius_meters: int = Field(default=5000, ge=500, le=50000, description="Search radius in meters")
    limit: int = Field(default=10, ge=1, le=50, description="Max number of places to retrieve")
