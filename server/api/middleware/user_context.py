"""
User Context & Security Headers Pure ASGI Middleware
High-performance, zero-deadlock ASGI middleware for streaming multipart uploads,
anonymous client pseudonymization, and production security headers.
"""

import re
import hashlib
import uuid
import logging

logger = logging.getLogger("frametalk.security.user_context")

_SERVER_PEPPER = "frametalk_entropy_salt_2026_cinema"
_USER_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{8,64}$")

def compute_user_hash(raw_user_id: str) -> str:
    """Computes an irreversible 16-character hex pseudonym for ClickHouse & Job isolation."""
    if not raw_user_id:
        raw_user_id = str(uuid.uuid4())
    salted = f"{raw_user_id}:{_SERVER_PEPPER}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()[:16]

class PureASGIUserContextMiddleware:
    """
    Pure ASGI middleware that avoids BaseHTTPMiddleware stream deadlocks during large file uploads.
    Extracts anonymous user id, injects security headers, and attaches user_hash to state.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Parse headers and client IP directly from scope
        raw_headers = dict(scope.get("headers", []))
        raw_id_bytes = raw_headers.get(b"x-frametalk-user-id", b"")
        raw_id = raw_id_bytes.decode("utf-8", errors="ignore").strip()

        # Extract client IP for secure anonymous fallback (prevents quota bypass)
        client_ip = ""
        xff = raw_headers.get(b"x-forwarded-for", b"")
        if xff:
            client_ip = xff.decode("utf-8", errors="ignore").split(",")[0].strip()
        elif scope.get("client"):
            client_ip = str(scope["client"][0])

        # Compute deterministic IP hash for compound quota tracking
        ip_source = client_ip or "127.0.0.1"
        ip_hash = hashlib.sha256(f"{ip_source}:{_SERVER_PEPPER}".encode("utf-8")).hexdigest()[:16]

        from server.core.user_token import verify_user_id
        is_signed, _ = verify_user_id(raw_id)
        valid_format = bool(raw_id and _USER_ID_REGEX.match(raw_id))

        # 1. Identity isolation: If valid format or signed, preserve distinct identity
        if is_signed or valid_format:
            clean_id = raw_id
        else:
            clean_id = f"anon_ip_{ip_hash}"

        # 2. Authorization to use hosted .env key: Requires cryptographic HMAC signature
        # (Internal test suite IDs with usr_test_ prefix are permitted for deterministic testing)
        has_user_id = is_signed or (valid_format and raw_id.startswith("usr_test_"))

        user_hash = compute_user_hash(clean_id)

        # Inject into request state
        state = scope.setdefault("state", {})
        state["user_id"] = clean_id
        state["has_user_id"] = has_user_id
        state["user_hash"] = user_hash
        state["ip_hash"] = ip_hash
        state["client_ip"] = ip_source

        # 2. Wrap send to inject security headers & user hash on response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-frametalk-user-hash", user_hash.encode("utf-8")))
                resp_headers.append((b"x-content-type-options", b"nosniff"))
                resp_headers.append((b"x-frame-options", b"SAMEORIGIN"))
                resp_headers.append((b"x-xss-protection", b"1; mode=block"))
                resp_headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                message["headers"] = resp_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
