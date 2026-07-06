"""
Video utility functions for the AI Dubbing System.
Provides helpers for video analysis, manipulation, and format handling.
"""
from pathlib import Path
from utils.logger import logger


def get_video_info(file_path: str) -> dict:
    """
    Extract metadata from a video file.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Dictionary with video metadata
    """
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(file_path) as clip:
            info = {
                "duration": clip.duration,
                "fps": clip.fps,
                "size": clip.size,
                "width": clip.size[0],
                "height": clip.size[1],
                "has_audio": clip.audio is not None,
                "filename": Path(file_path).name,
            }
            logger.info(f"Video info: {info['width']}x{info['height']}, "
                       f"{info['duration']:.1f}s, {info['fps']}fps")
            return info
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {}


def validate_video_file(file_path: str, allowed_extensions: set) -> bool:
    """
    Validate that a file is a supported video format.
    
    Args:
        file_path: Path to check
        allowed_extensions: Set of allowed extensions (e.g., {'.mp4', '.avi'})
        
    Returns:
        True if valid video file
    """
    path = Path(file_path)
    
    if not path.exists():
        logger.error(f"Video file not found: {file_path}")
        return False
    
    if path.suffix.lower() not in allowed_extensions:
        logger.error(f"Unsupported format: {path.suffix}")
        return False
    
    if path.stat().st_size == 0:
        logger.error(f"Video file is empty: {file_path}")
        return False
    
    return True


def get_video_duration(file_path: str) -> float:
    """
    Get the duration of a video file in seconds.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Duration in seconds
    """
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(file_path) as clip:
            return clip.duration
    except Exception as e:
        logger.error(f"Failed to get video duration: {e}")
        return 0.0


def format_duration(seconds: float) -> str:
    """
    Format seconds into a human-readable duration string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like '2m 30s'
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
