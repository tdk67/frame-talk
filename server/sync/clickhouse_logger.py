"""
ClickHouse Time-Series Logging Connector for CastOps AI.
Logs millisecond-precision synchronization events, audio durations,
freeze offsets, and generation observability metrics.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("castops.clickhouse")

# In-memory buffer fallback when ClickHouse service is offline
_in_memory_events: List[Dict[str, Any]] = []
_in_memory_llm_calls: List[Dict[str, Any]] = []
_in_memory_user_activities: List[Dict[str, Any]] = []

class ClickHouseLogger:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 database: str = "castops"):
        self.host = host or os.getenv("CLICKHOUSE_HOST", "localhost")
        self.port = port or int(os.getenv("CLICKHOUSE_PORT", "8123"))
        self.username = username or os.getenv("CLICKHOUSE_USER", "default")
        self.password = password or os.getenv("CLICKHOUSE_PASSWORD", "")
        self.database = database
        self.client = None
        self.is_connected = False
        self._last_connect_attempt = 0.0
        self._init_connection()

    def check_connection(self) -> bool:
        """Dynamically attempts reconnection if not currently connected."""
        if self.is_connected and self.client:
            return True
        now = time.time()
        if now - self._last_connect_attempt > 10.0:
            self._last_connect_attempt = now
            self._init_connection()
        return self.is_connected

    def _init_connection(self):
        import socket
        try:
            # Fast non-blocking socket probe (200ms) to avoid multi-second driver timeout
            with socket.create_connection((self.host, self.port), timeout=0.2):
                pass
        except Exception:
            self.is_connected = False
            logger.info(f"ClickHouse not detected at {self.host}:{self.port}. Operating in resilient in-memory observability mode.")
            return

        try:
            import clickhouse_connect
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                connect_timeout=2
            )
            # Create database and tables
            self.client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            self.client.command(f"""
                CREATE TABLE IF NOT EXISTS {self.database}.sync_events (
                    event_time DateTime64(3),
                    session_id String,
                    turn_index UInt16,
                    speaker LowCardinality(String),
                    dialogue_text String,
                    audio_clip_path String,
                    audio_duration_ms UInt32,
                    video_scene_start_ms UInt32,
                    video_scene_end_ms UInt32,
                    video_scene_duration_ms UInt32,
                    required_freeze_ms UInt32,
                    accumulated_drift_ms Int32,
                    pacing_status LowCardinality(String),
                    token_cost Float32,
                    user_hash LowCardinality(String) DEFAULT ''
                ) ENGINE = MergeTree()
                ORDER BY (session_id, turn_index)
            """)
            self.client.command(f"""
                CREATE TABLE IF NOT EXISTS {self.database}.llm_calls (
                    call_time DateTime64(3),
                    session_id String,
                    agent_name LowCardinality(String),
                    model_name LowCardinality(String),
                    prompt_tokens UInt32,
                    completion_tokens UInt32,
                    total_tokens UInt32,
                    cost_usd Float64,
                    latency_ms UInt32,
                    status LowCardinality(String),
                    user_hash LowCardinality(String) DEFAULT ''
                ) ENGINE = MergeTree()
                ORDER BY (session_id, call_time)
            """)
            self.client.command(f"""
                CREATE TABLE IF NOT EXISTS {self.database}.user_activity (
                    event_time DateTime64(3),
                    user_hash LowCardinality(String),
                    action_type LowCardinality(String),
                    session_id String,
                    metadata String
                ) ENGINE = MergeTree()
                ORDER BY (user_hash, event_time)
            """)
            self.is_connected = True
            logger.info(f"Connected to ClickHouse at {self.host}:{self.port} [{self.database}.sync_events, {self.database}.llm_calls, {self.database}.user_activity]")
        except Exception as e:
            self.is_connected = False
            logger.warning(f"ClickHouse server unavailable at {self.host}:{self.port} ({e}). Using in-memory observability buffer.")

    def log_sync_event(self,
                       session_id: str,
                       turn_index: int,
                       speaker: str,
                       dialogue_text: str,
                       audio_clip_path: str,
                       audio_duration_ms: int,
                       video_scene_start_ms: int,
                       video_scene_end_ms: int,
                       video_scene_duration_ms: int,
                       required_freeze_ms: int,
                       accumulated_drift_ms: int = 0,
                       pacing_status: str = "SYNCHRONIZED",
                       token_cost: float = 0.0) -> Dict[str, Any]:
        """
        Logs a micro-dialogue synchronization event down to millisecond precision.
        """
        now = datetime.now(timezone.utc)
        event_dict = {
            "event_time": now.isoformat(),
            "session_id": session_id,
            "turn_index": turn_index,
            "speaker": speaker,
            "dialogue_text": dialogue_text,
            "audio_clip_path": audio_clip_path,
            "audio_duration_ms": audio_duration_ms,
            "video_scene_start_ms": video_scene_start_ms,
            "video_scene_end_ms": video_scene_end_ms,
            "video_scene_duration_ms": video_scene_duration_ms,
            "required_freeze_ms": required_freeze_ms,
            "accumulated_drift_ms": accumulated_drift_ms,
            "pacing_status": pacing_status,
            "token_cost": token_cost
        }

        # Store in memory for instant API observability queries
        _in_memory_events.append(event_dict)
        if len(_in_memory_events) > 500:
            _in_memory_events.pop(0)

        # Write to ClickHouse if connected
        if self.check_connection() and self.client:
            try:
                row = [
                    now,
                    session_id,
                    turn_index,
                    speaker,
                    dialogue_text,
                    audio_clip_path,
                    audio_duration_ms,
                    video_scene_start_ms,
                    video_scene_end_ms,
                    video_scene_duration_ms,
                    required_freeze_ms,
                    accumulated_drift_ms,
                    pacing_status,
                    token_cost
                ]
                self.client.insert(f"{self.database}.sync_events", [row],
                                   column_names=[
                                       "event_time", "session_id", "turn_index", "speaker",
                                       "dialogue_text", "audio_clip_path", "audio_duration_ms",
                                       "video_scene_start_ms", "video_scene_end_ms",
                                       "video_scene_duration_ms", "required_freeze_ms",
                                       "accumulated_drift_ms", "pacing_status", "token_cost"
                                   ])
            except Exception as e:
                logger.error(f"Failed to insert row into ClickHouse: {e}")

        return event_dict

    def get_events(self, session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves recent sync events for display in the Observability Studio.
        """
        if self.check_connection() and self.client:
            try:
                query = f"SELECT * FROM {self.database}.sync_events"
                params = {}
                if session_id:
                    query += " WHERE session_id = %(session_id)s"
                    params["session_id"] = str(session_id).strip()
                query += f" ORDER BY event_time DESC LIMIT {max(1, min(int(limit), 500))}"
                result = self.client.query(query, parameters=params)
                columns = result.column_names
                events = []
                for row in result.result_rows:
                    row_dict = dict(zip(columns, row))
                    if isinstance(row_dict.get("event_time"), datetime):
                        row_dict["event_time"] = row_dict["event_time"].isoformat()
                    events.append(row_dict)
                return events
            except Exception as e:
                logger.warning(f"Error querying ClickHouse ({e}), falling back to in-memory events.")

        # Fallback to in-memory
        if session_id:
            filtered = [e for e in _in_memory_events if e["session_id"] == session_id]
            return filtered[-limit:]
        return _in_memory_events[-limit:]

    def get_metrics_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates aggregated pipeline metrics (total freeze time, latency, drift).
        """
        events = self.get_events(session_id=session_id, limit=200)
        if not events:
            return {
                "total_events": 0,
                "total_audio_duration_ms": 0,
                "total_freeze_injected_ms": 0,
                "avg_audio_duration_ms": 0,
                "max_drift_ms": 0,
                "status": "AWAITING_RUN"
            }

        total_audio = sum(e.get("audio_duration_ms", 0) for e in events)
        total_freeze = sum(e.get("required_freeze_ms", 0) for e in events)
        drifts = [abs(e.get("accumulated_drift_ms", 0)) for e in events]
        max_drift = max(drifts) if drifts else 0

        return {
            "total_events": len(events),
            "total_audio_duration_ms": total_audio,
            "total_freeze_injected_ms": total_freeze,
            "avg_audio_duration_ms": round(total_audio / len(events), 2) if events else 0,
            "max_drift_ms": max_drift,
            "status": "OPTIMAL_SYNC" if max_drift < 200 else "DRIFT_CORRECTED"
        }

    def log_llm_call(self,
                     session_id: str,
                     agent_name: str,
                     model_name: str,
                     prompt_tokens: int = 0,
                     completion_tokens: int = 0,
                     total_tokens: int = 0,
                     cost_usd: float = 0.0,
                     latency_ms: int = 0,
                     status: str = "SUCCESS") -> Dict[str, Any]:
        """
        Logs an individual LLM or TTS model invocation for observability and cost tracking.
        """
        now = datetime.now(timezone.utc)
        tot_tok = total_tokens or (prompt_tokens + completion_tokens)
        call_dict = {
            "call_time": now.isoformat(),
            "session_id": session_id,
            "agent_name": agent_name,
            "model_name": model_name,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(tot_tok),
            "cost_usd": round(float(cost_usd), 6),
            "latency_ms": int(latency_ms),
            "status": status
        }

        # Store in-memory buffer
        _in_memory_llm_calls.append(call_dict)
        if len(_in_memory_llm_calls) > 500:
            _in_memory_llm_calls.pop(0)

        # Write to ClickHouse if connected
        if self.check_connection() and self.client:
            try:
                row = [
                    now,
                    session_id,
                    agent_name,
                    model_name,
                    int(prompt_tokens),
                    int(completion_tokens),
                    int(tot_tok),
                    float(cost_usd),
                    int(latency_ms),
                    status
                ]
                self.client.insert(
                    f"{self.database}.llm_calls",
                    [row],
                    column_names=[
                        "call_time", "session_id", "agent_name", "model_name",
                        "prompt_tokens", "completion_tokens", "total_tokens",
                        "cost_usd", "latency_ms", "status"
                    ]
                )
            except Exception as e:
                logger.error(f"Failed to insert row into ClickHouse llm_calls: {e}")

        return call_dict

    def get_llm_calls(self, session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent LLM invocations."""
        if self.check_connection() and self.client:
            try:
                query = f"SELECT * FROM {self.database}.llm_calls"
                params = {}
                if session_id:
                    query += " WHERE session_id = %(session_id)s"
                    params["session_id"] = str(session_id).strip()
                query += f" ORDER BY call_time DESC LIMIT {max(1, min(int(limit), 500))}"
                result = self.client.query(query, parameters=params)
                columns = result.column_names
                calls = []
                for row in result.result_rows:
                    row_dict = dict(zip(columns, row))
                    if isinstance(row_dict.get("call_time"), datetime):
                        row_dict["call_time"] = row_dict["call_time"].isoformat()
                    calls.append(row_dict)
                return calls
            except Exception as e:
                logger.warning(f"Error querying ClickHouse llm_calls ({e}), using in-memory buffer.")

        if session_id:
            return [c for c in _in_memory_llm_calls if c["session_id"] == session_id][-limit:]
        return _in_memory_llm_calls[-limit:]

    def get_llm_metrics_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates total calls, token consumption, and cost per model and agent."""
        calls = self.get_llm_calls(session_id=session_id, limit=500)
        total_calls = len(calls)
        total_prompt = sum(c.get("prompt_tokens", 0) for c in calls)
        total_completion = sum(c.get("completion_tokens", 0) for c in calls)
        total_tokens = sum(c.get("total_tokens", 0) for c in calls)
        total_cost = sum(c.get("cost_usd", 0.0) for c in calls)

        by_model = {}
        by_agent = {}
        for c in calls:
            m = c.get("model_name", "unknown")
            a = c.get("agent_name", "unknown")

            if m not in by_model:
                by_model[m] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
            by_model[m]["calls"] += 1
            by_model[m]["prompt_tokens"] += c.get("prompt_tokens", 0)
            by_model[m]["completion_tokens"] += c.get("completion_tokens", 0)
            by_model[m]["total_tokens"] += c.get("total_tokens", 0)
            by_model[m]["cost_usd"] = round(by_model[m]["cost_usd"] + c.get("cost_usd", 0.0), 6)

            if a not in by_agent:
                by_agent[a] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_agent[a]["calls"] += 1
            by_agent[a]["tokens"] += c.get("total_tokens", 0)
            by_agent[a]["cost_usd"] = round(by_agent[a]["cost_usd"] + c.get("cost_usd", 0.0), 6)

        return {
            "total_llm_calls": total_calls,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "formatted_cost": f"${total_cost:.4f} USD",
            "by_model": by_model,
            "by_agent": by_agent
        }

    def log_user_activity(self,
                          user_hash: str,
                          action_type: str,
                          session_id: str = "",
                          metadata: str = "") -> Dict[str, Any]:
        """
        Logs an anonymous user action to ClickHouse with zero PII.
        action_type can be: 'VIDEO_ANALYZED', 'SCRIPT_GENERATED', 'AUDIO_SYNTHESIZED', 'VIDEO_COMPILED'
        """
        now = datetime.now(timezone.utc)
        record = {
            "event_time": now.isoformat(),
            "user_hash": user_hash or "anon_unknown",
            "action_type": action_type.upper(),
            "session_id": session_id or "",
            "metadata": metadata or ""
        }

        if self.check_connection():
            try:
                row = [now, record["user_hash"], record["action_type"], record["session_id"], record["metadata"]]
                self.client.insert(
                    f"{self.database}.user_activity",
                    [row],
                    column_names=["event_time", "user_hash", "action_type", "session_id", "metadata"]
                )
                return record
            except Exception as e:
                logger.warning(f"Failed to log user activity to ClickHouse ({e}). Buffering in memory.")

        _in_memory_user_activities.append(record)
        if len(_in_memory_user_activities) > 10000:
            _in_memory_user_activities.pop(0)
        return record

    def get_user_activities(self, limit: int = 50, user_hash: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves recent user activities."""
        if self.check_connection():
            try:
                query = f"SELECT event_time, user_hash, action_type, session_id, metadata FROM {self.database}.user_activity"
                params = {}
                if user_hash:
                    query += " WHERE user_hash = %(user_hash)s"
                    params["user_hash"] = user_hash
                query += f" ORDER BY event_time DESC LIMIT {int(limit)}"
                result = self.client.query(query, parameters=params)
                activities = []
                for row in result.result_rows:
                    activities.append({
                        "event_time": str(row[0]),
                        "user_hash": row[1],
                        "action_type": row[2],
                        "session_id": row[3],
                        "metadata": row[4]
                    })
                return activities
            except Exception as e:
                logger.warning(f"Querying user_activity from ClickHouse failed: {e}")

        filtered = _in_memory_user_activities
        if user_hash:
            filtered = [a for a in filtered if a.get("user_hash") == user_hash]
        return list(reversed(filtered))[:limit]

    def get_user_statistics_summary(self) -> Dict[str, Any]:
        """
        Aggregates anonymous user statistics: total users, conversion funnel,
        and action distributions (Average, Min, Max actions per user).
        """
        all_activities = self.get_user_activities(limit=10000)

        # 1. Unique users
        unique_users = set(a.get("user_hash") for a in all_activities if a.get("user_hash"))
        total_unique_users = len(unique_users)

        # 2. Funnel metrics
        funnel = {
            "VIDEO_ANALYZED": 0,
            "SCRIPT_GENERATED": 0,
            "AUDIO_SYNTHESIZED": 0,
            "VIDEO_COMPILED": 0
        }
        user_action_counts: Dict[str, Dict[str, int]] = {}

        for a in all_activities:
            act = a.get("action_type", "").upper()
            u = a.get("user_hash", "")
            if act in funnel:
                funnel[act] += 1
            if u:
                if u not in user_action_counts:
                    user_action_counts[u] = {}
                user_action_counts[u][act] = user_action_counts[u].get(act, 0) + 1

        # 3. Compute distributions per action: avg, min, max
        distributions = {}
        for act in ["VIDEO_ANALYZED", "SCRIPT_GENERATED", "AUDIO_SYNTHESIZED", "VIDEO_COMPILED"]:
            user_counts = [counts.get(act, 0) for counts in user_action_counts.values() if counts.get(act, 0) > 0]
            if user_counts:
                distributions[act] = {
                    "avg_per_user": round(sum(user_counts) / len(user_counts), 2),
                    "min_per_user": min(user_counts),
                    "max_per_user": max(user_counts),
                    "active_users": len(user_counts)
                }
            else:
                distributions[act] = {
                    "avg_per_user": 0.0,
                    "min_per_user": 0,
                    "max_per_user": 0,
                    "active_users": 0
                }

        return {
            "total_unique_users": total_unique_users,
            "total_activity_events": len(all_activities),
            "funnel": funnel,
            "distributions": distributions
        }

# Global singleton logger
ch_logger = ClickHouseLogger()

