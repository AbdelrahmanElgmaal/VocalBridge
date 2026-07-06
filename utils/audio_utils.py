"""
Audio utility functions for the AI Dubbing System.
Provides helpers for audio format conversion, normalization, and analysis.
"""
import os
import numpy as np
from pathlib import Path
from utils.logger import logger


def normalize_audio(audio_array: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Normalize audio array to target dB level.
    
    Args:
        audio_array: Input audio as numpy array
        target_db: Target loudness in dB
        
    Returns:
        Normalized audio array
    """
    if audio_array.size == 0:
        return audio_array
    
    # Calculate current RMS
    rms = np.sqrt(np.mean(audio_array.astype(float) ** 2))
    if rms == 0:
        return audio_array
    
    # Calculate target RMS
    target_rms = 10 ** (target_db / 20.0)
    
    # Scale audio
    gain = target_rms / rms
    normalized = audio_array * gain
    
    # Clip to prevent distortion
    max_val = np.iinfo(np.int16).max if audio_array.dtype == np.int16 else 1.0
    normalized = np.clip(normalized, -max_val, max_val)
    
    logger.info(f"Audio normalized: gain={gain:.2f}, target_db={target_db}")
    return normalized


def get_audio_duration(file_path: str) -> float:
    """
    Get the duration of an audio file in seconds.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Duration in seconds
    """
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(file_path) as clip:
            return clip.duration
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        return 0.0


def convert_sample_rate(audio_array: np.ndarray, original_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio to a different sample rate.
    
    Args:
        audio_array: Input audio array
        original_sr: Original sample rate
        target_sr: Target sample rate
        
    Returns:
        Resampled audio array
    """
    if original_sr == target_sr:
        return audio_array
    
    from scipy.signal import resample
    
    ratio = target_sr / original_sr
    target_length = int(len(audio_array) * ratio)
    resampled = resample(audio_array, target_length)
    
    logger.info(f"Audio resampled: {original_sr}Hz → {target_sr}Hz")
    return resampled


def split_text_into_chunks(text: str, max_length: int = 200) -> list:
    """
    Split text into chunks suitable for TTS processing.
    Splits on sentence boundaries to maintain natural speech flow.
    
    Args:
        text: Input text to split
        max_length: Maximum characters per chunk
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    # Split on sentence boundaries
    sentences = []
    for delimiter in ['. ', '! ', '? ', '؟ ', '。']:
        if delimiter in text:
            parts = text.split(delimiter)
            sentences = [p + delimiter.strip() for p in parts if p.strip()]
            break
    
    if not sentences:
        # Fall back to splitting on spaces
        words = text.split()
        sentences = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > max_length:
                if current:
                    sentences.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            sentences.append(current)
    
    # Merge short sentences into chunks
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk = f"{current_chunk} {sentence}".strip()
    if current_chunk:
        chunks.append(current_chunk)
    
    logger.info(f"Text split into {len(chunks)} chunks")
    return chunks


def ensure_wav_format(file_path: str) -> str:
    """
    Ensure an audio file is in WAV format. Convert if necessary.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Path to the WAV file
    """
    path = Path(file_path)
    if path.suffix.lower() == ".wav":
        return str(path)
    
    wav_path = path.with_suffix(".wav")
    try:
        from moviepy.editor import AudioFileClip
        with AudioFileClip(str(path)) as clip:
            clip.write_audiofile(str(wav_path), logger=None)
        logger.info(f"Converted {path.suffix} to WAV: {wav_path}")
        return str(wav_path)
    except Exception as e:
        logger.error(f"Failed to convert to WAV: {e}")
        raise
