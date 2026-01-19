# Seal

Job aggregation backend that crawls company career pages, extracts structured job data using LLM, and stores results in PostgreSQL.

## What It Does

1. **Crawls** career pages using Playwright (handles SPAs, pagination, infinite scroll)
2. **Reduces** HTML to minimize LLM token costs (~80% reduction)
3. **Extracts** job data using Google Gemini 1.5 Pro
4. **Validates** with Pydantic and stores in Supabase
5. **Runs** every 6 hours via GitHub Actions

**Stack:** Python 3.13 · Playwright · Gemini API · Supabase · Pydantic

---

## Architecture

```
configs/urls.txt (30+ company URLs)
        │
        ▼
┌───────────────────────────────────────────────────┐
│  CRAWLER (src/crawler/)                           │
│  Playwright browser automation                    │
│  • Navigate & render JavaScript                   │
│  • Handle pagination + infinite scroll            │
│  • Save 3 HTML versions (full, reduced, lite)     │
└───────────────────────────────────────────────────┘
        │
        ▼  out/<domain>/reduced_focus/*.html
┌───────────────────────────────────────────────────┐
│  LLM EXTRACTOR (src/llm/)                         │
│  Google Gemini 1.5 Pro                            │
│  • Parse JSON robustly (4 fallback strategies)    │
│  • Normalize & deduplicate jobs                   │
│  • Validate with Pydantic                         │
└───────────────────────────────────────────────────┘
        │
        ▼  Structured job data
┌───────────────────────────────────────────────────┐
│  DATABASE (src/db/)                               │
│  Supabase (PostgreSQL)                            │
│  • Upsert with conflict resolution                │
│  • Preserve first_seen_at, update last_seen_at    │
└───────────────────────────────────────────────────┘
```

### Module Dependencies

```
src/core/           Config + logging (shared)
    │
    ├── src/crawler/    Web scraping with Playwright
    ├── src/llm/        LLM extraction with Gemini
    └── src/db/         Database operations
```

---

## Project Structure

```
seal/
├── src/
│   ├── crawler/          # Web scraping
│   │   ├── multi_capture.py   # Main entry point
│   │   ├── navigation.py      # Browser interactions
│   │   ├── page_analyzer.py   # Progress detection
│   │   ├── file_manager.py    # File I/O
│   │   ├── url_utils.py       # URL parsing
│   │   └── reducers.py        # HTML reduction JS
│   │
│   ├── llm/              # LLM extraction
│   │   ├── extractor.py       # Orchestration
│   │   ├── client.py          # Gemini API client
│   │   ├── parsers.py         # JSON parsing
│   │   └── prompt_loader.py   # Prompt management
│   │
│   ├── db/               # Database
│   │   ├── supabase_client.py # DB operations
│   │   └── models.py          # Pydantic models
│   │
│   └── core/             # Shared
│       ├── config.py          # Environment vars
│       └── logging.py         # Structured logging
│
├── configs/
│   ├── .env                   # Secrets (gitignored)
│   ├── .env.example           # Template
│   ├── urls.txt               # URLs to crawl
│   └── llm_extraction_prompt.txt
│
├── tests/
│   ├── unit/                  # 148+ tests
│   └── integration/
│
├── out/                  # Output (gitignored)
│   └── <domain>/
│       ├── full/              # Complete HTML
│       ├── reduced_focus/     # For LLM (~100KB)
│       ├── reduced_lite/      # Scripts stripped
│       ├── meta/              # Metadata JSON
│       ├── signals/           # Reduction scores
│       └── llm/               # Extracted jobs
│
└── .github/workflows/
    └── crawler.yml            # Scheduled automation
```

---

## Setup

### Requirements

- Python 3.13+
- Google Gemini API key
- Supabase account (optional)

### Installation

```bash
# Clone and enter directory
git clone https://github.com/vatsalvatsyayan/seal.git
cd seal

# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Install Playwright browser
playwright install chromium

# Configure environment
cp configs/.env.example configs/.env
# Edit configs/.env with your API keys
```

### Configuration

Edit `configs/.env`:

```bash
# Required
GEMINI_API_KEY=your-api-key

# Optional (Supabase)
SUPABASE_ENABLED=1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-key

# Crawler settings
NAV_TIMEOUT_MS=45000
PER_DOMAIN_DELAY_MIN=8
PER_DOMAIN_DELAY_MAX=15

# LLM settings
LLM_MAX_HTML_CHARS=250000
LLM_MAX_RETRIES=2
```

---

## Usage

### Basic Crawl

```bash
# Crawl and save HTML only
python -m src.crawler.multi_capture --urls configs/urls.txt

# Crawl + LLM extraction
python -m src.crawler.multi_capture --urls configs/urls.txt --with-llm

# Headless mode (CI/automation)
python -m src.crawler.multi_capture --urls configs/urls.txt --headless --with-llm
```

