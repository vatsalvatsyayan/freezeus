# LLM Module

Job extraction from HTML using Google Gemini LLM with robust error handling and data normalization.

## 📁 Module Structure

```
src/llm/
├── README.md             # This file
├── __init__.py           # Module exports with lazy loading
├── parsers.py            # JSON parsing and data normalization
├── prompt_loader.py      # Prompt management
├── client.py             # Gemini API client with retry logic
├── extractor.py          # Main extraction orchestration
└── llm_helper.py         # Legacy compatibility wrapper (deprecated)
```

## 🔗 Module Dependencies

```
extractor.py (orchestrator)
    ├── client.py (requires: google-generativeai)
    │   └── prompt_loader.py (no external deps)
    ├── parsers.py (no external deps, optional: json5)
    ├── src.db.supabase_client (optional)
    └── src.db.models (Pydantic validation)
```

## 📄 File Descriptions

### `parsers.py` - JSON Parsing & Normalization
**Purpose**: Robust JSON parsing with error recovery and intelligent data normalization.

**No external dependencies** (optional: json5) - Safe to import for testing.

**Key Functions**:

#### `parse_json_robust(text: str) -> dict`
Multi-strategy JSON parser with fallbacks.

**Strategy Cascade**:
1. **Strict parsing** - Try standard `json.loads()`
2. **Sanitization** - Clean malformed JSON and retry
3. **json5** - Use json5 library for relaxed syntax (if installed)
4. **Brace slicing** - Extract first {...} or [...] and parse

**Example**:
```python
from src.llm.parsers import parse_json_robust

# Handles LLM output with code fences
text = '''
```json
{"jobs": [{"title": "Engineer"}]}
```
'''
data = parse_json_robust(text)  # {"jobs": [{"title": "Engineer"}]}
```

#### `sanitize_json_text(text: str) -> str`
Clean common LLM output issues.

**Fixes**:
- Removes code fences (```json...```)
- Replaces smart quotes (" " → " ")
- Removes trailing commas
- Strips control characters
- Handles HTML entities

#### `normalize_and_dedupe(data: dict) -> Tuple[dict, dict]`
Deduplicate jobs and normalize data.

**Deduplication Strategy**:
1. By `job_url` (exact match)
2. By `requisition_id` or `job_id`
3. By `(title, location)` signature
4. Keeps **richer version** (more non-empty fields)

**Normalization**:
- Canonicalizes seniority fields
- Converts location lists to comma-separated strings
- Removes empty/whitespace-only fields
- Strips whitespace from all strings

**Returns**: `(normalized_data, stats)`

**Example**:
```python
data = {
    "jobs": [
        {"job_url": "https://x.com/job/1", "title": "Engineer", "seniority_level": "Senior"},
        {"job_url": "https://x.com/job/1", "title": "Senior Engineer"},  # Duplicate URL
        {"title": "Designer", "location": ["SF", "NYC"]},  # List → string
    ]
}

result, stats = normalize_and_dedupe(data)
# result["jobs"] = [
#     {"job_url": "https://x.com/job/1", "title": "Engineer",
#      "seniority_level": "Senior", "seniority_bucket": "senior"},
#     {"title": "Designer", "location": "SF, NYC"}
# ]
# stats = {"original": 3, "after_dedupe": 2, "removed": 1}
```

#### `normalize_seniority_fields(job: dict) -> dict`
Map seniority variations to canonical buckets.

**Mapping**:
- "Intern", "Internship" → `intern`
- "Junior", "Entry Level" → `entry`
- "Mid Level", "Intermediate" → `mid`
- "Senior", "Sr" → `senior`
- "Director", "VP" → `director_vp`
- "C-Level", "Executive" → `executive`
- Unknown/missing → `unknown`

**Used By**: `normalize_and_dedupe()`

**Testing**: `tests/unit/test_parsers.py` (34 tests)

---

### `prompt_loader.py` - Prompt Management
**Purpose**: Load and manage LLM extraction prompts.

**No external dependencies** - Safe to import.

**Key Functions**:

#### `load_extraction_prompt(prompt_path: Optional[Path] = None) -> str`
Load prompt from file with fallback to default.

**Search Path**:
1. Custom path (if provided)
2. `configs/llm_extraction_prompt.txt` (default)
3. Hardcoded `DEFAULT_PROMPT` (fallback)

**Example**:
```python
from src.llm.prompt_loader import load_extraction_prompt

# Load from default location
prompt = load_extraction_prompt()

# Load from custom path
prompt = load_extraction_prompt(Path("custom_prompt.txt"))
```

#### `get_default_prompt() -> str`
Get the hardcoded default prompt.

