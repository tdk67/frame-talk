import os
import json
import uuid
import time
from typing import Dict, Any, Optional
from server.core.config import config

class JobRepository:
    def __init__(self):
        self.jobs_dir = config.uploads_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, job_id: str):
        import re
        from server.core.exceptions import InvalidInputException
        cleaned = job_id.strip()
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            raise InvalidInputException(f"Path traversal characters detected in job_id '{job_id}'.")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise InvalidInputException("Invalid job ID characters.")
        resolved = (self.jobs_dir / f"{cleaned}.json").resolve()
        if not resolved.is_relative_to(self.jobs_dir.resolve()):
            raise InvalidInputException("Job ID path traversal detected.")
        return resolved

    def create_job(self, job_id: Optional[str] = None) -> str:
        if not job_id:
            job_id = f"job_{uuid.uuid4().hex}"
        state = {
            "job_id": job_id,
            "status": "PENDING",
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "error": None
        }
        with open(self._get_path(job_id), "w", encoding="utf-8") as f:
            json.dump(state, f)
        return job_id

    def update_job(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        path = self._get_path(job_id)
        if not path.exists():
            return
            
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        state["status"] = status
        state["updated_at"] = time.time()
        if result is not None:
            state["result"] = result
        if error is not None:
            state["error"] = error
            
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_path(job_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

job_repository = JobRepository()
