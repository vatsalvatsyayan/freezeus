# Crawler Module

Multi-site job board crawler with pagination detection, infinite scroll support, and optional LLM-based extraction.

## 📁 Module Structure

```
src/crawler/
├── README.md              # This file
├── __init__.py           # Module exports with lazy loading
├── url_utils.py          # URL parsing and path generation
├── reducers.py           # HTML reduction JavaScript
├── page_analyzer.py      # Page content analysis
├── navigation.py         # Browser interactions
├── file_manager.py       # File I/O operations
└── multi_capture.py      # Main orchestration (entry point)
```

## 🔗 Module Dependencies

```
multi_capture.py (orchestrator)
    ├── url_utils.py (no external deps)
    ├── page_analyzer.py (requires: playwright)
    │   └── url_utils.py
    ├── navigation.py (requires: playwright)
    │   └── reducers.py
    └── file_manager.py
        └── url_utils.py
```

## 📄 File Descriptions

### `url_utils.py` - URL & Path Utilities
**Purpose**: Handle all URL parsing, normalization, and output path generation.

**No external dependencies** - Safe to import for testing.

**Key Functions**:
- `domain_of(url: str) -> str` - Extract domain from URL
- `canon_url(seed: str, href: str) -> Optional[str]` - Canonicalize URL (remove tracking params, resolve relatives)
- `normalize_url(url: str) -> str` - Normalize URL format
- `base_name_for(url: str, title: str) -> str` - Generate unique filename for URL
- `site_dir(domain: str) -> Path` - Get/create output directory for domain
- `sha1(text: str) -> str` - Compute SHA1 hash

**Used By**: All other crawler modules

**Testing**: `tests/unit/test_crawler_url_utils.py` (37 tests)

**Example**:
```python
from src.crawler.url_utils import canon_url, domain_of

# Extract domain
domain = domain_of("https://example.com/careers")  # "example.com"

# Canonicalize URL (remove tracking)
url = canon_url(
    "https://example.com",
    "/jobs?id=123&utm_source=twitter"
)  # "https://example.com/jobs?id=123"
```

---

### `reducers.py` - HTML Reduction Scripts
**Purpose**: JavaScript code executed in browser to reduce HTML to essential content.

**No external dependencies** - Pure JavaScript strings.

**Key Constants**:
- `REDUCE_FOCUS_JS` - Smart reducer that scores and keeps job-heavy containers
  - Detects job links (Greenhouse, Workday, Lever, etc.)
  - Scores containers by text length, link density, semantic HTML
  - Gives +25 point boost to containers with job links
  - Returns top 10 high-scoring containers
- `REDUCE_LITE_JS` - Simple reducer that strips scripts/styles only

**Used By**: `navigation.py` (executed via page.evaluate())

**How It Works**:
```python
# In navigation.py
result = await page.evaluate(REDUCE_FOCUS_JS)
reduced_html = result["reduced_html"]
signals = result["kept_signals"]  # Scoring metadata
```

---

### `page_analyzer.py` - Page Content Analysis
**Purpose**: Analyze page content, detect job listings, track changes for pagination/scroll detection.

**Dependencies**: `playwright` (async_api)

**Key Functions**:
- `ordered_job_hrefs(page, seed_url, cap=60) -> List[str]` - Extract job links from page
- `job_list_len(page) -> int` - Count job listings on page
- `page_text_fingerprint(page, cap=50) -> str` - SHA1 hash of page text for change detection
- `scroll_to_bottom_until_stable(page, max_rounds=20)` - Trigger infinite scroll
- `results_fingerprint(page, seed_url) -> dict` - Comprehensive page state snapshot
- `progressed(before: dict, after: dict) -> Tuple[bool, List[str]]` - Detect if content changed
- `wait_for_jobs_or_timeout(page, seed_url, max_wait_ms=35000) -> bool` - Wait for content to load

**Used By**: `multi_capture.py` (main orchestrator)

**Change Detection Flow**:
```python
# 1. Capture initial state
before = await results_fingerprint(page, seed_url)

# 2. User action (click, scroll, etc.)
await try_click_load_more(page)

# 3. Check if content changed
after = await results_fingerprint(page, seed_url)
changed, reasons = progressed(before, after)
# reasons might be: ["text_changed", "more_jobs", "url_changed"]
```

**Testing**: Requires playwright - integration tests only

---

### `navigation.py` - Browser Interactions
**Purpose**: Handle all browser interactions - navigation, clicking, scrolling, page snapshots.

