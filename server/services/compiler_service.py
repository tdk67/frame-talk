"""
Compiler Service: Orchestrates server-side FFmpeg dynamic frame hold video stitching.
"""

from typing import Dict, Any
from server.compiler.video_compiler import video_compiler
from server.repositories.file_repository import file_repository

class CompilerService:
    def compile_production_video(
        self,
        session_id: str,
        video_filename: str,
        audio_filename: str,
        chronos_schedule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stitches final frame-stretched 1080p MP4."""
        video_path = file_repository.get_upload_path(video_filename)
        audio_path = file_repository.get_output_path(audio_filename)

        out_name = f"frametalk_synced_{session_id[:8]}.mp4"
        res = video_compiler.compile_synchronized_video(
            video_input_path=video_path,
            audio_input_path=audio_path,
            chronos_schedule=chronos_schedule,
            output_filename=out_name
        )
        res["video_url"] = f"/output/{out_name}"
        return res

compiler_service = CompilerService()
