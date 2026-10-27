# ✈️ VibeTrip Agent

> **AI-Powered Travel Discovery & Taste-Based Itinerary Planning Web Application**  
> Built for the **Qloo Hackathon** using **Qloo Taste Intelligence**, **Google Gemini Reasoning**, and **Geoapify Geospatial Places**.

---

## 🌟 1. Project Overview

**VibeTrip Agent** is an intelligent travel discovery web application that transcends conventional tourist booking engines. Instead of directing travelers toward cookie-cutter top attractions, VibeTrip interprets a user's personality, aesthetic preferences, travel mood, and cultural affinities to curate hidden gems and personalized day-by-day itineraries that truly match their personal vibe.

### Real-World Example
> *"I'm visiting Jaipur for 2 days. I love indie music, artistic cafes, vintage architecture, street photography, and peaceful places. My budget is ₹5,000."*

VibeTrip orchestrates:
1. **Preference Extraction**: Parses natural-language vibe prompts into structured aesthetic and atmospheric signals.
2. **Qloo Taste Intelligence**: Queries cultural affinity signals and taste correlations via `/v2/insights`.
3. **Geoapify Place Discovery**: Discovers verified real-world places, coordinates, and street addresses using proximity and circular geospatial filtering.
4. **Matching & Grounding**: Ranks and matches venues based on taste overlap and ensures no fake or hallucinated venues are presented.
5. **Gemini Reasoning**: Synthesizes a cohesive, grounded day-by-day travel plan conforming strictly to Pydantic schemas.
6. **Client-Side Trip Persistence**: Saves trips and personal collections locally in browser storage with instant retrieval.
7. **Editorial Visual Dashboard**: Delivers a responsive, magazine-style travel experience with clear data provenance and transparent degradation notes.

---

## 🛠 2. Technology Stack

### Frontend
- **HTML5**: Semantic, accessible markup.
- **Vanilla CSS3**: Custom design system utilizing CSS variables, responsive layouts, subtle shadows, and editorial serif typography.
- **Vanilla JavaScript**: Modular, framework-free client (`api.js`, `planner.js`, `results.js`, `saved-trips.js`, `app.js`) using standard Fetch API.
- *Strictly avoids React, Vue, Next.js, or external heavy UI frameworks.*

### Backend
- **Python 3.10+ / 3.14**: Fully typed, asynchronous REST API.
- **FastAPI**: REST API with interactive Swagger documentation (`/docs`).
- **Pydantic & Pydantic-Settings**: Strict request/response validation and centralized configuration.
- **HTTPX**: Asynchronous, connection-pooled HTTP client with timeouts.
- **Uvicorn**: High-performance ASGI server.
- **Pytest & Pytest-Asyncio**: Comprehensive test suite without requiring active API keys.

### External API Integrations
- **Qloo API**: Hackathon endpoint (`https://hackathon.api.qloo.com/v2/insights`) for taste intelligence, entity/tag lookups, and cultural affinities.
- **Google Gemini API**: Configurable model (`gemini-2.5-flash`) via official `google-genai` SDK for preference extraction and grounded itinerary synthesis.
- **Geoapify API**: Geocoding (`/v1/geocode/search`) and Places (`/v2/places`) with longitude-first circular filtering (`circle:lon,lat,radius`).

---

## 📐 3. System Architecture & Workflow

```
   USER TRAVEL REQUEST
           ↓
   PREFERENCE EXTRACTION (Gemini / Rule Fallback)
           ↓
   QLOO TASTE INTELLIGENCE (/v2/insights Cultural Signals)
           ↓
   GEOAPIFY PLACE DISCOVERY (Geocoding + Geospatial Search)
           ↓
   MATCHING & RANKING (Transparent Affinity Scoring)
           ↓
   GEMINI ITINERARY SYNTHESIS (Grounded Venue Activities)
           ↓
   VALIDATION & ENRICHMENT (Pydantic Verification & Provenance)
           ↓
   PERSONALIZED TRAVEL DASHBOARD (Editorial UI + Map Links)
           ↓
   BROWSER CLIENT PERSISTENCE (Saved Journeys & Cached Itinerary)
```

