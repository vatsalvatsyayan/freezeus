# Freezeus - Job Aggregation Backend

Production-grade job board crawler and extraction system that automatically scrapes career pages, extracts structured job data using LLM, and stores results in a database.

## 🚀 What This System Does

1. **Crawls** company career pages using Playwright with anti-bot detection
2. **Reduces** HTML intelligently to minimize LLM processing costs
3. **Extracts** structured job data using Google Gemini 1.5 Pro
4. **Validates** and normalizes job listings with Pydantic
5. **Stores** data in Supabase (PostgreSQL) with automatic upsert logic
6. **Runs** automatically every 6 hours via GitHub Actions

**Tech Stack**: Python 3.13 • Playwright • Google Gemini API • Supabase • Pydantic • Pytest

---

## 📁 Project Structure

```
freezeus/
├── src/                      # Source code
│   ├── crawler/              # Web scraping with Playwright
│   ├── llm/                  # LLM extraction with Gemini
│   ├── db/                   # Database models and operations
│   └── core/                 # Configuration and logging
│
├── tests/                    # Test suite (148 tests)
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
│
├── configs/                  # Configuration files
│   ├── .env                  # Environment variables (not in git)
│   ├── .env.example          # Template for environment variables
│   ├── urls.txt              # List of URLs to crawl
│   └── llm_extraction_prompt.txt  # Gemini extraction prompt
│
├── out/                      # Crawl output (gitignored)
│   └── <domain>/             # Per-domain subdirectories
│       ├── full/             # Complete HTML snapshots
│       ├── reduced_focus/    # Job-focused HTML reduction
│       ├── reduced_lite/     # Minimal HTML (scripts stripped)
│       ├── meta/             # Page metadata (JSON)
│       ├── signals/          # Reduction scoring signals
│       └── llm/              # Extracted job data (JSON)
│
├── scripts/                  # Utility scripts
│   └── crawl.sh              # Run crawler in headed mode
│
├── docs/                     # Additional documentation
│   └── analysis/             # Architecture analysis
│
└── logs/                     # Application logs
```

---

## 🏗️ System Architecture

### High-Level Data Flow

```
URLs (configs/urls.txt)
    ↓
┌─────────────────────────────────────────────────────────┐
│ 1. CRAWLER (src/crawler/)                               │
│    • Playwright browser automation                      │
│    • Multi-page capture (pagination + infinite scroll)  │
│    • HTML reduction (3 versions saved)                  │
└─────────────────────────────────────────────────────────┘
    ↓ HTML files saved to out/<domain>/
┌─────────────────────────────────────────────────────────┐
│ 2. LLM EXTRACTION (src/llm/)                            │
│    • Load reduced_focus HTML                            │
│    • Send to Gemini 1.5 Pro                             │
│    • Parse JSON response (multi-strategy)               │
│    • Validate with Pydantic                             │
└─────────────────────────────────────────────────────────┘
    ↓ JSON jobs data
┌─────────────────────────────────────────────────────────┐
│ 3. DATABASE (src/db/)                                   │
│    • Pydantic validation & normalization                │
│    • Upsert to Supabase (preserve first_seen_at)        │
│    • Track job lifecycle (first/last seen timestamps)   │
└─────────────────────────────────────────────────────────┘
    ↓
📊 Supabase Database (jobs_raw table)
```

### Module Dependencies

```
src/core/  (Config + Logging)
    ↓
    ├─→ src/crawler/  (Web scraping)
    ├─→ src/llm/      (LLM extraction)
    └─→ src/db/       (Database operations)

External Dependencies:
    • playwright (browser automation)
    • google-generativeai (Gemini API)
    • supabase-py (database client)
    • pydantic (data validation)
```

---

## 📚 Module Documentation

Each module has comprehensive documentation explaining its structure, purpose, and usage:

- **[src/crawler/README.md](src/crawler/README.md)** - Multi-site web crawler with pagination and infinite scroll support
- **[src/llm/README.md](src/llm/README.md)** - LLM job extraction using Google Gemini with robust parsing
- **[src/db/README.md](src/db/README.md)** - Pydantic models and Supabase database operations
- **[src/core/README.md](src/core/README.md)** - Configuration management and structured logging

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.13+
- Google Gemini API key
- Supabase account (optional, for database storage)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/vatsalvatsyayan/freezeus.git
   cd freezeus
   ```

2. **Create virtual environment**
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For testing
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Configure environment variables**
   ```bash
   cp configs/.env.example configs/.env
   # Edit configs/.env with your API keys
   ```

6. **Configure URLs to crawl**
   ```bash
   # Edit configs/urls.txt - one URL per line
   # Example:
   # https://example.com/careers
   # https://another.com/jobs
   ```

### Environment Configuration

Edit `configs/.env` with your settings:

```bash
# === Required ===
GEMINI_API_KEY=your-api-key-here

