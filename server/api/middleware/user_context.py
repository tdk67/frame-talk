"""
User Context Middleware: Anonymous Multi-User Identity & Pseudonymization
Extracts client identity from X-FrameTalk-User-Id, validates entropy,
and computes a privacy-preserving one-way pseudonym (user_hash) for storage and analytics.
"""

import re
import hashlib
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("frametalk.security.user_context")

# Server-side pepper for HMAC/hash one-way irreversibility
_SERVER_PEPPER = "frametalk_entropy_salt_2026_cinema"
_USER_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{8,64}$")

def compute_user_hash(raw_user_id: str) -> str:
    """Computes an irreversible 16-character hex pseudonym for ClickHouse & Job isolation."""
    if not raw_user_id:
        raw_user_id = str(uuid.uuid4())
    salted = f"{raw_user_id}:{_SERVER_PEPPER}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()[:16]

class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raw_id = request.headers.get("X-FrameTalk-User-Id", "").strip()

        # Validate format or fallback to ephemeral UUID
        if raw_id and _USER_ID_REGEX.match(raw_id):
            clean_id = raw_id
        else:
            clean_id = f"anon_{uuid.uuid4().hex[:12]}"

        # Compute deterministic one-way pseudonym
        user_hash = compute_user_hash(clean_id)

        # Inject into request state
        request.state.user_id = clean_id
        request.state.user_hash = user_hash

        response = await call_next(request)
        # Echo back sanitized user-id header so client is aware
        response.headers["X-FrameTalk-User-Hash"] = user_hash
        return response
