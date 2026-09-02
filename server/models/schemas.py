"""
Pydantic Request & Response Data Transfer Objects (DTOs) for Frame Talk
Separated from route definitions for clean hexagonal decoupling.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# ─── Health & Connectivity ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    clickhouse_connected: bool
    clickhouse_host: str
    vision_model: str
    script_model: str
    tts_model: str

# ─── Uploads & Ingestion ─────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    video_filename: Optional[str] = None
    video_path: Optional[str] = None
    original_video_name: Optional[str] = None
    video_hash: Optional[str] = None
    readme_filename: Optional[str] = None
    readme_text: Optional[str] = None
    original_readme_name: Optional[str] = None

class AnalyzeRequest(BaseModel):
    video_filename: str = Field(..., description="Filename of the uploaded video in uploads/")
    readme_text: str = Field(..., description="Full text content of project README.md")
    video_duration_seconds: float = Field(..., gt=0, description="Total video runtime in seconds")
    video_hash: Optional[str] = Field(None, description="SHA-256 hash of the video for caching")

class AnalyzeResponse(BaseModel):
    scenes: List[Dict[str, Any]]
    eval_scorecard: Optional[Dict[str, Any]] = None
    total_scenes: int

# ─── Dialogue Scriptwriting ──────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    scenes: List[Dict[str, Any]] = Field(..., min_items=1)
    readme_text: str

class ScriptResponse(BaseModel):
    dialogue: List[Dict[str, Any]]
    total_turns: int

# ─── QA & Pacing Audit ───────────────────────────────────────────────────────

class QaRequest(BaseModel):
    scenes: List[Dict[str, Any]]
    dialogue: List[Dict[str, Any]]
    readme_text: str

class QaResponse(BaseModel):
    overall_score: int
    accuracy_score: int
    readme_score: int
    pacing_score: int
    feedback: str
    checklist: Dict[str, bool]

# ─── Audio Synthesis & Chronos Sync ──────────────────────────────────────────

class TestVoiceRequest(BaseModel):
    voice_name: str = "Puck"
    text: str = "Hi, I'm your selected voice. How do I sound?"

class TestVoiceResponse(BaseModel):
    audio_url: str

class SynthesizeRequest(BaseModel):
    session_id: Optional[str] = None
    scenes: List[Dict[str, Any]]
    dialogue: List[Dict[str, Any]]
    voice_alex: str = "Puck"
    voice_sam: str = "Kore"

class SynthesizeResponse(BaseModel):
    session_id: str
    audio_url: str
    audio_filename: str
    chronos_schedule: Dict[str, Any]
    total_audio_ms: int
    updated_turns: List[Dict[str, Any]]

# ─── Production Video Compilation ────────────────────────────────────────────

class CompileRequest(BaseModel):
    session_id: str
    video_filename: str
    audio_filename: str
    chronos_schedule: Dict[str, Any]

class CompileResponse(BaseModel):
    status: str
    video_url: str
    video_path: str
    total_duration_sec: float
    message: str

# ─── Error Envelope ──────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: bool = True
    status_code: int
    error_type: str
    message: str
    detail: str