**Dependencies**: `playwright` (async_api), `reducers.py`

**Key Functions**:
- `navigate_seed(page, url) -> Tuple[html, focus, lite, signals, meta]` - Navigate to URL and capture content
- `snapshot_current(page) -> Tuple[html, focus, lite, signals, meta]` - Snapshot current page without navigation
- `try_click_load_more(page) -> bool` - Try to click "Load More" button (12 selector patterns)
- `click_next_page(page) -> bool` - Try to click "Next" pagination button (semantic + CSS fallbacks)

**Interaction Strategy**:
1. **Semantic HTML First** - Uses ARIA roles and labels
2. **CSS Fallbacks** - If semantic approach fails, tries CSS selectors
3. **Multiple Patterns** - Each function tries 10-15 different selector patterns

**Used By**: `multi_capture.py` (main orchestrator)

**Example - Load More Click**:
```python
# Tries in order:
# 1. button:has-text("Load more")
# 2. button:has-text("Show more")
# 3. [role="button"]:has-text("Load more")
# ... up to 12 patterns

clicked = await try_click_load_more(page)
if clicked:
    # Wait for content to load
    await wait_for_jobs_or_timeout(page, seed_url)
```

**Testing**: Requires playwright - integration tests only

---

### `file_manager.py` - File I/O Operations
**Purpose**: Manage all file writing, directory structure, and manifest generation.

**Dependencies**: `url_utils.py`

**Output Directory Structure**:
```
out/
└── example.com/
    ├── full/              # Complete HTML
    ├── reduced_focus/     # Job-heavy HTML (for LLM)
    ├── reduced_lite/      # Script-stripped HTML
    ├── meta/              # Page metadata JSON
    ├── signals/           # Scoring signals JSON
    ├── llm/               # LLM extraction results
    └── *.manifest.json    # Crawl session manifests
```

**Key Functions**:
- `write_outputs(domain, url, html, focus, lite, signals, meta, page_id) -> Dict[paths]` - Write all files for one page
- `write_manifest(domain, seed_base, entries, mode, stop_reason, cfg)` - Write crawl manifest
- `read_urls_from_file(path) -> List[str]` - Parse URL list file
- `ensure_type_dirs(domain) -> Dict[str, Path]` - Create output directory structure
- `build_paths(domain, base, page_id) -> Dict[str, Path]` - Generate file paths for page

**Used By**: `multi_capture.py` (main orchestrator)

**File Naming Convention**:
```
{slug}__{hash}.{page_id}.{ext}

Examples:
- engineering__a1b2c3d4.p001.html     # First page
- engineering__a1b2c3d4.expanded.html # After load-more
- engineering__a1b2c3d4.p002.html     # Second pagination page
```

**Testing**: `tests/unit/test_crawler_url_utils.py` covers path generation

---

### `multi_capture.py` - Main Orchestration (Entry Point)
**Purpose**: High-level crawl orchestration - domain management, seed crawling, pagination, CLI.

**Dependencies**: All other crawler modules, `src.llm.llm_helper`

**Key Functions**:

#### `crawl_seed(page, seed_url, **config) -> None`
Crawl a single seed URL with full pagination/scroll support.

**Flow**:
1. Navigate to seed URL → save as `p001`
2. **Expansion phase** (load-more + scroll):
   - Try clicking "Load More" buttons
   - Scroll to trigger infinite scroll
   - Check for progress after each action
   - Save as `expanded` if content grew
   - Stop on: jobs_cap, time_budget, stable (no changes)
3. **Pagination phase** (next clicks):
   - Click "Next" button
   - Check for progress
   - Save as `p002`, `p003`, etc.
   - Stop on: pages_max, no_next, stable
4. Write manifest with all captured pages

**Parameters**:
- `jobs_max=100` - Stop after finding N job links
- `time_budget=75` - Max seconds for expansion phase
- `pages_max=3` - Max pagination pages
- `loadmore_max=5` - Max load-more clicks
- `scroll_max=20` - Max scroll attempts
- `no_change_cap=2` - Stop after N rounds with no change

#### `crawl(urls, headed, **config) -> List[str]`
Crawl multiple URLs grouped by domain.

**Flow**:
1. Group URLs by domain
2. For each domain:
   - Create browser context (state persisted across seeds)
   - Create page
   - Crawl each seed sequentially
   - Wait `PER_DOMAIN_DELAY` between seeds (politeness)
