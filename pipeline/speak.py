"""
Stage 9 — Speak  (Edge TTS engine)

Synthesise speech for every subtitle entry using Microsoft Edge TTS
(edge-tts library, unofficial endpoint).

Key behaviours preserved from the OmniVoice implementation:
  • Per-segment generation with individual WAV output + cache.
  • Two-pass speed correction: Pass 1 at +0%, measure actual duration,
    compute required Edge TTS `rate` param, Pass 2 only if |rate| ≥ 2%.
  • Overrun-without-cut: if the required rate exceeds ±50% cap, generate
    at the capped rate and log a WARNING — never trim mid-word.
  • Energy-tail trimming BEFORE duration measurement (same helper as before).
  • Bounded async concurrency (Semaphore(10)) instead of sequential GPU calls.
  • Per-segment retry on network failure (max 2 retries).

Removed from OmniVoice implementation (intentionally):
  • torch / OmniVoice model loading — Edge TTS is a remote API, no local model.
  • torch.manual_seed() / MD5-seed latent determinism — replaced by a named
    voice parameter; determinism is guaranteed by selecting the same voice name
    every run rather than a stochastic seed.
  • Warm-up phrase / primer-bleed logic — Edge TTS has a stateless HTTP
    architecture with no persistent model state between calls, so the tonal-
    drift / bleed issue that required OmniVoice priming does not exist here.
  • _get_voice_clone_prompt() / voice_clone_prompt latent — Edge TTS exposes
    no voice-cloning / speaker-latent API. Voice identity is set by voice name.
  • Manual comma-splitting array stitching — Edge TTS handles Arabic commas
    (، ) natively in its SSML/text path; tested and produces natural pausing.
  • build_instruct() free-text builder — replaced by _select_voice() lookup.
"""

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import edge_tts
import numpy as np
import soundfile as sf

from pipeline.cache import get_segment_audio, mark_segment_done, segment_is_cached, get_segment_metadata
from utils.logger import pipeline_logger as logger
from utils.srt_utils import read_srt

# ── Locate FFmpeg binary ───────────────────────────────────────
# Mirrors the approach in download.py: prefer the system ffmpeg when available,
# fall back to the imageio_ffmpeg bundled binary.  Resolved once at import time
# so every subprocess call gets the correct executable path.

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

# ── Constants ─────────────────────────────────────────────────

SAMPLE_RATE = 24_000  # Edge TTS outputs 24 kHz audio

# Edge TTS rate parameter range (empirical; log if clamped).
EDGE_RATE_MAX = 50   # +50%
EDGE_RATE_MIN = -50  # -50%

# Rate delta below which we skip Pass 2 (avoids a redundant API call for
# negligible speed differences).
RATE_SKIP_THRESHOLD = 2  # percent

# Bounded concurrency: max simultaneous Edge TTS HTTP requests.
_CONCURRENCY = 10

# Retry policy for transient network errors.
_MAX_RETRIES = 2
_RETRY_DELAYS = [1.0, 3.0]  # seconds between retries

# ── Arabic Neural Voice Lookup Table ─────────────────────────
# Keys: (gender, age)  →  Edge TTS voice name.
# Defaults to Saudi Arabic. Egyptian variant used for young female because
# ar-SA only has one female voice (ZariyahNeural).
# Full list: https://learn.microsoft.com/azure/ai-services/speech-service/language-support
ARABIC_VOICES: dict[tuple, str] = {
    ("male",   "adult"): "ar-SA-HamedNeural",
    ("male",   "young"): "ar-SA-HamedNeural",   # only one male SA voice
    ("male",   "old"):   "ar-SA-HamedNeural",
    ("female", "adult"): "ar-SA-ZariyahNeural",
    ("female", "young"): "ar-EG-SalmaNeural",   # younger-sounding EG voice
    ("female", "old"):   "ar-SA-ZariyahNeural",
}
DEFAULT_VOICE = "ar-SA-HamedNeural"


