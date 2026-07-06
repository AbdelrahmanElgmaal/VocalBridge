"""
Stage 9 — Subtitle & Mux

Muxes the dubbed audio track back into the original video, muting the original audio track.
Uses the ffmpeg binary bundled with imageio-ffmpeg for high performance and reliability.
"""
import subprocess
import os
from pathlib import Path
from utils.logger import pipeline_logger as logger
import imageio_ffmpeg

def subtitle(video_path: str, audio_path: str, srt_path: str, output_path: str, burn_subs: bool = False) -> dict:
    """
    Muxes the new audio file into the original video, replacing the original audio.
    Optionally burns subtitles into the video track.
    
    Args:
        video_path: Path to the original video file
        audio_path: Path to the new translated WAV file
        srt_path: Path to the translated SRT file
        output_path: Path where the output MP4 should be saved
        burn_subs: If True, burn subtitles into the video stream (requires video re-encoding)
        
    Returns:
        dict: output_path
    """
    logger.info(f"🎬 Muxing audio & video: {video_path} + {audio_path} -> {output_path}")
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Base command: replace audio
    # -map 0:v:0 selects the first video stream of the video input
    # -map 1:a:0 selects the first audio stream of the audio input
    # This automatically ignores/mutes the original audio stream of the video input
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", video_path,
        "-i", audio_path,
    ]
    
    if burn_subs and srt_path and Path(srt_path).exists():
        logger.info(f"🔥 Burning subtitles into video: {srt_path}")
        # FFMPEG subtitle filter has tricky path escaping on Windows:
        # colons must be escaped, and slashes must be forward slashes.
        safe_srt_path = str(Path(srt_path).resolve()).replace("\\", "/")
        safe_srt_path = safe_srt_path.replace(":", "\\:")
        
        cmd.extend([
            "-filter_complex", f"subtitles='{safe_srt_path}'",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0"
        ])
    else:
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0"
        ])
        
    cmd.append(output_path)
    
    logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    
    if result.returncode != 0:
        logger.error(f"FFmpeg failed with return code {result.returncode}")
        logger.error(f"FFmpeg stderr:\n{result.stderr}")
        raise RuntimeError(f"FFmpeg muxing failed: {result.stderr}")
        
    logger.info(f"✅ Muxing complete -> {output_path}")
    return {
        "output_path": output_path,
    }
