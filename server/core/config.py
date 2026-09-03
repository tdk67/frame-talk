"""
Configuration Loader & Settings for Frame Talk
Reads config.json with environment variable fallback and typed properties.
"""

import os
import json
from typing import Dict, Any, List
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

ENV_PATH = BASE_DIR / ".env"

def _load_dotenv(env_path: Path):
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv(ENV_PATH)

class AppConfig:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @property
    def app_name(self) -> str:
        return self._data.get("app_name", "Frame Talk")

    @property
    def version(self) -> str:
        return self._data.get("version", "1.0.0")

    @property
    def domain(self) -> str:
        return os.getenv("APP_DOMAIN", self._data.get("domain", "taskmind-ai.com"))

    @property
    def app_subdomain(self) -> str:
        return os.getenv("APP_SUBDOMAIN", self._data.get("app_subdomain", "frame-talk"))

    @property
    def grafana_subdomain(self) -> str:
        return os.getenv("GRAFANA_SUBDOMAIN", self._data.get("grafana_subdomain", "grafana"))

    @property
    def app_url(self) -> str:
        env_url = os.getenv("APP_URL")
        if env_url:
            return env_url.rstrip("/")
        sub = f"{self.app_subdomain}." if self.app_subdomain else ""
        return f"https://{sub}{self.domain}".rstrip("/")

    @property
    def grafana_url(self) -> str:
        env_url = os.getenv("GRAFANA_URL")
        if env_url:
            return env_url.rstrip("/")
        sub = f"{self.grafana_subdomain}." if self.grafana_subdomain else ""
        return f"https://{sub}{self.domain}".rstrip("/")

    @property
    def cors_origins(self) -> List[str]:
        env_cors = os.getenv("CORS_ORIGINS")
        if env_cors:
            return [origin.strip() for origin in env_cors.split(",") if origin.strip()]
        return [
            self.app_url,
            self.grafana_url,
            f"https://{self.domain}",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3004",
            "http://127.0.0.1:3004",
        ]

    @property
    def vision_model(self) -> str:
        return os.getenv("VISION_MODEL", self._data.get("models", {}).get("vision_model", "gemini-3.7-flash"))

    @property
    def script_model(self) -> str:
        return os.getenv("SCRIPT_MODEL", self._data.get("models", {}).get("script_model", "gemini-3.7-flash"))

    @property
    def qa_model(self) -> str:
        return os.getenv("QA_MODEL", self._data.get("models", {}).get("qa_model", "gemini-3.7-flash"))

    @property
    def eval_model(self) -> str:
        return os.getenv("EVAL_MODEL", self._data.get("models", {}).get("eval_model", "gemini-3.7-flash"))

    @property
    def tts_model(self) -> str:
        return os.getenv("TTS_MODEL", self._data.get("models", {}).get("tts_model", "gemini-3.1-flash-tts-preview"))

    @property
    def default_male_voice(self) -> str:
        return self._data.get("voices", {}).get("default_male", "Puck")

    @property
    def default_female_voice(self) -> str:
        return self._data.get("voices", {}).get("default_female", "Kore")

    @property
    def max_retry_attempts(self) -> int:
        return self._data.get("retries", {}).get("max_attempts", 4)

    @property
    def initial_retry_delay_sec(self) -> float:
        return self._data.get("retries", {}).get("initial_delay_sec", 2.0)

    @property
    def backoff_multiplier(self) -> float:
        return self._data.get("retries", {}).get("backoff_multiplier", 2.0)

    @property
    def retriable_status_codes(self) -> List[int]:
        return self._data.get("retries", {}).get("retriable_status_codes", [429, 500, 502, 503, 504])

    @property
    def non_retriable_status_codes(self) -> List[int]:
        return self._data.get("retries", {}).get("non_retriable_status_codes", [400, 401, 403, 404])

    @property
    def file_processing_wait_max_sec(self) -> int:
        return self._data.get("timeouts", {}).get("file_processing_wait_max_sec", 180)

    @property
    def uploads_dir(self) -> Path:
        p = BASE_DIR / self._data.get("storage", {}).get("uploads_dir", "uploads")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_dir(self) -> Path:
        p = BASE_DIR / self._data.get("storage", {}).get("output_dir", "output")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def public_dir(self) -> Path:
        p = BASE_DIR / self._data.get("storage", {}).get("public_dir", "public")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def clickhouse_host(self) -> str:
        return os.getenv("CLICKHOUSE_HOST", self._data.get("clickhouse", {}).get("host", "localhost"))

    @property
    def clickhouse_port(self) -> int:
        return int(os.getenv("CLICKHOUSE_PORT", self._data.get("clickhouse", {}).get("port", 8123)))

    @property
    def clickhouse_database(self) -> str:
        return self._data.get("clickhouse", {}).get("database", "castops")

    @property
    def min_video_duration_sec(self) -> float:
        return float(self._data.get("video_limits", {}).get("min_duration_seconds", 30.0))

    @property
    def max_video_duration_sec(self) -> float:
        return float(self._data.get("video_limits", {}).get("max_duration_seconds", 300.0))

    @property
    def max_video_size_mb(self) -> float:
        return float(self._data.get("video_limits", {}).get("max_file_size_mb", 500.0))

    @property
    def supported_video_extensions(self) -> List[str]:
        return self._data.get("video_limits", {}).get("supported_extensions", [".mp4", ".webm", ".mov", ".mkv"])

    @property
    def vertex_ai_enabled(self) -> bool:
        env_val = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")
        return bool(self._data.get("vertex_ai", {}).get("enabled", False))

    @property
    def google_cloud_project(self) -> str:
        return os.getenv("GOOGLE_CLOUD_PROJECT", self._data.get("vertex_ai", {}).get("project", "agentic-cinema-frametalk"))

    @property
    def google_cloud_location(self) -> str:
        return os.getenv("GOOGLE_CLOUD_LOCATION", self._data.get("vertex_ai", {}).get("location", "us-west1"))

    @property
    def google_cloud_agent_id(self) -> str:
        return os.getenv("GOOGLE_CLOUD_AGENT_ID", self._data.get("vertex_ai", {}).get("agent_id", "agent_1788438917580"))

    @property
    def max_hosted_videos_per_user(self) -> int:
        return int(os.getenv("MAX_HOSTED_VIDEOS_PER_USER", self._data.get("quota", {}).get("max_hosted_videos_per_user", 3)))

    @property
    def max_hosted_cost_per_user_usd(self) -> float:
        return float(os.getenv("MAX_HOSTED_COST_PER_USER_USD", self._data.get("quota", {}).get("max_hosted_cost_per_user_usd", 1.00)))

    def get_server_api_key(self) -> str:
        """Returns the server-configured Gemini/Google API key if set."""
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""

config = AppConfig()
