"""
Job extraction orchestration from HTML using LLM.

This module coordinates the entire extraction pipeline:
HTML → LLM → JSON → Normalize → Dedupe → Write → Database
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from src.core.logging import get_logger
from src.core.error_logger import get_error_logger
from src.core.error_models import ErrorComponent, ErrorSeverity, ErrorType, ErrorStage
from src.core.process_logger import get_process_logger
from src.core.process_models import ProcessStep
from src.utils.url_utils import normalize_job_url, extract_company_name
from src.llm.parsers import parse_json_robust, normalize_and_dedupe
from src.llm.prompt_loader import load_extraction_prompt
from src.llm.client import call_gemini_with_retries

logger = get_logger(__name__)

# Configuration from environment
MAX_HTML_CHARS = int(os.getenv("LLM_MAX_HTML_CHARS", "250000"))
OVERWRITE = os.getenv("LLM_OVERWRITE", "0") in {"1", "true", "True"}
VERBOSE = os.getenv("LLM_VERBOSE", "1") not in {"0", "false", "False"}

# Supabase integration (optional)
_SUPABASE_IMPORTED_OK = False
_SUPABASE_IMPORT_ERR: Optional[Exception] = None

try:
    from src.db.supabase_client import upsert_jobs_for_page, is_supabase_enabled
    _SUPABASE_IMPORTED_OK = True
except Exception as e:
    _SUPABASE_IMPORTED_OK = False
    _SUPABASE_IMPORT_ERR = e


def _log(msg: str):
    """Internal logging helper."""
    if VERBOSE:
        logger.info(f"[Extractor] {msg}")


def _read_text(path: Path) -> str:
    """Read text file with error handling."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _truncate_html(html_text: str) -> Tuple[str, bool]:
    """Truncate HTML if it exceeds max length."""
    if MAX_HTML_CHARS and len(html_text) > MAX_HTML_CHARS:
        return html_text[:MAX_HTML_CHARS], True
    return html_text, False


def _fix_json_via_model(model_name: str, bad_text: str) -> Optional[Dict[str, Any]]:
    """
    Second-chance: ask model to convert malformed output into valid JSON.

    Args:
        model_name: Gemini model name
        bad_text: Malformed JSON text to fix

    Returns:
        Parsed JSON dict or None if fixing fails
    """
    try:
        fixer_prompt = (
            "You will be given text that should be JSON but may be malformed.\n"
            "Return ONLY valid JSON that conforms to this structure "
            "(omit unknown fields except seniority fields):\n"
            '{ "source_url": "...", "page_title": "...", "jobs": [ '
            '{ "title": "...", "job_url": "...", "company": "...", '
            '"location": "...", "team_or_category": "...", "employment_type": "...", '
            '"date_posted": "...", "requisition_id": "...", "office_or_remote": "...", '
            '"seniority_level": "...", "seniority_bucket": "...", "extra": { } } ] }\n\n'
            "For seniority_bucket use exactly one of: "
            "intern, entry, mid, senior, director_vp, executive, unknown.\n"
            f"Text:\n{bad_text}"
        )

        gen_config = {
            "temperature": 0.0,
            "candidate_count": 1,
            "response_mime_type": "application/json",
        }

        response = call_gemini_with_retries(
            prompt=fixer_prompt,
            model_name=model_name,
            generation_config=gen_config
        )

        txt = (getattr(response, "text", None) or "").strip()
        return parse_json_robust(txt)
    except Exception as e:
        _log(f"JSON fixer failed: {e}")
        return None


