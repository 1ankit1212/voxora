"""
DubKaro — Voice Cloning + TTS using Coqui XTTS v2
Creator ki original voice clone karke target language mein speech generate karo.
"""

import sys
import time
import torch
import soundfile as sf
from pathlib import Path
from typing import List, Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import get_device, SUPPORTED_LANGUAGES, TEMP_DIR
from utils.time_stretch import match_segment_duration


class VoiceCloner:
    """
    XTTS v2 wrapper — voice clone + text-to-speech.

    Usage:
        cloner = VoiceCloner()
        cloner.clone_and_speak(
            reference_audio="vocals.wav",
            segments=translated_segments,
            target_lang="tamil",
            output_dir="temp/job123/dubbed_clips/"
        )
    """

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self):
        self.device = get_device()
        self.tts = None
        print(f"[VOICE_CLONER] Initialized, device='{self.device}'")

    def load_model(self):
        if self.tts is not None:
            print("[VOICE_CLONER] Model already loaded.")
            return

        from TTS.api import TTS

        print(f"[VOICE_CLONER] Loading XTTS v2 model...")
        print(f"[VOICE_CLONER] First download ~1.8 GB hoga...")
        start = time.time()

        self.tts = TTS(self.MODEL_NAME, gpu=(self.device == "cuda"))

        print(f"[VOICE_CLONER] Loaded in {time.time() - start:.1f}s")

    def _prepare_reference(self, audio_path: str, output_dir: str, max_duration: float = 30.0) -> str:
        """
        Reference audio ko XTTS ke liye prepare karo.
        XTTS ko 6-30 seconds ka clean voice sample chahiye.
        """
        import librosa

        output_ref = Path(output_dir) / "reference_voice.wav"

        # Load audio
        audio, sr = librosa.load(str(audio_path), sr=22050)
        duration = len(audio) / sr

        # Agar audio 30s se zyada hai, pehle 30s lo
        if duration > max_duration:
            audio = audio[:int(max_duration * sr)]

        # Agar 6s se kam hai, warn karo (XTTS ko kam se kam 6s chahiye)
        if duration < 6.0:
            print(f"[VOICE_CLONER] WARNING: Reference audio sirf {duration:.1f}s hai. "
                  f"6s+ better results deta hai.")

        sf.write(str(output_ref), audio, sr)
        print(f"[VOICE_CLONER] Reference prepared: {output_ref} ({min(duration, max_duration):.1f}s)")
        return str(output_ref)

    def clone_and_speak(
            self,
            reference_audio: str,
            segments: list,
            target_lang: str,
            output_dir: str,
    ) -> List[dict]:
        """
        Voice clone karke translated text ko speech mein convert karo.

        Args:
            reference_audio: Creator ka original vocals.wav (voice sample)
            segments: List of TranslatedSegment (translated text with timestamps)
            target_lang: Target language key ("tamil", "telugu", etc.)
            output_dir: Dubbed audio clips yahan save honge

        Returns:
            List of dicts: [{segment_id, audio_path, start, end}, ...]
        """
        self.load_model()

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Reference audio prepare karo
        ref_audio = self._prepare_reference(reference_audio, str(output_dir))

        # XTTS language code
        xtts_lang = SUPPORTED_LANGUAGES.get(target_lang, {}).get("xtts", "hi")

        print(f"[VOICE_CLONER] Generating {len(segments)} clips in '{target_lang}' "
              f"(xtts_lang='{xtts_lang}')")

        start_time = time.time()
        generated_clips = []

        for seg in segments:
            clip_raw = output_dir / f"clip_{seg.id:04d}_raw.wav"
            clip_final = output_dir / f"clip_{seg.id:04d}.wav"

            text = seg.translated_text if hasattr(seg, 'translated_text') else seg.text

            if not text.strip():
                # Empty segment — silence generate karo
                duration = seg.end - seg.start
                sr = 22050
                silence = [0.0] * int(duration * sr)
                sf.write(str(clip_final), silence, sr)
                generated_clips.append({
                    "segment_id": seg.id, "audio_path": str(clip_final),
                    "start": seg.start, "end": seg.end
                })
                continue

            try:
                # XTTS se speech generate karo (voice cloning enabled)
                self.tts.tts_to_file(
                    text=text,
                    speaker_wav=ref_audio,
                    language=xtts_lang,
                    file_path=str(clip_raw),
                )

                # Time stretch — original segment ki duration mein fit karo
                match_segment_duration(
                    audio_clip_path=str(clip_raw),
                    target_start=seg.start,
                    target_end=seg.end,
                    output_path=str(clip_final),
                )

                # Raw file delete karo
                clip_raw.unlink(missing_ok=True)

            except Exception as e:
                print(f"[VOICE_CLONER] ERROR on segment {seg.id}: {e}")
                # Fallback: silence
                duration = seg.end - seg.start
                silence = [0.0] * int(duration * 22050)
                sf.write(str(clip_final), silence, 22050)

            generated_clips.append({
                "segment_id": seg.id,
                "audio_path": str(clip_final),
                "start": seg.start,
                "end": seg.end,
            })

            print(f"[VOICE_CLONER] Clip {seg.id + 1}/{len(segments)} done")

        elapsed = time.time() - start_time
        print(f"[VOICE_CLONER] All clips generated in {elapsed:.1f}s")

        return generated_clips

    def unload_model(self):
        if self.tts is not None:
            del self.tts
            self.tts = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[VOICE_CLONER] Model unloaded.")