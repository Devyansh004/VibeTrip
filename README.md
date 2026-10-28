# ✈️ VibeTrip Agent

> **AI-Powered Travel Discovery & Taste-Based Itinerary Planning Web Application**  
> Built for the **Qloo Hackathon** using **Qloo Taste Intelligence**, **Groq AI Reasoning** (GPT-OSS-20B / GPT-OSS-120B), and **Geoapify Geospatial Places**.

---

## 🌟 1. Project Overview

**VibeTrip Agent** is an intelligent travel discovery web application that transcends conventional tourist booking engines. Instead of directing travelers toward cookie-cutter top attractions, VibeTrip interprets a user's personality, aesthetic preferences, travel mood, and cultural affinities to curate hidden gems and personalized day-by-day itineraries that truly match their personal vibe.

VibeTrip orchestrates:
1. **Preference Extraction**: Parses natural-language vibe prompts into structured aesthetic and atmospheric signals.
2. **Qloo Taste Intelligence**: Queries cultural affinity signals and taste correlations via `/v2/insights`.
3. **Geoapify Place Discovery**: Discovers verified real-world places, coordinates, and street addresses using proximity and circular geospatial filtering.
4. **Matching & Grounding**: Ranks and matches venues based on taste overlap and ensures no fake or hallucinated venues are presented.
5. **Groq AI Reasoning**: Synthesizes a cohesive, grounded day-by-day travel plan conforming strictly to Pydantic schemas using GPT-OSS models with automatic model failover.
6. **Interactive Personalization**: Allows users to dynamically modify their itinerary with natural-language instructions (e.g. adding or removing venues, pacing adjustments) while maintaining strict place grounding.
7. **Client-Side Trip Persistence**: Saves trips and personal collections locally in browser storage with instant retrieval.
8. **Editorial Visual Dashboard**: Delivers a responsive, magazine-style travel experience with clear data provenance, live integration status pills, and transparent degradation notices.

---

## 🛠 2. Technology Stack

### Frontend
- **HTML5**: Semantic, accessible markup.
- **Vanilla CSS3**: Custom design system utilizing CSS variables, responsive layouts, subtle shadows, and editorial serif typography.
- **Vanilla JavaScript**: Modular, framework-free client (`api.js`, `planner.js`, `results.js`, `saved-trips.js`, `app.js`) using standard Fetch API.
- **Hosting / Deployment**: Production frontend hosted on **Vercel** with dynamic API routing to the backend service.
- *Strictly avoids React, Vue, Next.js, or external heavy UI frameworks.*

### Backend
- **Python 3.10+ / 3.13 / 3.14**: Fully typed, asynchronous REST API.
- **FastAPI**: High-performance REST API framework with automatic OpenAPI/Swagger documentation (`/docs`).
- **Pydantic & Pydantic-Settings v2**: Strict request/response validation, schema contracts, and centralized configuration.
- **HTTPX**: Asynchronous, connection-pooled HTTP client with timeouts.
- **OpenAI Python SDK (`openai>=1.35.0`)**: Used with Groq's high-speed inference API endpoint.
- **Uvicorn**: High-performance ASGI production server.
- **Pytest & Pytest-Asyncio**: 74 automated unit and integration tests executing completely offline without requiring live API keys.
- **Hosting / Deployment**: Production backend deployed on **Render** (`https://vibetrip-0o8v.onrender.com`).

### External API Integrations
- **Qloo API**: Hackathon endpoint (`https://hackathon.api.qloo.com/v2/insights`) for taste intelligence, entity/tag lookups, and cultural affinities.
- **Groq Cloud API**: High-speed LLM inference via OpenAI-compatible endpoints (`https://api.groq.com/openai/v1`):
  - **Primary Model**: `openai/gpt-oss-20b` (fast, structured JSON reasoning and itinerary synthesis).
  - **Fallback Model**: `openai/gpt-oss-120b` (high-capacity failover model triggered automatically during rate limits, capacity constraints, or transient errors).
  - **Resilience Engine**: Exponential backoff with jitter, retry-after header parsing, quota exhaustion detection, and duration-adaptive token budgeting.
