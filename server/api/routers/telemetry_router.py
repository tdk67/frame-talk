"""
Telemetry & Health API Router
"""

from typing import Optional
from fastapi import APIRouter
from server.models.schemas import HealthResponse
from server.repositories.telemetry_repository import telemetry_repository
from server.core.config import config

router = APIRouter(prefix="/api", tags=["4. Observability & Health"])

@router.get("/health", response_model=HealthResponse)
def health_check():
    """System heartbeat and connectivity metrics."""
    return HealthResponse(
        status="healthy",
        service=f"{config.app_name} Studio Engine",
        clickhouse_connected=telemetry_repository.is_connected,
        clickhouse_host=telemetry_repository.host_info,
        vision_model=config.vision_model,
        script_model=config.script_model,
        tts_model=config.tts_model
    )

@router.get("/clickhouse/events")
def get_clickhouse_events(session_id: Optional[str] = None, limit: int = 50):
    """Queries ClickHouse time-series event records."""
    events = telemetry_repository.get_events(session_id=session_id, limit=limit)
    metrics = telemetry_repository.get_metrics_summary(session_id=session_id)
    return {
        "events": events,
        "metrics": metrics,
        "clickhouse_status": "ONLINE" if telemetry_repository.is_connected else "SIMULATED_BUFFER"
    }

@router.get("/clickhouse/metrics")
def get_clickhouse_metrics(session_id: Optional[str] = None):
    """Aggregated sync & drift metrics."""
    return telemetry_repository.get_metrics_summary(session_id=session_id)

@router.get("/clickhouse/llm-calls")
def get_clickhouse_llm_calls(session_id: Optional[str] = None, limit: int = 50):
    """Queries individual LLM model invocations, token counts, and costs."""
    calls = telemetry_repository.get_llm_calls(session_id=session_id, limit=limit)
    metrics = telemetry_repository.get_llm_metrics_summary(session_id=session_id)
    return {
        "calls": calls,
        "metrics": metrics,
        "clickhouse_status": "ONLINE" if telemetry_repository.is_connected else "SIMULATED_BUFFER"
    }

@router.get("/clickhouse/llm-metrics")
def get_clickhouse_llm_metrics(session_id: Optional[str] = None):
    """Aggregated LLM invocation counts, tokens, and cost breakdown per model and agent."""
    return telemetry_repository.get_llm_metrics_summary(session_id=session_id)

@router.get("/clickhouse/user-statistics")
def get_user_statistics():
    """Aggregated anonymous user counts, conversion funnel, and activity distributions."""
    return telemetry_repository.get_user_statistics_summary()

@router.get("/clickhouse/user-activities")
def get_user_activities(limit: int = 50, user_hash: Optional[str] = None):
    """Recent anonymous user activity log (zero PII, pseudonymized)."""
    return {
        "activities": telemetry_repository.get_user_activities(limit=limit, user_hash=user_hash),
        "summary": telemetry_repository.get_user_statistics_summary()
    }

@router.get("/estimate-cost")
def estimate_cost_get(duration_sec: float = 120.0, readme_chars: int = 5000):
    """Calculates transparent pre-flight run cost and token estimation."""
    from server.core.pricing import estimate_pipeline_cost
    return estimate_pipeline_cost(video_duration_sec=duration_sec, readme_chars=readme_chars)

@router.post("/estimate-cost")
async def estimate_cost_post(request: Request):
    """Calculates transparent pre-flight run cost and token estimation via POST body."""
    from server.core.pricing import estimate_pipeline_cost
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    duration_sec = float(body.get("duration_sec", 120.0))
    readme_chars = int(body.get("readme_chars", 5000))
    return estimate_pipeline_cost(video_duration_sec=duration_sec, readme_chars=readme_chars)


# --- Zero-Token BYOK Verification (Matching VentureBot Spec) ---

import urllib.request
import urllib.parse
import json
import asyncio
from fastapi import Request

def mask_api_key(raw: str) -> str:
    if not raw: return ""
    trimmed = raw.strip()
    if len(trimmed) <= 8: return "••••••••"
    return f"{trimmed[:4]}••••••••{trimmed[-4:]}"

async def verify_google_gemini_key(api_key: str, timeout_seconds: float = 8.0) -> tuple[bool, str]:
    """Validate Google Gemini API key against Google's metadata models API.
    Zero token cost (metadata query only, no text generation).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(api_key.strip())}&pageSize=1"

    def _call() -> tuple[bool, str]:
        req = urllib.request.Request(url, headers={"User-Agent": "FrameTalk/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if resp.status == 200:
                    return True, ""
                return False, f"Google API returned status {resp.status}"
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("error", {}).get("message", "") or str(e)
            except Exception:
                msg = str(e)
            return False, msg
        except Exception as e:
            return False, f"Could not reach Google API: {e}"

    return await asyncio.to_thread(_call)

@router.post("/byok/verify")
async def verify_byok_endpoint(req: Request):
    """Verifies a Google Gemini API key with zero token cost against Google AI Studio API."""
    try:
        body = await req.json()
    except Exception:
        body = {}

    key = req.headers.get("X-API-Key") or req.headers.get("x-api-key") or body.get("api_key", "")
    if not key or not key.strip():
        return {"valid": False, "error": "Please paste your Google Gemini API key."}

    key = key.strip()
    if key.startswith("sk-or-") or key.startswith("sk-"):
        return {
            "valid": False,
            "provider": "openrouter",
            "error": "OpenRouter is not supported. Frame Talk runs natively on Google Gemini (Free Tier from Google AI Studio supported)."
        }

    valid, err_msg = await verify_google_gemini_key(key)
    return {
        "valid": valid,
        "provider": "gemini",
        "masked": mask_api_key(key),
        "error": err_msg if not valid else None
    }

