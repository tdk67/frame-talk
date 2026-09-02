"""
Studio Core Service
Coordinates video analysis, live dialogue generation, and script QA audit.
Enforces intelligent retries and transparent error propagation without silent death.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from server.agents.ingestion_agent import ingestion_agent
from server.agents.scriptwriter_agent import scriptwriter_agent
from server.agents.qa_agent import qa_agent
from server.repositories.file_repository import file_repository
from server.core.retry_handler import execute_with_retry
from server.core.exceptions import InvalidInputException

logger = logging.getLogger("frametalk.service.studio")

class StudioService:
    def analyze_video_screen(
        self,
        video_filename: str,
        readme_text: str,
        video_duration_seconds: float,
        api_key: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Analyzes raw video pixels and outputs granular visual scenes."""
        if not video_filename:
            raise InvalidInputException("video_filename cannot be empty.")
        if not readme_text:
            raise InvalidInputException("readme_text cannot be empty.")

        import os
        from server.core.config import config

        # Validate video format (supports .mp4, .webm, .mov, .mkv)
        ext = os.path.splitext(video_filename)[1].lower()
        if ext not in config.supported_video_extensions:
            raise InvalidInputException(
                f"Unsupported video format '{ext}'. Supported formats: {', '.join(config.supported_video_extensions)}",
                detail=f"Please upload a video with one of: {', '.join(config.supported_video_extensions)}"
            )

        # Validate duration limits (30s to 300s / 5min)
        if video_duration_seconds < config.min_video_duration_sec:
            raise InvalidInputException(
                f"Video duration ({video_duration_seconds:.1f}s) is too short. Minimum required is {config.min_video_duration_sec:.0f}s.",
                detail=f"Videos less than {config.min_video_duration_sec:.0f}s cannot produce a meaningful multi-scene podcast breakdown."
            )
        if video_duration_seconds > config.max_video_duration_sec:
            raise InvalidInputException(
                f"Video duration ({video_duration_seconds:.1f}s) exceeds limit of {config.max_video_duration_sec:.0f}s (5 minutes).",
                detail=f"Please trim your screencast to under {config.max_video_duration_sec:.0f} seconds."
            )

        video_path = file_repository.get_upload_path(video_filename)

        return execute_with_retry(
            action_name="Analyze Video Screen (Gemini 3.7 Flash)",
            fn=ingestion_agent.analyze_screencast,
            video_path=video_path,
            readme_text=readme_text,
            video_duration_seconds=video_duration_seconds,
            api_key=api_key
        )

    async def run_video_analysis_job(
        self,
        job_id: str,
        video_filename: str,
        readme_text: str,
        video_duration_seconds: float,
        api_key: Optional[str] = None,
        video_hash: Optional[str] = None
    ):
        """Background worker that runs analysis and updates job state."""
        from server.repositories.job_repository import job_repository
        job_repository.update_job(job_id, status="PROCESSING")
        try:
            scenes, eval_scorecard = self.analyze_video_screen(
                video_filename=video_filename,
                readme_text=readme_text,
                video_duration_seconds=video_duration_seconds,
                api_key=api_key
            )
            result = {
                "scenes": scenes,
                "eval_scorecard": eval_scorecard,
                "total_scenes": len(scenes)
            }
            
            job_repository.update_job(job_id, status="COMPLETED", result=result)
        except Exception as e:
            logger.error(f"Video analysis job {job_id} failed: {e}")
            job_repository.update_job(job_id, status="FAILED", error=str(e))


    def generate_dialogue_script(
        self,
        scenes: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates dynamic two-host live conversation anchored to scenes."""
        if not scenes:
            raise InvalidInputException("Cannot generate dialogue without visual scenes.")

        return execute_with_retry(
            action_name="Generate Dialogue Script (Gemini 3.7 Flash)",
            fn=scriptwriter_agent.generate_live_dialogue,
            scenes=scenes,
            readme_text=readme_text,
            api_key=api_key
        )

    def audit_dialogue_script(
        self,
        scenes: List[Dict[str, Any]],
        dialogue: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Audits dialogue for video fidelity, README coverage, and cadence."""
        return execute_with_retry(
            action_name="QA Script Audit",
            fn=qa_agent.audit_script,
            scenes=scenes,
            dialogue=dialogue,
            readme_text=readme_text,
            api_key=api_key
        )

studio_service = StudioService()
