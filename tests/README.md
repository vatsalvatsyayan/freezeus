# Freezeus Backend Test Suite

This directory contains all automated tests for the Freezeus job aggregation backend.

## Structure

```
tests/
├── unit/              # Fast, isolated unit tests
├── integration/       # Component integration tests
├── e2e/              # End-to-end tests (slow, expensive)
├── fixtures/         # Test data and mock responses
├── conftest.py       # Pytest configuration and shared fixtures
└── README.md         # This file
```

## Running Tests

### Prerequisites

```bash
# Install development dependencies
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html tests/

# Run verbose
pytest -v tests/
```

### Run Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# End-to-end tests (slow, expensive)
pytest tests/e2e/ -m e2e
```

### Run Specific Tests

```bash
# Run specific file
pytest tests/unit/test_url_normalization.py

# Run specific class
pytest tests/unit/test_url_normalization.py::TestURLNormalization

# Run specific test
pytest tests/unit/test_url_normalization.py::TestURLNormalization::test_already_complete_url

# Run tests matching pattern
pytest -k "normalize"
```

### Test Markers

Tests are marked for easy filtering:

```bash
# Run only unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Skip expensive tests (API calls)
pytest -m "not expensive"
```

## Test Coverage

View coverage after running tests with coverage:

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html tests/

# Open coverage report
open htmlcov/index.html
```

**Current Coverage Goal:** 80%+

## Writing Tests

### Unit Tests

Unit tests should be:
- Fast (< 100ms each)
- Isolated (no external dependencies)
- Deterministic (same result every time)
- Comprehensive (test edge cases)

```python
# tests/unit/test_example.py
import pytest
from src.module import function

def test_function_with_valid_input():
    """Test function with valid input."""
    result = function("valid")
    assert result == "expected"

def test_function_with_invalid_input():
    """Test function raises error with invalid input."""
    with pytest.raises(ValueError):
        function("invalid")
```

### Integration Tests

Integration tests verify components work together:

```python
# tests/integration/test_example.py
import pytest

@pytest.mark.integration
def test_crawler_to_database_flow(mock_supabase_client):
    """Test full flow from crawler to database."""
    # Test implementation
    ...
```

### End-to-End Tests

E2E tests run the full pipeline (use sparingly - expensive):

```python
# tests/e2e/test_full_pipeline.py
import pytest

@pytest.mark.e2e
@pytest.mark.expensive
@pytest.mark.slow
def test_full_crawl_pipeline():
    """Test complete crawl → extract → store pipeline."""
    # Use real URLs but limit scope
    ...
```

## Fixtures

Shared fixtures are defined in `conftest.py`:

```python
def test_something(sample_job, mock_gemini_response):
    """Use fixtures in tests."""
    # sample_job and mock_gemini_response are available
    ...
```

## Best Practices

1. **One assertion per test** (when possible)
2. **Descriptive test names** (describe what is tested)
3. **Arrange-Act-Assert** pattern
4. **Mock external services** (Gemini API, Supabase)
5. **Test edge cases** (empty, None, invalid input)
6. **Keep tests independent** (don't rely on test order)

## Continuous Integration

Tests run automatically on:
- Every push to GitHub
- Pull requests
- Scheduled runs

See `.github/workflows/tests.yml` for CI configuration.

## Troubleshooting

### Tests fail locally but pass in CI

- Check Python version matches (`python --version`)
- Ensure dependencies are up to date (`pip install -r requirements-dev.txt`)
- Clear pytest cache (`rm -rf .pytest_cache`)

### ImportError: No module named 'src'

- Run tests from project root: `pytest tests/`
- Check PYTHONPATH is correct

### Coverage report missing files

- Ensure you're running from project root
- Check `pytest.ini` coverage configuration

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)
- [Python Testing Guide](https://realpython.com/pytest-python-testing/)

---

**Last Updated:** 2026-01-08
**Test Framework:** pytest 7.4.3
**Current Coverage:** Starting (first tests added)
