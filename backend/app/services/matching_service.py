"""Matching and ranking service for place recommendations and taste affinity."""

from typing import List, Dict, Any, Optional
from app.schemas.places import PlaceRecommendation
from app.utils.logging import logger


# Mapping from Qloo tag types to Geoapify categories for semantic matching
QLOO_TAG_TYPE_TO_GEOAPIFY = {
    "urn:tag:cuisine:qloo": ["catering.restaurant", "catering.cafe"],
    "urn:tag:genre:place": ["tourism.sights", "entertainment.museum", "tourism.attraction"],
    "urn:tag:category:place": ["tourism.sights", "tourism.attraction"],
    "urn:tag:ambience:qloo": ["catering.cafe", "leisure.park"],
    "urn:tag:setting:qloo": ["tourism.sights", "natural"],
    "urn:tag:culinary_style:qloo": ["catering.restaurant", "catering.cafe"],
    "urn:tag:dining_option:qloo": ["catering.restaurant", "catering.cafe"],
    "urn:tag:amenity:qloo": ["tourism.sights", "leisure.park"],
    "urn:tag:activity_type:qloo": ["tourism.sights", "leisure.sports_centre"],
    "urn:tag:interests:qloo": ["tourism.sights", "tourism.attraction", "catering.cafe"],
    "urn:tag:nearby_attraction:qloo": ["tourism.sights", "tourism.attraction"],
    "urn:tag:ambience:place": ["catering.cafe", "leisure.park"],
    "urn:tag:visit_intent:qloo": ["tourism.sights", "catering.restaurant"],
    "urn:tag:beverage_offering:qloo": ["catering.cafe", "catering.bar"],
    "urn:tag:menu_highlight:qloo": ["catering.restaurant", "catering.cafe"],
    "urn:tag:dietary_option:qloo": ["catering.restaurant", "catering.cafe"],
    "urn:tag:music": ["entertainment.culture.theatre", "catering.pub"],
    "urn:tag:art": ["entertainment.museum", "tourism.sights"],
}

# Interest keyword to category keyword mapping for better matching
INTEREST_TO_CATEGORY_KEYWORDS = {
    "cafes": ["cafe", "coffee", "catering"],
    "food": ["restaurant", "catering", "food"],
    "art and culture": ["museum", "art", "culture", "entertainment"],
    "architecture": ["sights", "historic", "heritage", "building", "architecture"],
    "music": ["theatre", "pub", "music", "entertainment"],
    "photography": ["sights", "attraction", "viewpoint", "scenic"],
    "nature": ["natural", "park", "garden", "leisure"],
    "history": ["museum", "historic", "heritage", "castle", "ruins", "sights"],
    "nightlife": ["bar", "pub", "nightclub", "entertainment"],
    "shopping": ["shopping", "market", "commercial"],
    "adventure": ["sports", "activity", "adventure", "leisure"],
    "local experiences": ["catering", "market", "attraction", "local"],
}


def _normalize_category(cat: str) -> str:
    """Normalize category string for comparison (both 'catering.cafe' and 'catering / cafe' -> 'catering cafe')."""
    import re
    normalized = cat.lower().replace("/", " ").replace(".", " ").replace(",", " ")
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def _category_matches(place_category: str, target_category: str) -> bool:
    """Check if place category matches target category using normalized comparison."""
    place_norm = _normalize_category(place_category)
    target_norm = _normalize_category(target_category)
    return target_norm in place_norm


def _interest_matches_category(interest: str, place_category: str) -> bool:
    """Check if an interest keyword matches a place category via keyword mapping."""
    interest_lower = interest.lower().strip()
    if interest_lower in INTEREST_TO_CATEGORY_KEYWORDS:
        keywords = INTEREST_TO_CATEGORY_KEYWORDS[interest_lower]
        place_norm = _normalize_category(place_category)
        return any(kw in place_norm for kw in keywords)
    # Fallback: direct token match
    place_norm = _normalize_category(place_category)
    tokens = interest_lower.split()
    return any(token in place_norm for token in tokens if len(token) > 2)


