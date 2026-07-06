# Vocal Bridge — 9-Stage Architecture

The Vocal Bridge pipeline has evolved significantly. Here is the *current* architecture reflecting the strict timeline generation, OmniVoice local ML generation, and advanced LLM diacritization passes.

## Stage 1: Download (`download.py`)
- Pulls local files or URLs.
- **`yt-dlp` Sub-process Integration**: Bypasses Windows `PATH` issues by explicitly executing as a Python module (`sys.executable -m yt_dlp`). It avoids `--impersonate chrome` to prevent TCP resets (`curl: (56)`) triggered by platforms like TikTok.
- **TikTok Workaround & Self-Healing**: Includes a hardcoded bypass forcing `yt-dlp` to route through TikTok's legacy `api16` endpoints. If the local virtual environment's `yt-dlp` package is outdated and crashes, an emergency auto-updater intercepts the crash and dynamically installs the bleeding-edge nightly `yt-dlp` branch directly from GitHub into the running memory context, then retries the download.
- Extracts base PCM audio via FFmpeg.

## Stage 2: Transcribe (`transcribe.py`)
- Uses `faster-whisper` to generate base timestamped chunks of the original language audio.
- Emits raw SRT blocks.

## Stage 3 & 4: Thumbnails & Describe 
- *(Feature expansion areas for scene context mapping. Not currently blocking audio flow.)*

## Stage 5: Translate (`translate_srt.py`)
- Iterates over the raw SRT blocks.
- Calculates the explicit timestamp slot duration (`end - start`) for every single subtitle block before generation.
- Passes blocks to a Groq LLM endpoint to natively translate text into Arabic while preserving mathematical SRT cue numbering.
- **LLM Prompt Brief (`meta-llama/llama-4-scout-17b-16e-instruct`)**:
  - *Context*: "You are a senior Arabic dubbing translator. This is professional dubbing translation, NOT subtitle translation."
  - *Input Format*: Chunks are formatted with explicit slot durations per line (e.g., `1. [Slot: 2.45s] The text.`).
  - *Priority 1*: Grammatical Correctness (absolute).
  - *Priority 2*: Natural Phrasing.
  - *Priority 3 (Soft Guideline)*: Target 13–15 syllables per second based on the slot duration, but only if it doesn't break grammar/phrasing. Let the audio assembler handle timing drift.
  - *Pacing Rule*: If the original sentence is very short relative to a long slot duration, preserve the silence rather than stretching the translation.

## Stage 6: Diacritize (`diacritize.py`)
This stage underwent a massive structural overhaul to support advanced grammatical correction:
- **Concatenation**: To preserve context, it merges all translated SRT blocks into a massive string separated by `SPLITMARKERX`.
- **CAMeL Tools**: Processes the monolithic string to generate standard Arabic diacritization logic.
- **LLM Post-Processing**: Passes the CAMeL output back into a strict Groq prompt (`meta-llama/llama-4-scout-17b-16e-instruct`).
- **LLM Prompt Brief**:
  - *Context*: "You are an expert Arabic linguist reviewing diacritized text."
  - *Tasks*: Correct `ه → ة` based on strict Arabic grammar, correct `انّ ↔ انْ` contextual placement, and fix minor grammatical disjoints.
  - *Constraints*: "Do NOT change the underlying meaning, and you MUST keep every `SPLITMARKER` intact."
- **Safety Boundaries**: Validates response length (minimum 50% length requirement) to prevent LLM refusal corruption. Verifies all `SPLITMARKER` tags survive the roundtrip. Analyzes and explicitly logs the mathematical diff of substitutions applied.

## Stage 7: Remerge (`remerge.py`)
- Relies on the `SPLITMARKER` boundaries generated in Stage 6 to reconstruct the perfectly timed Arabic SRT object.

## Stage 8: Resegment (`resegment.py`)
- Mathematically joins fragment phrases and slices overwhelmingly long blocks to optimize the text for text-to-speech cadence parsing.

## Stage 9: Speak (`speak.py`) — The OmniVoice Reversion
The system has been completely reverted from the ElevenLabs REST architecture to the **native, local OmniVoice ML framework**.
- **Model Framework**: Uses `k2-fsa/OmniVoice` mapped to GPU (`torch.float16`).
- **Fixed Warm-up Phrase**: To solve tone-drift and primer bleeding, the system pre-measures the sample length of a fixed phonetic warm-up phrase (`بسم الله`) exactly once at startup. Every segment is generated as `warmup + text`, and the exact pre-calculated sample boundary is mathematically sliced off. This guarantees a clean, bleed-free start with consistent phonetic timbre.
- **Programmatic Comma Splicing**: Bypasses the model's inability to recognize Arabic punctuation by actively splitting the input string on Arabic commas (`،`), running OmniVoice independently on each fragment, and dynamically stitching the arrays back together using a strict 300ms absolute-zero `np.zeros` padding array.
- **Energy Tail Trimming**: Replaces unpredictable array math with a raw energy gate that scans the array backwards and aggressively truncates the audio at the absolute microsecond the signal amplitude drops below `-40dB` for more than `100ms`, destroying hallucinated breaths.
- **Deterministic Seeding**: Calculates an MD5 hash of the semantic text input (`text_hash_int % 999983`) and uses it as the `torch.manual_seed`. This mathematically ensures the exact same text input always maps to the same voice latent space across runs, while varying nicely between unique sentences to avoid OmniVoice tone degradation.
- **Prompt Injection**: Perfectly wires UI inputs (`gender`, `age`, `pitch`, `style`) into explicit OmniVoice comma-separated semantic instructions.

## Stage 10: Assemble (`assemble.py`)
- Moves away from dynamic timeline overlap mixing into **rigid, mathematical slot assembly**.
- **Time Stretching**: Uses `librosa.effects.time_stretch` to dynamically compress audio (up to **1.35x speed**) if OmniVoice's natural speaking pace overruns the available slot before the next subtitle begins.
- **Hard Clamping**: If 1.35x compression still overruns, mathematically truncates the `.wav` array exactly at the slot boundary and applies a clean **30ms linear fade-out** to prevent speaker popping.
- **Silence Padding**: If the OmniVoice segment runs short, calculates the remaining millisecond differential to the next block and pads it with absolute zero-array silence.
- **Guaranteed Output**: The final timeline array length is mathematically locked to exactly `video_duration * sample_rate`, guaranteeing a flawless sync.
