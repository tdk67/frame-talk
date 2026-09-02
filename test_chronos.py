"""
Verification script for CastOps AI Studio.
Tests Chronos Sync Engine, Audio Synthesis, ClickHouse logger, and Agent fallbacks.
"""

import sys
import os

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.sync.chronos_engine import chronos_engine
from server.sync.audio_synth import audio_synth
from server.sync.clickhouse_logger import ch_logger
from server.agents.ingestion_agent import ingestion_agent
from server.agents.scriptwriter_agent import scriptwriter_agent
from server.agents.qa_agent import qa_agent

def test_pipeline():
    print("=== Testing CastOps AI Studio Pipeline ===")

    # 1. Test Ingestion Agent fallback
    sample_readme = """
    # CastOps Engine
    ## Video Analysis
    Decomposes screencasts into visual scenes.
    ## Chronos Sync
    Aligns dialogue and stretches video.
    ## Compilation
    Exports 1080p MP4.
    """
    scenes = ingestion_agent._generate_fallback_scenes(sample_readme, total_duration_sec=30.0)
    print(f"[OK] Ingestion Agent generated {len(scenes)} visual scenes.")
    assert len(scenes) >= 3, "Expected at least 3 scenes"
    assert scenes[0]["start_time_ms"] == 0

    # 2. Test Scriptwriter Agent procedural generation
    dialogue = scriptwriter_agent._generate_procedural_dialogue(scenes)
    print(f"[OK] Scriptwriter Agent generated {len(dialogue)} dialogue turns.")
    assert len(dialogue) >= len(scenes), "Expected dialogue turns matching scenes"

    # 3. Test Audio Synthesis & Duration Metering
    turn = dialogue[0]
    pcm_bytes, dur_ms = audio_synth.synthesize_line(turn["text"], turn["speaker"])
    print(f"[OK] Audio Synth produced {len(pcm_bytes)} bytes of PCM ({dur_ms}ms) for turn 0.")
    assert dur_ms > 500, "Audio duration should be positive"
    turn["audio_duration_ms"] = dur_ms

    # Synthesize durations for remaining turns
    for t in dialogue[1:]:
        _, d_ms = audio_synth.synthesize_line(t["text"], t["speaker"])
        t["audio_duration_ms"] = d_ms

    # 4. Test Chronos Sync Engine Alignment & Dynamic Visual Hold
    alignment = chronos_engine.align_scenes_and_dialogue(scenes, dialogue)
    print(f"[OK] Chronos Alignment complete:")
    print(f"     Total Output Duration: {alignment['total_output_duration_ms']}ms")
    print(f"     Total Dynamic Freeze Injected: {alignment['total_freeze_injected_ms']}ms")
    assert alignment["total_output_duration_ms"] > 0
    assert len(alignment["aligned_timeline"]) == len(scenes)

    # 5. Test ClickHouse Logger
    event = ch_logger.log_sync_event(
        session_id="test_session_123",
        turn_index=0,
        speaker=turn["speaker"],
        dialogue_text=turn["text"],
        audio_clip_path="podcast_test.wav",
        audio_duration_ms=dur_ms,
        video_scene_start_ms=scenes[0]["start_time_ms"],
        video_scene_end_ms=scenes[0]["end_time_ms"],
        video_scene_duration_ms=scenes[0]["duration_ms"],
        required_freeze_ms=alignment["scene_schedules"][0]["required_freeze_ms"]
    )
    print(f"[OK] ClickHouse Logger recorded event for {event['speaker']} (Freeze: {event['required_freeze_ms']}ms).")
    events = ch_logger.get_events(session_id="test_session_123")
    assert len(events) >= 1

    # 6. Test QA Agent
    qa_results = qa_agent.audit_script(scenes, dialogue, sample_readme)
    print(f"[OK] QA Agent Score: {qa_results['overall_score']}% (Accuracy: {qa_results['accuracy_score']}%, Pacing: {qa_results['pacing_score']}%)")
    assert qa_results["checklist"]["no_robotic_timestamps"] is True

    print("\nALL SYSTEM VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_pipeline()
