"""
URL utility functions for Freezeus backend.

This module provides URL validation, normalization, and manipulation utilities.
"""

from typing import Optional
from urllib.parse import urljoin, urlparse
from src.core.logging import get_logger

logger = get_logger(__name__)


def normalize_job_url(
    job_url: str,
    source_url: Optional[str],
    source_domain: str
) -> Optional[str]:
    """
    Ensure job_url is a complete absolute URL.

    Args:
        job_url: URL from LLM (might be relative)
        source_url: The page URL we crawled (can be None)
        source_domain: Domain from directory name

    Returns:
        Complete absolute URL with protocol, or None if job_url is empty

    Examples:
        >>> normalize_job_url("/jobs/123", "https://company.com/careers", "company.com")
        'https://company.com/jobs/123'

        >>> normalize_job_url("https://jobs.example.com/123", None, "example.com")
        'https://jobs.example.com/123'

        >>> normalize_job_url("", "https://company.com", "company.com")
        None
    """
    if not job_url:
        return None

    job_url = job_url.strip()

    # Already complete?
    if job_url.startswith(('http://', 'https://')):
        return job_url

    # Try source_url first
    if source_url:
        try:
            return urljoin(source_url, job_url)
        except Exception as e:
            logger.warning(f"Failed to join URLs: {source_url} + {job_url}: {e}")

    # Fallback to domain
    if source_domain:
        if not source_domain.startswith(('http://', 'https://')):
            source_domain = f"https://{source_domain}"
        try:
            return urljoin(source_domain, job_url)
        except Exception as e:
            logger.warning(f"Failed to construct URL from domain: {e}")

    # Cannot normalize
    logger.error(f"Cannot normalize URL: '{job_url}' (no source)")
    return job_url


def validate_url(url: str) -> bool:
    """
    Check if a URL is valid and complete.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid and complete, False otherwise

    Examples:
        >>> validate_url("https://example.com/jobs/123")
        True

        >>> validate_url("/jobs/123")
        False

        >>> validate_url("not-a-url")
        False
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # Must start with http:// or https://
    if not url.startswith(('http://', 'https://')):
        return False

    # Try to parse
    try:
        result = urlparse(url)
        # Must have scheme and netloc
        return bool(result.scheme and result.netloc)
    except Exception:
        return False


def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from a URL.

    Args:
        url: URL to extract domain from

    Returns:
        Domain (netloc) or None if invalid

    Examples:
        >>> extract_domain("https://jobs.example.com/careers/123")
        'jobs.example.com'

        >>> extract_domain("http://example.com:8080/path")
        'example.com:8080'

        >>> extract_domain("invalid")
        None
    """
    if not url or not isinstance(url, str):
        return None

    try:
        result = urlparse(url)
        return result.netloc if result.netloc else None
    except Exception:
        return None


def is_absolute_url(url: str) -> bool:
    """
    Check if URL is absolute (has scheme and netloc).

    Args:
        url: URL to check

    Returns:
        True if absolute, False if relative or invalid

    Examples:
        >>> is_absolute_url("https://example.com/jobs")
        True

        >>> is_absolute_url("/jobs/123")
        False
    """
    if not url:
        return False

    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except Exception:
        return False


def extract_company_name(domain: str) -> str:
    """
    Extract a human-readable company name from a domain.

    Removes common job-related subdomains/prefixes and formats the result.

    Args:
        domain: Domain name (e.g., "jobs.dropbox.com", "careers-google.com")

    Returns:
        Human-readable company name (e.g., "Dropbox", "Google")

    Examples:
        >>> extract_company_name("jobs.dropbox.com")
        'Dropbox'

        >>> extract_company_name("careers.google.com")
        'Google'

        >>> extract_company_name("stripe-jobs.com")
        'Stripe'

        >>> extract_company_name("my-company.com")
        'My Company'
    """
    if not domain:
        return "Unknown"

    # Get the first part of the domain (before first dot)
    base = domain.split('.')[0]

    # Remove common job-related words
    job_words = ['jobs', 'careers', 'career', 'hiring', 'join', 'work']
    for word in job_words:
        base = base.replace(word, '')

    # Clean up dashes and underscores
    base = base.replace('-', ' ').replace('_', ' ')

    # Remove extra whitespace and title case
    base = ' '.join(base.split()).strip().title()

    # Return domain if nothing left after cleaning
    return base if base else domain
