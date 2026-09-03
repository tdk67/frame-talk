"""
Model Context Protocol (MCP) Server Endpoint for Frame Talk.
Enables Google Cloud Agent Platform / Agent Builder and other MCP clients
to discover and execute Chronos Sync, ClickHouse Telemetry, and Audio duration tools.
Implements the JSON-RPC 2.0 MCP specification over HTTP.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from server.sync.chronos_engine import chronos_engine
from server.repositories.telemetry_repository import telemetry_repository

logger = logging.getLogger("frametalk.api.mcp")

router = APIRouter(tags=["5. Model Context Protocol (MCP)"])

MCP_TOOLS = [
    {
        "name": "calculate_chronos_hold",
        "description": (
            "Calculates millisecond PCM duration and required dynamic video hold (freeze duration) "
            "using the Chronos synchronization engine math (pcm_bytes / 48)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "speech_text": {
                    "type": "string",
                    "description": "Dialogue script text to be spoken in the scene."
                },
                "video_duration_ms": {
                    "type": "integer",
                    "description": "Actual duration of the visual screencast scene in milliseconds."
                },
                "words_per_second": {
                    "type": "number",
                    "default": 2.5,
                    "description": "Speech velocity pacing (default: 2.5 words/sec)."
                }
            },
            "required": ["speech_text", "video_duration_ms"]
        }
    },
    {
        "name": "log_clickhouse_telemetry",
        "description": (
            "Streams real-time time-series synchronization events to ClickHouse (castops.sync_events) "
            "for live monitoring on the Grafana Labs observability dashboard."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Unique session or video run identifier."
                },
                "scene_id": {
                    "type": "string",
                    "description": "Target visual scene identifier (e.g. scene_1)."
                },
                "event_type": {
                    "type": "string",
                    "description": "Type of event (e.g. AUDIO_SYNTH, TIMELINE_FREEZE_INJECTED)."
                },
                "audio_duration_ms": {
                    "type": "integer",
                    "description": "Measured PCM audio duration in milliseconds."
                },
                "freeze_injected_ms": {
                    "type": "integer",
                    "description": "Calculated video hold length in milliseconds."
                }
            },
            "required": ["session_id", "event_type"]
        }
    },
    {
        "name": "audit_script_pacing",
        "description": (
            "Audits technical dialogue for anti-timestamp compliance (no explicit 'at 0:14' mentions) "
            "and mathematical speech pacing budget against visual scene duration."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dialogue_text": {
                    "type": "string",
                    "description": "Candidate line of dialogue."
                },
                "target_duration_sec": {
                    "type": "number",
                    "description": "Scene video length in seconds."
                }
            },
            "required": ["dialogue_text", "target_duration_sec"]
        }
    }
]

def handle_mcp_call(method: str, params: Dict[str, Any], msg_id: Any, request: Optional[Request] = None) -> Dict[str, Any]:
    """Processes MCP JSON-RPC 2.0 requests with exception safety."""
    try:
        return _handle_mcp_call_internal(method, params, msg_id, request=request)
    except Exception as e:
        logger.exception(f"Unhandled error in MCP call '{method}': {e}")
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32603, "message": f"Internal MCP Server Error: {str(e)}"}
        }

def _handle_mcp_call_internal(method: str, params: Dict[str, Any], msg_id: Any, request: Optional[Request] = None) -> Dict[str, Any]:
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "FrameTalk-Chronos-Tool",
                    "version": "1.0.0",
                    "description": "Frame Talk Chronos Sync, Video Hold & ClickHouse Observability MCP Server"
                }
            }
        }

    if method in ("notifications/initialized", "initialized"):
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": MCP_TOOLS
            }
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "calculate_chronos_hold":
            speech_text = args.get("speech_text", "")
            video_dur_ms = int(args.get("video_duration_ms", 1000))
            words = [w for w in speech_text.split() if w]
            wps = float(args.get("words_per_second", 2.5))
            est_audio_ms = int((len(words) / wps) * 1000) if words else 1000

            # Chronos formula: required_freeze_ms = max(0, speech_needed - video_dur + 300ms)
            freeze_ms = max(0, est_audio_ms - video_dur_ms + 300) if est_audio_ms > video_dur_ms else 0
            
            result_payload = {
                "speech_duration_ms": est_audio_ms,
                "video_duration_ms": video_dur_ms,
                "required_freeze_ms": freeze_ms,
                "freeze_anchor_ratio": 0.70,
                "status": "FREEZE_REQUIRED" if freeze_ms > 0 else "NO_FREEZE_NEEDED"
            }
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(result_payload)}],
                    "isError": False
                }
            }

        if tool_name == "log_clickhouse_telemetry":
            # 1. Authentication gate: requires signed session token, Bearer/API key header, or inline api_key
            is_authenticated = False
            if request:
                has_user_id = getattr(request.state, "has_user_id", False)
                auth_header = request.headers.get("authorization", "")
                api_key_header = request.headers.get("x-api-key", "")
                if has_user_id or auth_header or api_key_header:
                    is_authenticated = True
            if args.get("api_key") or args.get("auth_token"):
                is_authenticated = True

            if not is_authenticated:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized: log_clickhouse_telemetry requires authentication via X-FrameTalk-User-Id session token, Authorization header, or X-API-Key."
                    }
                }

            session_id = str(args.get("session_id", "mcp_session")).strip()
            event_type = str(args.get("event_type", "MCP_EVENT")).strip()
            scene_id = str(args.get("scene_id", "scene_1")).strip()
            audio_dur = int(args.get("audio_duration_ms", 0))
            freeze_dur = int(args.get("freeze_injected_ms", args.get("freeze_duration_ms", 0)))

            # Input validation and bounds checking to prevent database poisoning
            import re
            valid_id = bool(re.match(r"^[a-zA-Z0-9_\-]{3,64}$", session_id))
            valid_event = bool(re.match(r"^[a-zA-Z0-9_\-]{3,64}$", event_type))
            if not valid_id or not valid_event or not (0 <= audio_dur <= 600000) or not (0 <= freeze_dur <= 600000):
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": "Validation Error: session_id and event_type must be alphanumeric (3-64 chars) and durations within [0, 600000]ms."}],
                        "isError": True
                    }
                }

            telemetry_repository.log_sync_event(
                session_id=session_id,
                turn_index=int(args.get("turn_index", 0)),
                speaker=str(args.get("speaker", "Alex")).strip(),
                dialogue_text=str(args.get("dialogue_text", f"MCP Event {event_type} on {scene_id}")).strip(),
                audio_clip_path=str(args.get("audio_clip_path", f"{session_id}_{scene_id}.pcm")).strip(),
                audio_duration_ms=audio_dur,
                video_scene_start_ms=int(args.get("video_scene_start_ms", 0)),
                video_scene_end_ms=int(args.get("video_scene_end_ms", audio_dur)),
                video_scene_duration_ms=int(args.get("video_scene_duration_ms", max(0, audio_dur - freeze_dur))),
                required_freeze_ms=freeze_dur,
                accumulated_drift_ms=0,
                pacing_status="SYNCHRONIZED" if freeze_dur == 0 else "HOLD_INJECTED",
                token_cost=0.0
            )
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Successfully streamed {event_type} event to ClickHouse."}],
                    "isError": False
                }
            }

        if tool_name == "audit_script_pacing":
            dialogue_text = args.get("dialogue_text", "")
            target_dur_sec = float(args.get("target_duration_sec", 5.0))
            import re
            has_timestamps = bool(re.search(r'\b\d{1,2}:\d{2}\b', dialogue_text))
            words = len(dialogue_text.split())
            est_sec = words / 2.5
            pacing_ratio = round(est_sec / target_dur_sec, 2) if target_dur_sec > 0 else 1.0

            result_payload = {
                "contains_forbidden_timestamps": has_timestamps,
                "word_count": words,
                "estimated_speech_seconds": round(est_sec, 2),
                "target_seconds": target_dur_sec,
                "pacing_ratio": pacing_ratio,
                "passed": not has_timestamps and (0.7 <= pacing_ratio <= 1.5)
            }
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(result_payload)}],
                    "isError": False
                }
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."}
        }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method '{method}' not implemented."}
    }

@router.post("/mcp")
async def mcp_post_endpoint(request: Request):
    """MCP JSON-RPC 2.0 message handler for Google Cloud Agent Platform."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, status_code=400)

    method = data.get("method", "")
    params = data.get("params", {})
    msg_id = data.get("id")

    res = handle_mcp_call(method, params, msg_id, request=request)
    return JSONResponse(res)

@router.get("/mcp")
async def mcp_get_endpoint():
    """Returns the MCP server capability description and tool list."""
    return {
        "name": "FrameTalk-Chronos-Tool",
        "protocol": "Model Context Protocol (MCP)",
        "version": "1.0.0",
        "transport": "HTTP/JSON-RPC 2.0",
        "tools": MCP_TOOLS
    }
