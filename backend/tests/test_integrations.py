"""Unit tests for integration services, timeouts, and graceful degradation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Settings
from app.services.qloo_service import QlooService
from app.services.geoapify_service import GeoapifyService
from app.services.groq_service import GroqService
from app.services.itinerary_service import ItineraryService
from app.schemas.places import PlaceRecommendation


@pytest.mark.asyncio
async def test_qloo_service_unconfigured():
    """Verify Qloo service handles missing credentials honestly."""
    settings = Settings(qloo_api_key=None)
    qloo = QlooService(settings)
    assert not qloo.is_configured
    insights = await qloo.get_taste_insights(preferences={"interests": ["cafes"]})
    assert insights["status"] == "not_configured"
    assert "not configured" in insights["message"].lower()


@pytest.mark.asyncio
async def test_qloo_search_entities_parameter_format():
    """Verify Qloo search_entities uses correct endpoint and params."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.__aenter__.return_value.status_code = 200
        mock_get.return_value.__aenter__.return_value.json.return_value = {"results": []}
        
        await qloo.search_entities("cafe", "urn:entity:place")
        
        # Verify correct URL and params
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://hackathon.api.qloo.com/v2/search"
        assert call_args[1]["params"]["query"] == "cafe"
        assert call_args[1]["params"]["type"] == "urn:entity:place"
        assert call_args[1]["headers"]["X-Api-Key"] == "test_key"


@pytest.mark.asyncio
async def test_qloo_search_tags_parameter_format():
    """Verify Qloo search_tags uses correct endpoint and filter.query param."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.__aenter__.return_value.status_code = 200
        mock_get.return_value.__aenter__.return_value.json.return_value = {"results": {"tags": []}}
        
        await qloo.search_tags("cafe")
        
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://hackathon.api.qloo.com/v2/tags"
        assert call_args[1]["params"]["filter.query"] == "cafe"


@pytest.mark.asyncio
async def test_qloo_insights_parameter_format():
    """Verify Qloo get_taste_insights uses correct parameter format for /v2/insights."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    # Mock search_entities to return entities with entity_id
    with patch.object(qloo, "search_entities", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {"entity_id": "ent_1", "name": "Test Cafe"},
            {"entity_id": "ent_2", "name": "Test Museum"},
        ]
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.__aenter__.return_value.status_code = 200
            mock_get.return_value.__aenter__.return_value.json.return_value = {
                "results": {"entities": [{"tags": [{"name": "Cafe"}]}]}
            }
            
            await qloo.get_taste_insights(
                preferences={"interests": ["cafes"], "atmosphere": ["peaceful"]},
                destination="Jaipur"
            )
            
            call_args = mock_get.call_args
            assert call_args[0][0] == "https://hackathon.api.qloo.com/v2/insights"
            params = call_args[1]["params"]
            assert params["filter.type"] == "urn:entity:place"
            assert "signal.interests.entities" in params
            assert params["signal.interests.entities"] == "ent_1,ent_2"
            assert params["filter.location.query"] == "Jaipur"


@pytest.mark.asyncio
async def test_qloo_insights_http_400_error():
    """Verify Qloo handles HTTP 400 with error details."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    with patch.object(qloo, "search_entities", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [{"entity_id": "ent_1"}]
        
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"errors":[{"message":"filter.type is required"}]}'
        
        with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await qloo.get_taste_insights(
                preferences={"interests": ["cafes"]},
                destination="Jaipur"
            )
            
            assert result["status"] == "failed"
            assert "HTTP_400" in result["error_code"]
            assert "filter.type is required" in result["details"]


@pytest.mark.asyncio
async def test_qloo_insights_no_entities_found():
    """Verify Qloo handles case when no entities can be resolved for interests."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    with patch.object(qloo, "search_entities", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []  # No entities found
        
        result = await qloo.get_taste_insights(
            preferences={"interests": ["nonexistent_interest_xyz"]},
            destination="Jaipur"
        )
        
        assert result["status"] == "no_entities"
        assert "No valid Qloo entities" in result["message"]


@pytest.mark.asyncio
async def test_qloo_insights_empty_results():
    """Verify Qloo handles empty insights response gracefully."""
    settings = Settings(qloo_api_key="test_key")
    qloo = QlooService(settings)
    
    with patch.object(qloo, "search_entities", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [{"entity_id": "ent_1"}]
        
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"entities": []}
        }
        
        with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await qloo.get_taste_insights(
                preferences={"interests": ["cafes"]},
                destination="Jaipur"
            )
            
            assert result["status"] == "success"
            assert result["affinity_categories"] == []


@pytest.mark.asyncio
async def test_geoapify_service_unconfigured():
    """Verify Geoapify service handles missing credentials cleanly."""
    settings = Settings(geoapify_api_key=None)
    geoapify = GeoapifyService(settings)
    assert not geoapify.is_configured
    geocode = await geoapify.geocode_location("Jaipur")
    assert geocode is None
    places = await geoapify.search_places(latitude=26.9, longitude=75.8, categories=["catering.cafe"])
    assert places == []


@pytest.mark.asyncio
async def test_groq_service_unconfigured():
    """Verify Groq service provides transparent fallback when unconfigured."""
    settings = Settings(groq_api_key=None)
    groq = GroqService(settings)
    assert not groq.is_configured
    pref = await groq.extract_preferences({
        "interests": ["music", "cafes"],
        "atmosphere": ["peaceful"],
        "travel_pace": "relaxed",
    })
    assert "music" in pref.interests
    assert "cafes" in pref.interests
    assert pref.travel_pace == "relaxed"


def test_itinerary_place_id_grounding():
    """Verify that unverified place IDs referenced in raw activities are removed."""
    svc = ItineraryService()
    verified_places = [
        PlaceRecommendation(
            place_id="real_place_1",
            name="Real Cafe",
            category="Cafe",
        )
    ]
    raw_days = [
        {
            "theme": "Discovery",
            "activities": [
                {
                    "title": "Breakfast at Real Cafe",
                    "place_id": "real_place_1",
                },
                {
                    "title": "Visit Fake Venue",
                    "place_id": "hallucinated_place_999",  # Not in verified_places
                },
            ],
        }
    ]

    validated_days = svc.validate_and_normalize_itinerary(
        raw_days=raw_days,
        duration_days=1,
        start_date=None,
        places=verified_places,
    )

    activities = validated_days[0].activities
    assert activities[0].place_id == "real_place_1"
    # Unverified place ID must be grounded / stripped to None
    assert activities[1].place_id is None


