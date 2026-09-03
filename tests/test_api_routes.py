"""
Unit Tests: FastAPI API Endpoints & Middleware
Validates health checks, BYOK verification, job polling, security headers, and telemetry.
"""

import unittest
from fastapi.testclient import TestClient
from server.app import app
from server.repositories.job_repository import job_repository

class TestApiRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        """Verify /api/health returns 200 with service info."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("clickhouse_connected", data)
        self.assertIn("clickhouse_host", data)

    def test_security_headers_present(self):
        """Verify standard security headers are injected on all outgoing responses."""
        response = self.client.get("/api/health")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(response.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_byok_verify_empty_or_missing(self):
        """Verify /api/byok/verify rejects missing API key."""
        response = self.client.post("/api/byok/verify", json={})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("valid"))
        self.assertIn("Please paste", data.get("error", ""))

    def test_byok_verify_openrouter_rejected(self):
        """Verify /api/byok/verify rejects OpenRouter keys with clear guidance."""
        response = self.client.post("/api/byok/verify", json={"api_key": "sk-or-v1-abcdef123456"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("valid"))
        self.assertIn("OpenRouter is not supported", data.get("error", ""))

    def test_job_polling_not_found(self):
        """Verify /api/jobs/{job_id} returns 404 on nonexistent job."""
        response = self.client.get("/api/jobs/job_nonexistent_12345")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertTrue(data.get("error") or "detail" in data)

    def test_job_polling_existing(self):
        """Verify /api/jobs/{job_id} returns existing job details."""
        test_job_id = "test_job_unit_test_abc"
        job_repository.create_job(job_id=test_job_id)
        job_repository.update_job(test_job_id, status="COMPLETED", result={"scenes": []})

        response = self.client.get(f"/api/jobs/{test_job_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("job_id"), test_job_id)
        self.assertEqual(data.get("status"), "COMPLETED")
        self.assertEqual(data.get("result"), {"scenes": []})

    def test_clickhouse_events_endpoint(self):
        """Verify /api/clickhouse/events returns list and status."""
        response = self.client.get("/api/clickhouse/events?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("events", data)
        self.assertIn("clickhouse_status", data)
        self.assertIsInstance(data["events"], list)

    def test_clickhouse_metrics_endpoint(self):
        """Verify /api/clickhouse/metrics returns summary structure."""
        response = self.client.get("/api/clickhouse/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_events", data)
        self.assertIn("total_audio_duration_ms", data)
        self.assertIn("total_freeze_injected_ms", data)

if __name__ == "__main__":
    unittest.main()
