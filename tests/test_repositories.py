"""
Unit Tests: File, Job, and Telemetry Repositories
Validates persistence, caching, path traversal defenses, and in-memory fallbacks.
"""

import os
import unittest
import tempfile
from server.repositories.job_repository import job_repository
from server.repositories.file_repository import file_repository
from server.repositories.telemetry_repository import telemetry_repository
from server.core.exceptions import InvalidInputException, ResourceNotFoundException

class TestRepositories(unittest.TestCase):
    def test_job_repository_lifecycle(self):
        """Verify job creation, status updates, and retrieval."""
        test_id = "test_hash_abc123_456"
        created_id = job_repository.create_job(job_id=test_id)
        self.assertEqual(created_id, test_id)

        job = job_repository.get_job(test_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "PENDING")
        self.assertIsNone(job["result"])

        # Update to PROCESSING
        job_repository.update_job(test_id, status="PROCESSING")
        job = job_repository.get_job(test_id)
        self.assertEqual(job["status"], "PROCESSING")

        # Update to COMPLETED with result
        result_data = {"scenes": [{"scene_id": "scene_1"}], "total_scenes": 1}
        job_repository.update_job(test_id, status="COMPLETED", result=result_data)
        job = job_repository.get_job(test_id)
        self.assertEqual(job["status"], "COMPLETED")
        self.assertEqual(job["result"]["total_scenes"], 1)

    def test_job_repository_path_traversal_blocked(self):
        """Verify job_id path traversal attempts raise InvalidInputException."""
        with self.assertRaises(InvalidInputException):
            job_repository._get_path("../../evil_job")

        with self.assertRaises(InvalidInputException):
            job_repository._get_path("subdir/subjob")

        with self.assertRaises(InvalidInputException):
            job_repository._get_path("job;rm -rf")

    def test_file_repository_path_traversal_blocked(self):
        """Verify file_repository path traversal attempts raise InvalidInputException."""
        with self.assertRaises(InvalidInputException):
            file_repository.get_upload_path("../../../etc/passwd")

        with self.assertRaises(InvalidInputException):
            file_repository.get_output_path("..\\windows\\system32\\calc.exe")

    def test_file_repository_nonexistent_file(self):
        """Verify get_upload_path raises ResourceNotFoundException on missing file."""
        with self.assertRaises(ResourceNotFoundException):
            file_repository.get_upload_path("definitely_nonexistent_video_12345.mp4")

    def test_telemetry_repository_in_memory_logging(self):
        """Verify telemetry logging writes to buffer and computes metrics correctly."""
        session_id = "test_session_unit_xyz"
        telemetry_repository.log_sync_event(
            session_id=session_id,
            turn_index=0,
            speaker="Alex",
            dialogue_text="Testing telemetry logging.",
            audio_clip_path="clip_0.wav",
            audio_duration_ms=2500,
            video_scene_start_ms=0,
            video_scene_end_ms=3000,
            video_scene_duration_ms=3000,
            required_freeze_ms=0,
            accumulated_drift_ms=0,
            pacing_status="SYNCHRONIZED"
        )

        events = telemetry_repository.get_events(session_id=session_id)
        self.assertGreaterEqual(len(events), 1)
        ev = events[-1]
        self.assertEqual(ev["session_id"], session_id)
        self.assertEqual(ev["speaker"], "Alex")
        self.assertEqual(ev["audio_duration_ms"], 2500)

        # Check metrics
        metrics = telemetry_repository.get_metrics_summary(session_id=session_id)
        self.assertGreaterEqual(metrics["total_events"], 1)
        self.assertGreaterEqual(metrics["total_audio_duration_ms"], 2500)

if __name__ == "__main__":
    unittest.main()
