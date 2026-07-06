"""
Test suite for the AI Dubbing System pipeline and API.
"""
import pytest
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    SUPPORTED_LANGUAGES, LANGUAGE_MODELS,
    ALLOWED_VIDEO_EXTENSIONS, UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR,
)
from models.schemas import (
    DubbingJob, JobStatus, PipelineStep, DubRequest,
    DubResponse, HealthResponse, ProgressUpdate,
)
from utils.audio_utils import split_text_into_chunks
from utils.video_utils import format_duration
from utils.file_manager import get_safe_filename, create_job_directories, cleanup_job_temp


class TestConfig:
    """Test configuration values."""
    
    def test_supported_languages_not_empty(self):
        assert len(SUPPORTED_LANGUAGES) > 0
    
    def test_all_language_models_have_valid_keys(self):
        for key in LANGUAGE_MODELS:
            parts = key.split("-")
            assert len(parts) == 2, f"Invalid key: {key}"
            assert parts[0] in SUPPORTED_LANGUAGES, f"Source lang '{parts[0]}' not in supported"
            assert parts[1] in SUPPORTED_LANGUAGES, f"Target lang '{parts[1]}' not in supported"
    
    
    def test_allowed_extensions(self):
        assert ".mp4" in ALLOWED_VIDEO_EXTENSIONS
        assert ".avi" in ALLOWED_VIDEO_EXTENSIONS
        assert ".txt" not in ALLOWED_VIDEO_EXTENSIONS
    
    def test_directories_exist(self):
        assert UPLOAD_DIR.exists()
        assert OUTPUT_DIR.exists()
        assert TEMP_DIR.exists()


class TestSchemas:
    """Test Pydantic schemas."""
    
    def test_create_dubbing_job(self):
        job = DubbingJob()
        assert job.status == JobStatus.PENDING
        assert len(job.job_id) == 8
        assert len(job.steps) == 4
        assert job.overall_progress == 0.0
    
    def test_job_with_custom_values(self):
        job = DubbingJob(
            source_language="en",
            target_language="fr",
            original_filename="test.mp4",
        )
        assert job.source_language == "en"
        assert job.target_language == "fr"
        assert job.original_filename == "test.mp4"
    
    def test_pipeline_step(self):
        step = PipelineStep(name="extract_audio")
        assert step.status == "pending"
        assert step.progress == 0.0
    
    def test_dub_request(self):
        req = DubRequest(target_language="ar")
        assert req.target_language == "ar"
        assert req.source_language == "auto"
    
    def test_dub_response(self):
        resp = DubResponse(
            job_id="abc123",
            status=JobStatus.PENDING,
            message="Job created",
        )
        assert resp.job_id == "abc123"
    
    def test_health_response(self):
        health = HealthResponse()
        assert health.status == "healthy"
        assert health.version == "2.0.0"
    
    def test_progress_update(self):
        update = ProgressUpdate(
            job_id="test",
            status=JobStatus.TRANSCRIBING,
            overall_progress=30.0,
            current_step="transcribe",
            step_progress=50.0,
            message="Transcribing...",
            steps=[],
        )
        assert update.overall_progress == 30.0


