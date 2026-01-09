"""
Page navigation and interaction functions for crawler.

This module handles browser interactions like clicking buttons,
scrolling, and navigating between pages.
"""

import re
import random
from typing import Tuple, List, Dict, Any
from playwright.async_api import Page

from src.crawler.reducers import REDUCE_FOCUS_JS, REDUCE_LITE_JS


async def snapshot_current(page: Page) -> Tuple[str, str, str, List[Any], Dict[str, Any]]:
    """
    Capture current page state without navigation.

    Takes a snapshot of the full HTML and reduced versions.

    Args:
        page: Playwright page instance

    Returns:
        Tuple of (full_html, reduced_focus_html, reduced_lite_html, signals, meta)

    Example:
        >>> full, focus, lite, signals, meta = await snapshot_current(page)
        >>> len(full) > len(focus) > len(lite)
        True
    """
    # Wait for network to stabilize
    for t in (20_000, 8_000):
        try:
            await page.wait_for_load_state("networkidle", timeout=t)
        except Exception:
            pass

    try:
        full_html = await page.content()
    except Exception:
        full_html = ""

    # Run reduction scripts
    try:
        result = await page.evaluate(REDUCE_FOCUS_JS)
        red_focus = result.get("reduced_html", "")
        signals = result.get("kept_signals", [])
        meta = result.get("meta", {})
    except Exception:
        red_focus = ""
        signals = []
        meta = {}

    try:
        red_lite = await page.evaluate(REDUCE_LITE_JS)
    except Exception:
        red_lite = ""

    # Add metadata
    meta["title"] = await page.title()
    meta["url"] = page.url

    return full_html, red_focus, red_lite, signals, meta


async def navigate_seed(page: Page, url: str) -> Tuple[str, str, str, List[Any], Dict[str, Any]]:
    """
    Navigate to a seed URL and capture its content.

    Handles navigation with retries and waits for page load.

    Args:
        page: Playwright page instance
        url: URL to navigate to

    Returns:
        Tuple of (full_html, reduced_focus_html, reduced_lite_html, signals, meta)

    Example:
        >>> full, focus, lite, sigs, meta = await navigate_seed(page, "https://example.com/jobs")
        >>> meta['title']
        'Careers at Example'
    """
    max_retries = 3
    nav_timeout_ms = 45_000

    for attempt in range(max_retries):
        try:
            print(f"[nav] {url} (attempt {attempt + 1}/{max_retries})")
            await page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
            await page.wait_for_timeout(random.randint(1200, 2000))
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[nav error] Failed to load {url} after {max_retries} attempts: {e}")
                return "", "", "", [], {"error": str(e), "url": url}
            await page.wait_for_timeout(random.randint(2000, 4000))

    return await snapshot_current(page)


async def try_click_load_more(page: Page) -> bool:
    """
    Attempt to click a "Load More" button if present.

    Tries multiple common button patterns.

    Args:
        page: Playwright page instance

    Returns:
        True if button was clicked, False otherwise

    Example:
        >>> clicked = await try_click_load_more(page)
        >>> if clicked:
        ...     # More content should now be loading
    """
    # Common "Load More" button patterns
    candidates = [
        'button:has-text("Load more")',
        'button:has-text("Show more")',
        'button:has-text("Load More")',
        'button:has-text("Show More")',
        'button:has-text("See more")',
        'button:has-text("View more")',
        'a:has-text("Load more")',
        'a:has-text("Show more")',
        '[role="button"]:has-text("Load more")',
        '[role="button"]:has-text("Show more")',
        'button[aria-label*="Load more"]',
        'button[aria-label*="Show more"]',
    ]

    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible() and await loc.is_enabled():
                await loc.click()
                print(f"[click] load-more: {sel}")
                await page.wait_for_timeout(random.randint(1500, 2500))
                return True
        except Exception:
            continue

    return False


async def click_next_page(page: Page) -> bool:
    """
    Attempt to click a "Next" pagination button/link.

    Tries semantic HTML first (ARIA roles), then falls back to CSS selectors.

    Args:
        page: Playwright page instance

    Returns:
        True if navigation succeeded, False otherwise

    Example:
        >>> navigated = await click_next_page(page)
        >>> if navigated:
        ...     # Now on page 2
    """
    # ---- 1) Semantic HTML (ARIA) - preferred approach ----
    try:
        # Try role="link" with name containing "next" (case insensitive)
        for pattern in ["next", "Next", "NEXT", "Next page", "next page"]:
            try:
                link = page.get_by_role("link", name=re.compile(f".*{re.escape(pattern)}.*", re.I)).first
                if await link.count() > 0:
                    if await link.is_visible() and await link.is_enabled():
                        await link.click()
                        print(f"[click] next: role=link name~={pattern}")
                        await page.wait_for_timeout(random.randint(900, 1600))
                        return True
            except Exception:
                pass

        # Try role="button" with name containing "next"
        for pattern in ["next", "Next", "NEXT", "Next page", "next page"]:
            try:
                link = page.get_by_role("button", name=re.compile(f".*{re.escape(pattern)}.*", re.I)).first
                if await link.count() > 0:
                    if await link.is_visible() and await link.is_enabled():
                        await link.click()
                        print("[click] next: role=button name~=next")
                        await page.wait_for_timeout(random.randint(900, 1600))
                        return True
            except Exception:
                pass
    except Exception:
        pass

    # ---- 2) CSS fallbacks (older sites, non-semantic markup) ----
    candidates = [
        # aria-label / rel based
        'button[aria-label*="Next"]',
        'a[aria-label*="Next"]',
        '[role="button"][aria-label*="Next"]',
        'a[rel="next"]',

        # explicit "Next page" / "Next results"
        'button[aria-label*="Next page"]',
        'a[aria-label*="Next page"]',
        'button[aria-label*="Next results"]',
        'a[aria-label*="Next results"]',

        # generic nav arrows
        'nav button:has-text(">")',
        'nav a:has-text(">")',
        'nav button:has-text("›")',
        'nav a:has-text("›")',
        'nav button:has-text("»")',
        'nav a:has-text("»")',
    ]

    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible() and await loc.is_enabled():
                await loc.click()
                print(f"[click] next: {sel}")
                await page.wait_for_timeout(random.randint(900, 1600))
                return True
        except Exception:
            continue

    return False
