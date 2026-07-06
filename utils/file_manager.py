"""
File management utilities for the AI Dubbing System.
Handles temporary file creation, cleanup, and path management.
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from config import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR
from utils.logger import logger


def create_job_directories(job_id: str) -> dict:
    """
    Create temporary directories for a dubbing job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Dictionary with paths for the job
    """
    job_temp = TEMP_DIR / job_id
    job_temp.mkdir(parents=True, exist_ok=True)
    
    paths = {
        "temp_dir": str(job_temp),
        "extracted_audio": str(job_temp / "extracted_audio.wav"),
        "dubbed_audio": str(job_temp / "dubbed_audio.wav"),
        "output_video": str(OUTPUT_DIR / f"dubbed_{job_id}.mp4"),
    }
    
    logger.info(f"Created job directories for {job_id}")
    return paths


def cleanup_job_temp(job_id: str):
    """
    Clean up temporary files for a completed job.
    
    Args:
        job_id: Unique job identifier
    """
    job_temp = TEMP_DIR / job_id
    if job_temp.exists():
        shutil.rmtree(job_temp)
        logger.info(f"Cleaned up temp files for job {job_id}")


def cleanup_old_files(max_age_hours: int = 24):
    """
    Remove files older than the specified age from uploads, outputs, and temp.
    
    Args:
        max_age_hours: Maximum age in hours before files are cleaned up
    """
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    
    for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
        if not directory.exists():
            continue
        for item in directory.iterdir():
            try:
                mod_time = datetime.fromtimestamp(item.stat().st_mtime)
                if mod_time < cutoff:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    logger.info(f"Cleaned up old file: {item}")
            except Exception as e:
                logger.warning(f"Failed to clean up {item}: {e}")


def get_safe_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    # Remove path separators and dangerous characters
    safe = Path(filename).name
    safe = "".join(c for c in safe if c.isalnum() or c in ".-_")
    
    if not safe:
        safe = "unnamed_video.mp4"
    
    return safe


def get_upload_path(filename: str, job_id: str) -> str:
    """
    Generate a unique upload path for a video file.
    
    Args:
        filename: Original filename
        job_id: Job identifier
        
    Returns:
        Full path for the uploaded file
    """
    safe_name = get_safe_filename(filename)
    extension = Path(safe_name).suffix or ".mp4"
    upload_path = UPLOAD_DIR / f"{job_id}{extension}"
    return str(upload_path)


def get_disk_usage() -> dict:
    """
    Get disk usage statistics for the project directories.
    
    Returns:
        Dictionary with size info for each directory
    """
    stats = {}
    for name, directory in [("uploads", UPLOAD_DIR), ("outputs", OUTPUT_DIR), ("temp", TEMP_DIR)]:
        if directory.exists():
            total_size = sum(
                f.stat().st_size for f in directory.rglob("*") if f.is_file()
            )
            file_count = sum(1 for f in directory.rglob("*") if f.is_file())
            stats[name] = {
                "size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
            }
        else:
            stats[name] = {"size_mb": 0, "file_count": 0}
    return stats