class MatchingService:
    """Ranks and enriches place recommendations against user preferences and taste insights."""

    def score_place(
        self,
        place: PlaceRecommendation,
        interests: List[str],
        atmosphere: List[str],
        qloo_insights: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate a transparent compatibility score between a place and user preferences."""
        score = 1.0  # Base score

        place_cat = (place.category or "").lower()
        place_name = (place.name or "").lower()
        place_desc = (place.description or "").lower()
        text_corpus = f"{place_cat} {place_name} {place_desc}"

        # 1. Interest Keyword Overlap (with category mapping)
        interest_matches = 0
        for interest in interests:
            if _interest_matches_category(interest, place.category or ""):
                interest_matches += 1
                score += 2.0

        # 2. Atmospheric Compatibility
        for vibe in atmosphere:
            vibe_lower = vibe.lower()
            if vibe_lower in text_corpus:
                score += 1.5

        # 3. Taste Intelligence Signal Boost (from Qloo insights if available)
        qloo_boost = 0.0
        if qloo_insights and qloo_insights.get("status") == "success":
            # Use structured affinity tags for semantic matching
            affinity_tags = qloo_insights.get("affinity_tags", [])
            entity_popularity = qloo_insights.get("entity_popularity", {})

            # Collect relevant Geoapify categories from Qloo tags
            qloo_geoapify_categories: set[str] = set()
            tag_weights: dict[str, float] = {}
            for tag in affinity_tags:
                tag_type = tag.get("type", "")
                tag_weight = tag.get("weight") or 1.0
                # Find matching Geoapify categories for this Qloo tag type
                for qloo_prefix, geo_cats in QLOO_TAG_TYPE_TO_GEOAPIFY.items():
                    if tag_type.startswith(qloo_prefix):
                        for geo_cat in geo_cats:
                            qloo_geoapify_categories.add(geo_cat)
                            tag_weights[geo_cat] = max(tag_weights.get(geo_cat, 0.0), tag_weight)

            # Score boost based on Geoapify category match from Qloo tags
            if qloo_geoapify_categories:
                for geo_cat in qloo_geoapify_categories:
                    if _category_matches(place.category or "", geo_cat):
                        # Weight by tag relevance (weight or 1.0)
                        boost = 3.0 * tag_weights.get(geo_cat, 1.0)
                        qloo_boost += boost
                        logger.debug(f"Qloo tag matched Geoapify category '{geo_cat}' for place '{place.name}': +{boost}")

            # Additional boost if place entity_id matches a Qloo entity (direct match)
            if place.place_id and place.place_id in entity_popularity:
                pop = entity_popularity[place.place_id]
                # Scale popularity boost (0-1) to 0-5 points
                qloo_boost += min(5.0, pop * 5.0)
                logger.debug(f"Place '{place.name}' is a direct Qloo entity (popularity={pop:.3f}): +{min(5.0, pop * 5.0):.1f}")

        score += qloo_boost
        return score

    def rank_and_explain_places(
        self,
        places: List[PlaceRecommendation],
        interests: List[str],
        atmosphere: List[str],
        qloo_insights: Optional[Dict[str, Any]] = None,
    ) -> List[PlaceRecommendation]:
        """Rank places and generate transparent, evidence-aware match explanations."""
        if not places:
            return []

        scored_places: List[tuple[float, PlaceRecommendation]] = []

        qloo_available = bool(qloo_insights and qloo_insights.get("status") == "success")

        for place in places:
            score = self.score_place(place, interests, atmosphere, qloo_insights)

            # Construct honest explanation based on actual matched criteria
            matched_interests = [
                i for i in interests
                if _interest_matches_category(i, place.category or "")
            ]

            explanation_parts = []
            if matched_interests:
                explanation_parts.append(f"Aligns with your interest in {', '.join(matched_interests[:2])}")
            elif place.category:
                explanation_parts.append(f"Selected as a notable {place.category.split('/')[0].strip()} in the area")
            else:
                explanation_parts.append("Discovered near your travel hub")

            if atmosphere:
                explanation_parts.append(f"complements your desired {atmosphere[0].lower()} vibe")

            # Add Qloo-specific explanation if Qloo actually influenced ranking
            qloo_boost_applied = False
            if qloo_available:
                affinity_tags = qloo_insights.get("affinity_tags", [])
                entity_popularity = qloo_insights.get("entity_popularity", {})
                
                qloo_matched = False
                if affinity_tags:
                    qloo_geoapify_categories: set[str] = set()
                    for tag in affinity_tags:
                        tag_type = tag.get("type", "")
                        for qloo_prefix, geo_cats in QLOO_TAG_TYPE_TO_GEOAPIFY.items():
                            if tag_type.startswith(qloo_prefix):
                                qloo_geoapify_categories.update(geo_cats)
                    if any(_category_matches(place.category or "", geo_cat) for geo_cat in qloo_geoapify_categories):
                        qloo_matched = True
                
                if place.place_id and place.place_id in entity_popularity:
                    qloo_matched = True

                if qloo_matched:
                    explanation_parts.append("(ranked higher by Qloo taste insights)")
                    qloo_boost_applied = True
                elif not qloo_boost_applied:
                    explanation_parts.append("(Qloo insights available but no direct match for this venue)")

            explanation = "; ".join(explanation_parts) + "."

            # Clone place with updated explanation and score
            updated_place = place.model_copy(update={
                "match_explanation": explanation,
                "data_source": "geoapify+qloo" if qloo_boost_applied else ("geoapify+qloo" if qloo_available else "geoapify")
            })
            scored_places.append((score, updated_place))

        # Sort descending by score
        scored_places.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored_places]
