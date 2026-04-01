"""
DubKaro — Video Merger using FFmpeg
Dubbed audio clips + background music + video = Final dubbed video.
"""

import subprocess
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import List

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))


class VideoMerger:
    """
    FFmpeg wrapper — final video assembly.

    Steps:
    1. Saare dubbed clips ko ek continuous audio mein merge karo (with correct timing)
    2. Background music add karo (lower volume)
    3. Video ke saath merge karo
    """

    def __init__(self):
        print("[MERGER] Initialized")

    def merge_audio_clips(
        self,
        clips: List[dict],
        total_duration: float,
        output_path: str,
        sample_rate: int = 22050,
    ) -> str:
        """
        Individual dubbed clips ko ek continuous audio file mein combine karo.
        Har clip ko correct timestamp pe place karo.

        Args:
            clips: [{"segment_id": 0, "audio_path": "...", "start": 0.0, "end": 2.5}, ...]
            total_duration: Total video duration in seconds
            output_path: Output WAV path
            sample_rate: Audio sample rate
        """
        print(f"[MERGER] Merging {len(clips)} clips into continuous audio...")

        # Empty audio canvas (total duration)
        total_samples = int(total_duration * sample_rate)
        merged = np.zeros(total_samples, dtype=np.float32)

        for clip in clips:
            try:
                clip_audio, clip_sr = sf.read(clip["audio_path"])

                # Mono mein convert karo agar stereo hai
                if clip_audio.ndim > 1:
                    clip_audio = clip_audio.mean(axis=1)

                # Resample agar zaroorat ho
                if clip_sr != sample_rate:
                    import librosa
                    clip_audio = librosa.resample(
                        clip_audio.astype(np.float32), orig_sr=clip_sr, target_sr=sample_rate
                    )

                # Correct position pe place karo
                start_sample = int(clip["start"] * sample_rate)
                end_sample = start_sample + len(clip_audio)

                # Bounds check
                if end_sample > total_samples:
                    clip_audio = clip_audio[:total_samples - start_sample]
                    end_sample = total_samples

                merged[start_sample:end_sample] = clip_audio.astype(np.float32)

            except Exception as e:
                print(f"[MERGER] WARNING: Clip {clip['segment_id']} skip hua: {e}")

        sf.write(str(output_path), merged, sample_rate)
        print(f"[MERGER] Merged audio saved: {output_path}")
        return str(output_path)

    def mix_with_background(
        self,
        dubbed_audio_path: str,
        background_audio_path: str,
        output_path: str,
        bg_volume: float = 0.3,
    ) -> str:
        """
        Dubbed voice + background music ko mix karo.
        Background music volume lower rakho.

        Args:
            dubbed_audio_path: Dubbed voice audio
            background_audio_path: Background music from Demucs
            output_path: Mixed output path
            bg_volume: Background music volume (0.0-1.0), default 0.3 = 30%
        """
        print(f"[MERGER] Mixing dubbed audio with background (bg_vol={bg_volume})")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(dubbed_audio_path),
            "-i", str(background_audio_path),
            "-filter_complex",
            f"[0:a]volume=1.0[voice];"
            f"[1:a]volume={bg_volume}[bg];"
            f"[voice][bg]amix=inputs=2:duration=first:dropout_transition=2[out]",
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[MERGER] Mixed audio saved: {output_path}")
        return str(output_path)

    def merge_video_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        Final step — video + dubbed+bg audio ko merge karo.
        Original video ka audio replace karo dubbed audio se.
        """
        print(f"[MERGER] Final merge: video + dubbed audio")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),       # original video
            "-i", str(audio_path),       # dubbed + bg mixed audio
            "-c:v", "copy",              # video re-encode mat karo (fast)
            "-c:a", "aac",               # audio AAC mein encode karo
            "-b:a", "192k",              # audio bitrate
            "-map", "0:v:0",             # video stream from first input
            "-map", "1:a:0",             # audio stream from second input
            "-shortest",                 # shorter stream pe cut karo
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[MERGER] ✅ Final video: {output_path}")
        return str(output_path)

    def create_final_video(
        self,
        video_path: str,
        dubbed_clips: List[dict],
        background_audio_path: str,
        total_duration: float,
        output_dir: str,
        job_id: str,
        bg_volume: float = 0.3,
    ) -> str:
        """
        All-in-one: clips merge → bg mix → video merge.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step A: Clips → continuous audio
        dubbed_continuous = str(output_dir / "dubbed_continuous.wav")
        self.merge_audio_clips(dubbed_clips, total_duration, dubbed_continuous)

        # Step B: + background music
        mixed_audio = str(output_dir / "mixed_audio.wav")
        self.mix_with_background(dubbed_continuous, background_audio_path, mixed_audio, bg_volume)

        # Step C: Video + mixed audio = final
        final_video = str(output_dir / f"{job_id}_dubbed.mp4")
        self.merge_video_audio(video_path, mixed_audio, final_video)

        return final_video