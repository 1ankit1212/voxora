from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from config import SUPABASE_URL, SUPABASE_KEY
from middleware.auth import get_current_user
from supabase import create_client

router = APIRouter(prefix="/api", tags=["download"])
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@router.get("/download/{job_id}")
async def download_video(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    result = supabase.table("jobs").select(
        "status, dubbed_video_url, user_id"
    ).eq("id", job_id).execute()

    if not result.data:
        raise HTTPException(404, "Job not found")

    job = result.data[0]

    if job["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your job")

    if job["status"] != "completed":
        raise HTTPException(400, f"Job not ready — status: {job['status']}")

    video_path = Path(job["dubbed_video_url"])
    if not video_path.exists():
        raise HTTPException(404, "Video file not found on server")

    return FileResponse(
        path=str(video_path),
        filename=f"{job_id}_dubbed.mp4",
        media_type="video/mp4",
    )