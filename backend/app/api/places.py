"""Places search and discovery endpoint."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.places import PlaceSearchRequest, PlaceRecommendation
from app.services.geoapify_service import GeoapifyService
from app.dependencies import get_geoapify_service
from app.utils.logging import logger

router = APIRouter(prefix="/api/places", tags=["Places"])


@router.post("/search", response_model=List[PlaceRecommendation])
async def search_places(
    request: PlaceSearchRequest,
    geoapify: GeoapifyService = Depends(get_geoapify_service),
) -> List[PlaceRecommendation]:
    """Search for verified places by geographic coordinates or geocoded location."""
    if not geoapify.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Geoapify API credentials are not configured",
                "integration": "geoapify",
                "status": "not_configured",
            },
        )

    lat = request.latitude
    lon = request.longitude

    if (lat is None or lon is None) and request.location:
        clean_loc = request.location.strip()
        if not clean_loc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either valid coordinates (latitude & longitude) or a searchable location string must be provided",
            )
        geocode_result = await geoapify.geocode_location(clean_loc)
        if geocode_result:
            lat = geocode_result["latitude"]
            lon = geocode_result["longitude"]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to geocode location '{request.location}'",
            )

    if lat is None or lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either valid coordinates (latitude & longitude) or a searchable location string must be provided",
        )


    categories = request.categories
    if not categories:
        categories = ["tourism.sights", "catering.cafe"]

    try:
        places = await geoapify.search_places(
            latitude=lat,
            longitude=lon,
            categories=categories,
            radius_meters=request.radius_meters,
            limit=request.limit,
        )
        return places
    except Exception as exc:
        logger.error(f"Error in places search: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing place discovery: {str(exc)}",
        )
