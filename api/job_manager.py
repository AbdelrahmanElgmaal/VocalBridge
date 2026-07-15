"""
Job Manager — SQLite-Backed Persistence + Webhook Notifications
================================================================

Manages the full lifecycle of dubbing jobs with persistent state:

  1. Create   — register a job in SQLite + start background task.
  2. Track    — expose state via SQLite reads (survives restarts).
  3. Notify   — push webhook POSTs to .NET on every status change.
  4. Cancel   — cancel the asyncio task + update SQLite + cleanup.
  5. Download — build a local download URL for completed jobs.

Architecture:
  • SQLite (`jobs.db`)   → persistent source of truth for job state.
  • `_active_jobs` dict  → in-memory DubbingJob objects for running
                           orchestrators (only while task is alive).
  • `_tasks` dict        → asyncio.Task handles for cancellation.

Status normalisation for the strict .NET contract:
  Internal pipeline statuses (extract_audio, speech_recognition, ...)
  are all mapped to "processing" in SQLite/API responses.  Only
  "completed", "failed", and "cancelled" pass through unchanged.
"""

import asyncio
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, List

import httpx

from models.schemas import DubbingJob, JobStatus
from pipeline.vocal_bridge import VocalBridgeOrchestrator
from utils.file_manager import cleanup_job_temp
from utils.logger import pipeline_logger as logger
import config


# ── Constants ─────────────────────────────────────────────────────
DB_PATH = config.BASE_DIR / "jobs.db"
_WEBHOOK_TIMEOUT = 10.0
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _normalize_status(raw_status: str) -> str:
    """
    Map internal pipeline status to the strict .NET contract.

    All in-progress statuses → "processing".
    Terminal statuses pass through unchanged.
    """
    if raw_status in _TERMINAL_STATUSES:
        return raw_status
    return "processing"


def _build_download_url(job_id: str, is_audio: bool = False) -> str:
    """
    Construct the download URL for a completed job.

    The .NET backend fetches the dubbed media from this endpoint
    and uploads it to Azure Blob Storage.
    """
    host = os.getenv("SERVICE_HOST", "localhost")
    port = os.getenv("SERVICE_PORT", "8000")
    ext = "wav" if is_audio else "mp4"
    return f"http://{host}:{port}/api/dubbing/download/{job_id}.{ext}"


