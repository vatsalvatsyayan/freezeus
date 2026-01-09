"""
LLM module for job extraction from HTML using Google Gemini.

This module provides functionality for extracting job listings from HTML
using LLM-based parsing with robust error handling and data normalization.
"""

# Export parser functions directly - these don't require Gemini
from src.llm.parsers import (
    parse_json_robust,
    sanitize_json_text,
    normalize_and_dedupe,
    normalize_seniority_fields,
)

# Lazy import for functions that require Gemini
# This allows tests to import parsers without installing google-generativeai
def __getattr__(name):
    """Lazy loading for llm_helper functions."""
    if name in ("extract_one_focus_html", "extract_all_focus_htmls"):
        from src.llm.llm_helper import extract_one_focus_html, extract_all_focus_htmls
        return extract_one_focus_html if name == "extract_one_focus_html" else extract_all_focus_htmls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "parse_json_robust",
    "sanitize_json_text",
    "normalize_and_dedupe",
    "normalize_seniority_fields",
    "extract_one_focus_html",
    "extract_all_focus_htmls",
]
