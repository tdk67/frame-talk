"""
Domain Exceptions for Frame Talk
Categorized for transparent error reporting without silent fallbacks.
"""

class FrameTalkException(Exception):
    """Base exception for all Frame Talk domain errors."""
    def __init__(self, message: str, status_code: int = 500, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail

class QuotaExceededException(FrameTalkException):
    """Raised when LLM API returns 429 Resource Exhausted / Out of Credits."""
    def __init__(self, message: str = "Gemini API rate limit or credit quota reached.", detail: str = ""):
        super().__init__(
            message=message,
            status_code=429,
            detail=detail or "Your Gemini API key has exceeded its quota or run out of credits. Please check your Google Cloud / AI Studio billing."
        )

class InvalidCredentialsException(FrameTalkException):
    """Raised when LLM API returns 401 Unauthorized or 403 Forbidden."""
    def __init__(self, message: str = "Invalid API Key or unauthorized access.", detail: str = ""):
        super().__init__(
            message=message,
            status_code=401,
            detail=detail or "API key authentication failed. Please verify your Gemini API key in the settings modal."
        )

class InvalidInputException(FrameTalkException):
    """Raised when client parameters or uploaded media are malformed (400 Bad Request)."""
    def __init__(self, message: str, detail: str = ""):
        super().__init__(
            message=message,
            status_code=400,
            detail=detail or "The request payload or media format is invalid."
        )

class ResourceNotFoundException(FrameTalkException):
    """Raised when requested files or entities do not exist (404 Not Found)."""
    def __init__(self, message: str, detail: str = ""):
        super().__init__(
            message=message,
            status_code=404,
            detail=detail or "The requested asset was not found on the server."
        )

class VideoProcessingException(FrameTalkException):
    """Raised when video file processing or token ingestion fails."""
    def __init__(self, message: str, detail: str = ""):
        super().__init__(
            message=message,
            status_code=422,
            detail=detail or "Video processing or frame analysis encountered a fatal error."
        )

class ServiceUnavailableException(FrameTalkException):
    """Raised when an external service is overloaded or down (503)."""
    def __init__(self, message: str = "Service temporarily unavailable.", detail: str = ""):
        super().__init__(
            message=message,
            status_code=503,
            detail=detail or "Upstream model server is overloaded. Please try again shortly."
        )
