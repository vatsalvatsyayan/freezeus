"""
Crawler module for job board scraping.

This module provides multi-site crawling with robust pagination detection,
infinite scroll support, and optional LLM-based job extraction.

Module Structure:
- url_utils: URL parsing, normalization, and path generation
- reducers: HTML reduction scripts (focus and lite versions)
- page_analyzer: Page content analysis and job detection (requires playwright)
- navigation: Browser interaction and page navigation (requires playwright)
- file_manager: File I/O for crawler outputs
- multi_capture: Main crawler orchestration (entry point, requires playwright)
"""

# Export URL utilities directly (no playwright dependency)
from src.crawler.url_utils import (
    domain_of,
    site_dir,
    sha1,
    base_name_for,
    canon_url,
    normalize_url,
)

# Export reducers directly (no playwright dependency)
from src.crawler.reducers import (
    REDUCE_FOCUS_JS,
    REDUCE_LITE_JS,
)

# Export file management functions directly (no playwright dependency)
from src.crawler.file_manager import (
    ensure_type_dirs,
    build_paths,
    write_manifest,
    write_outputs,
    read_urls_from_file,
)


# Lazy loading for playwright-dependent functions
def __getattr__(name):
    """Lazy loading for playwright-dependent functions."""
    # Page analysis functions
    if name in (
        "ordered_job_hrefs",
        "job_list_len",
        "page_text_fingerprint",
        "normalized_url",
        "scroll_height",
        "scroll_to_bottom_until_stable",
        "results_fingerprint",
        "progressed",
        "wait_for_jobs_or_timeout",
    ):
        from src.crawler.page_analyzer import (
            ordered_job_hrefs,
            job_list_len,
            page_text_fingerprint,
            normalized_url,
            scroll_height,
            scroll_to_bottom_until_stable,
            results_fingerprint,
            progressed,
            wait_for_jobs_or_timeout,
        )
        return {
            "ordered_job_hrefs": ordered_job_hrefs,
            "job_list_len": job_list_len,
            "page_text_fingerprint": page_text_fingerprint,
            "normalized_url": normalized_url,
            "scroll_height": scroll_height,
            "scroll_to_bottom_until_stable": scroll_to_bottom_until_stable,
            "results_fingerprint": results_fingerprint,
            "progressed": progressed,
            "wait_for_jobs_or_timeout": wait_for_jobs_or_timeout,
        }[name]

    # Navigation functions
    if name in (
        "snapshot_current",
        "navigate_seed",
        "try_click_load_more",
        "click_next_page",
    ):
        from src.crawler.navigation import (
            snapshot_current,
            navigate_seed,
            try_click_load_more,
            click_next_page,
        )
        return {
            "snapshot_current": snapshot_current,
            "navigate_seed": navigate_seed,
            "try_click_load_more": try_click_load_more,
            "click_next_page": click_next_page,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # URL utilities (no playwright dependency)
    "domain_of",
    "site_dir",
    "sha1",
    "base_name_for",
    "canon_url",
    "normalize_url",
    # Reducers (no playwright dependency)
    "REDUCE_FOCUS_JS",
    "REDUCE_LITE_JS",
    # Page analysis (require playwright - lazy loaded)
    "ordered_job_hrefs",
    "job_list_len",
    "page_text_fingerprint",
    "normalized_url",
    "scroll_height",
    "scroll_to_bottom_until_stable",
    "results_fingerprint",
    "progressed",
    "wait_for_jobs_or_timeout",
    # Navigation (require playwright - lazy loaded)
    "snapshot_current",
    "navigate_seed",
    "try_click_load_more",
    "click_next_page",
    # File management (no playwright dependency)
    "ensure_type_dirs",
    "build_paths",
    "write_manifest",
    "write_outputs",
    "read_urls_from_file",
]
