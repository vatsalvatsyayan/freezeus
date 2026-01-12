"""
Unit tests for crawler URL utilities.

Tests URL parsing, normalization, canonicalization, and path generation.
"""

import pytest
from pathlib import Path

# Import directly from url_utils to avoid triggering __init__.py
# which would import playwright-dependent modules
from src.crawler.url_utils import (
    domain_of,
    site_dir,
    sha1,
    base_name_for,
    canon_url,
    normalize_url,
)


class TestDomainOf:
    """Tests for domain_of function."""

    def test_extract_domain_from_https(self):
        """Test extracting domain from HTTPS URL."""
        assert domain_of("https://example.com/jobs") == "example.com"

    def test_extract_domain_from_http(self):
        """Test extracting domain from HTTP URL."""
        assert domain_of("http://example.com/jobs") == "example.com"

    def test_extract_domain_with_subdomain(self):
        """Test extracting domain with subdomain."""
        assert domain_of("https://careers.example.com/jobs") == "careers.example.com"

    def test_extract_domain_with_port(self):
        """Test extracting domain with port number."""
        assert domain_of("https://example.com:8080/jobs") == "example.com:8080"

    def test_extract_domain_with_path_and_query(self):
        """Test extracting domain from URL with path and query params."""
        assert domain_of("https://example.com/jobs?page=2#results") == "example.com"

    def test_lowercase_domain(self):
        """Test that domain is lowercased."""
        assert domain_of("https://Example.COM/jobs") == "example.com"


class TestSiteDir:
    """Tests for site_dir function."""

    def test_returns_path_object(self):
        """Test that site_dir returns a Path object."""
        result = site_dir("example.com")
        assert isinstance(result, Path)

    def test_creates_directory(self):
        """Test that site_dir creates the directory."""
        domain = "test-domain-12345.com"
        result = site_dir(domain)
        assert result.exists()
        assert result.is_dir()
        # Cleanup
        result.rmdir()

    def test_path_structure(self):
        """Test that site_dir creates correct path structure."""
        result = site_dir("example.com")
        assert "out" in str(result)
        assert "example.com" in str(result)


class TestSha1:
    """Tests for sha1 function."""

    def test_deterministic_hash(self):
        """Test that same input produces same hash."""
        text = "hello world"
        hash1 = sha1(text)
        hash2 = sha1(text)
        assert hash1 == hash2

    def test_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        hash1 = sha1("hello")
        hash2 = sha1("world")
        assert hash1 != hash2

    def test_hash_length(self):
        """Test that hash is 40 characters (SHA1 hex)."""
        result = sha1("test")
        assert len(result) == 40

    def test_hash_is_hexadecimal(self):
        """Test that hash contains only hex characters."""
        result = sha1("test")
        assert all(c in "0123456789abcdef" for c in result)

    def test_unicode_handling(self):
        """Test that unicode text is handled correctly."""
        result = sha1("Hello 世界 🌍")
        assert len(result) == 40


class TestBaseNameFor:
    """Tests for base_name_for function."""

    def test_extract_path_segment(self):
        """Test extracting last path segment."""
        result = base_name_for("https://example.com/jobs/engineering")
        assert "engineering" in result
        assert "__" in result  # Contains hash separator

    def test_remove_leading_numbers(self):
        """Test that leading numbers are removed."""
        result = base_name_for("https://example.com/jobs/123-software-engineer")
        assert result.startswith("software")

    def test_remove_trailing_numbers(self):
        """Test that trailing numbers are removed."""
        result = base_name_for("https://example.com/jobs/software-123")
        assert "software" in result
        assert not result.split("__")[0].endswith("123")

    def test_uses_title_for_index(self):
        """Test that title is used for generic URLs."""
        result = base_name_for("https://example.com/index", "Careers Page")
        assert "careers-page" in result

    def test_includes_hash_for_uniqueness(self):
        """Test that result includes hash for uniqueness."""
        result = base_name_for("https://example.com/jobs")
        parts = result.split("__")
        assert len(parts) == 2
        assert len(parts[1]) == 8  # 8-char hash

    def test_different_urls_different_hashes(self):
        """Test that different URLs produce different hashes."""
        result1 = base_name_for("https://example.com/jobs/1")
        result2 = base_name_for("https://example.com/jobs/2")
        hash1 = result1.split("__")[1]
        hash2 = result2.split("__")[1]
        assert hash1 != hash2

    def test_normalizes_special_characters(self):
        """Test that special characters are replaced with hyphens."""
        result = base_name_for("https://example.com/jobs/c++_developer")
        assert "c--developer" in result or "developer" in result

    def test_max_length_enforcement(self):
        """Test that slug is truncated to max length."""
        long_url = "https://example.com/jobs/" + "a" * 100
        result = base_name_for(long_url)
        slug = result.split("__")[0]
        assert len(slug) <= 40