def extract_jobs_from_html(
    html_text: str,
    source_url: str = "",
    page_title: str = "",
    model_name: str = None,
    domain: str = "unknown"
) -> Dict[str, Any]:
    """
    Extract jobs from HTML text using LLM.

    Args:
        html_text: HTML content to extract from
        source_url: Source page URL
        page_title: Page title
        model_name: Optional Gemini model name
        domain: Domain name for error logging

    Returns:
        Dict with source_url, page_title, jobs list

    Example:
        >>> result = extract_jobs_from_html("<html>...</html>")
        >>> "jobs" in result
        True
    """
    # Truncate if needed
    html_text, was_trunc = _truncate_html(html_text)
    if was_trunc:
        _log(f"HTML truncated to {len(html_text):,} chars (max={MAX_HTML_CHARS:,})")

    # Load prompt
    prompt_text = load_extraction_prompt()

    # Build full prompt
    prompt = (
        f"{prompt_text}\n\n"
        "Return compact JSON on a single line if possible.\n\n"
        f"=== HTML START ===\n{html_text}\n=== HTML END ===\n"
    )

    # Call LLM
    _log("Calling Gemini API for job extraction")
    try:
        gen_config = {
            "temperature": 0.0,
            "candidate_count": 1,
            "response_mime_type": "application/json",
        }

        response = call_gemini_with_retries(
            prompt=prompt,
            model_name=model_name,
            generation_config=gen_config
        )
        text = (getattr(response, "text", None) or "").strip()

        # Parse JSON
        try:
            data = parse_json_robust(text)
        except Exception as e:
            _log("Primary JSON parse failed, attempting fixer")
            fixed = _fix_json_via_model(model_name, text)
            if fixed is None:
                # Last resort
                _log("JSON fixer failed, returning empty result with error")
                get_error_logger().log_exception(
                    e,
                    component=ErrorComponent.LLM,
                    stage=ErrorStage.PARSE_JSON,
                    domain=domain,
                    url=source_url or "",
                    severity=ErrorSeverity.ERROR,
                    error_type=ErrorType.JSON_ERROR,
                    metadata={
                        "page_title": page_title,
                        "response_preview": text[:500] if text else "",
                        "response_length": len(text) if text else 0,
                    }
                )
                return {
                    "source_url": source_url or "",
                    "page_title": page_title or "",
                    "jobs": [],
                    "error": "LLM returned non-JSON output; all repair attempts failed"
                }
            data = fixed

        # Seed top-level fields
        data.setdefault("source_url", source_url or "")
        data.setdefault("page_title", page_title or "")
        data.setdefault("jobs", [])

        return data

    except Exception as e:
        _log(f"Fatal extraction error: {e}")
        return {
            "source_url": source_url or "",
            "page_title": page_title or "",
            "jobs": [],
            "error": str(e)
        }


def extract_one_focus_html(
    domain_dir: Path,
    focus_html_path: Path,
    source_url: Optional[str] = "",
    page_title: Optional[str] = "",
    run_id: Optional[str] = None,
    company: Optional[str] = None
) -> Path:
    """
    Extract jobs from single HTML file and write to JSON.

    Reads HTML from focus_html_path, extracts jobs using LLM,
    normalizes and deduplicates, writes to domain_dir/llm/*.jobs.json,
    and optionally upserts to Supabase database.

    Args:
        domain_dir: Domain output directory (e.g., out/example.com)
        focus_html_path: Path to reduced_focus HTML file
        source_url: Original source URL
        page_title: Page title
        run_id: Optional run ID for process logging correlation
        company: Optional company name for logging

    Returns:
        Path to written JSON file

    Example:
        >>> out_path = extract_one_focus_html(
        ...     domain_dir=Path("out/example.com"),
        ...     focus_html_path=Path("out/example.com/reduced_focus/page.html")
        ... )
        >>> out_path.exists()
        True
    """
    domain_dir = Path(domain_dir)
    domain_name = str(domain_dir.name)
    company_name = company or extract_company_name(domain_name)
    process_logger = get_process_logger()

    llm_dir = domain_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    base = focus_html_path.stem  # e.g., careers__abcd1234.p001
    out_json = llm_dir / f"{base}.jobs.json"

    # Skip if exists and not overwriting
    if out_json.exists() and not OVERWRITE:
        _log(f"Skipping {out_json.name} (exists). Set LLM_OVERWRITE=1 to recompute.")
        return out_json

    # Read HTML
    _log(f"Reading {focus_html_path.name}")
    html_text = _read_text(focus_html_path)

    # Log Step 4: LLM_START
    if run_id:
        process_logger.log_step(
            run_id=run_id,
            step=ProcessStep.LLM_START,
            company=company_name,
            domain=domain_name,
            metadata={"file": focus_html_path.name, "html_length": len(html_text)}
        )

    # Extract jobs
    _log("Extracting jobs via Gemini API")
    raw = extract_jobs_from_html(html_text, source_url or "", page_title or "", domain=domain_name)

    # Normalize and deduplicate
    _log("Normalizing and deduplicating jobs")
    try:
        cleaned, stats = normalize_and_dedupe(raw)
        _log(
            f"Dedupe stats: in={stats['input_jobs']} → "
            f"out={stats['deduped_out']} (removed {stats['duplicates_removed']})"
        )
    except Exception as e:
        _log(f"Normalization error: {e}. Using unnormalized result.")
        cleaned = {
            "source_url": raw.get("source_url", source_url or ""),
            "page_title": raw.get("page_title", page_title or ""),
            "jobs": raw.get("jobs", []),
            "warning": f"normalize_error: {e}"
        }

    jobs_found = len(cleaned.get('jobs', []))

    # Log Step 5: LLM_COMPLETE
    if run_id:
        process_logger.log_step(
            run_id=run_id,
            step=ProcessStep.LLM_COMPLETE,
            company=company_name,
            domain=domain_name,
            metadata={"jobs_found": jobs_found, "file": out_json.name}
        )

    # URL normalization post-processing
    for job in cleaned.get("jobs", []):
        if job.get("job_url"):
            original = job["job_url"]
            normalized = normalize_job_url(original, source_url, domain_name)
            job["job_url"] = normalized

            if not normalized or not normalized.startswith('http'):
                _log(f"⚠️  WARNING: Incomplete URL: {original} -> {normalized}")

    # Write JSON
    out_json.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _log(f"Wrote {out_json.name}")

    # Supabase integration
    if _SUPABASE_IMPORTED_OK:
        try:
            if is_supabase_enabled():
                job_count = len(cleaned.get('jobs', []))
                _log(f"Upserting {job_count} jobs to Supabase for {domain_name}")
                upsert_jobs_for_page(cleaned, domain=domain_name, run_id=run_id, company=company_name)
            else:
                _log("Supabase disabled or client init failed")
        except Exception as e:
            logger.error(f"Supabase upsert error for {domain_name}: {e}")
            get_error_logger().log_exception(
                e,
                component=ErrorComponent.LLM,
                stage=ErrorStage.UPSERT_FROM_EXTRACTOR,
                domain=domain_name,
                url=source_url,
                severity=ErrorSeverity.WARNING,
                metadata={
                    "page_title": page_title,
                    "jobs_count": len(cleaned.get('jobs', [])),
                    "file": str(focus_html_path),
                }
            )
    else:
        _log(f"Supabase not available: {_SUPABASE_IMPORT_ERR}")

    return out_json


