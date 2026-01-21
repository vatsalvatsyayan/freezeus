# src/db/supabase_client.py
import os
from typing import Any, Dict, List
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from pydantic import ValidationError
from typing import Optional
from src.core.logging import get_logger
from src.core.error_logger import get_error_logger
from src.core.error_models import ErrorComponent, ErrorSeverity, ErrorType, ErrorStage
from src.core.process_logger import get_process_logger
from src.core.process_models import ProcessStep
from src.db.models import JobPosting, JobRecord, PageData
from src.utils.url_utils import extract_company_name

# Load the same configs/.env as the rest of your project
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# Initialize logger for this module
logger = get_logger(__name__)

# Turn ON by default; you can disable with SUPABASE_ENABLED=0 in configs/.env
SUPABASE_ENABLED = os.getenv("SUPABASE_ENABLED", "1") not in {"0", "false", "False"}
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
JOBS_TABLE = os.getenv("SUPABASE_JOBS_TABLE", "jobs")

_client = None

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
        logger.info("Supabase disabled via SUPABASE_ENABLED")
        return None

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase disabled: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")
        return None

    try:
        # pip package name is `supabase`
        from supabase import create_client, Client  # type: ignore
    except ImportError:
        logger.error("Supabase client not installed. Run: pip install supabase")
        return None

    _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info(f"Supabase client initialized for {SUPABASE_URL}")
    return _client

def get_supabase():
    """Convenience wrapper used by other modules."""
    return _init_client()

def is_supabase_enabled() -> bool:
    """True if a client can be created and used."""
    return _init_client() is not None

