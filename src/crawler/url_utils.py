"""
URL and path utilities for crawler.

This module handles URL parsing, normalization, canonicalization,
and path/filename generation for crawler outputs.
"""

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode


# Base output directory
BASE_OUT = Path("out")
BASE_OUT.mkdir(exist_ok=True, parents=True)


def domain_of(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: Full URL string

    Returns:
        Lowercase domain name

    Example:
        >>> domain_of("https://example.com/jobs")
        'example.com'
    """
    return urlparse(url).netloc.lower()


def site_dir(domain: str) -> Path:
    """
    Get output directory for a domain, creating it if needed.

    Args:
        domain: Domain name

    Returns:
        Path to domain output directory

    Example:
        >>> site_dir("example.com")
        Path('out/example.com')
    """
    p = BASE_OUT / domain
    p.mkdir(exist_ok=True, parents=True)
    return p


def sha1(text: str) -> str:
    """
    Compute SHA1 hash of text.

    Args:
        text: Text to hash

    Returns:
        Hexadecimal SHA1 hash

    Example:
        >>> sha1("hello")
        'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'
    """
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _slug_last_segment(u: str, fallback: str = "page", max_len: int = 40) -> str:
    """
    Extract and slugify the last URL path segment.

    Removes leading/trailing numbers and normalizes to safe filename characters.

    Args:
        u: URL string
        fallback: Default value if no valid segment found
        max_len: Maximum length of returned slug

    Returns:
        Slugified segment

    Example:
        >>> _slug_last_segment("https://example.com/jobs/engineering")
        'engineering'
        >>> _slug_last_segment("https://example.com/jobs/123-software-456")
        'software'
    """
    segs = [s for s in urlparse(u).path.split('/') if s] or [fallback]
    s = segs[-1]
    # Remove leading numbers
    s = re.sub(r"^\d+[-_]*", "", s)
    # Remove trailing numbers
    s = re.sub(r"[-_]*\d+$", "", s) or fallback
    # Unicode normalization
    s = unicodedata.normalize("NFKD", s).lower()
    # Replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    # Collapse multiple hyphens
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s or fallback)[:max_len]


def _short_hash(u: str) -> str:
    """
    Create a short 8-character hash of a URL.

    Args:
        u: URL string

    Returns:
        8-character hexadecimal hash

    Example:
        >>> _short_hash("https://example.com/jobs")
        'a1b2c3d4'
    """
    return hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]


def base_name_for(url: str, title: Optional[str] = None) -> str:
    """
    Generate a unique base filename for a URL.

    Combines a slugified URL segment (or title) with a short hash for uniqueness.

    Args:
        url: Full URL
        title: Optional page title to use for generic URLs

    Returns:
        Base filename (without extension)

    Example:
        >>> base_name_for("https://example.com/jobs/engineering", "Engineering Jobs")
        'engineering__a1b2c3d4'
        >>> base_name_for("https://example.com/index", "Home Page")
        'home-page__a1b2c3d4'
    """
    seg = _slug_last_segment(url, fallback="index")

    # If segment is generic and we have a title, use the title instead
    if seg in ("index", "page") and title:
        t = unicodedata.normalize("NFKD", title).lower()
        t = re.sub(r"[^a-z0-9\-]+", "-", t)
        seg = (re.sub(r"-{2,}", "-", t).strip("-") or "page")[:40]

    return f"{seg}__{_short_hash(url)}"


def canon_url(seed: str, href: str) -> Optional[str]:
    """
    Canonicalize a URL by removing tracking parameters and normalizing format.

    Resolves relative URLs, removes UTM parameters, lowercases scheme/domain,
    and strips fragments.

    Args:
        seed: Base URL for resolving relative hrefs
        href: URL to canonicalize (can be relative)

    Returns:
        Canonicalized absolute URL, or None if parsing fails

    Example:
        >>> canon_url("https://example.com", "/jobs?utm_source=twitter#apply")
        'https://example.com/jobs'
        >>> canon_url("https://example.com/careers", "../jobs/123")
        'https://example.com/jobs/123'
    """
    try:
        # Resolve to absolute URL
        absu = urljoin(seed, href)
        u = urlparse(absu)

        # Filter out tracking parameters
        qs = [
            (k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
            if k.lower() not in {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "gclid", "fbclid"
            }
        ]

        # Rebuild URL with normalized parts
        newu = u._replace(query=urlencode(qs), fragment="")
        return urlunparse((
            newu.scheme.lower(),
            newu.netloc.lower(),
            newu.path,
            newu.params,
            newu.query,
            ""
        ))
    except Exception:
        return None


def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing tracking parameters.

    Similar to canon_url but works on absolute URLs without a seed.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL, or original if parsing fails

    Example:
        >>> normalize_url("https://example.com/jobs?utm_source=email&page=2")
        'https://example.com/jobs?page=2'
    """
    try:
        u = urlparse(url)
        qs = [
            (k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
            if k.lower() not in {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "gclid", "fbclid"
            }
        ]
        return urlunparse((
            u.scheme.lower(),
            u.netloc.lower(),
            u.path,
            u.params,
            urlencode(qs),
            ""
        ))
    except Exception:
        return url
