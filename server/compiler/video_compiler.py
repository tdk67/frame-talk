"""
Compiler Agent: Production-Grade Video-Audio Stitching Engine.
Takes the raw screencast, injects calculated frame-freezes/holds
to expand the video timeline dynamically, and muxes the synchronized
podcast audio into a final output MP4.
"""

import os
import subprocess
import logging
import tempfile
from typing import Dict, Any, List, Optional

logger = logging.getLogger("castops.compiler")

class VideoCompiler:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def compile_synchronized_video(
        self,
        video_input_path: str,
        audio_input_path: str,
        chronos_schedule: Dict[str, Any],
        output_filename: str = "castops_synchronized_podcast.mp4"
    ) -> Dict[str, Any]:
        """
        Executes FFmpeg dynamic timeline stretching:
        For each scene with required_freeze_ms > 0, cuts video up to freeze point,
        inserts a frozen frame of exact duration, then resumes, muxing with master audio.
        """
        output_path = os.path.join(self.output_dir, output_filename)
        aligned_timeline = chronos_schedule.get("aligned_timeline", [])
        total_freeze_ms = chronos_schedule.get("total_freeze_injected_ms", 0)

        # If no freezes needed, simple 1:1 remux with audio
        if total_freeze_ms == 0 or not aligned_timeline:
            return self._simple_remux(video_input_path, audio_input_path, output_path)

        try:
            return self._execute_dynamic_freeze_compilation(
                video_input_path, audio_input_path, aligned_timeline, output_path
            )
        except Exception as e:
            logger.error(f"Complex freeze compilation failed: {e}. Falling back to clean remux.")
            return self._simple_remux(video_input_path, audio_input_path, output_path)

    def _simple_remux(self, video_path: str, audio_path: str, output_path: str) -> Dict[str, Any]:
        """Directly muxes video and audio track."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path
        ]
        logger.info(f"Running simple remux: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed ({result.returncode}): {result.stderr[:300]}")

        return {
            "success": True,
            "output_path": output_path,
            "output_filename": os.path.basename(output_path),
            "file_size_bytes": os.path.getsize(output_path) if os.path.exists(output_path) else 0,
            "freeze_applied": False
        }

    def _execute_dynamic_freeze_compilation(
        self,
        video_path: str,
        audio_path: str,
        aligned_timeline: List[Dict[str, Any]],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Builds a multi-segment timeline using FFmpeg concat with freeze holds.
        """
        temp_dir = tempfile.mkdtemp(prefix="castops_compile_")
        segment_files = []

        try:
            for idx, seg in enumerate(aligned_timeline):
                v_start_s = seg["video_start_ms"] / 1000.0
                v_end_s = seg["video_end_ms"] / 1000.0
                v_dur_s = max(0.2, v_end_s - v_start_s)
                freeze_ms = seg.get("freeze_duration_ms", 0)

                # 1. Base video clip for this segment
                base_clip = os.path.join(temp_dir, f"seg_{idx}_base.mp4")
                cmd_cut = [
                    "ffmpeg", "-y",
                    "-ss", f"{v_start_s:.3f}",
                    "-i", video_path,
                    "-t", f"{v_dur_s:.3f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                    "-an", base_clip
                ]
                subprocess.run(cmd_cut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                segment_files.append(base_clip)

                # 2. If freeze required, extract last frame and generate freeze video
                if freeze_ms > 0:
                    freeze_dur_s = freeze_ms / 1000.0
                    frame_img = os.path.join(temp_dir, f"seg_{idx}_freeze_frame.jpg")
                    freeze_clip = os.path.join(temp_dir, f"seg_{idx}_freeze.mp4")

                    # Extract frame at end of segment
                    cmd_frame = [
                        "ffmpeg", "-y",
                        "-sseof", "-0.1",
                        "-i", base_clip,
                        "-vframes", "1",
                        "-q:v", "2",
                        frame_img
                    ]
                    subprocess.run(cmd_frame, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    if os.path.exists(frame_img):
                        # Generate video from freeze frame
                        cmd_freeze = [
                            "ffmpeg", "-y",
                            "-loop", "1",
                            "-i", frame_img,
                            "-t", f"{freeze_dur_s:.3f}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                            freeze_clip
                        ]
                        subprocess.run(cmd_freeze, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                        segment_files.append(freeze_clip)

            # Write concat manifest
            concat_list = os.path.join(temp_dir, "segments.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for s_file in segment_files:
                    # Windows paths need forward slashes or escaping for FFmpeg concat
                    safe_path = s_file.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            # Final stitch with master audio
            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-i", audio_path,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path
            ]
            logger.info(f"Stitching {len(segment_files)} segments with master audio...")
            subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            return {
                "success": True,
                "output_path": output_path,
                "output_filename": os.path.basename(output_path),
                "file_size_bytes": os.path.getsize(output_path),
                "freeze_applied": True,
                "total_segments_stitched": len(segment_files)
            }
        finally:
            # Cleanup temp files
            try:
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except Exception:
                pass

video_compiler = VideoCompiler()
