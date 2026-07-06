"""
Stage 1 — Download

Fetch a video from a URL **or** ingest a local file, then extract the
audio track as a 16 kHz mono WAV suitable for Whisper.

Supports:
 • Local file paths (copied into the job workspace)
 • HTTP(S) URLs (downloaded with requests / yt-dlp fallback)
"""
import os
import re
import shutil
import json
from pathlib import Path
from urllib.parse import urlparse

from utils.logger import pipeline_logger as logger


# ── Ensure FFmpeg is on PATH ──
_ffmpeg_dir = None

def ensure_ffmpeg():
    """Add imageio_ffmpeg's bundled ffmpeg to PATH if system ffmpeg is absent."""
    global _ffmpeg_dir
    if shutil.which("ffmpeg"):
        _ffmpeg_dir = str(Path(shutil.which("ffmpeg")).parent)
        return
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = Path(ffmpeg_exe).parent
        import sys
        std = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        std_path = ffmpeg_dir / std
        if not std_path.exists():
            shutil.copy2(ffmpeg_exe, str(std_path))
        d = str(ffmpeg_dir)
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        _ffmpeg_dir = d
    except Exception:
        pass


def get_ffmpeg_dir() -> str | None:
    """Return the directory containing ffmpeg, or None if unavailable.
    Useful for yt-dlp's ``ffmpeg_location`` option."""
    if _ffmpeg_dir is None:
        ensure_ffmpeg()
    return _ffmpeg_dir

ensure_ffmpeg()


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _download_url(url: str, dest: str) -> str:
    """Download a video from a URL.  Tries requests first, then yt-dlp."""
    logger.info(f"⬇️  Downloading from URL: {url}")
    Path(dest).parent.mkdir(parents=True, exist_ok=True)

    # ── TikTok-specific Bypass (TikWM API) ──
    if "tiktok.com" in url.lower():
        try:
            import requests as req
            logger.info("  🎵 Detected TikTok URL. Bypassing yt-dlp via TikWM API...")
            api_res = req.get("https://tikwm.com/api/", params={"url": url}, timeout=15).json()
            if api_res.get("code") == 0 and "data" in api_res:
                mp4_url = api_res["data"].get("play")
                if mp4_url:
                    logger.info("  🔗 Extracted raw MP4 URL. Downloading...")
                    r = req.get(mp4_url, stream=True, timeout=120)
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            f.write(chunk)
                    logger.info(f"✅ Downloaded TikTok {Path(dest).stat().st_size / 1e6:.1f} MB via bypass")
                    return dest
        except Exception as e:
            logger.warning(f"TikWM bypass failed ({e}), falling back to yt-dlp...")

    # ── Simple HTTP download ──
    parsed = urlparse(url)
    ext = parsed.path.split(".")[-1].lower()
    if ext in ("mp4", "mkv", "webm", "avi", "mov", "mp3", "wav", "m4a", "ogg", "flac"):
        try:
            import requests as req
            r = req.get(url, stream=True, timeout=120)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            logger.info(f"✅ Downloaded {Path(dest).stat().st_size / 1e6:.1f} MB")
            return dest
        except Exception as e:
            logger.warning(f"Direct download failed ({e}), trying yt-dlp…")

    # ── yt-dlp fallback (YouTube, etc.) ──
    try:
        import subprocess
        import sys
        
        CACHE_FILE = Path("temp/tiktok_api_cache.txt")
        KNOWN_HOSTNAMES = [
            "api16-normal-c-useast1a.tiktokv.com",
            "api22-normal-c-useast2a.tiktokv.com",
            "api16-core-c-useast1a.tiktokv.com",
            "api-h2.tiktokv.com",
            "api.tiktokv.com"
        ]

        def _get_dynamic_hostnames():
            hostnames = []
            if CACHE_FILE.exists():
                cached = CACHE_FILE.read_text().strip()
                if cached: hostnames.append(cached)
            
            # Scrape GitHub for the bleeding edge workaround
            try:
                import requests as req
                gh_url = "https://api.github.com/search/issues"
                res = req.get(gh_url, params={"q": "repo:yt-dlp/yt-dlp tiktok api_hostname", "sort": "updated"}, timeout=5).json()
                for item in res.get("items", [])[:3]:
                    body = item.get("body", "")
                    match = re.search(r"api_hostname=([a-zA-Z0-9.-]+\.tiktokv\.com)", body)
                    if match: hostnames.append(match.group(1))
                    
                    comments_url = item.get("comments_url")
                    if comments_url:
                        c_res = req.get(comments_url, timeout=5).json()
                        for comment in reversed(c_res[-5:]):
                            c_match = re.search(r"api_hostname=([a-zA-Z0-9.-]+\.tiktokv\.com)", comment.get("body", ""))
                            if c_match: hostnames.append(c_match.group(1))
            except Exception as e:
                logger.warning(f"Failed to scrape GitHub for hostnames: {e}")

            hostnames.extend(KNOWN_HOSTNAMES)
            seen = set()
            return [h for h in hostnames if not (h in seen or seen.add(h))]

        is_tiktok = "tiktok.com" in url.lower()
        hostnames_to_try = _get_dynamic_hostnames() if is_tiktok else [None]

        for idx, current_hostname in enumerate(hostnames_to_try):
            dl_cmd = [
                sys.executable, "-m", "yt_dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                "--socket-timeout", "30",
                "-o", dest, url
            ]
            if current_hostname:
                dl_cmd.extend(["--extractor-args", f"tiktok:api_hostname={current_hostname}"])
            
            try:
                subprocess.run(dl_cmd, check=True, capture_output=True, text=True)
                # Success: Cache hostname and return
                if current_hostname:
                    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    CACHE_FILE.write_text(current_hostname)
                logger.info("✅ Downloaded via yt-dlp")
                return dest
                
            except subprocess.CalledProcessError as e:
                # If rehydration error on the very first attempt, try the nightly update ONCE
                if ("Unable to extract universal data for rehydration" in e.stderr or "ERROR" in e.stderr) and idx == 0:
                    logger.warning("yt-dlp failed (rehydration or generic error). Attempting emergency nightly update...")
                    subprocess.run([sys.executable, "-m", "pip", "install", "-U", "https://github.com/yt-dlp/yt-dlp/archive/master.zip"], check=False, capture_output=True)
                    
                    try:
                        subprocess.run(dl_cmd, check=True, capture_output=True, text=True)
                        if current_hostname:
                            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                            CACHE_FILE.write_text(current_hostname)
                        logger.info("✅ Downloaded via yt-dlp after nightly update")
                        return dest
                    except subprocess.CalledProcessError as e2:
                        if "Unable to extract universal data for rehydration" in e2.stderr:
                            logger.warning(f"Nightly update didn't fix rehydration for {current_hostname}. Cycling to next fallback...")
                            continue
                        else:
                            raise RuntimeError(f"yt-dlp failed after update: {e2.stderr}")
                
                # If rehydration error on subsequent hostnames, just cycle
                elif "Unable to extract universal data for rehydration" in e.stderr:
                    logger.warning(f"Hostname {current_hostname} failed with rehydration error. Cycling...")
                    continue
                else:
                    raise RuntimeError(f"yt-dlp failed to download video: {e.stderr}")
                    
        raise RuntimeError("Exhausted all fallback hostnames and yt-dlp still failed.")

    except FileNotFoundError:
        raise RuntimeError("yt-dlp is not installed — cannot download this URL")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"yt-dlp failed to download video: {e.stderr}")


