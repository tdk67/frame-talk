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

    def get_events(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self._logger.get_events(session_id=session_id, limit=limit)

    def get_metrics_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._logger.get_metrics_summary(session_id=session_id)

telemetry_repository = TelemetryRepository()
