"""
Quota & Rate Limiting Service for Hosted Gemini Key.
Enforces multi-layer financial and security defense:
1. IP-Bound Compound Quota: Max 3 videos and $1.00 per IP address across all user IDs.
2. Global Daily Circuit Breaker: Hard cap on total platform hosted expenditure per 24 hours (configurable).
3. User ID Checksum: Requires valid cryptographically signed session tokens to use hosted key.
4. BYOK Bypass: Users providing custom Gemini API keys enjoy unlimited runs.
"""

import os
import json
import logging
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from datetime import datetime, timezone
from server.core.config import config

logger = logging.getLogger("frametalk.service.quota")

class QuotaService:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or (config.uploads_dir / "user_quotas.json")
        self._memory_cache: Dict[str, Any] = {
            "users": {},
            "ips": {},
            "global_daily": {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "videos_count": 0,
                "cost_usd": 0.0
            }
        }
        self._load_store()

    def _load_store(self):
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    if isinstance(raw_data, dict):
                        if "users" in raw_data or "global_daily" in raw_data:
                            self._memory_cache = raw_data
                        else:
                            # Migrate legacy flat user dictionary
                            self._memory_cache = {
                                "users": raw_data,
                                "ips": {},
                                "global_daily": {
                                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                    "videos_count": 0,
                                    "cost_usd": 0.0
                                }
                            }
            except Exception as e:
                logger.warning(f"Failed to load user quotas: {e}; resetting cache.")

    def _save_store(self):
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user quotas: {e}")

    def _check_and_rollover_global_daily(self) -> Dict[str, Any]:
        """Ensures global daily usage resets automatically at UTC midnight."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self._memory_cache.setdefault("global_daily", {
            "date": today,
            "videos_count": 0,
            "cost_usd": 0.0
        })
        if daily.get("date") != today:
            daily["date"] = today
            daily["videos_count"] = 0
            daily["cost_usd"] = 0.0
            self._save_store()
        return daily

    def get_quota_status(
        self,
        user_hash: str,
        ip_hash: Optional[str] = None,
        has_custom_key: bool = False,
        has_user_id: bool = True
    ) -> Dict[str, Any]:
        """Returns the current usage and quota status for a user, IP, and platform."""
        has_server_key = bool(config.get_server_api_key())
        users_store = self._memory_cache.setdefault("users", {})
        ips_store = self._memory_cache.setdefault("ips", {})
        daily = self._check_and_rollover_global_daily()

        user_record = users_store.get(user_hash, {"videos_count": 0, "cost_usd": 0.0})
        ip_record = ips_store.get(ip_hash, {"videos_count": 0, "cost_usd": 0.0}) if ip_hash else {"videos_count": 0, "cost_usd": 0.0}

        videos_used = max(user_record.get("videos_count", 0), ip_record.get("videos_count", 0))
        cost_used = max(user_record.get("cost_usd", 0.0), ip_record.get("cost_usd", 0.0))

        max_videos = config.max_hosted_videos_per_user
        max_cost = config.max_hosted_cost_per_user_usd
        global_max_videos = config.global_daily_max_hosted_videos
        global_max_cost = config.global_daily_max_hosted_cost_usd

        # 1. Custom BYOK users are always unlimited
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

        # 2. Missing or unverified User ID: Server key is strictly forbidden
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
                "message": "Missing User ID: Verified session token required for hosted demo key. Please obtain a signed session token from /api/auth/session or enter your own Gemini API key (BYOK)."
            }

        # 3. Global Daily Circuit Breaker: Protects against runaway costs
        if daily.get("videos_count", 0) >= global_max_videos or daily.get("cost_usd", 0.0) >= global_max_cost:
            return {
                "has_server_key": has_server_key,
                "has_custom_key": False,
                "hosted_mode": False,
                "videos_used": daily.get("videos_count", 0),
                "videos_remaining": 0,
                "max_videos": global_max_videos,
                "cost_usd": round(daily.get("cost_usd", 0.0), 4),
                "cost_cap_usd": global_max_cost,
                "is_quota_exhausted": True,
                "circuit_breaker_tripped": True,
                "message": (
                    f"Platform Daily Limit Reached: Hosted demo capacity is temporarily paused for today "
                    f"({daily.get('videos_count', 0)}/{global_max_videos} runs, ${daily.get('cost_usd', 0.0):.2f}/${global_max_cost:.2f} budget). "
                    f"Please enter your free Google Gemini API key (BYOK) in Settings to continue."
                )
            }

        # 4. IP-level Quota: Prevents cycling through random user IDs on the same IP
        if ip_hash and (ip_record.get("videos_count", 0) >= max_videos or ip_record.get("cost_usd", 0.0) >= max_cost):
            return {
                "has_server_key": has_server_key,
                "has_custom_key": False,
                "hosted_mode": True,
                "videos_used": ip_record.get("videos_count", 0),
                "videos_remaining": 0,
                "max_videos": max_videos,
                "cost_usd": round(ip_record.get("cost_usd", 0.0), 4),
                "cost_cap_usd": max_cost,
                "is_quota_exhausted": True,
                "message": f"IP Quota Limit Reached: This IP has used all {max_videos} free demo runs. Enter your own Gemini API key (BYOK) for unlimited generations."
            }

        # 5. User-level Quota
        user_videos = user_record.get("videos_count", 0)
        user_cost = user_record.get("cost_usd", 0.0)
        videos_remaining = max(0, max_videos - videos_used)
        is_exhausted = (user_videos >= max_videos) or (user_cost >= max_cost)

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
            "global_daily_videos_used": daily.get("videos_count", 0),
            "message": (
                f"Hosted Demo Active: {videos_remaining}/{max_videos} free runs remaining"
                if not is_exhausted else
                f"Hosted Demo Quota Exhausted ({user_videos}/{max_videos} videos used). Enter a Gemini API key for unlimited runs."
            )
        }

    def check_quota(
        self,
        user_hash: str,
        ip_hash: Optional[str] = None,
        has_custom_key: bool = False,
        has_user_id: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates if the user is allowed to start a video analysis.
        Returns (is_allowed, error_message, quota_status).
        """
        status = self.get_quota_status(
            user_hash=user_hash,
            ip_hash=ip_hash,
            has_custom_key=has_custom_key,
            has_user_id=has_user_id
        )

        # BYOK users are always permitted
        if has_custom_key:
            return True, "", status

        # Reject unverified or missing User ID
        if not has_user_id:
            return False, status["message"], status

        # Reject if server has no key configured
        if not status["has_server_key"]:
            return False, "No Gemini API key configured on server and no custom key provided. Please provide an API key.", status

        if status["is_quota_exhausted"]:
            return False, status["message"], status

        return True, "", status

    def record_usage(
        self,
        user_hash: str,
        ip_hash: Optional[str] = None,
        has_custom_key: bool = False,
        cost_usd: float = 0.0
    ):
        """Records a completed or started video run across user, IP, and platform tiers."""
        if not has_custom_key:
            users_store = self._memory_cache.setdefault("users", {})
            ips_store = self._memory_cache.setdefault("ips", {})
            daily = self._check_and_rollover_global_daily()

            # Increment User Tier
            user_rec = users_store.setdefault(user_hash, {"videos_count": 0, "cost_usd": 0.0})
            user_rec["videos_count"] += 1
            user_rec["cost_usd"] += cost_usd

            # Increment IP Tier
            if ip_hash:
                ip_rec = ips_store.setdefault(ip_hash, {"videos_count": 0, "cost_usd": 0.0})
                ip_rec["videos_count"] += 1
                ip_rec["cost_usd"] += cost_usd

            # Increment Global Daily Tier
            daily["videos_count"] += 1
            daily["cost_usd"] += cost_usd

            self._save_store()

quota_service = QuotaService()
