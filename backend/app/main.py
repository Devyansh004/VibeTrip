"""VibeTrip Agent FastAPI Application Entry Point."""

from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.utils.logging import logger
from app.utils.exceptions import VibeTripException
from app.api.health import router as health_router
from app.api.planner import router as planner_router
from app.api.places import router as places_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agentic travel discovery and itinerary planning powered by Qloo Taste Intelligence, Groq GPT-OSS-20B, and Geoapify.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
origins = settings.cors_origins
logger.info(f"Configuring CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Domain Exception Handler
@app.exception_handler(VibeTripException)
async def vibetrip_exception_handler(request: Request, exc: VibeTripException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "details": exc.details,
            }
        },
    )

# Include API Routers
app.include_router(health_router)
app.include_router(planner_router)
app.include_router(places_router)

# Mount Frontend Static Assets
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    logger.info(f"Mounting frontend directory: {frontend_dir}")
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}")
