"""
Audio & Compilation API Router
"""

from fastapi import APIRouter, Depends
from typing import Optional
from server.models.schemas import SynthesizeRequest, SynthesizeResponse, CompileRequest, CompileResponse
from server.services.audio_service import audio_service
from server.services.compiler_service import compiler_service
from server.api.dependencies import get_api_key

router = APIRouter(prefix="/api", tags=["3. Audio & Compilation"])

@router.post("/synthesize-audio", response_model=SynthesizeResponse)
async def synthesize_audio(req: SynthesizeRequest, api_key: Optional[str] = Depends(get_api_key)):
    """Synthesizes speech via gemini-3.1-flash-tts-preview and executes Chronos timeline stretch."""
    result = audio_service.synthesize_and_align(
        scenes=req.scenes,
        dialogue=req.dialogue,
        voice_alex=req.voice_alex,
        voice_sam=req.voice_sam,
        session_id=req.session_id,
        api_key=api_key
    )
    return SynthesizeResponse(**result)

@router.post("/compile-video", response_model=CompileResponse)
async def compile_video(req: CompileRequest):
    """Compiles the final synchronized 1080p MP4 with permanent frame freezes via FFmpeg."""
    res = compiler_service.compile_production_video(
        session_id=req.session_id,
        video_filename=req.video_filename,
        audio_filename=req.audio_filename,
        chronos_schedule=req.chronos_schedule
    )
    return CompileResponse(**res)
