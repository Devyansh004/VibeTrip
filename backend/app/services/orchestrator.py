"""Agent Orchestration engine coordinating Qloo, Groq, Geoapify, and synthesis."""

import uuid
from typing import Dict, Any, List, Optional

from app.config import Settings, get_settings
from app.schemas.planning import TravelPlanRequest, TravelPlanResponse, ExtractedPreferences, PersonalizePlanRequest
from app.schemas.places import PlaceRecommendation
from app.schemas.itinerary import DayItinerary
from app.services.qloo_service import QlooService
from app.services.groq_service import GroqService
from app.services.geoapify_service import GeoapifyService
from app.services.matching_service import MatchingService
from app.services.itinerary_service import ItineraryService
from app.services.preference_service import PreferenceService
from app.utils.logging import logger


# In-memory plan cache to reuse generated plans and avoid redundant LLM/API calls
_itinerary_cache: Dict[str, TravelPlanResponse] = {}


def _build_plan_cache_key(request: TravelPlanRequest, config_state: str = "") -> str:
    norm_dest = request.destination.strip().lower()
    days = request.duration_days or 3
    start = str(request.start_date) if request.start_date else ""
    end = str(request.end_date) if request.end_date else ""
    travelers = request.travelers
    budget = f"{request.budget}_{request.currency}" if request.budget else ""
    pace = (request.travel_pace or "balanced").lower()
    sorted_interests = ",".join(sorted([i.lower().strip() for i in request.interests]))
    sorted_atmosphere = ",".join(sorted([a.lower().strip() for a in request.atmosphere]))
    return f"{norm_dest}:{days}:{start}:{end}:{travelers}:{budget}:{pace}:{sorted_interests}:{sorted_atmosphere}:{config_state}"


