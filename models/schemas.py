"""
Pydantic schemas for the Mazinger Dubbing System.
Defines request/response models and job tracking structures.
"""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from datetime import datetime
import uuid


class JobStatus(str, Enum):
    """Enumeration of possible job states for the simplified 4-stage pipeline."""
    PENDING = "pending"
    DOWNLOADING_AUDIO = "download_audio"
    EXTRACTING_AUDIO = "extract_audio"
    TRANSCRIBING = "speech_recognition"
    TRANSLATING = "translate"
    GENERATING_VOICE = "voice_generation"
    MERGING_VIDEO = "merge_video"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(BaseModel):
    """Represents a single step in the dubbing pipeline."""
    name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0-100
    message: str = ""


class DubbingJob(BaseModel):
    """Full dubbing job with all metadata."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: JobStatus = JobStatus.PENDING
    source_language: str = "auto"
    target_language: str = "ar"
    input_type: str = "video"
    original_filename: str = ""
    input_path: str = ""
    output_path: Optional[str] = None
    # Voice configuration
    voice_gender: str = "female"
    voice_age: Optional[str] = "young adult"
    voice_pitch: Optional[str] = "moderate pitch"
    voice_style: Optional[str] = "natural"
    clone_speaker: bool = True

    # Pipeline data
    transcribed_text: Optional[str] = None
    transcript: Optional[str] = None
    translated_text: Optional[str] = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Progress tracking — 4 stages
    overall_progress: float = 0.0
    current_step: str = "pending"
    steps: List[PipelineStep] = Field(default_factory=list)

    # Error handling
    error_message: Optional[str] = None


class DubRequest(BaseModel):
    """Request model for starting a dubbing job."""
    target_language: str = Field(
        default="ar",
        description="Target language code (e.g., 'ar', 'fr', 'de')"
    )
    source_language: str = Field(
        default="auto",
        description="Source language code or 'auto' for automatic detection"
    )


class DubResponse(BaseModel):
    """Response model after creating a dubbing job."""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    job_id: str
    status: JobStatus
    overall_progress: float
    current_step: str
    steps: List[PipelineStep]
    transcribed_text: Optional[str] = None
    translated_text: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class LanguageInfo(BaseModel):
    """Information about a supported language."""
    code: str
    name: str
    available_as_target: bool = True
    available_as_source: bool = False


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "2.0.0"
    active_jobs: int = 0
    uptime_seconds: float = 0.0


class ProgressUpdate(BaseModel):
    """WebSocket progress update message."""
    job_id: str
    status: JobStatus
    overall_progress: float
    current_step: str
    step_progress: float
    message: str
    steps: List[PipelineStep]
    transcribed_text: Optional[str] = None
    translated_text: Optional[str] = None
