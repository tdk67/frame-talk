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

        from server.core.guardrails import validate_video_file
        valid, err_msg = validate_video_file(video_path, max_size_bytes=int(config.max_video_size_mb * 1024 * 1024))
        if not valid:
            raise InvalidInputException(f"Invalid video payload: {err_msg}")

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


    def _orchestrate_with_adk_director(
        self,
        scenes: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Executes dialogue generation through the Google Cloud Agent Platform
        ADK Director (agent.py:root_agent) or Vertex AI ReasoningEngine.
        Returns parsed and validated dialogue turns, or None if unavailable.
        """
        import os
        import json
        import re
        from server.core.config import config
        from server.repositories.telemetry_repository import telemetry_repository

        active_key = api_key or config.get_server_api_key()
        if active_key and not os.environ.get("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = active_key

        session_id = scenes[0].get("scene_id", "adk_session") if scenes else "adk_session"

        # 1. Attempt Google Cloud Vertex AI ReasoningEngine if explicitly enabled
        if config.vertex_ai_enabled:
            try:
                from vertexai.preview import reasoning_engines
                engine_resource = f"projects/{config.google_cloud_project}/locations/{config.google_cloud_location}/reasoningEngines/{config.google_cloud_agent_id}"
                logger.info(f"Dispatching script orchestration to Google Cloud ReasoningEngine: {engine_resource}")
                y_app = reasoning_engines.ReasoningEngine(engine_resource)
                payload = {
                    "video_scenes": scenes,
                    "readme_text": readme_text[:2000],
                    "session_source": "agent_engine"
                }
                res = y_app.query(input=json.dumps(payload))
                telemetry_repository.log_agent_callback(
                    session_id=session_id,
                    tool_name="reasoning_engine_query",
                    session_source="agent_engine",
                    metadata=f"scenes:{len(scenes)}"
                )
                if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                    return res
            except Exception as e:
                logger.warning(f"Google Cloud Agent Engine remote query bypassed ({e}). Falling back to ADK Director.")

        # 2. Execute Local Google Cloud ADK Director (agent.py:root_agent)
        try:
            from google.adk.runners import InMemoryRunner
            from google.genai import types
            import agent

            if hasattr(agent, "root_agent"):
                logger.info(f"Executing ADK Director agent '{agent.root_agent.name}' (InMemoryRunner)...")
                runner = InMemoryRunner(agent=agent.root_agent)
                runner.session_service.create_session_sync(
                    app_name=runner.app_name,
                    user_id="adk_director_user",
                    session_id=session_id
                )

                prompt = (
                    "You are FrameTalk_Director. Generate an engaging two-host technical podcast dialogue between Alex and Sarah for these visual scenes:\n"
                    f"{json.dumps(scenes, indent=2)}\n\n"
                    "README CONTEXT:\n"
                    f"{readme_text[:2000]}\n\n"
                    "Return ONLY valid JSON matching this schema:\n"
                    "```json\n"
                    '{"dialogue": [\n'
                    '  {"turn_index": 0, "scene_id": "scene_1", "speaker": "Alex", "text": "..."},\n'
                    '  {"turn_index": 1, "scene_id": "scene_1", "speaker": "Sarah", "text": "..."}\n'
                    ']}\n'
                    "```"
                )
                msg = types.Content(parts=[types.Part(text=prompt)])
                events = list(runner.run(user_id="adk_director_user", session_id=session_id, new_message=msg))

                combined_text = ""
                for ev in events:
                    if getattr(ev, "content", None) and ev.content.parts:
                        for p in ev.content.parts:
                            if getattr(p, "text", None):
                                combined_text += p.text

                turns = []
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", combined_text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        turns = data.get("dialogue", [])
                    except Exception:
                        pass
                if not turns:
                    first_brace = combined_text.find("{")
                    last_brace = combined_text.rfind("}")
                    if first_brace != -1 and last_brace > first_brace:
                        try:
                            data = json.loads(combined_text[first_brace:last_brace + 1])
                            turns = data.get("dialogue", [])
                        except Exception:
                            pass

                if turns and isinstance(turns, list) and isinstance(turns[0], dict):
                    telemetry_repository.log_agent_callback(
                        session_id=session_id,
                        tool_name="adk_director_execution",
                        session_source="adk_director",
                        metadata=f"scenes:{len(scenes)};turns:{len(turns)};agent:{agent.root_agent.name}"
                    )
                    cleaned = scriptwriter_agent._clean_and_index_turns(turns, scenes)
                    logger.info(f"ADK Director successfully produced {len(cleaned)} dialogue turns.")
                    return cleaned
        except Exception as e:
            logger.warning(f"ADK Director execution failed ({e}). Falling back to native in-process scriptwriter.")

        return None

    def generate_dialogue_script(
        self,
        scenes: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates dynamic two-host live conversation anchored to scenes."""
        if not scenes:
            raise InvalidInputException("Cannot generate dialogue without visual scenes.")

        # Try ADK Director / Agent Engine forward call if enabled
        adk_result = self._orchestrate_with_adk_director(scenes=scenes, readme_text=readme_text, api_key=api_key)
        if adk_result:
            return adk_result

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