**Prompt Structure**:
```
Extract all job postings from this HTML page.

For each job, return:
- job_url (required)
- title (required)
- company, location, team_or_category
- employment_type, office_or_remote
- seniority_level, seniority_bucket
- date_posted_raw
- any other fields found

Seniority bucket mapping:
[detailed rules for intern/entry/mid/senior/director_vp/executive/unknown]

Return as JSON: {"jobs": [...]}
```

**Testing**: `tests/unit/test_prompt_loader.py` (if created)

---

### `client.py` - Gemini API Client
**Purpose**: Handle all Gemini API interactions with retry logic and error handling.

**Dependencies**: `google-generativeai`, `dotenv`

**Configuration** (from `configs/.env`):
```bash
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=models/gemini-1.5-pro-latest
LLM_MAX_RETRIES=2
LLM_RETRY_BASE_SLEEP=1.6
LLM_VERBOSE=1
```

**Key Functions**:

#### `get_gemini_client(api_key: str = None, model_name: str = None)`
Initialize Gemini client.

**Example**:
```python
from src.llm.client import get_gemini_client

client = get_gemini_client()
# Uses GEMINI_API_KEY and GEMINI_MODEL from .env
```

#### `call_gemini_with_retries(prompt: str, model_name: str = None, generation_config: dict = None, max_retries: int = None, base_sleep: float = None)`
Call Gemini with exponential backoff.

**Retry Strategy**:
- Attempt 1: Immediate
- Attempt 2: Wait 1.6s
- Attempt 3: Wait 3.2s
- ...exponential backoff

**Default Generation Config**:
```python
{
    "temperature": 0.0,  # Deterministic
    "candidate_count": 1,
    "response_mime_type": "application/json"
}
```

**Example**:
```python
from src.llm.client import call_gemini_with_retries

response = call_gemini_with_retries(
    prompt="Extract jobs from: <html>...",
    max_retries=3
)
text = response.text
```

#### `call_gemini(prompt: str, model_name: str = None, temperature: float = 0.0, response_mime_type: str = "application/json")`
Simplified API call wrapper.

**Example**:
```python
from src.llm.client import call_gemini

json_text = call_gemini("Extract jobs from: <html>...")
```

**Testing**: Requires Gemini API key - integration tests only

---

### `extractor.py` - Extraction Orchestration
**Purpose**: Complete extraction pipeline from HTML to validated JSON.

**Dependencies**: `client.py`, `parsers.py`, `prompt_loader.py`, `src.db.*`

**Key Functions**:

#### `extract_jobs_from_html(html_text: str, source_url: str = "", page_title: str = "", model_name: str = None) -> dict`
Extract jobs from HTML string via LLM.

**Pipeline**:
1. Truncate HTML if > `LLM_MAX_HTML_CHARS` (default: 250k)
2. Load extraction prompt
3. Call Gemini API with retry
4. Parse JSON response (robust parsing)
5. If parsing fails, try `_fix_json_via_model()` (second LLM call)
6. Return normalized data

**Returns**:
```python
{
    "source_url": "https://example.com/careers",
    "page_title": "Careers",
    "jobs": [
        {
            "job_url": "https://example.com/jobs/123",
            "title": "Software Engineer",
            "company": "Example Inc",
            ...
        },
        ...
    ],
    "error": "..." # Only if extraction failed
}
```

**Example**:
```python
from src.llm.extractor import extract_jobs_from_html

html = Path("out/example.com/reduced_focus/page.html").read_text()
result = extract_jobs_from_html(
    html_text=html,
    source_url="https://example.com/careers",
    page_title="Careers at Example"
)

print(f"Found {len(result['jobs'])} jobs")
```

#### `extract_one_focus_html(html_path: Path, meta_path: Path, domain: str, supabase_enabled: bool = True) -> Optional[Path]`
Process single HTML file through complete pipeline.

**Pipeline**:
1. Read HTML file
2. Read metadata JSON
3. Extract jobs via `extract_jobs_from_html()`
4. Normalize and dedupe
5. Write JSON output to `llm/` directory
6. If `supabase_enabled`: Insert into database via `src.db.supabase_client.upsert_jobs_for_page()`

**Output Path**: `out/{domain}/llm/{base}.jobs.json`

**Example**:
```python
from pathlib import Path
from src.llm.extractor import extract_one_focus_html

json_path = extract_one_focus_html(
    html_path=Path("out/example.com/reduced_focus/careers__abc123.p001.html"),
    meta_path=Path("out/example.com/meta/careers__abc123.p001.json"),
    domain="example.com",
    supabase_enabled=True  # Write to database
)

print(f"Wrote: {json_path}")
```

#### `extract_all_focus_htmls(domain_dir: Path, supabase_enabled: bool = True) -> List[Path]`
Batch process all HTML files in domain directory.

**Process**:
1. Find all files in `{domain_dir}/reduced_focus/`
2. For each HTML file:
   - Check if `llm/*.jobs.json` already exists (skip if so)
   - Call `extract_one_focus_html()`
