"""
Unit Test Suite: Anonymous Multi-User Activity Isolation & Analytics
Verifies client pseudonymization, job ownership isolation, and ClickHouse user aggregations.
"""

import unittest
from fastapi.testclient import TestClient
from server.app import app
from server.repositories.job_repository import job_repository
from server.repositories.telemetry_repository import telemetry_repository

class TestUserIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_user_header_pseudonymization(self):
        """Verify client X-FrameTalk-User-Id is deterministically pseudonymized into X-FrameTalk-User-Hash."""
        raw_user_id = "usr_client_alpha_12345678"
        headers = {"X-FrameTalk-User-Id": raw_user_id}
        response = self.client.get("/api/health", headers=headers)
        self.assertEqual(response.status_code, 200)
        user_hash = response.headers.get("X-FrameTalk-User-Hash")
        self.assertIsNotNone(user_hash)
        self.assertEqual(len(user_hash), 16)
        # Raw ID must NEVER appear in response header
        self.assertNotIn(raw_user_id, user_hash)

    def test_missing_or_malformed_user_id_fallback(self):
        """Verify missing or injection user-id headers fallback to sanitized ephemeral pseudonym."""
        # Test missing header
        resp_empty = self.client.get("/api/health")
        self.assertEqual(resp_empty.status_code, 200)
        self.assertIn("X-FrameTalk-User-Hash", resp_empty.headers)

        # Test malicious injection payload in user header
        malicious_id = "usr_test' OR 1=1; DROP TABLE users; --"
        resp_malicious = self.client.get("/api/health", headers={"X-FrameTalk-User-Id": malicious_id})
        self.assertEqual(resp_malicious.status_code, 200)
        hash_val = resp_malicious.headers.get("X-FrameTalk-User-Hash")
        self.assertEqual(len(hash_val), 16)

    def test_job_multi_user_isolation(self):
        """Verify User A's job cannot be inspected or hijacked by User B."""
        user_a_raw = "usr_alice_workspace_11111111"
        user_b_raw = "usr_bob_workspace_22222222"

        # Compute user A's hash
        resp_a = self.client.get("/api/health", headers={"X-FrameTalk-User-Id": user_a_raw})
        user_a_hash = resp_a.headers["X-FrameTalk-User-Hash"]

        # User A creates a job
        job_id = f"job_isolated_{user_a_hash[:8]}"
        job_repository.create_job(job_id=job_id, user_hash=user_a_hash)
        job_repository.update_job(job_id=job_id, status="COMPLETED", result={"secret": "alice_project_data"})

        # User A requests the job -> should succeed (200)
        res_a = self.client.get(f"/api/jobs/{job_id}", headers={"X-FrameTalk-User-Id": user_a_raw})
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["result"]["secret"], "alice_project_data")

        # User B requests the job -> must be isolated (404)
        res_b = self.client.get(f"/api/jobs/{job_id}", headers={"X-FrameTalk-User-Id": user_b_raw})
        self.assertEqual(res_b.status_code, 404)

    def test_clickhouse_user_statistics_aggregation(self):
        """Verify user activity logging and executive statistics (Avg, Min, Max per user)."""
        user_1 = "hash_user_alpha"
        user_2 = "hash_user_beta"

        # User 1 performs 2 video analyses, 1 script generation
        telemetry_repository.log_user_activity(user_hash=user_1, action_type="VIDEO_ANALYZED", session_id="s1")
        telemetry_repository.log_user_activity(user_hash=user_1, action_type="VIDEO_ANALYZED", session_id="s2")
        telemetry_repository.log_user_activity(user_hash=user_1, action_type="SCRIPT_GENERATED", session_id="s1")

        # User 2 performs 1 video analysis
        telemetry_repository.log_user_activity(user_hash=user_2, action_type="VIDEO_ANALYZED", session_id="s3")

        # Fetch statistics via API
        response = self.client.get("/api/clickhouse/user-statistics")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("total_unique_users", data)
        self.assertGreaterEqual(data["total_unique_users"], 2)
        self.assertIn("funnel", data)
        self.assertIn("distributions", data)

        video_dist = data["distributions"].get("VIDEO_ANALYZED", {})
        self.assertIn("avg_per_user", video_dist)
        self.assertIn("min_per_user", video_dist)
        self.assertIn("max_per_user", video_dist)
        self.assertEqual(video_dist["min_per_user"], 1)
        self.assertEqual(video_dist["max_per_user"], 2)

if __name__ == "__main__":
    unittest.main()
