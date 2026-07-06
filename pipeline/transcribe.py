"""
Stage 2 — Transcribe

Convert speech to **SRT subtitles** using one of three backends:
 • OpenAI Whisper API  (cloud, fast)
 • faster-whisper       (local, CTranslate2)
 • WhisperX            (local, word-level alignment)

Falls back gracefully: WhisperX → faster-whisper → openai-whisper.
"""
import os
import numpy as np
from pathlib import Path
from typing import Optional

from config import WHISPER_MODEL
from utils.logger import pipeline_logger as logger
from utils.srt_utils import SRTEntry, write_srt

# ── Module-level model cache ──
_whisper_model = None
_backend: Optional[str] = None


def _detect_backend() -> str:
    """Pick the best available Whisper backend."""
    global _backend
    if _backend:
        return _backend

    # ── Allow override via ENV ──
    env_backend = os.getenv("WHISPER_BACKEND")
    if env_backend in ("whisperx", "faster_whisper", "openai_whisper", "transformers_whisper"):
        _backend = env_backend
        logger.info(f"🚀 Using forced backend: {_backend}")
        return _backend

    try:
        import faster_whisper  # noqa
        _backend = "faster_whisper"
        logger.info("🔍 faster-whisper detected")
        return _backend
    except (ImportError, Exception):
        pass

    try:
        import transformers  # noqa
        _backend = "transformers_whisper"
        logger.info("🔍 transformers detected — using distil-whisper")
        return _backend
    except (ImportError, Exception):
        pass

    try:
        import whisperx  # noqa
        _backend = "whisperx"
        logger.info("🔍 WhisperX detected — using for word-level alignment")
        return _backend
    except (ImportError, Exception):
        pass


    try:
        import whisper  # noqa
        _backend = "openai_whisper"
        logger.info("🔍 Using openai-whisper")
        return _backend
    except (ImportError, Exception):
        pass

    raise RuntimeError("No Whisper backend found. Install openai-whisper, faster-whisper, whisperx, or transformers.")


def _load_audio(path: str, sr: int = 16000) -> np.ndarray:
    """Load WAV as float32 numpy — avoids ffmpeg dependency at runtime."""
    from scipy.io.wavfile import read as wav_read
    sample_rate, data = wav_read(path)

    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype != np.float32:
        data = data.astype(np.float32)

    if len(data.shape) > 1:
        data = data.mean(axis=1)

    if sample_rate != sr:
        from scipy.signal import resample
        n = int(len(data) * sr / sample_rate)
        data = resample(data, n).astype(np.float32)

    return data


# ── Backend: openai-whisper ──────────────────────────────────
def _transcribe_openai(audio_path: str, language: str):
    global _whisper_model
    import whisper
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        _whisper_model = whisper.load_model(WHISPER_MODEL)

    audio = _load_audio(audio_path)
    opts = {"fp16": False, "verbose": False}
    if language != "auto":
        opts["language"] = language

    result = _whisper_model.transcribe(audio, **opts)
    segments = result.get("segments", [])
    full_text = result.get("text", "").strip()
    return result.get("language", language), segments, full_text


# ── Backend: faster-whisper ──────────────────────────────────
def _transcribe_faster(audio_path: str, language: str):
    global _whisper_model
    from faster_whisper import WhisperModel
    if _whisper_model is None:
        logger.info(f"Loading faster-whisper: {WHISPER_MODEL}")
        _whisper_model  = WhisperModel("base", device="cpu", compute_type="int8")

    lang = language if language != "auto" else None
    segments, info = _whisper_model.transcribe(audio_path, language=lang)
    segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    full_text = " ".join([s["text"] for s in segs])
    return info.language, segs, full_text


# ── Backend: whisperx ────────────────────────────────────────
def _transcribe_whisperx(audio_path: str, language: str):
    import whisperx, torch
    device = 'cpu'
    model = whisperx.load_model(WHISPER_MODEL, device)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio)

    detected = result.get("language", language if language != "auto" else "en")

    # Word-level alignment
    try:
        align_model, meta = whisperx.load_align_model(language_code=detected, device=device)
        result = whisperx.align(result["segments"], align_model, meta, audio, device)
    except Exception as e:
        logger.warning(f"WhisperX alignment failed ({e}), using raw segments")

    full_text = " ".join([s.get("text", "").strip() for s in result.get("segments", [])])
    return detected, result.get("segments", []), full_text


# ── Backend: transformers ────────────────────────────────────
def _transcribe_transformers(audio_path: str, language: str):
    global _whisper_model
    from transformers import pipeline
    if _whisper_model is None:
        logger.info("Loading transformers distil-whisper model: distil-whisper/distil-medium.en")
        _whisper_model = pipeline("automatic-speech-recognition", model="distil-whisper/distil-medium.en")

    result = _whisper_model(audio_path, return_timestamps="chunk")
    detected_lang = "en"  # distil-medium.en is English-only
    segments = [{"start": chunk["timestamp"][0], "end": chunk["timestamp"][1], "text": chunk["text"]} for chunk in result["chunks"]]
    full_text = result["text"]
    return detected_lang, segments, full_text


# ── Public API ───────────────────────────────────────────────
def transcribe(audio_path: str, srt_output: str, language: str = "auto") -> dict:
    """
    Stage 2 entry point.

    Args:
        audio_path: Path to 16 kHz mono WAV
        srt_output: Where to write the .srt file
        language:   ISO-639-1 code or 'auto'

    Returns:
        dict: srt_path, language, entry_count
    """
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    backend = _detect_backend()
    logger.info(f"🎙️ Transcribing with {backend} (model={WHISPER_MODEL})")

    dispatch = {
        "openai_whisper": _transcribe_openai,
        "faster_whisper": _transcribe_faster,
        "whisperx": _transcribe_whisperx,
        "transformers_whisper": _transcribe_transformers,
    }
    detected_lang, raw_segments, full_text = dispatch[backend](audio_path, language)

    # Build SRT entries
    entries = []
    for i, seg in enumerate(raw_segments, 1):
        entries.append(SRTEntry(
            index=i,
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        ))

    write_srt(entries, srt_output)
    logger.info(f"✅ Transcribed → {len(entries)} cues, lang={detected_lang}")

    return {
        "srt_path": srt_output,
        "language": detected_lang,
        "full_text": full_text,
        "entry_count": len(entries),
    }
