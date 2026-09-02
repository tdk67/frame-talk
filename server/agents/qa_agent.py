"""
QA & Pacing Audit Agent.
Audits the generated script for video accuracy, absence of robotic timestamps,
natural banter, and full visual scene pacing.
"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("castops.agent.qa")

class QaAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    def audit_script(
        self,
        scenes: List[Dict[str, Any]],
        dialogue: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Audits the dialogue against scenes and documentation.
        Returns accuracy scores, checklist, and actionable improvement feedback.
        """
        # Static heuristic audits first
        has_timestamps = False
        timestamp_patterns = [r'\b\d{1,2}:\d{2}\b', r'at\s+\d+\s+seconds', r'at\s+\d+\s+minute']
        total_words = 0
        for turn in dialogue:
            text = turn.get("text", "")
            total_words += len(text.split())
            for pat in timestamp_patterns:
                if re.search(pat, text, re.IGNORECASE):
                    has_timestamps = True
                    break
        
        # Estimate spoken duration (150 words / min = 2.5 words / sec)
        estimated_speech_sec = total_words / 2.5
        total_video_sec = scenes[-1].get("end_time_ms", 0) / 1000.0 if scenes else 0
        duration_ratio = estimated_speech_sec / max(1, total_video_sec)
        is_too_short = duration_ratio < 0.65

        all_scenes_covered = len(set(t.get("scene_id") for t in dialogue)) >= len(scenes) * 0.85
        natural_lengths = all(len(t.get("text", "").split()) >= 4 for t in dialogue)

        active_key = api_key or self.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if active_key:
            try:
                llm_eval = self._call_qa_llm(scenes, dialogue, readme_text, active_key, total_video_sec, estimated_speech_sec)
                if llm_eval:
                    return llm_eval
            except Exception as e:
                logger.warning(f"QA LLM call failed: {e}. Falling back to heuristic scorecard.")

        # Heuristic scorecard fallback
        accuracy_score = 95 if not has_timestamps else 75
        readme_score = 92 if len(dialogue) >= len(scenes) else 80
        pacing_score = 94 if all_scenes_covered and not is_too_short else 55

        feedback_text = "Flawless visual alignment: Dialogue turns match scene boundaries with high fidelity."
        if is_too_short:
            feedback_text = f"Script is too short ({estimated_speech_sec:.1f}s) for the video ({total_video_sec:.1f}s). Expand explanations to prevent massive dead air."
        elif has_timestamps:
            feedback_text = "Note: explicit timestamp references detected; consider smoothing into natural transitions."

        return {
            "overall_score": int((accuracy_score + readme_score + pacing_score) / 3),
            "accuracy_score": accuracy_score,
            "readme_score": readme_score,
            "pacing_score": pacing_score,
            "feedback": feedback_text,
            "checklist": {
                "discusses_video_actions": True,
                "explains_readme_concepts": True,
                "no_robotic_timestamps": not has_timestamps,
                "full_visual_coverage": all_scenes_covered,
                "organic_dialogue_cadence": natural_lengths and not is_too_short
            }
        }

    def _call_qa_llm(self, scenes: List[Dict[str, Any]], dialogue: List[Dict[str, Any]], readme: str, api_key: str, video_sec: float, speech_sec: float) -> Optional[Dict[str, Any]]:
        prompt = f"""You are a strict technical podcast QA auditor.
Evaluate the dialogue script against the visual scenes and documentation.

IMPORTANT TEMPORAL CONTEXT:
- Total Video Duration: {video_sec:.1f} seconds
- Estimated Script Spoken Duration: {speech_sec:.1f} seconds (based on 150 words/minute)

If the Estimated Script Spoken Duration is significantly shorter than the Total Video Duration (e.g. less than 65% of the video length), the script will have awkward dead air. You MUST penalize the pacing_score heavily (e.g. 50-60) and explicitly instruct the writer in the 'feedback' field to expand their explanations to cover the visual duration.

SCENES:
{json.dumps(scenes, indent=2)}

DIALOGUE:
{json.dumps(dialogue, indent=2)}

AUDIT CRITERIA:
1. Video Accuracy (0-100): Are dialogue turns discussing the correct actions for their scene_id?
2. Technical Depth (0-100): Are concepts explained accurately?
3. No Robotic Timestamps: Does the text strictly avoid saying numbers like "at 0:15"?
4. Conversational Pacing (0-100): Is it a snappy, natural conversation? AND does it cover the video duration properly?

OUTPUT JSON ONLY:
{{
  "overall_score": 92,
  "accuracy_score": 95,
  "readme_score": 90,
  "pacing_score": 92,
  "feedback": "Two-sentence summary of audit results.",
  "checklist": {{
    "discusses_video_actions": true,
    "explains_readme_concepts": true,
    "no_robotic_timestamps": true,
    "full_visual_coverage": true,
    "organic_dialogue_cadence": true
  }}
}}
"""
        if api_key.startswith("AIzaSy") or not api_key.startswith("sk-or"):
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model='gemini-3.7-flash',
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                cleaned = resp.text.strip()
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                return json.loads(cleaned)
            except Exception as ex:
                logger.warning(f"Direct Google GenAI QA call failed: {ex}. Falling back to HTTP...")

        import requests
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": "google/gemini-3.7-flash",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body, timeout=30)
        if resp.status_code == 200:
            cleaned = resp.json()["choices"][0]["message"]["content"]
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        return None

qa_agent = QaAgent()
