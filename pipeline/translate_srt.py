"""
Translate SRT

Translates subtitles using an LLM with full-context batched API calls.
"""
import json
import re
import time
from pathlib import Path

from config import GROQ_API_KEY_TRANSLATION, SUPPORTED_LANGUAGES
from utils.logger import pipeline_logger as logger
from utils.srt_utils import SRTEntry, read_srt, write_srt


# ─────────────────────────────────────────────────────────────
# Groq client factory
# ─────────────────────────────────────────────────────────────

# def _get_translation_client():
#     """Create and return a Groq client for translation."""
#     from groq import Groq
#     if not GROQ_API_KEY_TRANSLATION:
#         raise ValueError(
#             "GROQ_API_KEY_TRANSLATION is not set. Add it to your .env file."
#         )
#     return Groq(api_key=GROQ_API_KEY_TRANSLATION)


# # ─────────────────────────────────────────────────────────────
# # Prompts
# # ─────────────────────────────────────────────────────────────

# TRANSLATION_SYSTEM_PROMPT = """You are a senior Arabic dubbing translator with 20 years of experience
# translating Hollywood films and TV shows to Arabic.

# This is professional dubbing translation, NOT subtitle translation.

# PRIORITY ORDER — follow this strictly:
# 1. GRAMMATICAL CORRECTNESS: Arabic grammar, morphology, and agreement rules are absolute. Never break them.
# 2. NATURAL PHRASING: The translation must sound like it was originally written in Arabic — never like a translation.
# 3. TIMING: Each entry has a hard maximum target_words field. Exceeding it causes the dubbed audio to be cut off. Aim for 85-100% of the target. NEVER exceed it. If the original content is too dense to fit, prioritize core meaning and drop minor asides or redundant phrases rather than padding with filler.

# Additional rules:
# - Output Arabic text ONLY — no explanations, no transliteration, no notes, keep the same punctuation marks as the original.

# Gender and number agreement — this is critical for Arabic dubbing:
# - Always match the grammatical gender of the speaker and the person being addressed
# - Male speaker:   أنتَ / ذهبتَ / فعلتَ / قلتَ
# - Female speaker: أنتِ / ذهبتِ / فعلتِ / قلتِ
# - Addressing a male:   أنتَ / افعلْ / قلْ
# - Addressing a female: أنتِ / افعلي / قولي
# - Plural group:   أنتم / ذهبتم / افعلوا
# - Dual (two people): أنتما / ذهبتما
# Noun and adjective agreement:
# - Singular masculine: الرَّجُلُ الطَّوِيلُ
# - Singular feminine:  المَرْأَةُ الطَّوِيلَةُ
# - Plural (non-human): treat as feminine singular for adjective agreement
#   example: الكُتُبُ مُفِيدَةٌ (not مُفِيدُونَ)
# - Sound masculine plural: المُعَلِّمُونَ / المُعَلِّمِينَ
# - Sound feminine plural:  المُعَلِّمَاتُ
# - Broken plural: memorized forms — لا تَقِسْ عَلَى غَيْرِهَا

# How to handle idioms and metaphors:
# How to handle idioms and metaphors:
# - NEVER translate idioms or metaphors word-for-word
# - Find the equivalent Arabic idiom or metaphor that carries the same meaning and feeling
# - If no Arabic equivalent exists, rephrase naturally so it lands the same way on an Arabic ear
# - The emotional impact must be identical to the original — a joke should land as a joke,
#   a threat should feel like a threat, a compliment should feel warm

# Priority order:
# 1. Natural Arabic equivalent idiom or metaphor
# 2. Rephrased Arabic with same emotional meaning
# 3. Literal only if the expression is already universal"""


# # ─────────────────────────────────────────────────────────────
# # Batched translation helpers
# # ─────────────────────────────────────────────────────────────

