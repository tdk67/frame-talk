"""
Global Error Handling Middleware & Exception Handlers
Provides uniform, transparent JSON error responses with exact status codes.
Never hides errors, never silently dies.
"""

import logging
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from server.core.exceptions import FrameTalkException

logger = logging.getLogger("frametalk.api.error")

def setup_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FrameTalkException)
    async def frametalk_exception_handler(request: Request, exc: FrameTalkException):
        logger.error(f"[{request.method} {request.url.path}] Domain Exception ({exc.status_code}): {exc.message} | Detail: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "error_type": exc.__class__.__name__,
                "message": exc.message,
                "detail": exc.detail
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"[{request.method} {request.url.path}] Unhandled Exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "error_type": "InternalServerError",
                "message": "An unexpected server error occurred while processing your request.",
                "detail": "Please refer to the application logs for diagnostic information."
            }
        )
