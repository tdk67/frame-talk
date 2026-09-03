"""
Google Cloud Agent Builder & Vertex AI Enterprise Integration Module.
Provides dual-mode runtime client factory for Google Cloud Vertex AI / Gemini Enterprise
and exports official Agent Builder multi-agent specifications and tool contracts.
"""

import os
import logging
from typing import Optional, Dict, Any
from server.core.config import config

logger = logging.getLogger("frametalk.core.agent_builder")

def get_genai_client(api_key: Optional[str] = None):
    """
    Factory for Google GenAI Client:
    1. If Vertex AI is enabled (GOOGLE_GENAI_USE_VERTEXAI=true or config), connects
       directly to Google Cloud Vertex AI Enterprise (Gemini Enterprise Agent Platform).
    2. Otherwise, connects using the provided or server-configured Google Gemini API key.
    """
    from google import genai

    if config.vertex_ai_enabled:
        project = config.google_cloud_project
        location = config.google_cloud_location
        logger.info(f"Initializing Google GenAI Client with Google Cloud Vertex AI (Project: {project}, Location: {location})...")
        return genai.Client(vertexai=True, project=project, location=location)

    active_key = api_key or config.get_server_api_key()
    if not active_key:
        raise ValueError(
            "No Google Gemini API key provided. Please configure your API key in Frame Talk or set GOOGLE_API_KEY."
        )

    logger.info("Initializing Google GenAI Client with Google Gemini API key...")
    return genai.Client(api_key=active_key)

def get_agent_builder_spec() -> Dict[str, Any]:
    """
    Returns the formal Google Cloud Agent Builder architecture specification
    and tool contracts for the Agentic Cinema Hackathon.
    """
    return {
        "platform": "Google Cloud Agent Builder (Vertex AI Enterprise)",
        "runtime_mode": "Vertex AI Enterprise" if config.vertex_ai_enabled else "Google Cloud Gemini Native",
        "google_cloud_project": config.google_cloud_project,
        "google_cloud_location": config.google_cloud_location,
        "hackathon_partner_track": "ClickHouse + Grafana Labs",
        "agents": [
            {
                "agent_id": "director_ingestion_agent",
                "name": "Director & Ingestion Agent",
                "role": "Multimodal Visual Analysis & Scene Alignment",
                "model": config.vision_model,
                "description": (
                    "Ingests raw screencast video tokens directly into Gemini 3.7 Flash via Google Cloud "
                    "File API, cross-referencing visual clicks and state changes with project documentation."
                ),
                "capabilities": [
                    "Native raw video token execution (no external transcript needed)",
                    "Millisecond UI state boundary detection",
                    "Temporal Action-Reaction causality tracking",
                    "Self-correction refinement loop (re-prompts if visual eval < 80)"
                ],
                "tools": [
                    "video_magic_byte_validator",
                    "ffmpeg_subsegment_sampler",
                    "xml_boundary_isolation_wrapper"
                ]
            },
            {
                "agent_id": "scriptwriter_persona_agent",
                "name": "Technical Scriptwriter Persona Agent",
                "role": "Collaborative Dual-Host Technical Podcast Dialogue",
                "model": config.script_model,
                "description": (
                    "Orchestrates technical conversation between Alex (Lead Systems Architect) and Sam "
                    "(Dev Advocate & UX Specialist) grounded strictly in visual scenes."
                ),
                "capabilities": [
                    "Mathematical word budgeting (~2.5 words/sec) to prevent video overrun",
                    "Strict scene_id binding",
                    "Zero synthetic timestamp rule enforcement (no 'at 0:14')",
                    "Collaborative human turn-taking dynamics (180ms - 240ms pauses)"
                ],
                "grounding": [
                    "Technical Documentation (README.md inside <untrusted_documentation>)",
                    "Visual Scene Breakdown Array"
                ]
            },
            {
                "agent_id": "qa_pacing_auditor_agent",
                "name": "QA & Pacing Auditor Agent",
                "role": "Adversarial Quality Control & Pacing Verification",
                "model": config.qa_model,
                "description": (
                    "Audits dialogue drafts against visual scenes and README concepts using LLM-as-a-Judge, "
                    "returning structured scorecards and triggering refinement if defects are detected."
                ),
                "capabilities": [
                    "Anti-timestamp forensic check",
                    "Visual scene anchoring verification",
                    "README concept grounding ratio calculation",
                    "Refinement loop feedback generation"
                ]
            },
            {
                "agent_id": "chronos_telemetry_tool",
                "name": "Chronos Sync & Observability Engine",
                "role": "Millisecond PCM Duration Metering & Dynamic Visual Hold",
                "model": config.tts_model,
                "description": (
                    "Synthesizes uncompressed 24 kHz 16-bit Mono PCM audio, meters exact durations "
                    "(duration_ms = pcm_bytes / 48), calculates dynamic timeline stretching holds, and "
                    "streams real-time synchronization events to ClickHouse."
                ),
                "partner_integrations": [
                    {
                        "partner": "ClickHouse",
                        "component": "castops.sync_events",
                        "type": "Time-series columnar telemetry store",
                        "status": "Active"
                    },
                    {
                        "partner": "Grafana Labs",
                        "component": "CastOps Dashboard (Port 3004 / https://grafana.taskmind-ai.com)",
                        "type": "Production observability & latency monitoring",
                        "status": "Active"
                    }
                ],
                "capabilities": [
                    "Multi-speaker raw PCM synthesis (Puck & Kore)",
                    "Exact duration metering without audio estimation drift",
                    "Dynamic video hold calculation: required_freeze_ms = max(0, speech - video + 300ms)",
                    "70% scene depth visual anchor freeze placement",
                    "FFmpeg dynamic timeline concatenation"
                ]
            }
        ]
    }
