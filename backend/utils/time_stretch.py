"""
DubKaro — Audio Time Stretching
Dubbed audio clip ko original segment ki duration mein fit karo
bina pitch change kiye.
"""

import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path


def time_stretch_audio(
        input_path: str,
        target_duration: float,
        output_path: str
) -> str:
    """
    Audio ko stretch/compress karo taaki wo target_duration mein fit ho.
    Uses FFmpeg's atempo filter (preserves pitch).

    atempo range: 0.5 to 2.0 — multiple filters chain karo for extreme values.
    """
    input_path = str(input_path)
    output_path = str(output_path)

    # Current duration nikaalo
    data, sr = sf.read(input_path)
    current_duration = len(data) / sr

    if current_duration <= 0 or target_duration <= 0:
        # Edge case — just copy
        subprocess.run(["cp", input_path, output_path], check=True)
        return output_path

    # Speed ratio calculate karo
    # atempo > 1.0 = speed up, atempo < 1.0 = slow down
    ratio = current_duration / target_duration

    # Clamp to reasonable range (0.25x to 4.0x)
    ratio = max(0.25, min(ratio, 4.0))

    # FFmpeg atempo only accepts 0.5-2.0, so chain multiple filters
    atempo_filters = _build_atempo_chain(ratio)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:a", atempo_filters,
        "-acodec", "pcm_s16le",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _build_atempo_chain(ratio: float) -> str:
    """
    atempo filter 0.5-2.0 range mein kaam karta hai.
    Usse bahar ke values ke liye chain banao.
    Example: ratio=4.0 -> "atempo=2.0,atempo=2.0"
    """
    filters = []

    if ratio >= 1.0:
        while ratio > 2.0:
            filters.append("atempo=2.0")
            ratio /= 2.0
        filters.append(f"atempo={ratio:.4f}")
    else:
        while ratio < 0.5:
            filters.append("atempo=0.5")
            ratio /= 0.5
        filters.append(f"atempo={ratio:.4f}")

    return ",".join(filters)


def match_segment_duration(
        audio_clip_path: str,
        target_start: float,
        target_end: float,
        output_path: str
) -> str:
    """
    Audio clip ko exactly (target_end - target_start) seconds mein fit karo.
    """
    target_duration = target_end - target_start
    return time_stretch_audio(audio_clip_path, target_duration, output_path)