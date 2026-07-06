#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
 DRY-RUN INTEGRATION TEST — Vocal Bridge AI Pipeline
═══════════════════════════════════════════════════════════════════

Validates the full 9-stage pipeline chain using unittest.mock:

  ✓ All modules import cleanly (no broken deps)
  ✓ Dead config fields have been removed
  ✓ CUDA/CPU device detection handles both paths
  ✓ Translation prompt is fully dynamic (not hardcoded to Arabic)
  ✓ Stage 9 (subtitle muxing) is wired into the orchestrator
  ✓ Data flows correctly from Stage 1 through Stage 9

No heavy AI models. No heavy dependencies. No actual processing.
"""

import sys
import os
import types
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime, timezone
import uuid

# ═══════════════════════════════════════════════════════════════
# PHASE 1: Mock ALL third-party packages BEFORE any project import
# ═══════════════════════════════════════════════════════════════
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

print()
print("=" * 72)
print("   VOCAL BRIDGE AI PIPELINE — DRY-RUN INTEGRATION TEST")
print("=" * 72)
print()
print("[PHASE 1] Mocking heavy third-party dependencies...")
print()

# ── python-dotenv (lightweight but may not be installed) ──
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *a, **kw: None
sys.modules["dotenv"] = _dotenv

# ── pydantic (need real BaseModel/Field behavior for schemas.py) ──
class _BaseModel:
    """Minimal pydantic.BaseModel stand-in for dry-run testing."""
    def __init__(self, **kw):
        for cls in reversed(type(self).__mro__):
            if cls in (_BaseModel, object):
                continue
            for attr in getattr(cls, "__annotations__", {}):
                if attr not in kw:
                    setattr(self, attr, getattr(cls, attr, None))
        for k, v in kw.items():
            setattr(self, k, v)

def _Field(*a, **kw):
    if "default_factory" in kw:
        return kw["default_factory"]()
    if "default" in kw:
        return kw["default"]
    return a[0] if a else None

_pydantic = types.ModuleType("pydantic")
_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
sys.modules["pydantic"] = _pydantic

# ── torch (CUDA detection target) ──
_mock_torch = MagicMock()
_mock_torch.float16 = "float16"
_mock_torch.float32 = "float32"
_mock_torch.cuda.is_available.return_value = False

# ── All heavy package mocks ──
HEAVY_MOCKS = {
    "numpy":            MagicMock(float32="float32", int16="int16", int32="int32"),
    "torch":            _mock_torch,
    "soundfile":        MagicMock(),
    "omnivoice":        MagicMock(),
    "whisper":          MagicMock(),
    "faster_whisper":   MagicMock(),
    "whisperx":         MagicMock(),
    "transformers":     MagicMock(),
    "openai":           MagicMock(),
    "scipy":            MagicMock(),
    "scipy.io":         MagicMock(),
    "scipy.io.wavfile": MagicMock(),
    "scipy.signal":     MagicMock(),
    "moviepy":          MagicMock(),
    "moviepy.editor":   MagicMock(),
    "imageio_ffmpeg":   MagicMock(),
    "requests":         MagicMock(),
    "edge_tts":         MagicMock(),
}
for name, mock in HEAVY_MOCKS.items():
    sys.modules[name] = mock

print(f"  ✅ Mocked {len(HEAVY_MOCKS) + 2} third-party packages")
print(f"     (torch, omnivoice, whisper, transformers, openai, scipy, ...")
print()


# ═══════════════════════════════════════════════════════════════
# PHASE 2: Import ALL project modules (with mocks active)
# ═══════════════════════════════════════════════════════════════
print("[PHASE 2] Importing all pipeline modules...")
print()

try:
    # ── Core config ──
    import config

    # ── Models ──
    from models.schemas import DubbingJob, JobStatus, PipelineStep

    # ── Utilities ──
    from utils.logger import pipeline_logger
    from utils.srt_utils import SRTEntry, parse_srt, write_srt, srt_to_text
    from utils.file_manager import create_job_directories, cleanup_job_temp
    from utils.audio_utils import split_text_into_chunks
    from utils.video_utils import format_duration

    # ── Pipeline stages ──
    from pipeline.cache import stage_is_cached, save_cache, load_cached
    from pipeline.download import download
    from pipeline.transcribe import transcribe
    from pipeline.translate_srt import translate_srt, _translate_openai
    from pipeline.resegment import resegment
    from pipeline.speak import speak, _detect_device, build_instruct
    from pipeline.assemble import assemble
    from pipeline.subtitle import subtitle

    # ── Orchestrator ──
    from pipeline.vocal_bridge import VocalBridgeOrchestrator, STAGE_NAMES, STAGE_STATUS_MAP

    print("  ✅ config.py             — loaded")
    print("  ✅ models/schemas.py     — DubbingJob, JobStatus, PipelineStep")
    print("  ✅ utils/logger.py       — pipeline_logger")
    print("  ✅ utils/srt_utils.py    — SRTEntry, parse_srt, write_srt")
    print("  ✅ utils/file_manager.py — create_job_directories, cleanup_job_temp")
    print("  ✅ utils/audio_utils.py  — split_text_into_chunks")
    print("  ✅ utils/video_utils.py  — format_duration")
    print("  ✅ pipeline/cache.py     — stage_is_cached, save_cache, load_cached")
    print("  ✅ pipeline/download.py  — download")
    print("  ✅ pipeline/transcribe.py— transcribe")
    print("  ✅ pipeline/translate_srt— translate_srt, _translate_openai")
    print("  ✅ pipeline/resegment.py — resegment")
    print("  ✅ pipeline/speak.py     — speak, _detect_device, build_instruct")
    print("  ✅ pipeline/assemble.py  — assemble")
    print("  ✅ pipeline/subtitle.py  — subtitle")
    print("  ✅ pipeline/vocal_bridge — VocalBridgeOrchestrator")
    print()
    print(f"  🟢 ALL 16 MODULES IMPORTED SUCCESSFULLY")
    print(f"     BASE_DIR = {config.BASE_DIR}")
    print()

except Exception as e:
    print(f"\n  🔴 FATAL IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# Helper: create a fresh DubbingJob for each test
# ═══════════════════════════════════════════════════════════════
def _make_job(job_id="drytest", source="en", target="ar"):
    """Create a fresh DubbingJob with isolated mutable fields."""
    return DubbingJob(
        job_id=job_id,
        source_language=source,
        target_language=target,
        input_path=r"d:\test\input_video.mp4",
        voice_gender="male",
        voice_age=None,
        voice_pitch=None,
        voice_style=None,
        status=JobStatus.PENDING,
        overall_progress=0.0,
        current_step="pending",
        steps=[
            PipelineStep(name="extract_audio", status="pending", progress=0.0, message=""),
            PipelineStep(name="speech_recognition", status="pending", progress=0.0, message=""),
            PipelineStep(name="translate", status="pending", progress=0.0, message=""),
            PipelineStep(name="voice_generation", status="pending", progress=0.0, message=""),
        ],
    )


# ═══════════════════════════════════════════════════════════════
# PHASE 3: Test Suite
# ═══════════════════════════════════════════════════════════════

class Test01_ModuleIntegrity(unittest.TestCase):
    """Verify all modules loaded and config is clean."""

    def test_config_has_all_pipeline_vars(self):
        """Config exposes every variable the pipeline needs."""
        required = [
            "WHISPER_MODEL", "OPENAI_API_KEY", "ELEVENLABS_API_KEY",
            "LANGUAGE_MODELS", "SUPPORTED_LANGUAGES", "EDGE_TTS_VOICES",
            "BG_VOLUME", "TEMP_DIR", "OUTPUT_DIR", "UPLOAD_DIR", "BASE_DIR",
        ]
        for attr in required:
            self.assertTrue(hasattr(config, attr), f"Missing config var: {attr}")

    def test_dead_config_is_gone(self):
        """Dead server/API config removed after cleanup."""
        dead = ["HOST", "PORT", "DEBUG", "MAX_UPLOAD_SIZE_MB",
                "MAX_CONCURRENT_JOBS", "ALLOWED_VIDEO_EXTENSIONS"]
        for attr in dead:
            self.assertFalse(hasattr(config, attr), f"Dead config still present: {attr}")

    def test_jobstatus_enum_values(self):
        """JobStatus has exactly 7 members with correct values."""
        self.assertEqual(JobStatus.PENDING.value, "pending")
        self.assertEqual(JobStatus.EXTRACTING_AUDIO.value, "extract_audio")
        self.assertEqual(JobStatus.TRANSCRIBING.value, "speech_recognition")
        self.assertEqual(JobStatus.TRANSLATING.value, "translate")
        self.assertEqual(JobStatus.GENERATING_VOICE.value, "voice_generation")
        self.assertEqual(JobStatus.COMPLETED.value, "completed")
        self.assertEqual(JobStatus.FAILED.value, "failed")
        self.assertEqual(len(list(JobStatus)), 7)

    def test_stage_names_match_status_map(self):
        """Orchestrator STAGE_NAMES align with STAGE_STATUS_MAP."""
        self.assertEqual(STAGE_NAMES, [
            "extract_audio", "speech_recognition", "translate", "voice_generation"
        ])
        for idx in range(len(STAGE_NAMES)):
            self.assertIn(idx, STAGE_STATUS_MAP)
            self.assertIsInstance(STAGE_STATUS_MAP[idx], JobStatus)

    def test_srt_parse_roundtrip(self):
        """SRT text can be parsed, queried, and serialized."""
        raw = (
            "1\n00:00:01,000 --> 00:00:04,500\nHello world\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nGoodbye world\n"
        )
        entries = parse_srt(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].text, "Hello world")
        self.assertAlmostEqual(entries[0].start, 1.0)
        self.assertAlmostEqual(entries[0].duration, 3.5)
        self.assertAlmostEqual(entries[1].start, 5.0)
        # to_srt_block
        block = entries[0].to_srt_block()
        self.assertIn("Hello world", block)
        self.assertIn("-->", block)
        # srt_to_text
        full = srt_to_text(entries)
        self.assertIn("Hello world", full)
        self.assertIn("Goodbye world", full)

    def test_13_languages_supported(self):
        """Config has at least 13 supported languages."""
        self.assertGreaterEqual(len(config.SUPPORTED_LANGUAGES), 13)
        self.assertIn("en", config.SUPPORTED_LANGUAGES)
        self.assertIn("ar", config.SUPPORTED_LANGUAGES)
        self.assertIn("fr", config.SUPPORTED_LANGUAGES)
        self.assertIn("zh", config.SUPPORTED_LANGUAGES)

    def test_no_legacy_files_in_pipeline(self):
        """No __ prefixed legacy files remain in pipeline/."""
        pipeline_dir = config.BASE_DIR / "pipeline"
        legacy = [f.name for f in pipeline_dir.glob("__*.py") if f.name != "__init__.py"]
        self.assertEqual(legacy, [], f"Legacy files still present: {legacy}")

    def test_no_original_pipeline_dir(self):
        """original_pipeline/ directory has been deleted."""
        self.assertFalse(
            (config.BASE_DIR / "original_pipeline").exists(),
            "original_pipeline/ still exists"
        )


class Test02_DeviceDetection(unittest.TestCase):
    """Verify CUDA/CPU fallback logic in speak.py."""

    def test_cpu_fallback_when_no_cuda(self):
        """Without CUDA → cpu + float32."""
        _mock_torch.cuda.is_available.return_value = False
        device, dtype = _detect_device()
        self.assertEqual(device, "cpu")
        self.assertEqual(dtype, _mock_torch.float32)

    def test_cuda_selection_when_available(self):
        """With CUDA → cuda:0 + float16."""
        _mock_torch.cuda.is_available.return_value = True
        device, dtype = _detect_device()
        self.assertEqual(device, "cuda:0")
        self.assertEqual(dtype, _mock_torch.float16)
        _mock_torch.cuda.is_available.return_value = False  # reset

    def test_build_instruct_full(self):
        """All voice attributes concatenated properly."""
        result = build_instruct("female", "young adult", "high pitch", "whisper")
        self.assertEqual(result, "female, young adult, high pitch, whisper")

    def test_build_instruct_omits_normal_style(self):
        """Style 'normal' is excluded from the instruct string."""
        result = build_instruct("male", None, None, "normal")
        self.assertEqual(result, "male")

    def test_build_instruct_default(self):
        """No args → default 'male' instruct."""
        self.assertEqual(build_instruct(), "male")


class Test03_DynamicTranslation(unittest.TestCase):
    """Translation prompt adapts to ANY language pair, not just Arabic."""

    def _capture_prompt(self, source: str, target: str) -> str:
        """Call _translate_openai with a mock OpenAI client, return the prompt."""
        entries = [SRTEntry(index=1, start=0, end=5, text="Hello world")]

        # Build mock client chain: OpenAI() → client → .chat.completions.create() → response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Translated text"
        mock_client.chat.completions.create.return_value = mock_response
        sys.modules["openai"].OpenAI.return_value = mock_client

        with patch("pipeline.translate_srt.OPENAI_API_KEY", "test-key-123"):
            _translate_openai(entries, source, target)

        call_kw = mock_client.chat.completions.create.call_args
        return call_kw[1]["messages"][0]["content"]

    def test_en_to_arabic(self):
        prompt = self._capture_prompt("en", "ar")
        self.assertIn("English", prompt)
        self.assertIn("Arabic", prompt)

    def test_en_to_french_not_arabic(self):
        prompt = self._capture_prompt("en", "fr")
        self.assertIn("English", prompt)
        self.assertIn("French", prompt)
        self.assertNotIn("Arabic", prompt)

    def test_en_to_german(self):
        prompt = self._capture_prompt("en", "de")
        self.assertIn("German", prompt)
        self.assertNotIn("Arabic", prompt)

    def test_en_to_spanish(self):
        prompt = self._capture_prompt("en", "es")
        self.assertIn("Spanish", prompt)

    def test_en_to_japanese(self):
        prompt = self._capture_prompt("en", "ja")
        self.assertIn("Japanese", prompt)

    def test_prompt_has_structural_rules(self):
        """Prompt includes separation marker and mapping rules."""
        prompt = self._capture_prompt("en", "ko")
        self.assertIn("Korean", prompt)
        self.assertIn("---", prompt)
        self.assertIn("1-to-1", prompt)
        self.assertIn("do not merge", prompt.lower())


class Test04_Stage9Wiring(unittest.TestCase):
    """Stage 9 (subtitle muxing) is active and returns MP4."""

    def test_subtitle_module_exists_and_callable(self):
        """pipeline.subtitle has a callable subtitle() function."""
        from pipeline.subtitle import subtitle as sub_fn
        self.assertTrue(callable(sub_fn))

    def test_orchestrator_calls_subtitle_and_returns_mp4(self):
        """Orchestrator invokes Stage 9 and final output is .mp4."""
        job = _make_job(job_id="st9test")
        jd = str(config.TEMP_DIR / "st9test")

        with patch("pipeline.download.download") as m_dl, \
             patch("pipeline.transcribe.transcribe") as m_tr, \
             patch("pipeline.translate_srt.translate_srt") as m_ts, \
             patch("pipeline.resegment.resegment") as m_rs, \
             patch("pipeline.speak.speak") as m_sp, \
             patch("pipeline.assemble.assemble") as m_asm, \
             patch("pipeline.subtitle.subtitle") as m_sub:

            m_dl.return_value  = {"video_path": f"{jd}\\v.mp4", "audio_path": f"{jd}\\a.wav", "duration": 30.0}
            m_tr.return_value  = {"srt_path": f"{jd}\\t.srt", "language": "en", "full_text": "Hi", "entry_count": 1}
            m_ts.return_value  = {"srt_path": f"{jd}\\tl.srt", "full_translated_text": "مرحبا", "entry_count": 1}
            m_rs.return_value  = {"srt_path": f"{jd}\\rs.srt", "entry_count": 1}
            m_sp.return_value  = {"segment_paths": [f"{jd}\\s.wav"], "count": 1, "skipped": 0}
            m_asm.return_value = {"audio_path": f"{jd}\\asm.wav", "duration": 30.0}
            m_sub.return_value = {"output_path": str(config.OUTPUT_DIR / "vocal_bridge_st9test.mp4"), "size_mb": 5.0}

            result = asyncio.run(VocalBridgeOrchestrator(job).run())

            # ★ CRITICAL: subtitle() was actually called
            m_sub.assert_called_once()
            sub_args = m_sub.call_args[0]
            # subtitle(video_path, audio_path, srt_path, output_path, burn_subs)
            self.assertIn("v.mp4", sub_args[0], "subtitle should receive original video")
            self.assertIn("asm.wav", sub_args[1], "subtitle should receive assembled audio")

            # ★ CRITICAL: output is .mp4, NOT .wav
            self.assertTrue(result.output_path.endswith(".mp4"),
                            f"Expected .mp4 output, got: {result.output_path}")
            self.assertEqual(result.status, JobStatus.COMPLETED)


class Test05_FullPipelineFlow(unittest.TestCase):
    """End-to-end: verify data passes correctly Stage 1 → 9."""

    def test_complete_data_chain(self):
        """Every stage receives correct input from the previous stage."""
        job = _make_job(job_id="e2e001", source="en", target="fr")
        jd = str(config.TEMP_DIR / "e2e001")

        with patch("pipeline.download.download") as m_dl, \
             patch("pipeline.transcribe.transcribe") as m_tr, \
             patch("pipeline.translate_srt.translate_srt") as m_ts, \
             patch("pipeline.resegment.resegment") as m_rs, \
             patch("pipeline.speak.speak") as m_sp, \
             patch("pipeline.assemble.assemble") as m_asm, \
             patch("pipeline.subtitle.subtitle") as m_sub:

            # Set up mock return values for each stage
            m_dl.return_value  = {"video_path": f"{jd}\\video.mp4", "audio_path": f"{jd}\\audio.wav", "duration": 60.0}
            m_tr.return_value  = {"srt_path": f"{jd}\\transcript.srt", "language": "en", "full_text": "Hello test", "entry_count": 2}
            m_ts.return_value  = {"srt_path": f"{jd}\\translated.srt", "full_translated_text": "Bonjour test", "entry_count": 2}
            m_rs.return_value  = {"srt_path": f"{jd}\\resegmented.srt", "entry_count": 2}
            m_sp.return_value  = {"segment_paths": [f"{jd}\\seg0.wav", f"{jd}\\seg1.wav"], "count": 2, "skipped": 0}
            m_asm.return_value = {"audio_path": f"{jd}\\assembled.wav", "duration": 60.0}
            m_sub.return_value = {"output_path": str(config.OUTPUT_DIR / "vocal_bridge_e2e001.mp4"), "size_mb": 10.0}

            result = asyncio.run(VocalBridgeOrchestrator(job).run())

            # ── ALL 7 stages called exactly once ──
            for label, mock in [("download", m_dl), ("transcribe", m_tr),
                                ("translate", m_ts), ("resegment", m_rs),
                                ("speak", m_sp), ("assemble", m_asm),
                                ("subtitle", m_sub)]:
                mock.assert_called_once()

            # ── HANDOFF 1→2: download.audio_path → transcribe input ──
            self.assertEqual(m_tr.call_args[0][0], f"{jd}\\audio.wav",
                             "transcribe should receive audio_path from download")

            # ── HANDOFF 2→3: transcribe.srt_path → translate input ──
            self.assertEqual(m_ts.call_args[0][0], f"{jd}\\transcript.srt",
                             "translate should receive srt_path from transcribe")

            # ── Language params forwarded to translate ──
            self.assertEqual(m_ts.call_args[0][2], "en", "source_lang should be 'en'")
            self.assertEqual(m_ts.call_args[0][3], "fr", "target_lang should be 'fr'")

            # ── HANDOFF 3→4: translate.srt_path → resegment input ──
            self.assertEqual(m_rs.call_args[0][0], f"{jd}\\translated.srt",
                             "resegment should receive srt from translate")

            # ── HANDOFF 4→5: resegment.srt_path → speak input ──
            self.assertEqual(m_sp.call_args[0][0], f"{jd}\\resegmented.srt",
                             "speak should receive srt from resegment")
            self.assertEqual(m_sp.call_args[0][2], "fr",
                             "speak should receive target_lang 'fr'")

            # ── HANDOFF 5→6: speak.segment_paths → assemble input ──
            self.assertEqual(m_asm.call_args[0][1], [f"{jd}\\seg0.wav", f"{jd}\\seg1.wav"],
                             "assemble should receive segment_paths from speak")

            # ── HANDOFF 6→7: assemble.audio_path → subtitle input ──
            self.assertEqual(m_sub.call_args[0][1], f"{jd}\\assembled.wav",
                             "subtitle should receive assembled audio")

            # ── Subtitle receives original video (from Stage 1) ──
            self.assertEqual(m_sub.call_args[0][0], f"{jd}\\video.mp4",
                             "subtitle should receive original video from download")

            # ── Final output state ──
            self.assertEqual(result.status, JobStatus.COMPLETED)
            self.assertTrue(result.output_path.endswith(".mp4"))
            self.assertEqual(result.overall_progress, 100)
            self.assertEqual(result.translated_text, "Bonjour test")
            self.assertIsNotNone(result.completed_at)

    def test_pipeline_sets_failure_on_error(self):
        """If any stage fails, job status is FAILED."""
        job = _make_job(job_id="e2efail")

        with patch("pipeline.download.download") as m_dl:
            m_dl.side_effect = RuntimeError("Simulated download failure")

            with self.assertRaises(RuntimeError):
                asyncio.run(VocalBridgeOrchestrator(job).run())

            self.assertEqual(job.status, JobStatus.FAILED)
            self.assertIn("Simulated download failure", job.error_message)


# ═══════════════════════════════════════════════════════════════
# MAIN — Run with verbose output
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 72)
    print("[PHASE 3] Running test suite...")
    print("=" * 72)
    print()
    unittest.main(verbosity=2, exit=True)
