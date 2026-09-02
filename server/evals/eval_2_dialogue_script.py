"""
Stage 2 Evaluation: Dialogue Script Generation Evaluator
Evaluates the dialogue script generated from visual scenes and README documentation.
Checks:
- Visual Scene Anchoring: Dialogue turns align with scene events
- Documentation Grounding: Explains key concepts from the README
- Anti-Timestamp Constraint: Zero robotic timestamp utterances (e.g. 'at 0:15')
- Conversational Cadence: Fast-paced turn-taking between Mark and Sarah
"""

import os
import sys
import re
import json
import argparse
from typing import List, Dict, Any
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
if not DATASET_DIR.exists():
    DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "evals" / "dataset"

def _get_dataset_config(d_dir: Path) -> Dict[str, Any]:
    cfg = d_dir / "dataset_config.json"
    if cfg.exists():
        with open(cfg, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

_cfg = _get_dataset_config(DATASET_DIR)
EXPECTED_SCENES_PATH = DATASET_DIR / _cfg.get("expected_scenes_file", "expected_scenes.json")
EXPECTED_DIALOGUE_PATH = DATASET_DIR / _cfg.get("expected_dialogue_file", "expected_dialogue.json")
SAMPLE_README_PATH = DATASET_DIR / _cfg.get("sample_readme_file", "sample_readme.md")

TIMESTAMP_REGEX = re.compile(r'\b(\d{1,2}:\d{2}|at \d+ (seconds?|minutes?)|timestamp \d+)\b', re.IGNORECASE)

REQUIRED_README_CONCEPTS = [
    "courtroom", "adversarial", "byok", "privacy", "stateless",
    "researcher", "advocate", "critic", "judge", "prd", "decision gate"
]

class DialogueScriptEvaluator:
    def __init__(
        self,
        expected_scenes_path: Path = EXPECTED_SCENES_PATH,
        expected_dialogue_path: Path = EXPECTED_DIALOGUE_PATH,
        readme_path: Path = SAMPLE_README_PATH
    ):
        self.expected_scenes = self._load_json(expected_scenes_path)
        self.expected_dialogue = self._load_json(expected_dialogue_path)
        self.readme_text = self._load_text(readme_path)

    def _load_json(self, path: Path) -> List[Dict[str, Any]]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_text(self, path: Path) -> str:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def evaluate(
        self,
        dialogue: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]] = None,
        readme: str = ""
    ) -> Dict[str, Any]:
        """Evaluates a dialogue script across the 4 key dialogue pillars."""
        if not dialogue:
            return {"passed": False, "overall_score": 0, "reason": "Dialogue script is empty."}

        scenes_map = {s["scene_id"]: s for s in (scenes or self.expected_scenes)}
        full_dialogue_text = " ".join([t.get("text", "") for t in dialogue])

        # 1. Anti-Timestamp Constraint (100% Strict Pass)
        timestamp_violations = []
        for idx, turn in enumerate(dialogue):
            text = turn.get("text", "")
            matches = TIMESTAMP_REGEX.findall(text)
            if matches:
                timestamp_violations.append({
                    "turn_index": idx,
                    "speaker": turn.get("speaker"),
                    "matched": [m[0] if isinstance(m, tuple) else m for m in matches],
                    "text": text
                })

        timestamp_score = 100.0 if not timestamp_violations else 0.0

        # 2. Conversational Dynamics & Persona Distribution
        speakers = [t.get("speaker", "Alex") for t in dialogue]
        mark_turns = sum(1 for s in speakers if s.lower() in ("mark", "alex"))
        sarah_turns = sum(1 for s in speakers if s.lower() in ("sarah", "sam"))
        total_turns = len(dialogue)

        # Measure alternation (consecutive speaker repeats)
        consecutive_same = 0
        for i in range(1, len(speakers)):
            if speakers[i] == speakers[i - 1]:
                consecutive_same += 1

        alternation_ratio = 1.0 - (consecutive_same / max(1, total_turns - 1))
        balance_ratio = min(mark_turns, sarah_turns) / max(1, max(mark_turns, sarah_turns))
        cadence_score = min(100.0, (alternation_ratio * 60.0 + balance_ratio * 40.0))

        # 3. Documentation Concept Coverage
        readme_lower = (readme or self.readme_text).lower()
        dialogue_lower = full_dialogue_text.lower()
        matched_concepts = []
        missing_concepts = []
        for concept in REQUIRED_README_CONCEPTS:
            if concept in dialogue_lower:
                matched_concepts.append(concept)
            else:
                missing_concepts.append(concept)

        readme_coverage_score = (len(matched_concepts) / len(REQUIRED_README_CONCEPTS)) * 100.0

        # 4. Visual Scene Anchoring
        scene_anchoring_scores = []
        for turn in dialogue:
            s_id = turn.get("scene_id")
            scene_data = scenes_map.get(s_id, {})
            scene_text = f"{scene_data.get('action_title', '')} {scene_data.get('on_screen', '')} {scene_data.get('user_action', '')} {scene_data.get('app_reaction', '')}".lower()
            
            turn_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', turn.get("text", "").lower()))
            overlap = [w for w in turn_words if w in scene_text]
            # A turn should share topical words with its scene
            score = 100.0 if len(overlap) >= 2 else (len(overlap) / 2.0) * 100.0
            scene_anchoring_scores.append(score)

        avg_anchoring = sum(scene_anchoring_scores) / max(1, len(scene_anchoring_scores))

        # Overall Weighted Score
        if timestamp_violations:
            overall_score = min(50, int(avg_anchoring * 0.4 + readme_coverage_score * 0.3))
            passed = False
        else:
            overall_score = int(round(
                avg_anchoring * 0.35 +
                readme_coverage_score * 0.30 +
                cadence_score * 0.20 +
                timestamp_score * 0.15
            ))
            passed = (overall_score >= 80) and (len(timestamp_violations) == 0)

        return {
            "stage": "Stage 2: Dialogue Script Evaluation",
            "passed": passed,
            "overall_score": overall_score,
            "visual_anchoring_score": round(avg_anchoring, 1),
            "readme_coverage_score": round(readme_coverage_score, 1),
            "conversational_cadence_score": round(cadence_score, 1),
            "anti_timestamp_score": round(timestamp_score, 1),
            "timestamp_violations_count": len(timestamp_violations),
            "timestamp_violations": timestamp_violations,
            "total_turns": total_turns,
            "turn_distribution": f"Mark: {mark_turns} | Sarah: {sarah_turns}",
            "matched_concepts": matched_concepts,
            "missing_concepts": missing_concepts
        }

    def run_live_service_eval(self) -> Dict[str, Any]:
        """Calls real Gemini 3.7 Flash to generate dialogue from dataset scenes & README, then evaluates it."""
        import os
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No API key found in .env. Please configure GOOGLE_API_KEY or GEMINI_API_KEY.")

        from server.services.studio_service import studio_service

        print(f"Calling real Gemini 3.7 Flash to generate script from {len(self.expected_scenes)} scenes...")
        dialogue = studio_service.generate_dialogue_script(
            scenes=self.expected_scenes,
            readme_text=self.readme_text,
            api_key=api_key
        )

        out_path = DATASET_DIR / "live_generated_dialogue.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dialogue, f, indent=2)
        print(f"Saved live generated dialogue to: {out_path.name} ({len(dialogue)} turns)")

        eval_res = self.evaluate(dialogue)
        eval_res["dialogue"] = dialogue
        return eval_res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 2: Dialogue Script Generation Evaluator")
    parser.add_argument("--dialogue", type=str, default=None, help="Path to candidate dialogue JSON file")
    parser.add_argument("--benchmark", action="store_true", help="Evaluate predefined gold standard dialogue")
    parser.add_argument("--live", action="store_true", help="Call real Gemini 3.7 Flash to generate dialogue and evaluate it")
    args = parser.parse_args()

    evaluator = DialogueScriptEvaluator()

    if args.live:
        print("=" * 72)
        print("  EVAL 2: LIVE GEMINI SCRIPT GENERATION & EVALUATION")
        print("  Model: Gemini 3.7 Flash")
        print("=" * 72)
        res = evaluator.run_live_service_eval()
        title = "Live Gemini 3.7 Flash Generated Script"
        total_turns = len(res["dialogue"])
    elif args.dialogue and os.path.exists(args.dialogue):
        with open(args.dialogue, "r", encoding="utf-8") as f:
            data = json.load(f)
            cand = data.get("dialogue", data) if isinstance(data, dict) else data
        title = f"Candidate File: {args.dialogue}"
        total_turns = len(cand)
        res = evaluator.evaluate(cand)
    else:
        cand = evaluator.expected_dialogue
        title = "Predefined Gold Standard Dialogue Benchmark"
        total_turns = len(cand)
        res = evaluator.evaluate(cand)

    print("=" * 72)
    print(f"  Target: {title}")
    print(f"  Total Turns: {total_turns}")
    print("=" * 72)

    status_str = "PASSED" if res["passed"] else "FAILED"
    print(f"\nStatus:                       [{status_str}]")
    print(f"Overall Dialogue Score:       {res['overall_score']} / 100 (Threshold: 80)")
    print(f"Visual Scene Anchoring:       {res['visual_anchoring_score']}%")
    print(f"README Concepts Grounding:    {res['readme_coverage_score']}% ({len(res['matched_concepts'])}/{len(REQUIRED_README_CONCEPTS)} concepts)")
    print(f"Conversational Cadence:       {res['conversational_cadence_score']}% ({res['turn_distribution']})")
    print(f"Anti-Timestamp Constraint:    {res['anti_timestamp_score']}% ({res['timestamp_violations_count']} violations)")
    print(f"Matched Concepts:             {', '.join(res['matched_concepts'][:6])}")
    if res['missing_concepts']:
        print(f"Missing Concepts:             {', '.join(res['missing_concepts'][:4])}")
    print("=" * 72)