3. Return list of successfully processed domains

#### `llm_batch_postpass(out_root, domains) -> None`
Run LLM extraction on all captured HTML files.

**Called after crawl completes** if `--with-llm` flag is set.

**CLI Usage**:
```bash
# Basic crawl (headed mode)
python -m src.crawler.multi_capture --urls urls.txt

# Headless mode
python -m src.crawler.multi_capture --urls urls.txt --headless

# With LLM extraction
python -m src.crawler.multi_capture --urls urls.txt --with-llm

# Custom limits
python -m src.crawler.multi_capture \
    --urls urls.txt \
    --jobs-max 200 \
    --time-budget 120 \
    --pages-max 5
```

**Testing**: Integration tests require playwright + real URLs

---

## 🔄 How Modules Wire Together

### Crawl Execution Flow

```
1. CLI Entry Point (multi_capture.py:main)
   └── Read URL file (file_manager.read_urls_from_file)
   └── Group by domain (url_utils.domain_of)

2. For Each Domain (multi_capture.crawl)
   └── Create browser context (domain_context)
   └── For each seed URL (multi_capture.crawl_seed)

       a) Initial Navigation
          └── navigation.navigate_seed(page, url)
              └── Executes reducers.REDUCE_FOCUS_JS & REDUCE_LITE_JS
              └── Returns: full_html, reduced_html, signals, meta
          └── file_manager.write_outputs(..., page_id="p001")

       b) Expansion Phase (load-more + scroll)
          └── Loop:
              ├── navigation.try_click_load_more(page)
              ├── page.mouse.wheel() + page_analyzer.wait_for_jobs_or_timeout()
              ├── page_analyzer.results_fingerprint(page)
              ├── page_analyzer.progressed(before, after) → check if changed
              └── Stop if: jobs_max, time_budget, no_change_cap reached
          └── If content grew: file_manager.write_outputs(..., page_id="expanded")

       c) Pagination Phase (next clicks)
          └── Loop:
              ├── navigation.click_next_page(page)
              ├── page_analyzer.results_fingerprint(page)
              ├── page_analyzer.progressed(before, after)
              └── Stop if: pages_max, no_next, stable
          └── file_manager.write_outputs(..., page_id="p002", "p003", ...)

       d) Write Manifest
          └── file_manager.write_manifest(domain, seed_base, entries, ...)

3. Optional LLM Extraction (if --with-llm)
   └── multi_capture.llm_batch_postpass(out_root, domains)
       └── For each domain:
           └── src.llm.extract_all_focus_htmls(domain_dir)
               └── Processes all reduced_focus/*.html files
               └── Writes llm/*.jobs.json files
```

### Data Flow

```
URL → Browser → HTML → Reduction → Files → LLM → JSON → Database

1. URL (from file)
   └── multi_capture.crawl()
2. Browser (playwright)
   └── navigation.navigate_seed() / snapshot_current()
3. HTML (3 versions)
   ├── full_html: Complete page
   ├── reduced_focus: Job-heavy containers (for LLM)
   └── reduced_lite: Scripts stripped
4. Reduction (in browser)
   └── reducers.REDUCE_FOCUS_JS (JavaScript execution)
5. Files (organized by domain)
   └── file_manager.write_outputs()
6. LLM Extraction (optional)
   └── src.llm.extract_all_focus_htmls()
7. JSON (structured job data)
   └── llm/*.jobs.json
8. Database (Supabase)
   └── src.db.supabase_client.upsert_jobs_for_page()
```

## 🧪 Testing Strategy

### Unit Tests (No Playwright Required)
- `url_utils.py` → `tests/unit/test_crawler_url_utils.py` (37 tests)
  - URL parsing, normalization, canonicalization
  - Path generation, filename slugification
  - Tracking parameter removal

### Integration Tests (Require Playwright)
- `page_analyzer.py`, `navigation.py`, `multi_capture.py`
  - Requires real browser automation
  - Tests against actual HTML pages
  - Located in `tests/integration/` (if created)

### Manual Testing
```bash
# Test on a single URL
echo "https://jobs.example.com" > test_urls.txt
python -m src.crawler.multi_capture --urls test_urls.txt --headless

# Check output
ls -lh out/jobs.example.com/
```

## 🔧 Configuration