- **Geoapify API**: Geocoding (`/v1/geocode/search`) and Places (`/v2/places`) with longitude-first circular filtering (`circle:lon,lat,radius`).

---

## 📐 3. System Architecture & Workflow

```
   USER TRAVEL REQUEST
           ↓
   PREFERENCE EXTRACTION (Groq / Rule Fallback)
           ↓
   QLOO TASTE INTELLIGENCE (/v2/insights Cultural Signals)
           ↓
   GEOAPIFY PLACE DISCOVERY (Geocoding + Geospatial Search)
           ↓
   MATCHING & RANKING (Transparent Affinity Scoring)
           ↓
   GROQ ITINERARY SYNTHESIS (Primary: GPT-OSS-20B → Fallback: GPT-OSS-120B)
           ↓
   VALIDATION & ENRICHMENT (Pydantic Verification & Provenance)
           ↓
   PERSONALIZED TRAVEL DASHBOARD (Editorial UI + Live Integration Status)
           ↓
   BROWSER CLIENT PERSISTENCE (Saved Journeys & Cached Itinerary)
```

### Architectural Principles
1. **Decoupled API Scaffolding**: Each integration module (`qloo_service.py`, `groq_service.py`, `geoapify_service.py`) operates independently. Missing or invalid credentials trigger graceful degradation rather than application failure.
2. **Dual-Model Failover & Resiliency**: The Groq service attempts requests with `openai/gpt-oss-20b` and seamlessly fails over to `openai/gpt-oss-120b` upon model capacity issues, transient rate limits, or JSON validation errors. Non-retryable errors (e.g. invalid API keys or organization-wide quota exhaustion) fail immediately without repeated calls.
3. **Strict Grounding**: Groq is strictly constrained to reference verified place IDs discovered by Geoapify for specific venues. Hallucinated or invented place IDs are stripped and validated by the backend. General suggestions use `place_id: null`.
4. **Transparent Data Provenance**: Every place recommendation identifies its exact source (`geoapify` or `geoapify+qloo`). The UI displays live status pills showing whether Qloo, Geoapify, and Groq were **Active**, **Unconfigured**, or in **Fallback**.
5. **Smart Cache Management**: Itinerary caching incorporates configuration state (`qloo:groq:geoapify`). If API keys are added or services recover, stale degraded caches are automatically bypassed and cleared.
6. **Security & Privacy**: All secrets reside in backend `.env` variables and are never leaked to frontend assets, health check responses, or logs. All log output passes through regex sanitization.

---

## 📂 4. Project Directory Structure

