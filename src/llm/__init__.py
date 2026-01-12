"""
LLM module for job extraction from HTML using Google Gemini.

This module provides functionality for extracting job listings from HTML
using LLM-based parsing with robust error handling and data normalization.

Module Structure:
- parsers: JSON parsing and data normalization
- prompt_loader: Prompt management
- client: Gemini API interactions
- extractor: Job extraction orchestration
- llm_helper: Legacy compatibility wrapper (deprecated)
"""

# Export parser functions directly - these don't require Gemini
from src.llm.parsers import (
    parse_json_robust,
    sanitize_json_text,
    normalize_and_dedupe,
    normalize_seniority_fields,
)

# Export prompt functions - no Gemini dependency
from src.llm.prompt_loader import (
    load_extraction_prompt,
    get_default_prompt,
)

# Lazy import for functions that require Gemini
# This allows tests to import parsers without installing google-generativeai
def __getattr__(name):
    """Lazy loading for Gemini-dependent functions."""
    if name in ("extract_one_focus_html", "extract_all_focus_htmls", "extract_jobs_from_html"):
        from src.llm.extractor import (
            extract_one_focus_html,
            extract_all_focus_htmls,
            extract_jobs_from_html,
        )
        if name == "extract_one_focus_html":
            return extract_one_focus_html
        elif name == "extract_all_focus_htmls":
            return extract_all_focus_htmls
        else:
            return extract_jobs_from_html

    if name in ("get_gemini_client", "call_gemini_with_retries", "call_gemini"):
        from src.llm.client import (
            get_gemini_client,
            call_gemini_with_retries,
            call_gemini,
        )
        if name == "get_gemini_client":
            return get_gemini_client
        elif name == "call_gemini_with_retries":
            return call_gemini_with_retries
        else:
            return call_gemini

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Parser functions (no Gemini dependency)
    "parse_json_robust",
    "sanitize_json_text",
    "normalize_and_dedupe",
    "normalize_seniority_fields",
    # Prompt functions (no Gemini dependency)
    "load_extraction_prompt",
    "get_default_prompt",
    # Extraction functions (require Gemini - lazy loaded)
    "extract_one_focus_html",
    "extract_all_focus_htmls",
    "extract_jobs_from_html",
    # Client functions (require Gemini - lazy loaded)
    "get_gemini_client",
    "call_gemini_with_retries",
    "call_gemini",
]
