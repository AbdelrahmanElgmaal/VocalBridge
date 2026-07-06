"""
Pipeline package — 9-stage Mazinger AI dubbing pipeline.

Stages:
    1. download      – Fetch / ingest video, extract audio
    2. transcribe    – Speech → SRT subtitles (Whisper)
    3. thumbnails    – Key frame extraction + LLM ranking
    4. describe      – Structured video summary
    5. translate_srt – Duration-aware SRT translation
    6. resegment     – Merge/split subtitle cues
    7. speak         – Per-subtitle TTS with caching
    8. assemble      – Timeline placement & mixing
    9. subtitle      – Burn subtitles + mux audio
"""
