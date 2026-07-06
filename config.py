"""
Central configuration for the AI Dubbing System.
All settings are loaded from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Base Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMP_DIR = BASE_DIR / "temp"

# Create directories if they don't exist
for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ─── Server Settings ─────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ─── Whisper Settings ────────────────────────────────────────
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny, base, small, medium, large

# ─── ElevenLabs Voice Cloning Settings ───────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Voice ID to use for TTS. Leave empty to use the default (Adam — free-tier premade).
# Only premade voices and your own cloned voices work on the free plan via API.
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── Groq API (Translation + Diacritization) ─────────────────
GROQ_API_KEY_TRANSLATION = os.getenv("GROQ_API_KEY_TRANSLATION", "")
GROQ_API_KEY_DIACRITIZATION = os.getenv("GROQ_API_KEY_DIACRITIZATION", "")

# ─── Google Gemini API (Arabic Translation + Diacritization) ──
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ─── Translation Settings ────────────────────────────────────
# Supported language pairs (source -> target)
LANGUAGE_MODELS = {
    "en-ar": "Helsinki-NLP/opus-mt-en-ar",
    "en-fr": "Helsinki-NLP/opus-mt-en-fr",
    "en-de": "Helsinki-NLP/opus-mt-en-de",
    "en-es": "Helsinki-NLP/opus-mt-en-es",
    "en-it": "Helsinki-NLP/opus-mt-en-it",
    "en-pt": "Helsinki-NLP/opus-mt-en-pt",
    "en-ru": "Helsinki-NLP/opus-mt-en-ru",
    "en-zh": "Helsinki-NLP/opus-mt-en-zh",
    "en-ja": "Helsinki-NLP/opus-mt-en-jap",
    "en-ko": "Helsinki-NLP/opus-mt-en-ko",
    "en-hi": "Helsinki-NLP/opus-mt-en-hi",
    "en-tr": "Helsinki-NLP/opus-mt-en-tr",
    "ar-en": "Helsinki-NLP/opus-mt-ar-en",
    "fr-en": "Helsinki-NLP/opus-mt-fr-en",
    "de-en": "Helsinki-NLP/opus-mt-de-en",
    "es-en": "Helsinki-NLP/opus-mt-es-en",
}

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "hi": "Hindi",
    "tr": "Turkish",
}

# ─── Edge TTS Settings ───────────────────────────────────────
# Edge TTS voice presets mapped to language
EDGE_TTS_VOICES = {
    "en": "en-US-AriaNeural",
    "ar": "ar-EG-SalmaNeural",  # More natural female voice
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-IsabellaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "hi": "hi-IN-SwaraNeural",
    "tr": "tr-TR-EmelNeural",
}

# ─── File Settings ────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", 500))
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv"}

# ─── Job Settings ─────────────────────────────────────────────
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 2))

# ─── Mixing Settings ──────────────────────────────────────────
# Set to 0.0 to completely delete original audio from final video
BG_VOLUME = float(os.getenv("BG_VOLUME", 0.0))
