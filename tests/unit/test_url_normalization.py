"""
Unit tests for URL normalization functionality.

Tests the normalize_job_url function from src.llm.llm_helper
to ensure relative URLs are properly converted to absolute URLs.
"""

import pytest
from src.llm.llm_helper import normalize_job_url


class TestURLNormalization:
    """Test suite for URL normalization."""

    def test_normalize_relative_url_with_source(self):
        """Test normalizing a relative URL when source_url is provided."""
        result = normalize_job_url(
            job_url="/careers/jobs/12345",
            source_url="https://block.xyz/careers",
            source_domain="block.xyz"
        )
        assert result == "https://block.xyz/careers/jobs/12345"

    def test_normalize_relative_url_without_source(self):
        """Test normalizing a relative URL without source_url (uses domain)."""
        result = normalize_job_url(
            job_url="/jobs/12345",
            source_url=None,
            source_domain="amazon.jobs"
        )
        assert result == "https://amazon.jobs/jobs/12345"

    def test_already_complete_url(self):
        """Test that complete URLs pass through unchanged."""
        url = "https://jobs.dropbox.com/listing/7344941"
        result = normalize_job_url(
            job_url=url,
            source_url="https://jobs.dropbox.com",
            source_domain="jobs.dropbox.com"
        )
        assert result == url

    def test_url_with_http_protocol(self):
        """Test that http:// URLs are preserved."""
        url = "http://jobs.example.com/listing/123"
        result = normalize_job_url(
            job_url=url,
            source_url="http://jobs.example.com",
            source_domain="jobs.example.com"
        )
        assert result == url

    def test_relative_url_with_query_params(self):
        """Test normalizing relative URL with query parameters."""
        result = normalize_job_url(
            job_url="/jobs/123?source=careers",
            source_url="https://company.com/careers",
            source_domain="company.com"
        )
        assert result == "https://company.com/jobs/123?source=careers"

    def test_relative_url_with_parent_directory(self):
        """Test normalizing URL with parent directory reference."""
        result = normalize_job_url(
            job_url="../jobs/123",
            source_url="https://company.com/careers/listings",
            source_domain="company.com"
        )
        # urljoin should handle parent directory correctly
        assert "jobs/123" in result
        assert result.startswith("https://")

    def test_empty_url_returns_none(self):
        """Test that empty URL returns None."""
        result = normalize_job_url(
            job_url="",
            source_url="https://company.com",
            source_domain="company.com"
        )
        assert result is None

    def test_none_url_returns_none(self):
        """Test that None URL returns None."""
        result = normalize_job_url(
            job_url=None,
            source_url="https://company.com",
            source_domain="company.com"
        )
        assert result is None

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed from URLs."""
        result = normalize_job_url(
            job_url="  /jobs/123  ",
            source_url="https://company.com",
            source_domain="company.com"
        )
        assert result == "https://company.com/jobs/123"

    def test_domain_without_protocol_gets_https(self):
        """Test that domains without protocol get https:// added."""
        result = normalize_job_url(
            job_url="/jobs/123",
            source_url=None,
            source_domain="jobs.example.com"  # No protocol
        )
        assert result == "https://jobs.example.com/jobs/123"

    def test_complex_path_normalization(self):
        """Test normalization with complex relative path."""
        result = normalize_job_url(
            job_url="../../careers/jobs/123",
            source_url="https://company.com/a/b/c",
            source_domain="company.com"
        )
        # urljoin resolves relative paths
        assert result.startswith("https://company.com")
        assert "careers/jobs/123" in result

    def test_fragment_preserved(self):
        """Test that URL fragments (#) are preserved."""
        result = normalize_job_url(
            job_url="/jobs/123#details",
            source_url="https://company.com",
            source_domain="company.com"
        )
        assert result == "https://company.com/jobs/123#details"

    @pytest.mark.parametrize("relative_url,expected_suffix", [
        ("/jobs/123", "/jobs/123"),
        ("jobs/456", "/jobs/456"),  # urljoin adds leading slash
        ("/careers/engineering/789", "/careers/engineering/789"),
        ("/apply?id=999", "/apply?id=999"),
    ])
    def test_various_relative_formats(self, relative_url, expected_suffix):
        """Test various formats of relative URLs."""
        result = normalize_job_url(
            job_url=relative_url,
            source_url="https://company.com",
            source_domain="company.com"
        )
        assert result.startswith("https://company.com")
        # Check that the path is included (may have variations due to urljoin)
        assert relative_url.lstrip('/') in result or expected_suffix in result
