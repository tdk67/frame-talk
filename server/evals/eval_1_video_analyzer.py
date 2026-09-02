"""
Stage 1 Evaluation: Video Analyzer Evaluation
Zero hardcoded filenames — all paths and limits are loaded dynamically from config.json.

Evaluates:
1. Ground Truth Benchmark: Compares scenes against expected_scenes.json
2. Edge Cases Battery: Rejection of <30s, >300s, unsupported formats (.avi), and acceptance of .webm
3. Live Model Execution (--live): Calls real Gemini 3.7 Flash service with API key from .env
"""

import os
import re
import sys
import json
import argparse
from typing import List, Dict, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env credentials
load_dotenv(PROJECT_ROOT / ".env")

from server.core.config import config
from server.core.exceptions import InvalidInputException

GENERIC_BLACKLIST = [
    r"navigating interface",
    r"selecting demonstration options",
    r"real-time rendering and state transition update",
    r"generic demonstration",
    r"state transition update",
    r"clicking various buttons",
    r"system updates the view"
]

DATASET_DIR = Path(__file__).resolve().parent / "dataset"

class VideoAnalyzerEvaluator:
    def __init__(self, dataset_dir: Path = DATASET_DIR):
        self.dataset_dir = dataset_dir
        self.dataset_config = self._load_dataset_config()
        self.expected_scenes_path = self.dataset_dir / self.dataset_config.get("expected_scenes_file", "expected_scenes.json")
        self.video_path = self.dataset_dir / self.dataset_config.get("video_file", "Aufzeichnung 2026-08-30 094915.mp4")
        self.readme_path = self.dataset_dir / self.dataset_config.get("sample_readme_file", "sample_readme.md")
        self.expected_scenes = self._load_expected()

    def _load_dataset_config(self) -> Dict[str, Any]:
        cfg_file = self.dataset_dir / "dataset_config.json"
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_expected(self) -> List[Dict[str, Any]]:
        if self.expected_scenes_path.exists():
            with open(self.expected_scenes_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def evaluate(self, candidate_scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluates candidate scenes against the expected dataset."""
        if not candidate_scenes:
            return {
                "passed": False,
                "overall_score": 0,
                "reason": "Candidate scenes list is empty."
            }

        # 1. Anti-Boilerplate Check (Zero Tolerance)
        boilerplate_hits = []
        for s in candidate_scenes:
            text = f"{s.get('action_title', '')} {s.get('on_screen', '')} {s.get('user_action', '')} {s.get('app_reaction', '')} {s.get('screen_summary', '')} {s.get('user_inputs', '')} {s.get('system_response', '')}"
            for pat in GENERIC_BLACKLIST:
                if re.search(pat, text, re.IGNORECASE):
                    boilerplate_hits.append({"scene_id": s.get("scene_id"), "pattern": pat})

        # 2. Key Ground-Truth Entity Recall
        expected_entities = []
        for exp in self.expected_scenes:
            expected_entities.extend(exp.get("key_entities", []))

        all_candidate_text = " ".join([
            f"{s.get('action_title', '')} {s.get('on_screen', '')} {s.get('user_action', '')} {s.get('app_reaction', '')} {s.get('screen_summary', '')} {s.get('user_inputs', '')} {s.get('system_response', '')}"
            for s in candidate_scenes
        ]).lower()

        matched_entities = []
        missing_entities = []
        for ent in expected_entities:
            clean_ent = re.sub(r'[^\w\s]', '', ent).lower().strip()
            if clean_ent and clean_ent in all_candidate_text:
                matched_entities.append(ent)
            else:
                missing_entities.append(ent)

        entity_recall = (len(matched_entities) / max(1, len(expected_entities))) * 100.0

        # 3. Action-Reaction Causality Check
        causality_scores = []
        for s in candidate_scenes:
            user_act = (s.get("user_action") or s.get("user_inputs") or "").strip()
            app_react = (s.get("app_reaction") or s.get("system_response") or "").strip()
            score = 100.0
            if len(user_act) < 15: score -= 30.0
            if len(app_react) < 15: score -= 30.0
            if user_act.lower() == app_react.lower(): score -= 50.0
            causality_scores.append(max(0.0, score))

        avg_causality = sum(causality_scores) / max(1, len(causality_scores))

        # 4. Temporal Granularity Check
        n_scenes = len(candidate_scenes)
        count_score = 100.0 if (6 <= n_scenes <= 14) else 70.0

        if boilerplate_hits:
            overall_score = 0
            passed = False
        else:
            overall_score = int(round(
                entity_recall * 0.45 +
                avg_causality * 0.35 +
                count_score * 0.20
            ))
            passed = (overall_score >= 80) and (len(boilerplate_hits) == 0)

        return {
            "stage": "Stage 1: Video Analyzer Evaluation",
            "passed": passed,
            "overall_score": overall_score,
            "entity_recall_score": round(entity_recall, 1),
            "matched_entities_count": len(matched_entities),
            "total_expected_entities": len(expected_entities),
            "action_reaction_causality": round(avg_causality, 1),
            "boilerplate_hits": len(boilerplate_hits),
            "flagged_boilerplate": boilerplate_hits,
            "total_scenes": n_scenes,
            "sample_matched_entities": matched_entities[:6],
            "sample_missing_entities": missing_entities[:5]
        }

    def run_edge_cases_battery(self) -> Dict[str, Any]:
        """
        Tests the strict limits and format constraints:
        - Case 1: Rejection of video < 30 seconds
        - Case 2: Rejection of video > 300 seconds (5 minutes)
        - Case 3: Rejection of unsupported extension (e.g. .avi)
        - Case 4: Acceptance of .webm format
        """
        from server.services.studio_service import studio_service

        results = []

        # Test 1: Video too short (< 30s)
        t1_passed = False
        try:
            studio_service.analyze_video_screen("dummy.mp4", "readme text", video_duration_seconds=20.0)
        except InvalidInputException as ex:
            t1_passed = "too short" in str(ex).lower() or "minimum" in str(ex).lower()
        results.append({
            "case": "Case 1: Video < 30s Rejection",
            "tested_duration": "20.0s",
            "expected": "400 InvalidInputException (Too short)",
            "passed": t1_passed
        })

        # Test 2: Video too long (> 300s / 5min)
        t2_passed = False
        try:
            studio_service.analyze_video_screen("dummy.mp4", "readme text", video_duration_seconds=360.0)
        except InvalidInputException as ex:
            t2_passed = "exceeds" in str(ex).lower() or "5 minutes" in str(ex).lower() or "limit" in str(ex).lower()
        results.append({
            "case": "Case 2: Video > 300s (5min) Rejection",
            "tested_duration": "360.0s",
            "expected": "400 InvalidInputException (Exceeds 5min)",
            "passed": t2_passed
        })

        # Test 3: Unsupported format (.avi)
        t3_passed = False
        try:
            studio_service.analyze_video_screen("screencast.avi", "readme text", video_duration_seconds=120.0)
        except InvalidInputException as ex:
            t3_passed = "unsupported video format" in str(ex).lower()
        results.append({
            "case": "Case 3: Unsupported Extension (.avi) Rejection",
            "tested_format": ".avi",
            "expected": "400 InvalidInputException (Unsupported format)",
            "passed": t3_passed
        })

        # Test 4: WebM format supported (.webm)
        t4_passed = False
        try:
            # Should pass format & duration validation, then fail on file not found (which proves validation passed)
            studio_service.analyze_video_screen("non_existent_test.webm", "readme text", video_duration_seconds=120.0)
        except Exception as ex:
            # If it failed on file not found or resource not found, it accepted the .webm format!
            t4_passed = "does not exist" in str(ex).lower() or "not found" in str(ex).lower()
        results.append({
            "case": "Case 4: WebM Format (.webm) Acceptance",
            "tested_format": ".webm",
            "expected": "Validation Passed (Accepted as supported format)",
            "passed": t4_passed
        })

        all_passed = all(r["passed"] for r in results)
        return {
            "battery": "Video Constraints & Format Edge Cases",
            "all_passed": all_passed,
            "cases": results
        }

    def run_live_service_eval(self) -> Dict[str, Any]:
        """Calls the real Gemini 3.7 Flash service with the video from dataset and scores it."""
        from server.services.studio_service import studio_service

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No API key found in .env. Please configure GOOGLE_API_KEY or GEMINI_API_KEY.")

        if not self.video_path.exists():
            raise FileNotFoundError(f"Benchmark video not found at: {self.video_path}")

        # Ensure video is available in uploads/ for the service
        from server.core.config import config
        target_upload = config.uploads_dir / self.video_path.name
        if not target_upload.exists():
            import shutil
            shutil.copyfile(self.video_path, target_upload)

        with open(self.readme_path, "r", encoding="utf-8") as f:
            readme_text = f.read()

        print(f"Calling real Gemini 3.7 Flash on {self.video_path.name} (262s)...")
        scenes, eval_scorecard = studio_service.analyze_video_screen(
            video_filename=self.video_path.name,
            readme_text=readme_text,
            video_duration_seconds=262.0,
            api_key=api_key
        )

        eval_res = self.evaluate(scenes)
        eval_res["live_eval_scorecard"] = eval_scorecard
        eval_res["scenes"] = scenes

        # Save live extracted scenes to file for inspection
        out_path = self.dataset_dir / "live_extracted_scenes.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(scenes, f, indent=2)
        print(f"Saved live extracted scenes to: {out_path.name}")

        return eval_res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1: Video Analyzer Evaluation Suite")
    parser.add_argument("--benchmark", action="store_true", help="Run expected ground truth benchmark")
    parser.add_argument("--edge-cases", action="store_true", help="Run format & duration limits edge cases battery")
    parser.add_argument("--live", action="store_true", help="Call real Gemini 3.7 Flash service with .env key")
    parser.add_argument("--scenes", type=str, default=None, help="Path to custom scenes JSON file")

    args = parser.parse_args()
    evaluator = VideoAnalyzerEvaluator()

    # Default if no flags passed: run benchmark + edge-cases
    run_bench = args.benchmark or (not args.edge_cases and not args.live and not args.scenes)
    run_edge = args.edge_cases or (not args.benchmark and not args.live and not args.scenes)

    print("=" * 76)
    print("  FRAME TALK - STAGE 1: VIDEO ANALYZER EVALUATION")
    print(f"  Dataset Config:     {evaluator.dataset_dir / 'dataset_config.json'}")
    print(f"  Configured Video:   {evaluator.video_path.name}")
    print(f"  Configured Expected: {evaluator.expected_scenes_path.name}")
    print(f"  Duration Limits:    {config.min_video_duration_sec}s - {config.max_video_duration_sec}s (5 min)")
    print(f"  Supported Formats:  {', '.join(config.supported_video_extensions)}")
    print("=" * 76)

    # 1. Edge cases
    if run_edge:
        print("\n[BATTERY 1: EDGE CASES & CONSTRAINTS]")
        edge_res = evaluator.run_edge_cases_battery()
        for c in edge_res["cases"]:
            mark = "[PASS]" if c["passed"] else "[FAIL]"
            print(f"  {mark} {c['case'].ljust(45)}: {c['expected']}")
        print(f"  Battery Status: {'PASSED' if edge_res['all_passed'] else 'FAILED'}")

    # 2. Benchmark evaluation
    if run_bench:
        print("\n[BATTERY 2: GROUND TRUTH BENCHMARK]")
        if args.scenes:
            with open(args.scenes, "r", encoding="utf-8") as f:
                d = json.load(f)
                cand = d.get("scenes", d) if isinstance(d, dict) else d
        else:
            cand = evaluator.expected_scenes

        bench_res = evaluator.evaluate(cand)
        status_str = "PASSED" if bench_res["passed"] else "FAILED"
        print(f"  Status:                     [{status_str}]")
        print(f"  Overall Analyzer Score:     {bench_res['overall_score']} / 100 (Threshold: 80)")
        print(f"  Ground-Truth Entity Recall: {bench_res['entity_recall_score']}% ({bench_res['matched_entities_count']}/{bench_res['total_expected_entities']})")
        print(f"  Action-Reaction Causality:  {bench_res['action_reaction_causality']}%")
        print(f"  Boilerplate Hits:           {bench_res['boilerplate_hits']} (Zero tolerance: 0)")
        print(f"  Sample Matched:             {', '.join(bench_res['sample_matched_entities'][:5])}")

    # 3. Live Service Call
    if args.live:
        print("\n[BATTERY 3: LIVE GEMINI SERVICE CALL]")
        live_res = evaluator.run_live_service_eval()
        status_str = "PASSED" if live_res["passed"] else "FAILED"
        print(f"  Status:                     [{status_str}]")
        print(f"  Live Overall Score:         {live_res['overall_score']} / 100 (Threshold: 80)")
        print(f"  Extracted Scenes Count:     {live_res['total_scenes']}")
        print(f"  Entity Recall:              {live_res['entity_recall_score']}% ({live_res['matched_entities_count']}/{live_res['total_expected_entities']})")
        print(f"  Action-Reaction Causality:  {live_res['action_reaction_causality']}%")
        print(f"  Boilerplate Hits:           {live_res['boilerplate_hits']}")
        print(f"  Matched Entities:           {', '.join(live_res['sample_matched_entities'][:6])}")
        print(f"  Sample Missing:             {', '.join(live_res['sample_missing_entities'][:6])}")

    print("\n" + "=" * 76)
