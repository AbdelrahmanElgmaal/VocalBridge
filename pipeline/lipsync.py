"""
Stage 10.5 — Lip Sync (Wav2Lip)

Takes the original video and the assembled dubbed audio,
and generates a new video where the speaker's lips are
synchronized with the dubbed audio using the Wav2Lip model.

This stage is OPTIONAL — controlled by the `enable_lipsync`
flag on the DubbingJob. When disabled, the pipeline skips
this stage entirely.
"""
import subprocess
import sys
import os
from pathlib import Path
from utils.logger import pipeline_logger as logger


# ── Wav2Lip engine paths ─────────────────────────────────────
WAV2LIP_DIR = Path(__file__).resolve().parent.parent / "wav2lip_engine"
CHECKPOINT_PATH = WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"
FACE_DETECT_PATH = WAV2LIP_DIR / "face_detection" / "detection" / "sfd" / "s3fd.pth"


def check_wav2lip_ready() -> bool:
    """Check if Wav2Lip engine and models are properly set up."""
    if not WAV2LIP_DIR.exists():
        logger.warning(f"Wav2Lip engine directory not found: {WAV2LIP_DIR}")
        return False
    if not CHECKPOINT_PATH.exists():
        logger.warning(f"Wav2Lip checkpoint not found: {CHECKPOINT_PATH}")
        return False
    if not (WAV2LIP_DIR / "inference.py").exists():
        logger.warning(f"Wav2Lip inference.py not found in: {WAV2LIP_DIR}")
        return False
    return True