# --- Matching Service Tests ---

def test_matching_service_basic_scoring():
    """Verify basic interest and atmosphere scoring works."""
    from app.services.matching_service import MatchingService
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    places = [
        PlaceRecommendation(place_id="p1", name="Cafe Roma", category="Catering / Cafe"),
        PlaceRecommendation(place_id="p2", name="History Museum", category="Entertainment / Museum"),
        PlaceRecommendation(place_id="p3", name="Random Shop", category="Commercial / Shop"),
    ]
    ranked = svc.rank_and_explain_places(
        places=places,
        interests=["cafes", "history"],
        atmosphere=["peaceful"],
    )
    # Cafe Roma should score highest (matches "cafes")
    assert ranked[0].place_id == "p1"
    assert "cafes" in ranked[0].match_explanation


def test_matching_service_qloo_affinity_tag_influence():
    """Verify Qloo affinity tags influence ranking via semantic Geoapify category mapping."""
    from app.services.matching_service import MatchingService, QLOO_TAG_TYPE_TO_GEOAPIFY
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    
    # Two places with different Geoapify categories
    places = [
        PlaceRecommendation(
            place_id="cafe_1",
            name="Italian Cafe",
            category="Catering / Cafe",  # Maps to catering.cafe
        ),
        PlaceRecommendation(
            place_id="museum_1",
            name="Art Museum",
            category="Entertainment / Museum",  # Maps to entertainment.museum
        ),
        PlaceRecommendation(
            place_id="shop_1",
            name="Random Shop",
            category="Commercial / Shop",  # Maps to commercial.shopping_mall
        ),
    ]

    # Qloo insights with ONLY cuisine tag (should boost catering.cafe)
    # Not including genre tag that would also match museum
    qloo_insights = {
        "status": "success",
        "affinity_tags": [
            {"type": "urn:tag:cuisine:qloo:italian", "name": "Italian", "id": "urn:tag:cuisine:qloo:italian", "weight": 1.0},
        ],
        "entity_popularity": {},
    }

    ranked = svc.rank_and_explain_places(
        places=places,
        interests=["history"],  # Museum matches this
        atmosphere=["peaceful"],
        qloo_insights=qloo_insights,
    )

    # Cafe should now rank highest due to Qloo cuisine tag -> catering.cafe mapping
    # Even though "history" interest matches museum, Qloo boost for cafe (3.0) should overcome history match (2.0)
    assert ranked[0].place_id == "cafe_1"
    assert "Qloo taste insights" in ranked[0].match_explanation or "ranked higher by Qloo" in ranked[0].match_explanation


def test_matching_service_qloo_direct_entity_match():
    """Verify direct Qloo entity ID match boosts score."""
    from app.services.matching_service import MatchingService
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    places = [
        PlaceRecommendation(place_id="ent_1", name="Qloo Entity Cafe", category="Catering / Cafe"),
        PlaceRecommendation(place_id="other_1", name="Regular Cafe", category="Catering / Cafe"),
    ]

    qloo_insights = {
        "status": "success",
        "affinity_tags": [],
        "entity_popularity": {"ent_1": 0.9},  # High popularity
    }

    ranked = svc.rank_and_explain_places(
        places=places,
        interests=[],
        atmosphere=[],
        qloo_insights=qloo_insights,
    )

    # ent_1 should rank higher due to direct entity match + popularity
    assert ranked[0].place_id == "ent_1"
    assert "Qloo taste insights" in ranked[0].match_explanation


def test_matching_service_qloo_no_match_explanation():
    """Verify honest explanation when Qloo available but no match for a place."""
    from app.services.matching_service import MatchingService
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    places = [
        PlaceRecommendation(place_id="cafe_1", name="Cafe", category="Catering / Cafe"),
        PlaceRecommendation(place_id="shop_1", name="Shop", category="Commercial / Shop"),
    ]

    qloo_insights = {
        "status": "success",
        "affinity_tags": [
            {"type": "urn:tag:cuisine:qloo:italian", "name": "Italian", "id": "urn:tag:cuisine:qloo:italian", "weight": 1.0},
        ],
        "entity_popularity": {},
    }

    ranked = svc.rank_and_explain_places(
        places=places,
        interests=[],
        atmosphere=[],
        qloo_insights=qloo_insights,
    )

    # Cafe gets Qloo boost, shop doesn't
    cafe_explanation = next(p.match_explanation for p in ranked if p.place_id == "cafe_1")
    shop_explanation = next(p.match_explanation for p in ranked if p.place_id == "shop_1")
    
    assert "ranked higher by Qloo" in cafe_explanation
    assert "no direct match" in shop_explanation.lower()


def test_matching_service_missing_qloo_fallback():
    """Verify graceful fallback when Qloo insights missing or failed."""
    from app.services.matching_service import MatchingService
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    places = [
        PlaceRecommendation(place_id="p1", name="Cafe", category="Catering / Cafe"),
    ]

    # Qloo failed
    ranked = svc.rank_and_explain_places(
        places=places,
        interests=["cafes"],
        atmosphere=["peaceful"],
        qloo_insights={"status": "failed", "message": "API error"},
    )
    assert len(ranked) == 1
    assert ranked[0].data_source == "geoapify"

    # Qloo not configured
    ranked = svc.rank_and_explain_places(
        places=places,
        interests=["cafes"],
        atmosphere=["peaceful"],
        qloo_insights=None,
    )
    assert ranked[0].data_source == "geoapify"


