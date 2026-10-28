"""Qloo API integration service for taste intelligence and cultural recommendations."""

from typing import Dict, Any, List, Optional
import httpx

from app.config import Settings, get_settings
from app.utils.logging import logger
from app.utils.exceptions import ConfigurationError, ExternalAPIError


class QlooService:
    """Service client for Qloo Hackathon Taste Intelligence API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.qloo_base_url.rstrip("/")
        self.api_key = self.settings.qloo_api_key
        self.timeout = 15.0

    @property
    def is_configured(self) -> bool:
        """Check if service has valid API credentials."""
        return self.settings.is_qloo_configured

    def _get_headers(self) -> Dict[str, str]:
        """Construct request headers with X-Api-Key."""
        if not self.is_configured:
            raise ConfigurationError("Qloo API key is missing", integration="qloo")
        return {
            "X-Api-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "VibeTrip-Agent/1.0",
        }

    async def search_entities(self, query: str, entity_type: str = "urn:entity:place") -> List[Dict[str, Any]]:
        """Search for Qloo entities by name or keyword.

        Uses GET /v2/search with query and type parameters.
        Returns entities with entity_id for use in insights requests.
        """
        if not self.is_configured:
            logger.info("Qloo search_entities skipped: Qloo API key not configured")
            return []

        url = f"{self.base_url}/v2/search"
        params = {"query": query, "type": entity_type}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("results", [])
                logger.warning(f"Qloo entity search returned status {response.status_code}: {response.text[:200]}")
                return []
        except httpx.HTTPError as exc:
            logger.warning(f"Qloo search_entities network error: {str(exc)}")
            return []

    async def search_tags(self, query: str) -> List[Dict[str, Any]]:
        """Search for Qloo interest/taste tags by keyword.

        Uses GET /v2/tags with filter.query parameter.
        Returns tags with id for use in insights requests.
        """
        if not self.is_configured:
            logger.info("Qloo search_tags skipped: Qloo API key not configured")
            return []

        url = f"{self.base_url}/v2/tags"
        params = {"filter.query": query}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("results", {}).get("tags", [])
                logger.warning(f"Qloo search_tags returned status {response.status_code}: {response.text[:200]}")
                return []
        except httpx.HTTPError as exc:
            logger.warning(f"Qloo search_tags network error: {str(exc)}")
            return []

    async def _resolve_interest_entities(self, interests: List[str], max_entities: int = 10) -> List[str]:
        """Resolve user interest keywords to Qloo entity IDs via search.

        Searches for each interest keyword and collects valid entity_ids.
        """
        entity_ids: List[str] = []
        seen: set[str] = set()

        for interest in interests[:5]:
            if not interest.strip():
                continue
            results = await self.search_entities(interest.strip())
            for entity in results:
                eid = entity.get("entity_id")
                if eid and eid not in seen:
                    seen.add(eid)
                    entity_ids.append(eid)
                    if len(entity_ids) >= max_entities:
                        break
            if len(entity_ids) >= max_entities:
                break

        return entity_ids

    async def get_taste_insights(
        self,
        preferences: Dict[str, Any],
        destination: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query Qloo /v2/insights for taste intelligence and cultural correlations.

        Uses GET /v2/insights with:
        - filter.type=urn:entity:place (required)
        - signal.interests.entities - valid Qloo entity IDs from search
        - filter.location.query - destination string
        """
        if not self.is_configured:
            logger.info("Qloo get_taste_insights skipped: Qloo API key not configured")
            return {
                "status": "not_configured",
                "message": "Qloo API credentials are not configured",
                "signals": [],
                "insights": {},
            }

        url = f"{self.base_url}/v2/insights"

        interests = preferences.get("interests", [])
        atmosphere = preferences.get("atmosphere", [])
        combined_signals = list(set([str(i).lower().strip() for i in (interests + atmosphere)]))

        entity_ids = await self._resolve_interest_entities(combined_signals)

        if not entity_ids:
            logger.info("No valid Qloo entities found for interests; skipping insights")
            return {
                "status": "no_entities",
                "message": "No valid Qloo entities could be resolved for the given interests",
                "signals_used": combined_signals,
                "insights": {},
            }

        params: Dict[str, Any] = {
            "filter.type": "urn:entity:place",
            "signal.interests.entities": ",".join(entity_ids),
        }
        if destination:
            params["filter.location.query"] = destination

        logger.info(f"Querying Qloo insights at {url} with {len(entity_ids)} entities, location={destination}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)

                if response.status_code == 200:
                    data = response.json()
                    logger.info("Qloo insights retrieved successfully")
                    entities = data.get("results", {}).get("entities", [])
                    affinity_categories = []
                    affinity_tags = []  # Structured tag data: (tag_type, tag_name, tag_id, weight)
                    for entity in entities:
                        tags = entity.get("tags") or []
                        for tag in tags:
                            tag_name = tag.get("name")
                            tag_id = tag.get("id")
                            tag_type = tag.get("type")
                            weight = tag.get("weight")
                            if tag_name and tag_name not in affinity_categories:
                                affinity_categories.append(tag_name)
                            if tag_id and tag_type:
                                affinity_tags.append({
                                    "type": tag_type,
                                    "name": tag_name,
                                    "id": tag_id,
                                    "weight": weight,
                                })

                    return {
                        "status": "success",
                        "data": data,
                        "signals_used": combined_signals,
                        "entity_ids_used": entity_ids,
                        "entity_popularity": {e.get("entity_id"): e.get("popularity", 0) for e in entities},
                        "taste_profile": data.get("taste_profile", {}),
                        "affinity_categories": affinity_categories[:20],
                        "affinity_tags": affinity_tags[:50],
                    }
                elif response.status_code in (401, 403):
                    logger.error("Qloo API authentication failed: invalid or unauthorized key")
                    return {
                        "status": "failed",
                        "message": "Qloo API authentication failed (401/403)",
                        "error_code": "UNAUTHORIZED",
                    }
                else:
                    logger.warning(f"Qloo insights endpoint returned HTTP {response.status_code}: {response.text[:500]}")
                    return {
                        "status": "failed",
                        "message": f"Qloo API returned HTTP {response.status_code}",
                        "error_code": f"HTTP_{response.status_code}",
                        "details": response.text[:500],
                    }

        except httpx.TimeoutException:
            logger.warning("Qloo insights request timed out")
            return {
                "status": "failed",
                "message": "Qloo API request timed out",
                "error_code": "TIMEOUT",
            }
        except httpx.HTTPError as exc:
            logger.warning(f"Qloo network error: {str(exc)}")
            return {
                "status": "failed",
                "message": f"Qloo network error: {str(exc)}",
                "error_code": "NETWORK_ERROR",
            }