class JobManager:
    """
    SQLite-backed job registry with background asyncio execution
    and optional webhook push notifications.

    Usage from the router:
        job_id = job_manager.create_job(video_url="...", target_language="fr")
        job_manager.start_pipeline(job_id)
        row = job_manager.get_job(job_id)       # reads from SQLite
        await job_manager.cancel_job(job_id)     # cancels + updates DB
    """

    def __init__(self) -> None:
        # In-memory: only for running orchestrators and task handles
        self._active_jobs: Dict[str, DubbingJob] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._db_lock = threading.Lock()
        self._init_db()

    # ══════════════════════════════════════════════════════════
    # SQLite Helpers
    # ══════════════════════════════════════════════════════════

    def _init_db(self) -> None:
        """Create the jobs table if it doesn't exist."""
        self._db_write("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id               TEXT PRIMARY KEY,
                status               TEXT NOT NULL DEFAULT 'processing',
                progress             REAL NOT NULL DEFAULT 0.0,
                translated_video_url TEXT,
                error_message        TEXT,
                webhook_url          TEXT,
                current_stage        TEXT,
                transcript           TEXT,
                translated_text      TEXT
            )
        """)
        logger.info(f"📂 SQLite database ready at {DB_PATH}")

        self._ensure_column("current_stage", "TEXT")
        self._ensure_column("transcript", "TEXT")
        self._ensure_column("translated_text", "TEXT")

    def _ensure_column(self, name: str, column_type: str) -> None:
        """Add a nullable column to existing SQLite databases."""
        with self._db_lock:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
                }
                if name not in columns:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {column_type}")
                    conn.commit()
            finally:
                conn.close()

    def _db_write(self, sql: str, params: tuple = ()) -> None:
        """Execute a write query with thread-safe locking."""
        with self._db_lock:
            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()

    def _db_read_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Read a single row and return it as a dict (or None)."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _db_read_all(self, sql: str, params: tuple = ()) -> List[dict]:
        """Read all matching rows as a list of dicts."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def _update_job(self, job_id: str, **fields) -> None:
        """Update specific columns in the jobs table."""
        if not fields:
            return
        set_clause = ", ".join(f"{col} = ?" for col in fields)
        values = tuple(fields.values()) + (job_id,)
        self._db_write(
            f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values
        )

    # ══════════════════════════════════════════════════════════
    # Create
    # ══════════════════════════════════════════════════════════

    def create_job(
        self,
        video_url: str,
        target_language: str,
        input_type: str = "video",
        source_language: str = "auto",
        voice_gender: str = "male",
        voice_age: Optional[str] = None,
        voice_pitch: Optional[str] = None,
        voice_style: Optional[str] = None,
        clone_speaker: bool = True,
        burn_subtitles: bool = True,
        enable_lipsync: bool = False,
        webhook_url: Optional[str] = None,
    ) -> str:
        """
        Create a DubbingJob, persist it in SQLite, and return the job_id.

        The `video_url` is stored as `input_path` on the internal
        DubbingJob — the pipeline's download stage handles URL fetching.
        """
        # Build the in-memory job object for the orchestrator
        job = DubbingJob(
            input_path=video_url,
            input_type=input_type,
            target_language=target_language,
            source_language=source_language,
            voice_gender=voice_gender or "male",
            voice_age=voice_age,
            voice_pitch=voice_pitch,
            voice_style=voice_style,
            clone_speaker=clone_speaker,
            burn_subtitles=burn_subtitles,
            enable_lipsync=enable_lipsync,
        )
        job_id = job.job_id

        # Persist to SQLite
        self._db_write(
            """INSERT INTO jobs
               (job_id, status, progress, translated_video_url,
                error_message, webhook_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, "processing", 0.0, None, None, webhook_url),
        )

        # Keep in-memory for the orchestrator
        self._active_jobs[job_id] = job

        logger.info(
            f"📋 Job {job_id} created  "
            f"{source_language} → {target_language}  "
            f"{'webhook=' + webhook_url if webhook_url else '(polling only)'}"
        )
        return job_id

    # ══════════════════════════════════════════════════════════
    # Read (from SQLite)
    # ══════════════════════════════════════════════════════════

    def get_job(self, job_id: str) -> Optional[dict]:
        """
        Look up a job by ID from SQLite.

        Returns a dict with keys matching the strict .NET contract:
        {job_id, status, progress, translated_video_url, error_message}
        or None if not found.
        """
        return self._db_read_one(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        )

    def list_jobs(self) -> List[dict]:
        """Return all registered jobs from SQLite."""
        return self._db_read_all("SELECT * FROM jobs ORDER BY rowid DESC")

    @property
    def active_count(self) -> int:
        """Number of jobs currently running (in-memory tasks)."""
        return sum(1 for t in self._tasks.values() if not t.done())

    # ══════════════════════════════════════════════════════════
    # Start
    # ══════════════════════════════════════════════════════════

    def start_pipeline(self, job_id: str) -> asyncio.Task:
        """
        Launch the pipeline as a background asyncio task.

        Uses `asyncio.create_task()` (not BackgroundTasks) so we get
        a Task handle that supports `.cancel()`.
        """
        task = asyncio.create_task(
            self._execute(job_id),
            name=f"dubbing-{job_id}",
        )
        self._tasks[job_id] = task
        logger.info(f"▶️  Job {job_id} — pipeline task launched")
        return task

    # ══════════════════════════════════════════════════════════
    # Cancel
    # ══════════════════════════════════════════════════════════

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job's asyncio task.

        1. Sends task.cancel() → raises CancelledError at next await.
        2. The current stage finishes; the next stage never starts.
        3. Sets SQLite status to "cancelled" immediately.
        4. Orchestrator's finally block cleans up temp files.

        Returns True if a running task was found and cancelled.
        """
        task = self._tasks.get(job_id)
        if not task or task.done():
            return False

        logger.info(f"🛑 Job {job_id} — cancellation requested")
        task.cancel()

        # Update SQLite immediately to 'cancelled' so status is synced instantly
        self._update_job(
            job_id,
            status="cancelled",
            progress=0.0,
            error_message=None,
            current_stage="cancelled",
        )

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=30.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        return True

    # ══════════════════════════════════════════════════════════
    # Webhook Push Notifications
    # ══════════════════════════════════════════════════════════

    async def _send_webhook(self, job_id: str) -> None:
        """
        POST a status update to the .NET backend's webhook URL.

        Reads the current state from SQLite and sends it.  Failures
        are logged but never block the pipeline — webhooks are
        best-effort.  .NET can always fall back to polling.
        """
        row = self.get_job(job_id)
        if not row:
            return

        webhook_url = row.get("webhook_url")
        if not webhook_url:
            return

        payload = {
            "job_id":               row["job_id"],
            "status":               row["status"],
            "progress":             row["progress"],
            "translated_video_url": row.get("translated_video_url"),
            "error_message":        row.get("error_message"),
            "currentStage":         row.get("current_stage"),
            "transcript":           row.get("transcript"),
            "translatedText":       row.get("translated_text"),
        }

        try:
            async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
                webhook_headers = {"X-Webhook-Secret": "your-shared-webhook-secret"}
                resp = await client.post(webhook_url, json=payload, headers=webhook_headers)
                logger.info(
                    f"  🔔 Webhook → {webhook_url}  "
                    f"status={payload['status']}  "
                    f"progress={payload['progress']}%  "
                    f"http={resp.status_code}"
                )
        except httpx.TimeoutException:
            logger.warning(
                f"  ⚠️  Webhook timed out for job {job_id} → {webhook_url}"
            )
        except Exception as exc:
            logger.warning(
                f"  ⚠️  Webhook failed for job {job_id}: {exc}"
            )

    # ══════════════════════════════════════════════════════════
    # Internal: Pipeline Execution Wrapper
    # ══════════════════════════════════════════════════════════

    async def _execute(self, job_id: str) -> None:
        """
        Run the full pipeline inside a background asyncio task.

        Three outcomes:
          ✅ Success  → status="completed", translated_video_url set
          ⛔ Failure  → status="failed",    error_message set
          🛑 Cancel   → status="cancelled"

        On every internal status change the progress is synced to
        SQLite and a webhook is fired (if configured).
        """
        job = self._active_jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in active jobs")
            return

        # Track internal status for change-detection (webhooks fire
        # only on actual transitions, not on every progress tick).
        last_internal_status = job.status
        last_transcript = job.transcript or job.transcribed_text
        last_translated_text = job.translated_text

        async def _on_progress(updated_job: DubbingJob) -> None:
            nonlocal last_internal_status, last_transcript, last_translated_text
            current = updated_job.status

            # Sync to SQLite on every progress tick
            raw = current.value if isinstance(current, JobStatus) else str(current)
            resolved_transcript = updated_job.transcript or updated_job.transcribed_text
            self._update_job(
                job_id,
                status=_normalize_status(raw),
                progress=round(updated_job.overall_progress or 0.0, 1),
                current_stage=raw,
                transcript=resolved_transcript,
                translated_text=updated_job.translated_text,
            )

            transcript_changed = resolved_transcript != last_transcript
            translated_text_changed = updated_job.translated_text != last_translated_text
            should_notify = (
                current != last_internal_status
                or transcript_changed
                or translated_text_changed
            )

            # Fire webhook only on stage/text transitions
            if should_notify:
                last_internal_status = current
                last_transcript = resolved_transcript
                last_translated_text = updated_job.translated_text
                logger.debug(
                    f"  📊 Job {job_id}: stage → {raw}  "
                    f"({updated_job.overall_progress:.0f}%)"
                )
                await self._send_webhook(job_id)

        orchestrator = VocalBridgeOrchestrator(
            job, progress_callback=_on_progress
        )

        try:
            # ── Run the pipeline ──
            await orchestrator.run()

            # ── Success ──
            is_audio = job.input_type.lower() == "audio"
            download_url = _build_download_url(job_id, is_audio=is_audio)
            self._update_job(
                job_id,
                status="completed",
                progress=100.0,
                translated_video_url=download_url,
                current_stage="completed",
                transcript=job.transcript or job.transcribed_text,
                translated_text=job.translated_text,
            )
            logger.info(
                f"✅ Job {job_id} completed → {download_url}"
            )
            await self._send_webhook(job_id)

        except asyncio.CancelledError:
            # ── Cancellation ──
            self._update_job(
                job_id,
                status="cancelled",
                progress=0.0,
                error_message=None,
                current_stage="cancelled",
            )
            logger.warning(f"🛑 Job {job_id} cancelled")
            # Shield the final webhook from the cancellation signal
            try:
                await asyncio.shield(self._send_webhook(job_id))
            except asyncio.CancelledError:
                pass
            raise  # re-raise so asyncio marks the Task as cancelled

        except Exception as exc:
            # ── Failure ──
            self._update_job(
                job_id,
                status="failed",
                progress=100.0,
                error_message=str(exc),
                current_stage="failed",
                transcript=job.transcript or job.transcribed_text,
                translated_text=job.translated_text,
            )
            logger.error(f"💥 Job {job_id} failed: {exc}")
            await self._send_webhook(job_id)

        finally:
            self._active_jobs.pop(job_id, None)
            self._tasks.pop(job_id, None)


# ─── Singleton ────────────────────────────────────────────────────
job_manager = JobManager()