# === Optional (Supabase) ===
SUPABASE_ENABLED=1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# === Crawler Settings ===
MAX_RETRIES=3
NAV_TIMEOUT_MS=45000
PER_DOMAIN_DELAY_MIN=8
PER_DOMAIN_DELAY_MAX=15

# === LLM Settings ===
LLM_MAX_HTML_CHARS=250000
LLM_MAX_RETRIES=2
LLM_VERBOSE=1
```

See [configs/.env.example](configs/.env.example) for full documentation.

---

## 🚀 Usage

### Running the Crawler

**Basic crawl** (saves HTML only):
```bash
python -m src.crawler.multi_capture --urls configs/urls.txt
```

**Crawl with LLM extraction**:
```bash
python -m src.crawler.multi_capture --urls configs/urls.txt --with-llm
```

**Headless mode** (for CI/automation):
```bash
python -m src.crawler.multi_capture --urls configs/urls.txt --headless --with-llm
```

**Custom parameters**:
```bash
python -m src.crawler.multi_capture \
  --urls configs/urls.txt \
  --with-llm \
  --jobs-max 150 \
  --pages-max 5 \
  --time-budget 120
```

### Running LLM Extraction Only

If you already have crawled HTML and want to extract jobs:

```bash
python -c "
from pathlib import Path
from src.llm.llm_helper import extract_all_focus_htmls

# Extract from all reduced_focus HTMLs for a domain
domain_dir = Path('out/example.com')
json_paths = extract_all_focus_htmls(domain_dir)
print(f'Extracted {len(json_paths)} job files')
"
```

### Running Tests

**All tests**:
```bash
pytest
```

**Specific module**:
```bash
pytest tests/unit/test_crawler_url_utils.py -v
pytest tests/unit/test_llm_parsers.py -v
pytest tests/unit/test_db_models.py -v
```

**With coverage**:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 📊 Output Structure

After running the crawler, you'll find organized output in `out/<domain>/`:

```
out/example.com/
├── full/
│   ├── careers__a1b2c3d4.p001.html       # Initial page load
│   ├── careers__a1b2c3d4.expanded.html   # After load-more/scroll
│   ├── careers__a1b2c3d4.p002.html       # Page 2
│   └── careers__a1b2c3d4.p003.html       # Page 3
│
├── reduced_focus/                         # Job-focused reduction (for LLM)
│   ├── careers__a1b2c3d4.p001.html
│   └── ...
│
├── reduced_lite/                          # Minimal HTML (scripts stripped)
│   ├── careers__a1b2c3d4.p001.html
│   └── ...
│
├── meta/                                  # Page metadata
│   ├── careers__a1b2c3d4.p001.json       # {title, url, sha1, timestamps}
│   └── ...
│
├── signals/                               # Reduction scoring
│   ├── careers__a1b2c3d4.p001.json       # [{score, hasJobLinks, ...}]
│   └── ...
│
├── llm/                                   # Extracted jobs (if --with-llm)
│   ├── careers__a1b2c3d4.p001.jobs.json  # [{title, company, location, ...}]
│   └── ...
│
└── careers__a1b2c3d4.manifest.json       # Crawl summary
```

### Manifest File Structure

```json
{
  "seed_base": "careers__a1b2c3d4",
  "mode": "pagination",
  "stop_reason": "pages_cap",
  "pages": [
    {
      "page_id": "p001",
      "files": {
        "full": "out/example.com/full/careers__a1b2c3d4.p001.html",
        "focus": "out/example.com/reduced_focus/careers__a1b2c3d4.p001.html",
        ...
      },
      "counts": {
        "unique_jobs": 25,
        "list_len": 25
      },
      "ts": 1704729600
    },
    ...
  ],
  "config": {
    "jobs_max": 100,
    "pages_max": 3,
    ...
  },
  "ts": 1704729650
}
```

---

## 🧪 Testing Strategy

**Current Test Coverage**: 148 tests passing

### Test Organization

```
tests/
├── unit/                              # Unit tests (no external dependencies)
│   ├── test_crawler_url_utils.py     # 37 tests - URL parsing, normalization
│   ├── test_llm_parsers.py           # 34 tests - JSON parsing strategies
│   └── test_db_models.py             # 26 tests - Pydantic validation
│
└── integration/                       # Integration tests (require APIs)
    ├── test_crawler_integration.py    # Playwright browser tests
    ├── test_llm_integration.py        # Gemini API tests
    └── test_db_integration.py         # Supabase database tests