3. Return list of written JSON paths

**Example**:
```python
from pathlib import Path
from src.llm.extractor import extract_all_focus_htmls

json_paths = extract_all_focus_htmls(
    domain_dir=Path("out/example.com")
)

print(f"Processed {len(json_paths)} pages")
```

**Testing**: Requires Gemini API - integration tests only

---

### `llm_helper.py` - Legacy Wrapper (DEPRECATED)
**Purpose**: Backwards compatibility only.

**Status**: DEPRECATED - New code should import from specific modules.

Re-exports all functions from:
- `parsers.py`
- `prompt_loader.py`
- `client.py`
- `extractor.py`

---

## 🔄 How Modules Wire Together

### Extraction Flow (Single File)

```
1. Entry Point (extractor.extract_one_focus_html)
   ├── Read HTML file
   ├── Read metadata JSON
   └── Call extract_jobs_from_html()

2. LLM Extraction (extractor.extract_jobs_from_html)
   ├── prompt_loader.load_extraction_prompt()
   ├── Truncate HTML if too large
   ├── client.call_gemini_with_retries(prompt + html)
   │   └── Exponential backoff on failures
   ├── parsers.parse_json_robust(response.text)
   │   └── Multi-strategy parsing with fallbacks
   ├── If parse fails: _fix_json_via_model() (second LLM call)
   └── Return: {"source_url": ..., "jobs": [...]}

3. Normalization (extractor.extract_one_focus_html continues)
   ├── parsers.normalize_and_dedupe(data)
   │   ├── Deduplicate by URL/ID/title+location
   │   ├── normalize_seniority_fields() for each job
   │   └── Clean empty fields, strip whitespace
   └── Return: (normalized_data, stats)

4. Output Writing
   ├── Write JSON to llm/{base}.jobs.json
   └── Log: "Wrote {filename} ({N} jobs, removed {M} dupes)"

5. Database Insertion (if enabled)
   └── src.db.supabase_client.upsert_jobs_for_page()
       ├── Validate with src.db.models.PageData
       ├── For each job: Validate with src.db.models.JobPosting
       ├── Create JobRecord.from_job_posting()
       └── Upsert to Supabase (on conflict: job_url)
```

### Batch Extraction Flow

```
1. Entry Point (extractor.extract_all_focus_htmls)
   └── Find all: {domain_dir}/reduced_focus/*.html

2. For Each HTML File
   ├── Check if llm/{base}.jobs.json exists
   │   └── Skip if already processed
   ├── Find matching meta/{base}.json
   └── Call extract_one_focus_html()
       └── (see single file flow above)

3. Return
   └── List of JSON paths written
```

### Data Flow

```
HTML → Gemini LLM → Raw JSON → Parsed → Normalized → Deduplicated → Validated → Database

1. HTML (from crawler)
   └── out/{domain}/reduced_focus/{base}.{page_id}.html
2. Gemini LLM (client.py)
   └── prompt + html → JSON string
3. Raw JSON (may have errors)
   └── parsers.parse_json_robust()
4. Parsed (dict)
   └── {"jobs": [...]}
5. Normalized (seniority, location, whitespace)
   └── parsers.normalize_and_dedupe()
6. Deduplicated (by URL/ID/signature)
   └── Keeps richer version
7. Validated (Pydantic models)
   └── src.db.models.PageData, JobPosting
8. Database (Supabase)
   └── src.db.supabase_client.upsert_jobs_for_page()
```

## 🧪 Testing Strategy

### Unit Tests (No API Required)
- `parsers.py` → `tests/unit/test_parsers.py` (34 tests)
  - JSON parsing with various malformed inputs
  - Sanitization of LLM output
  - Deduplication logic
  - Seniority field normalization

### Integration Tests (Require Gemini API)
- `client.py`, `extractor.py`
  - Requires `GEMINI_API_KEY` in environment
  - Tests against real API
  - Located in `tests/integration/test_llm_extraction.py` (if created)

### Manual Testing
```bash
# Extract from single file
python -c "
from pathlib import Path
from src.llm.extractor import extract_one_focus_html

extract_one_focus_html(
    Path('out/example.com/reduced_focus/page.html'),
    Path('out/example.com/meta/page.json'),
    'example.com'
)
"

# Batch extract
python -c "
from pathlib import Path
from src.llm.extractor import extract_all_focus_htmls

extract_all_focus_htmls(Path('out/example.com'))
"
```

## 🔧 Configuration

### Environment Variables (`configs/.env`)
```bash
# API Configuration
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=models/gemini-1.5-pro-latest

# Processing Limits
LLM_MAX_HTML_CHARS=250000  # Truncate HTML if larger

# Retry Configuration
LLM_MAX_RETRIES=2          # Number of retries after first attempt
LLM_RETRY_BASE_SLEEP=1.6   # Base delay in seconds (exponential backoff)

# Logging
LLM_VERBOSE=1              # Enable verbose logging (0 to disable)

# Database (optional)
SUPABASE_ENABLED=1         # Enable database writes
SUPABASE_URL=https://...
SUPABASE_KEY=...
```

