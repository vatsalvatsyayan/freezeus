# src/db/supabase_client.py
import os
from typing import Any, Dict, List
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load the same configs/.env as the rest of your project
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# Turn ON by default; you can disable with SUPABASE_ENABLED=0 in configs/.env
SUPABASE_ENABLED = os.getenv("SUPABASE_ENABLED", "1") not in {"0", "false", "False"}
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
JOBS_TABLE = os.getenv("SUPABASE_JOBS_TABLE", "jobs")

_client = None

def _log(msg: str):
    print(f"[SUPABASE] {msg}", flush=True)

def _init_client():
    """
    Lazily create a singleton Supabase client.

    Returns:
        client instance or None if disabled / misconfigured.
    """
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_ENABLED:
        _log("disabled via SUPABASE_ENABLED")
        return None

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        _log("disabled: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")
        return None

    try:
        # pip package name is `supabase`
        from supabase import create_client, Client  # type: ignore
    except ImportError:
        _log("supabase client not installed. Run: pip install supabase")
        return None

    _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    _log(f"client initialized for {SUPABASE_URL}")
    return _client

def get_supabase():
    """Convenience wrapper used by other modules."""
    return _init_client()

def is_supabase_enabled() -> bool:
    """True if a client can be created and used."""
    return _init_client() is not None

def upsert_jobs_for_page(cleaned_page: Dict[str, Any], domain: str) -> None:
    """
    Push all jobs from one LLM-cleaned page into Supabase.

    cleaned_page looks like:
      {
        "source_url": "...",
        "page_title": "...",
        "jobs": [ { ... per-job fields ... } ]
      }

    - Uses job_url as unique key (on_conflict).
    - If job_url is missing, that job is skipped.
    - Tracks first_seen_at (only for new jobs) and last_seen_at (updated on every crawl).
    - Extracts data from JSONB fields (raw_extra, raw_job) to main columns.
    """
    client = _init_client()
    if client is None:
        return

    source_url = cleaned_page.get("source_url") or ""
    page_title = cleaned_page.get("page_title") or ""
    jobs = cleaned_page.get("jobs") or []

    rows: List[Dict[str, Any]] = []
    current_time = datetime.now(timezone.utc).isoformat()
    skipped = 0

    for j in jobs:
        if not isinstance(j, dict):
            continue

        job_url = j.get("job_url")

        # Skip only if completely missing (per user preference: insert with warning)
        if not job_url:
            _log(f"Skipping job without URL: {j.get('title', 'Unknown')}")
            skipped += 1
            continue

        # Warn about incomplete URLs but still insert them
        if not job_url.startswith('http'):
            _log(f"⚠️  WARNING: Job has incomplete URL (will still insert): {job_url}")

        # Check if job exists (to preserve first_seen_at)
        is_new = True
        existing_first_seen = None
        try:
            existing = client.table(JOBS_TABLE) \
                .select("job_url, first_seen_at") \
                .eq("job_url", job_url) \
                .limit(1) \
                .execute()
            is_new = len(existing.data) == 0
            # Preserve existing first_seen_at to avoid race conditions
            if not is_new and existing.data[0].get('first_seen_at'):
                existing_first_seen = existing.data[0]['first_seen_at']
        except Exception as e:
            _log(f"Error checking existing job: {e}")
            is_new = False  # Safer: don't set first_seen_at if check fails

        # Extract from JSONB
        raw_extra = j.get("extra") or {}

        row: Dict[str, Any] = {
            "job_url": job_url,
            "title": j.get("title"),
            "company": j.get("company") or None,
            "location": j.get("location"),

            # NEW: Country field
            "country": j.get("country") or "Unknown",

            "team_or_category": j.get("team_or_category"),
            "employment_type": j.get("employment_type"),
            "office_or_remote": j.get("office_or_remote"),
            "seniority_level": j.get("seniority_level"),
            "seniority_bucket": j.get("seniority_bucket") or "unknown",

            # Date tracking
            "date_posted_raw": j.get("date_posted"),
            "last_seen_at": current_time,

            # Extract from JSONB
            "job_description": raw_extra.get("job_description") or j.get("job_description"),
            "weekly_hours": raw_extra.get("weekly_hours"),
            "apply_url": raw_extra.get("apply_url"),
            "job_id": raw_extra.get("job_id"),
            "role_number": raw_extra.get("role_number"),

            # Source tracking
            "source_domain": domain,
            "source_page_url": source_url,
            "source_page_title": page_title,

            # Raw storage
            "raw_extra": raw_extra,
            "raw_job": j,
        }

        # Set first_seen_at: new jobs get current time, existing jobs preserve original
        if is_new:
            row["first_seen_at"] = current_time
        elif existing_first_seen:
            # Preserve existing first_seen_at to prevent race condition overwrites
            row["first_seen_at"] = existing_first_seen

        rows.append(row)

    if not rows:
        if skipped > 0:
            _log(f"{domain}: skipped all {skipped} jobs (no valid URLs) for page '{page_title}'")
        else:
            _log(f"{domain}: no rows to upsert for page '{page_title}' ({source_url})")
        return

    try:
        # on_conflict=job_url → de-duplicate by job URL
        _log(f"{domain}: upserting {len(rows)} jobs into '{JOBS_TABLE}' (skipped {skipped})")
        client.table(JOBS_TABLE).upsert(rows, on_conflict="job_url").execute()
        _log(f"✅ Successfully upserted {len(rows)} jobs from {domain}")
    except Exception as e:
        # Fail *softly*: we don't want to kill the whole crawl
        _log(f"❌ Upsert error ({domain}): {e}")