"""
Audio & Synchronization Service
Orchestrates speech synthesis via gemini-3.1-flash-tts-preview,
calculates millisecond Chronos dynamic visual holds, and logs telemetry.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional
from server.sync.audio_synth import audio_synth
from server.sync.chronos_engine import chronos_engine
from server.repositories.file_repository import file_repository
from server.repositories.telemetry_repository import telemetry_repository
from server.core.retry_handler import execute_with_retry

logger = logging.getLogger("frametalk.service.audio")

class AudioService:
    def synthesize_and_align(
        self,
        scenes: List[Dict[str, Any]],
        dialogue: List[Dict[str, Any]],
        voice_alex: str = "Puck",
        voice_sam: str = "Kore",
        session_id: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synthesizes dialogue lines, aligns timeline via Chronos, and logs to ClickHouse."""
        sid = session_id or str(uuid.uuid4())
        audio_chunks = []
        updated_turns = []

        for idx, turn in enumerate(dialogue):
            text = turn.get("text", "")
            speaker = turn.get("speaker", "Alex")

            pcm_bytes, dur_ms = execute_with_retry(
                action_name=f"TTS Line Synthesis (Turn {idx})",
                fn=audio_synth.synthesize_line,
                text=text,
                speaker=speaker,
                voice_alex=voice_alex,
                voice_sam=voice_sam,
                api_key=api_key
            )
            audio_chunks.append((pcm_bytes, dur_ms))

            updated_turns.append({
                **turn,
                "turn_index": idx,
                "audio_duration_ms": dur_ms,
                "pcm_bytes": pcm_bytes
            })

        # Calculate Chronos Dynamic Video Stretch
        chronos_result = chronos_engine.align_scenes_and_dialogue(scenes, updated_turns)

        # Concatenate Master Audio Perfectly Padded to Video Timeline
        master_pcm = bytearray()
        conversational_pause_ms = chronos_engine.conversational_pause_ms

        for segment in chronos_result.get("aligned_timeline", []):
            segment_duration_ms = segment.get("playhead_end_ms", 0) - segment.get("playhead_start_ms", 0)
            
            if segment.get("segment_type") == "video_passthrough":
                # No dialogue in this scene, just pad silence for the full video duration
                master_pcm.extend(audio_synth.generate_silence(segment_duration_ms))
            else:
                # Scene with dialogue
                scene_turns = segment.get("turns", [])
                audio_consumed_ms = 0
                
                for t_idx, turn in enumerate(scene_turns):
                    pcm_bytes = turn.get("pcm_bytes", b'')
                    dur_ms = turn.get("audio_duration_ms", 0)
                    
                    master_pcm.extend(pcm_bytes)
                    audio_consumed_ms += dur_ms
                    
                    if t_idx < len(scene_turns) - 1:
                        master_pcm.extend(audio_synth.generate_silence(conversational_pause_ms))
                        audio_consumed_ms += conversational_pause_ms
                
                # Pad the remaining time in this scene with silence so it aligns perfectly with the video
                remaining_silence_ms = segment_duration_ms - audio_consumed_ms
                if remaining_silence_ms > 0:
                    master_pcm.extend(audio_synth.generate_silence(remaining_silence_ms))

        # Remove the temporary pcm_bytes to avoid polluting the JSON response
        for turn in updated_turns:
            turn.pop("pcm_bytes", None)
        for segment in chronos_result.get("aligned_timeline", []):
            for turn in segment.get("turns", []):
                turn.pop("pcm_bytes", None)

        master_wav = audio_synth.pcm_to_wav(bytes(master_pcm))

        audio_filename = f"podcast_{sid[:8]}.wav"
        file_repository.save_output_file(audio_filename, master_wav)

        # Log to ClickHouse
        scene_sched_map = {s["scene_id"]: s for s in chronos_result.get("scene_schedules", [])}
        scene_map = {s["scene_id"]: s for s in scenes}

        for turn in updated_turns:
            s_id = turn.get("scene_id")
            sc = scene_map.get(s_id, {})
            sched = scene_sched_map.get(s_id, {})

            telemetry_repository.log_sync_event(
                session_id=sid,
                turn_index=turn.get("turn_index", 0),
                speaker=turn.get("speaker", "Alex"),
                dialogue_text=turn.get("text", ""),
                audio_clip_path=audio_filename,
                audio_duration_ms=turn.get("audio_duration_ms", 0),
                video_scene_start_ms=sc.get("start_time_ms", 0),
                video_scene_end_ms=sc.get("end_time_ms", 0),
                video_scene_duration_ms=sc.get("duration_ms", 0),
                required_freeze_ms=sched.get("required_freeze_ms", 0),
                accumulated_drift_ms=0,
                pacing_status=sched.get("pacing", "SYNCHRONIZED"),
                token_cost=round(len(turn.get("text", "").split()) * 0.00004, 6)
            )

        return {
            "session_id": sid,
            "audio_url": f"/output/{audio_filename}",
            "audio_filename": audio_filename,
            "chronos_schedule": chronos_result,
            "total_audio_ms": len(master_pcm) // 48,
            "updated_turns": updated_turns
        }

    def test_voice(self, voice_name: str, text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Synthesizes a short test clip for a specific voice."""
        pcm_bytes, dur_ms = execute_with_retry(
            action_name=f"Test Voice Synthesis",
            fn=audio_synth.synthesize_line,
            text=text,
            speaker="Test",
            voice_alex=voice_name,
            voice_sam=voice_name,
            api_key=api_key
        )
        wav_bytes = audio_synth.pcm_to_wav(pcm_bytes)
        filename = f"test_voice_{uuid.uuid4().hex[:8]}.wav"
        file_repository.save_output_file(filename, wav_bytes)
        return {"audio_url": f"/output/{filename}"}

audio_service = AudioService()
