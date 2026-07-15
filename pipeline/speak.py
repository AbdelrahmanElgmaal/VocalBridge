"""
Stage 9 — Speak (Edge TTS & OmniVoice engines)

Synthesise speech for every subtitle entry using either Microsoft Edge TTS
or the local OmniVoice model-based zero-shot voice cloner.
"""

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Tuple

import edge_tts
import numpy as np
import soundfile as sf

from pipeline.cache import get_segment_audio, mark_segment_done, segment_is_cached, get_segment_metadata
from utils.logger import pipeline_logger as logger
from utils.srt_utils import read_srt

# ── Toggle Engine ─────────────────────────────────────────────
USE_OMNIVOICE = True  # Set to True to use OmniVoice (voice cloning/design), False to use Edge TTS
OMNIVOICE_ENABLE_HEAD_TRIM = False  # Set to True to enable onset click head trim in voice-cloning mode

# ── General Constants ─────────────────────────────────────────
SAMPLE_RATE = 24_000  # Both engines output/expect 24 kHz audio
EDGE_RATE_MAX = 50   # Edge TTS rate parameter range cap (empirical)
EDGE_RATE_MIN = -50

# Rate delta below which we skip Pass 2 in Edge TTS (avoids redundant call)
RATE_SKIP_THRESHOLD = 2  # percent

# Bounded concurrency: max simultaneous Edge TTS HTTP requests
_CONCURRENCY = 10

# Retry policy for Edge TTS transient network errors
_MAX_RETRIES = 2
_RETRY_DELAYS = [1.0, 3.0]  # seconds between retries

# ── OmniVoice Generation Configuration (Tuning) ────────────────
OMNIVOICE_POSITION_TEMPERATURE = 3.00  # reduces stochastic drift in mask-position selection (default: 5.0)
OMNIVOICE_GUIDANCE_SCALE = 2.0         # stronger adherence to ref_audio/ref_text conditioning (default: 2.0)
OMNIVOICE_NUM_STEP = 48                # more decoding steps, better quality (default: 32)

# Model cache and locks for OmniVoice
_omnivoice_model = None
_model_lock = threading.Lock()

# ── Locate FFmpeg binary ───────────────────────────────────────
def _get_ffmpeg_exe() -> str:
    """Return the path to a working ffmpeg executable."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        # Also add to PATH so child processes spawned by edge-tts can find it.
        ffmpeg_dir = str(Path(ffmpeg_exe).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        return ffmpeg_exe
    except Exception as exc:
        raise RuntimeError(
            "ffmpeg not found on PATH and imageio_ffmpeg is not installed. "
            "Install ffmpeg or add it to PATH."
        ) from exc

_FFMPEG_EXE = _get_ffmpeg_exe()


# ── Arabic Neural Voice Lookup Table (Edge TTS) ──────────────
ARABIC_VOICES: dict[tuple, str] = {
    ("male",   "adult"): "ar-SA-HamedNeural",
    ("male",   "young"): "ar-SA-HamedNeural",   # only one male SA voice
    ("male",   "old"):   "ar-SA-HamedNeural",
    ("female", "adult"): "ar-SA-ZariyahNeural",
    ("female", "young"): "ar-EG-SalmaNeural",   # younger-sounding EG voice
    ("female", "old"):   "ar-SA-ZariyahNeural",
}
DEFAULT_VOICE = "ar-SA-HamedNeural"


def _select_voice_edge(
    gender: Optional[str] = None,
    age: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    """Map UI voice parameters to an Edge TTS Arabic neural voice name."""
    g = (gender or "male").lower().strip()
    a = (age or "adult").lower().strip()

    if pitch and pitch not in ("default", ""):
        logger.warning(
            f"  ⚠️ speak.py: `pitch='{pitch}'` has no Edge TTS equivalent. "
            f"Pitch is a no-op for this engine path."
        )
    if style and style not in ("default", "normal", ""):
        logger.warning(
            f"  ⚠️ speak.py: `style='{style}'` has no Edge TTS equivalent. "
            f"Style is a no-op for this engine path."
        )

    voice = ARABIC_VOICES.get((g, a))
    if voice is None:
        logger.warning(
            f"  ⚠️ No voice mapping for (gender='{g}', age='{a}'). "
            f"Falling back to default: {DEFAULT_VOICE}"
        )
        voice = DEFAULT_VOICE
    return voice


# ── Lazy Loading OmniVoice Model ──────────────────────────────
def _load_omnivoice_model():
    """Lazy load OmniVoice model and initialize lock."""
    global _omnivoice_model
    if _omnivoice_model is None:
        import torch
        from omnivoice import OmniVoice
        
        logger.info("Loading OmniVoice model (from pretrained k2-fsa/OmniVoice)...")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if "cuda" in device else torch.float32
        
        _omnivoice_model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=device,
            dtype=dtype,
        )
        logger.info("OmniVoice model loaded successfully.")
        
    return _omnivoice_model, _model_lock


# ── Helpers ───────────────────────────────────────────────────
def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _trim_tail(arr: np.ndarray, sr: int) -> np.ndarray:
    """
    Energy-based tail trimmer: cut where signal drops below -40 dB for >100 ms.
    Applied BEFORE the speed-correction duration measurement.
    """
    amp_threshold = 10 ** (-40.0 / 20.0)
    active = np.where(np.abs(arr) > amp_threshold)[0]
    if len(active) == 0:
        return arr
    trim_idx = min(len(arr), active[-1] + int(sr * 0.100))
    return arr[:trim_idx]


def _load_audio_numpy(path: str, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """Decode any audio file to float32 mono numpy array via ffmpeg."""
    cmd = [
        _FFMPEG_EXE, "-y", "-i", path,
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ar", str(target_sr), "-ac", "1",
        "pipe:1",
    ]
    startupinfo = None
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        startupinfo=startupinfo,
    )
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg decode failed: {err.decode('utf-8', errors='ignore')[:300]}"
        )
    arr = np.frombuffer(out, dtype=np.float32).copy()
    return arr


def _rate_str(rate_pct: int) -> str:
    """Format rate_pct as Edge TTS rate string, e.g. +12% or -5%."""
    return f"{rate_pct:+d}%"


def _is_job_cancelled(job_id: str) -> bool:
    """Query SQLite database to see if the job's status has been set to cancelled."""
    import sqlite3
    import config
    db_path = config.BASE_DIR / "jobs.db"
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == "cancelled":
            return True
    except Exception:
        pass
    return False


