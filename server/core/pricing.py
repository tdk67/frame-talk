"""
Pricing & Cost Estimation Model for Google Gemini Models
Provides transparent calculation for token expenditure and pre-flight estimation.
"""

from typing import Dict, Any

# Gemini 3.7 Flash Pricing (USD per 1,000,000 tokens)
GEMINI_FLASH_INPUT_PER_M = 0.15    # $0.15 / 1M input tokens
GEMINI_FLASH_OUTPUT_PER_M = 0.60   # $0.60 / 1M output tokens

# Gemini 3.1 Flash TTS Preview Pricing (USD per 1,000 characters)
GEMINI_TTS_PER_1K_CHARS = 0.015    # $0.015 / 1,000 characters

# Video token density (Gemini standard: 258 tokens per second at 1 FPS)
VIDEO_TOKENS_PER_SECOND = 258

def calculate_llm_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates dollar cost for a given LLM model invocation."""
    m = model_name.lower()
    if "tts" in m:
        # For TTS, completion_tokens represents synthesized characters
        chars = completion_tokens or prompt_tokens
        return round((chars / 1000.0) * GEMINI_TTS_PER_1K_CHARS, 6)
    
    # Standard Gemini 3.7 / 2.0 Flash
    cost_in = (prompt_tokens / 1_000_000.0) * GEMINI_FLASH_INPUT_PER_M
    cost_out = (completion_tokens / 1_000_000.0) * GEMINI_FLASH_OUTPUT_PER_M
    return round(cost_in + cost_out, 6)

def estimate_pipeline_cost(video_duration_sec: float, readme_chars: int = 5000) -> Dict[str, Any]:
    """
    Computes a realistic pre-flight cost and token estimation for a complete
    Frame Talk production run (Ingestion + Scriptwriting + QA + TTS Synthesis).
    """
    dur_sec = max(10.0, float(video_duration_sec))
    chars = max(100, int(readme_chars))

    # 1. Stage 1: Ingestion (Gemini 3.7 Flash Video Token Analysis)
    ONE_M = 1_000_000.0
    video_tokens = int(dur_sec * VIDEO_TOKENS_PER_SECOND)
    readme_tokens = int(chars / 4)
    ingest_prompt_tokens = video_tokens + readme_tokens + 800  # System instructions
    ingest_completion_tokens = 1400  # Structured scene breakdown
    ingest_cost = (ingest_prompt_tokens / ONE_M) * GEMINI_FLASH_INPUT_PER_M + \
                  (ingest_completion_tokens / ONE_M) * GEMINI_FLASH_OUTPUT_PER_M

    # 2. Stage 2: Scriptwriter (Alex & Sam Dialogue Generation)
    # Speech target: ~2.5 words per second of video
    est_spoken_words = int(dur_sec * 2.5)
    script_output_tokens = int(est_spoken_words * 1.35)
    script_input_tokens = ingest_completion_tokens + readme_tokens + 1000
    script_cost = (script_input_tokens / ONE_M) * GEMINI_FLASH_INPUT_PER_M + \
                  (script_output_tokens / ONE_M) * GEMINI_FLASH_OUTPUT_PER_M

    # 3. Stage 3: QA Auditor (Forensic Grounding & Pacing Verification)
    qa_input_tokens = ingest_completion_tokens + script_output_tokens + 800
    qa_output_tokens = 450
    qa_cost = (qa_input_tokens / ONE_M) * GEMINI_FLASH_INPUT_PER_M + \
              (qa_output_tokens / ONE_M) * GEMINI_FLASH_OUTPUT_PER_M

    # 4. Stage 4: Speech Synthesis (Gemini 3.1 Flash TTS Preview)
    est_tts_chars = int(est_spoken_words * 5.5)
    tts_cost = (est_tts_chars / 1000.0) * GEMINI_TTS_PER_1K_CHARS

    total_tokens = (ingest_prompt_tokens + ingest_completion_tokens +
                    script_input_tokens + script_output_tokens +
                    qa_input_tokens + qa_output_tokens)
    total_cost_usd = round(ingest_cost + script_cost + qa_cost + tts_cost, 4)

    return {
        "video_duration_sec": round(dur_sec, 1),
        "readme_chars": chars,
        "stages": {
            "vision_ingest": {
                "model": "gemini-3.7-flash",
                "estimated_tokens": ingest_prompt_tokens + ingest_completion_tokens,
                "cost_usd": round(ingest_cost, 4)
            },
            "scriptwriter": {
                "model": "gemini-3.7-flash",
                "estimated_tokens": script_input_tokens + script_output_tokens,
                "cost_usd": round(script_cost, 4)
            },
            "qa_auditor": {
                "model": "gemini-3.7-flash",
                "estimated_tokens": qa_input_tokens + qa_output_tokens,
                "cost_usd": round(qa_cost, 4)
            },
            "tts_synthesis": {
                "model": "gemini-3.1-flash-tts-preview",
                "estimated_chars": est_tts_chars,
                "cost_usd": round(tts_cost, 4)
            }
        },
        "total_estimated_tokens": total_tokens,
        "total_estimated_chars": est_tts_chars,
        "total_estimated_cost_usd": max(0.01, total_cost_usd),
        "formatted_cost": f"${max(0.01, total_cost_usd):.3f} USD"
    }
