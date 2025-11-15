# src/db/supabase_client.py
import os
from typing import Any, Dict, List
from pathlib import Path

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
    """
    client = _init_client()
    if client is None:
        return

    source_url = cleaned_page.get("source_url") or ""
    page_title = cleaned_page.get("page_title") or ""
    jobs = cleaned_page.get("jobs") or []

    rows: List[Dict[str, Any]] = []
    for j in jobs:
        if not isinstance(j, dict):
            continue

        job_url = j.get("job_url")
        if not job_url:
            # No stable URL → can't use as unique key; skip
            continue

        row: Dict[str, Any] = {
            "job_url": job_url,
            "title": j.get("title"),
            "company": j.get("company") or None,             # optional, if you add later
            "location": j.get("location"),
            "team_or_category": j.get("team_or_category"),
            "employment_type": j.get("employment_type"),
            "date_posted_raw": j.get("date_posted"),
            "office_or_remote": j.get("office_or_remote"),

            # Match LLM fields: `seniority_level` and `job_description`
            "seniority_level": j.get("seniority_level"),
            "job_description": j.get("job_description"),

            "source_domain": domain,
            "source_page_url": source_url,
            "source_page_title": page_title,

            # Store extra stuff for future experiments
            "raw_extra": j.get("extra") or {},
            "raw_job": j,
        }

        rows.append(row)

    if not rows:
        _log(f"{domain}: no rows to upsert for page '{page_title}' ({source_url})")
        return

    try:
        # on_conflict=job_url → de-duplicate by job URL
        _log(f"{domain}: upserting {len(rows)} jobs into '{JOBS_TABLE}'")
        client.table(JOBS_TABLE).upsert(rows, on_conflict="job_url").execute()
    except Exception as e:
        # Fail *softly*: we don't want to kill the whole crawl
        _log(f"upsert error ({domain}): {e}")