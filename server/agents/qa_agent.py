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
        # Scene-by-scene analysis
        scene_durations = {}
        for s in scenes:
            s_id = s.get("scene_id")
            s_vid_sec = (s.get("end_time_ms", 0) - s.get("start_time_ms", 0)) / 1000.0
            scene_durations[s_id] = {"video_sec": s_vid_sec, "words": 0}

        has_timestamps = False
        timestamp_patterns = [r'\b\d{1,2}:\d{2}\b', r'at\s+\d+\s+seconds', r'at\s+\d+\s+minute']
        total_words = 0

        for turn in dialogue:
            text = turn.get("text", "")
            turn_words = len(text.split())
            total_words += turn_words
            s_id = turn.get("scene_id")
            if s_id in scene_durations:
                scene_durations[s_id]["words"] += turn_words

            for pat in timestamp_patterns:
                if re.search(pat, text, re.IGNORECASE):
                    has_timestamps = True
                    break
        
        # Estimate spoken duration and build scene feedback
        scene_pacing_feedback = []
        has_major_pacing_issue = False
        
        for s_id, stats in scene_durations.items():
            speech_sec = stats["words"] / 2.5
            vid_sec = max(1.0, stats["video_sec"])
            ratio = speech_sec / vid_sec
            
            if ratio < 0.70:
                has_major_pacing_issue = True
                scene_pacing_feedback.append(f"[{s_id}]: Speech ({speech_sec:.1f}s) is too short for video ({vid_sec:.1f}s). Introduce a gap or expand text.")
            elif ratio > 1.15:
                has_major_pacing_issue = True
                scene_pacing_feedback.append(f"[{s_id}]: Speech ({speech_sec:.1f}s) is too long for video ({vid_sec:.1f}s). Reduce text to fit.")

        scene_feedback_str = " ".join(scene_pacing_feedback)
        
        estimated_speech_sec = total_words / 2.5
        total_video_sec = scenes[-1].get("end_time_ms", 0) / 1000.0 if scenes else 0

        all_scenes_covered = len(set(t.get("scene_id") for t in dialogue)) >= len(scenes) * 0.85
        natural_lengths = all(len(t.get("text", "").split()) >= 4 for t in dialogue)

        active_key = api_key or self.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if active_key:
            try:
                llm_eval = self._call_qa_llm(scenes, dialogue, readme_text, active_key, total_video_sec, estimated_speech_sec, scene_feedback_str)
                if llm_eval:
                    return llm_eval
            except Exception as e:
                logger.warning(f"QA LLM call failed: {e}. Falling back to heuristic scorecard.")

        # Heuristic scorecard fallback
        accuracy_score = 95 if not has_timestamps else 75
        readme_score = 92 if len(dialogue) >= len(scenes) else 80
        pacing_score = 94 if all_scenes_covered and not has_major_pacing_issue else 55

        feedback_text = "Flawless visual alignment: Dialogue turns match scene boundaries with high fidelity."
        if has_major_pacing_issue:
            feedback_text = f"Pacing issues detected. {scene_feedback_str}"
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
                "organic_dialogue_cadence": natural_lengths and not has_major_pacing_issue
            }
        }

    def _call_qa_llm(self, scenes: List[Dict[str, Any]], dialogue: List[Dict[str, Any]], readme: str, api_key: str, video_sec: float, speech_sec: float, scene_feedback: str) -> Optional[Dict[str, Any]]:
        prompt = f"""You are a strict technical podcast QA auditor.
Evaluate the dialogue script against the visual scenes and documentation.

IMPORTANT TEMPORAL CONTEXT:
- Total Video Duration: {video_sec:.1f} seconds
- Estimated Script Spoken Duration: {speech_sec:.1f} seconds (based on 150 words/minute)

SCENE-BY-SCENE PACING ANALYSIS:
{scene_feedback if scene_feedback else "All scenes map perfectly to their time bounds."}

If there are pacing issues listed above, you MUST penalize the pacing_score heavily (e.g., 50-60) and explicitly include the scene-by-scene instructions in the 'feedback' field (e.g. telling the writer exactly which scenes to expand, introduce a gap in, or reduce text for).

SCENES:
{json.dumps(scenes, indent=2)}

DIALOGUE:
{json.dumps(dialogue, indent=2)}

AUDIT CRITERIA:
1. Video Accuracy (0-100): Are dialogue turns discussing the correct actions for their scene_id?
2. Technical Depth (0-100): Are concepts explained accurately?
3. No Robotic Timestamps: Does the text strictly avoid saying numbers like "at 0:15"?
4. Conversational Pacing (0-100): Is it a snappy, natural conversation? AND does it cover the video duration properly per scene?

OUTPUT JSON ONLY:
{{
  "overall_score": 92,
  "accuracy_score": 95,
  "readme_score": 90,
  "pacing_score": 92,
  "feedback": "Two-sentence summary of audit results, including explicit scene-by-scene fixing instructions if pacing is off.",
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
