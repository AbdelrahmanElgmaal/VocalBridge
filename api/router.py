"""
API Router — Dubbing Endpoints for .NET Integration
====================================================

Four endpoints for the external .NET backend:

  POST  /api/dubbing/start            → Queue a new dubbing job
  GET   /api/dubbing/status/{id}      → Poll real-time progress
  POST  /api/dubbing/cancel/{id}      → Abort a running job
  GET   /api/dubbing/download/{id}    → Stream the dubbed MP4 file

All status/webhook responses use the strict 5-field contract:
  {job_id, status, progress, translated_video_url, error_message}

The .NET backend workflow:
  1. POST /start with a video URL + target language.
  2. Receive a job_id immediately (HTTP 202).
  3. Poll GET /status/{job_id} every 2–5s, OR receive webhooks.
  4. When status="completed", GET /download/{job_id}.mp4 to stream
     the result and upload it to Azure Blob Storage.
  5. Optionally POST /cancel/{job_id} to abort mid-pipeline.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from api.schemas import (
    DubbingStartRequest,
    DubbingStartResponse,
    DubbingStatusResponse,
    DubbingCancelResponse,
)
from api.job_manager import job_manager
import config

router = APIRouter(prefix="/api/dubbing", tags=["Dubbing"])


# ═══════════════════════════════════════════════════════════════
# POST /api/dubbing/start
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/start",
    response_model=DubbingStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new dubbing job",
    description=(
        "Accepts a video URL and target language, queues the job "
        "in SQLite, and returns immediately with a job_id."
    ),
)
async def start_dubbing(request: DubbingStartRequest):
    """
    .NET calls this to kick off a dubbing pipeline.

    Example cURL:
        curl -X POST http://localhost:8000/api/dubbing/start \\
             -H "Content-Type: application/json" \\
             -d '{
                   "video_url": "https://storage.blob.core.windows.net/v/lecture.mp4",
                   "target_language": "fr",
                   "webhook_url": "https://myapp.com/callback"
                 }'

    Response (HTTP 202):
        {"job_id": "a3f1c8e2", "status": "queued"}
    """
    # 1. Create the job in SQLite + build in-memory DubbingJob
    job_id = job_manager.create_job(
        video_url=str(request.video_url),
        input_type=request.input_type,
        target_language=request.target_language,
        source_language=request.source_language,
        voice_gender=request.voice_gender,
        voice_age=request.voice_age,
        voice_pitch=request.voice_pitch,
        voice_style=request.voice_style,
        clone_speaker=request.clone_speaker,
        burn_subtitles=request.burn_subtitles,
        enable_lipsync=request.enable_lipsync,
        webhook_url=str(request.webhook_url) if request.webhook_url else None,
    )

    # 2. Launch the pipeline as a background asyncio task
    job_manager.start_pipeline(job_id)

    # 3. Return immediately — .NET polls /status or receives webhooks
    return DubbingStartResponse(job_id=job_id, status="queued")


# ═══════════════════════════════════════════════════════════════
# GET /api/dubbing/status/{job_id}
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/status/{job_id}",
    response_model=DubbingStatusResponse,
    summary="Poll job status",
    description=(
        "Returns real-time progress from SQLite. "
        "The .NET backend should poll this every 2–5 seconds."
    ),
)
async def get_job_status(job_id: str):
    """
    .NET polls this to track pipeline progress.

    Example cURL:
        curl http://localhost:8000/api/dubbing/status/a3f1c8e2

    Response examples:
        Processing:  {"job_id":"a3f1","status":"processing","progress":45.0,
                      "translated_video_url":null,"error_message":null}
        Completed:   {"job_id":"a3f1","status":"completed","progress":100.0,
                      "translated_video_url":"http://.../download/a3f1.mp4",
                      "error_message":null}
    """
    row = job_manager.get_job(job_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return DubbingStatusResponse(
        job_id=row["job_id"],
        status=row["status"],
        progress=row["progress"],
        translated_video_url=row.get("translated_video_url"),
        error_message=row.get("error_message"),
        currentStage=row.get("current_stage"),
        transcript=row.get("transcript"),
        translatedText=row.get("translated_text"),
    )


# ═══════════════════════════════════════════════════════════════
# POST /api/dubbing/cancel/{job_id}
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/cancel/{job_id}",
    response_model=DubbingCancelResponse,
    summary="Cancel a running job",
    description=(
        "Aborts a running dubbing job. Returns 400 if the job "
        "has already completed or failed."
    ),
)
async def cancel_dubbing(job_id: str):
    """
    .NET calls this to abort a running pipeline.

    Rules:
        - completed/failed jobs → 400 Bad Request (can't cancel)
        - already cancelled     → 200 with informational message
        - running/processing    → cancel + update SQLite + cleanup

    Example cURL:
        curl -X POST http://localhost:8000/api/dubbing/cancel/a3f1c8e2
    """
    row = job_manager.get_job(job_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    current_status = row["status"]

    # ── 400: Cannot cancel finished jobs ──
    if current_status in ("completed", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot cancel job '{job_id}': "
                f"it has already '{current_status}'. "
                f"Finished jobs cannot be reversed."
            ),
        )

    # ── Already cancelled ──
    if current_status == "cancelled":
        return DubbingCancelResponse(
            job_id=job_id,
            status="cancelled",
            message="Job was already cancelled.",
        )

    # ── Send cancellation signal ──
    cancelled = await job_manager.cancel_job(job_id)

    if cancelled:
        return DubbingCancelResponse(
            job_id=job_id,
            status="cancelled",
            message=(
                "Cancellation signal sent. The current pipeline stage "
                "will complete before the job stops. Temp files will "
                "be cleaned up automatically."
            ),
        )

    # Edge case: task finished between our DB check and cancel call
    return DubbingCancelResponse(
        job_id=job_id,
        status=current_status,
        message="Job is no longer running (may have just finished).",
    )


# ═══════════════════════════════════════════════════════════════
# GET /api/dubbing/download/{job_id}.mp4
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/download/{filename}",
    summary="Download the dubbed media",
    description=(
        "Streams the completed dubbed file. The .NET backend "
        "calls this to fetch the result and upload it to Azure Blob."
    ),
    responses={
        200: {"description": "Dubbed media file"},
        400: {"description": "Job not yet completed"},
        404: {"description": "Job or output file not found"},
    },
)
async def download_result(filename: str):
    """
    .NET streams the dubbed media from this endpoint.
    
    Example cURL:
        curl -o dubbed.mp4 http://localhost:8000/api/dubbing/download/a3f1c8e2.mp4
    """
    import os
    from pathlib import Path
    
    # Safely extract job_id from filename (e.g. a3f1c8e2.mp4 -> a3f1c8e2)
    job_id = Path(filename).stem
    
    row = job_manager.get_job(job_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )

    if row["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not completed (current status: {row['status']})."
        )

    output_path = None
    
    # Try reading the exact output path saved in the database
    output_path_str = row.get("output_path")
    if output_path_str:
        candidate_path = Path(output_path_str)
        if candidate_path.exists():
            output_path = candidate_path

    if not output_path:
        from config import OUTPUT_DIR
        # Fallback heuristics
        output_path = OUTPUT_DIR / f"vocal_bridge_lipsync_{job_id}.mp4"
        if not output_path.exists():
            output_path = OUTPUT_DIR / f"vocal_bridge_{job_id}.mp4"
            if not output_path.exists():
                output_path = OUTPUT_DIR / f"vocal_bridge_{job_id}.wav"
                if not output_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Output file for job {job_id} not found on disk."
                    )

    return FileResponse(
        path=str(output_path),
        filename=filename,
        media_type="audio/wav" if output_path.suffix == ".wav" else "video/mp4",
    )
