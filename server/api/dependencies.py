"""
FastAPI Dependencies for Header Authentication and Common Injections
"""

from typing import Optional
from fastapi import Header

def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", description="Gemini or OpenRouter API key"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token header")
) -> Optional[str]:
    """
    Extracts API key exclusively from HTTP headers:
    1. Priority: 'X-API-Key' header
    2. Fallback: 'Authorization: Bearer <key>' header
    """
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()

    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()

    return None
