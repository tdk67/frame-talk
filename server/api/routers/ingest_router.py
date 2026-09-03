"""
Ingestion API Router: Uploads & Video Analysis
"""

from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from typing import Optional
from server.models.schemas import UploadResponse, AnalyzeRequest, AnalyzeResponse
from server.repositories.file_repository import file_repository
from server.repositories.job_repository import job_repository
from server.services.studio_service import studio_service
from server.api.dependencies import get_api_key

router = APIRouter(prefix="/api", tags=["1. Ingestion & Analysis"])

@router.post("/upload", response_model=UploadResponse)
async def upload_assets(
    video: Optional[UploadFile] = File(None),
    readme: Optional[UploadFile] = File(None)
):
    """Ingests raw screencast (.mp4) and project README.md text."""
    resp = UploadResponse()
    if video:
        v_name, v_path, v_hash = await file_repository.save_uploaded_video(video, video.filename or "screencast.mp4")
        resp.video_filename = v_name
        resp.video_path = f"/uploads/{v_name}"
        resp.original_video_name = video.filename
        resp.video_hash = v_hash

    if readme:
        content = await readme.read()
        r_name, r_text, r_path = await file_repository.save_uploaded_readme(content, readme.filename or "README.md")
        resp.readme_filename = r_name
        resp.readme_text = r_text
        resp.original_readme_name = readme.filename

    return resp

from fastapi import Response, Request
from server.repositories.telemetry_repository import telemetry_repository

@router.post("/analyze-video")
async def analyze_video(
    req: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    request: Request,
    api_key: Optional[str] = Depends(get_api_key)
):
    """Dispatches video analysis to a background worker or returns existing job status."""
    import uuid
    user_hash = getattr(request.state, "user_hash", "anon_default")
    job_id = req.video_hash or f"job_{uuid.uuid4().hex}"
    
    job = job_repository.get_job(job_id, user_hash=user_hash)
    if job:
        response.status_code = 200
        return {"job_id": job_id, "status": job["status"]}

    job_repository.create_job(job_id=job_id, user_hash=user_hash)
    
    # Log user activity event
    telemetry_repository.log_user_activity(
        user_hash=user_hash,
        action_type="VIDEO_ANALYZED",
        session_id=job_id,
        metadata=f"video:{req.video_filename},dur:{req.video_duration_seconds}"
    )
    
    background_tasks.add_task(
        studio_service.run_video_analysis_job,
        job_id=job_id,
        video_filename=req.video_filename,
        readme_text=req.readme_text,
        video_duration_seconds=req.video_duration_seconds,
        api_key=api_key,
        video_hash=req.video_hash
    )
    
    response.status_code = 202
    return {"job_id": job_id, "status": "PENDING"}

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    """Polls the background worker job status with multi-user isolation."""
    user_hash = getattr(request.state, "user_hash", None)
    job = job_repository.get_job(job_id, user_hash=user_hash)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

