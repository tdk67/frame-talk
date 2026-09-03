"""
Quota & Rate Limiting Service for Hosted Gemini Key.
Allows demo users to test Frame Talk with zero setup (hosted cloud key)
while strictly capping usage at max 3 videos and $1.00 per user.
BYOK users (bringing their own Gemini API key) enjoy unlimited generations.
"""

import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from server.core.config import config

logger = logging.getLogger("frametalk.service.quota")

class QuotaService:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or (config.uploads_dir / "user_quotas.json")
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._load_store()

    def _load_store(self):
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    self._memory_cache = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load user quotas: {e}; resetting cache.")
                self._memory_cache = {}

    def _save_store(self):
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user quotas: {e}")

    def get_quota_status(self, user_hash: str, has_custom_key: bool = False, has_user_id: bool = True) -> Dict[str, Any]:
        """Returns the current usage and quota status for a user."""
        has_server_key = bool(config.get_server_api_key() or config.vertex_ai_enabled)
        user_record = self._memory_cache.get(user_hash, {"videos_count": 0, "cost_usd": 0.0})

        videos_used = user_record.get("videos_count", 0)
        cost_used = user_record.get("cost_usd", 0.0)
        max_videos = config.max_hosted_videos_per_user
        max_cost = config.max_hosted_cost_per_user_usd

        if has_custom_key:
            return {
                "has_server_key": has_server_key,
                "has_custom_key": True,
                "hosted_mode": False,
                "videos_used": videos_used,
                "videos_remaining": 9999,
                "max_videos": 9999,
                "cost_usd": round(cost_used, 4),
                "cost_cap_usd": 999.0,
                "is_quota_exhausted": False,
                "message": "Unlimited runs active (BYOK Custom Key)"
            }

        # If no user ID provided and no custom key, server key is forbidden
        if not has_user_id:
            return {
                "has_server_key": has_server_key,
                "has_custom_key": False,
                "hosted_mode": False,
                "videos_used": videos_used,
                "videos_remaining": 0,
                "max_videos": max_videos,
                "cost_usd": round(cost_used, 4),
                "cost_cap_usd": max_cost,
                "is_quota_exhausted": True,
                "message": "User ID required for hosted demo key. Anonymous requests must provide their own Gemini API key (BYOK) via 'X-API-Key'."
            }

        videos_remaining = max(0, max_videos - videos_used)
        is_exhausted = (videos_used >= max_videos) or (cost_used >= max_cost)

        return {
            "has_server_key": has_server_key,
            "has_custom_key": False,
            "hosted_mode": True,
            "videos_used": videos_used,
            "videos_remaining": videos_remaining,
            "max_videos": max_videos,
            "cost_usd": round(cost_used, 4),
            "cost_cap_usd": max_cost,
            "is_quota_exhausted": is_exhausted,
            "message": (
                f"Hosted Demo Active: {videos_remaining}/{max_videos} free runs remaining"
                if not is_exhausted else
                f"Hosted demo quota exhausted ({videos_used}/{max_videos} videos used). Enter a Gemini API key for unlimited runs."
            )
        }

    def check_quota(self, user_hash: str, has_custom_key: bool = False, has_user_id: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates if the user is allowed to start a video analysis.
        Returns (is_allowed, error_message, quota_status).
        """
        status = self.get_quota_status(user_hash, has_custom_key, has_user_id=has_user_id)

        # BYOK users are always permitted
        if has_custom_key:
            return True, "", status

        # If no User ID provided, using server key from .env is forbidden
        if not has_user_id:
            return False, "Access Denied: Missing User ID. The hosted server key cannot be used without an 'X-FrameTalk-User-Id' header. Please provide your own Gemini API key (BYOK) via 'X-API-Key'.", status

        # If no server key and no custom key, cannot run
        if not status["has_server_key"]:
            return False, "No Gemini API key configured on server and no custom key provided. Please provide an API key.", status

        if status["is_quota_exhausted"]:
            msg = (
                f"Hosted Demo Quota Exhausted: You have used {status['videos_used']}/{status['max_videos']} "
                f"free video generations. To run unlimited video podcasts, please enter your free Google Gemini API key in Settings."
            )
            return False, msg, status

        return True, "", status

    def record_usage(self, user_hash: str, has_custom_key: bool = False, cost_usd: float = 0.0):
        """Records a completed or started video run for the user."""
        if user_hash not in self._memory_cache:
            self._memory_cache[user_hash] = {"videos_count": 0, "cost_usd": 0.0}

        if not has_custom_key:
            self._memory_cache[user_hash]["videos_count"] = self._memory_cache[user_hash].get("videos_count", 0) + 1
            self._memory_cache[user_hash]["cost_usd"] = self._memory_cache[user_hash].get("cost_usd", 0.0) + cost_usd
            self._save_store()

quota_service = QuotaService()