class TravelAgentOrchestrator:
    """Orchestrates multi-service workflow to build personalized travel plans."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        qloo_service: Optional[QlooService] = None,
        groq_service: Optional[GroqService] = None,
        geoapify_service: Optional[GeoapifyService] = None,
        matching_service: Optional[MatchingService] = None,
        itinerary_service: Optional[ItineraryService] = None,
        preference_service: Optional[PreferenceService] = None,
    ):
        self.settings = settings or get_settings()
        self.qloo = qloo_service or QlooService(self.settings)
        self.groq = groq_service or GroqService(self.settings)
        self.geoapify = geoapify_service or GeoapifyService(self.settings)
        self.matching = matching_service or MatchingService()
        self.itinerary = itinerary_service or ItineraryService()
        self.preference = preference_service or PreferenceService()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the in-memory itinerary cache."""
        _itinerary_cache.clear()

    async def plan_trip(self, request: TravelPlanRequest) -> TravelPlanResponse:
        """Execute the end-to-end travel planning orchestration workflow."""
        config_state = f"{self.qloo.is_configured}:{self.groq.is_configured}:{self.geoapify.is_configured}"
        cache_key = _build_plan_cache_key(request, config_state)
        if cache_key in _itinerary_cache:
            cached_plan = _itinerary_cache[cache_key]
            # Verify cached plan does not contain stale unconfigured warnings if services are now configured
            has_stale_warning = any(
                ("qloo api is not configured" in w.lower() and self.qloo.is_configured) or
                ("geoapify api is not configured" in w.lower() and self.geoapify.is_configured) or
                ("groq api is not configured" in w.lower() and self.groq.is_configured)
                for w in (cached_plan.warnings or [])
            )
            if not has_stale_warning:
                logger.info(f"Reusing cached itinerary for destination '{request.destination}'")
                return cached_plan


        trip_id = str(uuid.uuid4())
        warnings: List[str] = []
        groq_init = "not_configured" if not self.groq.is_configured else "pending"
        integration_status: Dict[str, str] = {
            "qloo": "not_configured" if not self.qloo.is_configured else "pending",
            "groq": groq_init,
            "geoapify": "not_configured" if not self.geoapify.is_configured else "pending",
        }

        logger.info(f"Initiating trip planning for destination: {request.destination}")

        # Step 1: Normalize direct structured preferences (skips unnecessary LLM extraction hop)
        normalized_prefs = self.preference.normalize_request_preferences(request)

        # Step 3: Qloo Taste Intelligence
        taste_insights: Optional[Dict[str, Any]] = None
        if self.qloo.is_configured:
            try:
                taste_result = await self.qloo.get_taste_insights(
                    preferences=normalized_prefs, destination=request.destination
                )
                if taste_result.get("status") == "success":
                    taste_insights = taste_result
                    integration_status["qloo"] = "success"
                else:
                    integration_status["qloo"] = "failed"
                    warnings.append(f"Qloo taste intelligence unavailable: {taste_result.get('message')}")
            except Exception as exc:
                logger.warning(f"Qloo service call error: {str(exc)}")
                integration_status["qloo"] = "failed"
                warnings.append("Qloo taste intelligence request failed; proceeding without cultural affinity signals.")
        else:
            integration_status["qloo"] = "not_configured"
            warnings.append("Qloo API is not configured; taste intelligence insights could not be retrieved.")

        # Step 4: Geoapify Place Discovery
        discovered_places: List[PlaceRecommendation] = []
        if self.geoapify.is_configured:
            try:
                geocode = await self.geoapify.geocode_location(request.destination)
                if geocode:
                    lat = geocode["latitude"]
                    lon = geocode["longitude"]
                    cats = self.geoapify.map_interests_to_categories(normalized_prefs["interests"])
                    discovered_places = await self.geoapify.search_places(
                        latitude=lat,
                        longitude=lon,
                        categories=cats,
                        radius_meters=10000,
                        limit=min(15, request.duration_days * 5),
                    )
                    integration_status["geoapify"] = "success"
                else:
                    integration_status["geoapify"] = "failed"
                    warnings.append(f"Could not geocode destination '{request.destination}'.")
            except Exception as exc:
                logger.warning(f"Geoapify places search failed: {str(exc)}")
                integration_status["geoapify"] = "failed"
                warnings.append("Geoapify place search failed; verified venue listing is unavailable.")
        else:
            integration_status["geoapify"] = "not_configured"
            warnings.append("Geoapify API is not configured; real-world venue coordinates cannot be fetched.")

        # Step 5: Match and Rank Places
        ranked_places = self.matching.rank_and_explain_places(
            places=discovered_places,
            interests=normalized_prefs["interests"],
            atmosphere=normalized_prefs["atmosphere"],
            qloo_insights=taste_insights,
        )

        # Step 6: Itinerary Generation
        itinerary_days: List[DayItinerary] = []
        summary: str = ""
        budget_breakdown: Optional[Dict[str, Any]] = None

        if self.groq.is_configured and integration_status["groq"] != "failed":
            try:
                groq_output = await self.groq.generate_itinerary(
                    destination=request.destination,
                    duration_days=request.duration_days,
                    preferences=normalized_prefs,
                    taste_insights=taste_insights,
                    places=ranked_places,
                    budget=request.budget,
                    currency=request.currency,
                    travelers=request.travelers,
                )
                summary = groq_output.get("summary", f"Personalized {request.destination} trip.")
                budget_breakdown = groq_output.get("budget_breakdown")
                raw_days = groq_output.get("days", [])
                if not raw_days:
                    raise ValueError("Groq returned empty or missing itinerary days")

                itinerary_days = self.itinerary.validate_and_normalize_itinerary(
                    raw_days=raw_days,
                    duration_days=request.duration_days,
                    start_date=request.start_date,
                    places=ranked_places,
                    currency=request.currency,
                )
                integration_status["groq"] = "success"
                if groq_output.get("failover_occurred"):
                    logger.info(f"Orchestrator plan_trip: Failover succeeded using model '{groq_output.get('model_used')}'")
                if groq_output.get("warnings"):
                    warnings.extend(groq_output["warnings"])
            except Exception as exc:
                category = getattr(exc, "category", "service_error")
                safe_msg = getattr(
                    exc,
                    "user_friendly_message",
                    "Groq itinerary generation was unavailable; falling back to grounded rule-based itinerary.",
                )
                logger.warning(f"Groq itinerary generation failed ({category}); falling back to grounded itinerary")
                integration_status["groq"] = "failed"
                warnings.append(safe_msg)
                summary, itinerary_days, budget_breakdown = self.itinerary.build_grounded_itinerary_fallback(
                    destination=request.destination,
                    duration_days=request.duration_days,
                    start_date=request.start_date,
                    places=ranked_places,
                    interests=normalized_prefs["interests"],
                    atmosphere=normalized_prefs["atmosphere"],
                    currency=request.currency,
                    budget=request.budget,
                )
        else:
            if not self.groq.is_configured:
                integration_status["groq"] = "not_configured"
                warnings.append("Groq API is not configured; assembled grounded rule-based itinerary.")
            # Deterministic fallback with verified places
            summary, itinerary_days, budget_breakdown = self.itinerary.build_grounded_itinerary_fallback(
                destination=request.destination,
                duration_days=request.duration_days,
                start_date=request.start_date,
                places=ranked_places,
                interests=normalized_prefs["interests"],
                atmosphere=normalized_prefs["atmosphere"],
                currency=request.currency,
                budget=request.budget,
            )


        # Step 7 & 8: Assemble final TravelPlanResponse
        response = TravelPlanResponse(
            trip_id=trip_id,
            destination=request.destination,
            summary=summary,
            preferences=normalized_prefs,
            taste_insights=taste_insights,
            recommended_places=ranked_places,
            itinerary=itinerary_days,
            estimated_budget=budget_breakdown,
            integration_status=integration_status,
            warnings=warnings,
        )

        # Cache valid response to prevent duplicate LLM/API calls
        if itinerary_days:
            _itinerary_cache[cache_key] = response

        return response

    async def personalize_trip(
        self,
        request: PersonalizePlanRequest,
    ) -> TravelPlanResponse:
        """Personalize an existing travel plan using natural-language instructions and place selections."""
        warnings: List[str] = []

        # 1. Establish the base plan
        base_plan: Optional[TravelPlanResponse] = request.current_plan

        if not base_plan:
            raise ValueError("No valid travel plan provided to personalize. Please provide current_plan.")

        # 2. Establish authoritative places from the base plan
        authoritative_places: List[PlaceRecommendation] = base_plan.recommended_places or []
        authoritative_ids = {p.place_id for p in authoritative_places}

        # 3. Validate selected and excluded IDs against authoritative places
        valid_selected = [pid for pid in request.selected_place_ids if pid in authoritative_ids]
        unknown_selected = [pid for pid in request.selected_place_ids if pid not in authoritative_ids]
        if unknown_selected:
            warnings.append(f"Ignored unknown or unverified selected place IDs: {', '.join(unknown_selected)}")

        valid_excluded = [pid for pid in request.excluded_place_ids if pid in authoritative_ids]
        unknown_excluded = [pid for pid in request.excluded_place_ids if pid not in authoritative_ids]
        if unknown_excluded:
            warnings.append(f"Ignored unknown excluded place IDs: {', '.join(unknown_excluded)}")

        # 4. Personalize Itinerary via Groq
        integration_status = dict(base_plan.integration_status)
        new_summary = base_plan.summary
        new_budget = base_plan.estimated_budget
        duration_days = len(base_plan.itinerary) or base_plan.preferences.get("duration_days", 3)
        start_date = base_plan.itinerary[0].date if base_plan.itinerary else None

        if self.groq.is_configured:
            try:
                groq_output = await self.groq.personalize_itinerary(
                    current_itinerary=base_plan.itinerary,
                    destination=base_plan.destination,
                    preferences=base_plan.preferences,
                    instructions=request.instructions,
                    selected_place_ids=valid_selected,
                    excluded_place_ids=valid_excluded,
                    available_places=authoritative_places,
                    budget=base_plan.estimated_budget.get("estimated_total") if base_plan.estimated_budget else None,
                    currency=base_plan.estimated_budget.get("currency", "USD") if base_plan.estimated_budget else "USD",
                    travelers=base_plan.preferences.get("travelers", 1),
                )
                raw_days = groq_output.get("days", [])
                if not raw_days:
                    raise ValueError("Groq returned empty days during personalization")

                validated_days, itin_warnings = self.itinerary.validate_personalized_itinerary(
                    raw_days=raw_days,
                    duration_days=duration_days,
                    start_date=start_date,
                    available_places=authoritative_places,
                    selected_place_ids=valid_selected,
                    excluded_place_ids=valid_excluded,
                    currency=base_plan.estimated_budget.get("currency", "USD") if base_plan.estimated_budget else "USD",
                )
                new_summary = groq_output.get("summary") or base_plan.summary
                if groq_output.get("budget_breakdown"):
                    new_budget = groq_output.get("budget_breakdown")
                if groq_output.get("warnings"):
                    warnings.extend(groq_output["warnings"])
                warnings.extend(itin_warnings)
                integration_status["groq"] = "success"
                if groq_output.get("failover_occurred"):
                    logger.info(f"Orchestrator personalize_trip: Failover succeeded using model '{groq_output.get('model_used')}'")
                itinerary_days = validated_days
            except Exception as exc:
                category = getattr(exc, "category", "service_error")
                raw_msg = getattr(
                    exc,
                    "user_friendly_message",
                    "AI service was temporarily unavailable.",
                )
                safe_msg = f"Groq personalization failed: {raw_msg}" if "failed" not in raw_msg.lower() else raw_msg
                logger.warning(f"Groq personalization failed ({category}); preserving original itinerary")
                integration_status["groq"] = "failed"
                warnings.append(safe_msg)
                itinerary_days = base_plan.itinerary
        else:
            integration_status["groq"] = "not_configured"
            warnings.append("Groq API is not configured; natural language personalization could not be applied.")
            itinerary_days = base_plan.itinerary

        # Remove stale configuration warnings if the services are now configured
        stale_prefixes = []
        if self.qloo.is_configured:
            stale_prefixes.append("qloo api is not configured")
        if self.geoapify.is_configured:
            stale_prefixes.append("geoapify api is not configured")
        if self.groq.is_configured:
            stale_prefixes.append("groq api is not configured")

        cleaned_base_warnings = [
            w for w in (base_plan.warnings or [])
            if not any(w.lower().startswith(prefix) for prefix in stale_prefixes)
        ]
        all_warnings = list(dict.fromkeys(cleaned_base_warnings + warnings))

        # Ensure integration_status accurately reflects current configuration for unconfigured services
        if self.qloo.is_configured and integration_status.get("qloo") == "not_configured":
            integration_status["qloo"] = "configured"
        if self.geoapify.is_configured and integration_status.get("geoapify") == "not_configured":
            integration_status["geoapify"] = "configured"

        return TravelPlanResponse(
            trip_id=base_plan.trip_id or str(uuid.uuid4()),
            destination=base_plan.destination,
            summary=new_summary,
            preferences=base_plan.preferences,
            taste_insights=base_plan.taste_insights,
            recommended_places=base_plan.recommended_places,
            itinerary=itinerary_days,
            estimated_budget=new_budget,
            integration_status=integration_status,
            warnings=all_warnings,
        )

