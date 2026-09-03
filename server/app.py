"""
Frame Talk: The Multimodal Screen-to-Podcast Studio Engine.
FastAPI Application Entrypoint (Hexagonal Architecture).
"""

import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import config
from server.api.middleware.error_handler import setup_error_handlers
from server.api.routers.ingest_router import router as ingest_router
from server.api.routers.script_router import router as script_router
from server.api.routers.audio_router import router as audio_router
from server.api.routers.telemetry_router import router as telemetry_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("frametalk.server")

# Instantiate FastAPI Application
app = FastAPI(
    title=f"{config.app_name} Studio Engine",
    description="Multimodal Screen-to-Podcast Production Pipeline with Gemini 3.7 Flash, Chronos Sync & ClickHouse",
    version=config.version
)

# User Context & Production Security Headers ASGI Middleware (Zero-deadlock on large uploads)
from server.api.middleware.user_context import PureASGIUserContextMiddleware
app.add_middleware(PureASGIUserContextMiddleware)

from fastapi.responses import PlainTextResponse, Response

# Restricted Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Attach Global Error Handlers (Fail-fast, transparent JSON envelopes)
setup_error_handlers(app)

from server.api.routers.mcp_router import router as mcp_router

# Register Hexagonal API Routers
app.include_router(ingest_router)
app.include_router(script_router)
app.include_router(audio_router)
app.include_router(telemetry_router)
app.include_router(mcp_router)

# Dynamic Crawler & LLM Manifest Endpoints (Automatically respect configured domain)
@app.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt(request: Request):
    app_url = config.app_url.rstrip("/")
    return f"""# ==============================================================================
# Frame Talk: Robots.txt Specification
# Multimodal Screen-to-Podcast Studio Engine
# Host: {app_url}
# ==============================================================================

# 1. Standard Web Search Crawlers (Google, Bing, DuckDuckGo, Baidu, Yandex)
User-agent: *
Allow: /
Allow: /index.html
Allow: /impressum.html
Allow: /datenschutz.html
Allow: /sitemap.xml
Allow: /llms.txt
Allow: /llms-full.txt
Allow: /api/health
Allow: /api/docs
Allow: /api/openapi.json

# Disallow raw internal uploads and output directories
Disallow: /uploads/
Disallow: /output/
Disallow: /api/jobs/

# 2. AI Crawlers & LLM Scrapers (OpenAI, Anthropic, Google, Perplexity, Cohere)
User-agent: GPTBot
User-agent: ChatGPT-User
User-agent: ClaudeBot
User-agent: Claude-Web
User-agent: Google-Extended
User-agent: PerplexityBot
User-agent: CCBot
User-agent: Bytespider
User-agent: cohere-ai
Allow: /
Allow: /llms.txt
Allow: /llms-full.txt
Allow: /sitemap.xml
Allow: /api/openapi.json
Disallow: /uploads/
Disallow: /output/

# 3. Sitemap Index Reference
Sitemap: {app_url}/sitemap.xml
"""

@app.get("/sitemap.xml")
def get_sitemap_xml(request: Request):
    app_url = config.app_url.rstrip("/")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{app_url}/</loc>
        <lastmod>2026-09-03</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{app_url}/llms.txt</loc>
        <lastmod>2026-09-03</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>{app_url}/llms-full.txt</loc>
        <lastmod>2026-09-03</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>{app_url}/impressum.html</loc>
        <lastmod>2026-09-03</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
    <url>
        <loc>{app_url}/datenschutz.html</loc>
        <lastmod>2026-09-03</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
</urlset>"""
    return Response(content=content, media_type="application/xml")

@app.get("/llms.txt", response_class=PlainTextResponse)
def get_llms_txt(request: Request):
    app_url = config.app_url.rstrip("/")
    template_path = config.public_dir / "llms.txt"
    if template_path.exists():
        text = template_path.read_text(encoding="utf-8")
        return text.replace("https://frame-talk.taskmind-ai.com", app_url)
    return f"# Frame Talk\n\n> Multimodal Studio Engine\n\n- [API Docs]({app_url}/docs)\n"

@app.get("/llms-full.txt", response_class=PlainTextResponse)
def get_llms_full_txt(request: Request):
    target_host = f"{config.app_subdomain}.{config.domain}" if config.app_subdomain else config.domain
    template_path = config.public_dir / "llms-full.txt"
    if template_path.exists():
        text = template_path.read_text(encoding="utf-8")
        return text.replace("frame-talk.taskmind-ai.com", target_host)
    return f"# Frame Talk Full Guide\n\nHost: {target_host}\n"

# Mount Static Directories (Uploads, Output, Public Web UI)
app.mount("/uploads", StaticFiles(directory=str(config.uploads_dir)), name="uploads")
app.mount("/output", StaticFiles(directory=str(config.output_dir)), name="output")
app.mount("/", StaticFiles(directory=str(config.public_dir), html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