### Architectural Principles
1. **Decoupled API Scaffolding**: Each integration module (`qloo_service.py`, `gemini_service.py`, `geoapify_service.py`) operates independently. Missing credentials trigger graceful degradation rather than application failure.
2. **Strict Grounding**: Gemini is strictly constrained to reference verified place IDs discovered by Geoapify for specific venues. General suggestions have `place_id: null`.
3. **No Hallucinated Data**: Venue details, coordinates, ratings, and opening hours are never invented. When an integration is unconfigured, an honest status notice is displayed.
4. **Security & Privacy**: All secrets reside in backend `.env` variables and are never leaked to frontend assets or health responses.

---

## 📂 4. Project Directory Structure

```
VibeTripQloo/
│
├── frontend/
│   ├── index.html               # Main planning form & results dashboard
│   ├── trips.html               # Saved journeys & management page
│   ├── trip-details.html        # Detailed saved trip view
│   ├── css/
│   │   ├── styles.css           # Editorial typography & base tokens
│   │   ├── components.css       # Cards, chips, loading, modals, timeline
│   │   └── responsive.css       # Mobile & tablet breakpoints
│   ├── js/
│   │   ├── api.js               # Central backend API client
│   │   ├── app.js               # Health check, modals, toasts, nav toggle
│   │   ├── planner.js           # Multi-stage loading & form logic
│   │   ├── results.js           # Place cards, timeline, and budget renderer
│   │   └── saved-trips.js       # Cloud & guest trip storage manager
│   └── assets/
│       └── hero.jpg             # Editorial travel visual asset
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI startup, CORS, routes & static mount
│   │   ├── config.py            # Pydantic Settings configuration
│   │   ├── dependencies.py      # Dependency injection providers
│   │   ├── api/
│   │   │   ├── health.py        # GET /api/health (status & readiness)
│   │   │   ├── planner.py       # POST /api/plan & /api/plan/personalize
│   │   │   └── places.py        # POST /api/places/search (Geoapify discovery)
│   │   ├── schemas/
│   │   │   ├── common.py        # Health & standardized error schemas
│   │   │   ├── places.py        # PlaceRecommendation & search models
│   │   │   ├── itinerary.py     # ItineraryActivity & DayItinerary
│   │   │   └── planning.py      # TravelPlanRequest & TravelPlanResponse
│   │   ├── services/
│   │   │   ├── orchestrator.py  # Master workflow coordinator
│   │   │   ├── qloo_service.py  # Qloo API client & insights
│   │   │   ├── gemini_service.py# Google Gen AI reasoning client
│   │   │   ├── geoapify_service.py # Geospatial search & geocoding
│   │   │   ├── matching_service.py # Affinity scoring & ranking
│   │   │   ├── itinerary_service.py # Grounding & fallback builder
│   │   │   └── preference_service.py # Preference normalizer
│   │   └── utils/
│   │       ├── exceptions.py    # Custom domain exceptions
│   │       └── logging.py       # Sanitized structured logging
│   │
│   ├── tests/
│   │   ├── test_health.py       # Health check & secret masking tests
│   │   ├── test_schemas.py      # Pydantic validation & date logic tests
│   │   ├── test_planner.py      # Orchestrator & mocked planner tests
│   │   └── test_integrations.py # Service degradation & place grounding tests
│   │
│   ├── requirements.txt         # Production dependencies
│   ├── .env.example             # Environment variable template
│   └── README.md
│
├── pytest.ini                   # Pytest path & asyncio configuration
├── .gitignore                   # Ignore .env, caches, and virtual environments
└── README.md                    # Master documentation
```

---

## 🚀 5. Prerequisites & Quickstart