def extract_all_focus_htmls(domain_dir: Path, run_id: Optional[str] = None) -> List[Path]:
    """
    Batch extract jobs from all HTML files in domain directory.

    Walks domain_dir/reduced_focus/*.html and extracts jobs from each.
    Never raises exceptions; continues on errors.

    Args:
        domain_dir: Domain output directory
        run_id: Optional run ID for process logging correlation

    Returns:
        List of written JSON file paths

    Example:
        >>> paths = extract_all_focus_htmls(Path("out/example.com"))
        >>> all(p.suffix == ".json" for p in paths)
        True
    """
    domain_dir = Path(domain_dir)
    domain_name = str(domain_dir.name)
    company_name = extract_company_name(domain_name)

    focus_dir = domain_dir / "reduced_focus"
    meta_dir = domain_dir / "meta"
    llm_dir = domain_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []

    if not focus_dir.exists():
        _log(f"{domain_dir.name}: No reduced_focus/ directory found")
        return written

    files = sorted(focus_dir.glob("*.html"))
    _log(f"{domain_dir.name}: Found {len(files)} HTML files to process")

    for idx, html_file in enumerate(files, 1):
        _log(f"[{idx}/{len(files)}] Processing {html_file.name}")

        # Load metadata if available
        src_url = ""
        page_title = ""
        meta_path = meta_dir / f"{html_file.stem}.json"

        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                src_url = meta.get("url", "") or meta.get("source_url", "")
                page_title = (
                    meta.get("title") or
                    (meta.get("reduce_meta", {}) or {}).get("title", "")
                )
            except Exception as e:
                _log(f"Warning: Failed to read metadata from {meta_path.name}: {e}")

        # Extract jobs
        try:
            out_path = extract_one_focus_html(domain_dir, html_file, src_url, page_title, run_id=run_id, company=company_name)
            written.append(out_path)
        except Exception as e:
            logger.error(f"Unhandled error processing {html_file.name}: {e}. Continuing...")

    _log(f"{domain_dir.name}: Completed. Wrote {len(written)} JSON files.")
    return written