def _select_voice(
    gender: Optional[str] = None,
    age: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    """
    Map UI voice parameters to an Edge TTS Arabic neural voice name.

    `pitch` and `style` have no direct Edge TTS equivalent (Edge TTS is not
    Azure Cognitive Services / Custom Neural Voice).  They are accepted here
    for API compatibility but are no-ops; a clear log message is emitted so
    the caller is never silently surprised.
    """
    g = (gender or "male").lower().strip()
    a = (age or "adult").lower().strip()

    if pitch and pitch not in ("default", ""):
        logger.warning(
            f"  ⚠️ speak.py: `pitch='{pitch}'` has no Edge TTS equivalent "
            f"(Edge TTS is a consumer API, not Azure Custom Neural Voice). "
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


# ── Helpers ───────────────────────────────────────────────────

def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _trim_tail(arr: np.ndarray, sr: int) -> np.ndarray:
    """
    Energy-based tail trimmer: cut where signal drops below -40 dB for >100 ms.
    Applied BEFORE the speed-correction duration measurement so that trailing
    silence / breath artifacts from Edge TTS do not inflate the measured duration
    and cause a spurious speed-up request.
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


# ── Per-segment async generator ───────────────────────────────

async def _generate_segment(
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

    Returns a dict containing segment audio path, actual duration, original
    slot duration, and whether the segment was rate-capped.
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
            was_capped = (raw_rate_pct > EDGE_RATE_MAX)            # FIX 1: CAPPED DETECTION (SPEED-UP ONLY)
            rate_pct = clamped_rate_pct  # this is what actually gets used for Pass 2

            if was_capped:
                logger.warning(
                    f"  ⚠️ Seg {i} ['{text[:40]}…']: required rate={raw_rate_pct:+d}% "
                    f"exceeds Edge TTS cap (+{EDGE_RATE_MAX}%). "
                    f"Clamped to {clamped_rate_pct:+d}%. "
                    f"Downstream reconciliation (Stage 10) will need to borrow silence from elsewhere to avoid drift."
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


# ── Async orchestrator ────────────────────────────────────────

async def _speak_all(
    entries,
    segments_dir: str,
    voice: str,
    job_id: str,
) -> Tuple[List[str], int, List[dict]]:
    """
    Drive all segment generation coroutines with bounded concurrency.
    Returns (segment_paths, skipped_count, segment_details).
    """
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    segment_paths: List[Optional[str]] = [None] * len(entries)
    segment_details: List[Optional[dict]] = [None] * len(entries)
    skipped = 0

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

    # Compute slot durations for pending segments.
    async def _run(i: int) -> None:
        entry = entries[i]
        text = entry.text.strip()
        th = _text_hash(text)
        out = str(Path(segments_dir) / f"seg_{i:05d}.wav")
        slot_dur = entry.end - entry.start

        logger.info(f"  🔊 Seg {i} — synthesising via Edge TTS | slot={slot_dur:.2f}s")
        try:
            res_dict = await _generate_segment(
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

    # Replace any remaining None (shouldn't happen, but be safe)
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
) -> dict:
    """
    Stage 9 entry point — synthesise all SRT segments via Edge TTS.

    Signature preserved from OmniVoice implementation for drop-in compatibility.
    `original_audio_path` and `voice_preset` are accepted but unused (they were
    OmniVoice voice-clone inputs; Edge TTS uses a named neural voice instead).
    """
    voice = _select_voice(gender, age, pitch, style)

    logger.info(f"🗣️  Stage 9 — Generating speech via Edge TTS")
    logger.info(f"  Voice: {voice}  |  Concurrency: {_CONCURRENCY}")

    entries = read_srt(srt_path)
    if not entries:
        raise ValueError("SRT is empty — nothing to speak")
    logger.info(f"📝 SRT loaded — {len(entries)} entries")

    Path(segments_dir).mkdir(parents=True, exist_ok=True)

    # Run the async pipeline. vocal_bridge.py calls speak() inside
    # run_in_executor (a plain thread), so there is no running event loop here.
    # If one exists anyway (e.g., in test environments), asyncio.run() raises;
    # handle that gracefully.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # We are inside a running loop (e.g. pytest-asyncio) — schedule as a
        # nested coroutine via a new thread event loop.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                lambda: asyncio.run(_speak_all(entries, segments_dir, voice, job_id))
            )
            segment_paths, skipped, segment_details = future.result()
    else:
        segment_paths, skipped, segment_details = asyncio.run(
            _speak_all(entries, segments_dir, voice, job_id)
        )

    generated = len([p for p in segment_paths if p]) - skipped
    logger.info(
        f"🎉 Stage 9 complete — {generated} generated, {skipped} cached, "
        f"{len(segment_paths) - generated - skipped} failed/skipped."
    )

    return {
        "segment_paths": segment_paths,
        "count": len(segment_paths),
        "skipped": skipped,
        "instruct": voice,           # voice name replaces OmniVoice free-text instruct
        "voice_clone_prompt": None,  # Edge TTS has no latent/voice-clone-prompt concept
        "segment_details": segment_details,
    }