"""
Crawler module for job board scraping.

This module provides multi-site crawling with robust pagination detection,
infinite scroll support, and optional LLM-based job extraction.

Module Structure:
- url_utils: URL parsing, normalization, and path generation
- reducers: HTML reduction scripts (focus and lite versions)
- page_analyzer: Page content analysis and job detection
- navigation: Browser interaction and page navigation
- file_manager: File I/O for crawler outputs
- multi_capture: Main crawler orchestration (entry point)
"""

# Export URL utilities
from src.crawler.url_utils import (
    domain_of,
    site_dir,
    sha1,
    base_name_for,
    canon_url,
    normalize_url,
)

# Export reducers
from src.crawler.reducers import (
    REDUCE_FOCUS_JS,
    REDUCE_LITE_JS,
)

# Export page analysis functions
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

# Export navigation functions
from src.crawler.navigation import (
    snapshot_current,
    navigate_seed,
    try_click_load_more,
    click_next_page,
)

# Export file management functions
from src.crawler.file_manager import (
    ensure_type_dirs,
    build_paths,
    write_manifest,
    write_outputs,
    read_urls_from_file,
)

__all__ = [
    # URL utilities
    "domain_of",
    "site_dir",
    "sha1",
    "base_name_for",
    "canon_url",
    "normalize_url",
    # Reducers
    "REDUCE_FOCUS_JS",
    "REDUCE_LITE_JS",
    # Page analysis
    "ordered_job_hrefs",
    "job_list_len",
    "page_text_fingerprint",
    "normalized_url",
    "scroll_height",
    "scroll_to_bottom_until_stable",
    "results_fingerprint",
    "progressed",
    "wait_for_jobs_or_timeout",
    # Navigation
    "snapshot_current",
    "navigate_seed",
    "try_click_load_more",
    "click_next_page",
    # File management
    "ensure_type_dirs",
    "build_paths",
    "write_manifest",
    "write_outputs",
    "read_urls_from_file",
]
