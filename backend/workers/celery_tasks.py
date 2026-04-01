"""
DubKaro — Celery Background Tasks
Heavy video processing background mein chalega.
"""

import sys
from pathlib import Path
from celery import Celery

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import REDIS_URL

# Celery app
celery_app = Celery(
    "dubkaro",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)


def _update_job_in_db(job_id: str, status: str, progress: int, error: str = ""):
    from supabase import create_client
    from config import SUPABASE_URL, SUPABASE_KEY
    from datetime import datetime

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    update_data = {
        "status": status,
        "progress": progress,
        "updated_at": datetime.utcnow().isoformat(),
    }

    if error:
        update_data["error_message"] = error

    supabase.table("jobs").update(update_data).eq("id", job_id).execute()


# ✅ IMPORTANT: function name = process_video_task
@celery_app.task(bind=True, name="dubkaro.process_video")
def process_video_task(self, job_id: str, video_path: str,
                       source_lang: str, target_lang: str,
                       enable_lip_sync: bool = False):

    from services.pipeline import DubbingPipeline

    print(f"[CELERY] Starting job: {job_id}")

    pipeline = DubbingPipeline()

    result = pipeline.run(
        video_path=video_path,
        source_lang=source_lang,
        target_lang=target_lang,
        job_id=job_id,
        enable_lip_sync=enable_lip_sync,
        progress_callback=_update_job_in_db,
    )

    if result["status"] == "completed":
        _update_job_in_db(job_id, "completed", 100)

        from supabase import create_client
        from config import SUPABASE_URL, SUPABASE_KEY

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        supabase.table("jobs").update({
            "dubbed_video_url": result["output_path"],
            "progress": 100,
            "status": "completed",
        }).eq("id", job_id).execute()

    else:
        _update_job_in_db(job_id, "failed", 0, result.get("error", "Unknown error"))

    return result