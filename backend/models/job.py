"""
DubKaro — Job Data Model
Supabase 'jobs' table se interact karta hai.
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    SEPARATING = "separating_audio"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    CLONING_VOICE = "cloning_voice"
    LIP_SYNCING = "lip_syncing"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    user_id: str
    status: str = JobStatus.PENDING.value
    progress: int = 0                       # 0-100
    source_language: str = ""
    target_language: str = ""
    original_video_url: str = ""
    dubbed_video_url: str = ""
    enable_lip_sync: bool = False
    error_message: str = ""
    video_duration: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Steps with progress percentage mapping ──
STEP_PROGRESS = {
    JobStatus.PENDING: 0,
    JobStatus.UPLOADING: 5,
    JobStatus.SEPARATING: 15,
    JobStatus.TRANSCRIBING: 30,
    JobStatus.TRANSLATING: 50,
    JobStatus.CLONING_VOICE: 70,
    JobStatus.LIP_SYNCING: 85,
    JobStatus.MERGING: 95,
    JobStatus.COMPLETED: 100,
}