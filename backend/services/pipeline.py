"""
DubKaro — Master Pipeline (Multi-Speaker + All Languages)
"""

import sys
import time
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import TEMP_DIR, OUTPUT_DIR
from models.job import JobStatus, STEP_PROGRESS
from utils.helpers import extract_audio_from_video, create_job_dirs, get_video_duration
from services.audio_separator import AudioSeparator
from services.speaker_detector import SpeakerDetector
from services.transcriber import WhisperTranscriber
from services.translator import IndicTranslator
from services.voice_cloner import VoiceCloner
from services.lip_sync import LipSyncer
from services.video_merger import VideoMerger


class DubbingPipeline:

    def __init__(self):
        self.separator = AudioSeparator()
        self.speaker_detector = SpeakerDetector()
        self.transcriber = WhisperTranscriber()
        self.translator = IndicTranslator()
        self.voice_cloner = VoiceCloner()
        self.lip_syncer = LipSyncer()
        self.merger = VideoMerger()
        print("[PIPELINE] All services initialized (Multi-Speaker Enabled)")

    def run(
        self,
        video_path: str,
        source_lang: str,
        target_lang: str,
        job_id: str,
        enable_lip_sync: bool = False,
        progress_callback=None,
    ) -> dict:

        total_start = time.time()
        video_path = str(video_path)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        job_dirs = create_job_dirs(job_id, TEMP_DIR)

        def update_progress(status: JobStatus):
            progress = STEP_PROGRESS.get(status, 0)
            print(f"\n{'='*60}")
            print(f"  STEP: {status.value} | Progress: {progress}%")
            print(f"{'='*60}")
            if progress_callback:
                progress_callback(job_id, status.value, progress)

        try:
            # ── STEP 0: Video duration ──
            video_duration = get_video_duration(video_path)
            print(f"[PIPELINE] Video: {video_duration:.1f}s")

            # ── STEP 1: AUDIO SEPARATION ──
            update_progress(JobStatus.SEPARATING)

            raw_audio = str(job_dirs["root"] / "raw_audio.wav")
            extract_audio_from_video(video_path, raw_audio, sample_rate=44100)

            vocals_path, bg_music_path = self.separator.separate(
                raw_audio, str(job_dirs["separated"])
            )

            # ── STEP 1.5: SPEAKER DETECTION ──
            print("\n[PIPELINE] Detecting speakers...")
            speaker_segments = self.speaker_detector.detect(vocals_path)
            num_speakers = len(set(s.speaker_id for s in speaker_segments))
            print(f"[PIPELINE] Found {num_speakers} speaker(s)")

            # Extract per-speaker reference audio
            speaker_dir = job_dirs["root"] / "speakers"
            speaker_audios = self.speaker_detector.extract_speaker_audio(
                vocals_path, speaker_segments, str(speaker_dir)
            )

            # ── STEP 2: TRANSCRIBE ──
            update_progress(JobStatus.TRANSCRIBING)

            transcript = self.transcriber.transcribe(
                audio_path=vocals_path,
                language=source_lang,
                word_timestamps=True,
            )

            if not transcript or not transcript.segments:
                raise Exception("No speech detected")

            # ── STEP 3: TRANSLATE ──
            update_progress(JobStatus.TRANSLATING)
            self.transcriber.unload_model()

            translated_segments = self.translator.translate(
                segments=transcript.segments,
                source_lang=source_lang,
                target_lang=target_lang,
                speaker_segments=speaker_segments,
            )

            if not translated_segments:
                raise Exception("Translation failed")

            # ── STEP 4: VOICE CLONE (Per Speaker) ──
            update_progress(JobStatus.CLONING_VOICE)
            self.translator.unload_model()

            all_dubbed_clips = []

            if num_speakers > 1:
                # Multi-speaker: clone each speaker separately
                for speaker_id, ref_audio in speaker_audios.items():
                    speaker_segs = [
                        s for s in translated_segments
                        if s.speaker_id == speaker_id
                    ]

                    if not speaker_segs:
                        continue

                    print(f"\n[PIPELINE] Cloning {speaker_id} "
                          f"({len(speaker_segs)} segments)...")

                    clips = self.voice_cloner.clone_and_speak(
                        reference_audio=ref_audio,
                        segments=speaker_segs,
                        target_lang=target_lang,
                        output_dir=str(job_dirs["dubbed_clips"] / speaker_id.lower()),
                    )
                    all_dubbed_clips.extend(clips)
            else:
                # Single speaker
                all_dubbed_clips = self.voice_cloner.clone_and_speak(
                    reference_audio=vocals_path,
                    segments=translated_segments,
                    target_lang=target_lang,
                    output_dir=str(job_dirs["dubbed_clips"]),
                )

            if not all_dubbed_clips:
                raise Exception("Voice cloning failed")

            # Sort by start time
            all_dubbed_clips.sort(key=lambda c: c["start"])

            # ── STEP 5: LIP SYNC ──
            if enable_lip_sync:
                update_progress(JobStatus.LIP_SYNCING)

                temp_dubbed = str(job_dirs["root"] / "temp_dubbed.wav")
                temp_mixed = str(job_dirs["root"] / "temp_mixed.wav")

                self.merger.merge_audio_clips(
                    all_dubbed_clips, video_duration, temp_dubbed
                )
                self.merger.mix_with_background(
                    temp_dubbed, bg_music_path, temp_mixed
                )

                lip_synced = str(job_dirs["lipsync"] / "lip_synced.mp4")
                self.lip_syncer.sync(video_path, temp_mixed, lip_synced)
                video_for_merge = lip_synced
            else:
                video_for_merge = video_path

            # ── STEP 6: FINAL MERGE ──
            update_progress(JobStatus.MERGING)
            self.voice_cloner.unload_model()
            self.speaker_detector.unload_model()

            final_output = self.merger.create_final_video(
                video_path=video_for_merge,
                dubbed_clips=all_dubbed_clips,
                background_audio_path=bg_music_path,
                total_duration=video_duration,
                output_dir=str(OUTPUT_DIR),
                job_id=job_id,
            )

            if not final_output or not os.path.exists(final_output):
                raise Exception("Final video not created")

            update_progress(JobStatus.COMPLETED)

            return {
                "status": "completed",
                "output_path": final_output,
                "video_duration": video_duration,
                "num_speakers": num_speakers,
                "processing_time": round(time.time() - total_start, 2),
            }

        except Exception as e:
            print(f"[PIPELINE] ❌ ERROR: {e}")
            if progress_callback:
                progress_callback(job_id, JobStatus.FAILED.value, 0, str(e))
            return {"status": "failed", "error": str(e)}