### Prerequisites
- **Python 3.10+** (Tested on Python 3.10, 3.11, 3.12, 3.14)
- **Pip** (Package manager)
- Any modern web browser (Chrome, Edge, Firefox, Safari)

### Installation
1. Clone or navigate to the repository:
   ```bash
   cd d:\Projects\VibeTripQloo
   ```

2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

---

## 🔑 6. Environment Configuration

Copy `backend/.env.example` to `backend/.env` (or root `.env`):

```bash
cp backend/.env.example backend/.env
```

Edit `.env` with your API credentials:

```env
# Application
APP_ENV=development
APP_NAME=VibeTrip Agent
FRONTEND_ORIGIN=http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000

# Qloo (Hackathon Base URL)
QLOO_API_KEY=your_qloo_hackathon_key_here
QLOO_BASE_URL=https://hackathon.api.qloo.com

# Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Geoapify
GEOAPIFY_API_KEY=your_geoapify_key_here
GEOAPIFY_BASE_URL=https://api.geoapify.com

```

> **Note on Missing Credentials**:
> If any API credentials are omitted, VibeTrip will gracefully run in **autonomous degradation mode**:
> - If **Qloo** is unconfigured, geospatial venues will be ranked based on direct keyword matching without taste affinities.
> - If **Geoapify** is unconfigured, neighborhood discovery activities will be suggested without fake venue pins.
> - If **Gemini / Groq** is unconfigured, a deterministic rule-based itinerary synthesizer will assemble the plan.
> - Personal collections and itineraries are persisted in browser local storage with zero cloud credentials required.

---

## 🏃 7. Running the Application

### Option A: Unified Full-Stack Server (Recommended)
FastAPI serves both the REST API and the static frontend simultaneously:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

- **Frontend App**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Saved Trips**: Open [http://127.0.0.1:8000/trips.html](http://127.0.0.1:8000/trips.html)
- **Swagger API Docs**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Endpoint**: Open [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Option B: Separate Frontend Dev Server
If using VS Code Live Server on port 5500:
1. Start the backend:
   ```bash
   python -m uvicorn app.main:app --app-dir backend --port 8000
   ```
2. Serve the `frontend/` directory with Live Server at `http://127.0.0.1:5500`. CORS is preconfigured to accept requests from this origin.

---

## 🧪 8. Automated Testing

Run the automated test suite using `pytest`:

```bash
python -m pytest backend/tests -v
```

All automated unit and integration tests run **offline without requiring active API keys**:
- Request validation, date ranges, duration calculation, and budget validation.
- Missing credentials and graceful service degradation.
- Grounding verification (ensuring hallucinated place IDs are stripped).
- Mocked multi-service orchestrator execution.
- Security checks (verifying that secret keys are never leaked).

---

## 🛡 9. Security & Data Integrity

1. **Secret Redaction**: Structured logging passes all messages through a regex sanitizer that strips any `key`, `token`, `secret`, or `password` occurrences.
2. **No Frontend Secrets**: Browser JavaScript only communicates with `/api/...` endpoints and never receives external API credentials.
3. **Data Provenance**: Every place recommendation identifies its exact data source (`geoapify` or `geoapify+qloo`).
4. **XSS Protection**: All untrusted user or API content rendered in the DOM passes through HTML entity encoding.

---

## 🏆 10. Definition of Done Checklist

- [x] Polished, responsive editorial travel-tech frontend.
- [x] Dynamic planning form with multi-select chips, quick destination buttons, and vibe prompt.
- [x] Multi-stage loading progress reflecting real orchestration steps.
- [x] Day-by-day itinerary timeline with time brackets and budget breakdown.
- [x] Modular FastAPI backend with Pydantic validation.
- [x] Independent Qloo, Gemini, and Geoapify service modules.
- [x] Transparent handling of missing credentials and degradation notices.
- [x] Client-side saved journeys and cached itinerary persistence.
- [x] 60 automated unit and integration tests passing.
- [x] Complete setup, API, and troubleshooting documentation.