```

### Unit Tests (No Dependencies)

Run without any external services:
```bash
pytest tests/unit/ -v
```

These test:
- URL parsing and canonicalization
- JSON parsing with multiple fallback strategies
- Pydantic model validation and normalization
- Configuration loading
- Logging setup

### Integration Tests (Require Services)

Run with Playwright, Gemini API, Supabase:
```bash
pytest tests/integration/ -v
```

These test:
- End-to-end crawling workflow
- LLM extraction with real API calls
- Database upsert operations
- Error handling and retries

---

## 🔧 Key Features

### 1. Intelligent HTML Reduction

The crawler saves **3 versions** of each page to optimize for different use cases:

| Version | Purpose | Size | Use Case |
|---------|---------|------|----------|
| **full** | Complete HTML | ~500KB | Archive, debugging |
| **reduced_focus** | Job-focused containers | ~100KB | LLM extraction (cost optimization) |
| **reduced_lite** | Scripts/styles stripped | ~50KB | Manual review, testing |

Reduction uses smart scoring to keep containers with high job link density.

### 2. Multi-Page Capture Strategy

**Handles 3 pagination patterns**:
1. **Numbered pagination** (p001, p002, p003...) - Click "Next" buttons
2. **Infinite scroll** (expanded) - Scroll down to trigger lazy loading
3. **Load More buttons** (expanded) - Click "Show More" / "Load More"

**Progress detection**:
- SHA1 fingerprinting of job URLs
- Unique job count tracking
- First/last job URL comparison
- Scroll height monitoring

### 3. Robust JSON Parsing

LLM responses can be messy. The parser uses **4 fallback strategies**:

1. **Direct JSON parse** - Try standard `json.loads()`
2. **Extract from markdown** - Strip ```json code fences
3. **Regex extraction** - Find JSON object/array with regex
4. **Line-by-line recovery** - Parse each line as JSON object

This ensures >99% successful extraction even with malformed responses.

### 4. Type-Safe Data Pipeline

**Pydantic models enforce validation** at every step:

```
Raw LLM JSON → JobPosting model → Validation → JobRecord → Database
                    ↓
                Catches errors:
                • Missing required fields
                • Invalid URLs
                • Type mismatches
                • Normalization (seniority, location)
```

### 5. Smart Database Upserts

**Conflict resolution** on `job_url`:
- **Preserve** `first_seen_at` from existing records
- **Update** `last_seen_at` on every crawl
- **Merge** extra fields without overwriting
- **Track** job lifecycle (first posted vs last seen)

### 6. Anti-Bot Detection

**Crawler mimics real users**:
- Random user agents from pool
- Random viewport sizes
- Natural mouse scrolling
- Random delays between actions
- Session state persistence
- Disabled automation flags

---

## 🐛 Troubleshooting

### Issue: Import errors with Playwright

**Symptoms**: `ModuleNotFoundError: No module named 'playwright'`

**Solution**:
```bash
pip install playwright
playwright install chromium
```

### Issue: Gemini API rate limits

**Symptoms**: `429 Too Many Requests` or `ResourceExhausted`

**Solution**:
- The system has built-in exponential backoff retry
- Increase `LLM_RETRY_BASE_SLEEP` in `.env`
- Reduce batch size (process fewer domains at once)
- Use `LLM_VERBOSE=1` to see retry attempts

### Issue: Supabase connection fails

**Symptoms**: `ValueError: SUPABASE_URL is required`

**Solution**:
- Check `.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Or disable: `SUPABASE_ENABLED=0`
- Verify Supabase project is active and accessible

### Issue: No jobs extracted from page

**Symptoms**: LLM returns empty job list `{"jobs": []}`

**Solution**:
- Check `out/<domain>/reduced_focus/` - is HTML actually job listings?
- Page may require JavaScript or be behind login
- Try increasing `time_budget` for more scrolling
- Check `signals/` JSON - are job links detected?

### Issue: Tests failing

**Symptoms**: Import errors or test failures

**Solution**:
```bash
# Unit tests should work without external dependencies
pytest tests/unit/ -v

