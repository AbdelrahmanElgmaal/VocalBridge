"""
Stage 3.5 — Diacritize

Diacritizes translated Arabic SRT segments using CAMeL Tools BERT.
"""
import os
import re
import gc
from typing import List
from groq import Groq
from utils.logger import pipeline_logger as logger
from utils.srt_utils import SRTEntry, read_srt, write_srt

# def diacritize_srt(srt_path: str, output_path: str) -> dict:
#     """
#     Diacritize the Arabic SRT using CAMeL Tools BERT tagger.
#     The model is lazy-loaded and deleted from RAM afterward.
#     """
#     logger.info("🪄  Diacritizing Arabic subtitles with CAMeL Tools (BERT)…")
    
#     entries = read_srt(srt_path)
#     if not entries:
#         raise ValueError("SRT file is empty")

#     logger.info("🔄 Lazy loading BERTUnfactoredDisambiguator (this may take a moment)…")
#     try:
#         from camel_tools.disambig.bert import BERTUnfactoredDisambiguator
#         from camel_tools.tagger.default import DefaultTagger
        
#         # Initialize models
#         bert = BERTUnfactoredDisambiguator.pretrained('msa')
#         tagger = DefaultTagger(bert, 'diac')
#         logger.info("✅ Model loaded successfully.")
#     except Exception as e:
#         logger.error(f"❌ Failed to load CAMeL Tools model: {e}")
#         raise

#     # Tag each segment independently
#     diacritized_segments = []
    
#     logger.info(f"✨ Tagging {len(entries)} segments independently to prevent attention bleed…")
#     for i, entry in enumerate(entries):
#         text = entry.translated if entry.translated else entry.text
#         words = text.split()
        
#         if words:
#             # Tag purely Arabic, short sequences without fake marker words
#             diac_words = tagger.tag(words)
#             diacritized_segments.append(" ".join(diac_words))
#         else:
#             diacritized_segments.append("")

#     # Reconstruct the marker stream for the LLM batch call
#     raw_text_with_markers = ""
#     for i, seg in enumerate(diacritized_segments):
#         if i > 0:
#             raw_text_with_markers += f" SPLITMARKER{i} "
#         raw_text_with_markers += seg
    
#     # --- LLM Post-Processing ---
#     logger.info("🧠 Passing diacritized text to LLM for grammatical corrections…")
#     try:
#         client = Groq(api_key=os.environ.get("GROQ_API_KEY_check", os.environ.get("GROQ_API_KEY")))
#         prompt = (
#             "You are an Arabic text corrector. You will receive diacritized Arabic text. Perform exactly two corrections:\n"
#             "1. For every word ending in ه, check if it should be ة based on Arabic grammar and context. If yes, replace ه with ة.\n"
#             "2. For every occurrence of انّ or انْ, determine which is grammatically correct in context and replace with the correct form.\n"
#             "Make no other changes whatsoever. Output only the corrected text, nothing else.\n"
#             "The text contains SPLITMARKER tags (e.g. SPLITMARKER1, SPLITMARKER2). Leave all SPLITMARKER tags completely unchanged in your output."
#         )
#         res = client.chat.completions.create(
#             model="meta-llama/llama-4-scout-17b-16e-instruct",
#             messages=[
#                 {"role": "system", "content": prompt},
#                 {"role": "user", "content": raw_text_with_markers}
#             ],
#             temperature=0.0,
#             max_tokens=8000
#         )
#         corrected_text = res.choices[0].message.content.strip()
        
#         # 1. Log the raw response
#         logger.info(f"📝 Raw Groq LLM Response:\n{corrected_text}\n{'-'*40}")
        
#         # 2. Validate response length
#         if len(corrected_text) < 0.5 * len(raw_text_with_markers):
#             logger.warning(f"⚠️ LLM response too short ({len(corrected_text)} chars vs {len(raw_text_with_markers)} chars). Likely a refusal. Falling back.")
#             corrected_text = raw_text_with_markers
            
#         # 3. Check SPLITMARKER tags survived
#         missing_markers = []
#         for i in range(1, len(entries)):
#             if f"SPLITMARKER{i}" not in corrected_text:
#                 missing_markers.append(i)
                
#         if missing_markers:
#             logger.error(f"❌ LLM destroyed {len(missing_markers)} SPLITMARKER tags (e.g. {missing_markers[:3]}). Falling back.")
#             corrected_text = raw_text_with_markers
            
#         # 5. Diff log
#         if corrected_text != raw_text_with_markers:
#             diff_h = max(0, corrected_text.count('ة') - raw_text_with_markers.count('ة'))
#             diff_in = abs(corrected_text.count('انّ') - raw_text_with_markers.count('انّ')) + abs(corrected_text.count('انْ') - raw_text_with_markers.count('انْ'))
#             # divide by 2 because one goes up, one goes down
#             diff_in = diff_in // 2 
#             logger.info(f"📊 LLM Corrections Applied: [ه → ة]: ~{diff_h} | [انّ ↔ انْ]: ~{diff_in}")
#         else:
#             logger.info("📊 LLM made exactly 0 substitutions.")
            
#     except Exception as e:
#         # 4. Check API key and rate limits
#         logger.warning(f"⚠️ LLM correction failed (HTTP/Auth/API Error): {type(e).__name__}: {e}")
#         logger.warning("Falling back to raw diacritized text.")
#         corrected_text = raw_text_with_markers

#     # Recover individual segments using regex split on SPLITMARKERs
#     # The string is: seg0 SPLITMARKER1 seg1 SPLITMARKER2 seg2 ...
#     segments = re.split(r'\s*SPLITMARKER\d+\s*', corrected_text)
    
#     if len(segments) != len(entries):
#         logger.warning(f"⚠️ Marker mismatch after LLM! Expected {len(entries)} segments, got {len(segments)}. Recovering best effort.")
#         # Fallback to token zip if regex fails horribly
#         corrected_text = raw_text_with_markers
#         segments = re.split(r'\s*SPLITMARKER\d+\s*', corrected_text)
        
#     for i, seg_text in enumerate(segments):
#         if i < len(entries):
#             clean_seg = seg_text.strip()
#             entries[i].translated = clean_seg
#             entries[i].text = clean_seg

#     # Write output
#     write_srt(entries, output_path, use_translated=True)
    
#     # We strip out any stray markers just in case for the full text return
#     full_diacritized_text = " ".join(e.text for e in entries if e.text)

#     # Clean up RAM immediately
#     logger.info("🧹 Unloading model and freeing RAM…")
#     del tagger
#     del bert
#     gc.collect()

#     logger.info(f"✅ Diacritization complete — {len(entries)} cues processed.")
    
#     return {
#         "srt_path": output_path,
#         "full_translated_text": full_diacritized_text,
#         "entry_count": len(entries),
#    }
