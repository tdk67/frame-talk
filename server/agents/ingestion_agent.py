"""
Ingestion & Alignment Agent for Frame Talk
Ingests silent screencast video and project README.md, extracts UI actions
and system state transitions down to the millisecond using gemini-3.7-flash.
Ensures screen-by-screen granular inspection of real visual pixels, button clicks,
and state changes.
"""

import os
import re
import json
import time
import base64
import logging
import subprocess
from typing import List, Dict, Any, Optional

from server.core.agent_builder import get_genai_client
from server.core.config import config

logger = logging.getLogger("frametalk.agent.ingestion")

class IngestionAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.get_server_api_key()

    def analyze_screencast(
        self,
        video_path: str,
        readme_text: str,
        video_duration_seconds: float,
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Multimodal video analysis: parses video file and cross-references README.
        Returns a list of structured Visual Scenes with millisecond precision.
        """
        active_key = api_key or self.api_key or config.get_server_api_key()
        if not active_key and not config.vertex_ai_enabled:
            raise ValueError("No Gemini API key provided. Please configure your API key in Frame Talk.")

        from server.core.guardrails import sanitize_and_inspect_text, wrap_with_isolation_boundary
        sanitized_readme = sanitize_and_inspect_text(readme_text, max_chars=40000, context_name="README.md")
        isolated_readme = wrap_with_isolation_boundary(sanitized_readme, "untrusted_documentation")

        # Prompt for Gemini Multimodal Timelined Breakdown (Matching Gold Standard PDF)
        prompt = f"""Analyse the uploaded video and project documentation.
Generate a timelined breakdown of the video in approximately 20-30 second intervals (or natural UI transition boundaries) detailing:
1. What we see on the screen (exact page titles, active tabs, dialogs, visible text in quotes, terminal logs, code)
2. What the user is doing (exact clicks on named buttons, text typed into inputs, scrolling, switching browser tabs)
3. How the application is reacting (navigation changes, modal popups, status badges changing, streaming markdown, rendering data tables or scorecards)

DOCUMENTATION CONTEXT:
{isolated_readme}

TOTAL VIDEO DURATION: {video_duration_seconds:.2f} seconds ({self._format_time(video_duration_seconds)})

FEW-SHOT GOLD STANDARD REFERENCE (MATCH THIS LEVEL OF GRANULARITY AND SPECIFICITY):
- On Screen: The landing page of Idea Lint ("Stop Guessing. Start Validating.") displaying value propositions (6 AI Agents, 5 min debate, privacy features, and step-by-step workflow).
- User Action: The user scrolls through the features and pricing sections, clicks "Start Your First Debate", checks the Model API Settings (BYOK) modal, closes it, and enters an idea pitch for "Song Blueprint Analyser" into the debate input box.
- App Reaction: The app navigates to the Command Center dashboard, opens and closes the BYOK modal smoothly, and accepts the text input in the prompt bar.

CRITICAL RULES:
- Cover the entire video from 00:00 to {self._format_time(video_duration_seconds)} without gaps.
- NO GENERIC BOILERPLATE: Every line must name the real, concrete buttons, tabs, text, and components visible in the recording.

OUTPUT FORMAT:
Output ONLY a raw JSON array of objects conforming to this schema:
[
  {{
    "scene_id": "scene_1",
    "start_time_sec": 0.0,
    "end_time_sec": 30.0,
    "action_title": "Landing Page & Debate Setup",
    "on_screen": "The landing page of Idea Lint displaying value propositions and active navigation buttons.",
    "user_action": "The user scrolls through features, clicks 'Start Your First Debate', and enters an idea pitch into the input box.",
    "app_reaction": "The app navigates to the Command Center dashboard, updates the status badge to RUNNING, and streams agent logs.",
    "readme_feature": "Relevant feature name from documentation"
  }}
]
"""

        scenes = []
        try:
            raw_response = self._call_gemini_multimodal(video_path, prompt, active_key, video_duration_seconds)
            parsed = self._extract_json(raw_response)
            if isinstance(parsed, list) and len(parsed) > 0:
                scenes = self._normalize_scenes(parsed, video_duration_seconds)
        except Exception as e:
            logger.error(f"Gemini multimodal video analysis failed: {e}. Attempting sampled frames vision analysis...")
            # Fallback to high-density FFmpeg sampled frames vision call
            try:
                raw_response = self._call_gemini_with_sampled_frames(video_path, prompt, active_key, video_duration_seconds)
                parsed = self._extract_json(raw_response)
                if isinstance(parsed, list) and len(parsed) > 0:
                    scenes = self._normalize_scenes(parsed, video_duration_seconds)
            except Exception as ex2:
                logger.error(f"Sampled frames vision call also failed: {ex2}")
                raise RuntimeError(f"Multimodal video inspection failed: {e}. Please ensure your Gemini API key has access to gemini-3.7-flash.")

        if not scenes:
            raise RuntimeError("Failed to parse visual scenes from Gemini response. Please try again.")

        # Run strict video description evaluation
        from server.evals.eval_video_description import video_description_evaluator
        eval_scorecard = video_description_evaluator.evaluate_scenes(scenes, video_path=video_path, run_vision_judge=False)

        # Self-correction loop if strict eval flags boilerplate or low specificity
        if not eval_scorecard["passed"] and eval_scorecard["overall_score"] < 80:
            logger.warning(f"Extracted scenes failed strict eval ({eval_scorecard['overall_score']}/100). Running self-refinement...")
            refine_prompt = f"""{prompt}

CRITICAL QUALITY AUDIT FEEDBACK:
Your previous scene extraction scored {eval_scorecard['overall_score']}/100 on the Strict Precision Evaluation and failed because:
{eval_scorecard['summary']}

REFINEMENT INSTRUCTIONS:
- You MUST eliminate all vague boilerplate phrasing completely.
- You MUST name the actual visual buttons clicked in brackets (e.g. [Submit Query], [Connect Wallet], [Upload File]).
- You MUST describe the actual text, forms, terminal commands, and dialogs visible on screen.
- You MUST describe the direct visual system reaction that appeared on screen.
"""
            try:
                raw_refine = self._call_gemini_multimodal(video_path, refine_prompt, active_key, video_duration_seconds)
                parsed_refine = self._extract_json(raw_refine)
                if isinstance(parsed_refine, list) and len(parsed_refine) > 0:
                    refined_scenes = self._normalize_scenes(parsed_refine, video_duration_seconds)
                    refine_eval = video_description_evaluator.evaluate_scenes(refined_scenes, video_path=video_path, run_vision_judge=False)
                    if refine_eval["overall_score"] >= eval_scorecard["overall_score"]:
                        scenes = refined_scenes
                        eval_scorecard = refine_eval
            except Exception as ref_err:
                logger.warning(f"Self-refinement loop error: {ref_err}; proceeding with best extracted scenes.")

        return scenes, eval_scorecard

    def _call_gemini_multimodal(self, video_path: str, prompt: str, api_key: str, video_duration_sec: float) -> str:
        """
        Uploads video to Google Cloud Gemini File API, waits for ACTIVE state, and analyzes with gemini-3.7-flash.
        Supports both Google Cloud Vertex AI and Google AI Studio modes.
        """
        from google.genai import types
        client = get_genai_client(api_key)

        logger.info(f"Uploading video {video_path} to Gemini File API...")
        video_file = client.files.upload(file=video_path)
        logger.info(f"Uploaded file {video_file.name}. Polling until ACTIVE...")

        # Poll for ACTIVE state
        max_wait = config.file_processing_wait_max_sec
        elapsed = 0
        while elapsed < max_wait:
            file_status = client.files.get(name=video_file.name)
            state_name = getattr(file_status.state, "name", str(file_status.state))
            logger.info(f"Gemini File state: {state_name} ({elapsed}s elapsed)")
            if state_name == "ACTIVE":
                video_file = file_status
                break
            elif state_name == "FAILED":
                raise RuntimeError(f"Gemini File API processing failed for {video_path}")
            time.sleep(3)
            elapsed += 3

        logger.info("Generating content with gemini-3.7-flash directly on video tokens (JSON forced)...")
        response = client.models.generate_content(
            model=config.vision_model,
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        # Log telemetry
        try:
            p_tok = getattr(response.usage_metadata, "prompt_token_count", 0) if hasattr(response, "usage_metadata") else 0
            c_tok = getattr(response.usage_metadata, "candidates_token_count", 0) if hasattr(response, "usage_metadata") else 0
            from server.core.pricing import calculate_llm_cost
            cost = calculate_llm_cost(config.vision_model, p_tok, c_tok)
            from server.repositories.telemetry_repository import telemetry_repository
            telemetry_repository.log_llm_call(
                session_id=os.path.basename(video_path),
                agent_name="DirectorIngestionAgent",
                model_name=config.vision_model,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=p_tok + c_tok,
                cost_usd=cost,
                latency_ms=int(elapsed * 1000)
            )
        except Exception as tel_err:
            logger.warning(f"Telemetry logging failed: {tel_err}")
        return response.text

    def _call_gemini_with_sampled_frames(self, video_path: str, prompt: str, api_key: str, duration_sec: float) -> str:
        """
        Extracts representative high-resolution frames using FFmpeg across the video
        and sends them as image parts to gemini-3.7-flash (Vertex AI / Google GenAI).
        """
        logger.info(f"Extracting sample frames from {video_path} with FFmpeg...")
        num_frames = min(12, max(5, int(duration_sec // 15)))
        step = duration_sec / (num_frames + 1)
        temp_dir = os.path.join(os.path.dirname(video_path), "temp_frames")
        os.makedirs(temp_dir, exist_ok=True)

        frame_paths = []

        try:
            for i in range(1, num_frames + 1):
                timestamp = i * step
                frame_file = os.path.join(temp_dir, f"frame_{i:02d}.jpg")
                cmd = [
                    "ffmpeg", "-y", "-ss", str(timestamp),
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    frame_file
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(frame_file):
                    frame_paths.append((timestamp, frame_file))

            from google.genai import types
            client = get_genai_client(api_key)
            uploaded_parts = []
            for ts, fp in frame_paths:
                with open(fp, "rb") as f:
                    img_bytes = f.read()
                uploaded_parts.append(f"Screen capture at {self._format_time(ts)}:")
                uploaded_parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

            uploaded_parts.append(prompt)
            logger.info(f"Calling gemini-3.7-flash with {len(frame_paths)} extracted video frames (JSON forced)...")
            resp = client.models.generate_content(
                model=config.vision_model,
                contents=uploaded_parts,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return resp.text

        finally:
            for _, fp in frame_paths:
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass

    def _normalize_scenes(self, raw_scenes: List[Dict[str, Any]], total_duration_sec: float) -> List[Dict[str, Any]]:
        """Ensures millisecond fields, monotonic timestamps, and valid boundaries."""
        normalized = []
        for idx, s in enumerate(raw_scenes):
            start_s = float(s.get("start_time_sec", idx * (total_duration_sec / len(raw_scenes))))
            end_s = float(s.get("end_time_sec", min(total_duration_sec, (idx + 1) * (total_duration_sec / len(raw_scenes)))))
            if end_s <= start_s:
                end_s = start_s + 2.0

            start_ms = int(start_s * 1000)
            end_ms = int(end_s * 1000)

            on_screen = s.get("on_screen") or s.get("screen_summary", "Detailed visual screen state")
            user_action = s.get("user_action") or s.get("user_inputs", "User interaction on screen")
            app_reaction = s.get("app_reaction") or s.get("system_response", "Application interface update")

            normalized.append({
                "scene_id": f"scene_{idx + 1}",
                "start_time_ms": start_ms,
                "end_time_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "timestamp_str": f"{self._format_time(start_s)} - {self._format_time(end_s)}",
                "action_title": s.get("action_title", f"Scene {idx + 1}"),
                "on_screen": on_screen,
                "user_action": user_action,
                "app_reaction": app_reaction,
                "screen_summary": on_screen,
                "user_inputs": user_action,
                "system_response": app_reaction,
                "readme_feature": s.get("readme_feature", "Walkthrough Documentation")
            })
        return normalized

    def _extract_json(self, text: str) -> Any:
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(cleaned)

    def _format_time(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

ingestion_agent = IngestionAgent()
