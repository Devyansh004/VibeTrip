"""Custom application exceptions for VibeTrip Agent."""


class VibeTripException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(VibeTripException):
    """Raised when an integration is missing required configuration."""
    def __init__(self, message: str, integration: str):
        super().__init__(message, status_code=503, details={"integration": integration})


class IntegrationUnavailableError(VibeTripException):
    """Raised when an external service is unavailable or returned an error."""
    def __init__(self, integration: str, reason: str, status_code: int = 502):
        super().__init__(f"{integration} service unavailable: {reason}", status_code=status_code, details={"integration": integration, "reason": reason})


class ExternalAPIError(VibeTripException):
    """Raised when an external API call fails with HTTP error."""
    def __init__(self, integration: str, status_code: int, message: str):
        super().__init__(f"{integration} API returned status {status_code}: {message}", status_code=502, details={"integration": integration, "upstream_status": status_code})


class TripNotFoundError(VibeTripException):
    """Raised when a requested trip cannot be found."""
    def __init__(self, trip_id: str):
        super().__init__(f"Trip '{trip_id}' not found", status_code=404, details={"trip_id": trip_id})


class UnauthorizedError(VibeTripException):
    """Raised when user authorization fails or ownership check fails."""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(VibeTripException):
    """Raised when user does not have permission to access a specific resource."""
    def __init__(self, message: str = "Access to resource is forbidden"):
        super().__init__(message, status_code=403)


class GroqServiceException(VibeTripException):
    """Raised when Groq API encounters a classified error."""
    def __init__(
        self,
        message: str,
        category: str,
        user_friendly_message: str,
        status_code: int = 502,
        is_retryable: bool = False,
        retry_after_seconds: float | None = None,
        is_org_quota: bool = False,
        is_json_validate_failed: bool = False,
        details: dict | None = None,
    ):
        super().__init__(message, status_code=status_code, details=details or {})
        self.category = category
        self.user_friendly_message = user_friendly_message
        self.is_retryable = is_retryable
        self.retry_after_seconds = retry_after_seconds
        self.is_org_quota = is_org_quota
        self.is_json_validate_failed = is_json_validate_failed

