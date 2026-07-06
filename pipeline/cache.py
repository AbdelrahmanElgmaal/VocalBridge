"""
Pipeline Stage Cache

Provides transparent caching for each stage so that interrupted runs
can resume automatically.  Each stage result is stored as a JSON
manifest alongside any binary artefacts in:

    <TEMP_DIR>/<job_id>/cache/<stage_name>/

A SHA-256 fingerprint (built from stage inputs) decides whether the
cached result is still valid.  Individual TTS segments are cached
independently so that partially-completed Speak stages don't restart.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from config import TEMP_DIR
from utils.logger import pipeline_logger as logger


def _cache_dir(job_id: str, stage: str) -> Path:
    p = TEMP_DIR / job_id / "cache" / stage
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fingerprint(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
    return h.hexdigest()[:16]


def stage_is_cached(job_id: str, stage: str, *input_keys: str) -> bool:
    """Return True if <stage> was already completed with the same inputs."""
    d = _cache_dir(job_id, stage)
    manifest = d / "manifest.json"
    if not manifest.exists():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data.get("fingerprint") == _fingerprint(*input_keys)
    except Exception:
        return False


def load_cached(job_id: str, stage: str) -> Optional[Any]:
    """Load the cached result payload for a stage."""
    d = _cache_dir(job_id, stage)
    manifest = d / "manifest.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data.get("result")
    except Exception:
        return None


def save_cache(job_id: str, stage: str, result: Any, *input_keys: str) -> None:
    """Persist the result payload for a stage."""
    d = _cache_dir(job_id, stage)
    manifest = d / "manifest.json"
    data = {
        "fingerprint": _fingerprint(*input_keys),
        "result": result,
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"💾 Cached stage '{stage}' for job {job_id}")


# ── Segment-level cache (for TTS) ────────────────────────────
def segment_is_cached(job_id: str, seg_index: int, text_hash: str) -> bool:
    d = _cache_dir(job_id, "speak") / "segments"
    d.mkdir(exist_ok=True)
    marker = d / f"seg_{seg_index:05d}_{text_hash}.done"
    return marker.exists()


def mark_segment_done(
    job_id: str,
    seg_index: int,
    text_hash: str,
    audio_path: str,
    was_capped: bool = False,
    slot_duration_sec: float = 0.0,
    actual_duration_sec: float = 0.0,
) -> None:
    d = _cache_dir(job_id, "speak") / "segments"
    d.mkdir(exist_ok=True)
    marker = d / f"seg_{seg_index:05d}_{text_hash}.done"
    data = {
        "audio_path": audio_path,
        "was_capped": was_capped,
        "slot_duration_sec": slot_duration_sec,
        "actual_duration_sec": actual_duration_sec,
    }
    marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_segment_audio(job_id: str, seg_index: int, text_hash: str) -> Optional[str]:
    d = _cache_dir(job_id, "speak") / "segments"
    marker = d / f"seg_{seg_index:05d}_{text_hash}.done"
    if marker.exists():
        content = marker.read_text(encoding="utf-8").strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "audio_path" in data:
                return data["audio_path"]
        except json.JSONDecodeError:
            pass
        return content
    return None


def get_segment_metadata(job_id: str, seg_index: int, text_hash: str) -> Optional[dict]:
    d = _cache_dir(job_id, "speak") / "segments"
    marker = d / f"seg_{seg_index:05d}_{text_hash}.done"
    if marker.exists():
        content = marker.read_text(encoding="utf-8").strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None