# ── OmniVoice Helpers ─────────────────────────────────────────
def _normalize_lang_for_omnivoice(lang: Optional[str]) -> Optional[str]:
    """Normalizes the target language string to map recognized languages in OmniVoice."""
    if not lang:
        return None
    lang_clean = lang.lower().strip()
    if lang_clean in ("ar", "arabic"):
        return "standard arabic"
    return lang


def _trim_head(
    arr: np.ndarray,
    sr: int,
    skip_ms: float = 10.0,
    threshold: float = 0.012,
    window_ms: float = 10.0,
    cushion_ms: float = 40.0,
) -> np.ndarray:
    """
    Trims the leading click, transition noise, and silent commas from the audio.
    Skips the first `skip_ms` to avoid the initial massive click, then detects
    the speech onset using energy thresholding, and returns the audio starting
    from the onset (minus `cushion_ms` to avoid clipping the first word).
    """
    skip_samples = int((skip_ms / 1000.0) * sr)
    window_size = int((window_ms / 1000.0) * sr)
    cushion_samples = int((cushion_ms / 1000.0) * sr)
    
    if len(arr) <= skip_samples:
        return arr
        
    detected_idx = skip_samples
    for i in range(skip_samples, len(arr) - window_size, window_size):
        window = arr[i : i + window_size]
        rms = np.sqrt(np.mean(window ** 2))
        if rms > threshold:
            detected_idx = i
            break
            
    trim_start = max(0, detected_idx - cushion_samples)
    logger.info(f"  [OmniVoice Head Trim] Click/silence trimmed: onset={detected_idx/sr*1000:.1f}ms, cut={trim_start/sr*1000:.1f}ms")
    return arr[trim_start:]


def is_audio_valid(file_path: str) -> bool:
    """
    Validates a generated audio segment to ensure it is not silent or hallucinated.
    """
    try:
        p = Path(file_path)
        if not p.exists():
            return False
            
        data, sr = sf.read(str(p))
        if data.size == 0:
            return False
            
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
            
        rms_total = np.sqrt(np.mean(data ** 2))
        silence_threshold = 0.005
        silent_frames = np.sum(np.abs(data) < silence_threshold)
        silence_ratio = silent_frames / len(data)
        
        if rms_total < 0.002:
            logger.warning(f"  [Audio Validation] Failed: extremely low RMS energy ({rms_total:.6f})")
            return False
            
        if silence_ratio >= 0.40:
            logger.warning(f"  [Audio Validation] Failed: silence ratio too high ({silence_ratio * 100:.1f}%)")
            return False
            
        return True
    except Exception as exc:
        logger.warning(f"  [Audio Validation] Failed with read error: {exc}")
        return False


