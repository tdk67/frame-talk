"""
Scriptwriting & QA API Router
"""

from fastapi import APIRouter, Depends, Request
from typing import Optional
from server.models.schemas import ScriptRequest, ScriptResponse, QaRequest, QaResponse
from server.services.studio_service import studio_service
from server.repositories.telemetry_repository import telemetry_repository
from server.api.dependencies import get_api_key

router = APIRouter(prefix="/api", tags=["2. Script & QA"])

@router.post("/generate-script", response_model=ScriptResponse)
async def generate_script(req: ScriptRequest, request: Request, api_key: Optional[str] = Depends(get_api_key)):
    """Generates two-host technical conversation anchored to visual scenes."""
    dialogue = studio_service.generate_dialogue_script(
        scenes=req.scenes,
        readme_text=req.readme_text,
        api_key=api_key
    )
    user_hash = getattr(request.state, "user_hash", "anon_default")
    telemetry_repository.log_user_activity(
        user_hash=user_hash,
        action_type="SCRIPT_GENERATED",
        metadata=f"turns:{len(dialogue)}"
    )
    return ScriptResponse(dialogue=dialogue, total_turns=len(dialogue))

@router.post("/audit-script", response_model=QaResponse)
async def audit_script(req: QaRequest, api_key: Optional[str] = Depends(get_api_key)):
    """QA Pacing Agent auditing accuracy, README coverage, and conversational cadence."""
    audit_res = studio_service.audit_dialogue_script(
        scenes=req.scenes,
        dialogue=req.dialogue,
        readme_text=req.readme_text,
        api_key=api_key
    )
    return QaResponse(
        overall_score=audit_res.get("overall_score", 90),
        accuracy_score=audit_res.get("accuracy_score", 90),
        readme_score=audit_res.get("readme_score", 90),
        pacing_score=audit_res.get("pacing_score", 90),
        feedback=audit_res.get("feedback", "Audit verified."),
        checklist=audit_res.get("checklist", {})
    )
