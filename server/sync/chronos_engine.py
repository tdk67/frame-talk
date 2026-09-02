"""
Chronos Sync Engine: Millisecond-Precision Audio-to-Visual Alignment.
Calculates exact audio durations, eliminates timing drift, replaces
artificial silence padding with dynamic video timeline stretching
(frame freezes and focal holds), and maintains natural conversational cadence.
"""

from typing import List, Dict, Any, Tuple
import math

CONVERSATIONAL_PAUSE_MS = 220  # Natural human turn-taking gap (180ms - 260ms)

class ChronosSyncEngine:
    def __init__(self, conversational_pause_ms: int = CONVERSATIONAL_PAUSE_MS):
        self.conversational_pause_ms = conversational_pause_ms

    def align_scenes_and_dialogue(
        self,
        scenes: List[Dict[str, Any]],
        dialogue_turns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Takes visual scenes and dialogue turns (with exact audio durations in ms),
        calculating required_freeze_ms per scene and producing a unified timeline schedule.

        Each scene has:
          - scene_id: str
          - start_time_ms: int
          - end_time_ms: int
          - duration_ms: int
          - screen_summary: str
          - action_type: str

        Each dialogue turn has:
          - turn_index: int
          - scene_id: str
          - speaker: str ("Alex" or "Sam")
          - text: str
          - audio_duration_ms: int
          - audio_clip_path: str (optional)
        """
        # Map turns to their respective scene
        scene_map = {s["scene_id"]: s for s in scenes}
        scene_turns: Dict[str, List[Dict[str, Any]]] = {s["scene_id"]: [] for s in scenes}

        for turn in dialogue_turns:
            s_id = turn.get("scene_id")
            if s_id in scene_turns:
                scene_turns[s_id].append(turn)
            else:
                # Fallback: assign to closest scene by index or first scene
                if scenes:
                    scene_turns[scenes[0]["scene_id"]].append(turn)

        aligned_timeline = []
        schedule_per_scene = []
        master_playhead_ms = 0
        total_freeze_injected_ms = 0

        for s_idx, scene in enumerate(scenes):
            s_id = scene["scene_id"]
            v_start = scene["start_time_ms"]
            v_end = scene["end_time_ms"]
            v_dur = scene.get("duration_ms", max(1000, v_end - v_start))

            turns = scene_turns.get(s_id, [])

            if not turns:
                # No dialogue for this scene: runs at native video speed
                aligned_timeline.append({
                    "segment_type": "video_passthrough",
                    "scene_id": s_id,
                    "video_start_ms": v_start,
                    "video_end_ms": v_end,
                    "video_duration_ms": v_dur,
                    "playhead_start_ms": master_playhead_ms,
                    "playhead_end_ms": master_playhead_ms + v_dur,
                    "freeze_duration_ms": 0,
                    "turns": []
                })
                master_playhead_ms += v_dur
                schedule_per_scene.append({
                    "scene_id": s_id,
                    "required_freeze_ms": 0,
                    "video_duration_ms": v_dur,
                    "total_audio_ms": 0,
                    "pacing": "NATIVE_PASSTHROUGH"
                })
                continue

            # Calculate total dialogue time needed in this scene
            total_audio_ms = sum(t.get("audio_duration_ms", 3000) for t in turns)
            # Add natural conversational pauses between turns
            total_pauses_ms = max(0, len(turns) - 1) * self.conversational_pause_ms
            total_speech_needed_ms = total_audio_ms + total_pauses_ms

            # Dynamic Video Timeline Stretching Calculation:
            # If the speech takes longer than the raw visual scene, calculate exact freeze required
            required_freeze_ms = 0
            if total_speech_needed_ms > v_dur:
                # Add a 300ms visual buffer so the viewer comfortably absorbs the visual after the last word
                required_freeze_ms = (total_speech_needed_ms - v_dur) + 300
                total_freeze_injected_ms += required_freeze_ms

            effective_scene_duration_ms = v_dur + required_freeze_ms

            # Schedule individual dialogue turns within the scene
            current_turn_audio_start = master_playhead_ms
            scheduled_turns = []

            for t_idx, turn in enumerate(turns):
                dur = turn.get("audio_duration_ms", 3000)
                turn_schedule = {
                    **turn,
                    "timeline_start_ms": current_turn_audio_start,
                    "timeline_end_ms": current_turn_audio_start + dur,
                    "video_scene_start_ms": v_start,
                    "video_scene_end_ms": v_end,
                    "relative_to_scene_ms": current_turn_audio_start - master_playhead_ms
                }
                scheduled_turns.append(turn_schedule)
                current_turn_audio_start += dur + self.conversational_pause_ms

            # Determine optimal freeze point in the video:
            # Typically 70% into the visual action (when UI element / modal is fully visible)
            freeze_anchor_video_ms = min(v_end - 100, v_start + int(v_dur * 0.7))

            aligned_timeline.append({
                "segment_type": "dialogue_scene",
                "scene_id": s_id,
                "video_start_ms": v_start,
                "video_end_ms": v_end,
                "video_duration_ms": v_dur,
                "playhead_start_ms": master_playhead_ms,
                "playhead_end_ms": master_playhead_ms + effective_scene_duration_ms,
                "freeze_anchor_video_ms": freeze_anchor_video_ms,
                "freeze_duration_ms": required_freeze_ms,
                "is_frozen": required_freeze_ms > 0,
                "turns": scheduled_turns
            })

            schedule_per_scene.append({
                "scene_id": s_id,
                "required_freeze_ms": required_freeze_ms,
                "video_duration_ms": v_dur,
                "total_audio_ms": total_audio_ms,
                "effective_duration_ms": effective_scene_duration_ms,
                "pacing": "FRAME_STRETCHED" if required_freeze_ms > 0 else "NATURAL_FIT"
            })

            master_playhead_ms += effective_scene_duration_ms

        return {
            "total_output_duration_ms": master_playhead_ms,
            "total_freeze_injected_ms": total_freeze_injected_ms,
            "aligned_timeline": aligned_timeline,
            "scene_schedules": schedule_per_scene
        }

chronos_engine = ChronosSyncEngine()
