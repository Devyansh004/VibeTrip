"""Travel itinerary planning and personalization endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.planning import TravelPlanRequest, TravelPlanResponse, PersonalizePlanRequest
from app.services.orchestrator import TravelAgentOrchestrator
from app.dependencies import get_orchestrator
from app.utils.logging import logger

router = APIRouter(prefix="/api", tags=["Planner"])


@router.post("/plan", response_model=TravelPlanResponse)
async def plan_trip(
    request: TravelPlanRequest,
    orchestrator: TravelAgentOrchestrator = Depends(get_orchestrator),
) -> TravelPlanResponse:
    """Generate a personalized travel plan and itinerary matching user vibe and taste preferences."""
    try:
        response = await orchestrator.plan_trip(request)
        return response
    except ValueError as exc:
        logger.warning(f"Validation error in trip planning: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error(f"Unexpected error orchestrating trip plan: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the itinerary: {str(exc)}",
        )


@router.post("/plan/personalize", response_model=TravelPlanResponse)
async def personalize_trip(
    request: PersonalizePlanRequest,
    orchestrator: TravelAgentOrchestrator = Depends(get_orchestrator),
) -> TravelPlanResponse:
    """Personalize and refine an existing itinerary based on natural-language instructions and place selections."""
    try:
        response = await orchestrator.personalize_trip(request)
        return response
    except ValueError as exc:
        logger.warning(f"Validation error in itinerary personalization: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.error(f"Unexpected error personalizing itinerary: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while personalizing the itinerary: {str(exc)}",
        )