def upsert_jobs_for_page(cleaned_page: Dict[str, Any], domain: str, run_id: Optional[str] = None, company: Optional[str] = None) -> None:
    """
    Push all jobs from one LLM-cleaned page into Supabase with Pydantic validation.

    cleaned_page looks like:
      {
        "source_url": "...",
        "page_title": "...",
        "jobs": [ { ... per-job fields ... } ]
      }

    - Uses job_url as unique key (on_conflict).
    - Validates jobs using Pydantic models before insertion.
    - If job_url is missing or validation fails, that job is skipped.
    - Tracks first_seen_at (only for new jobs) and last_seen_at (updated on every crawl).
    - Extracts data from JSONB fields (raw_extra, raw_job) to main columns.

    Args:
        cleaned_page: Page data with jobs list
        domain: Source domain name
        run_id: Optional run ID for process logging correlation
        company: Optional company name for logging

    Returns:
        None
    """
    client = _init_client()
    if client is None:
        return

    # Validate page data structure
    try:
        page_data = PageData(**cleaned_page)
    except ValidationError as e:
        logger.error(f"Page data validation failed for {domain}: {e}")
        get_error_logger().log_exception(
            e,
            component=ErrorComponent.DATABASE,
            stage=ErrorStage.VALIDATE_PAGE,
            domain=domain,
            url=cleaned_page.get("source_url", ""),
            severity=ErrorSeverity.ERROR,
            error_type=ErrorType.VALIDATION_ERROR,
            metadata={
                "page_title": cleaned_page.get("page_title"),
                "jobs_count": len(cleaned_page.get("jobs", [])),
            }
        )
        return

    source_url = page_data.source_url
    page_title = page_data.page_title
    jobs = page_data.jobs

    rows: List[Dict[str, Any]] = []
    current_time = datetime.now(timezone.utc).isoformat()
    skipped = 0
    validation_errors = 0

    for idx, job_dict in enumerate(jobs):
        if not isinstance(job_dict, dict):
            logger.debug(f"Skipping non-dict job at index {idx}")
            skipped += 1
            continue

        # Validate job using Pydantic model
        try:
            job = JobPosting(**job_dict)
        except ValidationError as e:
            logger.warning(f"Job validation failed for {job_dict.get('title', 'Unknown')}: {e}")
            get_error_logger().log_exception(
                e,
                component=ErrorComponent.DATABASE,
                stage=ErrorStage.VALIDATE_JOB,
                domain=domain,
                url=source_url,
                severity=ErrorSeverity.WARNING,
                error_type=ErrorType.VALIDATION_ERROR,
                include_stack_trace=False,  # Expected error, no stack needed
                metadata={
                    "job_title": job_dict.get("title"),
                    "job_url": job_dict.get("job_url"),
                    "page_title": page_title,
                }
            )
            validation_errors += 1
            skipped += 1
            continue

        job_url = job.job_url

        # Warn about incomplete URLs but still insert them
        if not job_url.startswith('http'):
            logger.warning(f"Job has incomplete URL (will still insert): {job_url}")

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
            logger.error(f"Error checking existing job: {e}")
            get_error_logger().log_exception(
                e,
                component=ErrorComponent.DATABASE,
                stage=ErrorStage.CHECK_EXISTING,
                domain=domain,
                url=source_url,
                severity=ErrorSeverity.WARNING,
                error_type=ErrorType.DB_QUERY_ERROR,
                metadata={"job_url": job_url, "page_title": page_title}
            )
            is_new = False  # Safer: don't set first_seen_at if check fails

        # Use JobRecord to construct validated database row
        job_record = JobRecord.from_job_posting(
            job=job,
            domain=domain,
            source_url=source_url,
            page_title=page_title,
            first_seen_at=None,  # Will be set below based on is_new
            last_seen_at=current_time,
        )

        # Convert to dict for database insertion
        row = job_record.model_dump(exclude_none=True)

        # Set first_seen_at: new jobs get current time, existing jobs preserve original
        if is_new:
            row["first_seen_at"] = current_time
        elif existing_first_seen:
            # Preserve existing first_seen_at to prevent race condition overwrites
            row["first_seen_at"] = existing_first_seen

        rows.append(row)

    if not rows:
        if validation_errors > 0:
            logger.warning(
                f"{domain}: skipped all {skipped} jobs "
                f"({validation_errors} validation errors) for page '{page_title}'"
            )
        elif skipped > 0:
            logger.warning(f"{domain}: skipped all {skipped} jobs (no valid data) for page '{page_title}'")
        else:
            logger.info(f"{domain}: no rows to upsert for page '{page_title}' ({source_url})")
        return

    try:
        # on_conflict=job_url → de-duplicate by job URL
        log_msg = f"{domain}: upserting {len(rows)} jobs into '{JOBS_TABLE}'"
        if skipped > 0:
            log_msg += f" (skipped {skipped}"
            if validation_errors > 0:
                log_msg += f", {validation_errors} validation errors"
            log_msg += ")"
        logger.info(log_msg)

        client.table(JOBS_TABLE).upsert(rows, on_conflict="job_url").execute()
        logger.info(f"Successfully upserted {len(rows)} jobs from {domain}")

        # Log Step 6: DB_COMPLETE
        if run_id:
            company_name = company or extract_company_name(domain)
            get_process_logger().log_step(
                run_id=run_id,
                step=ProcessStep.DB_COMPLETE,
                company=company_name,
                domain=domain,
                metadata={"jobs_saved": len(rows), "skipped": skipped, "validation_errors": validation_errors}
            )
    except Exception as e:
        # Fail *softly*: we don't want to kill the whole crawl
        logger.error(f"Upsert error ({domain}): {e}")
        get_error_logger().log_exception(
            e,
            component=ErrorComponent.DATABASE,
            stage=ErrorStage.UPSERT_JOBS,
            domain=domain,
            url=source_url,
            severity=ErrorSeverity.ERROR,
            error_type=ErrorType.DB_UPSERT_ERROR,
            metadata={
                "page_title": page_title,
                "jobs_count": len(rows),
                "skipped": skipped,
                "validation_errors": validation_errors,
                "table": JOBS_TABLE,
            }
        )