def lipsync(
    video_path: str,
    audio_path: str,
    output_path: str,
    resize_factor: int = 1,
    pads: str = "0 20 0 0",          # More chin room → better accuracy
    nosmooth: bool = False,
    face_det_batch_size: int = 4,    # Smaller = more careful, less skipped frames
    wav2lip_batch_size: int = 8,     # Smaller = less temporal audio-frame drift
    mel_step_size: int = 16,         # Larger mel context (try 20) → better sync
    enhance_face: bool = True,       # Bicubic+unsharp sharpening on face crops
) -> dict:
    """
    Run Wav2Lip inference to generate a lip-synced video.

    The model takes the original video (as the face source) and the
    new dubbed audio, then generates a video where the speaker's lips
    move in sync with the dubbed audio.

    Args:
        video_path:           Path to the original video (face source)
        audio_path:           Path to the assembled dubbed audio (WAV)
        output_path:          Path where the lip-synced video will be saved
        resize_factor:        Reduce video resolution for faster processing
                              (1=original, 2=half resolution, etc.)
                              Default is 1 (full res) for optimized CPU processing.
        pads:                 Face detection bounding box padding
                              "top bottom left right" — increase bottom if
                              chin is cut off
        nosmooth:             If True, disable face detection smoothing
                              (try if face tracking is jittery)
        face_det_batch_size:  Batch size for face detection (higher = faster).
                              Default 8 for optimized CPU processing.
        wav2lip_batch_size:   Batch size for Wav2Lip model (higher = faster).
                              Default 16 for optimized CPU processing.

    Returns:
        dict: {'output_path': str} — path to the lip-synced video
    """
    logger.info("👄 Starting Wav2Lip lip-sync…")
    logger.info(f"   Video (face source): {video_path}")
    logger.info(f"   Audio (dubbed):      {audio_path}")
    logger.info(f"   Output:              {output_path}")
    logger.info(f"   Resize factor:       {resize_factor}")
    logger.info(f"   Pads:                {pads}")
    logger.info(f"   mel_step_size:       {mel_step_size}")
    logger.info(f"   enhance_face:        {enhance_face}")

    # ── Validate prerequisites ──
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Input audio not found: {audio_path}")

    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(
            f"Wav2Lip checkpoint not found at {CHECKPOINT_PATH}.\n"
            f"Download wav2lip_gan.pth from:\n"
            f"  https://iiitaphyd-my.sharepoint.com/:u:/g/personal/"
            f"radrabha_m_research_iiit_ac_in/EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA\n"
            f"and place it in: {CHECKPOINT_PATH.parent}"
        )

    inference_script = WAV2LIP_DIR / "inference.py"
    if not inference_script.exists():
        raise FileNotFoundError(
            f"Wav2Lip inference.py not found at {inference_script}. "
            f"Make sure wav2lip_engine/ is cloned from "
            f"https://github.com/Rudrabha/Wav2Lip.git"
        )

    # ── Ensure output directory exists ──
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # ── Build the inference command ──
    pad_values = pads.split()
    cmd = [
        sys.executable,
        str(inference_script),
        "--checkpoint_path", str(CHECKPOINT_PATH),
        "--face", str(video_path),
        "--audio", str(audio_path),
        "--outfile", str(output_path),
        "--resize_factor", str(resize_factor),
        "--pads", *pad_values,
        "--face_det_batch_size", str(face_det_batch_size),
        "--wav2lip_batch_size", str(wav2lip_batch_size),
        "--mel_step_size", str(mel_step_size),
    ]

    if nosmooth:
        cmd.append("--nosmooth")
    if enhance_face:
        cmd.append("--enhance_face")

    logger.info(f"   Python executable: {sys.executable}")
    logger.info(f"   Command: {' '.join(cmd)}")

    # ── Configure environment variables to limit thread counts ──
    env = os.environ.copy()
    cpu_count = os.cpu_count() or 4
    # Leave at least 1-2 cores free, using at most half of the available cores.
    # This prevents the computer's CPU from being pinned at 100% and lagging the OS.
    threads_to_use = str(max(1, min(cpu_count - 1, cpu_count // 2)))

    env["OMP_NUM_THREADS"] = threads_to_use
    env["MKL_NUM_THREADS"] = threads_to_use
    env["OPENBLAS_NUM_THREADS"] = threads_to_use
    env["VECLIB_MAXIMUM_THREADS"] = threads_to_use
    env["NUMEXPR_NUM_THREADS"] = threads_to_use
    env["TF_NUM_INTEROP_THREADS"] = threads_to_use
    env["TF_NUM_INTRAOP_THREADS"] = threads_to_use

    # ── Ensure wav2lip_engine is on PYTHONPATH so the bundled
    #    face_detection package is always importable regardless of how
    #    the parent server process was launched. ──
    existing_pypath = env.get("PYTHONPATH", "")
    wav2lip_dir_str = str(WAV2LIP_DIR)
    if wav2lip_dir_str not in existing_pypath:
        env["PYTHONPATH"] = wav2lip_dir_str + os.pathsep + existing_pypath if existing_pypath else wav2lip_dir_str
    logger.info(f"   PYTHONPATH for subprocess: {env['PYTHONPATH']}")

    # ── Run Wav2Lip as a subprocess with live streaming ──
    # Use Popen instead of run() so we can stream stdout/stderr line-by-line
    # in real time. subprocess.run() buffers ALL output until the process exits,
    # making it look completely frozen during the 15-45 min CPU inference.
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS

    # ── Timeout: 90 minutes max for a CPU-only machine ──
    TIMEOUT_SECONDS = 90 * 60

    import threading
    import time

    proc = subprocess.Popen(
        cmd,
        cwd=str(WAV2LIP_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr → stdout so one reader handles both
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,                  # line-buffered
        startupinfo=startupinfo,
        creationflags=creationflags,
    )

    stderr_lines: list[str] = []   # collect for error reporting

    # ── Heartbeat thread — logs "still running" every 30 s so the terminal
    #    never goes silent and the user knows it hasn't frozen ──
    _stop_heartbeat = threading.Event()

    def _heartbeat():
        elapsed = 0
        while not _stop_heartbeat.is_set():
            time.sleep(30)
            elapsed += 30
            if not _stop_heartbeat.is_set():
                logger.info(f"   [Wav2Lip] ⏳ Still running… ({elapsed}s elapsed, timeout={TIMEOUT_SECONDS}s)")

    hb_thread = threading.Thread(target=_heartbeat, daemon=True)
    hb_thread.start()

    # ── Stream output line-by-line ──
    try:
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            stderr_lines.append(line)          # keep last N lines for error msg
            if len(stderr_lines) > 200:
                stderr_lines.pop(0)
            # Wav2Lip prints tqdm bars with \r — show them as progress lines
            logger.info(f"   [Wav2Lip] {line}")

        proc.wait(timeout=TIMEOUT_SECONDS)

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RuntimeError(
            f"Wav2Lip timed out after {TIMEOUT_SECONDS // 60} minutes. "
            f"The video may be too long to process on CPU. "
            f"Try a shorter clip or enable GPU support."
        )
    finally:
        _stop_heartbeat.set()

    # ── Check return code ──
    if proc.returncode != 0:
        tail = "\n".join(stderr_lines[-30:])
        logger.error(f"Wav2Lip failed (exit code {proc.returncode})")
        raise RuntimeError(
            f"Wav2Lip inference failed (exit code {proc.returncode}):\n{tail}"
        )

    # ── Verify output file ──
    if not Path(output_path).exists():
        # Wav2Lip sometimes writes to results/result_voice.mp4 by default
        fallback = WAV2LIP_DIR / "results" / "result_voice.mp4"
        if fallback.exists():
            import shutil
            shutil.move(str(fallback), output_path)
            logger.info(f"   Moved Wav2Lip output from fallback: {fallback} → {output_path}")
        else:
            raise RuntimeError(
                f"Wav2Lip completed but output file not found at {output_path} "
                f"or fallback {fallback}"
            )

    file_size = Path(output_path).stat().st_size
    logger.info(f"✅ Lip-sync complete → {output_path} ({file_size / 1024 / 1024:.1f} MB)")

    return {"output_path": output_path}
