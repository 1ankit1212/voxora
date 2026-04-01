"""
DubKaro — Lip Sync using Wav2Lip
Video mein speaker ke lips ko new audio ke saath sync karo.
"""

import sys
import subprocess
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import WAV2LIP_PATH


class LipSyncer:
    """
    Wav2Lip wrapper — lip movements ko dubbed audio ke saath match karo.

    Usage:
        syncer = LipSyncer()
        output = syncer.sync("video.mp4", "dubbed_audio.wav", "output.mp4")
    """

    def __init__(self):
        self.wav2lip_dir = WAV2LIP_PATH
        self.checkpoint = self.wav2lip_dir / "checkpoints" / "wav2lip_gan.pth"
        self._validate_setup()

    def _validate_setup(self):
        """Check karo ki Wav2Lip repo aur model exist karte hain."""
        if not self.wav2lip_dir.exists():
            print(f"[LIPSYNC] WARNING: Wav2Lip directory not found at {self.wav2lip_dir}")
            print(f"[LIPSYNC] Run: git clone https://github.com/Rudrabha/Wav2Lip.git")
            self.available = False
            return

        if not self.checkpoint.exists():
            print(f"[LIPSYNC] WARNING: Wav2Lip model not found at {self.checkpoint}")
            print(f"[LIPSYNC] Download wav2lip_gan.pth and place in Wav2Lip/checkpoints/")
            self.available = False
            return

        self.available = True
        print(f"[LIPSYNC] Ready — checkpoint: {self.checkpoint}")

    def sync(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        resize_factor: int = 1,
        pad_bottom: int = 0,
    ) -> str:
        """
        Video ke lip movements ko audio ke saath sync karo.

        Args:
            video_path: Original video
            audio_path: Dubbed audio (full mixed audio)
            output_path: Output lip-synced video
            resize_factor: Video resize (1=original, 2=half — faster processing)
            pad_bottom: Bottom padding for face detection (chin area)

        Returns:
            Path to lip-synced video
        """
        if not self.available:
            print("[LIPSYNC] Wav2Lip not available — skipping lip sync.")
            print("[LIPSYNC] Returning original video with new audio.")
            return self._fallback_merge(video_path, audio_path, output_path)

        print(f"[LIPSYNC] Starting lip sync...")
        print(f"[LIPSYNC] Video: {video_path}")
        print(f"[LIPSYNC] Audio: {audio_path}")

        # Wav2Lip inference command
        cmd = [
            "python",
            str(self.wav2lip_dir / "inference.py"),
            "--checkpoint_path", str(self.checkpoint),
            "--face", str(video_path),
            "--audio", str(audio_path),
            "--outfile", str(output_path),
            "--resize_factor", str(resize_factor),
            "--nosmooth",  # Smoother results without this, but faster with it
        ]

        if pad_bottom > 0:
            cmd.extend(["--pads", "0", "0", "0", str(pad_bottom)])

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 min timeout
                cwd=str(self.wav2lip_dir),
            )
            print(f"[LIPSYNC] Done: {output_path}")
            return str(output_path)

        except subprocess.CalledProcessError as e:
            print(f"[LIPSYNC] ERROR: {e.stderr[:500]}")
            print("[LIPSYNC] Falling back to simple audio merge...")
            return self._fallback_merge(video_path, audio_path, output_path)

        except subprocess.TimeoutExpired:
            print("[LIPSYNC] TIMEOUT — process took too long.")
            return self._fallback_merge(video_path, audio_path, output_path)

    def _fallback_merge(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Lip sync fail ho to sirf audio replace karo (no lip movement change)."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[LIPSYNC] Fallback merge done: {output_path}")
        return str(output_path)