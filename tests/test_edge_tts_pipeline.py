"""
Task 5 — Edge TTS Integration Test

Tests three segment types:
  A) Normal segment — fits in slot → single-pass or small rate-adjust
  B) Short segment — finishes early → padded with silence
  C) Intentionally overlong — text that will require > +50% speed to fit
     in a 1.5s slot → should trigger the overrun WARNING, not be cut

Run with:
    venv/Scripts/python.exe tests/test_edge_tts_pipeline.py
"""
import asyncio
import os
import sys
import tempfile
import logging
from pathlib import Path

# ── Make project root importable ──────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from utils.srt_utils import SRTEntry, write_srt
from pipeline.speak import speak
from pipeline.assemble import assemble

# ── Test SRT content ──────────────────────────────────────────
# Total video duration = 30 seconds.
# Slot durations (next.start - this.start):
#   Seg 1: 0.0 → next at 8.0   = 8.0s  slot (NORMAL, Arabic sentence)
#   Seg 2: 8.0 → next at 16.0  = 8.0s  slot (SHORT, very brief text)
#   Seg 3: 16.0 → next at 18.0 = 2.0s  slot (OVERLONG: long Arabic sentence crammed into 2s)
#   Seg 4: 18.0 → end  30.0    = 12.0s slot (normal wrap-up)
ENTRIES = [
    SRTEntry(index=1, start=0.0,  end=7.0,  text="السلام عليكم ومرحبًا بكم في برنامجنا اليوم. سنتحدث عن أهمية التكنولوجيا في حياتنا اليومية."),
    SRTEntry(index=2, start=8.0,  end=15.0, text="شكرًا."),
    SRTEntry(index=3, start=16.0, end=17.5,
             text="هذه جملة عربية طويلة جدًا ومليئة بالكلمات التي تتجاوز المدة الزمنية المخصصة لها في هذا المقطع الصوتي المحدد وتحتاج إلى معالجة خاصة."),
    SRTEntry(index=4, start=18.0, end=29.0, text="وفي الختام، نتمنى لكم يومًا سعيدًا ومليئًا بالإنجازات."),
]

TOTAL_DURATION = 30.0  # seconds
JOB_ID = "test_edge_tts_001"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        srt_path  = str(tmp / "test.srt")
        segs_dir  = str(tmp / "segments")
        output_wav = str(tmp / "assembled.wav")

        # Write test SRT
        write_srt(ENTRIES, srt_path)
        print(f"\n{'='*60}")
        print("Stage 9 — speak()")
        print(f"{'='*60}")

        sp = speak(
            srt_path=srt_path,
            segments_dir=segs_dir,
            target_lang="ar",
            job_id=JOB_ID,
            gender="male",
            age="adult",
        )

        print(f"\nSegment paths returned: {sp['segment_paths']}")
        print(f"Voice used: {sp['instruct']}")
        print(f"voice_clone_prompt is None: {sp['voice_clone_prompt'] is None}")

        # Verify all non-empty paths exist
        for i, p in enumerate(sp["segment_paths"]):
            if p:
                assert Path(p).exists(), f"Segment {i} path does not exist: {p}"
        print("✅ All segment files exist on disk.")

        print(f"\n{'='*60}")
        print("Stage 10 — assemble()")
        print(f"{'='*60}")

        asm = assemble(
            srt_path=srt_path,
            segment_paths=sp["segment_paths"],
            output_path=output_wav,
            total_duration=TOTAL_DURATION,
            bg_volume=0.0,
        )

        print(f"\nOutput: {asm['audio_path']}")
        assert Path(asm["audio_path"]).exists(), "Assembled WAV does not exist"

        # ── Verify exact duration match ──────────────────────────
        import numpy as np
        from scipy.io.wavfile import read as wav_read
        sr_out, data = wav_read(output_wav)
        n_samples = len(data)
        expected_samples = int(TOTAL_DURATION * sr_out)

        print(f"\nSample rate: {sr_out}")
        print(f"Output samples:  {n_samples}")
        print(f"Expected samples: {expected_samples}")

        tolerance_samples = int(0.200 * sr_out)  # 200ms tolerance for minor rate variations
        assert abs(n_samples - expected_samples) <= tolerance_samples, (
            f"❌ Duration mismatch: got {n_samples} samples, expected {expected_samples} (diff {abs(n_samples - expected_samples)})"
        )
        print(f"✅ Final audio duration matches video duration ({TOTAL_DURATION}s) within tolerance.")
        print("\n🎉 All integration checks PASSED.")


if __name__ == "__main__":
    main()
