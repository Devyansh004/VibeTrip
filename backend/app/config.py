"""Central application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine absolute paths for deterministic .env loading regardless of working directory
_APP_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _APP_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Discover potential .env locations in order of priority (later entries take precedence)
_ENV_CANDIDATES = [
    _PROJECT_ROOT / ".env",
    _BACKEND_DIR / ".env",
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
]
if os.environ.get("ENV_FILE"):
    _ENV_CANDIDATES.append(Path(os.environ["ENV_FILE"]).resolve())

# Filter to unique paths as absolute Path objects
_ENV_FILES: tuple[Path, ...] = tuple(
    dict.fromkeys([p.resolve() for p in _ENV_CANDIDATES if p.is_file() or p in (_PROJECT_ROOT / ".env", _BACKEND_DIR / ".env")])
)


def is_valid_credential(key: Optional[str]) -> bool:
    """Validate whether an API key is non-empty and not a placeholder."""
    if not key or not isinstance(key, str):
        return False
    val = key.strip()
    if not val:
        return False
    val_lower = val.lower()
    placeholders = {
        "your_qloo_hackathon_key_here",
        "your_geoapify_key_here",
        "your_gemini_api_key_here",
        "your_groq_api_key_here",
        "your_api_key_here",
        "your_api_key",
        "placeholder",
        "api_key_here",
        "insert_key_here",
        "todo",
        "xxx",
        "none",
        "null",
    }
    if val_lower in placeholders:
        return False
    if val_lower.startswith("your_") or val_lower.startswith("<your") or val_lower.endswith("_here"):
        return False
    if len(val) < 8:
        return False
    return True


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
        env_file=_ENV_FILES,
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
        """Check if Qloo credentials are provided and valid."""
        return is_valid_credential(self.qloo_api_key)

    @property
    def is_groq_configured(self) -> bool:
        """Check if Groq credentials are provided and valid."""
        return is_valid_credential(self.groq_api_key)

    @property
    def is_geoapify_configured(self) -> bool:
        """Check if Geoapify credentials are provided and valid."""
        return is_valid_credential(self.geoapify_api_key)

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


def clear_settings_cache() -> None:
    """Clear the cached settings instance (useful in tests and reloads)."""
    get_settings.cache_clear()

