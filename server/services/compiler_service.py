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
        
        # Determine total duration (if available from FFmpeg or approximate)
        # We can try to extract duration or just set it to 0 for now.
        video_url = f"/output/{out_name}"
        
        return {
            "status": "success" if res.get("success") else "failed",
            "video_url": video_url,
            "video_path": res.get("output_path", ""),
            "total_duration_sec": 0.0, # Will need FFprobe to get exact, placeholder for now
            "message": "Compilation completed successfully." if res.get("success") else "Compilation failed."
        }

compiler_service = CompilerService()