# # Maximum number of segments per API call.
# # Llama-4-Scout has a 128k context window on Groq, so 200 segments is safe
# # for typical subtitle line lengths while keeping latency low.
# _BATCH_SIZE = 200

# # Regex that matches a numbered response line: "1. text" or "1) text"
# _NUMBERED_LINE_RE = re.compile(r'^\s*(\d+)[.)]\s*(.+)', re.MULTILINE)


# def _build_batch_user_message(segments: list[tuple[int, str, float]], src_name: str, tgt_name: str) -> str:
#     """Format a JSON array of segments for the batch translation prompt."""
#     MIN_TARGET_WORDS = 4
#     duration_budget = 0.85
#     words_per_second = 3.0
    
#     batch_data = []
#     for idx, text, dur in segments:
#         target_words = max(MIN_TARGET_WORDS, round(dur * words_per_second * duration_budget))
#         batch_data.append({"index": idx, "text": text, "target_words": target_words})
        
#     json_str = json.dumps(batch_data, ensure_ascii=False, indent=2)
    
#     return (
#         f"Translate the following {src_name} subtitle segments to {tgt_name}.\n"
#         f"The input is a JSON array of objects. Each object has an index, the text to translate, and a hard target_words limit.\n"
#         f"Return ONLY the translated lines, formatting your output as a numbered list matching the index.\n"
#         f"One numbered line per segment — no extra commentary.\n\n"
#         f"{json_str}"
#     )


# def _parse_batch_response(raw: str, expected_ids: list[int]) -> dict[int, str]:
#     """Parse a numbered LLM response back into a {segment_id: translated_text} dict."""
#     results: dict[int, str] = {}
#     expected_set = set(expected_ids)
#     for match in _NUMBERED_LINE_RE.finditer(raw):
#         idx = int(match.group(1))
#         text = match.group(2).strip()
#         if idx in expected_set and text:
#             results[idx] = text
#     return results


# def _translate_segment(client, segment_text: str, duration: float, src_name: str, tgt_name: str, retries: int = 3) -> str:
#     """Translate a single segment via Groq.

#     Used only as a repair fallback for individual segments that failed
#     during the batched translation pass.
#     Falls back to original text after exhausting retries.
#     """
#     for attempt in range(1, retries + 1):
#         try:
#             MIN_TARGET_WORDS = 4
#             duration_budget = 0.85
#             words_per_second = 3.0
#             target_words = max(MIN_TARGET_WORDS, round(duration * words_per_second * duration_budget))
#             json_str = json.dumps([{"index": 1, "text": segment_text, "target_words": target_words}], ensure_ascii=False)
            
#             response = client.chat.completions.create(
#                 model="meta-llama/llama-4-scout-17b-16e-instruct",
#                 messages=[
#                     {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
#                     {"role": "user", "content": f"Translate the following {src_name} subtitle segment to {tgt_name}.\n\nThe input is a JSON array containing one object.\nReturn ONLY the translated line.\n\n{json_str}"},
#                 ],
#                 temperature=0.2,
#                 max_tokens=1024,
#             )
#             result = response.choices[0].message.content.strip()
#             if result:
#                 return result
#             logger.warning(f"  ⚠️  Empty translation on attempt {attempt}, retrying…")
#         except Exception as e:
#             logger.warning(f"  ⚠️  Translation attempt {attempt} failed: {e}")
#             if attempt < retries:
#                 time.sleep(2 ** attempt)

#     logger.error(f"  ❌ Translation failed after {retries} attempts for: {segment_text[:60]}…")
#     return segment_text  # fallback: return original text


# def _translate_batch(
#     client,
#     segments: list[tuple[int, str]],
#     src_name: str,
#     tgt_name: str,
#     retries: int = 3,
# ) -> dict[int, str]:
#     """Send a numbered batch of segments in a single API call.

