"""
DubKaro — Process Router (start dubbing)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from config import SUPABASE_URL, SUPABASE_KEY, SUPPORTED_LANGUAGES, TOKENS_PER_SECOND
from middleware.auth import get_current_user
from supabase import create_client
from datetime import datetime, timezone

router = APIRouter(prefix="/api", tags=["process"])
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class ProcessRequest(BaseModel):
    target_lang: str
    source_lang: str = "hindi"
    enable_lip_sync: bool = False


@router.post("/process/{job_id}")
async def start_processing(
    job_id: str,
    req: ProcessRequest,
    user: dict = Depends(get_current_user),
):
    # Validate languages
    if req.source_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Unsupported source: {req.source_lang}")
    if req.target_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Unsupported target: {req.target_lang}")
    if req.source_lang == req.target_lang:
        raise HTTPException(400, "Source and target languages must be different")

    # Fetch job
    result = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(404, "Job not found")

    job = result.data[0]

    # Verify ownership
    if job["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your job")

    if job["status"] not in ["pending", "failed"]:
        raise HTTPException(400, f"Job already {job['status']}")

    # Lip sync plan check
    if req.enable_lip_sync:
        from config import API_KEY_PLANS
        plan = user.get("plan", "free")
        if not API_KEY_PLANS.get(plan, {}).get("lip_sync_allowed", False):
            raise HTTPException(
                403,
                f"Lip sync not available on {plan} plan. Upgrade to starter or above.",
            )

    # Deduct tokens for API key users
    if user.get("auth_type") == "api_key":
        tokens_needed = int(job.get("video_duration", 0) * TOKENS_PER_SECOND)
        api_key_id = user["api_key_id"]

        # Deduct tokens
        supabase.table("api_keys").update({
            "tokens_used": user.get("tokens_remaining", 0) - user.get("tokens_remaining", 0) + tokens_needed + (supabase.table("api_keys").select("tokens_used").eq("id", api_key_id).execute().data[0]["tokens_used"]),
        }).eq("id", api_key_id).execute()

        # Actually, simpler way:
        current = supabase.table("api_keys").select(
            "tokens_used"
        ).eq("id", api_key_id).execute().data[0]

        supabase.table("api_keys").update({
            "tokens_used": current["tokens_used"] + tokens_needed,
        }).eq("id", api_key_id).execute()

        # Log usage
        supabase.table("api_usage_logs").insert({
            "api_key_id": api_key_id,
            "job_id": job_id,
            "endpoint": f"POST /api/process/{job_id}",
            "tokens_consumed": tokens_needed,
            "video_duration_sec": job.get("video_duration", 0),
            "source_lang": req.source_lang,
            "target_lang": req.target_lang,
            "status": "started",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

    # Update job
    supabase.table("jobs").update({
        "source_language": req.source_lang,
        "target_language": req.target_lang,
        "enable_lip_sync": req.enable_lip_sync,
        "status": "separating_audio",
        "progress": 5,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    # Celery task
    from workers.celery_tasks import process_video_task
    process_video_task.delay(
        job_id=job_id,
        video_path=job["original_video_url"],
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        enable_lip_sync=req.enable_lip_sync,
    )

    return {
        "job_id": job_id,
        "status": "processing_started",
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "message": f"Dubbing started. Poll GET /api/status/{job_id} for progress.",
    }