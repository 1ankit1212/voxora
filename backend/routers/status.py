from fastapi import APIRouter, HTTPException, Depends
from config import SUPABASE_URL, SUPABASE_KEY, SUPPORTED_LANGUAGES
from middleware.auth import get_current_user
from supabase import create_client

router = APIRouter(prefix="/api", tags=["status"])
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@router.get("/status/{job_id}")
async def get_status(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    result = supabase.table("jobs").select(
        "id, status, progress, source_language, target_language, "
        "video_duration, error_message, created_at, updated_at"
    ).eq("id", job_id).execute()

    if not result.data:
        raise HTTPException(404, "Job not found")

    job = result.data[0]

    # Verify ownership (skip for service role)
    if user.get("auth_type") != "service_role":
        full_job = supabase.table("jobs").select(
            "user_id"
        ).eq("id", job_id).execute()
        if full_job.data and full_job.data[0]["user_id"] != user["user_id"]:
            raise HTTPException(403, "Not your job")

    return job


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    result = supabase.table("jobs").select("*").eq(
        "user_id", user["user_id"]
    ).order("created_at", desc=True).limit(50).execute()

    return {"jobs": result.data}


@router.get("/languages")
async def get_languages():
    languages = {
        "indian": [],
        "foreign": [],
    }
    for key, val in SUPPORTED_LANGUAGES.items():
        item = {
            "key": key,
            "display": val["display"],
            "flag": val.get("flag", ""),
        }
        if val.get("region") == "indian":
            languages["indian"].append(item)
        else:
            languages["foreign"].append(item)

    return {"languages": languages, "total": len(SUPPORTED_LANGUAGES)}