# Integration tests need services configured
# Check .env has required API keys
pytest tests/integration/ -v
```

---

## 🔐 Security & Best Practices

### Environment Variables

- **Never commit** `.env` to git (already in `.gitignore`)
- Use **service role key** for Supabase (not anon key)
- Rotate API keys periodically
- Use separate keys for dev/prod

### Rate Limiting

- Respect `robots.txt` (not enforced by default, add if needed)
- Use `PER_DOMAIN_DELAY_MIN/MAX` for politeness
- Don't hammer sites - default is 8-15 seconds between seeds
- GitHub Actions runs every 6 hours (see `.github/workflows/`)

### Data Privacy

- Scrape only **public** career pages
- Don't scrape personal data or applicant information
- Store only job posting metadata (titles, descriptions, URLs)

---

## 📈 Performance & Costs

### Crawling Performance

- **~13 companies** crawled in ~10-15 minutes
- **3-5 pages** per company (initial + pagination)
- **25-100 jobs** extracted per company
- **HTML reduction** cuts LLM costs by ~80% (500KB → 100KB)

### LLM API Costs (Gemini 1.5 Pro)

**Approximate costs per crawl** (13 companies, 50 pages total):
- Input: ~50 pages × 100KB = 5MB HTML → ~$0.10
- Output: ~1000 jobs × 500 chars = 500KB JSON → $0.05
- **Total: ~$0.15 per full crawl**

Running every 6 hours = 4× daily = **~$0.60/day** or **~$18/month**

### Optimization Tips

- Use `LLM_MAX_HTML_CHARS` to cap input size
- HTML reduction already saves ~80% on input tokens
- Batch processing amortizes API overhead
- Cache crawled HTML to re-run LLM without re-crawling

---

## 🤝 Contributing

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Write docstrings for public APIs
- Keep functions focused (single responsibility)

### Testing Requirements

- Write unit tests for new utility functions
- Add integration tests for end-to-end flows
- Ensure tests pass: `pytest`
- Maintain >80% coverage for critical paths

### Pull Request Process

1. Create a feature branch
2. Add tests for new functionality
3. Update relevant README files
4. Ensure all tests pass
5. Submit PR with clear description

---

## 📝 Additional Documentation

- **[docs/analysis/ARCHITECTURE.md](docs/analysis/ARCHITECTURE.md)** - Detailed system architecture
- **[docs/refactoring-plan.md](docs/refactoring-plan.md)** - Refactoring milestones
- **[tests/README.md](tests/README.md)** - Testing documentation
- **[configs/.env.example](configs/.env.example)** - Configuration reference

---

## 📄 License

This project is private and proprietary. Unauthorized use is prohibited.

---

## 👤 Author

**Vatsal Vatsyayan**
- GitHub: [@vatsalvatsyayan](https://github.com/vatsalvatsyayan)

---

## 🔄 Changelog

### Recent Updates

**2026-01-08**: Comprehensive refactoring and documentation
- ✅ Modularized codebase into `crawler/`, `llm/`, `db/`, `core/`
- ✅ Added 148 unit and integration tests
- ✅ Created comprehensive README for each module
- ✅ Implemented lazy loading for optional dependencies
- ✅ Improved error handling and retry logic

**Previous**: Initial implementation
- Multi-site crawler with Playwright
- LLM extraction with Gemini
- Supabase database integration
- GitHub Actions automation

---

## ❓ FAQ

**Q: Can I crawl sites that require login?**
A: Not out of the box. You'd need to implement authentication in the crawler module. The system persists session state (`_storage_state.json`) per domain, so cookies are preserved.

**Q: What if a site changes its HTML structure?**
A: The crawler uses generic selectors (`[role='listitem']`, `a[href*='/jobs/']`) that work across many sites. For site-specific issues, you may need to adjust selectors in `src/crawler/page_analyzer.py`.

**Q: Can I use a different LLM (OpenAI, Claude, etc.)?**
A: Yes. Modify `src/llm/client.py` to use a different API. The parsing logic in `src/llm/parsers.py` is LLM-agnostic.

**Q: How do I add more companies to crawl?**
A: Add URLs to `configs/urls.txt`, one per line. The crawler automatically groups by domain.

**Q: Can I run this locally without Supabase?**
A: Yes. Set `SUPABASE_ENABLED=0` in `.env`. Jobs will be saved to `out/<domain>/llm/*.jobs.json` files.

---

## 🙏 Acknowledgments

- **Playwright** - Robust browser automation
- **Google Gemini** - Powerful LLM for extraction
- **Supabase** - Excellent PostgreSQL platform
- **Pydantic** - Type-safe data validation
