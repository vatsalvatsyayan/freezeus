"""
Page analysis functions for crawler.

This module provides functions to analyze page content, detect job listings,
and track page changes during crawling.
"""

import re
from typing import List, Tuple, Dict, Any
from playwright.async_api import Page

from src.crawler.url_utils import sha1, canon_url, domain_of
from src.core.error_logger import get_error_logger
from src.core.error_models import ErrorComponent, ErrorSeverity, ErrorType, ErrorStage


# Regex to detect job-related keywords
KEYWORD_RE = re.compile(
    r"(job|jobs|career|opening|openings|position|positions|role|roles|req|requisition|opportunit)",
    re.I
)


async def ordered_job_hrefs(page: Page, seed_url: str, cap: int = 200) -> List[str]:
    """
    Extract job-related links from the page in document order.

    Searches for links containing job-related keywords in href or text.

    Args:
        page: Playwright page instance
        seed_url: Base URL for resolving relative links
        cap: Maximum number of links to return (default: 200)

    Returns:
        List of canonical job URLs

    Example:
        >>> hrefs = await ordered_job_hrefs(page, "https://example.com/careers")
        >>> len(hrefs)
        25
    """
    anchors = await page.eval_on_selector_all(
        "main a[href], article a[href], section a[href], div a[href]",
        "els => els.map(a => ({href:a.getAttribute('href')||'',text:a.innerText||''}))"
    )
    out: List[str] = []
    for a in anchors:
        href = (a.get("href") or "").strip()
        text = (a.get("text") or "").strip()
        if not href:
            continue
        if KEYWORD_RE.search(href) or KEYWORD_RE.search(text):
            cu = canon_url(seed_url, href)
            if cu:
                out.append(cu)
                if len(out) >= cap:
                    break
    return out


async def job_list_len(page: Page) -> int:
    """
    Estimate the number of job listings on the page.

    Counts listitem roles, articles, or card-like divs.

    Args:
        page: Playwright page instance

    Returns:
        Estimated count of job listings

    Example:
        >>> count = await job_list_len(page)
        >>> count
        42
    """
    try:
        # Try listitem role first
        li = await page.locator('[role="listitem"]').count()
        if li >= 5:
            return li
        # Fallback to cards/articles
        cards = await page.locator(
            "article, li, div[class*='card'], div[class*='result']"
        ).count()
        return cards
    except Exception:
        return 0


async def page_text_fingerprint(page: Page, cap: int = 50) -> str:
    """
    Create a fingerprint of visible page text for change detection.

    Concatenates text from first N job items and hashes it.

    Args:
        page: Playwright page instance
        cap: Maximum number of elements to include

    Returns:
        SHA1 hash of concatenated text

    Example:
        >>> fp1 = await page_text_fingerprint(page)
        >>> # User clicks "Load More"
        >>> fp2 = await page_text_fingerprint(page)
        >>> fp1 != fp2  # Content changed
        True
    """
    try:
        texts = await page.eval_on_selector_all(
            "main [role='listitem'], main article, main li, section [role='listitem'], section article",
            f"els => els.slice(0,{cap}).map(e => (e.innerText||'').trim()).join('\\n\\n')"
        )
        return sha1(texts or "")
    except Exception:
        return ""


async def normalized_url(page: Page) -> str:
    """
    Get the current page URL with tracking parameters removed.

    Args:
        page: Playwright page instance

    Returns:
        Normalized URL string

    Example:
        >>> url = await normalized_url(page)
        >>> url
        'https://example.com/careers/engineering'
    """
    try:
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        u = urlparse(page.url)
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
        return page.url


async def scroll_height(page: Page) -> int:
    """
    Get the total scrollable height of the page.

    Args:
        page: Playwright page instance

    Returns:
        Height in pixels

    Example:
        >>> height = await scroll_height(page)
        >>> height
        3500
    """
    try:
        return await page.evaluate(
            "()=>(document.scrollingElement||document.documentElement).scrollHeight|0"
        )
    except Exception:
        return 0


async def scroll_to_bottom_until_stable(
    page: Page,
    max_rounds: int = 20,
    wait_ms: int = 800,
    min_delta: int = 200
) -> None:
    """
    Scroll to bottom repeatedly until page height stops growing.

    Triggers infinite scroll / lazy load behavior on pages like Dropbox careers.

    Args:
        page: Playwright page instance
        max_rounds: Maximum number of scroll attempts
        wait_ms: Milliseconds to wait between scrolls
        min_delta: Minimum height increase to continue scrolling

    Example:
        >>> await scroll_to_bottom_until_stable(page)
        # Page is now fully loaded with all dynamic content
    """
    try:
        last_h = await scroll_height(page)
        stable_rounds = 0

        for _ in range(max_rounds):
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(wait_ms)

            new_h = await scroll_height(page)
            delta = new_h - last_h

            if delta < min_delta:
                stable_rounds += 1
                if stable_rounds >= 2:
                    # Height stable for 2 rounds, done
                    break
            else:
                # Height increased significantly, reset counter
                stable_rounds = 0

            last_h = new_h
    except Exception:
        pass  # Silently fail, page might not support scrolling