def test_matching_service_different_preferences_different_rankings():
    """Verify different preference inputs produce different rankings when candidate data differs."""
    from app.services.matching_service import MatchingService
    from app.schemas.places import PlaceRecommendation

    svc = MatchingService()
    places = [
        PlaceRecommendation(place_id="cafe", name="Cafe", category="Catering / Cafe"),
        PlaceRecommendation(place_id="museum", name="Museum", category="Entertainment / Museum"),
        PlaceRecommendation(place_id="park", name="Park", category="Natural / Park"),
    ]

    # Pref 1: cafes
    ranked_cafe = svc.rank_and_explain_places(
        places=places,
        interests=["cafes"],
        atmosphere=[],
        qloo_insights=None,
    )
    assert ranked_cafe[0].place_id == "cafe"

    # Pref 2: history
    ranked_history = svc.rank_and_explain_places(
        places=places,
        interests=["history"],
        atmosphere=[],
        qloo_insights=None,
    )
    assert ranked_history[0].place_id == "museum"

    # Pref 3: nature
    ranked_nature = svc.rank_and_explain_places(
        places=places,
        interests=["nature"],
        atmosphere=[],
        qloo_insights=None,
    )
    assert ranked_nature[0].place_id == "park"


# --- Groq JSON Mode & Personalization Tests ---

@pytest.mark.asyncio
async def test_groq_json_mode_configured_in_generate_and_personalize():
    """Verify that GroqService passes response_format={'type': 'json_object'}."""
    settings = Settings(groq_api_key="gsk_test_key")
    groq = GroqService(settings)

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"summary": "Test", "days": []}'))
    ]

    with patch.object(groq, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        # Test generate_itinerary
        await groq.generate_itinerary(
            destination="Jaipur",
            duration_days=1,
            preferences={"interests": ["cafes"]},
            taste_insights=None,
            places=[],
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}

        # Test personalize_itinerary
        await groq.personalize_itinerary(
            current_itinerary=[],
            destination="Jaipur",
            preferences={},
            instructions="Make it relaxed",
            selected_place_ids=[],
            excluded_place_ids=[],
            available_places=[],
        )

        call_kwargs2 = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs2.get("response_format") == {"type": "json_object"}


def test_validate_personalized_itinerary_enforces_exclusions_and_grounding():
    """Verify validate_personalized_itinerary removes excluded and fabricated place IDs."""
    svc = ItineraryService()

    allowed_place = PlaceRecommendation(
        place_id="real_cafe_1",
        name="Real Cafe",
        category="Cafe",
    )
    excluded_place = PlaceRecommendation(
        place_id="noisy_bar_2",
        name="Noisy Bar",
        category="Bar",
    )

    available_places = [allowed_place, excluded_place]

    raw_days = [
        {
            "day_number": 1,
            "theme": "Quiet Exploration",
            "activities": [
                {
                    "title": "Visit Real Cafe",
                    "place_id": "real_cafe_1",
                },
                {
                    "title": "Visit Noisy Bar",
                    "place_id": "noisy_bar_2",  # In excluded list!
                },
                {
                    "title": "Visit Hallucinated Venue",
                    "place_id": "fake_place_999",  # Not in available_places!
                },
            ],
        }
    ]

    validated_days, warnings = svc.validate_personalized_itinerary(
        raw_days=raw_days,
        duration_days=1,
        start_date=None,
        available_places=available_places,
        selected_place_ids=["real_cafe_1"],
        excluded_place_ids=["noisy_bar_2"],
    )

    activities = validated_days[0].activities
    # 1. Allowed place retained
    assert activities[0].place_id == "real_cafe_1"
    # 2. Excluded place stripped
    assert activities[1].place_id is None
    # 3. Hallucinated place stripped
    assert activities[2].place_id is None

    # Verify warnings were generated
    warning_text = " ".join(warnings).lower()
    assert "excluded" in warning_text
    assert "unverified" in warning_text or "fabricated" in warning_text


def test_validate_personalized_itinerary_fulfills_selected_places():
    """Verify validate_personalized_itinerary injects unfulfilled selected places where feasible."""
    svc = ItineraryService()

    must_visit = PlaceRecommendation(
        place_id="must_visit_spot",
        name="Heritage Palace",
        category="Historic Sights",
    )

    raw_days = [
        {
            "day_number": 1,
            "theme": "Palace Tour",
            "activities": [
                {
                    "title": "Morning Stroll",
                    "place_id": None,  # Open slot
                }
            ],
        }
    ]

    validated_days, warnings = svc.validate_personalized_itinerary(
        raw_days=raw_days,
        duration_days=1,
        start_date=None,
        available_places=[must_visit],
        selected_place_ids=["must_visit_spot"],
        excluded_place_ids=[],
    )

    activities = validated_days[0].activities
    # The open slot should be assigned to the selected must_visit_spot
    assert activities[0].place_id == "must_visit_spot"
    assert "Heritage Palace" in activities[0].title


@pytest.mark.asyncio
async def test_orchestrator_personalize_trip_success():
    """Verify TravelAgentOrchestrator.personalize_trip successfully refines plan."""
    from app.schemas.planning import TravelPlanResponse, PersonalizePlanRequest
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    from app.schemas.places import PlaceRecommendation
    from app.services.orchestrator import TravelAgentOrchestrator

    mock_place = PlaceRecommendation(
        place_id="geo_garden_1",
        name="Scenic Garden",
        category="Park",
    )

    base_plan = TravelPlanResponse(
        trip_id="trip-abc-123",
        destination="Kyoto",
        summary="Original Kyoto Journey",
        preferences={"travel_pace": "balanced", "interests": ["nature"]},
        recommended_places=[mock_place],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Original Day",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1_1",
                        title="City Walk",
                        description="Explore city center",
                        place_id=None,
                        day_number=1,
                    )
                ],
            )
        ],
        integration_status={"groq": "success"},
        warnings=[],
    )

    mock_groq = MagicMock(spec=GroqService)
    mock_groq.is_configured = True
    mock_groq.personalize_itinerary = AsyncMock(return_value={
        "summary": "Personalized relaxing nature retreat in Kyoto.",
        "days": [
            {
                "day_number": 1,
                "theme": "Relaxing Garden Retreat",
                "activities": [
                    {
                        "activity_id": "act_1_1",
                        "title": "Visit Scenic Garden",
                        "place_id": "geo_garden_1",
                        "day_number": 1,
                    }
                ],
            }
        ],
    })

    orchestrator = TravelAgentOrchestrator(groq_service=mock_groq)

    req = PersonalizePlanRequest(
        instructions="Focus on scenic gardens and keep it relaxed",
        current_plan=base_plan,
        selected_place_ids=["geo_garden_1"],
        excluded_place_ids=[],
    )

    result = await orchestrator.personalize_trip(req)
    assert result.destination == "Kyoto"
    assert "Personalized relaxing" in result.summary
    assert result.itinerary[0].activities[0].place_id == "geo_garden_1"
    assert result.integration_status["groq"] == "success"


