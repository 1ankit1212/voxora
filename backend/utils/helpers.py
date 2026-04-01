"""
DubKaro — Helper Utilities
"""

import subprocess
import uuid
from pathlib import Path


def generate_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


def get_video_duration(video_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def extract_audio_from_video(
    video_path: str,
    output_path: str,
    sample_rate: int = 44100,
) -> str:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(output_path)


def create_job_dirs(job_id: str, base_dir: Path) -> dict:
    root = base_dir / job_id
    dirs = {
        "root": root,
        "separated": root / "separated",
        "dubbed_clips": root / "dubbed_clips",
        "lipsync": root / "lipsync",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs