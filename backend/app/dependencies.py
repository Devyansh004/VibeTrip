"""Dependency injection providers and authentication utilities."""

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.qloo_service import QlooService
from app.services.groq_service import GroqService
from app.services.geoapify_service import GeoapifyService
from app.services.matching_service import MatchingService
from app.services.itinerary_service import ItineraryService
from app.services.preference_service import PreferenceService
from app.services.orchestrator import TravelAgentOrchestrator


def get_qloo_service(settings: Settings = Depends(get_settings)) -> QlooService:
    return QlooService(settings)


def get_groq_service(settings: Settings = Depends(get_settings)) -> GroqService:
    return GroqService(settings)


def get_geoapify_service(settings: Settings = Depends(get_settings)) -> GeoapifyService:
    return GeoapifyService(settings)


def get_matching_service() -> MatchingService:
    return MatchingService()


def get_itinerary_service() -> ItineraryService:
    return ItineraryService()


def get_preference_service() -> PreferenceService:
    return PreferenceService()


def get_orchestrator(
    settings: Settings = Depends(get_settings),
    qloo: QlooService = Depends(get_qloo_service),
    groq: GroqService = Depends(get_groq_service),
    geoapify: GeoapifyService = Depends(get_geoapify_service),
    matching: MatchingService = Depends(get_matching_service),
    itinerary: ItineraryService = Depends(get_itinerary_service),
    preference: PreferenceService = Depends(get_preference_service),
) -> TravelAgentOrchestrator:
    return TravelAgentOrchestrator(
        settings=settings,
        qloo_service=qloo,
        groq_service=groq,
        geoapify_service=geoapify,
        matching_service=matching,
        itinerary_service=itinerary,
        preference_service=preference,
    )