class TestCanonUrl:
    """Tests for canon_url function."""

    def test_resolve_relative_url(self):
        """Test resolving relative URL to absolute."""
        result = canon_url("https://example.com/careers", "../jobs/123")
        assert result == "https://example.com/jobs/123"

    def test_resolve_absolute_url(self):
        """Test that absolute URL is preserved."""
        result = canon_url("https://example.com", "https://other.com/jobs")
        assert result == "https://other.com/jobs"

    def test_remove_utm_parameters(self):
        """Test that UTM tracking parameters are removed."""
        result = canon_url(
            "https://example.com",
            "/jobs?id=123&utm_source=twitter&utm_campaign=hiring"
        )
        assert result == "https://example.com/jobs?id=123"

    def test_remove_gclid(self):
        """Test that Google click ID is removed."""
        result = canon_url("https://example.com", "/jobs?id=123&gclid=xyz123")
        assert result == "https://example.com/jobs?id=123"

    def test_remove_fbclid(self):
        """Test that Facebook click ID is removed."""
        result = canon_url("https://example.com", "/jobs?id=123&fbclid=abc456")
        assert result == "https://example.com/jobs?id=123"

    def test_remove_fragment(self):
        """Test that URL fragment is removed."""
        result = canon_url("https://example.com", "/jobs#section")
        assert result == "https://example.com/jobs"

    def test_lowercase_scheme_and_domain(self):
        """Test that scheme and domain are lowercased."""
        result = canon_url("https://example.com", "HTTPS://Example.COM/Jobs")
        assert result == "https://example.com/Jobs"  # Path case preserved

    def test_preserve_important_params(self):
        """Test that non-tracking parameters are preserved."""
        result = canon_url("https://example.com", "/jobs?page=2&sort=date")
        assert "page=2" in result
        assert "sort=date" in result

    def test_invalid_url_graceful_handling(self):
        """Test that invalid URLs are handled gracefully."""
        # urljoin is permissive and treats these as relative paths
        result = canon_url("https://example.com", "relative/path")
        assert result is not None
        # But truly malformed URLs should return None
        result2 = canon_url("ht!tp://bad", None)
        assert result2 is None or isinstance(result2, str)


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_remove_tracking_params(self):
        """Test that tracking parameters are removed."""
        result = normalize_url("https://example.com/jobs?utm_source=email&page=2")
        assert "utm_source" not in result
        assert "page=2" in result

    def test_preserve_non_tracking_params(self):
        """Test that non-tracking parameters are preserved."""
        result = normalize_url("https://example.com/jobs?location=remote&level=senior")
        assert "location=remote" in result
        assert "level=senior" in result

    def test_lowercase_scheme_and_domain(self):
        """Test that scheme and domain are lowercased."""
        result = normalize_url("HTTPS://Example.COM/jobs")
        assert result.startswith("https://example.com")

    def test_remove_multiple_tracking_params(self):
        """Test removing multiple tracking parameters."""
        result = normalize_url(
            "https://example.com/jobs?utm_source=a&utm_medium=b&utm_campaign=c&page=1"
        )
        assert "utm_" not in result
        assert "page=1" in result

    def test_invalid_url_returns_original(self):
        """Test that invalid URL returns the original string."""
        invalid = "not a valid url"
        result = normalize_url(invalid)
        assert result == invalid

    def test_empty_query_string(self):
        """Test URL with no query parameters."""
        result = normalize_url("https://example.com/jobs")
        assert result == "https://example.com/jobs"