### Prompt Customization
Edit `configs/llm_extraction_prompt.txt` to customize extraction prompt:
```
Extract all job postings from this HTML page.

[Your custom instructions here...]

Return as JSON: {"jobs": [{"job_url": "...", "title": "...", ...}]}
```

## 🚀 Common Use Cases

### 1. Extract from Single HTML File
```python
from pathlib import Path
from src.llm.extractor import extract_jobs_from_html

html = Path("page.html").read_text()
result = extract_jobs_from_html(
    html_text=html,
    source_url="https://example.com/careers",
    page_title="Careers at Example"
)

print(f"Found {len(result['jobs'])} jobs")
for job in result['jobs']:
    print(f"- {job['title']} at {job.get('company', 'Unknown')}")
```

### 2. Batch Process Crawler Output
```python
from pathlib import Path
from src.llm.extractor import extract_all_focus_htmls

# Process all HTML files for a domain
json_paths = extract_all_focus_htmls(
    domain_dir=Path("out/example.com"),
    supabase_enabled=True  # Write to database
)

print(f"Processed {len(json_paths)} pages")
```

### 3. Process with Custom Prompt
```python
from pathlib import Path
from src.llm.prompt_loader import load_extraction_prompt
from src.llm.extractor import extract_jobs_from_html

# Load custom prompt
prompt = load_extraction_prompt(Path("custom_prompt.txt"))

# Note: extract_jobs_from_html uses default prompt internally
# For custom prompt, use client.call_gemini directly
```

### 4. Parse LLM Output Manually
```python
from src.llm.parsers import parse_json_robust, normalize_and_dedupe

# LLM returned malformed JSON
llm_output = '''
```json
{"jobs": [{"title": "Engineer",}]}  // trailing comma
```
'''

# Parse robustly
data = parse_json_robust(llm_output)  # Succeeds despite errors

# Normalize and dedupe
normalized, stats = normalize_and_dedupe(data)
print(f"Removed {stats['removed']} duplicates")
```

## 📝 Important Functions Reference

### Parsers
| Function | Purpose | Returns |
|----------|---------|---------|
| `parse_json_robust(text)` | Parse JSON with fallbacks | `dict` |
| `sanitize_json_text(text)` | Clean malformed JSON | `str` |
| `normalize_and_dedupe(data)` | Dedupe + normalize | `(dict, dict)` |
| `normalize_seniority_fields(job)` | Map seniority to buckets | `dict` |

### Prompt Loading
| Function | Purpose | Returns |
|----------|---------|---------|
| `load_extraction_prompt(path)` | Load prompt from file | `str` |
| `get_default_prompt()` | Get hardcoded prompt | `str` |

### Client
| Function | Purpose | Returns |
|----------|---------|---------|
| `get_gemini_client(...)` | Initialize client | `GenerativeModel` |
| `call_gemini_with_retries(...)` | API call with retry | `Response` |
| `call_gemini(...)` | Simplified API call | `str` |

### Extractor
| Function | Purpose | Returns |
|----------|---------|---------|
| `extract_jobs_from_html(...)` | Extract from HTML string | `dict` |
| `extract_one_focus_html(...)` | Process single file | `Optional[Path]` |
| `extract_all_focus_htmls(...)` | Batch process directory | `List[Path]` |

## 🐛 Troubleshooting

### Issue: API quota exceeded
**Solution**: Reduce processing rate, increase `LLM_RETRY_BASE_SLEEP`, or upgrade API plan

### Issue: JSON parsing fails
**Check**: `parse_json_robust()` should handle most cases. If still failing, check LLM response in logs

### Issue: No jobs extracted
**Check**:
- Is HTML actually in `reduced_focus` file? (should contain job listings)
- Check `LLM_MAX_HTML_CHARS` - may be truncating too much
- Review extraction prompt - may need customization for site

### Issue: Duplicates in output
**Check**: `normalize_and_dedupe()` should catch this. Check if jobs have unique `job_url` or `requisition_id`

### Issue: Database writes failing
**Check**:
- Pydantic validation errors in logs
- Check `SUPABASE_ENABLED`, `SUPABASE_URL`, `SUPABASE_KEY`
- Verify job data has required fields (`job_url`, `title`)

## 📚 Further Reading

- **Gemini API Docs**: https://ai.google.dev/docs
- **Crawler Module**: `src/crawler/README.md` (for HTML capture)
- **Database Module**: `src/db/README.md` (for data storage)
- **Pydantic Docs**: https://docs.pydantic.dev/ (for validation)
