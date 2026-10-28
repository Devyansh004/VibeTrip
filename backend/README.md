# VibeTrip Agent - Backend Service

FastAPI-powered agentic backend orchestrating **Qloo Taste Intelligence**, **Groq AI Reasoning** (GPT-OSS-20B / GPT-OSS-120B), and **Geoapify Geospatial Places**.

## Architecture

- `app/api/`: REST API route endpoints:
  - `health.py`: `GET /api/health` — Readiness status and integration health without secret leakage.
  - `planner.py`: `POST /api/plan` — End-to-end itinerary generation pipeline; `POST /api/plan/personalize` — Interactive natural-language itinerary modifications.
  - `places.py`: `POST /api/places/search` — Direct Geoapify place discovery and geocoding.
- `app/services/`: Independent integration and domain services:
  - `qloo_service.py`: Qloo Taste Intelligence API integration (`/v2/insights`).
  - `groq_service.py`: Groq AI client with dual-model failover (`openai/gpt-oss-20b` primary → `openai/gpt-oss-120b` fallback), retry logic with exponential backoff, retry-after header parsing, quota detection, and duration-adaptive token budgeting.
  - `geoapify_service.py`: Geospatial place discovery (`/v2/places`) and geocoding (`/v1/geocode/search`).
  - `matching_service.py`: Cultural affinity scoring and place-vibe ranking.
  - `orchestrator.py`: Multi-stage workflow orchestrator with cache state management.
  - `itinerary_service.py`: Strict place ID grounding enforcement and deterministic fallback generator.
  - `preference_service.py`: Normalization of vibe tags, duration, and budget.
- `app/schemas/`: Pydantic models for request validation and standardized responses (`planning.py`, `places.py`, `itinerary.py`, `common.py`).
- `app/config.py`: Central Pydantic Settings reading environment variables with placeholder detection (`is_valid_credential`).
- `app/utils/`: Custom domain exceptions (`exceptions.py`) and regex secret sanitizing logger (`logging.py`).
- `tests/`: Automated unit and integration test suite (74 tests passing completely offline).

## Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Key environment variables:
- `GROQ_API_KEY`: Groq Cloud API key
- `GROQ_MODEL`: `openai/gpt-oss-20b` (Primary)
- `GROQ_FALLBACK_MODEL`: `openai/gpt-oss-120b` (Failover)
- `QLOO_API_KEY`: Qloo Hackathon API key
- `GEOAPIFY_API_KEY`: Geoapify Places API key

## Running Tests

All 74 unit and integration tests run offline without active API keys:

```bash
python -m pytest backend/tests -v
```

## Running Dev Server

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Deployment

The backend service is containerized / configured for deployment on **Render** (`https://vibetrip-0o8v.onrender.com`), serving requests from both local development origins and the Vercel-hosted frontend.
