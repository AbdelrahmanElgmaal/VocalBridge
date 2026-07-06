"""
API Request / Response Schemas (Cloud-Ready .NET Contract)
===========================================================

Pydantic models defining the strict JSON contract between the .NET
backend and this Python AI microservice.

Key design decisions:
  • The .NET backend sends a `video_url` (Azure Blob SAS URL), NOT a
    local file path.  The AI service downloads it for processing.
  • All responses use a flat, 5-field contract for easy deserialization
    on the C# side.
  • `translated_video_url` points to a local download endpoint hosted
    by this service, so .NET can stream the result and upload it to
    Azure Blob Storage.
"""

from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ═══════════════════════════════════════════════════════════════════
# Request Schemas
# ═══════════════════════════════════════════════════════════════════

class DubbingStartRequest(BaseModel):
    """
    POST /api/dubbing/start — Request body from the .NET backend.

    Example JSON:
    {
        "video_url": "https://mystorage.blob.core.windows.net/videos/lecture.mp4?sv=...",
        "target_language": "fr",
        "source_language": "auto",
        "voice_gender": "female",
        "webhook_url": "https://dotnet-backend.com/api/dubbing-callback"
    }
    """
    video_url: HttpUrl = Field(
        ...,
        description=(
        "URL to the source media (e.g., Azure Blob SAS URL). "
            "The AI service downloads it into a local temp workspace."
        ),
        examples=["https://mystorage.blob.core.windows.net/videos/lecture.mp4"],
    )
    input_type: str = Field(
        default="video",
        description="Type of input media: 'video' or 'audio'.",
    )
    target_language: str = Field(
        ...,
        description="ISO 639-1 target language code.",
        examples=["ar", "fr", "de", "es", "ja"],
    )
    source_language: str = Field(
        default="auto",
        description="Source language code, or 'auto' for detection.",
    )
    voice_gender: Optional[str] = Field(
        default="male",
        description="TTS voice gender: 'male' or 'female'.",
    )
    voice_age: Optional[str] = Field(
        default=None,
        description="TTS voice age descriptor.",
    )
    voice_pitch: Optional[str] = Field(
        default=None,
        description="TTS voice pitch descriptor.",
    )
    voice_style: Optional[str] = Field(
        default=None,
        description="TTS voice style: 'whisper' or null for normal.",
    )
    clone_speaker: bool = Field(
        default=True,
        description="Clone the original speaker's voice for dubbing.",
    )
    burn_subtitles: bool = Field(
        default=True,
        description="Burn translated subtitles into the output video.",
    )
    webhook_url: Optional[HttpUrl] = Field(
        default=None,
        description=(
            "Optional callback URL for push notifications. "
            "If omitted, the .NET backend should poll GET /status/{job_id}."
        ),
        examples=["https://dotnet-backend.com/api/dubbing-callback"],
    )


# ═══════════════════════════════════════════════════════════════════
# Response Schemas — Strict .NET Contract
# ═══════════════════════════════════════════════════════════════════
#
# Every status/webhook response uses the SAME flat 5-field contract:
#
#   Processing:  {"job_id":"abc","status":"processing","progress":45.0,
#                 "translated_video_url":null,"error_message":null}
#
#   Completed:   {"job_id":"abc","status":"completed","progress":100.0,
#                 "translated_video_url":"http://.../download/abc.mp4",
#                 "error_message":null}
#
#   Failed:      {"job_id":"abc","status":"failed","progress":100.0,
#                 "translated_video_url":null,
#                 "error_message":"Detailed error"}
#
#   Cancelled:   {"job_id":"abc","status":"cancelled","progress":0.0,
#                 "translated_video_url":null,"error_message":null}
# ═══════════════════════════════════════════════════════════════════

class DubbingStartResponse(BaseModel):
    """POST /api/dubbing/start — Immediate HTTP 202 response."""
    job_id: str
    status: str = "queued"


class DubbingStatusResponse(BaseModel):
    """
    GET /api/dubbing/status/{job_id} — Polling response.

    The .NET backend deserialises this into a single C# DTO.
    All intermediate pipeline stages are normalised to "processing".
    """
    job_id: str
    status: str
    progress: float
    translated_video_url: Optional[str] = None
    error_message: Optional[str] = None
    currentStage: Optional[str] = None
    transcript: Optional[str] = None
    translatedText: Optional[str] = None


class DubbingCancelResponse(BaseModel):
    """POST /api/dubbing/cancel/{job_id} — Cancellation response."""
    job_id: str
    status: str
    message: str


class WebhookPayload(BaseModel):
    """
    Outbound webhook POSTed to the .NET callback URL.

    Identical shape to DubbingStatusResponse so the .NET backend
    can deserialise both with the same C# class.
    """
    job_id: str
    status: str
    progress: float
    translated_video_url: Optional[str] = None
    error_message: Optional[str] = None
    currentStage: Optional[str] = None
    transcript: Optional[str] = None
    translatedText: Optional[str] = None
