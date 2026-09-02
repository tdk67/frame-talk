"""
Ingestion API Router: Uploads & Video Analysis
"""

from fastapi import APIRouter, UploadFile, File, Depends
from typing import Optional
from server.models.schemas import UploadResponse, AnalyzeRequest, AnalyzeResponse
from server.repositories.file_repository import file_repository
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
        v_name, v_path = await file_repository.save_uploaded_video(video, video.filename or "screencast.mp4")
        resp.video_filename = v_name
        resp.video_path = f"/uploads/{v_name}"
        resp.original_video_name = video.filename

    if readme:
        content = await readme.read()
        r_name, r_text, r_path = await file_repository.save_uploaded_readme(content, readme.filename or "README.md")
        resp.readme_filename = r_name
        resp.readme_text = r_text
        resp.original_readme_name = readme.filename

    return resp

@router.post("/analyze-video", response_model=AnalyzeResponse)
async def analyze_video(req: AnalyzeRequest, api_key: Optional[str] = Depends(get_api_key)):
    """Decomposes video tokens using Gemini 3.7 Flash with strict precision evaluation."""
    scenes, eval_scorecard = studio_service.analyze_video_screen(
        video_filename=req.video_filename,
        readme_text=req.readme_text,
        video_duration_seconds=req.video_duration_seconds,
        api_key=api_key
    )
    return AnalyzeResponse(
        scenes=scenes,
        eval_scorecard=eval_scorecard,
        total_scenes=len(scenes)
    )
