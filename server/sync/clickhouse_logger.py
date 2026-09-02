"""
ClickHouse Time-Series Logging Connector for CastOps AI.
Logs millisecond-precision synchronization events, audio durations,
freeze offsets, and generation observability metrics.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("castops.clickhouse")

# In-memory buffer fallback when ClickHouse service is offline
_in_memory_events: List[Dict[str, Any]] = []

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
        self._init_connection()

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
            # Create database and table
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
                    token_cost Float32
                ) ENGINE = MergeTree()
                ORDER BY (session_id, turn_index)
            """)
            self.is_connected = True
            logger.info(f"Connected to ClickHouse at {self.host}:{self.port} [{self.database}.sync_events]")
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
        now = datetime.utcnow()
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
        if self.is_connected and self.client:
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
        if self.is_connected and self.client:
            try:
                query = f"SELECT * FROM {self.database}.sync_events"
                if session_id:
                    query += f" WHERE session_id = '{session_id}'"
                query += f" ORDER BY event_time DESC LIMIT {limit}"
                result = self.client.query(query)
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

# Global singleton logger
ch_logger = ClickHouseLogger()
