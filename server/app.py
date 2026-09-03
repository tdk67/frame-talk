"""
Frame Talk: The Multimodal Screen-to-Podcast Studio Engine.
FastAPI Application Entrypoint (Hexagonal Architecture).
Bootstraps middleware, global error handlers, and hexagonal API routers.
"""

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import config
from server.api.middleware.error_handler import setup_error_handlers
from server.api.middleware.user_context import PureASGIUserContextMiddleware

from server.api.routers.discovery_router import router as discovery_router
from server.api.routers.ingest_router import router as ingest_router
from server.api.routers.script_router import router as script_router
from server.api.routers.audio_router import router as audio_router
from server.api.routers.telemetry_router import router as telemetry_router
from server.api.routers.mcp_router import router as mcp_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("frametalk.server")

# Instantiate FastAPI Application
app = FastAPI(
    title=f"{config.app_name} Studio Engine",
    description="Multimodal Screen-to-Podcast Production Pipeline with Gemini 3.7 Flash, Chronos Sync & ClickHouse",
    version=config.version
)

# User Context & Production Security Headers ASGI Middleware (Zero-deadlock on large uploads)
app.add_middleware(PureASGIUserContextMiddleware)

# Restricted Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Attach Global Error Handlers (Fail-fast, transparent JSON envelopes)
setup_error_handlers(app)

# Register Hexagonal API Routers
app.include_router(discovery_router)
app.include_router(ingest_router)
app.include_router(script_router)
app.include_router(audio_router)
app.include_router(telemetry_router)
app.include_router(mcp_router)

@app.on_event("startup")
def on_startup():
    """Fails fast on application startup if required secrets are absent in .env."""
    config.validate_secrets()

# Mount Static Directories (Output media and Public Web UI)
# Note: uploads directory is intentionally NOT mounted statically to prevent arbitrary file enumeration
app.mount("/output", StaticFiles(directory=str(config.output_dir)), name="output")
app.mount("/", StaticFiles(directory=str(config.public_dir), html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)