```
VibeTrip/
│
├── frontend/
│   ├── index.html               # Main planning form & results dashboard
│   ├── trips.html               # Saved journeys & collection management page
│   ├── trip-details.html        # Detailed saved trip view & interactive edits
│   ├── css/
│   │   ├── styles.css           # Editorial typography & base tokens
│   │   ├── components.css       # Cards, chips, loading, modals, timeline
│   │   └── responsive.css       # Mobile & tablet breakpoints
│   ├── js/
│   │   ├── api.js               # Central backend API client & Render URL routing
│   │   ├── app.js               # Health check, modals, toasts, nav toggle
│   │   ├── planner.js           # Multi-stage loading & form logic
│   │   ├── results.js           # Place cards, timeline, status banner & budget renderer
│   │   └── saved-trips.js       # LocalStorage saved trip collection manager
│   └── assets/
│       └── hero.jpg             # Editorial travel visual asset
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI startup, CORS, routes & static mount
│   │   ├── config.py            # Pydantic Settings & credential validation
│   │   ├── dependencies.py      # Dependency injection providers
│   │   ├── requirements.txt     # App-level dependencies
│   │   ├── api/
│   │   │   ├── health.py        # GET /api/health (status & readiness)
│   │   │   ├── planner.py       # POST /api/plan & POST /api/plan/personalize
│   │   │   └── places.py        # POST /api/places/search (Geoapify discovery)
│   │   ├── schemas/
│   │   │   ├── common.py        # Health & standardized error schemas
│   │   │   ├── places.py        # PlaceRecommendation & search models
│   │   │   ├── itinerary.py     # ItineraryActivity & DayItinerary
│   │   │   └── planning.py      # TravelPlanRequest & TravelPlanResponse
│   │   ├── services/
│   │   │   ├── orchestrator.py  # Master workflow coordinator
│   │   │   ├── qloo_service.py  # Qloo API client & insights
│   │   │   ├── groq_service.py  # Groq AI reasoning client (GPT-OSS-20B / 120B)
│   │   │   ├── geoapify_service.py # Geospatial search & geocoding
│   │   │   ├── matching_service.py # Affinity scoring & ranking
│   │   │   ├── itinerary_service.py # Grounding & fallback builder
│   │   │   └── preference_service.py # Preference normalizer
│   │   └── utils/
│   │       ├── exceptions.py    # Custom domain exceptions
│   │       └── logging.py       # Sanitized structured logging
│   │
│   ├── tests/
│   │   ├── test_audit_and_repairs.py # Credential validation, cache & failover tests
│   │   ├── test_health.py       # Health check & secret masking tests
│   │   ├── test_schemas.py      # Pydantic validation & date logic tests
│   │   ├── test_planner.py      # Orchestrator & mocked planner tests
│   │   └── test_integrations.py # Service degradation, place grounding & Groq failover
│   │
│   ├── requirements.txt         # Production backend dependencies
│   ├── .env.example             # Backend environment variable template
│   └── README.md                # Backend service overview
│
├── pytest.ini                   # Pytest path & asyncio configuration
├── .gitignore                   # Ignore .env, caches, and virtual environments
├── .env.example                 # Root environment variable template
└── README.md                    # Master documentation
```

---

## 🚀 5. Prerequisites & Quickstart

### Prerequisites
- **Python 3.10+** (Tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)
- **Pip** (Python package installer)
- Any modern web browser (Chrome, Edge, Firefox, Safari)

### Installation
1. Clone or navigate to the repository:
   ```bash
   cd VibeTrip
   ```

2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

---

## 🔑 6. Environment Configuration

Copy `backend/.env.example` to `backend/.env` (or create `.env` in the project root):

```bash
cp backend/.env.example backend/.env
```

Configure your API credentials in `.env`:

```env
# Application
APP_ENV=development
APP_NAME=VibeTrip Agent
FRONTEND_ORIGIN=http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000

# Qloo (Hackathon Base URL)
QLOO_API_KEY=your_qloo_hackathon_key_here
QLOO_BASE_URL=https://hackathon.api.qloo.com

# Groq (Primary: GPT-OSS-20B, Fallback: GPT-OSS-120B)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_PRIMARY_MODEL=openai/gpt-oss-20b
GROQ_FALLBACK_MODEL=openai/gpt-oss-120b
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_TIMEOUT_SECONDS=60
GROQ_MAX_RETRIES=2
GROQ_MAX_RETRY_WAIT_SECONDS=5.0

# Geoapify
GEOAPIFY_API_KEY=your_geoapify_key_here
GEOAPIFY_BASE_URL=https://api.geoapify.com
```

### Autonomous Degradation Behavior
If any API credentials are omitted or placeholders are detected, VibeTrip runs in **autonomous degradation mode**:
- If **Qloo** is unconfigured, geospatial venues will be ranked based on direct keyword matching without taste affinities.
- If **Geoapify** is unconfigured, neighborhood discovery activities will be suggested without fake venue pins.
- If **Groq** is unconfigured, a deterministic rule-based itinerary synthesizer will assemble the plan.
- The UI honestly displays which services were active vs. in fallback via the **Service Integrations Provenance Banner**.
- Personal collections and itineraries are persisted in browser local storage with zero cloud credentials required.

---

## 🏃 7. Running the Application