### Environment Variables (configs/.env)
```bash
# Crawler settings (in code constants)
PER_DOMAIN_DELAY=(8, 15)  # Seconds between seeds on same domain
NAV_TIMEOUT_MS=45000      # Navigation timeout
BLOCK_RESOURCE_TYPES={"media", "font", "image"}  # Block these to speed up

# User agent pool (random selection)
UA_POOL=[...]  # Desktop Chrome user agents
```

### CLI Parameters
```bash
--urls FILE           # Required: Path to URL list file
--headed              # Run browser in headed mode (default)
--headless            # Force headless mode
--with-llm            # Run LLM extraction after crawl
--jobs-max 100        # Stop after N job links found
--time-budget 75      # Max seconds for expansion phase
--pages-max 3         # Max pagination pages
--loadmore-max 5      # Max load-more clicks
--scroll-max 20       # Max scroll attempts
--no-change-cap 2     # Stop after N rounds with no change
```

## 🚀 Common Use Cases

### 1. Crawl Multiple Domains
```python
from pathlib import Path
from src.crawler.multi_capture import crawl
import asyncio

urls = [
    "https://example.com/careers",
    "https://other.com/jobs",
]

# Run crawl
domains = asyncio.run(crawl(
    urls=urls,
    headed=False,  # Headless
    jobs_max=200,
    pages_max=5
))
print(f"Crawled domains: {domains}")
```

### 2. Process Single URL Programmatically
```python
from playwright.async_api import async_playwright
from src.crawler.multi_capture import domain_context, crawl_seed

async def main():
    async with async_playwright() as pw:
        async with domain_context(pw, "example.com", headed=False) as ctx:
            page = await ctx.new_page()
            await crawl_seed(page, "https://example.com/careers")

asyncio.run(main())
```

### 3. Extract URLs from Captured Pages
```python
from src.crawler.url_utils import domain_of, site_dir
from pathlib import Path
import json

domain = "example.com"
site = site_dir(domain)

# Read manifest to find all captured pages
manifests = list(site.glob("*.manifest.json"))
for manifest_path in manifests:
    manifest = json.loads(manifest_path.read_text())
    print(f"Mode: {manifest['mode']}")
    print(f"Stop reason: {manifest['stop_reason']}")
    print(f"Pages captured: {len(manifest['pages'])}")
```

## 📝 Important Functions Reference

### URL Utilities
| Function | Purpose | Returns |
|----------|---------|---------|
| `domain_of(url)` | Extract domain | `str` |
| `canon_url(seed, href)` | Canonicalize URL | `Optional[str]` |
| `base_name_for(url, title)` | Generate filename | `str` |

### Page Analysis
| Function | Purpose | Returns |
|----------|---------|---------|
| `ordered_job_hrefs(page, seed, cap)` | Extract job links | `List[str]` |
| `results_fingerprint(page, seed)` | Page state snapshot | `dict` |
| `progressed(before, after)` | Detect changes | `(bool, List[str])` |

### Navigation
| Function | Purpose | Returns |
|----------|---------|---------|
| `navigate_seed(page, url)` | Navigate + capture | `(html, focus, lite, signals, meta)` |
| `try_click_load_more(page)` | Click load more | `bool` |
| `click_next_page(page)` | Click pagination | `bool` |

### File Management
| Function | Purpose | Returns |
|----------|---------|---------|
| `write_outputs(...)` | Write all page files | `Dict[str, Path]` |
| `write_manifest(...)` | Write crawl manifest | `None` |
| `read_urls_from_file(path)` | Parse URL file | `List[str]` |

## 🐛 Troubleshooting

### Issue: No jobs found
**Check**:
- Is the site using JavaScript to load content? (wait_for_jobs_or_timeout)
- Are job links using non-standard patterns? (check KEYWORD_RE in page_analyzer.py)
- Inspect reduced_focus HTML to see what's being captured

### Issue: Pagination not working
**Check**:
- Inspect page for next button selector
- Add custom selector to navigation.click_next_page() patterns
- Check if site uses infinite scroll instead of pagination

### Issue: Load More not working
**Check**:
- Inspect button text/attributes
- Add custom selector to navigation.try_click_load_more() patterns
- Try increasing scroll_max instead

### Issue: Browser crashes
**Check**:
- Increase NAV_TIMEOUT_MS
- Reduce jobs_max to limit page size
- Enable BLOCK_RESOURCE_TYPES to reduce memory

## 📚 Further Reading

- **Playwright Docs**: https://playwright.dev/python/
- **LLM Module**: `src/llm/README.md` (for extraction pipeline)
- **Database Module**: `src/db/README.md` (for data storage)
