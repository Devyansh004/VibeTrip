# VibeTrip Agent - Backend Service

FastAPI-powered agentic backend orchestrating Qloo Taste Intelligence, Groq Reasoning, and Geoapify Places.

## Architecture

- `app/api/`: REST API route endpoints (`health.py`, `planner.py`, `places.py`).
- `app/services/`: Independent integration services (`qloo_service.py`, `groq_service.py`, `geoapify_service.py`, `matching_service.py`, `orchestrator.py`).
- `app/schemas/`: Pydantic models for request validation and standardized responses (`planning.py`, `places.py`, `itinerary.py`, `common.py`).
- `app/config.py`: Central Pydantic Settings reading environment variables.
- `tests/`: Automated unit and integration test suite.

## Running Tests

```bash
python -m pytest backend/tests -v
```

## Running Dev Server

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