@pytest.mark.asyncio
async def test_orchestrator_personalize_trip_groq_failure_preserves_base_plan():
    """Verify that if Groq fails during personalization, base plan is preserved without false success."""
    from app.schemas.planning import TravelPlanResponse, PersonalizePlanRequest
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    from app.services.orchestrator import TravelAgentOrchestrator

    base_plan = TravelPlanResponse(
        trip_id="trip-fail-test",
        destination="Kyoto",
        summary="Original summary",
        preferences={"travel_pace": "balanced"},
        recommended_places=[],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Original Theme",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1_1",
                        title="Original Activity",
                        description="Original description",
                        place_id=None,
                        day_number=1,
                    )
                ],
            )
        ],
        integration_status={"groq": "success"},
        warnings=[],
    )

    mock_groq = MagicMock(spec=GroqService)
    mock_groq.is_configured = True
    mock_groq.personalize_itinerary = AsyncMock(side_effect=RuntimeError("Groq 429 rate limit exceeded"))

    orchestrator = TravelAgentOrchestrator(groq_service=mock_groq)

    req = PersonalizePlanRequest(
        instructions="Make it more adventurous",
        current_plan=base_plan,
    )

    result = await orchestrator.personalize_trip(req)
    # Original summary and itinerary must be preserved
    assert result.summary == "Original summary"
    assert result.itinerary[0].theme == "Original Theme"
    # Status must NOT be success!
    assert result.integration_status["groq"] == "failed"
    # Warning must explain Groq failure honestly
    assert any("failed" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_groq_personalize_caps_candidates_and_prioritizes_selected():
    """Verify GroqService.personalize_itinerary caps candidate places at 10, prioritizes selected, and truncates text."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.schemas.places import PlaceRecommendation
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    import json

    settings = Settings(groq_api_key="mock_key")
    svc = GroqService(settings)

    # 15 available places
    places = [
        PlaceRecommendation(
            place_id=f"place_{i}",
            name=f"Place Number {i}",
            category="Sightseeing",
            address=f"Very long street address for place {i} that exceeds normal lengths " * 3,
            description=f"Detailed verbose description of place {i} that goes on and on " * 5,
        )
        for i in range(1, 16)
    ]

    selected = ["place_14", "place_15"]  # Towards the end of the ranking
    excluded = ["place_1", "place_2"]

    captured_prompt = {}

    async def mock_create(**kwargs):
        messages = kwargs.get("messages", [])
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        captured_prompt["content"] = user_content
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "summary": "Updated summary",
                "days": [{"day_number": 1, "theme": "Day 1", "activities": []}]
            })))
        ]
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    itinerary = [
        DayItinerary(
            day_number=1,
            theme="Day 1",
            activities=[ItineraryActivity(activity_id="a1", title="Start", description="Morning walk", place_id=None, day_number=1)]
        )
    ]

    res = await svc.personalize_itinerary(
        current_itinerary=itinerary,
        destination="Kyoto",
        preferences={},
        instructions="Relaxing day",
        selected_place_ids=selected,
        excluded_place_ids=excluded,
        available_places=places,
    )

    prompt_text = captured_prompt["content"]
    assert prompt_text is not None

    # Extract JSON candidate dataset from prompt
    candidates_section = prompt_text.split("AVAILABLE VERIFIED PLACES DATASET:\n")[1].split("\n\nCRITICAL PERSONALIZATION")[0]
    candidate_data = json.loads(candidates_section)

    # Excluded places must NOT appear in candidate places
    candidate_ids = {p["place_id"] for p in candidate_data}
    assert "place_1" not in candidate_ids
    assert "place_2" not in candidate_ids

    # Prioritized must-include places must appear
    assert "place_14" in candidate_ids
    assert "place_15" in candidate_ids

    # Exactly 10 candidate places capped
    assert len(candidate_data) == 10

    # Selected places must have must_include=True
    selected_in_data = [p for p in candidate_data if p["place_id"] in selected]
    assert len(selected_in_data) == 2
    assert all(p["must_include"] is True for p in selected_in_data)

    # Check truncation
    for p in candidate_data:
        if "address" in p and p["address"]:
            assert len(p["address"]) <= 70
        if "description" in p and p["description"]:
            assert len(p["description"]) <= 100


@pytest.mark.asyncio
async def test_groq_personalize_selected_exceeds_cap_warning():
    """Verify truthful warning when selected places exceed the 10 candidate places limit."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.schemas.places import PlaceRecommendation
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    import json

    settings = Settings(groq_api_key="mock_key")
    svc = GroqService(settings)

    # 14 available places, user selects 12 of them
    places = [
        PlaceRecommendation(place_id=f"place_{i}", name=f"Place {i}", category="Spot")
        for i in range(1, 15)
    ]
    selected = [f"place_{i}" for i in range(1, 13)]  # 12 selected

    async def mock_create(**kwargs):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "summary": "Updated summary",
                "days": [{"day_number": 1, "theme": "Day 1", "activities": []}]
            })))
        ]
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    itinerary = [
        DayItinerary(
            day_number=1,
            theme="Day 1",
            activities=[ItineraryActivity(activity_id="a1", title="Start", description="Morning walk", place_id=None, day_number=1)]
        )
    ]

    res = await svc.personalize_itinerary(
        current_itinerary=itinerary,
        destination="Kyoto",
        preferences={},
        instructions="Visit all my places",
        selected_place_ids=selected,
        excluded_place_ids=[],
        available_places=places,
    )

    assert "warnings" in res
    assert any("candidate limit of 10" in w for w in res["warnings"])


