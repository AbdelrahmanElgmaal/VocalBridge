"""
Stage 6 — Re-segment

This file has been deprecated and now acts as a pure pass-through.
All segmentation logic is now handled proactively in pipeline/remerge.py.
"""
from utils.logger import pipeline_logger as logger
from utils.srt_utils import read_srt, write_srt

def resegment(
    srt_path: str,
    output_path: str,
    max_chars: int = 84,  # Kept for signature compatibility
    max_gap: float = 0.3, # Kept for signature compatibility
) -> dict:
    """
    Stage 6 entry point.
    """
    logger.info("✂️  Re-segmenting subtitles (Pass-through)…")

    entries = read_srt(srt_path)
    if not entries:
        raise ValueError("SRT file is empty")

    write_srt(entries, output_path, use_translated=True)
    logger.info(f"✅ Stage 6 complete — {len(entries)} cues (0 merges, 0 splits)")

    return {
        "srt_path": output_path,
        "entry_count": len(entries),
        "merges": 0,
        "splits": 0,
    }
