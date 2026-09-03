"""
Discovery & SEO Router for Frame Talk.
Reads and serves dynamic search crawler specifications, sitemaps, and LLM manifests
directly from the repository's `public/` asset directory.
Adheres strictly to the hexagonal architecture with zero hardcoded file content in Python.
"""

from pathlib import Path
from fastapi import APIRouter, Response, Request
from fastapi.responses import PlainTextResponse
from server.core.config import config

router = APIRouter(tags=["0. Discovery & SEO"])

DEFAULT_HOST = "https://frame-talk.taskmind-ai.com"

def _read_public_file(filename: str) -> str:
    """Reads a file from the configured public directory."""
    file_path = config.public_dir / filename
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return ""

def _interpolate_domain(content: str) -> str:
    """Substitutes the configured domain URL into template content."""
    app_url = config.app_url.rstrip("/")
    if app_url != DEFAULT_HOST:
        return content.replace(DEFAULT_HOST, app_url)
    return content

@router.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt():
    """Serves robots.txt directly from public/robots.txt."""
    content = _read_public_file("robots.txt")
    if not content:
        return PlainTextResponse("User-agent: *\nAllow: /\n", status_code=200)
    return PlainTextResponse(_interpolate_domain(content), media_type="text/plain")

@router.get("/sitemap.xml")
def get_sitemap_xml():
    """Serves sitemap.xml directly from public/sitemap.xml."""
    content = _read_public_file("sitemap.xml")
    if not content:
        return Response(content="<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>", media_type="application/xml")
    return Response(content=_interpolate_domain(content), media_type="application/xml")

@router.get("/llms.txt", response_class=PlainTextResponse)
def get_llms_txt():
    """Serves llms.txt directly from public/llms.txt."""
    content = _read_public_file("llms.txt")
    if not content:
        return PlainTextResponse("# Frame Talk\n\n> Multimodal Studio Engine\n", status_code=200)
    return PlainTextResponse(_interpolate_domain(content), media_type="text/plain")

@router.get("/llms-full.txt", response_class=PlainTextResponse)
def get_llms_full_txt():
    """Serves llms-full.txt directly from public/llms-full.txt."""
    content = _read_public_file("llms-full.txt")
    if not content:
        return PlainTextResponse("# Frame Talk Full Architecture Guide\n", status_code=200)
    return PlainTextResponse(_interpolate_domain(content), media_type="text/plain")

@router.get("/api/auth/session")
def get_or_create_session(request: Request):
    """
    Returns a cryptographically signed session User ID (usr_<timestamp>_<nonce>.<hmac_sig>).
    Clients attach this in X-FrameTalk-User-Id to authenticate their demo session.
    """
    from server.core.user_token import sign_user_id, verify_user_id
    existing_id = request.headers.get("x-frametalk-user-id")
    if existing_id:
        is_valid, _ = verify_user_id(existing_id)
        if is_valid:
            return {"user_id": existing_id, "signature_valid": True, "status": "active"}

    signed_id = sign_user_id()
    return {"user_id": signed_id, "signature_valid": True, "status": "issued"}

