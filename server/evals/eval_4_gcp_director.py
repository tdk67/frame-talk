"""
Stage 4 Evaluation: Google Cloud ADK Director Agent vs Ground Truth Screencast
Validates that FrameTalk_Director (defined in agent.py) correctly coordinates
the Scriptwriter and QA sub-agents on real silent screencast scenes and documentation.
"""

import sys
import os
import json
import re
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET_DIR = PROJECT_ROOT / "evals" / "dataset"
EXPECTED_SCENES_PATH = DATASET_DIR / "expected_scenes.json"
SAMPLE_README_PATH = DATASET_DIR / "sample_readme.md"

class GcpDirectorEvaluator:
    def __init__(self):
        with open(EXPECTED_SCENES_PATH, "r", encoding="utf-8") as f:
            self.expected_scenes = json.load(f)
        with open(SAMPLE_README_PATH, "r", encoding="utf-8") as f:
            self.readme_text = f.read()

    def evaluate(self, num_scenes: int = 2) -> dict:
        """Runs the Google Cloud ADK Director Agent on silent screencast scenes."""
        test_scenes = self.expected_scenes[:num_scenes]

        scenes_summary = []
        for s in test_scenes:
            scenes_summary.append(
                f"- Scene {s['scene_id']} ({s['timestamp_str']}, duration: {s['end_time_ms'] - s['start_time_ms']}ms): "
                f"Visuals: {s['on_screen']} | User Action: {s['user_action']} | Key Entities: {', '.join(s['key_entities'][:4])}"
            )
        scenes_block = "\n".join(scenes_summary)

        prompt = (
            f"Here are {len(test_scenes)} visual scenes extracted from a silent developer screencast:\n"
            f"{scenes_block}\n\n"
            f"<untrusted_documentation>\n{self.readme_text[:600]}\n</untrusted_documentation>\n\n"
            f"Task for FrameTalk_Director:\n"
            f"1. Delegate dialogue generation to the Scriptwriter-Persona-Agent for each scene between Alex and Sam.\n"
            f"2. Enforce strict pacing (~2.5 words/sec) and zero artificial timestamps.\n"
            f"3. Calculate the Chronos dynamic visual hold (freeze-frame) for any scene where speech duration exceeds scene duration.\n"
            f"Provide the finalized podcast dialogue and Chronos sync hold summary."
        )

        print(f"Executing Google Cloud ADK Director Agent via ADK Runtime with {len(test_scenes)} scenes...")
        
        proc = subprocess.run(
            [sys.executable, "-m", "google.adk.cli", "run", ".", prompt],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=90
        )

        text = proc.stdout + proc.stderr

        # 1. Anti-timestamp violation check on spoken dialogue
        timestamp_pattern = re.compile(r'\b(?:at|around|timestamp)\s+\d{1,2}:\d{2}\b', re.IGNORECASE)
        dialogue_lines = re.findall(r'(?:Alex|Sam|Mark|Sarah):\s*"([^"]+)"', text)
        if not dialogue_lines:
            dialogue_lines = re.findall(r'"([^"]{15,})"', text)
        
        timestamp_violations = []
        for d in dialogue_lines:
            violations = timestamp_pattern.findall(d)
            if violations:
                timestamp_violations.extend(violations)
        anti_timestamp_passed = len(timestamp_violations) == 0

        # 2. Key entity grounding (Idea Lint, BYOK, Alex, Sam)
        entities_found = [e for e in ["Idea Lint", "BYOK", "Alex", "Sam", "Debate"] if e.lower() in text.lower()]
        entity_grounding_score = int((len(entities_found) / 5.0) * 100)

        # 3. Dynamic freeze hold calculation check
        has_freeze_calc = any(kw in text.lower() for kw in ["hold", "freeze", "duration", "pacing", "ms", "seconds"])

        # 4. Successful Agent execution check
        agent_executed = "[FrameTalk_Director]:" in text or "Session ID:" in text

        overall_score = 0
        if agent_executed:
            overall_score += 20
        if anti_timestamp_passed:
            overall_score += 30
        overall_score += int(entity_grounding_score * 0.3)
        if has_freeze_calc:
            overall_score += 20

        passed = overall_score >= 80

        # Extract only the response section for preview
        preview_match = re.search(r'\[FrameTalk_Director\]:(.*)', text, re.DOTALL)
        preview_text = preview_match.group(1).strip() if preview_match else text

        return {
            "passed": passed,
            "overall_score": overall_score,
            "agent_executed": agent_executed,
            "anti_timestamp_passed": anti_timestamp_passed,
            "timestamp_violations_count": len(timestamp_violations),
            "entity_grounding_score": entity_grounding_score,
            "entities_found": entities_found,
            "has_freeze_calc": has_freeze_calc,
            "output_preview": preview_text[:600] + ("..." if len(preview_text) > 600 else "")
        }

if __name__ == "__main__":
    print("=" * 70)
    print("  STAGE 4: GOOGLE CLOUD ADK DIRECTOR AGENT EVALUATION")
    print("=" * 70)
    evaluator = GcpDirectorEvaluator()
    res = evaluator.evaluate(num_scenes=2)
    print(f"Status:                      [{'PASSED' if res['passed'] else 'FAILED'}]")
    print(f"Overall Director Score:      {res['overall_score']} / 100 (Threshold: 80)")
    print(f"ADK Agent Execution:         {'VERIFIED' if res['agent_executed'] else 'FAILED'}")
    print(f"Anti-Timestamp Constraint:   {'PASSED (0 violations)' if res['anti_timestamp_passed'] else 'FAILED'}")
    print(f"Visual Entity Grounding:     {res['entity_grounding_score']}% ({', '.join(res['entities_found'])})")
    print(f"Chronos Hold Calculation:    {'VERIFIED' if res['has_freeze_calc'] else 'MISSING'}")
    print("-" * 70)
    print(f"Output Preview:\n{res['output_preview']}")
    print("=" * 70)
