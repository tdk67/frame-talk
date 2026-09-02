"""
Stage 3 Evaluation: QA Auditor Evaluation
Evaluates the QA Auditor agent itself to verify it accurately detects quality dialogue
and catches defects/hallucinations (defect injection sensitivity test).
"""

import os
import sys
import json
import copy
import argparse
from typing import Dict, Any
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.agents.qa_agent import qa_agent

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

class QaAuditorEvaluator:
    def __init__(
        self,
        scenes_path: Path = EXPECTED_SCENES_PATH,
        dialogue_path: Path = EXPECTED_DIALOGUE_PATH,
        readme_path: Path = SAMPLE_README_PATH
    ):
        with open(scenes_path, "r", encoding="utf-8") as f:
            self.scenes = json.load(f)
        with open(dialogue_path, "r", encoding="utf-8") as f:
            self.dialogue = json.load(f)
        with open(readme_path, "r", encoding="utf-8") as f:
            self.readme = f.read()

    def evaluate(self, api_key: str = None) -> Dict[str, Any]:
        """
        Runs two evaluation batteries against the QA Auditor:
        1. Positive Benchmark: Evaluates high-quality gold standard dialogue.
        2. Defect Injection Benchmark: Injects explicit timestamps and hallucinations,
           verifying that the QA Auditor catches them.
        """
        # Battery 1: Positive Test
        pos_audit = qa_agent.audit_script(
            scenes=self.scenes,
            dialogue=self.dialogue,
            readme_text=self.readme,
            api_key=api_key
        )
        pos_passed = pos_audit.get("overall_score", 0) >= 80

        # Battery 2: Defect Injection (Robotic Timestamp & Hallucination)
        flawed_dialogue = copy.deepcopy(self.dialogue)
        flawed_dialogue[0]["text"] = "At 0:15 in the video, we can see the app starting."
        flawed_dialogue[1]["text"] = "Yes, and at timestamp 0:45 let's order some pizza and talk about outer space."

        neg_audit = qa_agent.audit_script(
            scenes=self.scenes,
            dialogue=flawed_dialogue,
            readme_text=self.readme,
            api_key=api_key
        )

        # The QA auditor should report lower score or catch timestamp violation
        caught_timestamp = not neg_audit.get("checklist", {}).get("no_robotic_timestamps", True) or (neg_audit.get("overall_score", 100) < pos_audit.get("overall_score", 100))
        caught_defect = caught_timestamp or (neg_audit.get("accuracy_score", 100) < pos_audit.get("accuracy_score", 100))

        stage_passed = pos_passed and caught_defect

        score = 100.0
        if not pos_passed: score -= 50.0
        if not caught_defect: score -= 50.0

        return {
            "stage": "Stage 3: QA Auditor Evaluation",
            "passed": stage_passed,
            "overall_score": int(score),
            "positive_benchmark": {
                "overall_score": pos_audit.get("overall_score"),
                "accuracy_score": pos_audit.get("accuracy_score"),
                "readme_score": pos_audit.get("readme_score"),
                "pacing_score": pos_audit.get("pacing_score"),
                "feedback": pos_audit.get("feedback"),
                "checklist": pos_audit.get("checklist"),
                "passed": pos_passed
            },
            "defect_injection_benchmark": {
                "injected_defects": ["Explicit robotic timestamp 'At 0:15'", "Off-topic pizza hallucination"],
                "caught_defect": caught_defect,
                "reported_overall_score": neg_audit.get("overall_score"),
                "reported_accuracy_score": neg_audit.get("accuracy_score"),
                "feedback": neg_audit.get("feedback"),
                "checklist": neg_audit.get("checklist")
            }
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 3: QA Auditor Sensitivity & Robustness Evaluation")
    parser.add_argument("--api-key", type=str, default=None, help="Optional Gemini API key")
    parser.add_argument("--live", action="store_true", help="Call real Gemini 3.7 Flash LLM judge with .env key")
    args = parser.parse_args()

    active_key = args.api_key
    if args.live and not active_key:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
        active_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not active_key:
            raise RuntimeError("No API key found in .env. Please configure GOOGLE_API_KEY.")

    evaluator = QaAuditorEvaluator()

    mode_title = "Live Gemini 3.7 Flash LLM-as-a-Judge" if active_key else "Heuristic Verification Mode"
    print("=" * 72)
    print("  EVAL 3: QA AUDITOR DISCRIMINATION & SENSITIVITY EVALUATION")
    print(f"  Execution Mode: {mode_title}")
    print("  Batteries: Positive Benchmark + Defect Injection Sensitivity Test")
    print("=" * 72)

    if active_key:
        print("Calling real Gemini 3.7 Flash to audit both benchmark scripts...")

    res = evaluator.evaluate(api_key=active_key)
    status_str = "PASSED" if res["passed"] else "FAILED"

    print(f"\nStatus:                       [{status_str}]")
    print(f"QA Auditor Integrity Score:   {res['overall_score']} / 100")

    print("\n--- Battery 1: Positive Benchmark (Gold-Standard Dialogue) ---")
    pos = res["positive_benchmark"]
    print(f"  Overall Score:              {pos['overall_score']}/100 (Passed: {pos['passed']})")
    print(f"  Video Accuracy Score:       {pos['accuracy_score']}/100")
    print(f"  README Alignment Score:     {pos['readme_score']}/100")
    print(f"  Conversational Pacing:      {pos['pacing_score']}/100")
    if pos.get("feedback"):
        print(f"  AI Judge Feedback:          \"{pos['feedback']}\"")
    print(f"  Checklist Passed:           {all(pos['checklist'].values()) if pos['checklist'] else 'N/A'}")

    print("\n--- Battery 2: Defect Injection Benchmark (Flawed Dialogue) ---")
    neg = res["defect_injection_benchmark"]
    print(f"  Injected:                   {', '.join(neg['injected_defects'])}")
    print(f"  Defect Detected by QA:      {neg['caught_defect']}")
    print(f"  Penalized Overall Score:    {neg['reported_overall_score']}/100")
    print(f"  Penalized Accuracy Score:   {neg['reported_accuracy_score']}/100")
    if neg.get("feedback"):
        print(f"  AI Judge Critique:          \"{neg['feedback']}\"")
    print("=" * 72)
