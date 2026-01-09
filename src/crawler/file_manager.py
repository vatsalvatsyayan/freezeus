"""
File I/O management for crawler outputs.

This module handles saving HTML files, metadata, manifests, and organizing
crawler outputs into structured directories.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any

from src.crawler.url_utils import site_dir, base_name_for, sha1


# Directory structure for outputs
TYPE_DIRS = {
    "full": "full",
    "focus": "reduced_focus",
    "lite": "reduced_lite",
    "meta": "meta",
    "signals": "signals",
}


def ensure_type_dirs(domain: str) -> Dict[str, Path]:
    """
    Create all required output subdirectories for a domain.

    Args:
        domain: Domain name

    Returns:
        Dictionary mapping type names to Path objects

    Example:
        >>> dirs = ensure_type_dirs("example.com")
        >>> dirs["full"]
        Path('out/example.com/full')
        >>> dirs["focus"]
        Path('out/example.com/reduced_focus')
    """
    root = site_dir(domain)
    out: Dict[str, Path] = {}
    for k, sub in TYPE_DIRS.items():
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        out[k] = d
    # also ensure LLM dir exists (output lives there)
    (root / "llm").mkdir(parents=True, exist_ok=True)
    return out


def build_paths(domain: str, base: str, page_id: str) -> Dict[str, Path]:
    """
    Build file paths for all output types for a page.

    Args:
        domain: Domain name
        base: Base filename (from base_name_for)
        page_id: Page identifier (e.g., "p001", "p002", "expanded")

    Returns:
        Dictionary mapping type names to full file paths

    Example:
        >>> paths = build_paths("example.com", "careers__a1b2c3d4", "p001")
        >>> paths["full"]
        Path('out/example.com/full/careers__a1b2c3d4.p001.html')
        >>> paths["meta"]
        Path('out/example.com/meta/careers__a1b2c3d4.p001.json')
    """
    dirs = ensure_type_dirs(domain)
    return {
        "full": dirs["full"] / f"{base}.{page_id}.html",
        "focus": dirs["focus"] / f"{base}.{page_id}.html",
        "lite": dirs["lite"] / f"{base}.{page_id}.html",
        "meta": dirs["meta"] / f"{base}.{page_id}.json",
        "signals": dirs["signals"] / f"{base}.{page_id}.json",
    }


def write_manifest(
    domain: str,
    seed_base: str,
    entries: List[Dict[str, Any]],
    mode: str,
    stop_reason: str,
    cfg: Dict[str, Any]
) -> None:
    """
    Write a manifest JSON file summarizing a crawl session.

    The manifest tracks all pages captured, their file paths, counts, and metadata.

    Args:
        domain: Domain name
        seed_base: Base name of the seed URL
        entries: List of page entry dictionaries
        mode: Crawl mode (e.g., "pagination", "infinite_scroll")
        stop_reason: Why the crawl stopped
        cfg: Configuration parameters used

    Example:
        >>> entries = [
        ...     {"page_id": "p001", "files": {...}, "counts": {...}, "ts": 1234567890},
        ...     {"page_id": "p002", "files": {...}, "counts": {...}, "ts": 1234567900},
        ... ]
        >>> write_manifest("example.com", "careers__hash", entries, "pagination", "pages_cap", {"pages_max": 3})
    """
    root = site_dir(domain)
    # Convert Path objects to strings for JSON serialization
    for e in entries:
        if "files" in e:
            e["files"] = {k: str(v) for k, v in e["files"].items()}

    manifest = {
        "seed_base": seed_base,
        "mode": mode,
        "stop_reason": stop_reason,
        "pages": entries,
        "config": cfg,
        "ts": int(time.time())
    }

    manifest_path = root / f"{seed_base}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        "utf-8"
    )


def write_outputs(
    domain: str,
    url: str,
    full_html: str,
    red_focus: str,
    red_lite: str,
    signals: List[Any],
    meta: Dict[str, Any],
    page_id: str
) -> Dict[str, Path]:
    """
    Write all output files for a single page capture.

    Saves full HTML, reduced versions, metadata, and signals to disk.

    Args:
        domain: Domain name
        url: Page URL
        full_html: Complete HTML content
        red_focus: Focused reduction (job-heavy containers)
        red_lite: Lite reduction (scripts/styles stripped)
        signals: Scoring signals from reduction
        meta: Page metadata
        page_id: Page identifier

    Returns:
        Dictionary of file paths written

    Example:
        >>> paths = write_outputs(
        ...     "example.com",
        ...     "https://example.com/careers",
        ...     "<html>...</html>",
        ...     "<html>...reduced...</html>",
        ...     "<html>...lite...</html>",
        ...     [{"score": 25, "hasJobLinks": True}],
        ...     {"title": "Careers", "url": "https://example.com/careers"},
        ...     "p001"
        ... )
        >>> paths["full"].exists()
        True
    """
    title = (meta.get("reduce_meta") or {}).get("title") or meta.get("title")
    base = base_name_for(url, title)
    paths = build_paths(domain, base, page_id)

    # Enrich metadata
    meta = dict(meta or {})
    meta["sha1"] = sha1(full_html or "")
    meta["url"] = url
    meta["page_id"] = page_id

    # Write all files
    paths["full"].write_text(full_html or "", "utf-8")
    paths["focus"].write_text(red_focus or "", "utf-8")
    paths["lite"].write_text(red_lite or "", "utf-8")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")

    if signals:
        paths["signals"].write_text(json.dumps(signals, ensure_ascii=False, indent=2), "utf-8")

    print(f"[saved] {domain}  {paths['full'].name}")
    return paths


def read_urls_from_file(path: Path) -> List[str]:
    """
    Read URLs from a text file, one per line.

    Filters out comments (lines starting with #) and duplicates.

    Args:
        path: Path to text file with URLs

    Returns:
        List of unique URLs

    Example:
        >>> urls = read_urls_from_file(Path("urls.txt"))
        >>> len(urls)
        15
        >>> urls[0]
        'https://example.com/careers'
    """
    out: List[str] = []
    for line in path.read_text("utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)

    # Deduplicate while preserving order
    seen = set()
    dedup: List[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup
