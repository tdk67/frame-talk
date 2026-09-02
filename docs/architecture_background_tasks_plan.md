# Frame Talk: Asynchronous Video Analysis & Distributed State Architecture

> **Architecture Proposal & RFC**  
> **Status:** Planning / TODO (Ready for implementation upon user approval)  
> **Target Subsystems:** `server/api/routers/ingest_router.py`, `server/services/studio_service.py`, `server/repositories/`

---

## 1. Objectives & Requirements

1. **Decouple Request-Response from Heavy AI Work**: Video analysis with `gemini-3.7-flash` takes 15–45 seconds. Long synchronous HTTP requests are vulnerable to proxy timeouts (e.g. Cloud Run 60s default timeout) and poor user experience.
2. **Deduplication & Concurrency Guard**:
   - Prevent identical videos from triggering duplicate expensive Gemini API calls simultaneously.
   - Return **HTTP 202 Accepted** for newly submitted videos queued for processing.
   - Return **HTTP 200 OK** if the video is already processing or has completed results.
   - Support `force=true` query flag to force re-analysis if desired.
3. **Thread-Safety & Race Condition Prevention**:
   - Single-instance mutex with **Double-Checked Locking** before entering critical section.
   - Distributed locking ready (via Redis / DB row locks) for horizontal multi-instance scaling.
4. **Load Balancer & Multi-Instance Compatibility**:
   - Instances behind a Round-Robin or Least-Connections Load Balancer must share job state so polling `GET /api/jobs/{id}` succeeds regardless of which node receives the poll.
5. **Data Retention & Lifecycle Management**:
   - Establish retention policies for video uploads vs. analysed scene descriptions.

---

## 2. API Contract Specification

### `POST /api/analyze-video`
* **Query Parameters:**
  - `force: bool = false` (Bypasses deduplication cache and re-analyzes).
* **Request Headers:**
  - `X-API-Key: string`
* **Request Body:**
  ```json
  {
    "video_filename": "Aufzeichnung 2026-08-30 094915.mp4",
    "video_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "readme_text": "# Idea Lint...",
    "video_duration_seconds": 262.0
  }
  ```
* **Responses:**
  * **HTTP 202 Accepted** (New job created & processing queued):
    ```json
    {
      "job_id": "job_9b1deb4d",
      "status": "PENDING",
      "created_at": "2026-09-02T15:15:00Z",
      "poll_url": "/api/analyze-video/job_9b1deb4d"
    }
    ```
  * **HTTP 200 OK** (Already submitted / cached / currently processing):
    ```json
    {
      "job_id": "job_9b1deb4d",
      "status": "PROCESSING",
      "progress_pct": 45,
      "message": "Analyzing multimodal video tokens with Gemini 3.7 Flash...",
      "created_at": "2026-09-02T15:14:30Z",
      "poll_url": "/api/analyze-video/job_9b1deb4d"
    }
    ```
  * **HTTP 400 Bad Request**: Validation failures (duration $< 30$s or $> 300$s, unsupported format).

---

### `GET /api/analyze-video/{job_id}`
* **Responses:**
  * **HTTP 200 OK** (When still running):
    ```json
    {
      "job_id": "job_9b1deb4d",
      "status": "PROCESSING",
      "progress_pct": 65,
      "scenes": null,
      "eval_scorecard": null
    }
    ```
  * **HTTP 200 OK** (When complete):
    ```json
    {
      "job_id": "job_9b1deb4d",
      "status": "DONE",
      "progress_pct": 100,
      "scenes": [ ... 9 forensic scenes ... ],
      "eval_scorecard": { "overall_score": 88, "passed": true },
      "completed_at": "2026-09-02T15:15:35Z"
    }
    ```
  * **HTTP 200 OK** (When failed):
    ```json
    {
      "job_id": "job_9b1deb4d",
      "status": "FAILED",
      "error": "QuotaExceededException: Gemini rate limit reached (429).",
      "can_retry": true
    }
    ```
  * **HTTP 404 Not Found**: If `job_id` does not exist in the database.

---

## 3. Concurrency Control: Double-Checked Locking Pattern

```python
import asyncio
from typing import Dict, Optional

class JobManager:
    def __init__(self, repository):
        self.repo = repository
        self._lock = asyncio.Lock()

    async def submit_analysis(
        self,
        video_hash: str,
        video_filename: str,
        readme_text: str,
        duration: float,
        api_key: Optional[str],
        force: bool = False
    ) -> Tuple[Dict[str, Any], int]:
        # --- Check 1 (Fast path outside lock) ---
        if not force:
            existing = await self.repo.get_job_by_video_hash(video_hash)
            if existing and existing.status in ("PENDING", "PROCESSING", "DONE"):
                return existing.to_dict(), 200  # Already submitted

        # --- Acquire Mutex ---
        async with self._lock:
            # --- Check 2 (Double-check inside critical section) ---
            if not force:
                existing = await self.repo.get_job_by_video_hash(video_hash)
                if existing and existing.status in ("PENDING", "PROCESSING", "DONE"):
                    return existing.to_dict(), 200

            # Create new PENDING record in shared database
            job = await self.repo.create_job(
                video_hash=video_hash,
                video_filename=video_filename,
                status="PENDING"
            )

            # Enqueue background task
            asyncio.create_task(self._execute_worker(job.id, video_filename, readme_text, duration, api_key))

            return job.to_dict(), 202  # Accepted
```

---

## 4. Multi-Instance State & Storage Retention

### The Load Balancer Problem
```
                     [ Client Browser ]
                              │
                     [ Load Balancer ]
                       /           \
           [ Server Node 1 ]    [ Server Node 2 ]
                 │                    │
                 └───► [ Shared DB ] ◄┘
```
If Instance 1 receives the `POST` and stores state in local Python memory, Instance 2 will return **404 Not Found** on the next polling request.

### Solution: Shared Persistence Layer
1. **ClickHouse or PostgreSQL Job Table**:
   - `video_jobs` table:
     * `job_id` (UUID)
     * `video_hash` (FixedString(64) / SHA-256)
     * `status` (Enum8: PENDING, PROCESSING, DONE, FAILED)
     * `scenes_json` (Nullable String)
     * `eval_scorecard_json` (Nullable String)
     * `created_at` (DateTime)
     * `updated_at` (DateTime)

### How Long to Store Analysed Video Descriptions?

| Artifact | Recommended TTL | Rationale |
| :--- | :--- | :--- |
| **Raw Video File** (`uploads/*.mp4`) | **24 to 48 hours** | Video files are large (100MB–500MB). Once Gemini finishes processing tokens and scenes are generated, the raw file is only needed for video compilation. |
| **Scene Descriptions & Scorecards** | **30 to 90 days** | JSON payload is lightweight (~15KB per video). 10,000 video analyses consume only ~150MB of DB storage. Allows founders to return and re-synthesize podcasts without re-paying LLM vision costs. |
| **Telemetry Sync Events** | **90 days** | ClickHouse time-series data for Grafana dashboards. |

---

## 5. Implementation Roadmap (TODO)

1. [ ] **Step 1:** Create `server/repositories/job_repository.py` backed by SQLite/ClickHouse.
2. [ ] **Step 2:** Refactor `ingest_router.py` to implement `POST /api/analyze-video` returning 202/200 and `GET /api/analyze-video/{job_id}`.
3. [ ] **Step 3:** Implement double-checked locking in `StudioService`.
4. [ ] **Step 4:** Update frontend `public/js/app.js` with polling progress indicator (`setInterval` polling every 2s until status is `DONE`).
