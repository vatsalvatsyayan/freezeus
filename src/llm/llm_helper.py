"""
LLM helper module (legacy compatibility wrapper).

This module now serves as a compatibility wrapper, re-exporting functions
from the refactored LLM module structure. All new code should import directly
from the specific modules:
- src.llm.parsers: JSON parsing and data normalization
- src.llm.prompt_loader: Prompt management
- src.llm.client: Gemini API interactions
- src.llm.extractor: Job extraction orchestration

DEPRECATED: This file is maintained for backwards compatibility only.
It will be removed in a future version.
"""

# Re-export main extraction functions
from src.llm.extractor import (
    extract_one_focus_html,
    extract_all_focus_htmls,
    extract_jobs_from_html,
)

# Re-export parser functions (for backwards compatibility)
from src.llm.parsers import (
    parse_json_robust,
    sanitize_json_text,
    normalize_and_dedupe,
    normalize_seniority_fields,
)

# Re-export prompt functions
from src.llm.prompt_loader import (
    load_extraction_prompt,
    get_default_prompt,
)

# Re-export client functions
from src.llm.client import (
    get_gemini_client,
    call_gemini_with_retries,
    call_gemini,
)

__all__ = [
    # Extraction functions
    "extract_one_focus_html",
    "extract_all_focus_htmls",
    "extract_jobs_from_html",
    # Parser functions
    "parse_json_robust",
    "sanitize_json_text",
    "normalize_and_dedupe",
    "normalize_seniority_fields",
    # Prompt functions
    "load_extraction_prompt",
    "get_default_prompt",
    # Client functions
    "get_gemini_client",
    "call_gemini_with_retries",
    "call_gemini",
]
