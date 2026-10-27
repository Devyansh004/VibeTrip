"""Central application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Application
    app_env: str = "development"
    app_name: str = "VibeTrip Agent"
    app_version: str = "1.0.0"
    frontend_origin: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000"

    # Qloo
    qloo_api_key: str | None = None
    qloo_base_url: str = "https://hackathon.api.qloo.com"

    # Groq (Primary: GPT-OSS-20B, Fallback: GPT-OSS-120B)
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_primary_model: str = "openai/gpt-oss-20b"
    groq_fallback_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: int = 60
    groq_max_retries: int = 2
    groq_max_retry_wait_seconds: float = 5.0

    # Geoapify
    geoapify_api_key: str | None = None
    geoapify_base_url: str = "https://api.geoapify.com"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated frontend origins for CORS configuration."""
        if not self.frontend_origin:
            return ["*"]
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def is_qloo_configured(self) -> bool:
        """Check if Qloo credentials are provided."""
        return bool(self.qloo_api_key and self.qloo_api_key.strip())

    @property
    def is_groq_configured(self) -> bool:
        """Check if Groq credentials are provided."""
        return bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def is_geoapify_configured(self) -> bool:
        """Check if Geoapify credentials are provided."""
        return bool(self.geoapify_api_key and self.geoapify_api_key.strip())

    def get_integration_statuses(self) -> Dict[str, str]:
        """Return human-readable integration readiness statuses without exposing secrets."""
        groq_status = "configured" if self.is_groq_configured else "not_configured"
        return {
            "qloo": "configured" if self.is_qloo_configured else "not_configured",
            "groq": groq_status,
            "geoapify": "configured" if self.is_geoapify_configured else "not_configured",
        }


@lru_cache()
def get_settings() -> Settings:
    """Cached factory function for application settings."""
    return Settings()
