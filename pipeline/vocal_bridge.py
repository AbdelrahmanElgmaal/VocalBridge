"""
Vocal Bridge — 9-Stage Pipeline Orchestrator

Chains all stages into a single pipeline with automatic caching and
resume.  Every stage can also run independently.

Stages:
 1. Download    – fetch / ingest video, extract audio
 2. Transcribe  – speech → SRT subtitles
 3. Thumbnails  – extract key frames
 4. Describe    – structured video summary
 5. Translate   – SRT translation with word budgets
 6. Re-segment  – merge fragments, split long cues
 7. Speak       – per-subtitle TTS with voice cloning
 8. Assemble    – build timeline with tempo/loudness/mixing
 9. Subtitle    – burn subs + mux audio → final video
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional
import shutil

from models.schemas import DubbingJob, JobStatus
from pipeline.cache import stage_is_cached, load_cached, save_cache
from utils.file_manager import create_job_directories, cleanup_job_temp
from utils.logger import pipeline_logger as logger
from config import TEMP_DIR, OUTPUT_DIR

from dataclasses import dataclass

@dataclass
class PipelineConfig:
    stage_names: list[str]
    status_map: dict[int, JobStatus]
    progress_ranges: dict[int, tuple[int, int]]

VIDEO_CONFIG = PipelineConfig(
    stage_names=[
        "extract_audio",
        "speech_recognition",
        "translate",
        "voice_generation",
        "merge_video",
    ],
    status_map={
        0: JobStatus.EXTRACTING_AUDIO,
        1: JobStatus.TRANSCRIBING,
        2: JobStatus.TRANSLATING,
        3: JobStatus.GENERATING_VOICE,
        4: JobStatus.MERGING_VIDEO,
    },
    progress_ranges={
        0: (10, 25),
        1: (30, 45),
        2: (50, 70),
        3: (75, 90),
        4: (95, 99),
    }
)

AUDIO_CONFIG = PipelineConfig(
    stage_names=[
        "download_audio",
        "speech_recognition",
        "translate",
        "voice_generation",
    ],
    status_map={
        0: JobStatus.DOWNLOADING_AUDIO,
        1: JobStatus.TRANSCRIBING,
        2: JobStatus.TRANSLATING,
        3: JobStatus.GENERATING_VOICE,
    },
    progress_ranges={
        0: (10, 30),
        1: (30, 50),
        2: (50, 75),
        3: (75, 99),
    }
)


class VocalBridgeOrchestrator:
    """
    Orchestrates the simplified 4-stage Vocal Bridge pipeline.
    """

    def __init__(self, job: DubbingJob, progress_callback: Optional[Callable] = None):
        self.job = job
        self.progress_callback = progress_callback
        self.paths = create_job_directories(job.job_id)
        
        # Determine media type once
        self.is_audio = job.input_type.lower() == "audio"
        self.config = AUDIO_CONFIG if self.is_audio else VIDEO_CONFIG
        self._num_stages = len(self.config.stage_names)
        
        # Initialize steps dynamically based on config if empty
        if not self.job.steps:
            from models.schemas import PipelineStep
            stage_names = list(self.config.stage_names)
            if not self.is_audio and getattr(self.job, 'enable_lipsync', False):
                stage_names.append("lip_sync")
            self.job.steps = [PipelineStep(name=name) for name in stage_names]
            self._num_stages = len(self.job.steps)

    # ── Progress Helpers ─────────────────────────────────────
    async def _update_progress(self, step_idx: int, progress: float, message: str):
        step = self.job.steps[step_idx]
        step.progress = progress
        step.message = message

        if not self.is_audio and getattr(self.job, 'enable_lipsync', False):
            if step_idx == 4:
                start, end = 90, 95
            elif step_idx == 5:
                start, end = 95, 99
            else:
                start, end = self.config.progress_ranges.get(step_idx, (95, 99))
        else:
            start, end = self.config.progress_ranges[step_idx]

        self.job.overall_progress = min(start + (progress / 100) * (end - start), 100)
        self.job.current_step = step.name

        if self.progress_callback:
            await self.progress_callback(self.job)

    async def _run_stage(self, idx: int, name: str, func, *args, **kwargs):
        """Run a single stage with progress tracking."""
        step = self.job.steps[idx]

        step.status = "running"
        step.started_at = datetime.utcnow()
        if not self.is_audio and getattr(self.job, 'enable_lipsync', False) and idx == 5:
            self.job.status = JobStatus.LIP_SYNCING
        else:
            self.job.status = self.config.status_map.get(idx, JobStatus.PENDING)
        await self._update_progress(idx, 0, f"Starting {name}…")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))

            step.status = "completed"
            step.completed_at = datetime.utcnow()
            await self._update_progress(idx, 100, f"{name} ✅")

            return result

        except Exception as e:
            step.status = "failed"
            step.message = str(e)
            raise

    # ── Full Pipeline ────────────────────────────────────────
    async def run(self) -> DubbingJob:
        """Execute the pipeline based on media type."""
        job = self.job
        jid = job.job_id
        media_type = "Audio" if self.is_audio else "Video"
        logger.info(f"🚀 {media_type} Job {jid} Started")
        logger.info(f"  {job.source_language} → {job.target_language}")
        job.started_at = datetime.utcnow()

        from pathlib import Path
        from config import TEMP_DIR, OUTPUT_DIR

        job_dir = str(TEMP_DIR / jid)

        try:
            # ── 1. Download / Extract ──
            from pipeline.download import download
            stage_name = "download_audio" if self.is_audio else "extract_audio"
            dl = await self._run_stage(
                0, stage_name, download,
                job.input_path, job_dir, is_audio=self.is_audio
            )
            video_path = dl.get("video_path")
            audio_path = dl["audio_path"]
            duration = dl["duration"]

            # ── 2. Speech Recognition ──
            from pipeline.transcribe import transcribe
            srt_out = str(Path(job_dir) / "transcript.srt")
            tr = await self._run_stage(
                1, "speech_recognition", transcribe,
                audio_path, srt_out, job.source_language,
            )
            
            srt_path = tr["srt_path"]
            detected_lang = tr["language"]
            job.transcribed_text = tr.get("full_text")
            job.transcript = job.transcribed_text
            if job.source_language == "auto":
                job.source_language = detected_lang
            if self.progress_callback:
                await self.progress_callback(job)

            # ── 3. Translate (and Diacritize) ──
            def translate_and_diacritize():
                from pipeline.translate_srt import translate_srt
                translated_srt = str(Path(job_dir) / "translated.srt")
                res = translate_srt(
                    srt_path, translated_srt,
                    job.source_language, job.target_language
                )
                current_srt = translated_srt

                # Remerge the translated output
                from pipeline.remerge import remerge_srt
                remerged_translated_srt = str(Path(job_dir) / "remerged_translated.srt")
                remerge_srt(current_srt, remerged_translated_srt, video_duration=duration)
                
                res["srt_path"] = remerged_translated_srt
                
                return res

            tl = await self._run_stage(2, "translate", translate_and_diacritize)
            job.translated_text = tl.get("full_translated_text")
            if self.progress_callback:
                await self.progress_callback(job)

            # ── 4. Voice Generation (Internal multi-step) ──
            def generate_voice_full():
                # Re-segment
                from pipeline.resegment import resegment
                reseg_srt = str(Path(job_dir) / "resegmented.srt")
                rs = resegment(tl["srt_path"], reseg_srt)

                # Speak
                from pipeline.speak import speak
                segs_dir = str(Path(job_dir) / "segments")
                # Pass voice configuration to speak
                logger.info(f"🗣️  Calling speak() — srt={rs['srt_path']}, segs_dir={segs_dir}, lang={job.target_language}")
                sp = speak(
                    rs["srt_path"], segs_dir, job.target_language, jid,
                    audio_path,
                    gender=job.voice_gender,
                    age=job.voice_age,
                    pitch=job.voice_pitch,
                    style=job.voice_style,
                    clone_speaker=job.clone_speaker,
                    whisper_srt_path=srt_path
                )
                
                
                # Assemble
                from pipeline.assemble import assemble
                assembled_wav = str(Path(job_dir) / "assembled.wav")
                asm = assemble(
                    rs["srt_path"], sp["segment_paths"],
                    assembled_wav, duration,
                    original_audio_path=audio_path, bg_volume=0.00,
                    instruct=sp.get("instruct", "male"),
                    voice_clone_prompt=sp.get("voice_clone_prompt"),
                    segment_details=sp.get("segment_details")
                )
                
                # Return assembled Arabic audio for the merge stage.
                return {"srt_path": rs["srt_path"], "audio_path": asm["audio_path"]}

            # ── Done ──
            ###################################################################
            voice_result = await self._run_stage(3, "voice_generation", generate_voice_full)

            if self.is_audio:
                # Audio workflow ends here. Move the assembled audio to OUTPUT_DIR
                output_audio_path = str(OUTPUT_DIR / f"vocal_bridge_{jid}.wav")
                shutil.move(voice_result["audio_path"], output_audio_path)
                job.output_path = output_audio_path
            else:
                # Video workflow continues to merge step
                def merge_video_full():
                    from pipeline.subtitle import subtitle
                    output_video_path = str(OUTPUT_DIR / f"vocal_bridge_{jid}.mp4")
                    return subtitle(
                        video_path, voice_result["audio_path"],
                        voice_result["srt_path"], output_video_path,
                        burn_subs=job.burn_subtitles,
                    )

                sub_result = await self._run_stage(4, "merge_video", merge_video_full)

                if not sub_result.get("output_path"):
                    raise ValueError("subtitle() produced no video output")

                job.output_path = sub_result["output_path"]

                # ── 5. Lip Sync (Wav2Lip) — optional stage ──
                if getattr(job, 'enable_lipsync', False):
                    from pipeline.lipsync import lipsync, check_wav2lip_ready
                    if not check_wav2lip_ready():
                        logger.warning("Wav2Lip not properly configured, skipping lip-sync")
                        job.steps[5].status = "failed"
                        job.steps[5].message = "Wav2Lip not configured — skipped"
                        if self.progress_callback:
                            await self.progress_callback(job)
                    else:
                        lipsync_output = str(OUTPUT_DIR / f"vocal_bridge_lipsync_{jid}.mp4")

                        def run_lipsync():
                            return lipsync(
                                video_path=job.output_path,
                                audio_path=voice_result["audio_path"],
                                output_path=lipsync_output,
                                pads=job.lipsync_pads,
                                enhance_face=job.lipsync_enhance_face,
                                nosmooth=job.lipsync_nosmooth,
                                face_det_batch_size=job.lipsync_face_det_batch,
                                wav2lip_batch_size=job.lipsync_wav2lip_batch,
                                mel_step_size=job.lipsync_mel_step_size,
                            )

                        ls_result = await self._run_stage(5, "lip_sync", run_lipsync)
                        job.output_path = ls_result["output_path"]
            ###################################################################

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.overall_progress = 100

            elapsed = (job.completed_at - job.started_at).total_seconds()
            logger.info(f"🎉 {media_type} Job {jid} Completed in {elapsed:.1f}s")

            if self.progress_callback:
                await self.progress_callback(job)

            return job

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            logger.error(f"💥 Pipeline failed — job {jid}: {e}")

            if self.progress_callback:
                await self.progress_callback(job)
            raise

        finally:
            try:
                import config
                if config.CLEANUP_TEMP_FILES:
                    cleanup_job_temp(jid)
                    logger.info(f"🧹 Temp files cleaned up for job {jid}")
                else:
                    logger.info(f"🧹 Temp files cleanup skipped for job {jid} (configured to keep)")
            except Exception as ce:
                logger.warning(f"Cleanup failed: {ce}")
