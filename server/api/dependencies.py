"""
FastAPI Dependencies for Header Authentication and Common Injections
"""

from typing import Optional
from fastapi import Header, Request, HTTPException

def get_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", description="Google Gemini API key (Required if no X-FrameTalk-User-Id provided)"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token header")
) -> Optional[str]:
    """
    Extracts API key exclusively from HTTP headers:
    1. Priority: 'X-API-Key' header (BYOK)
    2. Fallback: 'Authorization: Bearer <key>' header (BYOK)
    3. If no custom BYOK key is provided:
       - Requires 'X-FrameTalk-User-Id' header to access the server's hosted demo key from .env.
       - If no User ID is passed, using the .env API key is STRICTLY BLOCKED; only BYOK is allowed.
    """
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()

    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()

    # If no custom key, check if client provided a valid User ID
    has_user_id = getattr(request.state, "has_user_id", False)
    if not has_user_id:
        raise HTTPException(
            status_code=401,
            detail="Access Denied: Missing User ID. The hosted server demo key cannot be used without an 'X-FrameTalk-User-Id' header. Anonymous requests must provide their own Gemini API key (BYOK) via 'X-API-Key'."
        )

    return None