async def results_fingerprint(page: Page, seed_url: str) -> Dict[str, Any]:
    """
    Create a comprehensive fingerprint of page state for change detection.

    Combines URL, text fingerprint, job count, and scroll height.

    Args:
        page: Playwright page instance
        seed_url: Base URL for resolving relative links

    Returns:
        Dictionary with fingerprint components

    Example:
        >>> before = await results_fingerprint(page, seed_url)
        >>> # User clicks "Load More"
        >>> after = await results_fingerprint(page, seed_url)
        >>> progressed(before, after)
        (True, ['text_changed', 'more_jobs'])
    """
    try:
        url_tuple = await normalized_url(page)
        text_fp = await page_text_fingerprint(page, cap=50)
        job_count = len(await ordered_job_hrefs(page, seed_url, cap=60))
        sh = await scroll_height(page)

        return {
            "url": url_tuple,
            "text_fp": text_fp,
            "job_count": job_count,
            "scroll_h": sh,
        }
    except Exception:
        return {
            "url": page.url,
            "text_fp": "",
            "job_count": 0,
            "scroll_h": 0,
        }


def progressed(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Detect if page content has meaningfully changed.

    Compares fingerprints to determine if new content appeared
    (pagination, infinite scroll, load more, etc).

    Args:
        before: Fingerprint before action
        after: Fingerprint after action

    Returns:
        Tuple of (changed, list of reasons)

    Example:
        >>> before = {"url": "page1", "job_count": 20, "text_fp": "abc123"}
        >>> after = {"url": "page2", "job_count": 20, "text_fp": "abc123"}
        >>> progressed(before, after)
        (True, ['url_changed'])

        >>> after = {"url": "page1", "job_count": 40, "text_fp": "def456"}
        >>> progressed(before, after)
        (True, ['text_changed', 'more_jobs'])
    """
    reasons: List[str] = []

    # URL changed (pagination)
    if before.get("url") != after.get("url"):
        reasons.append("url_changed")

    # Text content changed (new jobs loaded)
    if before.get("text_fp") != after.get("text_fp"):
        reasons.append("text_changed")

    # More jobs detected
    if after.get("job_count", 0) > before.get("job_count", 0):
        reasons.append("more_jobs")

    # Page height increased significantly
    if after.get("scroll_h", 0) > before.get("scroll_h", 0) + 500:
        reasons.append("scroll_grew")

    return (len(reasons) > 0, reasons)


async def _has_any(page: Page, selectors: List[str]) -> bool:
    """
    Check if any of the given selectors match visible elements.

    Args:
        page: Playwright page instance
        selectors: List of CSS selectors to check

    Returns:
        True if any selector matches a visible element

    Example:
        >>> has_next = await _has_any(page, ['button:has-text("Next")', 'a[rel="next"]'])
        >>> has_next
        True
    """
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                return True
        except Exception:
            continue
    return False


async def wait_for_jobs_or_timeout(
    page: Page,
    seed_url: str,
    max_wait_ms: int = 35000
) -> bool:
    """
    Wait for job listings to appear on the page.

    Tries multiple detection strategies with timeout.

    Args:
        page: Playwright page instance
        seed_url: Base URL for link resolution
        max_wait_ms: Maximum wait time in milliseconds

    Returns:
        True if jobs detected, False if timeout

    Example:
        >>> success = await wait_for_jobs_or_timeout(page, seed_url)
        >>> if success:
        ...     # Jobs are loaded, proceed with extraction
    """
    # Strategy 1: Wait for common job listing selectors
    job_selectors = [
        '[role="listitem"]',
        'article[class*="job"]',
        'div[class*="job-card"]',
        'li[class*="position"]',
        'a[href*="/jobs/"]',
    ]

    try:
        for sel in job_selectors:
            try:
                await page.wait_for_selector(sel, timeout=max_wait_ms // len(job_selectors))
                return True
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Check if we found any job-like hrefs
    hrefs = await ordered_job_hrefs(page, seed_url, cap=5)
    if hrefs:
        return True

    # Strategy 3: Check for pagination/navigation (implies jobs exist)
    nav_selectors = [
        'nav button:has-text("Next")',
        'a[rel="next"]',
        'button[aria-label*="Next"]',
    ]
    if await _has_any(page, nav_selectors):
        return True

    # No jobs detected after all strategies - log warning
    get_error_logger().log_error(
        component=ErrorComponent.CRAWLER,
        stage=ErrorStage.WAIT_FOR_JOBS,
        error_type=ErrorType.TIMEOUT,
        domain=domain_of(seed_url),
        url=page.url,
        severity=ErrorSeverity.WARNING,
        message=f"No job listings detected after {max_wait_ms}ms wait",
        metadata={
            "seed_url": seed_url,
            "max_wait_ms": max_wait_ms,
            "page_title": await page.title() if page else "unknown",
        }
    )

    return False
