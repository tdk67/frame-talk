"""
Unit Tests: Chronos Synchronization Engine
Validates exact millisecond PCM audio metering, dynamic video hold calculations,
conversational pause gaps, and timeline stretching.
"""

import unittest
from server.sync.chronos_engine import chronos_engine, ChronosSyncEngine, CONVERSATIONAL_PAUSE_MS
from server.sync.audio_synth import PCM_SAMPLE_RATE, PCM_CHANNELS, PCM_SAMPLE_WIDTH, PCM_BYTES_PER_SECOND

class TestChronosEngine(unittest.TestCase):
    def test_pcm_byte_duration_math(self):
        """Verify 24 kHz 16-bit Mono audio duration math: 48,000 bytes = 1,000 ms."""
        self.assertEqual(PCM_SAMPLE_RATE, 24000)
        self.assertEqual(PCM_CHANNELS, 1)
        self.assertEqual(PCM_SAMPLE_WIDTH, 2)
        self.assertEqual(PCM_BYTES_PER_SECOND, 48000)

        # 48 bytes per millisecond
        one_second_bytes = b"\x00" * 48000
        dur_ms = int((len(one_second_bytes) / PCM_BYTES_PER_SECOND) * 1000)
        self.assertEqual(dur_ms, 1000)

        two_point_five_sec_bytes = b"\x00" * 120000
        dur_ms_2 = int((len(two_point_five_sec_bytes) / PCM_BYTES_PER_SECOND) * 1000)
        self.assertEqual(dur_ms_2, 2500)

    def test_chronos_no_freeze_needed(self):
        """When speech fits within video scene, required_freeze_ms should be 0."""
        engine = ChronosSyncEngine(conversational_pause_ms=200)
        scenes = [
            {
                "scene_id": "scene_1",
                "start_time_ms": 0,
                "end_time_ms": 10000,
                "duration_ms": 10000,
                "action_title": "Overview"
            }
        ]
        dialogue = [
            {
                "turn_index": 0,
                "scene_id": "scene_1",
                "speaker": "Alex",
                "text": "Hello and welcome.",
                "audio_duration_ms": 3000
            }
        ]

        result = engine.align_scenes_and_dialogue(scenes, dialogue)
        self.assertEqual(result["total_freeze_injected_ms"], 0)
        self.assertEqual(len(result["scene_schedules"]), 1)
        sched = result["scene_schedules"][0]
        self.assertEqual(sched["required_freeze_ms"], 0)
        self.assertEqual(sched["pacing"], "NATURAL_FIT")

    def test_chronos_dynamic_freeze_calculation(self):
        """When speech exceeds video scene, required_freeze_ms must stretch the timeline with +300ms buffer."""
        engine = ChronosSyncEngine(conversational_pause_ms=200)
        scenes = [
            {
                "scene_id": "scene_1",
                "start_time_ms": 0,
                "end_time_ms": 5000,
                "duration_ms": 5000,
                "action_title": "Complex Architecture"
            }
        ]
        # Dialogue takes 7000ms, exceeding the 5000ms scene by 2000ms
        dialogue = [
            {
                "turn_index": 0,
                "scene_id": "scene_1",
                "speaker": "Alex",
                "text": "Notice the deep technical details here.",
                "audio_duration_ms": 4000
            },
            {
                "turn_index": 1,
                "scene_id": "scene_1",
                "speaker": "Sam",
                "text": "Right, that architecture completely eliminates the bottleneck.",
                "audio_duration_ms": 3000
            }
        ]

        result = engine.align_scenes_and_dialogue(scenes, dialogue)
        sched = result["scene_schedules"][0]

        # Total speech: 4000 + 200 (pause) + 3000 = 7200ms
        # Scene duration: 5000ms -> Required freeze: (7200 - 5000) + 300ms buffer = 2500ms
        expected_freeze = (7200 - 5000) + 300
        self.assertEqual(sched["required_freeze_ms"], expected_freeze)
        self.assertEqual(sched["pacing"], "FRAME_STRETCHED")
        self.assertEqual(result["total_freeze_injected_ms"], expected_freeze)
        self.assertGreater(result["total_output_duration_ms"], 5000)

    def test_chronos_multi_scene_chain(self):
        """Verify playhead accumulates correctly across multiple scenes with dynamic holds."""
        engine = ChronosSyncEngine(conversational_pause_ms=200)
        scenes = [
            {"scene_id": "s1", "start_time_ms": 0, "end_time_ms": 4000, "duration_ms": 4000},
            {"scene_id": "s2", "start_time_ms": 4000, "end_time_ms": 8000, "duration_ms": 4000}
        ]
        dialogue = [
            {"turn_index": 0, "scene_id": "s1", "speaker": "Alex", "audio_duration_ms": 5000}, # (5000-4000)+300 = 1300ms freeze
            {"turn_index": 1, "scene_id": "s2", "speaker": "Sam", "audio_duration_ms": 2000}  # Fits easily
        ]

        result = engine.align_scenes_and_dialogue(scenes, dialogue)
        self.assertEqual(len(result["scene_schedules"]), 2)
        s1 = result["scene_schedules"][0]
        s2 = result["scene_schedules"][1]

        self.assertEqual(s1["required_freeze_ms"], 1300)
        self.assertEqual(s1["pacing"], "FRAME_STRETCHED")
        self.assertEqual(s2["required_freeze_ms"], 0)
        self.assertEqual(s2["pacing"], "NATURAL_FIT")
        self.assertEqual(result["total_freeze_injected_ms"], 1300)

if __name__ == "__main__":
    unittest.main()
