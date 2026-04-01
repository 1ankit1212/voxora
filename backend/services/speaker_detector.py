"""
DubKaro — Multi-Speaker Detection
Free version using SpeechBrain + Resemblyzer.
Detects different speakers in audio and clusters them.
"""

import sys
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import get_device


@dataclass
class SpeakerSegment:
    speaker_id: str          # "SPEAKER_0", "SPEAKER_1", etc.
    start: float
    end: float
    duration: float = 0.0

    def __post_init__(self):
        self.duration = round(self.end - self.start, 3)


class SpeakerDetector:
    """
    Multi-speaker detection using Resemblyzer (FREE, no HF token needed).

    Pipeline:
    1. Audio ko fixed-length chunks mein divide karo
    2. Har chunk ka voice embedding nikalo (Resemblyzer)
    3. Embeddings ko cluster karo (Agglomerative Clustering)
    4. Speaker labels assign karo

    Usage:
        detector = SpeakerDetector()
        speakers = detector.detect("vocals.wav")
        # Returns: [SpeakerSegment(speaker_id="SPEAKER_0", start=0.0, end=5.2), ...]
    """

    def __init__(self):
        self.encoder = None
        self.device = get_device()
        print("[SPEAKER_DETECTOR] Initialized (Resemblyzer — FREE)")

    def load_model(self):
        if self.encoder is not None:
            return

        from resemblyzer import VoiceEncoder

        print("[SPEAKER_DETECTOR] Loading voice encoder...")
        self.encoder = VoiceEncoder(device=self.device)
        print("[SPEAKER_DETECTOR] Encoder loaded")

    def detect(
        self,
        audio_path: str,
        num_speakers: int = None,
        min_speakers: int = 1,
        max_speakers: int = 8,
        window_size: float = 1.5,
        step_size: float = 0.75,
    ) -> List[SpeakerSegment]:
        """
        Audio mein speakers detect karo.

        Args:
            audio_path: Vocals audio file path
            num_speakers: Fixed speaker count (None = auto detect)
            min_speakers: Minimum expected speakers
            max_speakers: Maximum expected speakers
            window_size: Analysis window in seconds
            step_size: Step between windows

        Returns:
            List of SpeakerSegment with speaker_id and timestamps
        """
        self.load_model()

        from resemblyzer import preprocess_wav
        from sklearn.cluster import AgglomerativeClustering
        from scipy.ndimage import median_filter

        print(f"[SPEAKER_DETECTOR] Processing: {audio_path}")

        # 1. Load and preprocess audio
        wav = preprocess_wav(Path(audio_path))
        total_duration = len(wav) / 16000  # Resemblyzer uses 16kHz

        print(f"[SPEAKER_DETECTOR] Audio duration: {total_duration:.1f}s")

        # 2. Create sliding windows
        window_samples = int(window_size * 16000)
        step_samples = int(step_size * 16000)

        windows = []
        timestamps = []
        pos = 0

        while pos + window_samples <= len(wav):
            window = wav[pos:pos + window_samples]
            windows.append(window)
            timestamps.append(pos / 16000)
            pos += step_samples

        if not windows:
            # Audio bahut chhota hai — single speaker maan lo
            return [SpeakerSegment(
                speaker_id="SPEAKER_0",
                start=0.0,
                end=total_duration,
            )]

        print(f"[SPEAKER_DETECTOR] {len(windows)} windows created")

        # 3. Voice embeddings nikalo
        embeddings = np.array([
            self.encoder.embed_utterance(w) for w in windows
        ])

        print(f"[SPEAKER_DETECTOR] Embeddings shape: {embeddings.shape}")

        # 4. Auto-detect number of speakers (if not provided)
        if num_speakers is None:
            num_speakers = self._estimate_speakers(
                embeddings, min_speakers, max_speakers
            )

        print(f"[SPEAKER_DETECTOR] Detected speakers: {num_speakers}")

        # 5. Clustering
        if num_speakers <= 1:
            labels = np.zeros(len(windows), dtype=int)
        else:
            clustering = AgglomerativeClustering(
                n_clusters=num_speakers,
                metric="cosine",
                linkage="average",
            )
            labels = clustering.fit_predict(embeddings)

        # 6. Smooth labels (remove flickering)
        labels = median_filter(labels, size=5).astype(int)

        # 7. Convert to segments
        segments = self._labels_to_segments(labels, timestamps, step_size, total_duration)

        # 8. Merge short segments
        segments = self._merge_short_segments(segments, min_duration=0.5)

        print(f"[SPEAKER_DETECTOR] {len(segments)} speaker segments found")
        for seg in segments:
            print(f"  {seg.speaker_id}: {seg.start:.1f}s - {seg.end:.1f}s ({seg.duration:.1f}s)")

        return segments

    def _estimate_speakers(
        self,
        embeddings: np.ndarray,
        min_k: int,
        max_k: int,
    ) -> int:
        """
        Silhouette score se optimal speaker count estimate karo.
        """
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics import silhouette_score

        if len(embeddings) < 3:
            return 1

        best_k = 1
        best_score = -1

        for k in range(min_k, min(max_k + 1, len(embeddings))):
            if k <= 1:
                continue

            try:
                clustering = AgglomerativeClustering(
                    n_clusters=k,
                    metric="cosine",
                    linkage="average",
                )
                labels = clustering.fit_predict(embeddings)

                # All same label = skip
                if len(set(labels)) < 2:
                    continue

                score = silhouette_score(embeddings, labels, metric="cosine")

                if score > best_score:
                    best_score = score
                    best_k = k

            except Exception:
                continue

        # Low silhouette = probably single speaker
        if best_score < 0.15:
            return 1

        return best_k

    def _labels_to_segments(
        self,
        labels: np.ndarray,
        timestamps: list,
        step_size: float,
        total_duration: float,
    ) -> List[SpeakerSegment]:
        """Labels ko contiguous speaker segments mein convert karo."""
        segments = []
        current_speaker = labels[0]
        start_time = timestamps[0]

        for i in range(1, len(labels)):
            if labels[i] != current_speaker:
                segments.append(SpeakerSegment(
                    speaker_id=f"SPEAKER_{current_speaker}",
                    start=round(start_time, 3),
                    end=round(timestamps[i], 3),
                ))
                current_speaker = labels[i]
                start_time = timestamps[i]

        # Last segment
        segments.append(SpeakerSegment(
            speaker_id=f"SPEAKER_{current_speaker}",
            start=round(start_time, 3),
            end=round(total_duration, 3),
        ))

        return segments

    def _merge_short_segments(
        self,
        segments: List[SpeakerSegment],
        min_duration: float = 0.5,
    ) -> List[SpeakerSegment]:
        """Bahut chhote segments ko adjacent same-speaker segments mein merge karo."""
        if len(segments) <= 1:
            return segments

        merged = [segments[0]]

        for seg in segments[1:]:
            prev = merged[-1]

            # Same speaker — merge karo
            if seg.speaker_id == prev.speaker_id:
                merged[-1] = SpeakerSegment(
                    speaker_id=prev.speaker_id,
                    start=prev.start,
                    end=seg.end,
                )
            # Too short — merge into previous
            elif seg.duration < min_duration:
                merged[-1] = SpeakerSegment(
                    speaker_id=prev.speaker_id,
                    start=prev.start,
                    end=seg.end,
                )
            else:
                merged.append(seg)

        return merged

    def extract_speaker_audio(
        self,
        audio_path: str,
        segments: List[SpeakerSegment],
        output_dir: str,
    ) -> Dict[str, str]:
        """
        Har speaker ka audio alag file mein extract karo.
        Returns: {"SPEAKER_0": "/path/to/speaker_0.wav", ...}
        """
        import librosa

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        audio, sr = librosa.load(audio_path, sr=22050)
        speaker_audios = {}

        # Group segments by speaker
        speaker_segments = {}
        for seg in segments:
            if seg.speaker_id not in speaker_segments:
                speaker_segments[seg.speaker_id] = []
            speaker_segments[seg.speaker_id].append(seg)

        for speaker_id, segs in speaker_segments.items():
            # Concatenate all segments for this speaker
            chunks = []
            for seg in segs:
                start_sample = int(seg.start * sr)
                end_sample = int(seg.end * sr)
                chunks.append(audio[start_sample:end_sample])

            if chunks:
                speaker_audio = np.concatenate(chunks)
                output_path = output_dir / f"{speaker_id.lower()}.wav"
                sf.write(str(output_path), speaker_audio, sr)
                speaker_audios[speaker_id] = str(output_path)
                print(f"[SPEAKER_DETECTOR] Extracted {speaker_id}: {output_path}")

        return speaker_audios

    def unload_model(self):
        if self.encoder is not None:
            del self.encoder
            self.encoder = None
            print("[SPEAKER_DETECTOR] Model unloaded")