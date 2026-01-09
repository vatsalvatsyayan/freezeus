# LLM Module

This module handles job extraction from HTML using Google Gemini LLM.

## Structure

```
src/llm/
├── __init__.py           # Module exports
├── README.md             # This file
├── parsers.py            # JSON parsing and data cleaning
├── prompt_loader.py      # Prompt management
├── client.py             # Gemini API client
└── extractor.py          # Main extraction orchestration
```

## Components

### parsers.py
Handles JSON parsing with robust error recovery:
- `parse_json_robust()` - Parse JSON with fallback strategies
- `sanitize_json_text()` - Clean malformed JSON text
- `normalize_and_dedupe()` - Deduplicate and normalize job data
- Helper functions for data cleaning

### prompt_loader.py
Manages extraction prompts:
- `load_extraction_prompt()` - Load from file with fallback
- `get_default_prompt()` - Default prompt template

### client.py
Gemini API client:
- `get_gemini_client()` - Initialize Gemini client
- `call_gemini()` - Make API calls with retry logic
- Configuration from environment

### extractor.py
Main extraction logic:
- `extract_jobs_from_html()` - Extract jobs from single HTML file
- `extract_all_focus_htmls()` - Batch process multiple HTML files
- Orchestrates prompt, LLM, parsing, and database

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