### Option A: Unified Full-Stack Server (Recommended for Local Dev)
FastAPI serves both the REST API and the static frontend simultaneously:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

- **Frontend App**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Saved Trips**: Open [http://127.0.0.1:8000/trips.html](http://127.0.0.1:8000/trips.html)
- **Swagger API Docs**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Endpoint**: Open [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Option B: Separate Frontend Dev Server
If running frontend with VS Code Live Server (port 5500) or another dev server:
1. Start the backend:
   ```bash
   python -m uvicorn app.main:app --app-dir backend --port 8000
   ```
2. Open `frontend/index.html` via Live Server. `frontend/js/api.js` automatically connects to the backend and CORS is preconfigured.

### 🌐 Cloud Deployment Architecture
- **Frontend**: Hosted on **Vercel**.
- **Backend API**: Hosted on **Render** at [https://vibetrip-0o8v.onrender.com](https://vibetrip-0o8v.onrender.com).
- In `frontend/js/api.js`, non-port-8000 clients automatically route API calls to the deployed Render backend:
  ```javascript
  const API_BASE = (() => {
    const isDirectFastAPI = window.location.port === '8000';
    if (isDirectFastAPI && window.location.origin && window.location.origin !== 'null') {
      return window.location.origin;
    }
    return 'https://vibetrip-0o8v.onrender.com';
  })();
  ```

---

## 🧪 8. Automated Testing

Run the automated test suite using `pytest`:

```bash
python -m pytest backend/tests -v
```

All **74 automated unit and integration tests** pass completely offline without requiring active external API keys:
- **`test_audit_and_repairs.py`**: Credential validation, placeholder rejection, settings cache clearing, places search coordinates vs location fallback, health contract, stale warning cleanup, and cache bypass.
- **`test_integrations.py`**: Qloo parameter formatting & graceful degradation, Geoapify geocoding & radius search, Groq service dual-model failover (`gpt-oss-20b` → `gpt-oss-120b`), transient rate-limit handling, daily token quota detection, place ID grounding, and token budgeting.
- **`test_planner.py`**: End-to-end trip planning workflow, mocked integrations, initial planning optimization, and natural language personalization (`/api/plan/personalize`).
- **`test_schemas.py`**: Pydantic request/response validation, ISO date calculation, budget parsing, and duplicate place deduplication.
- **`test_health.py`**: Health endpoint readiness, service configuration flags, and secret masking tests.

---

## 🛡 9. Security & Data Integrity

1. **Credential Validation & Sanitization**: The settings engine detects dummy placeholders (e.g. `your_groq_api_key_here`) and marks services unconfigured rather than making failing remote calls.
2. **Secret Redaction**: Structured logging passes all messages through a regex sanitizer that strips any `key`, `token`, `secret`, or `password` occurrences.
3. **No Frontend Secrets**: Browser JavaScript only communicates with `/api/...` endpoints and never receives external API credentials.
4. **Data Provenance**: Every place recommendation identifies its exact data source (`geoapify` or `geoapify+qloo`).
5. **XSS Protection**: All user or API content rendered in the DOM passes through HTML entity encoding.

---

## 🏆 10. Definition of Done Checklist

- [x] Polished, responsive editorial travel-tech frontend deployed on Vercel.
- [x] High-performance FastAPI backend deployed on Render with Swagger docs.
- [x] Multi-stage planning form with multi-select vibe chips, duration, budget, and natural-language prompt.
- [x] Independent Qloo, Groq (GPT-OSS-20B / 120B), and Geoapify service modules.
- [x] Groq dual-model failover engine with exponential backoff and token budgeting.
- [x] Strict place grounding verifying that all itinerary venues link to real Geoapify place IDs.
- [x] Live execution provenance banner displaying honest integration statuses.
- [x] Interactive itinerary personalization (`/api/plan/personalize`) with preserved grounding.
- [x] Client-side saved journeys and cached itinerary persistence in LocalStorage.
- [x] 74 automated unit and integration tests passing offline.
- [x] Complete setup, API, environment, and deployment documentation.