def _prepare_voice_clone(
    whisper_srt_path: Optional[str],
    original_audio: str,
    temp_dir: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts a dynamic 3-10 second clip of spoken audio and its transcript for voice cloning.
    Starts from the first spoken segment to avoid silence if Whisper transcript is available.
    Otherwise, extracts from the beginning.
    Caches the extracted audio and text in the job directory.
    Returns (ref_audio_path, ref_text).
    """
    if not original_audio or not Path(original_audio).exists():
        logger.warning("No original audio path provided for voice cloning.")
        return None, None

    job_dir = Path(temp_dir).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    ref_audio_path = str(job_dir / "ref_clone.wav")
    ref_text_path = str(job_dir / "ref_clone.txt")

    # Try to load from cache
    if Path(ref_audio_path).exists() and Path(ref_text_path).exists():
        try:
            with open(ref_text_path, "r", encoding="utf-8") as f:
                cached_text = f.read().strip()
            logger.info(f"🗣️ Voice Clone Reference Audio Path: {ref_audio_path}")
            logger.info(f"📝 Voice Clone Reference Text: '{cached_text}'")
            return ref_audio_path, cached_text
        except Exception as e:
            logger.warning(f"Failed to read cached voice clone files: {e}. Re-extracting...")

    # Get total duration of the original audio
    try:
        total_dur = sf.info(original_audio).duration
    except Exception as exc:
        logger.warning(f"Could not get audio duration using soundfile: {exc}. Defaulting to 10.0s window.")
        total_dur = 10.0

    # Locate Whisper SRT and parse entries
    entries = []
    if whisper_srt_path and Path(whisper_srt_path).exists():
        entries = read_srt(whisper_srt_path)

    # Find the first non-empty spoken segment
    first_entry = None
    if entries:
        for entry in entries:
            if entry.text.strip() and re.search(r'[^\W\d_]', entry.text, re.UNICODE):
                first_entry = entry
                break

    if first_entry:
        start_time = first_entry.start
        
        # Check speech segments in [start_time, start_time + 10.0]
        overlapping_entries = []
        for entry in entries:
            if entry.start >= start_time and entry.start < start_time + 10.0:
                if entry.text.strip() and re.search(r'[^\W\d_]', entry.text, re.UNICODE):
                    overlapping_entries.append(entry)
                    
        # Select entries that sum up to at least 5.0 seconds
        selected_entries = []
        accumulated_dur = 0.0
        for entry in overlapping_entries:
            accumulated_dur = entry.end - start_time
            selected_entries.append(entry)
            if accumulated_dur >= 5.0:
                break
                
        if selected_entries:
            duration = selected_entries[-1].end - start_time
            ref_texts = [e.text.strip() for e in selected_entries if e.text.strip()]
            ref_text = " ".join(ref_texts).strip()
        else:
            duration = max(3.0, min(10.0, total_dur))
            ref_text = None
    else:
        # Fallback to starting from 0.0
        logger.info("No Whisper SRT speech segments found. Extracting reference audio starting from 0.0s.")
        start_time = 0.0
        duration = max(3.0, min(10.0, total_dur))
        ref_text = None

    if duration <= 0.1:
        logger.warning("Original audio duration is too short for cloning.")
        return None, None
        
    # Run ffmpeg to extract the audio
    cmd = [
        _FFMPEG_EXE, "-y",
        "-ss", f"{start_time:.3f}",
        "-i", original_audio,
        "-t", f"{duration:.3f}",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        ref_audio_path
    ]
    
    startupinfo = None
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    logger.info(f"Extracting voice clone reference audio (duration={duration:.2f}s) starting at {start_time:.2f}s")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        startupinfo=startupinfo,
    )
    out, err = proc.communicate()
    if proc.returncode != 0:
        logger.error(f"FFmpeg extraction of reference audio failed: {err.decode('utf-8', errors='ignore')}")
        return None, None
        
    if ref_text is None and first_entry:
        ref_text = first_entry.text.strip()
            
    # Cache the ref text to file
    try:
        with open(ref_text_path, "w", encoding="utf-8") as f:
            f.write(ref_text or "")
    except Exception as e:
        logger.warning(f"Failed to cache ref_text: {e}")

    logger.info(f"🗣️ Voice Clone Reference Audio Path: {ref_audio_path}")
    logger.info(f"📝 Voice Clone Reference Text: '{ref_text}'")
    logger.info(f"Voice Clone Reference window size determined: {duration:.2f}s")
    return ref_audio_path, ref_text


def _get_voice_clone_prompt(
    gender: Optional[str] = "male",
    age: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    """Build a natural language voice description using strictly valid OmniVoice instruct items."""
    parts = []
    # gender
    g = (gender or "male").lower().strip()
    if g == "female":
        parts.append("female")
    else:
        parts.append("male")
        
    # age
    a = (age or "adult").lower().strip()
    if a == "child":
        parts.append("child")
    elif a in ("teenager", "young"):
        parts.append("young adult")
    elif a in ("middle-aged", "middle_aged", "adult"):
        parts.append("middle-aged")
    elif a in ("elderly", "old"):
        parts.append("elderly")
        
    # pitch
    p = (pitch or "medium").lower().strip()
    if p in ("very low", "very_low"):
        parts.append("very low pitch")
    elif p == "low":
        parts.append("low pitch")
    elif p in ("moderate", "medium", "moderate pitch"):
        parts.append("moderate pitch")
    elif p == "high":
        parts.append("high pitch")
    elif p in ("very high", "very_high"):
        parts.append("very high pitch")
        
    # style
    s = (style or "normal").lower().strip()
    if s == "whisper":
        parts.append("whisper")
        
    return ", ".join(parts)


def _change_speed_ffmpeg(audio_arr: np.ndarray, speed: float) -> np.ndarray:
    """
    Time-stretch audio array using ffmpeg's high-quality atempo filter.
    speed > 1.0 makes it faster/shorter; speed < 1.0 makes it slower/longer.
    """
    if abs(speed - 1.0) < 0.01:
        return audio_arr

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, "in.wav")
        out_path = os.path.join(tmpdir, "out.wav")
        
        # Write input array
        sf.write(in_path, audio_arr, SAMPLE_RATE)
        
        # Build atempo filter string (chain if speed is outside [0.5, 2.0])
        filters = []
        rem = speed
        while rem > 2.0:
            filters.append("atempo=2.0")
            rem /= 2.0
        while rem < 0.5:
            filters.append("atempo=0.5")
            rem /= 0.5
        if abs(rem - 1.0) > 0.01:
            filters.append(f"atempo={rem:.4f}")
            
        filter_str = ",".join(filters)
        
        cmd = [
            _FFMPEG_EXE, "-y",
            "-i", in_path,
            "-filter:a", filter_str,
            out_path
        ]
        
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        out, err = proc.communicate()
        if proc.returncode != 0:
            logger.error(f"FFmpeg atempo speed change failed: {err.decode('utf-8', errors='ignore')}")
            return audio_arr
            
        try:
            stretched_arr, _ = sf.read(out_path)
            return stretched_arr
        except Exception as exc:
            logger.error(f"Failed to read stretched audio: {exc}")
            return audio_arr


# ── Edge TTS segment generator ───────────────────────────────
async def _generate_segment_edge(
    i: int,
    entry,
    slot_dur: float,
    out_path: str,
    voice: str,
    job_id: str,
    text_hash: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """
    Generate TTS audio for a single SRT segment with two-pass speed correction.
    """
    text = entry.text.strip()

    async def _call_edge(rate_pct: int, dest: str) -> None:
        """Single Edge TTS call with retry."""
        rate = _rate_str(rate_pct)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                comm = edge_tts.Communicate(text, voice, rate=rate)
                await comm.save(dest)
                return
            except Exception as exc:
                if attempt == _MAX_RETRIES:
                    raise RuntimeError(
                        f"Edge TTS failed after {_MAX_RETRIES + 1} attempts: {exc}"
                    ) from exc
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.warning(
                    f"  ⚠️ Seg {i} — Edge TTS attempt {attempt + 1} failed "
                    f"({exc}). Retrying in {delay:.0f}s…"
                )
                await asyncio.sleep(delay)

    async with semaphore:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_mp3 = str(Path(tmp_dir) / "pass1.mp3")
            out_mp3  = str(Path(tmp_dir) / "pass2.mp3")
            out_wav  = out_path  # final destination is always a .wav

            # ── Pass 1: neutral rate → measure duration ────────────────
            await _call_edge(0, tmp_mp3)

            arr = _load_audio_numpy(tmp_mp3)
            if arr.size == 0 or np.max(np.abs(arr)) <= 0.005:
                raise ValueError(f"Edge TTS produced silent/empty audio for: '{text}'")

            arr = _trim_tail(arr, SAMPLE_RATE)
            actual_dur = len(arr) / SAMPLE_RATE

            # ── Speed correction calculation ───────────────────────────
            if slot_dur > 0:
                speed_ratio = actual_dur / slot_dur
            else:
                speed_ratio = 1.0

            raw_rate_pct = round((speed_ratio - 1) * 100)          # pre-clamp value
            clamped_rate_pct = max(0, min(EDGE_RATE_MAX, raw_rate_pct))
            was_capped = (raw_rate_pct > EDGE_RATE_MAX)            # CAPPED DETECTION (SPEED-UP ONLY)
            rate_pct = clamped_rate_pct

            if was_capped:
                logger.warning(
                    f"  ⚠️ Seg {i} ['{text[:40]}…']: required rate={raw_rate_pct:+d}% "
                    f"exceeds Edge TTS cap (+{EDGE_RATE_MAX}%). "
                    f"Clamped to {clamped_rate_pct:+d}%. "
                    f"Downstream reconciliation will need to borrow silence from elsewhere to avoid drift."
                )

            # ── Pass 2: re-generate only if rate change is meaningful ──
            if rate_pct >= RATE_SKIP_THRESHOLD:
                await _call_edge(rate_pct, out_mp3)
                arr = _load_audio_numpy(out_mp3)
                arr = _trim_tail(arr, SAMPLE_RATE)
                if arr.size == 0 or np.max(np.abs(arr)) <= 0.005:
                    logger.warning(
                        f"  ⚠️ Seg {i} — Pass 2 produced silence; falling back to Pass 1 audio."
                    )
                    arr = _load_audio_numpy(tmp_mp3)
                    arr = _trim_tail(arr, SAMPLE_RATE)
                actual_dur = len(arr) / SAMPLE_RATE
                logger.info(
                    f"  📊 Seg {i} — Pass 2 at {_rate_str(rate_pct)} | "
                    f"slot={slot_dur:.2f}s | actual={actual_dur:.2f}s"
                )
            else:
                actual_dur = len(arr) / SAMPLE_RATE
                logger.info(
                    f"  📊 Seg {i} — single-pass (rate {_rate_str(rate_pct)} < threshold) | "
                    f"slot={slot_dur:.2f}s | actual={actual_dur:.2f}s"
                )

            # ── Write final WAV ────────────────────────────────────────
            Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
            sf.write(out_wav, arr, SAMPLE_RATE)

            mark_segment_done(job_id, i, text_hash, out_wav, was_capped, slot_dur, actual_dur)
            return {
                "path": out_wav,
                "actual_duration_sec": actual_dur,
                "slot_duration_sec": slot_dur,
                "was_capped": was_capped,
            }


# ── OmniVoice segment generator ───────────────────────────────
async def _generate_segment_omnivoice(
    i: int,
    entry,
    slot_dur: float,
    out_path: str,
    model,
    model_lock,
    ref_audio_path: Optional[str],
    ref_text: Optional[str],
    instruct: Optional[str],
    job_id: str,
    text_hash: str,
    target_lang: str,
) -> dict:
    """
    Generate TTS audio for a single SRT segment using OmniVoice.
    """
    text = entry.text.strip()

    lang_norm = _normalize_lang_for_omnivoice(target_lang)

    text_for_model = text


    async def _call_omnivoice(speed: float) -> np.ndarray:
        def _generate_with_lock():
            with model_lock:
                if ref_audio_path:
                    # Voice Cloning mode: Do NOT pass speed to OmniVoice generate()
                    return model.generate(
                        text=text_for_model,
                        ref_audio=ref_audio_path,
                        ref_text=ref_text,
                        language=lang_norm,
                        position_temperature=OMNIVOICE_POSITION_TEMPERATURE,
                        guidance_scale=OMNIVOICE_GUIDANCE_SCALE,
                        num_step=OMNIVOICE_NUM_STEP,
                    )
                else:
                    # Voice Design mode: Pass speed to model.generate
                    return model.generate(
                        text=text_for_model,
                        instruct=instruct,
                        speed=speed,
                        language=lang_norm,
                    )

        audio = await asyncio.to_thread(_generate_with_lock)
            
        # Convert PyTorch tensor or list to NumPy array safely
        if hasattr(audio[0], "cpu"):
            arr = audio[0].cpu().numpy()
        else:
            arr = audio[0]
            
        if len(arr.shape) > 1:
            arr = arr.squeeze()
            
        return arr

    # ── Pass 1: speed=1.0 → measure duration ────────────────


    arr = None


    actual_dur = 0.0


    was_capped = False


    max_attempts = 3



    for attempt in range(max_attempts):


        try:


            arr = await _call_omnivoice(1.0)


            if arr.size == 0 or np.max(np.abs(arr)) <= 0.005:


                raise ValueError("OmniVoice produced silent/empty audio")



            if ref_audio_path and OMNIVOICE_ENABLE_HEAD_TRIM:


                arr = _trim_head(arr, SAMPLE_RATE)



            arr = _trim_tail(arr, SAMPLE_RATE)


            actual_dur = len(arr) / SAMPLE_RATE



            # ── Speed correction calculation ───────────────────────────


            if slot_dur > 0:


                speed_ratio = actual_dur / slot_dur


            else:


                speed_ratio = 1.0



            # OmniVoice speed: values > 1.0 produce shorter/faster audio


            clamped_speed = max(1.0, min(1.5, speed_ratio))


            was_capped = (speed_ratio > 1.5)



            if was_capped:


                logger.warning(


                    f"  ⚠️ Seg {i} ['{text[:40]}…']: required speed={speed_ratio:.2f} "


                    f"exceeds OmniVoice speed cap (1.5). Clamped to 1.5. "


                    f"Downstream reconciliation will need to borrow silence to avoid drift."


                )



            # ── Apply Speed correction if speed change is meaningful ──


            if clamped_speed >= 1.02:


                if ref_audio_path:


                    # Voice Cloning: Apply post-hoc speed correction using ffmpeg atempo


                    logger.info(f"  stretch: applying post-hoc ffmpeg atempo speed correction: {clamped_speed:.2f}")


                    arr = await asyncio.to_thread(_change_speed_ffmpeg, arr, clamped_speed)


                else:


                    # Voice Design: Call OmniVoice model again with speed parameter (Pass 2)


                    pass1_arr = arr.copy()


                    try:


                        arr2 = await _call_omnivoice(clamped_speed)


                        arr2 = _trim_tail(arr2, SAMPLE_RATE)


                        if arr2.size == 0 or np.max(np.abs(arr2)) <= 0.005:


                            logger.warning(


                                f"  ⚠️ Seg {i} — Pass 2 produced silence; falling back to Pass 1 audio."


                            )


                            arr = pass1_arr


                        else:


                            arr = arr2


                    except Exception as exc:


                        logger.warning(


                            f"  ⚠️ Seg {i} — Pass 2 generation failed: {exc}; falling back to Pass 1 audio."


                        )


                        arr = pass1_arr



                actual_dur = len(arr) / SAMPLE_RATE


                logger.info(


                    f"  📊 Seg {i} — Speed correction applied at {clamped_speed:.2f} | "


                    f"slot={slot_dur:.2f}s | actual={actual_dur:.2f}s"


                )


            else:


                actual_dur = len(arr) / SAMPLE_RATE


                logger.info(


                    f"  📊 Seg {i} — single-pass (speed {clamped_speed:.2f} near 1.0) | "


                    f"slot={slot_dur:.2f}s | actual={actual_dur:.2f}s"


                )



            # ── Write WAV to out_path ────────────────────────────────────────


            Path(out_path).parent.mkdir(parents=True, exist_ok=True)


            sf.write(out_path, arr, SAMPLE_RATE)



            if is_audio_valid(out_path):


                break


            else:


                if attempt < max_attempts - 1:


                    logger.warning(


                        f"  ⚠️ Seg {i} validation failed. Retrying OmniVoice generation (attempt {attempt + 2}/{max_attempts})..."


                    )


                else:


                    logger.error(


                        f"  ❌ Seg {i} validation failed on final attempt ({max_attempts}/{max_attempts})."


                    )


        except Exception as exc:


            if attempt < max_attempts - 1:


                logger.warning(


                    f"  ⚠️ Seg {i} generation failed on attempt {attempt + 1}: {exc}. Retrying..."


                )


            else:


                logger.error(


                    f"  ❌ Seg {i} generation failed all {max_attempts} attempts. Error: {exc}"


                )


                raise exc



    mark_segment_done(job_id, i, text_hash, out_path, was_capped, slot_dur, actual_dur)
    
    return {
        "path": out_path,
        "actual_duration_sec": actual_dur,
        "slot_duration_sec": slot_dur,
        "was_capped": was_capped,
    }


# ── Edge TTS async orchestrator ──────────────────────────────
async def _speak_all_edge(
    entries,
    segments_dir: str,
    voice: str,
    job_id: str,
) -> Tuple[List[str], int, List[dict]]:
    """Drive all segment generation coroutines with bounded concurrency via Edge TTS."""
    if _is_job_cancelled(job_id):
        logger.warning(f"🛑 Job {job_id} cancelled: speak stage will not start.")
        raise asyncio.CancelledError(f"Job {job_id} was cancelled")

    semaphore = asyncio.Semaphore(_CONCURRENCY)
    segment_paths: List[Optional[str]] = [None] * len(entries)
    segment_details: List[Optional[dict]] = [None] * len(entries)
    skipped = 0

    pending_indices = []
    for i, entry in enumerate(entries):
        slot_dur = entry.end - entry.start
        text = entry.text.strip()
        if not text or not re.search(r'[^\W\d_]', text, re.UNICODE):
            logger.info(f"  ⏭️  Seg {i} skipped (no speakable text): '{text}'")
            segment_paths[i] = ""
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": slot_dur,
                "was_capped": False,
            }
            continue

        th = _text_hash(text)
        if segment_is_cached(job_id, i, th):
            cached = get_segment_audio(job_id, i, th)
            if cached and Path(cached).exists():
                logger.info(f"  ⚡ Seg {i} — cache hit → {cached}")
                segment_paths[i] = cached
                skipped += 1
                
                meta = get_segment_metadata(job_id, i, th)
                if meta and isinstance(meta, dict) and "was_capped" in meta:
                    segment_details[i] = {
                        "path": cached,
                        "actual_duration_sec": meta.get("actual_duration_sec", 0.0),
                        "slot_duration_sec": meta.get("slot_duration_sec", slot_dur),
                        "was_capped": meta.get("was_capped", False),
                    }
                else:
                    try:
                        actual_dur = sf.info(cached).duration
                    except Exception:
                        actual_dur = 0.0
                    segment_details[i] = {
                        "path": cached,
                        "actual_duration_sec": actual_dur,
                        "slot_duration_sec": slot_dur,
                        "was_capped": False,
                    }
                continue

        pending_indices.append(i)

    async def _run(i: int) -> None:
        if _is_job_cancelled(job_id):
            logger.warning(f"🛑 Job {job_id} cancelled: aborting segment {i} synthesis.")
            raise asyncio.CancelledError(f"Job {job_id} was cancelled")

        entry = entries[i]
        text = entry.text.strip()
        th = _text_hash(text)
        out = str(Path(segments_dir) / f"seg_{i:05d}.wav")
        slot_dur = entry.end - entry.start

        logger.info(f"  🔊 Seg {i} — synthesising via Edge TTS | slot={slot_dur:.2f}s")
        try:
            res_dict = await _generate_segment_edge(
                i, entry, slot_dur, out, voice, job_id, th, semaphore
            )
            segment_paths[i] = res_dict["path"]
            segment_details[i] = res_dict
            logger.info(f"  ✅ Seg {i} — done → {res_dict['path']}")
        except Exception as exc:
            logger.error(f"  ❌ Seg {i} failed: {exc}")
            segment_paths[i] = ""
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": slot_dur,
                "was_capped": False,
            }

    await asyncio.gather(*[_run(i) for i in pending_indices])

    # Replace any remaining None
    for i in range(len(segment_paths)):
        if segment_paths[i] is None:
            segment_paths[i] = ""
        if segment_details[i] is None:
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": entries[i].end - entries[i].start,
                "was_capped": False,
            }

    return segment_paths, skipped, segment_details


# ── OmniVoice async orchestrator ──────────────────────────────
async def _speak_all_omnivoice(
    entries,
    segments_dir: str,
    target_lang: str,
    job_id: str,
    original_audio_path: Optional[str],
    whisper_srt_path: Optional[str],
    clone_speaker: bool,
    gender: Optional[str],
    age: Optional[str],
    pitch: Optional[str],
    style: Optional[str],
) -> Tuple[List[str], int, List[dict]]:
    """Drive all segment generation coroutines with local OmniVoice."""
    if _is_job_cancelled(job_id):
        logger.warning(f"🛑 Job {job_id} cancelled: speak stage will not start.")
        raise asyncio.CancelledError(f"Job {job_id} was cancelled")

    segment_paths: List[Optional[str]] = [None] * len(entries)
    segment_details: List[Optional[dict]] = [None] * len(entries)
    skipped = 0

    # 1. Prepare cloning or design prompt
    ref_audio_path = None
    ref_text = None
    instruct = None
    
    if clone_speaker and original_audio_path:
        ref_audio_path, ref_text = await asyncio.to_thread(
            _prepare_voice_clone, whisper_srt_path, original_audio_path, segments_dir
        )
        
    if ref_audio_path is None:
        if clone_speaker:
            logger.warning("Voice cloning requested but failed to prepare reference audio. Falling back to Voice Design.")
        instruct = _get_voice_clone_prompt(gender, age, pitch, style)
        logger.info(f"Using Voice Design mode with instruction prompt: '{instruct}'")
    else:
        if ref_text:
            logger.info(f"Using Voice Cloning mode with reference text: '{ref_text}'")
        else:
            logger.info("Using Voice Cloning mode without reference text (auto-transcribing)")

    # 2. Load model & Lock
    model, model_lock = _load_omnivoice_model()

    # Identify segments that are already cached so we don't re-fire them.
    pending_indices = []
    for i, entry in enumerate(entries):
        slot_dur = entry.end - entry.start
        text = entry.text.strip()
        if not text or not re.search(r'[^\W\d_]', text, re.UNICODE):
            logger.info(f"  ⏭️  Seg {i} skipped (no speakable text): '{text}'")
            segment_paths[i] = ""
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": slot_dur,
                "was_capped": False,
            }
            continue

        th = _text_hash(text)
        if segment_is_cached(job_id, i, th):
            cached = get_segment_audio(job_id, i, th)
            if cached and Path(cached).exists():
                logger.info(f"  ⚡ Seg {i} — cache hit → {cached}")
                segment_paths[i] = cached
                skipped += 1
                
                # Retrieve metadata from cache
                meta = get_segment_metadata(job_id, i, th)
                if meta and isinstance(meta, dict) and "was_capped" in meta:
                    segment_details[i] = {
                        "path": cached,
                        "actual_duration_sec": meta.get("actual_duration_sec", 0.0),
                        "slot_duration_sec": meta.get("slot_duration_sec", slot_dur),
                        "was_capped": meta.get("was_capped", False),
                    }
                else:
                    try:
                        actual_dur = sf.info(cached).duration
                    except Exception:
                        actual_dur = 0.0
                    segment_details[i] = {
                        "path": cached,
                        "actual_duration_sec": actual_dur,
                        "slot_duration_sec": slot_dur,
                        "was_capped": False,
                    }
                continue

        pending_indices.append(i)

    # Run pending segments sequentially
    async def _run(i: int) -> None:
        if _is_job_cancelled(job_id):
            logger.warning(f"🛑 Job {job_id} cancelled: aborting segment {i} synthesis.")
            raise asyncio.CancelledError(f"Job {job_id} was cancelled")

        entry = entries[i]
        text = entry.text.strip()
        th = _text_hash(text)
        out = str(Path(segments_dir) / f"seg_{i:05d}.wav")
        slot_dur = entry.end - entry.start

        logger.info(f"  🔊 Seg {i} — synthesising via OmniVoice | slot={slot_dur:.2f}s")
        try:
            res_dict = await _generate_segment_omnivoice(
                i, entry, slot_dur, out, model, model_lock,
                ref_audio_path, ref_text, instruct, job_id, th, target_lang
            )
            segment_paths[i] = res_dict["path"]
            segment_details[i] = res_dict
            logger.info(f"  ✅ Seg {i} — done → {res_dict['path']}")
        except Exception as exc:
            logger.error(f"  ❌ Seg {i} failed: {exc}", exc_info=True)
            segment_paths[i] = ""
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": slot_dur,
                "was_capped": False,
            }

    await asyncio.gather(*[_run(i) for i in pending_indices])

    # Check for failures and hard-fail if any segment failed to generate
    failed_indices = [i for i in pending_indices if not segment_paths[i]]
    if failed_indices:
        raise RuntimeError(f"Speech synthesis failed for segments: {failed_indices}")

    # Replace any remaining None
    for i in range(len(segment_paths)):
        if segment_paths[i] is None:
            segment_paths[i] = ""
        if segment_details[i] is None:
            segment_details[i] = {
                "path": "",
                "actual_duration_sec": 0.0,
                "slot_duration_sec": entries[i].end - entries[i].start,
                "was_capped": False,
            }

    return segment_paths, skipped, segment_details


# ── Public entry point ────────────────────────────────────────
def speak(
    srt_path: str,
    segments_dir: str,
    target_lang: str,
    job_id: str,
    original_audio_path: str = None,
    voice_preset: str = None,
    gender: Optional[str] = "male",
    age: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = None,
    clone_speaker: bool = False,
    whisper_srt_path: str = None,
) -> dict:
    """
    Stage 9 entry point — synthesise all SRT segments via Edge TTS or OmniVoice.
    """
    entries = read_srt(srt_path)
    if not entries:
        raise ValueError("SRT is empty — nothing to speak")
    logger.info(f"📝 SRT loaded — {len(entries)} entries")

    Path(segments_dir).mkdir(parents=True, exist_ok=True)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if USE_OMNIVOICE:
        logger.info(f"🗣️  Stage 9 — Generating speech via OmniVoice")
        logger.info(f"  Cloning enabled: {clone_speaker}")

        if loop is not None:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    lambda: asyncio.run(
                        _speak_all_omnivoice(
                            entries, segments_dir, target_lang, job_id, original_audio_path,
                            whisper_srt_path, clone_speaker, gender, age, pitch, style
                        )
                    )
                )
                segment_paths, skipped, segment_details = future.result()
        else:
            segment_paths, skipped, segment_details = asyncio.run(
                _speak_all_omnivoice(
                    entries, segments_dir, target_lang, job_id, original_audio_path,
                    whisper_srt_path, clone_speaker, gender, age, pitch, style
                )
            )

        ref_prompt = _get_voice_clone_prompt(gender, age, pitch, style) if not clone_speaker else f"Cloned: {original_audio_path}"
        return {
            "segment_paths": segment_paths,
            "count": len(segment_paths),
            "skipped": skipped,
            "instruct": ref_prompt,
            "voice_clone_prompt": original_audio_path if clone_speaker else None,
            "segment_details": segment_details,
        }
    else:
        logger.info(f"🗣️  Stage 9 — Generating speech via Edge TTS")
        voice = _select_voice_edge(gender, age, pitch, style)
        logger.info(f"  Voice: {voice}  |  Concurrency: {_CONCURRENCY}")

        if loop is not None:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    lambda: asyncio.run(
                        _speak_all_edge(entries, segments_dir, voice, job_id)
                    )
                )
                segment_paths, skipped, segment_details = future.result()
        else:
            segment_paths, skipped, segment_details = asyncio.run(
                _speak_all_edge(entries, segments_dir, voice, job_id)
            )

        return {
            "segment_paths": segment_paths,
            "count": len(segment_paths),
            "skipped": skipped,
            "instruct": voice,
            "voice_clone_prompt": None,
            "segment_details": segment_details,
        }