"""
DubKaro — Translation Service
IndicTrans2 for Indian languages + NLLB for Foreign languages.
"""

import sys
import time
import torch
from pathlib import Path
from typing import List
from dataclasses import dataclass

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import get_device, SUPPORTED_LANGUAGES


@dataclass
class TranslatedSegment:
    id: int
    start: float
    end: float
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    speaker_id: str = "SPEAKER_0"


class IndicTranslator:
    """
    IndicTrans2 for Indian language pairs.
    NLLB-200 for Foreign language pairs.
    Auto-picks the right model based on source/target.
    """

    INDIC_INDIC = "ai4bharat/indictrans2-indic-indic-1B"
    EN_INDIC = "ai4bharat/indictrans2-en-indic-1B"
    INDIC_EN = "ai4bharat/indictrans2-indic-en-1B"
    NLLB_MODEL = "facebook/nllb-200-distilled-600M"

    def __init__(self):
        self.device = get_device()
        self.model = None
        self.tokenizer = None
        self.processor = None
        self._loaded_model_name = None
        self._model_type = None  # "indictrans" or "nllb"
        print(f"[TRANSLATOR] Initialized, device='{self.device}'")

    def _get_translation_route(self, src: str, tgt: str) -> tuple:
        """Decide which model to use based on language pair."""
        src_info = SUPPORTED_LANGUAGES.get(src, {})
        tgt_info = SUPPORTED_LANGUAGES.get(tgt, {})

        src_region = src_info.get("region", "foreign")
        tgt_region = tgt_info.get("region", "foreign")

        # Both Indian → IndicTrans2
        if src_region == "indian" and tgt_region == "indian":
            if src == "english":
                return self.EN_INDIC, "indictrans"
            elif tgt == "english":
                return self.INDIC_EN, "indictrans"
            else:
                return self.INDIC_INDIC, "indictrans"

        # English ↔ Indian → IndicTrans2
        if src == "english" and tgt_region == "indian":
            return self.EN_INDIC, "indictrans"
        if src_region == "indian" and tgt == "english":
            return self.INDIC_EN, "indictrans"

        # Everything else → NLLB
        return self.NLLB_MODEL, "nllb"

    def load_model(self, src_lang: str, tgt_lang: str):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model_name, model_type = self._get_translation_route(src_lang, tgt_lang)

        if self.model is not None and self._loaded_model_name == model_name:
            return

        self.unload_model()

        print(f"[TRANSLATOR] Loading {model_name} ({model_type})...")
        start = time.time()

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, trust_remote_code=True
        )

        if self.device == "cuda":
            self.model = self.model.to(self.device).half()

        self.model.eval()
        self._loaded_model_name = model_name
        self._model_type = model_type

        # IndicTrans needs processor
        if model_type == "indictrans":
            from IndicTransToolkit import IndicProcessor
            self.processor = IndicProcessor(inference=True)

        print(f"[TRANSLATOR] Loaded in {time.time() - start:.1f}s")

    def translate(
        self,
        segments: list,
        source_lang: str,
        target_lang: str,
        batch_size: int = 8,
        speaker_segments: list = None,
    ) -> List[TranslatedSegment]:
        """
        Translate segments. Supports both IndicTrans2 and NLLB.
        """
        self.load_model(source_lang, target_lang)

        print(f"[TRANSLATOR] Translating {len(segments)} segments: "
              f"{source_lang} → {target_lang} (model: {self._model_type})")

        start_time = time.time()

        if self._model_type == "indictrans":
            translated = self._translate_indictrans(
                segments, source_lang, target_lang, batch_size
            )
        else:
            translated = self._translate_nllb(
                segments, source_lang, target_lang, batch_size
            )

        # Add speaker_id from speaker_segments
        if speaker_segments:
            translated = self._assign_speakers(translated, speaker_segments)

        print(f"[TRANSLATOR] Done — {len(translated)} segments in "
              f"{time.time() - start_time:.1f}s")
        return translated

    def _translate_indictrans(self, segments, src, tgt, batch_size):
        src_code = SUPPORTED_LANGUAGES[src]["indictrans"]
        tgt_code = SUPPORTED_LANGUAGES[tgt]["indictrans"]

        all_texts = [seg.text for seg in segments]
        all_translated = []

        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i:i + batch_size]

            preprocessed = self.processor.preprocess_batch(
                batch, src_lang=src_code, tgt_lang=tgt_code
            )

            inputs = self.tokenizer(
                preprocessed, truncation=True, padding="longest",
                max_length=512, return_tensors="pt"
            )

            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                generated = self.model.generate(
                    **inputs, max_new_tokens=512, num_beams=5
                )

            with self.tokenizer.as_target_tokenizer():
                decoded = self.tokenizer.batch_decode(
                    generated, skip_special_tokens=True
                )

            postprocessed = self.processor.postprocess_batch(decoded, lang=tgt_code)
            all_translated.extend(postprocessed)

        return [
            TranslatedSegment(
                id=seg.id, start=seg.start, end=seg.end,
                original_text=seg.text,
                translated_text=text.strip(),
                source_lang=src, target_lang=tgt,
            )
            for seg, text in zip(segments, all_translated)
        ]

    def _translate_nllb(self, segments, src, tgt, batch_size):
        src_code = SUPPORTED_LANGUAGES[src].get("nllb", SUPPORTED_LANGUAGES[src].get("indictrans", "eng_Latn"))
        tgt_code = SUPPORTED_LANGUAGES[tgt].get("nllb", SUPPORTED_LANGUAGES[tgt].get("indictrans", "eng_Latn"))

        all_texts = [seg.text for seg in segments]
        all_translated = []

        # Set source language for tokenizer
        self.tokenizer.src_lang = src_code

        for i in range(0, len(all_texts), batch_size):
            batch = all_texts[i:i + batch_size]

            inputs = self.tokenizer(
                batch, return_tensors="pt", padding=True,
                truncation=True, max_length=512
            )

            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get target language token id
            tgt_token_id = self.tokenizer.convert_tokens_to_ids(tgt_code)

            with torch.no_grad():
                generated = self.model.generate(
                    **inputs,
                    forced_bos_token_id=tgt_token_id,
                    max_new_tokens=512,
                    num_beams=5,
                )

            decoded = self.tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )
            all_translated.extend(decoded)

        return [
            TranslatedSegment(
                id=seg.id, start=seg.start, end=seg.end,
                original_text=seg.text,
                translated_text=text.strip(),
                source_lang=src, target_lang=tgt,
            )
            for seg, text in zip(segments, all_translated)
        ]

    def _assign_speakers(self, translated_segments, speaker_segments):
        """Har translated segment ko correct speaker assign karo based on timestamp."""
        for t_seg in translated_segments:
            mid_point = (t_seg.start + t_seg.end) / 2
            for s_seg in speaker_segments:
                if s_seg.start <= mid_point <= s_seg.end:
                    t_seg.speaker_id = s_seg.speaker_id
                    break
        return translated_segments

    def unload_model(self):
        if self.model is not None:
            del self.model, self.tokenizer
            if self.processor:
                del self.processor
            self.model = self.tokenizer = self.processor = None
            self._loaded_model_name = None
            self._model_type = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[TRANSLATOR] Model unloaded")