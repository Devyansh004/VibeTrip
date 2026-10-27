"""Itinerary validation, enrichment, and fallback synthesis service."""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from app.schemas.places import PlaceRecommendation
from app.schemas.itinerary import DayItinerary, ItineraryActivity
from app.utils.logging import logger


class ItineraryService:
    """Handles validation, grounding verification, and itinerary assembly."""

    def validate_and_normalize_itinerary(
        self,
        raw_days: List[Dict[str, Any]],
        duration_days: int,
        start_date: Optional[date],
        places: List[PlaceRecommendation],
        currency: str = "USD",
    ) -> List[DayItinerary]:
        """Validate generated days and activities against ground truth places."""
        valid_place_ids = {p.place_id for p in places}
        validated_days: List[DayItinerary] = []

        # Filter out any non-dict elements from raw_days
        dict_days = [d for d in raw_days if isinstance(d, dict)]
        day_count = min(len(dict_days), duration_days)

        for i in range(day_count):
            day_data = dict_days[i]
            day_num = day_data.get("day_number") or (i + 1)
            day_date = (start_date + timedelta(days=i)) if start_date else None

            raw_activities = day_data.get("activities", [])
            if not isinstance(raw_activities, list):
                raw_activities = []
            validated_activities: List[ItineraryActivity] = []

            for idx, act in enumerate(raw_activities):
                act_id = act.get("activity_id") or f"act_{day_num}_{idx+1}"
                if isinstance(act_id, str):
                    act_id = act_id.strip().rstrip(",").strip()
                place_id = act.get("place_id")
                if place_id and isinstance(place_id, str):
                    place_id = place_id.strip().rstrip(",").strip() or None

                # Verify grounding: place_id must exist in supplied verified places
                if place_id and place_id not in valid_place_ids:
                    logger.warning(
                        f"Activity '{act.get('title')}' referenced unverified place_id '{place_id}'. Clearing place_id."
                    )
                    place_id = None

                validated_activities.append(
                    ItineraryActivity(
                        activity_id=act_id,
                        title=act.get("title", f"Activity {idx+1}"),
                        description=act.get("description", "Explore local atmosphere"),
                        day_number=day_num,
                        time_label=act.get("time_label") or ("Morning" if idx == 0 else "Afternoon" if idx == 1 else "Evening"),
                        place_id=place_id,
                        estimated_duration_minutes=act.get("estimated_duration_minutes", 60),
                        estimated_cost=act.get("estimated_cost", 15.0),
                        currency=currency,
                        is_estimate=True,
                    )
                )

            validated_days.append(
                DayItinerary(
                    day_number=day_num,
                    date=day_date,
                    theme=day_data.get("theme", f"Day {day_num}: Exploration"),
                    activities=validated_activities,
                    notes=day_data.get("notes"),
                )
            )

        # Backfill any missing days with verified places if model generated fewer days than requested
        used_place_ids = {
            act.place_id for day in validated_days for act in day.activities if act.place_id
        }
        remaining_places = [p for p in places if p.place_id not in used_place_ids]
        place_idx = 0

        while len(validated_days) < duration_days:
            missing_day_num = len(validated_days) + 1
            missing_date = (start_date + timedelta(days=missing_day_num - 1)) if start_date else None
            backfill_activities: List[ItineraryActivity] = []

            time_labels = ["Morning", "Afternoon", "Evening"]
            for slot_idx, slot in enumerate(time_labels):
                if place_idx < len(remaining_places):
                    p = remaining_places[place_idx]
                    place_idx += 1
                    backfill_activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{missing_day_num}_{slot_idx+1}",
                            title=f"Visit {p.name}",
                            description=f"Explore {p.name} ({p.category or 'sightseeing'}), an authentic local venue.",
                            day_number=missing_day_num,
                            time_label=slot,
                            place_id=p.place_id,
                            estimated_duration_minutes=90,
                            estimated_cost=20.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )
                else:
                    backfill_activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{missing_day_num}_{slot_idx+1}",
                            title="Neighborhood Exploration & Scenic Walk",
                            description="Leisurely explore local side streets, cultural landmarks, and hidden gems.",
                            day_number=missing_day_num,
                            time_label=slot,
                            place_id=None,
                            estimated_duration_minutes=90,
                            estimated_cost=10.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )

            validated_days.append(
                DayItinerary(
                    day_number=missing_day_num,
                    date=missing_date,
                    theme=f"Day {missing_day_num}: Cultural Discovery & Highlights",
                    activities=backfill_activities,
                    notes="Practical exploration day grounded in verified local venues.",
                )
            )

        return validated_days

    def validate_personalized_itinerary(
        self,
        raw_days: List[Dict[str, Any]],
        duration_days: int,
        start_date: Optional[date],
        available_places: List[PlaceRecommendation],
        selected_place_ids: List[str],
        excluded_place_ids: List[str],
        currency: str = "USD",
    ) -> tuple[List[DayItinerary], List[str]]:
        """Validate personalized itinerary output, enforcing grounding, place exclusions, and inclusions.

        Returns (validated_days, warnings).
        """
        warnings: List[str] = []
        valid_places_map = {p.place_id: p for p in available_places}
        excluded_set = set(excluded_place_ids)

        # Candidate allowed places are those in available_places that are NOT excluded
        allowed_places = [p for p in available_places if p.place_id not in excluded_set]
        allowed_place_ids = {p.place_id for p in allowed_places}

        dict_days = [d for d in raw_days if isinstance(d, dict)]
        day_count = min(len(dict_days), duration_days)
        validated_days: List[DayItinerary] = []

        excluded_venues_detected = 0
        hallucinated_ids_detected = 0

        for i in range(day_count):
            day_data = dict_days[i]
            day_num = day_data.get("day_number") or (i + 1)
            day_date = (start_date + timedelta(days=i)) if start_date else None

            raw_activities = day_data.get("activities", [])
            if not isinstance(raw_activities, list):
                raw_activities = []
            validated_activities: List[ItineraryActivity] = []

            for idx, act in enumerate(raw_activities):
                act_id = act.get("activity_id") or f"act_{day_num}_{idx+1}"
                if isinstance(act_id, str):
                    act_id = act_id.strip().rstrip(",").strip()
                place_id = act.get("place_id")
                if place_id and isinstance(place_id, str):
                    place_id = place_id.strip().rstrip(",").strip() or None

                # Enforce exclusion: if model referenced an excluded place, strip it
                if place_id and place_id in excluded_set:
                    excluded_venues_detected += 1
                    place_id = None

                # Enforce grounding: must exist in allowed places
                if place_id and place_id not in allowed_place_ids:
                    hallucinated_ids_detected += 1
                    logger.warning(
                        f"Personalized activity '{act.get('title')}' referenced unverified place_id '{place_id}'. Clearing place_id."
                    )
                    place_id = None

                validated_activities.append(
                    ItineraryActivity(
                        activity_id=act_id,
                        title=act.get("title", f"Activity {idx+1}"),
                        description=act.get("description", "Explore local atmosphere"),
                        day_number=day_num,
                        time_label=act.get("time_label") or ("Morning" if idx == 0 else "Afternoon" if idx == 1 else "Evening"),
                        place_id=place_id,
                        estimated_duration_minutes=act.get("estimated_duration_minutes", 60),
                        estimated_cost=act.get("estimated_cost", 15.0),
                        currency=currency,
                        is_estimate=True,
                    )
                )

            validated_days.append(
                DayItinerary(
                    day_number=day_num,
                    date=day_date,
                    theme=day_data.get("theme", f"Day {day_num}: Exploration"),
                    activities=validated_activities,
                    notes=day_data.get("notes"),
                )
            )

        if excluded_venues_detected > 0:
            warnings.append(f"Removed {excluded_venues_detected} activities or references matching excluded place IDs.")
        if hallucinated_ids_detected > 0:
            warnings.append(f"Removed {hallucinated_ids_detected} unverified or fabricated place references from the itinerary.")

        # Backfill any missing days if fewer days returned than duration
        used_place_ids = {
            act.place_id for day in validated_days for act in day.activities if act.place_id
        }
        remaining_places = [p for p in allowed_places if p.place_id not in used_place_ids]
        place_idx = 0

        while len(validated_days) < duration_days:
            missing_day_num = len(validated_days) + 1
            missing_date = (start_date + timedelta(days=missing_day_num - 1)) if start_date else None
            backfill_activities: List[ItineraryActivity] = []

            for slot_idx, slot in enumerate(["Morning", "Afternoon", "Evening"]):
                if place_idx < len(remaining_places):
                    p = remaining_places[place_idx]
                    place_idx += 1
                    backfill_activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{missing_day_num}_{slot_idx+1}",
                            title=f"Visit {p.name}",
                            description=f"Explore {p.name} ({p.category or 'sightseeing'}), an authentic local venue.",
                            day_number=missing_day_num,
                            time_label=slot,
                            place_id=p.place_id,
                            estimated_duration_minutes=90,
                            estimated_cost=20.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )
                else:
                    backfill_activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{missing_day_num}_{slot_idx+1}",
                            title="Neighborhood Exploration & Scenic Walk",
                            description="Leisurely explore local side streets, cultural landmarks, and hidden gems.",
                            day_number=missing_day_num,
                            time_label=slot,
                            place_id=None,
                            estimated_duration_minutes=90,
                            estimated_cost=10.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )

            validated_days.append(
                DayItinerary(
                    day_number=missing_day_num,
                    date=missing_date,
                    theme=f"Day {missing_day_num}: Cultural Discovery & Highlights",
                    activities=backfill_activities,
                    notes="Practical exploration day grounded in verified local venues.",
                )
            )

        # Step 2: Selected must-visit places verification
        current_scheduled_pids = {
            act.place_id for day in validated_days for act in day.activities if act.place_id
        }
        unfulfilled_selected = [
            pid for pid in selected_place_ids
            if pid not in current_scheduled_pids and pid in allowed_place_ids
        ]

        # Attempt to insert unfulfilled selected places into activities that currently have place_id=None
        if unfulfilled_selected:
            unplaced = []
            for sel_pid in unfulfilled_selected:
                p = valid_places_map.get(sel_pid)
                if not p:
                    continue
                placed = False
                for day in validated_days:
                    for act in day.activities:
                        if act.place_id is None:
                            act.place_id = p.place_id
                            act.title = f"Visit {p.name}"
                            act.description = f"Experience {p.name} ({p.category or 'attraction'}) as requested in your preferences."
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    unplaced.append(p.name or sel_pid)

            if unplaced:
                warnings.append(
                    f"Selected places could not be fully fitted into the daily timeline: {', '.join(unplaced)}."
                )

        return validated_days, warnings

    def build_grounded_itinerary_fallback(
        self,
        destination: str,
        duration_days: int,
        start_date: Optional[date],
        places: List[PlaceRecommendation],
        interests: List[str],
        atmosphere: List[str],
        currency: str = "USD",
        budget: Optional[float] = None,
    ) -> tuple[str, List[DayItinerary], Dict[str, Any]]:
        """Construct a grounded, structured itinerary when Groq is not configured.
        
        Uses actual verified places from Geoapify without fabricating external AI content.
        """
        days: List[DayItinerary] = []
        places_per_day = 3
        place_idx = 0

        vibe_str = ", ".join(atmosphere[:2]) if atmosphere else "cultural discovery"
        interest_str = ", ".join(interests[:3]) if interests else "local highlights"

        summary = (
            f"A curated {duration_days}-day itinerary in {destination} centered around {interest_str} "
            f"and a {vibe_str} atmosphere. Highlights include verified points of interest "
            f"discovered via geospatial search."
        )

        time_brackets = ["Morning", "Afternoon", "Evening"]

        for d in range(1, duration_days + 1):
            day_date = (start_date + timedelta(days=d - 1)) if start_date else None
            activities: List[ItineraryActivity] = []

            for slot_idx, slot_name in enumerate(time_brackets):
                if place_idx < len(places):
                    p = places[place_idx]
                    place_idx += 1
                    activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{d}_{slot_idx+1}",
                            title=p.name,
                            description=f"Visit {p.name} ({p.category or 'Point of Interest'}). {p.match_explanation or ''}",
                            day_number=d,
                            time_label=slot_name,
                            place_id=p.place_id,
                            estimated_duration_minutes=p.estimated_visit_minutes or 90,
                            estimated_cost=20.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )
                else:
                    activities.append(
                        ItineraryActivity(
                            activity_id=f"act_{d}_{slot_idx+1}",
                            title=f"{slot_name} Atmosphere Walk & Leisure",
                            description=f"Enjoy a relaxed exploration of the surrounding neighborhood and cafes in {destination}.",
                            day_number=d,
                            time_label=slot_name,
                            place_id=None,
                            estimated_duration_minutes=60,
                            estimated_cost=10.0,
                            currency=currency,
                            is_estimate=True,
                        )
                    )

            days.append(
                DayItinerary(
                    day_number=d,
                    date=day_date,
                    theme=f"Day {d}: {interests[d % len(interests)].title() if interests else 'Discovery'} & Neighborhood Immersion",
                    activities=activities,
                    notes="Take time between stops to experience local cafe culture and street scenery.",
                )
            )

        budget_breakdown = {
            "estimated_total": round(duration_days * (budget / duration_days if budget else 60.0), 2),
            "currency": currency,
            "categories": {
                "activities": round(duration_days * 25.0, 2),
                "food_and_drink": round(duration_days * 25.0, 2),
                "transit": round(duration_days * 10.0, 2),
            },
            "note": "Budget values are advisory estimates.",
        }

        return summary, days, budget_breakdown
