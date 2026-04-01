"""
DubKaro — Whisper Speech-to-Text Service
"""

import sys
import time
import json
import whisper
import torch
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import WHISPER_MODEL_SIZE, TEMP_DIR, get_device, SUPPORTED_LANGUAGES


@dataclass
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    duration: float = 0.0
    words: list = field(default_factory=list)

    def __post_init__(self):
        self.duration = round(self.end - self.start, 3)


@dataclass
class TranscriptionResult:
    language: str
    language_name: str
    language_probability: float
    segments: list
    full_text: str
    total_duration: float
    processing_time: float
    model_size: str


class WhisperTranscriber:

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or WHISPER_MODEL_SIZE
        self.device = get_device()
        self.model = None
        print(f"[TRANSCRIBER] model='{self.model_size}', device='{self.device}'")

    def load_model(self):
        if self.model is not None:
            return
        print(f"[TRANSCRIBER] Loading Whisper '{self.model_size}'...")
        start = time.time()
        self.model = whisper.load_model(self.model_size, device=self.device)
        print(f"[TRANSCRIBER] Loaded in {time.time() - start:.1f}s")

    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   word_timestamps: bool = False) -> TranscriptionResult:
        self.load_model()
        print(f"[TRANSCRIBER] Transcribing: {audio_path}")
        start_time = time.time()

        options = {
            "task": "transcribe",
            "word_timestamps": word_timestamps,
            "verbose": False,
            "fp16": self.device == "cuda",
        }

        if language:
            lang_code = SUPPORTED_LANGUAGES.get(language, {}).get("whisper", language)
            options["language"] = lang_code

        result = self.model.transcribe(str(audio_path), **options)
        processing_time = time.time() - start_time

        segments = []
        for i, seg in enumerate(result["segments"]):
            words = []
            if word_timestamps and "words" in seg:
                words = [{"word": w["word"].strip(), "start": round(w["start"], 3),
                          "end": round(w["end"], 3)} for w in seg["words"]]
            segments.append(TranscriptSegment(
                id=i, start=round(seg["start"], 3),
                end=round(seg["end"], 3), text=seg["text"].strip(), words=words))

        detected_lang = result.get("language", "unknown")
        lang_name = detected_lang
        for key, val in SUPPORTED_LANGUAGES.items():
            if val["whisper"] == detected_lang:
                lang_name = val["display"]
                break

        total_duration = segments[-1].end if segments else 0.0

        transcription = TranscriptionResult(
            language=detected_lang, language_name=lang_name,
            language_probability=round(result.get("language_probability", 0.0), 4),
            segments=segments, full_text=result["text"].strip(),
            total_duration=round(total_duration, 3),
            processing_time=round(processing_time, 2), model_size=self.model_size)

        print(f"[TRANSCRIBER] Done — {len(segments)} segments, {total_duration:.1f}s audio, "
              f"{processing_time:.1f}s processing")
        return transcription

    def save_transcript(self, result: TranscriptionResult, output_path: str, fmt: str = "json") -> str:
        output_path = Path(output_path)
        if fmt == "json":
            filepath = output_path.with_suffix(".json")
            data = {"language": result.language, "language_name": result.language_name,
                    "full_text": result.full_text, "total_duration": result.total_duration,
                    "segments": [asdict(seg) for seg in result.segments]}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif fmt == "srt":
            filepath = output_path.with_suffix(".srt")
            with open(filepath, "w", encoding="utf-8") as f:
                for seg in result.segments:
                    h, m = int(seg.start // 3600), int((seg.start % 3600) // 60)
                    s, ms = int(seg.start % 60), int((seg.start % 1) * 1000)
                    start_tc = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                    h, m = int(seg.end // 3600), int((seg.end % 3600) // 60)
                    s, ms = int(seg.end % 60), int((seg.end % 1) * 1000)
                    end_tc = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                    f.write(f"{seg.id + 1}\n{start_tc} --> {end_tc}\n{seg.text}\n\n")
        elif fmt == "txt":
            filepath = output_path.with_suffix(".txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(result.full_text)
        print(f"[TRANSCRIBER] Saved: {filepath}")
        return str(filepath)

    def unload_model(self):
        if self.model:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[TRANSCRIBER] Model unloaded.")