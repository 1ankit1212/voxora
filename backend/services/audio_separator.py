"""
DubKaro — Audio Separation using Demucs (Meta)
Video ke audio se vocals alag karo background music se.
"""

import subprocess
import shutil
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import TEMP_DIR


class AudioSeparator:
    """
    Demucs wrapper — separates vocals from background music.

    Usage:
        separator = AudioSeparator()
        vocals, bg_music = separator.separate("audio.wav", "output_dir/")
    """

    def __init__(self, model: str = "htdemucs"):
        """
        Args:
            model: Demucs model name.
                   'htdemucs' = default hybrid transformer (best quality)
                   'htdemucs_ft' = fine-tuned (better but slower)
        """
        self.model = model
        print(f"[SEPARATOR] Initialized with model='{self.model}'")

    def separate(self, audio_path: str, output_dir: str) -> tuple:
        """
        Audio file ko vocals + accompaniment mein split karo.

        Args:
            audio_path: Input audio file path (.wav)
            output_dir: Directory jahan output files jayenge

        Returns:
            (vocals_path, accompaniment_path) — dono WAV files
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[SEPARATOR] Separating: {audio_path.name}")

        # Demucs CLI se run karo
        # --two-stems vocals: sirf vocals + accompaniment (4 stems nahi)
        # -o: output directory
        cmd = [
            "python", "-m", "demucs",
            "--two-stems", "vocals",
            "-n", self.model,
            "-o", str(output_dir),
            str(audio_path)
        ]

        try:
            subprocess.run(
                cmd, check=True,
                capture_output=True, text=True,
                timeout=600  # 10 min timeout
            )
        except subprocess.CalledProcessError as e:
            print(f"[SEPARATOR] ERROR: {e.stderr}")
            raise RuntimeError(f"Demucs failed: {e.stderr}")

        # Demucs outputs to: output_dir/{model_name}/{filename_stem}/vocals.wav
        stem = audio_path.stem
        demucs_out = output_dir / self.model / stem

        vocals_path = demucs_out / "vocals.wav"
        accompaniment_path = demucs_out / "no_vocals.wav"

        if not vocals_path.exists():
            raise FileNotFoundError(f"Vocals not found at {vocals_path}")

        # Move files to a cleaner location
        final_vocals = output_dir / "vocals.wav"
        final_bg = output_dir / "background_music.wav"

        shutil.move(str(vocals_path), str(final_vocals))
        shutil.move(str(accompaniment_path), str(final_bg))

        # Demucs ka temp folder clean karo
        demucs_model_dir = output_dir / self.model
        if demucs_model_dir.exists():
            shutil.rmtree(demucs_model_dir)

        print(f"[SEPARATOR] Vocals: {final_vocals}")
        print(f"[SEPARATOR] Background: {final_bg}")

        return str(final_vocals), str(final_bg)


# ── Quick Test ──
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to audio/wav file")
    args = parser.parse_args()

    sep = AudioSeparator()
    vocals, bg = sep.separate(args.file, str(TEMP_DIR / "separation_test"))
    print(f"\n✅ Done!\n  Vocals: {vocals}\n  Background: {bg}")