# Freezeus Backend Refactoring Plan

**Date:** 2026-01-08
**Status:** Phase 2 - Planning (Awaiting Approval)
**Branch:** refactor-logic
**Related Document:** [refactoring-analysis.md](refactoring-analysis.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Proposed Folder Structure](#proposed-folder-structure)
3. [Refactoring Strategy](#refactoring-strategy)
4. [Testing Strategy](#testing-strategy)
5. [Documentation Requirements](#documentation-requirements)
6. [Risk Mitigation](#risk-mitigation)
7. [Implementation Milestones](#implementation-milestones)
8. [Success Criteria](#success-criteria)

---

## Overview

### Goals

This refactoring will transform the Freezeus backend from a functional but cluttered codebase into a **maintainable, well-tested, production-grade system** following software engineering best practices.

### Principles

1. **Incremental Changes** - Small, reviewable changes rather than wholesale rewrites
2. **Safety First** - Preserve all existing functionality, zero data loss
3. **Test-Driven** - Write tests before refactoring code
4. **Documentation** - Keep docs in sync with code changes
5. **Backward Compatible** - No breaking changes to data or APIs

### Timeline

**Total Estimated Time:** 3-4 weeks (40-60 hours)

| Phase | Duration | Effort |
|-------|----------|--------|
| Phase 1: Analysis | ✅ Complete | 4 hours |
| Phase 2: Planning | ✅ In Progress | 2 hours |
| Phase 3: Execution | Pending Approval | 30-40 hours |
| Phase 4: QA | Pending | 4-6 hours |

---

## Proposed Folder Structure

### Current Structure (Problematic)

```
src/
├── crawler/
│   ├── multi_capture.py              ← ACTIVE
│   └── multi_capture_working.py      ← DELETE (old version)
├── llm/
│   ├── llm_helper.py                 ← ACTIVE
│   ├── llm_helper_working.py         ← DELETE (old version)
│   ├── llm_helper_working2.py        ← DELETE (old version)
│   └── llm_helper_working3.py        ← DELETE (old version)
└── db/
    └── supabase_client.py            ← ACTIVE
```

### Proposed Structure (Clean & Organized)

```
freezeus/
├── .github/
│   └── workflows/
│       └── crawler.yml
│
├── configs/
│   ├── .env.example                  # NEW: Template for .env
│   ├── .env                          # (gitignored)
│   ├── urls.txt
│   └── llm_extraction_prompt.txt
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                         # NEW: Core utilities
│   │   ├── __init__.py
│   │   ├── config.py                 # Configuration management
│   │   ├── logging.py                # Structured logging setup
│   │   └── constants.py              # Shared constants
│   │
│   ├── crawler/                      # Web scraping layer
│   │   ├── __init__.py
│   │   ├── README.md                 # NEW: Module documentation
│   │   ├── multi_capture.py          # Main crawler (refactored)
│   │   ├── browser.py                # NEW: Browser setup/config
│   │   ├── navigation.py             # NEW: Navigation logic
│   │   ├── html_reducer.py           # NEW: HTML reduction strategies
│   │   └── fingerprint.py            # NEW: Progress detection
│   │
│   ├── llm/                          # LLM extraction layer
│   │   ├── __init__.py
│   │   ├── README.md                 # NEW: Module documentation
│   │   ├── extractor.py              # Main LLM interface (refactored)
│   │   ├── parsers.py                # NEW: JSON parsing utilities
│   │   ├── normalizers.py            # NEW: URL/data normalization
│   │   └── prompt_loader.py          # NEW: Prompt management
│   │
│   ├── database/                     # Database layer (renamed from db)
│   │   ├── __init__.py
│   │   ├── README.md                 # NEW: Module documentation
│   │   ├── client.py                 # Supabase client (refactored)
│   │   ├── models.py                 # NEW: Data models (Pydantic)
│   │   └── operations.py             # NEW: DB operations (upsert, etc.)
│   │
│   └── utils/                        # NEW: Shared utilities
│       ├── __init__.py
│       ├── date_utils.py             # Date parsing/formatting
│       ├── url_utils.py              # URL validation/normalization
│       ├── file_utils.py             # File I/O helpers
│       └── retry.py                  # Retry logic with backoff
│
├── tests/                            # NEW: Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest configuration & fixtures
│   │
│   ├── unit/                         # Unit tests (fast, isolated)
│   │   ├── __init__.py
│   │   ├── test_url_utils.py
│   │   ├── test_date_utils.py
│   │   ├── test_parsers.py
│   │   ├── test_normalizers.py
│   │   ├── test_fingerprint.py
│   │   └── test_models.py
│   │
│   ├── integration/                  # Integration tests (slower)
│   │   ├── __init__.py
│   │   ├── test_crawler_pipeline.py
│   │   ├── test_llm_extraction.py
│   │   └── test_database_operations.py
│   │
│   ├── e2e/                          # End-to-end tests (slowest)
│   │   ├── __init__.py
│   │   └── test_full_pipeline.py
│   │
│   └── fixtures/                     # Test data
│       ├── sample_html/
│       ├── sample_json/
│       └── mock_responses/
│
├── scripts/
│   ├── crawl.sh                      # Local dev wrapper
│   ├── check_schema.py               # Database validation
│   ├── run_tests.sh                  # NEW: Test runner
│   └── setup_dev.sh                  # NEW: Dev environment setup
│
├── docs/
│   ├── refactoring-analysis.md       # ✅ Complete
│   ├── refactoring-plan.md           # ✅ This document
│   ├── refactoring-log.md            # NEW: Change log
│   ├── API.md                        # NEW: Internal API docs
│   ├── TESTING.md                    # NEW: Testing guide
│   └── analysis/                     # Existing analysis docs
│       └── ...
│
├── archive/                          # NEW: Old code for reference
│   └── pre_refactor/
│       ├── multi_capture_working.py
│       ├── llm_helper_working.py
│       ├── llm_helper_working2.py
│       └── llm_helper_working3.py
│
├── .pre-commit-config.yaml           # NEW: Auto-formatting/linting
├── pytest.ini                        # NEW: Pytest configuration
├── .pylintrc                         # NEW: Linting rules
├── pyproject.toml                    # NEW: Project metadata
├── requirements.txt                  # Updated with test deps
├── requirements-dev.txt              # NEW: Dev-only dependencies
└── README.md                         # Updated with new structure
```

### Key Improvements

1. **`src/core/`** - Centralized configuration, logging, constants
2. **Better separation** - Browser logic separate from navigation
3. **Utility modules** - Reusable helpers (dates, URLs, retry)
4. **Database models** - Pydantic models for type safety
5. **Complete test suite** - Unit, integration, e2e tests
6. **Archive folder** - Old code preserved but out of the way
7. **READMEs** - Each module explains its purpose

---

## Refactoring Strategy

### Priority System

- 🔴 **P0 (Critical):** Must do - foundational changes
- 🟡 **P1 (High):** Should do - major improvements
- 🟢 **P2 (Medium):** Nice to have - quality improvements
- ⚪ **P3 (Low):** Optional - polish

### Milestone 1: Foundation & Cleanup (Week 1)

#### 🔴 P0: Archive Legacy Files
**Goal:** Remove 75% of redundant code

**Tasks:**
1. Create `archive/pre_refactor/` directory
2. Move old "_working" files to archive:
   - `multi_capture_working.py`
   - `llm_helper_working.py`
   - `llm_helper_working2.py`
   - `llm_helper_working3.py`
3. Verify active files still work
4. Update any imports if needed
5. Commit with clear message

**Estimated Time:** 1 hour
**Risk:** Low (files aren't imported)

#### 🔴 P0: Set Up Testing Framework
**Goal:** Enable automated testing

**Tasks:**
1. Add test dependencies to `requirements-dev.txt`:
   ```
   pytest==7.4.3
   pytest-asyncio==0.21.1
   pytest-cov==4.1.0
   pytest-mock==3.12.0
   ```
2. Create `tests/` directory structure
3. Create `tests/conftest.py` with basic fixtures
4. Create `pytest.ini` configuration
5. Write first test (URL normalization)
6. Verify tests run: `pytest tests/`

**Estimated Time:** 3 hours
**Risk:** Low (new code, no changes to production)

#### 🟡 P1: Add Structured Logging
**Goal:** Replace print() with proper logging

**Tasks:**
1. Create `src/core/logging.py`:
   ```python
   import logging
   import sys

   def setup_logging(level: str = "INFO") -> logging.Logger:
       """Configure structured logging."""
       logging.basicConfig(
           level=getattr(logging, level.upper()),
           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
           handlers=[
               logging.StreamHandler(sys.stdout),
               logging.FileHandler('logs/crawler.log')
           ]
       )
       return logging.getLogger(__name__)
   ```
2. Replace print() statements in:
   - `multi_capture.py` (30+ occurrences)
   - `llm_helper.py` (20+ occurrences)
   - `supabase_client.py` (10+ occurrences)
3. Test logging output
4. Update README with logging configuration

**Estimated Time:** 4 hours
**Risk:** Low (backward compatible)

#### 🟡 P1: Create Configuration Module
**Goal:** Centralize configuration management

**Tasks:**
1. Create `src/core/config.py`:
   ```python
   from pathlib import Path
   from typing import Optional
   from pydantic import BaseSettings, Field

   class Config(BaseSettings):
       """Application configuration."""

       # Gemini API
       gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
       gemini_model: str = Field(default="models/gemini-1.5-pro-latest")

       # Supabase
       supabase_url: Optional[str] = Field(None, env="SUPABASE_URL")
       supabase_key: Optional[str] = Field(None, env="SUPABASE_SERVICE_ROLE_KEY")
       supabase_enabled: bool = Field(default=True)

       # Crawler
       max_retries: int = 3
       nav_timeout_ms: int = 45000

       class Config:
           env_file = "configs/.env"
   ```
2. Update modules to use Config
3. Add validation at startup
4. Create `configs/.env.example`

**Estimated Time:** 3 hours
**Risk:** Low (wrapper around existing config)

**Milestone 1 Total:** 11 hours

### Milestone 2: Core Refactoring (Week 2)

#### 🔴 P0: Extract Utility Functions
**Goal:** DRY - eliminate code duplication

**Tasks:**
1. Create `src/utils/url_utils.py`:
   - Move `normalize_job_url()` from llm_helper.py
   - Add URL validation function
   - Add tests (100% coverage)

2. Create `src/utils/date_utils.py`:
   - Date parsing utilities
   - Timestamp formatting
   - Add tests

3. Create `src/utils/retry.py`:
   - Exponential backoff decorator
   - Configurable retry logic
   - Add tests

4. Create `src/utils/file_utils.py`:
   - Safe file read/write
   - JSON load/save with error handling
   - Add tests

**Estimated Time:** 6 hours
**Risk:** Low (well-tested utilities)

#### 🟡 P1: Refactor LLM Module
**Goal:** Better structure and testability

**Tasks:**
1. Rename `src/llm/` → `src/llm/` (keep name, refactor contents)
2. Split `llm_helper.py` into:
   - `extractor.py` - Main LLM interface
   - `parsers.py` - JSON parsing logic
   - `normalizers.py` - Data normalization
   - `prompt_loader.py` - Prompt management
3. Add type hints to all functions
4. Add docstrings (Google style)
5. Write unit tests for each module
6. Integration test for full extraction

**Estimated Time:** 8 hours
**Risk:** Medium (core functionality, need good tests)

#### 🟡 P1: Refactor Database Module
**Goal:** Type-safe database operations

**Tasks:**
1. Rename `src/db/` → `src/database/`
2. Create `src/database/models.py`:
   ```python
   from pydantic import BaseModel, HttpUrl
   from typing import Optional
   from datetime import datetime

   class Job(BaseModel):
       """Job listing model."""
       job_url: HttpUrl
       title: str
       company: Optional[str]
       location: Optional[str]
       country: str = "Unknown"
       # ... other fields
   ```
3. Split `supabase_client.py` into:
   - `client.py` - Connection management
   - `operations.py` - CRUD operations
4. Use Pydantic models for validation
5. Add comprehensive tests
6. Test upsert logic thoroughly

**Estimated Time:** 8 hours
**Risk:** High (critical path, need extensive testing)

**Milestone 2 Total:** 22 hours

### Milestone 3: Crawler Refactoring (Week 3)

#### 🟡 P1: Modularize Crawler
**Goal:** Break up large multi_capture.py

**Tasks:**
1. Extract into separate files:
   - `browser.py` - Browser setup, user agents, viewport
   - `navigation.py` - Page navigation, waiting, scrolling
   - `html_reducer.py` - HTML reduction JavaScript
   - `fingerprint.py` - Progress detection logic
2. Keep `multi_capture.py` as orchestrator
3. Add type hints throughout
4. Add docstrings
5. Write unit tests for each module
6. Integration test for crawler

**Estimated Time:** 10 hours
**Risk:** Medium (complex logic, need careful testing)

#### 🟢 P2: Add Type Hints Everywhere
**Goal:** 100% type hint coverage

**Tasks:**
1. Install mypy: `pip install mypy`
2. Add mypy configuration to `pyproject.toml`
3. Run mypy and fix all issues
4. Add type hints to remaining functions
5. Configure CI to run mypy

**Estimated Time:** 4 hours
**Risk:** Low (improves code quality)

#### 🟢 P2: Add Pre-commit Hooks
**Goal:** Automated code quality checks

**Tasks:**
1. Create `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/psf/black
       rev: 23.12.1
       hooks:
         - id: black
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.1.9
       hooks:
         - id: ruff
     - repo: https://github.com/pre-commit/mirrors-mypy
       rev: v1.8.0
       hooks:
         - id: mypy
   ```
2. Install: `pre-commit install`
3. Run on all files: `pre-commit run --all-files`
4. Fix any issues
5. Document in README

**Estimated Time:** 2 hours
**Risk:** Low (improves workflow)

**Milestone 3 Total:** 16 hours

### Milestone 4: Testing & Documentation (Week 4)

#### 🔴 P0: Achieve 80% Test Coverage
**Goal:** Comprehensive test suite

**Tasks:**
1. Write unit tests for all utilities (100%)
2. Write unit tests for core logic (90%+)
3. Write integration tests for pipelines
4. Write e2e test (1 real URL)
5. Run coverage: `pytest --cov=src tests/`
6. Fill gaps until >80% coverage

**Estimated Time:** 12 hours
**Risk:** Low (improves quality)

#### 🟡 P1: Complete Documentation
**Goal:** Every module documented

**Tasks:**
1. Add README.md to each src/ subdirectory
2. Create `docs/API.md` - Internal API documentation
3. Create `docs/TESTING.md` - How to run tests
4. Create `docs/refactoring-log.md` - Change log
5. Update main README.md with new structure
6. Add code examples to docs

**Estimated Time:** 6 hours
**Risk:** Low (documentation)

#### 🟢 P2: Performance Benchmarking
**Goal:** Ensure no regressions

**Tasks:**
1. Create benchmark script
2. Measure before refactoring:
   - Crawl time per URL
   - LLM API calls per page
   - Database upsert time
3. Measure after refactoring
4. Compare results
5. Optimize if needed

**Estimated Time:** 4 hours
**Risk:** Low (informational)

**Milestone 4 Total:** 22 hours

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \  E2E Tests (1-2 tests, slow, expensive)
      /____\
     /      \  Integration Tests (10-15 tests, medium speed)
    /________\
   /          \  Unit Tests (50+ tests, fast, cheap)
  /____________\
```

### Unit Tests (Target: 50+ tests)

**Coverage Goal:** 80%+ overall, 100% for utilities

**What to Test:**
- ✅ URL normalization (all edge cases)
- ✅ JSON parsing (valid, invalid, malformed)
- ✅ Date parsing (various formats)
- ✅ Fingerprint generation
- ✅ Data validation (Pydantic models)
- ✅ Retry logic
- ✅ File I/O operations
- ✅ Configuration loading

**Example Test:**
```python
# tests/unit/test_url_utils.py
import pytest
from src.utils.url_utils import normalize_job_url

def test_normalize_relative_url():
    """Test normalizing relative URL with source."""
    result = normalize_job_url(
        "/careers/jobs/12345",
        "https://block.xyz/careers",
        "block.xyz"
    )
    assert result == "https://block.xyz/careers/jobs/12345"

def test_normalize_already_complete():
    """Test that complete URLs are unchanged."""
    url = "https://jobs.dropbox.com/listing/7344941"
    result = normalize_job_url(url, "https://jobs.dropbox.com", "jobs.dropbox.com")
    assert result == url

def test_normalize_without_protocol():
    """Test URL without http/https."""
    result = normalize_job_url(
        "jobs.amazon.com/12345",
        None,
        "amazon.jobs"
    )
    assert result.startswith("https://")
```

### Integration Tests (Target: 10-15 tests)

**What to Test:**
- ✅ Full crawler pipeline (mock browser)
- ✅ LLM extraction with mock API
- ✅ Database operations (test database)
- ✅ File I/O end-to-end
- ✅ Configuration loading
- ✅ Error handling flows

**Example Test:**
```python
# tests/integration/test_llm_extraction.py
import pytest
from pathlib import Path
from src.llm.extractor import extract_jobs_from_html
from tests.fixtures import sample_html, sample_meta

def test_llm_extraction_pipeline(tmp_path, mock_gemini_api):
    """Test full LLM extraction pipeline."""
    # Setup
    html_path = tmp_path / "test.html"
    html_path.write_text(sample_html)
    meta_path = tmp_path / "test.json"

    # Execute
    result = extract_jobs_from_html(str(html_path), str(meta_path), "test.com")

    # Verify
    assert "jobs" in result
    assert len(result["jobs"]) > 0
    assert all(job["job_url"].startswith("http") for job in result["jobs"])
```

### End-to-End Tests (Target: 1-2 tests)

**What to Test:**
- ✅ Full pipeline on 1 real URL (sparingly - costs money)
- ✅ Verify manifest.json generated
- ✅ Verify database writes work
- ✅ Verify all output files created

**Example Test:**
```python
# tests/e2e/test_full_pipeline.py
import pytest
from src.crawler.multi_capture import main

@pytest.mark.slow
@pytest.mark.expensive
def test_full_crawler_pipeline(test_database):
    """Test complete crawl → extract → store pipeline."""
    # This test runs a real crawl on 1 URL
    # Use sparingly - costs money for LLM API

    result = main(
        urls=["https://jobs.dropbox.com/all-jobs"],
        max_jobs=5,  # Limit to save costs
        with_llm=True
    )

    # Verify outputs
    assert result.success
    assert result.jobs_found > 0
    assert result.manifest_created

    # Verify database
    jobs = test_database.query_jobs(limit=5)
    assert len(jobs) > 0
```

### Test Fixtures

**Key Fixtures:**
```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_html():
    """Load sample HTML for testing."""
    return Path("tests/fixtures/sample_html/dropbox.html").read_text()

@pytest.fixture
def mock_gemini_api(monkeypatch):
    """Mock Gemini API responses."""
    def mock_generate(*args, **kwargs):
        return MockResponse(text='{"jobs": [...]}')
    monkeypatch.setattr("google.generativeai.GenerativeModel.generate_content", mock_generate)

@pytest.fixture
def test_database():
    """Create temporary test database."""
    # Use SQLite or test Supabase instance
    ...
```

### Running Tests

**Commands:**
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html tests/

# Run only unit tests (fast)
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_url_utils.py

# Run with verbosity
pytest -v tests/

# Run and stop on first failure
pytest -x tests/
```

### Continuous Integration

**GitHub Actions workflow:**
```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --cov=src --cov-report=xml tests/
      - uses: codecov/codecov-action@v3
```

---

## Documentation Requirements

### Module READMEs

Each module must have a README.md explaining:
1. **Purpose** - What this module does
2. **Key Components** - Main files and their roles
3. **Usage Examples** - How to use the module
4. **Dependencies** - What it depends on
5. **Testing** - How to test it

**Example: src/crawler/README.md**
```markdown
# Crawler Module

## Purpose
Web scraping module using Playwright to capture job listings from company career pages.

## Key Components
- `multi_capture.py` - Main orchestrator
- `browser.py` - Browser configuration and setup
- `navigation.py` - Page navigation and interaction
- `html_reducer.py` - HTML reduction strategies
- `fingerprint.py` - Progress detection

## Usage
\`\`\`python
from src.crawler.multi_capture import capture_multi_site

results = capture_multi_site(
    urls=["https://jobs.dropbox.com/all-jobs"],
    max_jobs=100,
    headless=True
)
\`\`\`

## Dependencies
- Playwright (browser automation)
- src.core.config (configuration)
- src.core.logging (logging)

## Testing
\`\`\`bash
pytest tests/unit/crawler/
pytest tests/integration/test_crawler_pipeline.py
\`\`\`
```

### Main README.md Update

**Add sections:**
1. **New Structure** - Diagram of folders
2. **Development Setup** - How to contribute
3. **Running Tests** - Test commands
4. **Code Quality** - Linting, formatting
5. **Architecture** - Link to ARCHITECTURE.md

### New Documentation Files

1. **docs/API.md** - Internal API reference
2. **docs/TESTING.md** - Comprehensive testing guide
3. **docs/refactoring-log.md** - Change log during refactoring
4. **docs/CONTRIBUTING.md** - Contribution guidelines

---

## Risk Mitigation

### Critical Risks & Mitigations

#### Risk 1: Breaking Production Crawler
**Likelihood:** Medium | **Impact:** High

**Mitigation:**
1. ✅ Write tests BEFORE refactoring
2. ✅ Run tests after EVERY change
3. ✅ Test on staging environment
4. ✅ Gradual rollout (canary deployment)
5. ✅ Monitor first production run closely
6. ✅ Keep rollback plan ready

**Rollback Plan:**
```bash
# If production breaks, immediately:
git revert <commit-hash>
git push origin main
# Triggers automatic redeployment
```

#### Risk 2: Data Loss or Corruption
**Likelihood:** Low | **Impact:** High

**Mitigation:**
1. ✅ Database backup before major changes
2. ✅ Test database operations thoroughly
3. ✅ Use transactions where appropriate
4. ✅ Verify first_seen_at preservation
5. ✅ Dry-run mode for database writes
6. ✅ Monitor database after deployment

**Backup Command:**
```bash
# Export Supabase data
supabase db dump > backup_$(date +%Y%m%d).sql
```

#### Risk 3: Performance Degradation
**Likelihood:** Low | **Impact:** Medium

**Mitigation:**
1. ✅ Benchmark before refactoring
2. ✅ Profile code during refactoring
3. ✅ Benchmark after refactoring
4. ✅ Compare results
5. ✅ Optimize hotspots if needed

**Benchmarking:**
```python
# scripts/benchmark.py
import time
from src.crawler import multi_capture

start = time.time()
multi_capture.main(urls=["test_url"], max_jobs=10)
elapsed = time.time() - start
print(f"Crawl time: {elapsed:.2f}s")
```

#### Risk 4: Test Suite False Positives
**Likelihood:** Medium | **Impact:** Medium

**Mitigation:**
1. ✅ Review all tests carefully
2. ✅ Use realistic test data
3. ✅ Mock external services properly
4. ✅ Run integration tests on staging
5. ✅ Manual QA before production

#### Risk 5: Incomplete Migration
**Likelihood:** Low | **Impact:** High

**Mitigation:**
1. ✅ Checklist of all files to migrate
2. ✅ Update all import statements
3. ✅ Search for hardcoded paths
4. ✅ Test in clean environment
5. ✅ Verify CI/CD pipeline works

### Safety Checklist

**Before Each Milestone:**
- [ ] All tests passing
- [ ] Code reviewed (self or peer)
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Performance benchmarked

**Before Production Deployment:**
- [ ] Full test suite passes
- [ ] Integration tests on staging pass
- [ ] Database backup created
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] Team notified of deployment

---

## Implementation Milestones

### Detailed Breakdown

#### Milestone 1: Foundation (Week 1)
**Effort:** 11 hours

| Task | Priority | Time | Risk | Dependencies |
|------|----------|------|------|--------------|
| Archive legacy files | P0 | 1h | Low | None |
| Setup pytest | P0 | 3h | Low | requirements-dev.txt |
| Add structured logging | P1 | 4h | Low | None |
| Create config module | P1 | 3h | Low | pydantic |

**Deliverables:**
- ✅ Clean src/ directory (75% smaller)
- ✅ Working test framework
- ✅ Structured logging throughout
- ✅ Centralized configuration

**Success Criteria:**
- All legacy files in archive/
- At least 1 passing test
- No more print() statements
- Config validates on startup

#### Milestone 2: Core Refactoring (Week 2)
**Effort:** 22 hours

| Task | Priority | Time | Risk | Dependencies |
|------|----------|------|------|--------------|
| Extract utils (URL, date, retry) | P0 | 6h | Low | Milestone 1 |
| Refactor LLM module | P1 | 8h | Med | Utils |
| Refactor database module | P1 | 8h | High | Utils, models |

**Deliverables:**
- ✅ Reusable utility modules
- ✅ Clean LLM module structure
- ✅ Type-safe database operations
- ✅ 50%+ test coverage

**Success Criteria:**
- All utils have 100% test coverage
- LLM module split into 4+ files
- Database uses Pydantic models
- No duplicate code

#### Milestone 3: Crawler Refactoring (Week 3)
**Effort:** 16 hours

| Task | Priority | Time | Risk | Dependencies |
|------|----------|------|------|--------------|
| Modularize crawler | P1 | 10h | Med | Milestone 2 |
| Add type hints everywhere | P2 | 4h | Low | None |
| Setup pre-commit hooks | P2 | 2h | Low | None |

**Deliverables:**
- ✅ Modular crawler structure
- ✅ 100% type hint coverage
- ✅ Automated code quality checks
- ✅ 70%+ test coverage

**Success Criteria:**
- Crawler split into 4+ modules
- mypy passes with no errors
- pre-commit hooks installed
- Integration tests pass

#### Milestone 4: Testing & Polish (Week 4)
**Effort:** 22 hours

| Task | Priority | Time | Risk | Dependencies |
|------|----------|------|------|--------------|
| Achieve 80% coverage | P0 | 12h | Low | All modules |
| Complete documentation | P1 | 6h | Low | None |
| Performance benchmarking | P2 | 4h | Low | Milestone 3 |

**Deliverables:**
- ✅ 80%+ test coverage
- ✅ Complete documentation
- ✅ Performance report
- ✅ Production-ready codebase

**Success Criteria:**
- pytest --cov shows >80%
- Every module has README
- No performance regressions
- All acceptance criteria met

### Weekly Review Points

**End of Week 1:**
- Review: Foundation complete?
- Decision: Proceed or adjust?

**End of Week 2:**
- Review: Core refactoring solid?
- Decision: Continue to crawler?

**End of Week 3:**
- Review: Crawler working well?
- Decision: Ready for testing phase?

**End of Week 4:**
- Review: All criteria met?
- Decision: Deploy to production?

---

## Success Criteria

### Functional Requirements

**Must Have (P0):**
- ✅ All 2,099 existing jobs preserved in database
- ✅ Crawler still extracts jobs from all 13 companies
- ✅ LLM extraction accuracy maintained (>95%)
- ✅ Database upserts work correctly (no duplicates)
- ✅ first_seen_at / last_seen_at tracking works
- ✅ GitHub Actions workflow runs successfully
- ✅ All output files generated correctly

**Should Have (P1):**
- ✅ URL normalization works (100% complete URLs)
- ✅ JSONB data extracted to main columns
- ✅ Country field populated for new jobs
- ✅ Structured logging throughout
- ✅ Configuration validation at startup

### Non-Functional Requirements

**Code Quality:**
- ✅ Test coverage ≥ 80%
- ✅ No legacy "_working" files
- ✅ All functions have type hints
- ✅ All modules have docstrings
- ✅ Code passes linting (ruff, black)
- ✅ mypy passes with no errors

**Performance:**
- ✅ Crawl time ≤ baseline (no regressions)
- ✅ LLM API calls ≤ baseline
- ✅ Database operations ≤ baseline
- ✅ Memory usage reasonable

**Documentation:**
- ✅ README updated with new structure
- ✅ Each module has README
- ✅ API documentation complete
- ✅ Testing guide available
- ✅ Refactoring log maintained

**Maintainability:**
- ✅ Clear folder structure
- ✅ No code duplication
- ✅ Easy to add new features
- ✅ Easy to onboard new developers

### Acceptance Tests

**Before declaring success, verify:**

1. **End-to-End Test:**
   ```bash
   python -m src.crawler.multi_capture \
     --urls configs/urls.txt \
     --with-llm \
     --jobs-max 50
   ```
   Expected: Completes successfully, all manifests generated

2. **Database Verification:**
   ```sql
   SELECT COUNT(*) FROM jobs;
   -- Should be ≥ 2,099 (existing + new)

   SELECT COUNT(*) FROM jobs WHERE job_description IS NOT NULL;
   -- Should be > 1,570 (JSONB extraction working)
   ```

3. **Test Suite:**
   ```bash
   pytest --cov=src --cov-report=html tests/
   # Coverage must be ≥ 80%
   # All tests must pass
   ```

4. **Code Quality:**
   ```bash
   mypy src/
   # No errors

   ruff check src/
   # No violations

   black --check src/
   # Already formatted
   ```

5. **Production Deployment:**
   - Deploy to production
   - Monitor first 2 runs (12 hours)
   - Verify no errors in logs
   - Verify jobs being added to database
   - Compare job counts before/after

---

## Next Steps

### Immediate Actions

1. **Review this plan** - User feedback/approval needed
2. **Questions/concerns** - Address any issues
3. **Adjust priorities** - If needed based on feedback
4. **Get approval** - Proceed only after sign-off

### Upon Approval

1. **Create git branch** - `git checkout -b refactor/milestone-1`
2. **Start Milestone 1** - Archive legacy files
3. **Commit frequently** - Small, focused commits
4. **Run tests often** - After each change
5. **Document progress** - Update refactoring-log.md

### Communication

**Daily Updates:**
- What was completed
- What's in progress
- Any blockers
- ETA for current milestone

**Weekly Review:**
- Milestone completion status
- Adjust plan if needed
- Demo progress
- Get feedback

---

## Appendix

### Useful Commands

**Development:**
```bash
# Setup development environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
pytest tests/
pytest --cov=src tests/
pytest -v tests/unit/

# Code quality
black src/ tests/
ruff check src/ tests/
mypy src/

# Pre-commit
pre-commit install
pre-commit run --all-files
```

**Git Workflow:**
```bash
# Create feature branch
git checkout -b refactor/milestone-1

# Make changes
git add .
git commit -m "refactor: archive legacy files"

# Push
git push origin refactor/milestone-1

# Merge to main (after review)
git checkout main
git merge refactor/milestone-1
git push origin main
```

### Resources

**Python Best Practices:**
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Effective Python](https://effectivepython.com/)

**Testing:**
- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)

**Type Hints:**
- [PEP 484 Type Hints](https://peps.python.org/pep-0484/)
- [mypy Documentation](https://mypy.readthedocs.io/)

---

## Conclusion

This refactoring plan provides a **systematic, low-risk approach** to transforming the Freezeus backend into a maintainable, well-tested, production-grade system.

**Key Highlights:**
- 📋 **Incremental** - 4 milestones, each reviewable
- 🧪 **Test-Driven** - Tests written before refactoring
- 🛡️ **Safe** - Zero data loss, zero downtime
- 📚 **Documented** - Every step explained
- ⏱️ **Time-Boxed** - 3-4 weeks, 40-60 hours

**Awaiting approval to proceed to Phase 3: Execution.**

---

**Plan Created By:** Claude (AI Assistant)
**Document Version:** 1.0
**Date:** 2026-01-08
**Status:** Awaiting User Approval