class TestAudioUtils:
    """Test audio utility functions."""
    
    def test_split_short_text(self):
        chunks = split_text_into_chunks("Hello world", 200)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"
    
    def test_split_long_text(self):
        text = "This is sentence one. This is sentence two. This is sentence three. " * 5
        chunks = split_text_into_chunks(text, 100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100 or len(chunk.split()) <= 2  # Allow single long words
    
    def test_split_empty_text(self):
        chunks = split_text_into_chunks("", 200)
        assert len(chunks) == 1
        assert chunks[0] == ""


class TestVideoUtils:
    """Test video utility functions."""
    
    def test_format_duration_seconds(self):
        assert format_duration(30) == "30s"
        assert format_duration(0) == "0s"
    
    def test_format_duration_minutes(self):
        assert format_duration(90) == "1m 30s"
        assert format_duration(600) == "10m 0s"
    
    def test_format_duration_hours(self):
        assert format_duration(3661) == "1h 1m"


class TestFileManager:
    """Test file management utilities."""
    
    def test_safe_filename(self):
        assert get_safe_filename("test.mp4") == "test.mp4"
        assert get_safe_filename("../../etc/passwd") == "passwd"
        assert get_safe_filename("my video (1).mp4") == "myvideo1.mp4"
    
    def test_safe_filename_empty(self):
        assert get_safe_filename("") == "unnamed_video.mp4"
        assert get_safe_filename("///") == "unnamed_video.mp4"
    
    def test_create_job_directories(self):
        paths = create_job_directories("test_job")
        assert "temp_dir" in paths
        assert "extracted_audio" in paths
        assert "dubbed_audio" in paths
        assert "output_video" in paths
        # Cleanup
        cleanup_job_temp("test_job")


class TestSubtitle:
    """Test subtitle/muxing utility."""
    
    def test_subtitle_success(self, monkeypatch):
        import subprocess
        from pipeline.subtitle import subtitle
        
        called_cmd = []
        
        class MockCompletedProcess:
            returncode = 0
            stdout = "success"
            stderr = ""
            
        def mock_run(cmd, *args, **kwargs):
            nonlocal called_cmd
            called_cmd = cmd
            return MockCompletedProcess()
            
        monkeypatch.setattr(subprocess, "run", mock_run)
        
        res = subtitle(
            video_path="input.mp4",
            audio_path="input.wav",
            srt_path="input.srt",
            output_path="output.mp4",
            burn_subs=False
        )
        
        assert res["output_path"] == "output.mp4"
        assert "input.mp4" in called_cmd
        assert "input.wav" in called_cmd
        assert "output.mp4" in called_cmd
        assert "-c:v" in called_cmd
        assert "copy" in called_cmd
        
    def test_subtitle_failure(self, monkeypatch):
        import subprocess
        from pipeline.subtitle import subtitle
        
        class MockCompletedProcess:
            returncode = 1
            stdout = ""
            stderr = "ffmpeg error"
            
        def mock_run(cmd, *args, **kwargs):
            return MockCompletedProcess()
            
        monkeypatch.setattr(subprocess, "run", mock_run)
        
        with pytest.raises(RuntimeError) as exc_info:
            subtitle(
                video_path="input.mp4",
                audio_path="input.wav",
                srt_path="input.srt",
                output_path="output.mp4",
                burn_subs=False
            )
        assert "FFmpeg muxing failed" in str(exc_info.value)


class TestAPIIntegration:
    """Test API endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint returns valid response."""
        from httpx import AsyncClient, ASGITransport
        from main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data

    @pytest.mark.asyncio
    async def test_dubbing_flow_and_cancel(self, monkeypatch):
        """Test submitting a dubbing job and cancelling it."""
        from httpx import AsyncClient, ASGITransport
        from main import app
        from api.job_manager import job_manager
        
        # Mock orchestrator run to avoid actually executing the pipeline
        async def mock_run(self):
            import asyncio
            try:
                # Simulate long running task that checks cancellation
                for _ in range(100):
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
        
        monkeypatch.setattr("pipeline.vocal_bridge.VocalBridgeOrchestrator.run", mock_run)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Start job
            payload = {
                "video_url": "https://storage.blob.core.windows.net/v/lecture.mp4",
                "target_language": "ar"
            }
            response = await client.post("/api/dubbing/start", json=payload)
            assert response.status_code == 202
            data = response.json()
            job_id = data["job_id"]
            assert data["status"] == "queued"

            # Check in-memory task exists
            task = job_manager._tasks.get(job_id)
            assert task is not None
            assert not task.done()

            # 2. Cancel job
            cancel_response = await client.post(f"/api/dubbing/cancel/{job_id}")
            assert cancel_response.status_code == 200
            cancel_data = cancel_response.json()
            assert cancel_data["status"] == "cancelled"

            # Check status from DB
            status_response = await client.get(f"/api/dubbing/status/{job_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["status"] == "cancelled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
