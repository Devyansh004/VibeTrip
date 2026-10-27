"""Preference processing and normalization service."""

from typing import Dict, Any, List, Optional
from app.schemas.planning import TravelPlanRequest, ExtractedPreferences


class PreferenceService:
    """Processes and standardizes user vibe preferences."""

    def normalize_request_preferences(
        self,
        request: TravelPlanRequest,
        extracted: Optional[ExtractedPreferences] = None,
    ) -> Dict[str, Any]:
        """Combine explicit form inputs with optional structured extracted nuances."""
        if extracted:
            combined_interests = list(
                dict.fromkeys(request.interests + extracted.interests)
            )
            combined_atmosphere = list(
                dict.fromkeys(request.atmosphere + extracted.atmosphere)
            )
            travel_pace = extracted.travel_pace or request.travel_pace
            vibe_keywords = extracted.vibe_keywords
        else:
            combined_interests = list(dict.fromkeys(request.interests))
            combined_atmosphere = list(dict.fromkeys(request.atmosphere))
            travel_pace = request.travel_pace
            vibe_keywords = [
                w.strip().lower()
                for w in (request.additional_preferences or "").replace(";", ",").split(",")
                if len(w.strip()) > 2
            ][:5]

        return {
            "interests": combined_interests or ["local experiences"],
            "atmosphere": combined_atmosphere or ["balanced"],
            "travel_pace": travel_pace or "balanced",
            "vibe_keywords": vibe_keywords,
            "raw_text": request.additional_preferences,
            "budget": request.budget,
            "currency": request.currency,
            "travelers": request.travelers,
            "duration_days": request.duration_days,
        }
