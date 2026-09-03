"""
Unit Tests: Quota & Rate Limiting Service
Validates max 3 videos on hosted demo key, cost cap limits, and BYOK unlimited bypass.
"""

import unittest
import tempfile
from pathlib import Path
from server.services.quota_service import QuotaService

class TestQuotaService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "test_quotas.json"
        self.service = QuotaService(store_path=self.store_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_quota_state(self):
        """User starts with full demo quota (3 free videos)."""
        status = self.service.get_quota_status("user_test_alpha", has_custom_key=False)
        self.assertEqual(status["videos_used"], 0)
        self.assertEqual(status["videos_remaining"], 3)
        self.assertFalse(status["is_quota_exhausted"])
        self.assertTrue(status["hosted_mode"])

    def test_quota_exhaustion_after_three_videos(self):
        """User is capped after 3 videos on hosted demo key."""
        user_hash = "user_test_beta"

        # Video 1
        allowed, _, _ = self.service.check_quota(user_hash, has_custom_key=False)
        self.assertTrue(allowed)
        self.service.record_usage(user_hash, has_custom_key=False)

        # Video 2
        allowed, _, _ = self.service.check_quota(user_hash, has_custom_key=False)
        self.assertTrue(allowed)
        self.service.record_usage(user_hash, has_custom_key=False)

        # Video 3
        allowed, _, _ = self.service.check_quota(user_hash, has_custom_key=False)
        self.assertTrue(allowed)
        self.service.record_usage(user_hash, has_custom_key=False)

        # Video 4 (Should be BLOCKED)
        allowed, err_msg, status = self.service.check_quota(user_hash, has_custom_key=False)
        self.assertFalse(allowed)
        self.assertIn("Exhausted", err_msg)
        self.assertEqual(status["videos_remaining"], 0)
        self.assertTrue(status["is_quota_exhausted"])

    def test_byok_bypasses_quota(self):
        """Custom API key user (BYOK) has unlimited access and never exhausts quota."""
        user_hash = "user_test_gamma"

        # Record 10 usages with BYOK key
        for _ in range(10):
            allowed, _, status = self.service.check_quota(user_hash, has_custom_key=True)
            self.assertTrue(allowed)
            self.assertFalse(status["hosted_mode"])
            self.assertTrue(status["has_custom_key"])
            self.service.record_usage(user_hash, has_custom_key=True)

        status = self.service.get_quota_status(user_hash, has_custom_key=True)
        self.assertFalse(status["is_quota_exhausted"])
        self.assertEqual(status["videos_remaining"], 9999)

    def test_cost_cap_exhaustion(self):
        """User exceeding dollar limit on hosted key is capped."""
        user_hash = "user_test_delta"
        self.service.record_usage(user_hash, has_custom_key=False, cost_usd=1.05)

        allowed, err_msg, status = self.service.check_quota(user_hash, has_custom_key=False)
        self.assertFalse(allowed)
        self.assertTrue(status["is_quota_exhausted"])

    def test_missing_user_id_blocks_server_key(self):
        """When no user id is provided, using the server key is blocked; only BYOK is allowed."""
        user_hash = "user_anon_no_id"
        allowed, err_msg, status = self.service.check_quota(user_hash, has_custom_key=False, has_user_id=False)
        self.assertFalse(allowed)
        self.assertIn("Missing User ID", err_msg)
        self.assertTrue(status["is_quota_exhausted"])
        self.assertFalse(status["hosted_mode"])

        allowed_byok, _, status_byok = self.service.check_quota(user_hash, has_custom_key=True, has_user_id=False)
        self.assertTrue(allowed_byok)
        self.assertFalse(status_byok["is_quota_exhausted"])

if __name__ == "__main__":
    unittest.main()
