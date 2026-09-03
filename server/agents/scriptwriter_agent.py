"""
Scriptwriter Persona Agent.
Generates an engaging, natural two-host live dialogue (Alex & Sam)
bound strictly to the visual scene boundaries, featuring natural conversational
cadence, witty interjections, and technical depth.
"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional

from server.core.agent_builder import get_genai_client
from server.core.config import config

logger = logging.getLogger("castops.agent.scriptwriter")

class ScriptwriterAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.get_server_api_key()

    def generate_live_dialogue(
        self,
        scenes: List[Dict[str, Any]],
        readme_text: str,
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Creates an organic conversational technical dialogue between Alex and Sam,
        broken down scene by scene.
        """
        active_key = api_key or self.api_key or config.get_server_api_key()

        # Inject video duration into scenes for LLM context
        enhanced_scenes = []
        for s in scenes:
            s_copy = dict(s)
            s_copy["video_duration_sec"] = max(1.0, (s.get("end_time_ms", 0) - s.get("start_time_ms", 0)) / 1000.0)
            enhanced_scenes.append(s_copy)

        from server.core.guardrails import sanitize_and_inspect_text, wrap_with_isolation_boundary
        sanitized_readme = sanitize_and_inspect_text(readme_text[:4000], max_chars=4000, context_name="README.md")
        isolated_readme = wrap_with_isolation_boundary(sanitized_readme, "untrusted_documentation")

        prompt = f"""You are an elite technical podcast scriptwriter and director.
Create a lively, organic, two-character live technical walkthrough conversation between two hosts:
- **Alex (Lead Systems Architect)**: Highly knowledgeable, direct, conversational, points out technical implementation details, architecture, and performance.
- **Sam (Tech Co-host & Dev Advocate)**: Inquisitive, quick on their feet, reacts to visual UI elements in real-time, asks probing technical questions, adds natural banter.

STYLE GUIDELINES (MAKE IT FEEL LIKE A REAL LIVE CONVERSATION):
1. **Natural Dialogue Dynamics**: Hosts should react to each other, use conversational hooks ("Right!", "Check that out—", "Wait, does that mean...", "Exactly, notice how..."), finish thoughts collaboratively, and sound like colleagues having coffee.
2. **NO Synthetic Timestamps**: NEVER mention explicit timestamps or times (DO NOT SAY "at 0:14" or "in this minute"). Reference screen actions naturally ("Now as the pipeline spins up...", "Look at that latency metric...").
3. **Strict Scene Binding**: You are provided a structured list of visual scenes. You MUST assign each dialogue line to its corresponding `scene_id`.
4. **Mathematical Pacing (CRITICAL)**: Speech duration is approx 2.5 words per second (150 WPM). You MUST match the total word count of the dialogue for each scene to its `video_duration_sec`. For example, a 10.0s scene needs exactly ~25 words total. A 3.0s scene needs ~7 words.
5. **QA Auditor Feedback**: If "QA AUDITOR FEEDBACK TO FIX" is present in the README CONTEXT below, you MUST prioritize it. If it says a scene is too short, expand the dialogue word count for that scene. If it says a scene is too long, reduce the word count for that scene.

INPUT SCENES:
\"\"\"
{json.dumps(enhanced_scenes, indent=2)}
\"\"\"

README CONTEXT:
{isolated_readme}

OUTPUT SCHEMA:
Output ONLY a raw JSON object with a "dialogue" array:
{{
  "dialogue": [
    {{
      "turn_index": 0,
      "scene_id": "scene_1",
      "speaker": "Alex",
      "text": "Welcome everyone! Today we're diving into the live architecture, and right off the bat, check out how cleanly the service boots up."
    }},
    {{
      "turn_index": 1,
      "scene_id": "scene_1",
      "speaker": "Sam",
      "text": "Yeah, notice that instant health check—no waiting around for heavy container warmups."
    }}
  ]
}}
"""

        if active_key or config.vertex_ai_enabled:
            try:
                raw = self._call_llm(prompt, active_key)
                parsed = self._extract_json(raw)
                turns = parsed.get("dialogue", [])
                if turns:
                    return self._clean_and_index_turns(turns, scenes)
            except Exception as e:
                logger.error(f"Script generation LLM call failed: {e}. Generating procedural dialogue.")

        return self._generate_procedural_dialogue(scenes)

    def _call_llm(self, prompt: str, api_key: str) -> str:
        from google.genai import types
        client = get_genai_client(api_key)
        resp = client.models.generate_content(
            model=config.script_model,
            contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            p_tok = getattr(resp.usage_metadata, "prompt_token_count", 0) if hasattr(resp, "usage_metadata") else 0
            c_tok = getattr(resp.usage_metadata, "candidates_token_count", 0) if hasattr(resp, "usage_metadata") else 0
            from server.core.pricing import calculate_llm_cost
            cost = calculate_llm_cost(config.script_model, p_tok, c_tok)
            from server.repositories.telemetry_repository import telemetry_repository
            telemetry_repository.log_llm_call(
                session_id="scriptwriter",
                agent_name="ScriptwriterPersonaAgent",
                model_name=config.script_model,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=p_tok + c_tok,
                cost_usd=cost
            )
        except Exception as tel_err:
            logger.warning(f"Telemetry logging failed: {tel_err}")
        return resp.text

    def _clean_and_index_turns(self, turns: List[Dict[str, Any]], scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        valid_scene_ids = {s["scene_id"] for s in scenes}
        first_scene = scenes[0]["scene_id"] if scenes else "scene_1"

        for idx, turn in enumerate(turns):
            s_id = turn.get("scene_id")
            if s_id not in valid_scene_ids:
                s_id = scenes[idx % len(scenes)]["scene_id"] if scenes else first_scene

            speaker = "Alex" if turn.get("speaker", "").lower() in ["alex", "mark", "host a"] else "Sam"
            text = turn.get("text", "").strip()
            # Estimate speech duration: ~150 words per minute (2.5 words per second)
            word_count = len(text.split())
            estimated_duration_ms = max(1800, int((word_count / 2.5) * 1000))

            cleaned.append({
                "turn_index": idx,
                "scene_id": s_id,
                "speaker": speaker,
                "text": text,
                "audio_duration_ms": estimated_duration_ms,  # will be updated with exact PCM duration upon TTS
                "word_count": word_count
            })
        return cleaned

    def _generate_procedural_dialogue(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback natural dialogue builder if LLM is unavailable."""
        turns = []
        turn_idx = 0

        dialogue_templates = [
            ("Alex", "Welcome back! Today we're breaking down this screencast walkthrough, and starting right here on the interface."),
            ("Sam", "Look at how cleanly that loads up—everything ready to go without any lag."),
            ("Alex", "Exactly. Let's trigger this first workflow and observe the system reaction in real time."),
            ("Sam", "Notice that immediate state transition? That confirms the event loop isn't blocked."),
            ("Alex", "Right! And looking at the terminal logs on screen, the multimodal alignment engine is already parsing every frame."),
            ("Sam", "That's super crisp. It keeps the UI and the underlying timing in complete lockstep."),
            ("Alex", "Finally, here is the compiled output. Everything synchronized down to the millisecond."),
            ("Sam", "Incredible workflow. This makes complex technical demonstrations effortless to follow.")
        ]

        for s_idx, scene in enumerate(scenes):
            scene_id = scene["scene_id"]
            # 2 turns per scene
            t1 = dialogue_templates[(s_idx * 2) % len(dialogue_templates)]
            t2 = dialogue_templates[(s_idx * 2 + 1) % len(dialogue_templates)]

            for speaker, text in [t1, t2]:
                word_count = len(text.split())
                dur_ms = max(2000, int((word_count / 2.5) * 1000))
                turns.append({
                    "turn_index": turn_idx,
                    "scene_id": scene_id,
                    "speaker": speaker,
                    "text": text,
                    "audio_duration_ms": dur_ms,
                    "word_count": word_count
                })
                turn_idx += 1

        return turns

    def _extract_json(self, text: str) -> Any:
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(cleaned)

scriptwriter_agent = ScriptwriterAgent()