@pytest.mark.asyncio
async def test_groq_retry_transient_429_then_success():
    """Verify that a transient 429 is retried with backoff and succeeds on subsequent attempt."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from openai import RateLimitError
    import httpx
    import json

    settings = Settings(groq_api_key="mock_key", groq_max_retries=2)
    svc = GroqService(settings)
    svc.base_retry_delay = 0.01

    call_count = 0
    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = httpx.Response(429, request=req, headers={"retry-after": "0.01"})
            raise RateLimitError("Rate limit reached", response=resp, body=None)
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "summary": "Updated summary",
                "days": [{"day_number": 1, "theme": "Day 1", "activities": []}]
            })))
        ]
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    res = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="Relaxing day",
        selected_place_ids=[],
        excluded_place_ids=[],
        available_places=[],
    )

    assert call_count == 2
    assert res.get("summary") == "Updated summary"


@pytest.mark.asyncio
async def test_groq_exhausted_daily_quota_no_repeated_retries():
    """Verify that a daily token quota (TPD) 429 fails immediately without pointless retries."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import RateLimitError
    import httpx

    settings = Settings(groq_api_key="mock_key", groq_max_retries=3)
    svc = GroqService(settings)

    call_count = 0
    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(429, request=req)
        # Real Groq message with organization ID and daily token quota details
        msg = (
            "Rate limit reached for model `openai/gpt-oss-20b` in organization `org_secret123` "
            "service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 196614. "
            "Please try again in 6m9s."
        )
        raise RateLimitError(msg, response=resp, body=None)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    with pytest.raises(GroqServiceException) as exc_info:
        await svc.personalize_itinerary(
            current_itinerary=[],
            destination="Kyoto",
            preferences={},
            instructions="Relaxing day",
            selected_place_ids=[],
            excluded_place_ids=[],
            available_places=[],
        )

    # Must fail on the FIRST attempt without retrying
    assert call_count == 1
    assert exc_info.value.category == "quota_exhausted"
    assert exc_info.value.is_retryable is False
    assert "daily token limit" in exc_info.value.user_friendly_message.lower()
    # Must NOT expose raw organization ID or secrets
    assert "org_secret123" not in exc_info.value.user_friendly_message


@pytest.mark.asyncio
async def test_groq_authentication_and_invalid_model_no_retries():
    """Verify that 401 AuthenticationError and 404 Model Not Found do not loop or retry."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import AuthenticationError, NotFoundError
    import httpx

    settings = Settings(groq_api_key="mock_key", groq_max_retries=3)
    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")

    # 1. Authentication Error
    svc1 = GroqService(settings)
    call_count1 = 0

    async def mock_auth_error(**kwargs):
        nonlocal call_count1
        call_count1 += 1
        resp = httpx.Response(401, request=req)
        raise AuthenticationError("Invalid API key secret_groq_key_123", response=resp, body=None)

    mock_client1 = MagicMock()
    mock_client1.chat.completions.create = AsyncMock(side_effect=mock_auth_error)
    svc1._client = mock_client1

    with pytest.raises(GroqServiceException) as exc_info1:
        await svc1.personalize_itinerary(
            current_itinerary=[],
            destination="Kyoto",
            preferences={},
            instructions="Relaxing day",
            selected_place_ids=[],
            excluded_place_ids=[],
            available_places=[],
        )

    assert call_count1 == 1
    assert exc_info1.value.category == "authentication_error"
    assert "secret_groq_key_123" not in exc_info1.value.user_friendly_message

    # 2. Model Unavailable
    svc2 = GroqService(settings)
    call_count2 = 0

    async def mock_not_found(**kwargs):
        nonlocal call_count2
        call_count2 += 1
        resp = httpx.Response(404, request=req)
        raise NotFoundError("The model `openai/gpt-oss-20b` does not exist", response=resp, body=None)

    mock_client2 = MagicMock()
    mock_client2.chat.completions.create = AsyncMock(side_effect=mock_not_found)
    svc2._client = mock_client2

    with pytest.raises(GroqServiceException) as exc_info2:
        await svc2.personalize_itinerary(
            current_itinerary=[],
            destination="Kyoto",
            preferences={},
            instructions="Relaxing day",
            selected_place_ids=[],
            excluded_place_ids=[],
            available_places=[],
        )

    assert call_count2 == 1
    assert exc_info2.value.category == "model_unavailable"


@pytest.mark.asyncio
async def test_orchestrator_personalize_fallback_with_safe_redacted_warnings():
    """Verify that orchestrator returns original itinerary and safe warnings without secret leakage."""
    from app.schemas.planning import TravelPlanResponse, PersonalizePlanRequest
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    from app.services.orchestrator import TravelAgentOrchestrator
    from app.utils.exceptions import GroqServiceException

    base_plan = TravelPlanResponse(
        trip_id="trip-redact-test",
        destination="Kyoto",
        summary="Original Kyoto summary",
        preferences={"travel_pace": "balanced"},
        recommended_places=[],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Original Theme",
                activities=[
                    ItineraryActivity(
                        activity_id="act_1_1",
                        title="Original Sight",
                        description="Walk through gardens",
                        place_id=None,
                        day_number=1,
                    )
                ],
            )
        ],
        integration_status={"groq": "success"},
        warnings=[],
    )

    mock_groq = MagicMock(spec=GroqService)
    mock_groq.is_configured = True
    # Raise a classified exception containing safe message and sensitive internal detail
    mock_groq.personalize_itinerary = AsyncMock(
        side_effect=GroqServiceException(
            message="Internal groq quota detail with org_private_key",
            category="quota_exhausted",
            user_friendly_message="Groq daily token limit (TPD) reached for this service tier. Original itinerary was preserved.",
        )
    )

    orchestrator = TravelAgentOrchestrator(groq_service=mock_groq)

    req = PersonalizePlanRequest(
        instructions="Make it more relaxed and scenic",
        current_plan=base_plan,
    )

    result = await orchestrator.personalize_trip(req)

    # 1. Base itinerary and summary strictly preserved
    assert result.summary == "Original Kyoto summary"
    assert result.itinerary[0].theme == "Original Theme"
    # 2. Status honestly set to failed
    assert result.integration_status["groq"] == "failed"
    # 3. Warning presents clear explanation
    assert any("daily token limit" in w.lower() for w in result.warnings)
    # 4. Sensitive detail strictly redacted
    for w in result.warnings:
        assert "org_private_key" not in w


# ==============================================================================
# BIDIRECTIONAL MODEL FAILOVER DETERMINISTIC UNIT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_groq_failover_primary_succeeds_without_failover():
    """Verify that when primary model succeeds, no failover occurs and primary model ID is recorded."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
    )
    svc = GroqService(settings)

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "summary": "Primary success summary",
                    "budget_breakdown": {"estimated_total": 50.0, "currency": "USD"},
                    "days": [{"day_number": 1, "theme": "Day 1", "activities": []}],
                })
            )
        )
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    svc._client = mock_client

    result = await svc.generate_itinerary(
        destination="Kyoto",
        duration_days=1,
        preferences={},
        taste_insights=None,
        places=[],
    )

    assert result["model_used"] == "openai/gpt-oss-20b"
    assert result["failover_occurred"] is False
    assert "warnings" not in result or not any("backup model" in w for w in result.get("warnings", []))
    assert mock_client.chat.completions.create.call_count == 1
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_groq_failover_primary_model_specific_quota_fallback_succeeds():
    """Verify primary model with model-specific TPM/RPM rate limit fails over to fallback model successfully."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from openai import RateLimitError
    import httpx
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=1,
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    models_called = []

    async def mock_create(**kwargs):
        model = kwargs.get("model")
        models_called.append(model)
        if model == "openai/gpt-oss-20b":
            resp = httpx.Response(429, request=req)
            # Model-specific TPM rate limit error
            raise RateLimitError(
                "Rate limit reached for model `openai/gpt-oss-20b` on tokens per minute (TPM): Limit 6000, Used 5900. Try again in 12s.",
                response=resp,
                body=None,
            )
        elif model == "openai/gpt-oss-120b":
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "Fallback success summary",
                            "budget_breakdown": {"estimated_total": 60.0, "currency": "USD"},
                            "days": [{"day_number": 1, "theme": "Day 1 Backup", "activities": []}],
                        })
                    )
                )
            ]
            return mock_resp
        raise ValueError(f"Unexpected model: {model}")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    result = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="Make it scenic",
        selected_place_ids=[],
        excluded_place_ids=[],
        available_places=[],
    )

    assert result["model_used"] == "openai/gpt-oss-120b"
    assert result["failover_occurred"] is True
    assert any("backup model (openai/gpt-oss-120b)" in w for w in result.get("warnings", []))
    assert models_called == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


@pytest.mark.asyncio
async def test_groq_failover_primary_fails_and_fallback_also_fails():
    """Verify that when both primary and fallback models fail, GroqServiceException is raised."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import InternalServerError
    import httpx

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=0,
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    models_called = []

    async def mock_server_error(**kwargs):
        model = kwargs.get("model")
        models_called.append(model)
        resp = httpx.Response(503, request=req)
        raise InternalServerError(f"Groq service unavailable for model {model}", response=resp, body=None)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_server_error)
    svc._client = mock_client

    with pytest.raises(GroqServiceException) as exc_info:
        await svc.generate_itinerary(
            destination="Kyoto",
            duration_days=1,
            preferences={},
            taste_insights=None,
            places=[],
        )

    assert exc_info.value.category == "server_error"
    assert models_called == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