#     Returns a dict of {original_1based_index: translated_text}.
#     On parse failure or count mismatch, returns whatever was successfully parsed
#     so the caller can identify and repair missing entries individually.
#     """
#     expected_ids = [idx for idx, _, _ in segments]
#     user_message = _build_batch_user_message(segments, src_name, tgt_name)
#     max_out = min(8192, max(1024, sum(len(t) for _, t, _ in segments) * 3))

#     last_raw = ""
#     for attempt in range(1, retries + 1):
#         try:
#             response = client.chat.completions.create(
#                 model="meta-llama/llama-4-scout-17b-16e-instruct",
#                 messages=[
#                     {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
#                     {"role": "user", "content": user_message},
#                 ],
#                 temperature=0.2,
#                 max_tokens=max_out,
#             )
#             last_raw = response.choices[0].message.content or ""
#             parsed = _parse_batch_response(last_raw, expected_ids)

#             missing = [i for i in expected_ids if i not in parsed]
#             if not missing:
#                 return parsed  # perfect match

#             logger.warning(
#                 f"  ⚠️  Batch attempt {attempt}: parsed {len(parsed)}/{len(expected_ids)} segments. "
#                 f"Missing IDs: {missing[:10]}{'…' if len(missing) > 10 else ''}"
#             )
#             if attempt < retries:
#                 time.sleep(2 ** attempt)

#         except Exception as e:
#             logger.warning(f"  ⚠️  Batch translation attempt {attempt} failed: {e}")
#             if attempt < retries:
#                 time.sleep(2 ** attempt)

#     return _parse_batch_response(last_raw, expected_ids)


# def _translate_all_segments(client, entries, src_name: str, tgt_name: str) -> None:
#     """Translate all SRT entries in place using batched API calls.

#     Strategy:
#     1. Split entries into chunks of _BATCH_SIZE and translate each chunk
#        in a single API call (full context within the chunk).
#     2. Collect any segments missing from the parsed response.
#     3. Repair each missing segment individually via _translate_segment().

#     Results are written directly to entry.translated on each SRTEntry.
#     """
#     indexed: list[tuple[int, str, float]] = [
#         (i + 1, entry.text, entry.end - entry.start) for i, entry in enumerate(entries)
#     ]

#     translations: dict[int, str] = {}
#     total_batches = (len(indexed) + _BATCH_SIZE - 1) // _BATCH_SIZE

#     # ── Batched pass ──
#     for batch_num, start in enumerate(range(0, len(indexed), _BATCH_SIZE), 1):
#         chunk = indexed[start: start + _BATCH_SIZE]
#         logger.info(
#             f"  📦 Translating batch {batch_num}/{total_batches} "
#             f"({len(chunk)} segments, IDs {chunk[0][0]}–{chunk[-1][0]})…"
#         )
#         batch_result = _translate_batch(client, chunk, src_name, tgt_name)
#         translations.update(batch_result)
#         logger.info(
#             f"  ✅ Batch {batch_num}/{total_batches} done — "
#             f"{len(batch_result)}/{len(chunk)} segments translated."
#         )

#     # ── Repair pass for any missing segments ──
#     missing_ids = [idx for idx, _, _ in indexed if idx not in translations]
#     if missing_ids:
#         logger.warning(
#             f"  🔧 Repair pass: re-translating {len(missing_ids)} missing segment(s) individually…"
#         )
#         for idx in missing_ids:
#             original_text = indexed[idx - 1][1]
#             dur = indexed[idx - 1][2]
#             logger.info(f"    Repairing segment {idx}: {original_text[:60]}…")
#             translations[idx] = _translate_segment(client, original_text, dur, src_name, tgt_name)

#     # ── Write results back to entries ──
#     MIN_TARGET_WORDS = 4
#     duration_budget = 0.85
#     words_per_second = 3.0
    
#     for i, entry in enumerate(entries):
#         translated_text = translations.get(i + 1, entry.text)
#         entry.translated = translated_text
        
