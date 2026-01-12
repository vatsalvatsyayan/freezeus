# Database Module

Pydantic models and Supabase client for type-safe job data storage with automatic validation.

## 📁 Module Structure

```
src/db/
├── README.md            # This file
├── __init__.py          # Module exports
├── models.py            # Pydantic models for validation
└── supabase_client.py   # Database operations
```

## 🔗 Module Dependencies

```
supabase_client.py
    └── models.py (Pydantic validation)
        └── pydantic (external dependency)
```

## 📄 File Descriptions

### `models.py` - Pydantic Models
**Purpose**: Type-safe data models with automatic validation.

**Models**:

#### `JobExtra` - Flexible extra fields
```python
JobExtra(
    job_description="...",
    weekly_hours=40,
    apply_url="...",
    # Allows any additional fields
)
```

#### `JobPosting` - Core job data with validation
```python
JobPosting(
    job_url="https://example.com/jobs/123",  # Required, min length 1
    title="Software Engineer",                # Required
    company="Example Inc",                    # Optional
    location="San Francisco, CA",            # String or list
    seniority_bucket="mid",                  # Validated to allowed values
   # ... more fields
)
```

**Validation**:
- `job_url` must not be empty
- `seniority_bucket` normalized to: intern/entry/mid/senior/director_vp/executive/unknown
- `location` list converted to comma-separated string
- Whitespace automatically stripped

#### `JobRecord` - Complete database record
```python
JobRecord(
    # All JobPosting fields plus:
    first_seen_at="2026-01-08T12:00:00Z",
    last_seen_at="2026-01-08T12:00:00Z",
    source_domain="example.com",
    source_page_url="...",
    source_page_title="...",
    raw_extra={...},
    raw_job={...}
)
```

**Factory Method**:
```python
record = JobRecord.from_job_posting(
    job=job_posting,
    domain="example.com",
    source_url="https://example.com/careers",
    page_title="Careers"
)
```

#### `PageData` - Page validation
```python
page = PageData(
    source_url="...",
    page_title="...",
    jobs=[{...}, {...}]
)

# Validate all jobs
validated_jobs = page.validate_jobs()  # Returns List[JobPosting]
```

**Testing**: `tests/unit/test_db_models.py` (26 tests)

---

### `supabase_client.py` - Database Operations
**Purpose**: Supabase database operations with Pydantic validation.

**Configuration** (`configs/.env`):
```bash
SUPABASE_ENABLED=1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-api-key
SUPABASE_JOBS_TABLE=jobs_raw
```

**Key Functions**:

#### `upsert_jobs_for_page(cleaned_page: dict, domain: str) -> None`
Insert/update jobs from LLM extraction.

**Flow**:
1. Validate page data with `PageData` model
2. For each job:
   - Validate with `JobPosting` model
   - Check if exists (preserve `first_seen_at`)
   - Create `JobRecord.from_job_posting()`
   - Normalize to dict
3. Batch upsert (conflict on `job_url`)

**Features**:
- Skips invalid jobs (logs validation errors)
- Preserves `first_seen_at` for existing jobs
- Updates `last_seen_at` on every crawl
- Returns counts (inserted/skipped/validation errors)

**Example**:
```python
from src.db.supabase_client import upsert_jobs_for_page

page_data = {
    "source_url": "https://example.com/careers",
    "page_title": "Careers",
    "jobs": [
        {"job_url": "...", "title": "Engineer", ...},
        # ... more jobs
    ]
}

upsert_jobs_for_page(page_data, "example.com")
```

#### `is_supabase_enabled() -> bool`
Check if Supabase is configured and enabled.

## 🔄 How Modules Wire Together

### Data Flow

```
LLM Extraction → Pydantic Validation → Database Upsert

1. LLM extracts jobs
   └── src.llm.extractor.extract_one_focus_html()

2. Validate page data
   └── models.PageData(**cleaned_page)

3. For each job
   ├── models.JobPosting(**job_dict)  # Validate
   ├── Check if exists in database
   └── models.JobRecord.from_job_posting()  # Convert to DB record

4. Batch upsert
   └── supabase_client.upsert_jobs_for_page()
```

### Validation Example

```python
# Invalid job (caught by Pydantic)
try:
    job = JobPosting(job_url="", title="Test")
except ValidationError as e:
    print(e)  # "String should have at least 1 character"

# Valid job with normalization
job = JobPosting(
    job_url="  https://example.com/jobs/123  ",  # Whitespace stripped
    title="Engineer",
    location=["SF", "NYC"],  # Converted to "SF, NYC"
    seniority_bucket="invalid"  # Normalized to "unknown"
)
```

## 🧪 Testing

**Unit Tests**: `tests/unit/test_db_models.py` (26 tests)
- Model creation and validation
- Field normalization
- Serialization/deserialization
- Factory methods

**Run Tests**:
```bash
pytest tests/unit/test_db_models.py -v
```

## 🔧 Configuration

### Required Environment Variables
```bash
SUPABASE_ENABLED=1                          # Enable database
SUPABASE_URL=https://xxx.supabase.co       # Your project URL
SUPABASE_KEY=eyJhbGc...                     # API key (anon/service)
SUPABASE_JOBS_TABLE=jobs_raw               # Table name
```

### Database Schema
```sql
CREATE TABLE jobs_raw (
    job_url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    country TEXT DEFAULT 'Unknown',
    seniority_level TEXT DEFAULT 'Unknown',
    seniority_bucket TEXT DEFAULT 'unknown',
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ NOT NULL,
    source_domain TEXT NOT NULL,
    source_page_url TEXT,
    source_page_title TEXT,
    raw_extra JSONB,
    raw_job JSONB,
    -- ... more fields
);
```

## 📝 Important Models Reference

| Model | Purpose | Required Fields |
|-------|---------|-----------------|
| `JobPosting` | Job with validation | `job_url`, `title` |
| `JobRecord` | DB record | All JobPosting + timestamps + source |
| `PageData` | Page validation | `source_url`, `page_title`, `jobs` |
| `JobExtra` | Flexible fields | None |

## 🐛 Troubleshooting

### Issue: Validation errors
**Check**: Review error message, fix data format. Common issues:
- Empty `job_url` or `title`
- Invalid `seniority_bucket` value (auto-fixed to "unknown")

### Issue: Database connection fails
**Check**: `SUPABASE_URL` and `SUPABASE_KEY` in `.env`

### Issue: Jobs not inserting
**Check**: Enable `LLM_VERBOSE=1` to see validation errors in logs

## 📚 Further Reading

- **Pydantic Docs**: https://docs.pydantic.dev/
- **Supabase Python Client**: https://github.com/supabase-community/supabase-py
- **LLM Module**: `src/llm/README.md` (for data extraction)