### Options

```bash
python -m src.crawler.multi_capture \
  --urls configs/urls.txt \
  --with-llm \
  --headless \
  --jobs-max 150 \      # Stop after N jobs per seed
  --pages-max 5 \       # Max pagination pages
  --time-budget 120     # Expansion phase timeout (seconds)
```

### Tests

```bash
# All tests
pytest

# Unit tests only (fast, no external deps)
pytest tests/unit/ -v

# With coverage
pytest --cov=src --cov-report=html
```

---

## How It Works

### 1. Crawling

The crawler handles three pagination patterns:

- **Numbered pagination** - Clicks "Next" buttons, saves p001, p002, p003...
- **Infinite scroll** - Scrolls to trigger lazy loading
- **Load more buttons** - Clicks "Show More" / "Load More"

Progress detection uses SHA1 fingerprints of job URLs to detect when new content loads.

### 2. HTML Reduction

Three versions saved per page:

| Version | Size | Purpose |
|---------|------|---------|
| `full` | ~500KB | Archive, debugging |
| `reduced_focus` | ~100KB | LLM input (job containers only) |
| `reduced_lite` | ~50KB | Scripts/styles stripped |

The reduction algorithm scores containers by job-relevance (presence of job links, repetition patterns, content density) and keeps the highest-scoring ones.

### 3. LLM Extraction

The JSON parser handles malformed LLM responses with 4 fallback strategies:

1. Direct `json.loads()`
2. Strip markdown code fences
3. Regex extraction
4. Line-by-line recovery

### 4. Database

Upsert logic:
- **Conflict key:** `job_url`
- **Preserved:** `first_seen_at` (never updated)
- **Updated:** `last_seen_at` (every crawl)

---

## Output

After crawling, `out/<domain>/` contains:

```
out/example.com/
├── full/
│   ├── careers__a1b2c3d4.p001.html
│   ├── careers__a1b2c3d4.expanded.html
│   └── careers__a1b2c3d4.p002.html
├── reduced_focus/
│   └── ...
├── reduced_lite/
│   └── ...
├── meta/
│   └── careers__a1b2c3d4.p001.json    # {title, url, sha1, ts}
├── signals/
│   └── careers__a1b2c3d4.p001.json    # Reduction scores
├── llm/
│   └── careers__a1b2c3d4.p001.jobs.json
└── careers__a1b2c3d4.manifest.json    # Crawl summary
```

---

## Database Schema

`jobs_raw` table:

| Column | Type | Description |
|--------|------|-------------|
| `job_url` | text (PK) | Unique job URL |
| `title` | text | Job title |
| `company` | text | Company name |
| `location` | text | Job location |
| `country` | text | Country |
| `seniority_bucket` | enum | intern/entry/mid/senior/director_vp/executive/unknown |
| `employment_type` | text | Full-time, Part-time, etc. |
| `office_or_remote` | text | Office, Remote, Hybrid |
| `first_seen_at` | timestamp | First time job was seen |
| `last_seen_at` | timestamp | Last time job was seen |
| `source_domain` | text | Source website domain |
| `raw_job` | jsonb | Full extracted data |

---

## CI/CD

GitHub Actions workflow (`.github/workflows/crawler.yml`):

- **Schedule:** Every 6 hours
- **Parallel execution:** Splits URLs into chunks of 5
- **Secrets:** `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## Costs

Approximate per crawl (30 companies, ~100 pages):

| Item | Cost |
|------|------|
| LLM input (~10MB HTML) | ~$0.10 |
| LLM output (~1MB JSON) | ~$0.05 |
| **Total per crawl** | ~$0.15 |

Running 4x daily = ~$18/month

---

## Troubleshooting

**Playwright import error**
```bash
pip install playwright
playwright install chromium
```

**Gemini rate limits (429)**
- Built-in exponential backoff handles this
- Increase `LLM_RETRY_BASE_SLEEP` if persistent

**Supabase connection fails**
- Check `.env` has correct URL and key
- Or disable: `SUPABASE_ENABLED=0`

**No jobs extracted**
- Check `out/<domain>/reduced_focus/` - is it job listings?
- Check `signals/` - are job links detected?
- Increase `time_budget` for more scrolling

---

## Module Documentation

- [src/crawler/README.md](src/crawler/README.md) - Web crawler
- [src/llm/README.md](src/llm/README.md) - LLM extraction
- [src/db/README.md](src/db/README.md) - Database operations
- [src/core/README.md](src/core/README.md) - Configuration and logging

---

## License

Private and proprietary.

---

## Author

Vatsal Vatsyayan - [@vatsalvatsyayan](https://github.com/vatsalvatsyayan)
