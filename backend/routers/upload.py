"""
DubKaro — Upload Router (with auth)
"""

import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from config import (
    UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_VIDEO_SIZE_MB,
    SUPABASE_URL, SUPABASE_KEY, API_KEY_PLANS, TOKENS_PER_SECOND,
)
from utils.helpers import generate_job_id, get_video_duration
from middleware.auth import get_current_user
from pathlib import Path
from datetime import datetime, timezone
from supabase import create_client

router = APIRouter(prefix="/api", tags=["upload"])
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    plan = user.get("plan", "free")
    plan_config = API_KEY_PLANS.get(plan, API_KEY_PLANS["free"])

    # Extension check
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Size check
    max_size = plan_config["max_video_size_mb"]
    if file.size and file.size > max_size * 1024 * 1024:
        raise HTTPException(400, f"File too large. Max {max_size}MB on {plan} plan.")

    # Save file
    job_id = generate_job_id()
    save_path = UPLOAD_DIR / f"{job_id}{ext}"

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Duration check
    try:
        duration = get_video_duration(str(save_path))
    except Exception:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, "Invalid video file.")

    max_duration = plan_config["max_video_duration"]
    if duration > max_duration:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            400,
            f"Video too long ({duration:.0f}s). Max {max_duration}s on {plan} plan.",
        )

    # Token check for API key users
    tokens_needed = int(duration * TOKENS_PER_SECOND)
    if user.get("auth_type") == "api_key":
        if user["tokens_remaining"] < tokens_needed:
            save_path.unlink(missing_ok=True)
            raise HTTPException(
                429,
                f"Not enough tokens. Need {tokens_needed}, have {user['tokens_remaining']}.",
            )

    # Create job in DB
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("jobs").insert({
        "id": job_id,
        "user_id": user_id,
        "status": "pending",
        "progress": 0,
        "original_video_url": str(save_path),
        "video_duration": duration,
        "created_at": now,
        "updated_at": now,
    }).execute()

    return {
        "job_id": job_id,
        "duration": round(duration, 2),
        "tokens_required": tokens_needed,
        "filename": file.filename,
        "message": "Video uploaded. Call POST /api/process/{job_id} to start dubbing.",
    }