@pytest.mark.asyncio
async def test_groq_failover_invalid_credentials_no_model_switch():
    """Verify that 401 AuthenticationError does not attempt fallback model."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import AuthenticationError
    import httpx

    settings = Settings(
        groq_api_key="mock_invalid_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    call_count = 0

    async def mock_auth_fail(**kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(401, request=req)
        raise AuthenticationError("Invalid API key", response=resp, body=None)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_auth_fail)
    svc._client = mock_client

    with pytest.raises(GroqServiceException) as exc_info:
        await svc.generate_itinerary(
            destination="Kyoto",
            duration_days=1,
            preferences={},
            taste_insights=None,
            places=[],
        )

    assert exc_info.value.category == "authentication_error"
    assert call_count == 1  # Never tried fallback model


@pytest.mark.asyncio
async def test_groq_failover_organization_quota_exhausted_no_repeated_calls():
    """Verify that confirmed organization-wide TPD limit does not make pointless fallback calls."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import RateLimitError
    import httpx

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=2,
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    call_count = 0

    async def mock_org_tpd(**kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(429, request=req)
        msg = (
            "Rate limit reached for model `openai/gpt-oss-20b` in organization `org_demo123` "
            "service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 200000. Try again in 8m."
        )
        raise RateLimitError(msg, response=resp, body=None)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_org_tpd)
    svc._client = mock_client

    with pytest.raises(GroqServiceException) as exc_info:
        await svc.generate_itinerary(
            destination="Kyoto",
            duration_days=1,
            preferences={},
            taste_insights=None,
            places=[],
        )

    assert exc_info.value.category == "quota_exhausted"
    assert call_count == 1  # Primary model only, zero calls to backup


@pytest.mark.asyncio
async def test_groq_failover_transient_rate_limit_bounded_retries():
    """Verify that a transient rate limit with small retry_after succeeds via bounded retry on primary model."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from openai import RateLimitError
    import httpx
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=2,
        groq_max_retry_wait_seconds=5.0,
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    attempts = 0

    async def mock_transient(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            resp = httpx.Response(429, request=req)
            raise RateLimitError("Rate limit reached. Try again in 0.05s", response=resp, body=None)
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "summary": "Primary retry success",
                        "budget_breakdown": {"estimated_total": 50.0, "currency": "USD"},
                        "days": [{"day_number": 1, "theme": "Day 1", "activities": []}],
                    })
                )
            )
        ]
        return mock_resp

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_transient)
    svc._client = mock_client

    result = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="Day 1 relaxing",
        selected_place_ids=[],
        excluded_place_ids=[],
        available_places=[],
    )

    assert attempts == 2
    assert result["model_used"] == "openai/gpt-oss-20b"
    assert result["failover_occurred"] is False


@pytest.mark.asyncio
async def test_groq_failover_bidirectional_request_scoped_next_request_prefers_primary():
    """Verify request-scoped failover: request 1 fails over to backup, but request 2 prefers primary again."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from openai import RateLimitError
    import httpx
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=0,
    )
    svc = GroqService(settings)

    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    primary_should_fail = True

    async def mock_create(**kwargs):
        model = kwargs.get("model")
        if model == "openai/gpt-oss-20b":
            if primary_should_fail:
                resp = httpx.Response(429, request=req)
                raise RateLimitError("Model openai/gpt-oss-20b capacity exceeded. Try again in 10s.", response=resp, body=None)
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "Primary recovered summary",
                            "budget_breakdown": {"estimated_total": 50.0, "currency": "USD"},
                            "days": [{"day_number": 1, "theme": "Day 1 Primary", "activities": []}],
                        })
                    )
                )
            ]
            return mock_resp
        elif model == "openai/gpt-oss-120b":
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "Fallback summary",
                            "budget_breakdown": {"estimated_total": 50.0, "currency": "USD"},
                            "days": [{"day_number": 1, "theme": "Day 1 Backup", "activities": []}],
                        })
                    )
                )
            ]
            return mock_resp
        raise ValueError(f"Unknown model: {model}")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    # Request 1: Primary fails -> fails over to fallback
    result1 = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="First request",
        selected_place_ids=[],
        excluded_place_ids=[],
        available_places=[],
    )
    assert result1["model_used"] == "openai/gpt-oss-120b"
    assert result1["failover_occurred"] is True

    # Critical check: service instance primary model was NOT mutated
    assert svc.primary_model == "openai/gpt-oss-20b"

    # Request 2: Primary is now available again
    primary_should_fail = False
    result2 = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="Second independent request",
        selected_place_ids=[],
        excluded_place_ids=[],
        available_places=[],
    )
    # Must prefer primary model again!
    assert result2["model_used"] == "openai/gpt-oss-20b"
    assert result2["failover_occurred"] is False


