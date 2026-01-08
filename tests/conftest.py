"""
Pytest Configuration and Shared Fixtures

This file contains pytest configuration and fixtures that are available
to all tests in the test suite.
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import json


# ============================================================================
# Paths and Directories
# ============================================================================

@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_job() -> Dict[str, Any]:
    """Return a sample job dictionary."""
    return {
        "title": "Senior Software Engineer",
        "job_url": "https://jobs.example.com/listing/12345",
        "company": "Example Corp",
        "location": "San Francisco, CA",
        "country": "United States",
        "team_or_category": "Engineering",
        "employment_type": "Full-time",
        "office_or_remote": "Hybrid",
        "seniority_level": "Senior",
        "seniority_bucket": "senior",
        "date_posted": "2026-01-08",
        "extra": {
            "job_description": "We are seeking a talented engineer...",
            "weekly_hours": "40",
            "apply_url": "https://jobs.example.com/apply/12345"
        }
    }


@pytest.fixture
def sample_jobs_response() -> Dict[str, Any]:
    """Return a sample LLM response with multiple jobs."""
    return {
        "source_url": "https://jobs.example.com/all-jobs",
        "page_title": "Careers - Example Corp",
        "jobs": [
            {
                "title": "Software Engineer",
                "job_url": "https://jobs.example.com/listing/1",
                "company": "Example Corp",
                "location": "Remote - US",
                "country": "United States",
                "seniority_bucket": "mid"
            },
            {
                "title": "Senior Data Scientist",
                "job_url": "https://jobs.example.com/listing/2",
                "company": "Example Corp",
                "location": "New York, NY",
                "country": "United States",
                "seniority_bucket": "senior"
            }
        ]
    }


@pytest.fixture
def sample_html() -> str:
    """Return sample HTML content."""
    return """
    <html>
        <head><title>Jobs - Example Corp</title></head>
        <body>
            <main>
                <h1>Open Positions</h1>
                <div class="job-listing">
                    <h2>Software Engineer</h2>
                    <p>Location: San Francisco, CA</p>
                    <a href="/jobs/12345">View Details</a>
                </div>
                <div class="job-listing">
                    <h2>Product Manager</h2>
                    <p>Location: Remote</p>
                    <a href="/jobs/67890">View Details</a>
                </div>
            </main>
        </body>
    </html>
    """


@pytest.fixture
def sample_meta() -> Dict[str, Any]:
    """Return sample metadata."""
    return {
        "url": "https://jobs.example.com/all-jobs",
        "ts": 1704724800,
        "title": "Careers - Example Corp",
        "sha1": "abc123def456",
        "page_id": "p001"
    }


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    class MockResponse:
        def __init__(self, text: str):
            self.text = text

    def _create_response(jobs_data: Dict[str, Any]) -> MockResponse:
        return MockResponse(text=json.dumps(jobs_data))

    return _create_response


@pytest.fixture
def mock_supabase_client(monkeypatch):
    """Mock Supabase client for testing."""
    class MockTable:
        def __init__(self):
            self.data = []

        def select(self, *args):
            return self

        def eq(self, field, value):
            return self

        def limit(self, n):
            return self

        def execute(self):
            class Result:
                def __init__(self, data):
                    self.data = data
            return Result(self.data)

        def upsert(self, rows, on_conflict=None):
            self.data.extend(rows)
            return self

    class MockClient:
        def __init__(self):
            self.tables = {}

        def table(self, name: str):
            if name not in self.tables:
                self.tables[name] = MockTable()
            return self.tables[name]

    mock_client = MockClient()

    # Monkeypatch the client getter
    import src.db.supabase_client as supabase_module
    monkeypatch.setattr(supabase_module, "_client", mock_client)
    monkeypatch.setattr(supabase_module, "get_supabase", lambda: mock_client)

    return mock_client


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "expensive: mark test as expensive (costs money)"
    )
