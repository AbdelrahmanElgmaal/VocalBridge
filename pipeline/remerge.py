"""
Stage 1.5 — Remerge

Merges fragmented Whisper segments into complete, natural sentences using purely deterministic rules.
Zero API calls.
"""
from typing import List

from utils.logger import pipeline_logger as logger
from utils.srt_utils import SRTEntry, read_srt, write_srt

def remerge_srt(srt_path: str, output_path: str, video_duration: float = None):
    logger.info("🧩 Remerging fragmented transcript (Deterministic Rule-Based)...")
    entries = read_srt(srt_path)
    if not entries:
        write_srt(entries, output_path)
        return
        
    output_groups = []
    
    current_start = None
    current_end = None
    accumulated_text = ""
    
    conjunctions = ["و", "أو", "ثم", "لكن", "but", "and"]
    punct_marks = ['.', '؟', '!', '،']
    sentence_enders = ('.', '؟', '!')
    
    for entry in entries:
        if current_start is None:
            current_start = entry.start
        current_end = entry.end
        
        if accumulated_text:
            accumulated_text += " " + entry.text.strip()
        else:
            accumulated_text = entry.text.strip()
            
        if accumulated_text.endswith(sentence_enders):
            words = accumulated_text.split()
            last_word = words[-1].strip(".,?!،;:'\"")
            if last_word in conjunctions:
                # Ends with conjunction, keep accumulating
                continue
            else:
                # Valid sentence end
                output_groups.append((accumulated_text, current_start, current_end))
                current_start = None
                current_end = None
                accumulated_text = ""
        elif len(accumulated_text) > 104:
            # Recursively split if over 104 chars
            while len(accumulated_text) > 104:
                split_idx = -1
                for i in range(103, -1, -1):
                    if accumulated_text[i] in punct_marks:
                        split_idx = i
                        break
                        
                if split_idx == -1:
                    split_idx = 103 # Force hard split if no punctuation found
                    logger.warning(f"  ⚠️ Text exceeds 104 chars with no punctuation. Forcing hard split.")
                
                text_1 = accumulated_text[:split_idx+1].strip()
                text_2 = accumulated_text[split_idx+1:].strip()
                
                ratio = len(text_1) / len(accumulated_text)
                mid_time = current_start + (current_end - current_start) * ratio
                
                output_groups.append((text_1, current_start, mid_time))
                
                current_start = mid_time
                accumulated_text = text_2

    # Close any remaining text
    if accumulated_text and current_start is not None:
        output_groups.append((accumulated_text, current_start, current_end))
        
    if video_duration and output_groups:
        last_text, last_start, last_end = output_groups[-1]
        if last_end > video_duration:
            logger.warning(f"  ⚠️ Clamping final group end time from {last_end:.2f}s to video duration {video_duration:.2f}s")
            output_groups[-1] = (last_text, last_start, video_duration)
            
    final_entries: List[SRTEntry] = []
    for idx, (text, start, end) in enumerate(output_groups):
        final_entries.append(SRTEntry(
            index=idx + 1,
            start=start,
            end=end,
            text=text
        ))
        
    write_srt(final_entries, output_path)
    logger.info(f"✅ Remerged {len(entries)} segments into {len(final_entries)} deterministic groups.")
