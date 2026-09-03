"""
Telemetry Repository: Persistence adapter for ClickHouse time-series event storage.
"""

from typing import Optional, List, Dict, Any
from server.sync.clickhouse_logger import ch_logger

class TelemetryRepository:
    def __init__(self):
        self._logger = ch_logger

    @property
    def is_connected(self) -> bool:
        return self._logger.check_connection()

    @property
    def host_info(self) -> str:
        return f"{self._logger.host}:{self._logger.port}"

    def log_sync_event(self, **kwargs: Any) -> bool:
        return self._logger.log_sync_event(**kwargs)

    def log_llm_call(self, **kwargs: Any) -> Dict[str, Any]:
        return self._logger.log_llm_call(**kwargs)

    def get_events(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self._logger.get_events(session_id=session_id, limit=limit)

    def get_llm_calls(self, session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._logger.get_llm_calls(session_id=session_id, limit=limit)

    def get_metrics_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._logger.get_metrics_summary(session_id=session_id)

    def get_llm_metrics_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._logger.get_llm_metrics_summary(session_id=session_id)

    def log_user_activity(self, user_hash: str, action_type: str, session_id: str = "", metadata: str = "") -> Dict[str, Any]:
        return self._logger.log_user_activity(user_hash=user_hash, action_type=action_type, session_id=session_id, metadata=metadata)

    def log_agent_callback(self, session_id: str, tool_name: str, session_source: str = "agent_engine", metadata: str = "") -> Dict[str, Any]:
        return self._logger.log_agent_callback(session_id=session_id, tool_name=tool_name, session_source=session_source, metadata=metadata)

    def get_user_activities(self, limit: int = 50, user_hash: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._logger.get_user_activities(limit=limit, user_hash=user_hash)

    def get_user_statistics_summary(self) -> Dict[str, Any]:
        return self._logger.get_user_statistics_summary()

telemetry_repository = TelemetryRepository()

