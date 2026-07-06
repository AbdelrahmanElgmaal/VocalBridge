"""
Stage 10 — Assemble

Place each audio segment on the original timeline with:
 • Loudness matching (normalize to -20 dB)
 • Global silence-budget reconciliation to handle overrunning segments (reconciled via natural gaps and unused slack)
 • Background audio mixing (original audio at configurable volume)

Produces a single WAV file matching the original video duration (or slightly longer if budget is exhausted and unavoidable drift occurs).
"""
import os
import shutil
from pathlib import Path
from typing import List
import numpy as np
import librosa
import soundfile as sf
from pipeline.speak import EDGE_RATE_MAX
from config import BG_VOLUME
from utils.logger import pipeline_logger as logger
from utils.srt_utils import read_srt


# ── Locate FFmpeg binary ───────────────────────────────────────
# Mirrors speak.py: prefer system ffmpeg, fall back to imageio_ffmpeg bundle.
def _get_ffmpeg_exe() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = str(Path(ffmpeg_exe).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        return ffmpeg_exe
    except Exception as exc:
        raise RuntimeError(
            "ffmpeg not found and imageio_ffmpeg is unavailable."
        ) from exc

_FFMPEG_EXE = _get_ffmpeg_exe()


def _load_audio_clip(path: str, sr: int = 44100) -> np.ndarray:
    """Load an audio file into a float32 numpy array using ffmpeg."""
    import subprocess
    
    # ── Command to decode to float32 PCM on stdout ──
    cmd = [
        _FFMPEG_EXE, "-y",
        "-i", path,
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ar", str(sr),
        "-ac", "1",
        "pipe:1"
    ]
    
    try:
        # Hide console window on Windows
        startupinfo = None
        if hasattr(subprocess, 'STARTUPINFO'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        out, err = process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {err.decode('utf-8', errors='ignore')}")
            
        audio = np.frombuffer(out, dtype=np.float32).copy()
        if audio.size == 0:
            return np.zeros(0, dtype=np.float32)
            
        return audio
        
    except Exception as e:
        logger.warning(f"  ⚠️ FFmpeg load failed for {path}: {e}")
        # Final fallback to a dummy array to avoid crashing, but this is bad
        return np.zeros(0, dtype=np.float32)


def _normalize(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """Normalize audio to target dB level."""
    if audio.size == 0:
        return audio
    rms = np.sqrt(np.mean(audio ** 2))
    if rms == 0:
        return audio
    target_rms = 10 ** (target_db / 20.0)
    return np.clip(audio * (target_rms / rms), -1.0, 1.0)


def _apply_fades(audio: np.ndarray, sr: int, fade_in_sec: float = 0.015, fade_out_sec: float = 0.050) -> np.ndarray:
    """Apply linear fade-in and fade-out to prevent clicks."""
    if len(audio) == 0:
        return audio
        
    out = audio.copy()
    in_samples = int(fade_in_sec * sr)
    out_samples = int(fade_out_sec * sr)
    
    if in_samples > 0 and len(out) > in_samples:
        ramp = np.linspace(0.0, 1.0, in_samples, dtype=np.float32)
        out[:in_samples] *= ramp
        
    if out_samples > 0 and len(out) > out_samples:
        ramp = np.linspace(1.0, 0.0, out_samples, dtype=np.float32)
        out[-out_samples:] *= ramp
        
    return out


def assemble(
    srt_path: str,
    segment_paths: List[str],
    output_path: str,
    total_duration: float,
    original_audio_path: str = None,
    bg_volume: float = BG_VOLUME,
    sample_rate: int = 44100,
    instruct: str = "male",         # Unused: kept for backwards-compat with vocal_bridge.py
    voice_clone_prompt: any = None, # Unused: Edge TTS has no latent/voice-clone concept
    segment_details: List[dict] = None,
) -> dict:
    """
    Stage 10 entry point.
    Reconciles overrunning segment durations using silence budget from natural gaps
    and unused segment slack. Guarantees no cuts, no overlaps, and exact video duration
    unless the silence budget is fully exhausted.
    """
    logger.info("🔧 Assembling timeline with global silence-budget reconciliation…")

    entries = read_srt(srt_path)
    if len(entries) != len(segment_paths):
        logger.warning(
            f"Entry/segment count mismatch: {len(entries)} vs {len(segment_paths)}"
        )

    # 1. Reconstruct segment_details if None (backward compatibility fallback)
    if segment_details is None:
        logger.info("  ℹ️ Reconstructing segment_details (legacy fallback)...")
        segment_details = []
        for i, (entry, seg_path) in enumerate(zip(entries, segment_paths)):
            slot_dur = entry.end - entry.start
            if not seg_path or not Path(seg_path).exists():
                segment_details.append({
                    "path": "",
                    "actual_duration_sec": 0.0,
                    "slot_duration_sec": slot_dur,
                    "was_capped": False,
                })
            else:
                try:
                    actual_dur = sf.info(seg_path).duration
                except Exception:
                    actual_dur = 0.0
                if slot_dur > 0:
                    speed_ratio = actual_dur / slot_dur
                    raw_rate_pct = round((speed_ratio - 1) * 100)
                    was_capped = raw_rate_pct > EDGE_RATE_MAX
                else:
                    was_capped = False
                logger.info(
                    f"    Seg {i}: actual_dur={actual_dur:.3f}s, slot_dur={slot_dur:.3f}s, "
                    f"was_capped={was_capped} (approximate — no cache metadata available)"
                )
                segment_details.append({
                    "path": seg_path,
                    "actual_duration_sec": actual_dur,
                    "slot_duration_sec": slot_dur,
                    "was_capped": was_capped,
                })

    # 2. Compute foundational arrays (with zero-clamping/overlap warnings)
    original_gaps = []
    if entries:
        for i in range(len(entries) - 1):
            gap = entries[i+1].start - entries[i].end
            if gap < 0:
                logger.warning(
                    f"  ⚠️ SRT entries {i} and {i+1} overlap by {-gap:.3f}s "
                    f"(entry {i} ends at {entries[i].end:.3f}s, entry {i+1} starts "
                    f"at {entries[i+1].start:.3f}s). Clamping gap to 0."
                )
            original_gaps.append(max(0.0, gap))
        original_gaps.append(max(0.0, total_duration - entries[-1].end))
    else:
        original_gaps.append(max(0.0, total_duration))

    segment_slack = [
        max(0.0, seg["slot_duration_sec"] - seg["actual_duration_sec"])
        for seg in segment_details
    ]

    # 3. Two separate borrowing pools
    slack_remaining = list(segment_slack)   # pool 1: starts full per segment
    gap_remaining   = list(original_gaps)   # pool 2: starts full, natural pauses

    unavoidable_drift_sec = 0.0
    capped_segments_report = []

    for i, seg in enumerate(segment_details):
        if not seg["was_capped"]:
            continue
        deficit = seg["actual_duration_sec"] - seg["slot_duration_sec"]
        if deficit <= 0:
            continue

        remaining_deficit = deficit
        capped_segments_report.append({
            "index": i,
            "slot_dur": seg["slot_duration_sec"],
            "actual_dur": seg["actual_duration_sec"],
            "overrun_sec": deficit,
        })

        # Borrow ONLY from positions j >= i (chronological, never borrow from the past)
        # Prefer slack first, then fall back to shrinking an actual natural pause
        for j in range(i, len(entries)):
            if remaining_deficit <= 0:
                break

            slack_avail = slack_remaining[j] if j < len(slack_remaining) else 0.0
            take_slack = min(remaining_deficit, slack_avail)
            slack_remaining[j] -= take_slack
            remaining_deficit -= take_slack
            assert slack_remaining[j] >= 0

            if remaining_deficit > 0 and j < len(gap_remaining):
                gap_avail = gap_remaining[j]
                take_gap = min(remaining_deficit, gap_avail)
                gap_remaining[j] -= take_gap
                remaining_deficit -= take_gap
                assert gap_remaining[j] >= 0

        if remaining_deficit > 0:
            # [MARK: NOT ENOUGH BUDGET FALLBACK TRIGGERS HERE]
            unavoidable_drift_sec += remaining_deficit
            logger.warning(
                f"  ⚠️ Insufficient silence budget after segment {i}: "
                f"{remaining_deficit:.3f}s of its {deficit:.3f}s overrun could "
                f"not be absorbed by any later slack or gap. Priorities 2 and 3 "
                f"(no cuts, no overlap) are preserved; Priority 1 (exact length) "
                f"is being relaxed by this amount for this run."
            )

    # 4. Compute reconciled gaps actually used for timeline cursor advancement
    reconciled_gaps = [
        gap_remaining[i] + slack_remaining[i]
        for i in range(len(original_gaps))
    ]

    # 5. Placement loop using a pure cursor
    cursor = entries[0].start if entries else 0.0
    placements = []
    for i, seg in enumerate(segment_details):
        desired_start = cursor
        placements.append((desired_start, seg["path"]))
        cursor = desired_start + seg["actual_duration_sec"] + reconciled_gaps[i]

    # 6. Set timeline bounds based on cursor
    final_audio_duration_sec = cursor
    total_drift_sec = final_audio_duration_sec - total_duration
    total_samples = int(final_audio_duration_sec * sample_rate)

    timeline = np.zeros(total_samples, dtype=np.float32)
    placed = 0

    # 7. Render segments onto the timeline
    for i, (desired_start, seg_path) in enumerate(placements):
        if not seg_path or not Path(seg_path).exists():
            continue

        try:
            seg_audio = _load_audio_clip(seg_path, sample_rate)
        except Exception as e:
            logger.warning(f"  ⚠️ Could not load segment {i}: {e}")
            continue

        seg_audio = _normalize(seg_audio, target_db=-20.0)
        seg_audio = _apply_fades(seg_audio, sample_rate, fade_in_sec=0.015, fade_out_sec=0.050)

        start_sample = int(desired_start * sample_rate)
        end_sample = start_sample + len(seg_audio)

        if start_sample >= total_samples:
            continue
        if end_sample > total_samples:
            seg_audio = seg_audio[:total_samples - start_sample]
            end_sample = total_samples

        timeline[start_sample:end_sample] += seg_audio
        placed += 1

    # 8. Mix background audio
    if original_audio_path and Path(original_audio_path).exists() and bg_volume > 0:
        try:
            logger.info(f"  🎵 Mixing background at {bg_volume * 100:.0f}% volume")
            bg = _load_audio_clip(original_audio_path, sample_rate)
            bg = _normalize(bg, target_db=-20.0) * bg_volume
            # Match length to final timeline length (intentional to cover any unavoidable voice drift)
            if len(bg) > total_samples:
                bg = bg[:total_samples]
            elif len(bg) < total_samples:
                padded = np.zeros(total_samples, dtype=np.float32)
                padded[:len(bg)] = bg
                bg = padded
            timeline += bg
            logger.info("  ✅ Background mixed successfully.")
        except Exception as e:
            logger.warning(f"  ⚠️ Background mixing failed: {e}")

    timeline = np.clip(timeline, -1.0, 1.0)

    if placed == 0:
        logger.warning("🚨 No voice segments were successfully placed!")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    from scipy.io.wavfile import write as wav_write
    wav_write(output_path, sample_rate, (timeline * 32767).astype(np.int16))

    logger.info(
        f"✅ Stage 10 complete — {placed}/{len(entries)} segments placed, "
        f"{final_audio_duration_sec:.2f}s timeline"
    )

    return {
        "audio_path": output_path,
        "duration": final_audio_duration_sec,
        "final_audio_duration_sec": final_audio_duration_sec,
        "original_video_duration_sec": total_duration,
        "total_drift_sec": total_drift_sec,
        "unavoidable_drift_sec": unavoidable_drift_sec,
        "silence_budget_used_sec": sum(
            (original_gaps[i] - gap_remaining[i]) + 
            (segment_slack[i] - slack_remaining[i])
            for i in range(len(original_gaps))
        ),
        "silence_budget_total_sec": sum(original_gaps) + sum(segment_slack),
        "capped_segments": capped_segments_report,
    }
