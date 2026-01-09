# LLM Module

This module handles job extraction from HTML using Google Gemini LLM.

## Structure

```
src/llm/
├── __init__.py           # Module exports with lazy loading
├── README.md             # This file
├── parsers.py            # JSON parsing and data normalization
├── prompt_loader.py      # Prompt management
├── client.py             # Gemini API client with retry logic
├── extractor.py          # Main extraction orchestration
└── llm_helper.py         # Legacy compatibility wrapper (deprecated)
```

## Components

### parsers.py
Handles JSON parsing with robust error recovery and data normalization:
- `parse_json_robust()` - Multi-strategy JSON parser (strict → sanitize → json5 → brace-slice)
- `sanitize_json_text()` - Clean malformed JSON (code fences, smart quotes, trailing commas)
- `normalize_and_dedupe()` - Deduplicate jobs by URL/requisition_id/title+location
- `normalize_seniority_fields()` - Map seniority variations to canonical buckets
- Helper functions: `_strip_ws()`, `_richness_score()`, `_canon_loc()`, `_sig()`, `_omit_empty()`

**Key Features:**
- No external dependencies (except optional json5)
- Handles common LLM output issues (code fences, smart quotes, control chars)
- Intelligent deduplication keeps richer job version
- 34 unit tests with 100% coverage

### prompt_loader.py
Manages extraction prompts:
- `load_extraction_prompt()` - Load from configs/llm_extraction_prompt.txt with fallback
- `get_default_prompt()` - Get default prompt template
- `DEFAULT_PROMPT` - Full extraction prompt with seniority inference rules

**Key Features:**
- Configurable prompt from file
- Graceful fallback to hardcoded default
- Detailed seniority bucket instructions for LLM

### client.py
Gemini API client with retry logic:
- `get_gemini_client()` - Initialize and configure Gemini client
- `call_gemini_with_retries()` - API call with exponential backoff
- `call_gemini()` - Simplified API call wrapper
- Configuration from environment variables

**Key Features:**
- Exponential backoff retry (configurable via LLM_MAX_RETRIES, LLM_RETRY_BASE_SLEEP)
- Structured logging of API calls and errors
- Temperature and response format configuration
- Environment-based model selection

### extractor.py
Main extraction orchestration:
- `extract_jobs_from_html()` - Extract jobs from HTML text via LLM
- `extract_one_focus_html()` - Process single HTML file (read → extract → normalize → write → DB)
- `extract_all_focus_htmls()` - Batch process directory of HTML files
- `_fix_json_via_model()` - Second-chance JSON repair via LLM

**Key Features:**
- Complete extraction pipeline: HTML → LLM → JSON → Normalize → Dedupe → Write → Supabase
- URL normalization and validation
- HTML truncation for large pages
- JSON repair fallback
- Optional Supabase database integration
- Comprehensive error handling (never raises, always writes output)

### llm_helper.py (DEPRECATED)
Legacy compatibility wrapper that re-exports all functions from the new modules.
Maintained for backwards compatibility only. New code should import directly from:
- `src.llm.parsers`
- `src.llm.prompt_loader`
- `src.llm.client`
- `src.llm.extractor`

## Usage

```python
from src.llm import extract_jobs_from_html, extract_all_focus_htmls

# Extract from single HTML file
result = extract_jobs_from_html(
    html_path=Path("out/domain/reduced_focus/page.html"),
    meta_path=Path("out/domain/meta/page.json"),
    domain="example.com"
)

# Batch extract from directory
json_paths = extract_all_focus_htmls(
    domain_dir=Path("out/example.com")
)
```

## Configuration

Set in `configs/.env`:
```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=models/gemini-1.5-pro-latest
LLM_MAX_HTML_CHARS=250000
LLM_MAX_RETRIES=2
LLM_VERBOSE=1
```

## Testing

```bash
# Run LLM module tests
pytest tests/unit/test_parsers.py
pytest tests/unit/test_prompt_loader.py
pytest tests/integration/test_llm_extraction.py
```