#         slot_dur = entry.end - entry.start
#         actual_words = len(translated_text.split())
#         target_words = max(MIN_TARGET_WORDS, round(slot_dur * words_per_second * duration_budget))
        
#         if actual_words > target_words * 1.5:
#             logger.warning(
#                 f"  ⚠️  Segment {i+1} word count ({actual_words}) exceeds target ({target_words}) "
#                 f"by >1.5x. This will be handled by timeline assembly."
#             )
            
#         logger.info(f"  🗣️  [Slot: {slot_dur:.2f}s | Target Words: {target_words} | Actual: {actual_words}] {translated_text}")


# ─────────────────────────────────────────────────────────────
# Arabic-specific: Unified Gemini Translation + Diacritization
# ─────────────────────────────────────────────────────────────

_GEMINI_MODEL = "gemini-3.1-flash-lite"
_CONTEXT_BEFORE = 2
_CONTEXT_AFTER = 2

_ARABIC_SYSTEM_PROMPT = """
You are a world-class English-to-Arabic dubbing translator and Arabic linguist.

You will receive one TARGET subtitle together with nearby subtitles that provide context.

The surrounding subtitles are ONLY for understanding the dialogue.
Translate ONLY the TARGET subtitle.

Requirements:

- Produce natural spoken Arabic suitable for professional dubbing.
- Never translate literally when a natural Arabic expression exists.
- Translate the intended meaning, emotion, and tone.
- Rewrite idioms and colloquial expressions naturally.
- Make the dialogue sound as if it was originally written in Arabic.

Use the surrounding context to determine:
- who is speaking
- who is being addressed
- whether "you" refers to one person or multiple people
- masculine/feminine agreement
- pronoun references
- tense
- emotional tone
- recurring terminology

Adapt the translation naturally for dubbing:
- Preserve the speaker's personality and emotions.
- Keep the dialogue smooth and easy to perform aloud.
- Prefer expressions commonly heard in Egyptian speech.
- Keep the translation reasonably close in length to the original for lip-sync and dubbing.

Arabic writing requirements:

- Fully add Arabic diacritics (tashkeel) to every Arabic word.
- Apply diacritics accurately.
- Do NOT omit tanween where grammatically appropriate.
- Correctly apply shadda, sukoon, long vowels, and hamzat al-waṣl/qaṭ'.
- Ensure grammatical agreement is correct.

Formatting:

- Preserve punctuation.
- Preserve commas.
- Preserve question marks.
- Preserve exclamation marks.
- Preserve ellipses.
- Preserve quotation marks.
- Preserve parentheses.
- Preserve numbers.

Do not translate proper names unless they have a well-established Arabic form.

Output ONLY the translated TARGET subtitle.

Do not explain.
Do not add notes.
Do not output English.
Do not use quotation marks around the translation.
"""


def _build_gemini_context(index, english_lines, arabic_lines):
    """Build a context prompt with previous Arabic translations and upcoming English lines."""
    prompt = []

    start = max(0, index - _CONTEXT_BEFORE)
    for i in range(start, index):
        if arabic_lines[i]:
            prompt.append(f"[PREVIOUS]\n{arabic_lines[i]}")

    prompt.append(f"[TARGET]\n{english_lines[index]}")

    end = min(len(english_lines), index + _CONTEXT_AFTER + 1)
    for i in range(index + 1, end):
        if english_lines[i]:
            prompt.append(f"[NEXT]\n{english_lines[i]}")

    return "\n\n".join(prompt)


def _translate_and_diacritize_single(client, context, retries=5):
    """Translate a single subtitle line via Gemini with exponential backoff retry."""
    from google.genai import types
    import random

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=_GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=_ARABIC_SYSTEM_PROMPT,
                    temperature=0.25
                ),
                contents=context
            )
            return response.text.strip()

        except Exception as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"  ⚠️  Retry {attempt+1}/{retries} — waiting {wait:.1f}s: {e}")
            time.sleep(wait)

    return "[TRANSLATION FAILED]"


