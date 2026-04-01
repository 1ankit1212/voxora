"""
DubKaro — Central Configuration
All languages + API key plans + settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"

for d in [UPLOAD_DIR, TEMP_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Whisper ──
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
DEVICE = os.getenv("DEVICE", "auto")

# ── Supabase ──
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # Use service_role key for backend

# ── Redis / Celery ──
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Wav2Lip ──
WAV2LIP_PATH = Path(os.getenv("WAV2LIP_PATH", str(BASE_DIR / "Wav2Lip")))

# ── HuggingFace ──
HF_TOKEN = os.getenv("HF_TOKEN", "")

# ── Server ──
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5000",
    "https://dubkaro.in",
    "https://voxora.in",
    "*",  # Allow all for API key users
]

# ── File Limits ──
MAX_VIDEO_SIZE_MB = 500
MAX_VIDEO_DURATION_SEC = 1800
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

# ── Language Map (Indian + Foreign) ──
SUPPORTED_LANGUAGES = {
    # ── Indian Languages ──
    "hindi":     {"whisper": "hi", "indictrans": "hin_Deva", "xtts": "hi", "display": "Hindi",     "flag": "🇮🇳", "region": "indian"},
    "tamil":     {"whisper": "ta", "indictrans": "tam_Taml", "xtts": "ta", "display": "Tamil",     "flag": "🇮🇳", "region": "indian"},
    "telugu":    {"whisper": "te", "indictrans": "tel_Telu", "xtts": "te", "display": "Telugu",    "flag": "🇮🇳", "region": "indian"},
    "bengali":   {"whisper": "bn", "indictrans": "ben_Beng", "xtts": "bn", "display": "Bengali",   "flag": "🇮🇳", "region": "indian"},
    "marathi":   {"whisper": "mr", "indictrans": "mar_Deva", "xtts": "hi", "display": "Marathi",   "flag": "🇮🇳", "region": "indian"},
    "kannada":   {"whisper": "kn", "indictrans": "kan_Knda", "xtts": "kn", "display": "Kannada",   "flag": "🇮🇳", "region": "indian"},
    "malayalam": {"whisper": "ml", "indictrans": "mal_Mlym", "xtts": "ml", "display": "Malayalam", "flag": "🇮🇳", "region": "indian"},
    "gujarati":  {"whisper": "gu", "indictrans": "guj_Gujr", "xtts": "hi", "display": "Gujarati",  "flag": "🇮🇳", "region": "indian"},
    "punjabi":   {"whisper": "pa", "indictrans": "pan_Guru", "xtts": "hi", "display": "Punjabi",   "flag": "🇮🇳", "region": "indian"},
    "odia":      {"whisper": "or", "indictrans": "ory_Orya", "xtts": "hi", "display": "Odia",      "flag": "🇮🇳", "region": "indian"},
    "urdu":      {"whisper": "ur", "indictrans": "urd_Arab", "xtts": "hi", "display": "Urdu",      "flag": "🇵🇰", "region": "indian"},

    # ── Foreign Languages ──
    "english":    {"whisper": "en", "nllb": "eng_Latn", "xtts": "en", "display": "English",    "flag": "🇬🇧", "region": "foreign"},
    "french":     {"whisper": "fr", "nllb": "fra_Latn", "xtts": "fr", "display": "French",     "flag": "🇫🇷", "region": "foreign"},
    "spanish":    {"whisper": "es", "nllb": "spa_Latn", "xtts": "es", "display": "Spanish",    "flag": "🇪🇸", "region": "foreign"},
    "german":     {"whisper": "de", "nllb": "deu_Latn", "xtts": "de", "display": "German",     "flag": "🇩🇪", "region": "foreign"},
    "italian":    {"whisper": "it", "nllb": "ita_Latn", "xtts": "it", "display": "Italian",    "flag": "🇮🇹", "region": "foreign"},
    "portuguese": {"whisper": "pt", "nllb": "por_Latn", "xtts": "pt", "display": "Portuguese", "flag": "🇧🇷", "region": "foreign"},
    "russian":    {"whisper": "ru", "nllb": "rus_Cyrl", "xtts": "ru", "display": "Russian",    "flag": "🇷🇺", "region": "foreign"},
    "japanese":   {"whisper": "ja", "nllb": "jpn_Jpan", "xtts": "ja", "display": "Japanese",   "flag": "🇯🇵", "region": "foreign"},
    "korean":     {"whisper": "ko", "nllb": "kor_Hang", "xtts": "ko", "display": "Korean",     "flag": "🇰🇷", "region": "foreign"},
    "chinese":    {"whisper": "zh", "nllb": "zho_Hans", "xtts": "zh-cn", "display": "Chinese",   "flag": "🇨🇳", "region": "foreign"},
    "arabic":     {"whisper": "ar", "nllb": "arb_Arab", "xtts": "ar", "display": "Arabic",     "flag": "🇸🇦", "region": "foreign"},
    "turkish":    {"whisper": "tr", "nllb": "tur_Latn", "xtts": "tr", "display": "Turkish",    "flag": "🇹🇷", "region": "foreign"},
    "dutch":      {"whisper": "nl", "nllb": "nld_Latn", "xtts": "nl", "display": "Dutch",      "flag": "🇳🇱", "region": "foreign"},
    "polish":     {"whisper": "pl", "nllb": "pol_Latn", "xtts": "pl", "display": "Polish",     "flag": "🇵🇱", "region": "foreign"},
    "swedish":    {"whisper": "sv", "nllb": "swe_Latn", "xtts": "sv", "display": "Swedish",    "flag": "🇸🇪", "region": "foreign"},
    "czech":      {"whisper": "cs", "nllb": "ces_Latn", "xtts": "cs", "display": "Czech",      "flag": "🇨🇿", "region": "foreign"},
    "romanian":   {"whisper": "ro", "nllb": "ron_Latn", "xtts": "ro", "display": "Romanian",   "flag": "🇷🇴", "region": "foreign"},
    "hungarian":  {"whisper": "hu", "nllb": "hun_Latn", "xtts": "hu", "display": "Hungarian",  "flag": "🇭🇺", "region": "foreign"},
    "finnish":    {"whisper": "fi", "nllb": "fin_Latn", "xtts": "fi", "display": "Finnish",    "flag": "🇫🇮", "region": "foreign"},
    "ukrainian":  {"whisper": "uk", "nllb": "ukr_Cyrl", "xtts": "uk", "display": "Ukrainian",  "flag": "🇺🇦", "region": "foreign"},
    "indonesian": {"whisper": "id", "nllb": "ind_Latn", "xtts": "id", "display": "Indonesian", "flag": "🇮🇩", "region": "foreign"},
    "thai":       {"whisper": "th", "nllb": "tha_Thai", "xtts": "th", "display": "Thai",       "flag": "🇹🇭", "region": "foreign"},
    "vietnamese": {"whisper": "vi", "nllb": "vie_Latn", "xtts": "vi", "display": "Vietnamese", "flag": "🇻🇳", "region": "foreign"},
}

# ── API Key Plans ──
API_KEY_PLANS = {
    "free": {
        "tokens_total": 1000,
        "rate_limit_per_min": 5,
        "max_video_duration": 300,      # 5 min
        "max_video_size_mb": 100,
        "lip_sync_allowed": False,
        "concurrent_jobs": 1,
        "price": "$0",
    },
    "starter": {
        "tokens_total": 10000,
        "rate_limit_per_min": 20,
        "max_video_duration": 900,      # 15 min
        "max_video_size_mb": 300,
        "lip_sync_allowed": True,
        "concurrent_jobs": 3,
        "price": "$29/mo",
    },
    "pro": {
        "tokens_total": 50000,
        "rate_limit_per_min": 60,
        "max_video_duration": 1800,     # 30 min
        "max_video_size_mb": 500,
        "lip_sync_allowed": True,
        "concurrent_jobs": 5,
        "price": "$99/mo",
    },
    "unlimited": {
        "tokens_total": 999999,
        "rate_limit_per_min": 120,
        "max_video_duration": 3600,     # 60 min
        "max_video_size_mb": 1000,
        "lip_sync_allowed": True,
        "concurrent_jobs": 10,
        "price": "$249/mo",
    },
}

# Token cost per second of video
TOKENS_PER_SECOND = 1  # 1 token = 1 second of video


def get_device() -> str:
    if DEVICE != "auto":
        return DEVICE
    import torch
    if torch.cuda.is_available():
        print(f"[CONFIG] GPU: {torch.cuda.get_device_name(0)}")
        return "cuda"
    print("[CONFIG] No GPU — using CPU")
    return "cpu"