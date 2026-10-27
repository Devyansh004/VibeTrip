"""Geoapify API integration service for geocoding and places discovery."""

from typing import List, Dict, Any, Optional
import httpx

from app.config import Settings, get_settings
from app.schemas.places import PlaceRecommendation
from app.utils.logging import logger
from app.utils.exceptions import ConfigurationError


# Common interest-to-Geoapify categories mapping (validated against Geoapify Places API v2)
INTEREST_CATEGORY_MAPPING = {
    "cafes": ["catering.cafe", "catering.restaurant"],
    "food": ["catering.restaurant", "catering.fast_food"],
    "art and culture": ["entertainment.museum", "tourism.attraction", "tourism.sights"],
    "architecture": ["tourism.sights", "building.historic", "heritage"],
    "music": ["entertainment.culture.theatre", "catering.pub"],
    "photography": ["tourism.sights", "tourism.attraction", "building.historic"],
    "nature": ["natural", "leisure.park"],
    "history": ["heritage", "tourism.sights", "building.historic"],
    "nightlife": ["catering.bar", "catering.pub", "entertainment.nightclub"],
    "shopping": ["commercial.shopping_mall", "commercial.marketplace"],
    "adventure": ["leisure.sports_centre", "activity"],
    "local experiences": ["catering", "commercial.marketplace", "tourism.attraction"],
}


class GeoapifyService:
    """Service client for Geoapify Geocoding and Places API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.geoapify_base_url.rstrip("/")
        self.api_key = self.settings.geoapify_api_key
        self.timeout = 10.0

    @property
    def is_configured(self) -> bool:
        """Check if Geoapify credentials are provided."""
        return bool(self.api_key and self.api_key.strip())

    async def geocode_location(self, location: str) -> Optional[Dict[str, Any]]:
        """Geocode a location or city name into latitude and longitude coordinates."""
        if not self.is_configured:
            logger.info("Geoapify geocode_location skipped: API key not configured")
            return None

        clean_location = location.strip()
        if not clean_location:
            return None

        url = f"{self.base_url}/v1/geocode/search"
        params = {
            "text": clean_location,
            "apiKey": self.api_key,
            "limit": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    features = data.get("features", [])
                    if features:
                        feature = features[0]
                        coords = feature.get("geometry", {}).get("coordinates", [])
                        props = feature.get("properties", {})
                        if len(coords) >= 2:
                            return {
                                "longitude": coords[0],
                                "latitude": coords[1],
                                "formatted": props.get("formatted", clean_location),
                                "city": props.get("city", clean_location),
                                "country": props.get("country", ""),
                            }
                logger.warning(f"Geoapify geocoding returned status {response.status_code}")
                return None
        except httpx.HTTPError as exc:
            logger.warning(f"Geoapify geocoding network error: {str(exc)}")
            return None

    def map_interests_to_categories(self, interests: List[str]) -> List[str]:
        """Convert user interest keywords to supported Geoapify place categories."""
        categories: set[str] = set()
        for interest in interests:
            key = interest.lower().strip()
            if key in INTEREST_CATEGORY_MAPPING:
                categories.update(INTEREST_CATEGORY_MAPPING[key])
            else:
                # Fallback to broader sights/tourism if unknown
                for mapped_key, cats in INTEREST_CATEGORY_MAPPING.items():
                    if mapped_key in key or key in mapped_key:
                        categories.update(cats)

        if not categories:
            categories = {"tourism.sights", "catering.cafe", "leisure.park"}

        return list(categories)

    async def search_places(
        self,
        latitude: float,
        longitude: float,
        categories: List[str],
        radius_meters: int = 5000,
        limit: int = 10,
    ) -> List[PlaceRecommendation]:
        """Search for real places using Geoapify Places API v2.
        
        Uses longitude before latitude for geographic circle filter string:
        filter=circle:lon,lat,radius_meters
        bias=proximity:lon,lat
        """
        if not self.is_configured:
            logger.info("Geoapify search_places skipped: API key not configured")
            return []

        # Validate parameters
        radius = max(500, min(radius_meters, 50000))
        lim = max(1, min(limit, 50))

        if not categories:
            categories = ["tourism.sights", "catering.cafe"]

        cat_param = ",".join(categories[:6])  # Cap at 6 categories per query
        # CRITICAL: Geoapify circle filter uses circle:lon,lat,radius
        filter_param = f"circle:{longitude},{latitude},{radius}"
        bias_param = f"proximity:{longitude},{latitude}"

        url = f"{self.base_url}/v2/places"
        params = {
            "categories": cat_param,
            "filter": filter_param,
            "bias": bias_param,
            "limit": lim,
            "apiKey": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    features = data.get("features", [])
                    results: List[PlaceRecommendation] = []

                    for feat in features:
                        props = feat.get("properties", {})
                        geom = feat.get("geometry", {})
                        coords = geom.get("coordinates", [])

                        place_lon = coords[0] if len(coords) >= 2 else props.get("lon")
                        place_lat = coords[1] if len(coords) >= 2 else props.get("lat")
                        place_name = props.get("name") or props.get("formatted", "Local Attraction")

                        # Generate map directions link
                        map_url = None
                        if place_lat and place_lon:
                            map_url = f"https://www.google.com/maps/search/?api=1&query={place_lat},{place_lon}"

                        # Format category
                        primary_category = None
                        cats = props.get("categories", [])
                        if cats:
                            primary_category = cats[0].replace(".", " / ").title()

                        results.append(
                            PlaceRecommendation(
                                place_id=props.get("place_id") or f"geo_{props.get('osm_id', id(props))}",
                                name=place_name,
                                category=primary_category,
                                address=props.get("formatted") or props.get("address_line2"),
                                latitude=place_lat,
                                longitude=place_lon,
                                description=props.get("description"),
                                match_explanation=None,
                                estimated_visit_minutes=60,
                                data_source="geoapify",
                                is_estimate=False,
                                map_url=map_url,
                            )
                        )

                    logger.info(f"Geoapify discovered {len(results)} verified places")
                    return results

                logger.warning(f"Geoapify places search failed with status {response.status_code}")
                return []

        except httpx.HTTPError as exc:
            logger.warning(f"Geoapify places network error: {str(exc)}")
            return []