def _translate_arabic_gemini(entries):
    """Translate all SRT entries to Arabic with diacritization using Google Gemini.

    Processes entries sequentially with a sliding context window so each
    translation can reference the previous Arabic output and upcoming English lines.
    """
    import os
    from google import genai
    from config import GOOGLE_API_KEY

    if not GOOGLE_API_KEY:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )

    client = genai.Client(api_key=GOOGLE_API_KEY)

    english_lines = [entry.text for entry in entries]
    arabic_lines = []

    for i, line in enumerate(english_lines):
        if not line.strip():
            arabic_lines.append("")
            entries[i].translated = ""
            continue

        context = _build_gemini_context(i, english_lines, arabic_lines)
        translated = _translate_and_diacritize_single(client, context)
        arabic_lines.append(translated)

        entries[i].translated = translated

        logger.info(f"  [{i+1}/{len(english_lines)}]")
        logger.info(f"  EN: {line}")
        logger.info(f"  AR: {translated}")
        logger.info(f"  {'-' * 60}")

        time.sleep(4)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def translate_srt(
    srt_path: str,
    output_path: str,
    source_lang: str,
    target_lang: str,
) -> dict:
    """
    Translates the SRT file.

    Args:
        srt_path:    Input SRT (from ASR)
        output_path: Where to write the translated SRT
        source_lang: ISO-639-1 source code
        target_lang: ISO-639-1 target code

    Returns:
        dict: srt_path, full_translated_text, entry_count
    """
    src_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
    tgt_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

    logger.info(f"🌍 Translating: {src_name} → {tgt_name}")

    # ── Same-language shortcut ──
    if source_lang == target_lang:
        logger.info(f"⏭️  Source and target are the same ({source_lang}). Skipping translation.")
        entries = read_srt(srt_path)
        for entry in entries:
            entry.translated = entry.text
        write_srt(entries, output_path, use_translated=True)
        full_text = " ".join(e.text for e in entries if e.text)
        return {
            "srt_path": output_path,
            "full_translated_text": full_text,
            "entry_count": len(entries),
        }

    # ── Read ASR segments ──
    entries = read_srt(srt_path)
    if not entries:
        raise ValueError("SRT file is empty")

    # ── Arabic: unified Gemini translation + diacritization ──
    if target_lang == "ar":
        logger.info(
            f"✨ Translating {len(entries)} segments to Arabic via Gemini ({_GEMINI_MODEL}) "
            f"with context-aware sequential translation + diacritization…"
        )
        _translate_arabic_gemini(entries)
    else:
        # ── All other languages: Groq batched translation ──
        translation_client = _get_translation_client()

        logger.info(
            f"✨ Translating {len(entries)} segments via Groq (meta-llama/llama-4-scout-17b-16e-instruct) "
            f"in batches of up to {_BATCH_SIZE}…"
        )
        _translate_all_segments(translation_client, entries, src_name, tgt_name)

    # ── Validate: no empty translations ──
    empty_translations = [
        i + 1 for i, e in enumerate(entries)
        if not e.translated or not e.translated.strip()
    ]
    if empty_translations:
        logger.error(
            f"  ❌ {len(empty_translations)} segment(s) returned empty after translation: "
            f"indices {empty_translations}"
        )
        raise RuntimeError(
            f"Translation produced empty results for {len(empty_translations)} segment(s). "
            f"Segment indices (1-based): {empty_translations}"
        )
    logger.info("  ✅ Translation validation passed — no empty segments.")

    # ── Write output ──
    full_translated_text = " ".join(e.translated for e in entries if e.translated)
    write_srt(entries, output_path, use_translated=True)

    logger.info(f"✅ Translation complete — {len(entries)} cues translated")

    return {
        "srt_path": output_path,
        "full_translated_text": full_translated_text,
        "entry_count": len(entries),
    }