def download(source: str, job_dir: str, is_audio: bool = False) -> dict:
    """
    Stage 1 entry point.

    Args:
        source:  Local file path **or** HTTP(S) URL
        job_dir: Directory for this job's temp files
        is_audio: If True, treats source as audio-only and skips video extraction.

    Returns:
        dict with keys: video_path (None if audio), audio_path, duration
    """
    job = Path(job_dir)
    job.mkdir(parents=True, exist_ok=True)

    # ── Get the file into the workspace ──
    if is_audio:
        # Audio Workflow
        source_ext = Path(urlparse(source).path).suffix if _is_url(source) else Path(source).suffix
        if not source_ext:
            source_ext = ".wav"
        
        audio_path = str(job / ("source_audio" + source_ext))
        
        if _is_url(source):
            _download_url(source, audio_path)
        else:
            if not Path(source).exists():
                raise FileNotFoundError(f"Audio file not found: {source}")
            shutil.copy2(source, audio_path)
            logger.info(f"📂 Copied local file → {Path(audio_path).name}")

        final_audio_path = str(job / "audio.wav")
        # Check if already 16kHz mono wav
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            if info.samplerate == 16000 and info.channels == 1 and info.format == "WAV":
                # Already correct format, just use it
                if audio_path != final_audio_path:
                    shutil.copy2(audio_path, final_audio_path)
                logger.info(f"✅ Audio already in correct format: {final_audio_path}")
            else:
                _convert_audio(audio_path, final_audio_path)
        except Exception:
            _convert_audio(audio_path, final_audio_path)

        # ── Get duration ──
        import soundfile as sf
        duration = sf.info(final_audio_path).duration

        logger.info(f"✅ Stage 1 complete — {duration:.1f}s audio")
        return {
            "video_path": None,
            "audio_path": final_audio_path,
            "duration": duration,
        }
    else:
        # Video Workflow
        if _is_url(source):
            video_path = str(job / "source_video.mp4")
            _download_url(source, video_path)
        else:
            if not Path(source).exists():
                raise FileNotFoundError(f"Video file not found: {source}")
            video_path = str(job / ("source_video" + Path(source).suffix))
            shutil.copy2(source, video_path)
            logger.info(f"📂 Copied local file → {Path(video_path).name}")

        # ── Extract audio ──
        audio_path = str(job / "audio.wav")
        _extract_audio(video_path, audio_path)

        # ── Get duration ──
        from moviepy.editor import VideoFileClip
        with VideoFileClip(video_path) as clip:
            duration = clip.duration

        logger.info(f"✅ Stage 1 complete — {duration:.1f}s video")
        return {
            "video_path": video_path,
            "audio_path": audio_path,
            "duration": duration,
        }

def _convert_audio(input_path: str, output_path: str) -> str:
    """Convert any audio file to 16 kHz mono WAV."""
    logger.info(f"🎧 Converting audio to 16kHz mono WAV: {Path(input_path).name}")
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info(f"✅ Audio converted: {output_path}")
    return output_path


def _extract_audio(video_path: str, output_audio_path: str) -> str:
    """Extract audio from a video file and save as 16 kHz mono WAV."""
    logger.info(f"🎬 Extracting audio from: {Path(video_path).name}")

    from moviepy.editor import VideoFileClip

    video = VideoFileClip(video_path)
    if video.audio is None:
        video.close()
        raise RuntimeError("Video file has no audio track")

    Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)
    video.audio.write_audiofile(
        output_audio_path,
        fps=16000,
        nbytes=2,
        codec="pcm_s16le",
        logger=None,
    )
    video.close()
    logger.info(f"✅ Audio extracted: {output_audio_path}")
    return output_audio_path
