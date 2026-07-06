"""
SRT (SubRip) Subtitle Utilities

Parse, serialise, and manipulate SRT subtitle files used as the
lingua franca data format throughout the Mazinger pipeline.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SRTEntry:
    """A single subtitle cue."""
    index: int
    start: float           # seconds
    end: float             # seconds
    text: str
    # Optional metadata attached by later stages
    translated: Optional[str] = None
    audio_path: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    def timecode(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS,mmm."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def to_srt_block(self, use_translated: bool = False) -> str:
        txt = self.translated if (use_translated and self.translated) else self.text
        return (
            f"{self.index}\n"
            f"{self.timecode(self.start)} --> {self.timecode(self.end)}\n"
            f"{txt}\n"
        )


_TIMECODE_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _parse_tc(tc: str) -> float:
    m = _TIMECODE_RE.match(tc.strip())
    if not m:
        raise ValueError(f"Invalid timecode: {tc}")
    h, mn, s, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
    return h * 3600 + mn * 60 + s + ms / 1000


def parse_srt(text: str) -> List[SRTEntry]:
    """Parse an SRT string into a list of SRTEntry objects."""
    entries: List[SRTEntry] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        tc_parts = lines[1].split("-->")
        if len(tc_parts) != 2:
            continue
        start = _parse_tc(tc_parts[0])
        end = _parse_tc(tc_parts[1])
        txt = "\n".join(lines[2:]).strip()
        entries.append(SRTEntry(index=idx, start=start, end=end, text=txt))
    return entries


def read_srt(path: str) -> List[SRTEntry]:
    """Read and parse an SRT file from disk."""
    content = Path(path).read_text(encoding="utf-8-sig")
    return parse_srt(content)


def write_srt(entries: List[SRTEntry], path: str, use_translated: bool = False) -> str:
    """Write SRTEntry list to an SRT file. Returns the path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    blocks = [e.to_srt_block(use_translated) for e in entries]
    Path(path).write_text("\n".join(blocks), encoding="utf-8")
    return path


def segments_to_srt(segments: list[dict]) -> List[SRTEntry]:
    """Convert Whisper-style segment dicts to SRTEntry list."""
    entries = []
    for i, seg in enumerate(segments, 1):
        entries.append(SRTEntry(
            index=i,
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        ))
    return entries


def srt_to_text(entries: List[SRTEntry]) -> str:
    """Concatenate subtitle text into a plain string."""
    return " ".join(e.text for e in entries)
