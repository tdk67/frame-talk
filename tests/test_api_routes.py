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
        self.assertEqual(response.headers.get("Strict-Transport-Security"), "max-age=31536000; includeSubDomains")
        self.assertIn("default-src 'self'", response.headers.get("Content-Security-Policy", ""))

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

    def test_clickhouse_llm_metrics_endpoint(self):
        """Verify /api/clickhouse/llm-metrics returns token and cost breakdown."""
        from server.repositories.telemetry_repository import telemetry_repository
        telemetry_repository.log_llm_call(
            session_id="test_llm_session",
            agent_name="IngestionAgent",
            model_name="gemini-3.7-flash",
            prompt_tokens=15000,
            completion_tokens=800,
            total_tokens=15800,
            cost_usd=0.0027,
            latency_ms=1200
        )
        response = self.client.get("/api/clickhouse/llm-metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_llm_calls", data)
        self.assertIn("total_prompt_tokens", data)
        self.assertIn("total_cost_usd", data)
        self.assertIn("by_model", data)
        self.assertIn("by_agent", data)
        self.assertGreaterEqual(data["total_llm_calls"], 1)

    def test_estimate_cost_endpoint(self):
        """Verify /api/estimate-cost returns pre-flight token and dollar estimation."""
        response = self.client.get("/api/estimate-cost?duration_sec=120&readme_chars=4000")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("stages", data)
        self.assertIn("total_estimated_tokens", data)
        self.assertIn("total_estimated_cost_usd", data)
        self.assertIn("formatted_cost", data)
        self.assertEqual(data["video_duration_sec"], 120.0)
        self.assertGreater(data["total_estimated_cost_usd"], 0.0)

    def test_quota_endpoint(self):
        """Verify /api/quota returns user quota status."""
        response = self.client.get("/api/quota")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("max_videos", data)
        self.assertIn("videos_remaining", data)
        self.assertIn("hosted_mode", data)

    def test_agent_builder_spec_endpoint(self):
        """Verify /api/agent-builder/spec returns Google Cloud Agent Builder specification."""
        response = self.client.get("/api/agent-builder/spec")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("platform", data)
        self.assertIn("agents", data)
        self.assertEqual(len(data["agents"]), 4)

    def test_mcp_endpoints(self):
        """Verify /mcp endpoint implements Model Context Protocol for Google Cloud Agent Platform."""
        # 1. GET returns tool inventory
        res_get = self.client.get("/mcp")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("tools", res_get.json())

        # 2. POST initialize handshake
        res_init = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(res_init.status_code, 200)
        self.assertEqual(res_init.json()["result"]["serverInfo"]["name"], "FrameTalk-Chronos-Tool")

        # 3. POST tools/list
        res_list = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()["result"]["tools"]), 3)

        # 4. POST tools/call for Chronos calculation
        call_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "calculate_chronos_hold",
                "arguments": {
                    "speech_text": "Here is an extended explanation of our distributed architecture and data flow.",
                    "video_duration_ms": 2000
                }
            }
        }
        res_call = self.client.post("/mcp", json=call_payload)
        self.assertEqual(res_call.status_code, 200)
        self.assertFalse(res_call.json()["result"]["isError"])

    def test_discovery_seo_endpoints(self):
        """Verify hexagonal discovery_router endpoints for robots.txt, sitemap.xml, llms.txt, and llms-full.txt."""
        res_robots = self.client.get("/robots.txt")
        self.assertEqual(res_robots.status_code, 200)
        self.assertIn("User-agent: *", res_robots.text)
        self.assertIn("Sitemap:", res_robots.text)

        res_sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertIn("<urlset", res_sitemap.text)

        res_llms = self.client.get("/llms.txt")
        self.assertEqual(res_llms.status_code, 200)
        self.assertIn("# Frame Talk", res_llms.text)

        res_llms_full = self.client.get("/llms-full.txt")
        self.assertEqual(res_llms_full.status_code, 200)
        self.assertIn("# Frame Talk", res_llms_full.text)

    def test_missing_user_id_blocks_hosted_key(self):
        """Verify endpoints reject requests without X-FrameTalk-User-Id from using the hosted server key."""
        response = self.client.post("/api/test-voice", json={"voice_name": "Puck", "text": "Hello"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Missing User ID", response.json().get("detail", ""))

    def test_missing_user_id_allowed_with_byok(self):
        """Verify requests without X-FrameTalk-User-Id ARE allowed if BYOK key is provided."""
        response = self.client.post(
            "/api/test-voice",
            json={"voice_name": "Puck", "text": "Hello"},
            headers={"X-API-Key": "AIzaSyTestKey_BYOK_123456"}
        )
        # Should NOT fail with 401 Missing User ID
        self.assertNotEqual(response.status_code, 401)

    def test_auth_session_issuance(self):
        """Verify /api/auth/session issues cryptographically signed session tokens."""
        response = self.client.get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("signature_valid"))
        user_id = data.get("user_id")
        self.assertTrue(user_id.startswith("usr_"))
        self.assertIn(".", user_id)

        # Using this signed token passes user ID verification
        res_voice = self.client.post(
            "/api/test-voice",
            json={"voice_name": "Puck", "text": "Hello"},
            headers={"X-FrameTalk-User-Id": user_id}
        )
        self.assertNotEqual(res_voice.status_code, 401)

    def test_missing_secret_key_fails_fast(self):
        """Verify that missing SESSION_SECRET_KEY in environment raises RuntimeError with no fallbacks."""
        import os
        from server.core.config import config
        original_secret = os.environ.get("SESSION_SECRET_KEY")
        try:
            os.environ.pop("SESSION_SECRET_KEY", None)
            with self.assertRaises(RuntimeError) as ctx:
                _ = config.session_secret_key
            self.assertIn("Missing required environment secret", str(ctx.exception))
        finally:
            if original_secret:
                os.environ["SESSION_SECRET_KEY"] = original_secret

    def test_analyze_video_nonexistent_file_rejected_without_quota_loss(self):
        """Verify that submitting a nonexistent video file returns 400 Bad Request without consuming quota."""
        from server.core.user_token import sign_user_id
        from server.services.quota_service import quota_service
        import hashlib
        user_id = sign_user_id("usr_probe_test_no_quota_loss")
        user_hash = hashlib.sha256(f"{user_id}:frametalk_salt".encode()).hexdigest()[:16]

        # Check quota before
        initial_status = quota_service.get_quota_status(user_hash=user_hash)
        self.assertEqual(initial_status["videos_used"], 0)

        # Submit probe with nonexistent file
        res = self.client.post(
            "/api/analyze-video",
            json={
                "video_filename": "nonexistent_screencast_file_123.mp4",
                "readme_text": "# Test Project",
                "video_duration_seconds": 15.0
            },
            headers={"X-FrameTalk-User-Id": user_id}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not exist", res.json().get("detail", ""))

        # Verify quota was NOT consumed
        post_status = quota_service.get_quota_status(user_hash=user_hash)
        self.assertEqual(post_status["videos_used"], 0)

    def test_analyze_video_successful_dispatch(self):
        """Verify that submitting a valid existing video file dispatches analysis job (202 PENDING) and logs activity without 500 error."""
        from server.core.user_token import sign_user_id
        from server.repositories.file_repository import file_repository
        user_id = sign_user_id("usr_success_test_video_dispatch")

        # Create a real dummy video file in uploads_dir
        test_video_name = "test_screencast_valid.mp4"
        dummy_file = file_repository.uploads_dir / test_video_name
        dummy_file.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")

        try:
            res = self.client.post(
                "/api/analyze-video",
                json={
                    "video_filename": test_video_name,
                    "readme_text": "# Valid Project README",
                    "video_duration_seconds": 12.0
                },
                headers={"X-FrameTalk-User-Id": user_id, "X-API-Key": "AIzaSyTest_BYOK_1234567890"}
            )
            self.assertEqual(res.status_code, 202)
            data = res.json()
            self.assertEqual(data.get("status"), "PENDING")
            self.assertIn("job_id", data)
        finally:
            dummy_file.unlink(missing_ok=True)

    def test_mcp_telemetry_unauthenticated_rejected(self):
        """Verify POST /mcp log_clickhouse_telemetry without authentication returns JSON-RPC Unauthorized without HTTP 500."""
        payload = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_probe_test",
                    "event_type": "PROBE_EVENT",
                    "scene_id": "scene_1",
                    "audio_duration_ms": 1500,
                    "freeze_injected_ms": 300
                }
            }
        }
        res = self.client.post("/mcp", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32001)
        self.assertIn("Unauthorized", data["error"]["message"])

    def test_mcp_telemetry_junk_bearer_token_rejected(self):
        """Verify POST /mcp log_clickhouse_telemetry with junk Authorization header is rejected (anti-security-theater)."""
        payload = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_probe_test",
                    "event_type": "PROBE_EVENT",
                    "scene_id": "scene_1",
                    "audio_duration_ms": 1500,
                    "freeze_injected_ms": 300
                }
            }
        }
        res = self.client.post(
            "/mcp",
            json=payload,
            headers={"Authorization": "Bearer junk-not-a-real-key"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32001)
        self.assertIn("Unauthorized", data["error"]["message"])

    def test_mcp_telemetry_authenticated_success(self):
        """Verify POST /mcp log_clickhouse_telemetry with valid session token succeeds cleanly with no HTTP 500."""
        from server.core.user_token import sign_user_id
        user_id = sign_user_id("usr_mcp_auth_tester")
        payload = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_success_session",
                    "event_type": "MCP_SYNTH",
                    "scene_id": "scene_1",
                    "audio_duration_ms": 2500,
                    "freeze_injected_ms": 400
                }
            }
        }
        res = self.client.post(
            "/mcp",
            json=payload,
            headers={"X-FrameTalk-User-Id": user_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("error", data)
        self.assertIn("result", data)
        self.assertFalse(data["result"]["isError"])
        self.assertIn("Successfully streamed", data["result"]["content"][0]["text"])

    def test_mcp_telemetry_test_prefix_backdoor_rejected(self):
        """Verify the removed test_/usr_test_ bypass stays closed: junk prefixes are rejected with no network call."""
        payload = {
            "jsonrpc": "2.0",
            "id": 102,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_probe_test",
                    "event_type": "PROBE_EVENT"
                }
            }
        }
        res = self.client.post("/mcp", json=payload, headers={"X-API-Key": "test_123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32001)

    def test_mcp_telemetry_fake_aizasy_key_rejected_via_live_validation(self):
        """Verify AIza-format keys are live-validated against Google (fail-closed on 403), not format-trusted."""
        from unittest.mock import patch, MagicMock
        fake_resp = MagicMock()
        fake_resp.status_code = 403
        payload = {
            "jsonrpc": "2.0",
            "id": 103,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_probe_test",
                    "event_type": "PROBE_EVENT"
                }
            }
        }
        fake_key = "AIzaSy" + "A" * 33  # 39 chars, matches Google key format
        with patch("server.api.routers.mcp_router.requests.get", return_value=fake_resp) as mock_get:
            res = self.client.post("/mcp", json=payload, headers={"X-API-Key": fake_key})
            mock_get.assert_called_once()  # proves a live validation attempt happened
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32001)

    def test_mcp_telemetry_valid_google_key_accepted_via_live_validation(self):
        """Verify a Google-validated API key (mocked 200) is accepted and the telemetry write succeeds."""
        from unittest.mock import patch, MagicMock
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        payload = {
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "log_clickhouse_telemetry",
                "arguments": {
                    "session_id": "mcp_byok_valid",
                    "event_type": "PROBE_EVENT"
                }
            }
        }
        fake_key = "AIzaSy" + "B" * 33
        with patch("server.api.routers.mcp_router.requests.get", return_value=ok_resp):
            res = self.client.post("/mcp", json=payload, headers={"X-API-Key": fake_key})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("error", data)
        self.assertFalse(data["result"]["isError"])

    def test_mcp_callback_logs_agent_callback_event(self):
        """Verify MCP tool calls log AGENT_CALLBACK_RECEIVED with session_source attribution."""
        from server.repositories.telemetry_repository import telemetry_repository
        payload = {
            "jsonrpc": "2.0",
            "id": 105,
            "method": "tools/call",
            "params": {
                "name": "calculate_chronos_hold",
                "arguments": {
                    "speech_text": "Alex explains our distributed sync logic.",
                    "video_duration_ms": 1500,
                    "session_id": "mcp_provable_test",
                    "session_source": "agent_engine"
                }
            }
        }
        res = self.client.post("/mcp", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["result"]["isError"])

        # Inspect logged activities
        activities = telemetry_repository.get_user_activities(limit=10)
        callback_events = [a for a in activities if a.get("action_type") == "AGENT_CALLBACK_RECEIVED"]
        self.assertTrue(len(callback_events) > 0)
        latest = callback_events[0]
        self.assertIn("calculate_chronos_hold", latest.get("metadata", ""))
        self.assertIn("agent_engine", latest.get("metadata", ""))

    def test_studio_service_adk_director_dispatch_and_fallback(self):
        """Verify studio_service._orchestrate_with_adk_director executes without crashing and logs dispatch."""
        from server.services.studio_service import studio_service
        from server.repositories.telemetry_repository import telemetry_repository
        test_scenes = [{
            "scene_id": "test_scene_adk_1",
            "start_time_ms": 0,
            "end_time_ms": 5000,
            "duration_ms": 5000,
            "on_screen": "System Dashboard",
            "user_action": "Click Refresh",
            "app_reaction": "Data Reloaded"
        }]
        readme = "# Sample Documentation\nExplains the data flow."

        # Should execute safely and return None or script without throwing
        result = studio_service._orchestrate_with_adk_director(
            scenes=test_scenes,
            readme_text=readme
        )
        # Verify telemetry recorded the dispatch attempt
        activities = telemetry_repository.get_user_activities(limit=10)
        callback_events = [a for a in activities if a.get("action_type") == "AGENT_CALLBACK_RECEIVED"]
        self.assertTrue(len(callback_events) > 0)

if __name__ == "__main__":
    unittest.main()