@pytest.mark.asyncio
async def test_groq_failover_malformed_json_triggers_failover_and_invalid_place_ids_rejected():
    """Verify malformed JSON triggers failover, and invalid/excluded place IDs cannot bypass validation."""
    from app.services.groq_service import GroqService
    from app.services.itinerary_service import ItineraryService
    from app.config import Settings
    from app.schemas.places import PlaceRecommendation
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
    )
    svc = GroqService(settings)

    async def mock_create(**kwargs):
        model = kwargs.get("model")
        mock_resp = MagicMock()
        if model == "openai/gpt-oss-20b":
            # Primary returns broken unparseable text
            mock_resp.choices = [
                MagicMock(message=MagicMock(content="<<<Broken Non-JSON Output>>>"))
            ]
            return mock_resp
        elif model == "openai/gpt-oss-120b":
            # Fallback returns JSON with:
            # 1. Valid place: 'place_valid'
            # 2. Fabricated place: 'fake_place_999'
            # 3. Excluded place: 'place_excluded'
            mock_resp.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "Fallback grounded summary",
                            "budget_breakdown": {"estimated_total": 45.0, "currency": "USD"},
                            "days": [
                                {
                                    "day_number": 1,
                                    "theme": "Cultural Morning",
                                    "activities": [
                                        {
                                            "activity_id": "act_1_1",
                                            "title": "Valid Temple",
                                            "description": "Authentic temple visit",
                                            "place_id": "place_valid",
                                            "day_number": 1,
                                            "time_label": "Morning",
                                        },
                                        {
                                            "activity_id": "act_1_2",
                                            "title": "Fabricated Stop",
                                            "description": "Fake place",
                                            "place_id": "fake_place_999",
                                            "day_number": 1,
                                            "time_label": "Afternoon",
                                        },
                                        {
                                            "activity_id": "act_1_3",
                                            "title": "Excluded Stop",
                                            "description": "User excluded place",
                                            "place_id": "place_excluded",
                                            "day_number": 1,
                                            "time_label": "Evening",
                                        },
                                    ],
                                }
                            ],
                        })
                    )
                )
            ]
            return mock_resp
        raise ValueError(f"Unknown model {model}")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)
    svc._client = mock_client

    available_places = [
        PlaceRecommendation(
            place_id="place_valid",
            name="Valid Temple",
            category="temple",
            address="123 Kyoto Way",
            city="Kyoto",
            country="Japan",
        ),
        PlaceRecommendation(
            place_id="place_excluded",
            name="Excluded Place",
            category="sight",
            address="456 Kyoto Way",
            city="Kyoto",
            country="Japan",
        ),
    ]

    result = await svc.personalize_itinerary(
        current_itinerary=[],
        destination="Kyoto",
        preferences={},
        instructions="Visit valid places",
        selected_place_ids=["place_valid"],
        excluded_place_ids=["place_excluded"],
        available_places=available_places,
    )

    # 1. Groq failover succeeded
    assert result["model_used"] == "openai/gpt-oss-120b"
    assert result["failover_occurred"] is True

    # 2. Itinerary grounding validation
    itin_service = ItineraryService()
    validated_days, itin_warnings = itin_service.validate_personalized_itinerary(
        raw_days=result["days"],
        duration_days=1,
        start_date=None,
        available_places=available_places,
        selected_place_ids=["place_valid"],
        excluded_place_ids=["place_excluded"],
    )

    activities = validated_days[0].activities
    assert len(activities) == 3
    # Valid place preserved
    assert activities[0].place_id == "place_valid"
    # Fabricated place stripped to None
    assert activities[1].place_id is None
    # Excluded place stripped to None
    assert activities[2].place_id is None
    # Warning generated for excluded place
    assert any("excluded place" in w.lower() for w in itin_warnings)


