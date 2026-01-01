#!/usr/bin/env python3
"""
Test URL normalization function to ensure it works correctly.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.llm_helper import normalize_job_url

def test_url_normalization():
    """Test URL normalization with various inputs."""
    print("=" * 80)
    print("TESTING URL NORMALIZATION")
    print("=" * 80)
    print()

    tests = [
        # (job_url, source_url, source_domain, expected)
        ("/careers/jobs/12345", "https://block.xyz/careers", "block.xyz", "https://block.xyz/careers/jobs/12345"),
        ("https://jobs.dropbox.com/123", "https://jobs.dropbox.com", "jobs.dropbox.com", "https://jobs.dropbox.com/123"),
        ("/jobs/456", None, "amazon.jobs", "https://amazon.jobs/jobs/456"),
        ("../job/789", "https://company.com/careers/listings", "company.com", "https://company.com/job/789"),  # urljoin handles ../ correctly
        ("https://example.com/job/999", "https://other.com", "other.com", "https://example.com/job/999"),  # Already complete
        ("job/111", "https://test.com/careers/", "test.com", "https://test.com/careers/job/111"),
    ]

    passed = 0
    failed = 0

    for job_url, source_url, source_domain, expected in tests:
        result = normalize_job_url(job_url, source_url, source_domain)
        is_pass = result == expected

        if is_pass:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"{status}")
        print(f"  Input:    '{job_url}'")
        print(f"  Source:   '{source_url}'")
        print(f"  Domain:   '{source_domain}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0

if __name__ == "__main__":
    success = test_url_normalization()
    sys.exit(0 if success else 1)
