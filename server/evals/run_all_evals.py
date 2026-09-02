"""
Master Evaluation Suite Runner for Frame Talk
Executes decoupled multi-stage evaluations:
  Stage 1: Video Analyzer vs Predefined Ground Truth Dataset
  Stage 2: Dialogue Script Generation vs Visuals & Documentation
  Stage 3: QA & Pacing Auditor Discrimination & Sensitivity
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path so it runs from any directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.evals.eval_1_video_analyzer import VideoAnalyzerEvaluator
from server.evals.eval_2_dialogue_script import DialogueScriptEvaluator
from server.evals.eval_3_qa_auditor import QaAuditorEvaluator

def run_stage_1() -> bool:
    print("\n" + "=" * 76)
    print("  STAGE 1: VIDEO ANALYZER VS. GROUND TRUTH DATASET")
    print("=" * 76)
    eval1 = VideoAnalyzerEvaluator()
    res = eval1.evaluate(eval1.expected_scenes)
    status_str = "PASSED" if res["passed"] else "FAILED"
    print(f"Status:                      [{status_str}]")
    print(f"Overall Analyzer Score:      {res['overall_score']} / 100 (Threshold: 80)")
    print(f"Ground-Truth Entity Recall:  {res['entity_recall_score']}% ({res['matched_entities_count']}/{res['total_expected_entities']} key entities)")
    print(f"Action-Reaction Causality:   {res['action_reaction_causality']}%")
    print(f"Boilerplate Violations:      {res['boilerplate_hits']} (Zero tolerance: 0)")
    print(f"Key Entities Verified:       {', '.join(res['sample_matched_entities'][:5])}")
    return res["passed"]

def run_stage_2() -> bool:
    print("\n" + "=" * 76)
    print("  STAGE 2: DIALOGUE SCRIPT GENERATION EVALUATION")
    print("=" * 76)
    eval2 = DialogueScriptEvaluator()
    res = eval2.evaluate(eval2.expected_dialogue)
    status_str = "PASSED" if res["passed"] else "FAILED"
    print(f"Status:                      [{status_str}]")
    print(f"Overall Dialogue Score:      {res['overall_score']} / 100 (Threshold: 80)")
    print(f"Visual Scene Anchoring:      {res['visual_anchoring_score']}%")
    print(f"README Concepts Grounding:   {res['readme_coverage_score']}%")
    print(f"Conversational Cadence:      {res['conversational_cadence_score']}% ({res['turn_distribution']})")
    print(f"Anti-Timestamp Constraint:   {res['anti_timestamp_score']}% ({res['timestamp_violations_count']} violations)")
    return res["passed"]

def run_stage_3() -> bool:
    print("\n" + "=" * 76)
    print("  STAGE 3: QA AUDITOR DISCRIMINATION & SENSITIVITY")
    print("=" * 76)
    eval3 = QaAuditorEvaluator()
    res = eval3.evaluate()
    status_str = "PASSED" if res["passed"] else "FAILED"
    print(f"Status:                      [{status_str}]")
    print(f"Auditor Integrity Score:     {res['overall_score']} / 100")
    print(f"Positive Benchmark Score:    {res['positive_benchmark']['overall_score']}/100 (Passed: {res['positive_benchmark']['passed']})")
    print(f"Defect Injection Caught:     {res['defect_injection_benchmark']['caught_defect']}")
    print(f"Penalized Defect Score:      {res['defect_injection_benchmark']['reported_overall_score']}/100")
    return res["passed"]

def main():
    parser = argparse.ArgumentParser(description="Frame Talk - Master Evaluation Suite Runner")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=None, help="Run specific stage (1, 2, or 3)")
    parser.add_argument("--all", action="store_true", help="Run all 3 evaluation stages consecutively")
    args = parser.parse_args()

    print("*" * 76)
    print("         FRAME TALK MULTI-STAGE DECOUPLED EVALUATION HARNESS")
    print("*" * 76)

    results = {}
    if args.stage == 1 or args.all or (args.stage is None and not args.all):
        if args.stage == 1 or args.all:
            results["Stage 1: Video Analyzer"] = run_stage_1()
    if args.stage == 2 or args.all:
        results["Stage 2: Dialogue Script"] = run_stage_2()
    if args.stage == 3 or args.all:
        results["Stage 3: QA Auditor"] = run_stage_3()

    if not results:
        # Default if no arguments given: run all
        results["Stage 1: Video Analyzer"] = run_stage_1()
        results["Stage 2: Dialogue Script"] = run_stage_2()
        results["Stage 3: QA Auditor"] = run_stage_3()

    print("\n" + "=" * 76)
    print("  EVALUATION SUMMARY MATRIX")
    print("=" * 76)
    all_passed = True
    for stage_name, passed in results.items():
        status = "PASSED [OK]" if passed else "FAILED [X]"
        print(f"  {stage_name.ljust(36)}: {status}")
        if not passed:
            all_passed = False
    print("=" * 76)

    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