@pytest.mark.asyncio
async def test_groq_failover_orchestrator_preserves_original_itinerary_when_both_models_fail():
    """Verify TravelAgentOrchestrator preserves base itinerary untouched when both models fail."""
    from app.schemas.planning import TravelPlanResponse, PersonalizePlanRequest
    from app.schemas.itinerary import DayItinerary, ItineraryActivity
    from app.services.orchestrator import TravelAgentOrchestrator
    from app.services.groq_service import GroqService
    from app.utils.exceptions import GroqServiceException

    original_activity = ItineraryActivity(
        activity_id="act_base_1",
        title="Original Kinkaku-ji",
        description="Golden pavilion view",
        place_id="place_kinkaku",
        day_number=1,
        time_label="Morning",
    )
    base_plan = TravelPlanResponse(
        trip_id="trip-failover-both-fail",
        destination="Kyoto",
        summary="Original untouched summary",
        preferences={"travel_pace": "balanced"},
        recommended_places=[],
        itinerary=[
            DayItinerary(
                day_number=1,
                theme="Original Peaceful Day",
                activities=[original_activity],
            )
        ],
        integration_status={"groq": "success"},
        warnings=[],
    )

    mock_groq = MagicMock(spec=GroqService)
    mock_groq.is_configured = True
    # Simulate both models failing, raising classified GroqServiceException
    mock_groq.personalize_itinerary = AsyncMock(
        side_effect=GroqServiceException(
            message="Primary and fallback models unavailable",
            category="server_error",
            user_friendly_message="AI service is temporarily unavailable. Your original itinerary has been preserved.",
            status_code=503,
        )
    )

    orchestrator = TravelAgentOrchestrator(groq_service=mock_groq)

    req = PersonalizePlanRequest(
        instructions="Make Day 1 more packed with sights",
        current_plan=base_plan,
    )

    result = await orchestrator.personalize_trip(req)

    # 1. Base itinerary completely intact
    assert len(result.itinerary) == 1
    assert result.itinerary[0].theme == "Original Peaceful Day"
    assert result.itinerary[0].activities[0].title == "Original Kinkaku-ji"
    assert result.itinerary[0].activities[0].place_id == "place_kinkaku"
    # 2. Base summary preserved
    assert result.summary == "Original untouched summary"
    # 3. Integration status marked as failed
    assert result.integration_status["groq"] == "failed"
    # 4. User-friendly preserved notice in warnings
    assert any("original itinerary has been preserved" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_token_allocation_for_short_and_longer_itineraries():
    """Verify max_tokens dynamically scales for reasoning + JSON across short and longer trip durations."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.schemas.itinerary import DayItinerary
    import json

    settings = Settings(groq_api_key="mock_key")
    svc = GroqService(settings)

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"summary": "Scale test", "days": [{"day_number": 1, "theme": "Day", "activities": []}]})
            )
        )
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    svc._client = mock_client

    # Test generate_itinerary: 1 day -> 2800 tokens
    await svc.generate_itinerary(destination="Kyoto", duration_days=1, preferences={}, taste_insights=None, places=[])
    kwargs_1day = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs_1day["max_tokens"] == 2800

    # Test generate_itinerary: 5 days -> 3750 tokens
    await svc.generate_itinerary(destination="Kyoto", duration_days=5, preferences={}, taste_insights=None, places=[])
    kwargs_5day = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs_5day["max_tokens"] == 3750

    # Test generate_itinerary: 7 days -> capped at 4096 tokens
    await svc.generate_itinerary(destination="Kyoto", duration_days=7, preferences={}, taste_insights=None, places=[])
    kwargs_7day = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs_7day["max_tokens"] == 4096

    # Test personalize_itinerary: 1 day -> 2600 tokens
    await svc.personalize_itinerary(current_itinerary=[DayItinerary(day_number=1, theme="Day", activities=[])], destination="Kyoto", preferences={}, instructions="Relax", selected_place_ids=[], excluded_place_ids=[], available_places=[])
    kwargs_pers_1day = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs_pers_1day["max_tokens"] == 2600

    # Test personalize_itinerary: 7 days -> capped at 4096 tokens
    itinerary_7days = [DayItinerary(day_number=i, theme=f"Day {i}", activities=[]) for i in range(1, 8)]
    await svc.personalize_itinerary(current_itinerary=itinerary_7days, destination="Kyoto", preferences={}, instructions="Relax", selected_place_ids=[], excluded_place_ids=[], available_places=[])
    kwargs_pers_7day = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs_pers_7day["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_groq_failover_json_validate_failed_triggers_fallback():
    """Verify HTTP 400 specifically with json_validate_failed triggers fallback model."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from openai import BadRequestError
    import httpx
    import json

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=0,
    )
    svc = GroqService(settings)
    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    models_called = []

    async def mock_call(**kwargs):
        model = kwargs.get("model")
        models_called.append(model)
        if model == "openai/gpt-oss-20b":
            resp = httpx.Response(400, request=req)
            body = {
                "error": {
                    "message": "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.",
                    "type": "invalid_request_error",
                    "code": "json_validate_failed",
                    "failed_generation": "",
                }
            }
            err = BadRequestError(
                message="Error code: 400 - Failed to validate JSON. code: json_validate_failed",
                response=resp,
                body=body,
            )
            err.code = "json_validate_failed"
            raise err
        elif model == "openai/gpt-oss-120b":
            mock_resp = MagicMock()
            mock_resp.choices = [
                MagicMock(
                    message=MagicMock(
                        content=json.dumps({
                            "summary": "Fallback success after json_validate_failed",
                            "budget_breakdown": {"estimated_total": 50.0, "currency": "USD"},
                            "days": [{"day_number": 1, "theme": "Day 1 Backup", "activities": []}],
                        })
                    )
                )
            ]
            return mock_resp
        raise ValueError(f"Unknown model: {model}")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_call)
    svc._client = mock_client

    result = await svc.generate_itinerary(
        destination="Kyoto",
        duration_days=2,
        preferences={},
        taste_insights=None,
        places=[],
    )

    assert result["model_used"] == "openai/gpt-oss-120b"
    assert result["failover_occurred"] is True
    assert models_called == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


@pytest.mark.asyncio
async def test_groq_failover_generic_http_400_does_not_trigger_fallback():
    """Verify that a generic HTTP 400 (e.g. invalid parameter syntax) does NOT trigger fallback."""
    from app.services.groq_service import GroqService
    from app.config import Settings
    from app.utils.exceptions import GroqServiceException
    from openai import BadRequestError
    import httpx

    settings = Settings(
        groq_api_key="mock_key",
        groq_primary_model="openai/gpt-oss-20b",
        groq_fallback_model="openai/gpt-oss-120b",
        groq_max_retries=0,
    )
    svc = GroqService(settings)
    req = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    call_count = 0

    async def mock_call(**kwargs):
        nonlocal call_count
        call_count += 1
        resp = httpx.Response(400, request=req)
        body = {
            "error": {
                "message": "Invalid temperature value: temperature must be between 0.0 and 2.0",
                "type": "invalid_request_error",
                "code": "invalid_parameter",
            }
        }
        raise BadRequestError(
            message="Error code: 400 - Invalid temperature value",
            response=resp,
            body=body,
        )

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_call)
    svc._client = mock_client

    with pytest.raises(GroqServiceException) as exc_info:
        await svc.generate_itinerary(
            destination="Kyoto",
            duration_days=2,
            preferences={},
            taste_insights=None,
            places=[],
        )

    assert exc_info.value.category == "client_error"
    assert call_count == 1  # Only primary was called; zero calls to fallback model




