"""
Centralized process logging system with Supabase integration.

This module provides a fail-safe process logger that:
- Logs process steps to Supabase with structured schema
- Falls back to local file logging on database failures
- Uses Pydantic validation for type safety
- Follows singleton pattern for global access
"""

import os
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dotenv import load_dotenv

from src.core.logging import get_logger
from src.core.process_models import (
    ProcessStep,
    ProcessStatus,
    ProcessLogRecord,
    get_step_description,
)

# Load environment
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

logger = get_logger(__name__)

# Configuration
PROCESS_LOG_TABLE = os.getenv("PROCESS_LOG_TABLE", "process_logs")
PROCESS_LOG_FALLBACK_DIR = Path(os.getenv("PROCESS_LOG_FALLBACK_DIR", "logs/process"))

# Singleton instance
_process_logger: Optional["ProcessLogger"] = None


class ProcessLogger:
    """
    Centralized process logger with database and file fallback.

    This class provides a simple, reliable API for logging process steps
    across the entire application. It automatically handles database failures
    by falling back to local file logging.

    Usage:
        >>> logger = get_process_logger()
        >>> run_id = logger.generate_run_id()
        >>> logger.log_step(
        ...     run_id=run_id,
        ...     step=ProcessStep.CRAWL_START,
        ...     company="Dropbox",
        ...     domain="jobs.dropbox.com",
        ...     metadata={"url": "https://jobs.dropbox.com/all-jobs"}
        ... )
    """

    def __init__(self):
        """Initialize process logger with database connection."""
        self._client = None
        self._db_available = False
        self._fallback_dir = PROCESS_LOG_FALLBACK_DIR
        self._fallback_dir.mkdir(exist_ok=True, parents=True)

        # Try to initialize database connection
        self._init_database()

    def _init_database(self) -> None:
        """Initialize Supabase client for process logging."""
        try:
            from supabase import create_client

            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

            if not url or not key:
                logger.warning("Process logging: Supabase credentials missing, using file fallback")
                return

            self._client = create_client(url, key)
            self._db_available = True
            logger.info("Process logging initialized with Supabase")

        except ImportError:
            logger.warning("Process logging: supabase package not installed, using file fallback")
        except Exception as e:
            logger.warning(f"Process logging: Database init failed ({e}), using file fallback")

    @staticmethod
    def generate_run_id() -> str:
        """
        Generate a unique run ID for correlating steps.

        Returns:
            UUID string for this crawl session
        """
        return str(uuid.uuid4())

    def log_step(
        self,
        run_id: str,
        step: ProcessStep,
        company: str,
        domain: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        status: ProcessStatus = ProcessStatus.SUCCESS,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log a process step to the database.

        This method never raises exceptions - it will fall back to file logging
        if database write fails.

        Args:
            run_id: UUID correlating all steps in a session
            step: Process step type
            company: Company name
            domain: Domain being processed
            started_at: Step start timestamp (defaults to now)
            completed_at: Step completion timestamp
            status: Execution status
            metadata: Additional context

        Returns:
            True if logged successfully, False otherwise
        """
        try:
            now = datetime.now(timezone.utc).isoformat()

            # Create and validate process log record
            record = ProcessLogRecord(
                run_id=run_id,
                step=step,
                company=company,
                domain=domain,
                started_at=started_at or now,
                completed_at=completed_at,  # Don't auto-fill - None means step is in progress
                status=status,
                metadata=metadata or {},
            )

            # Calculate duration
            record.duration_seconds = record.calculate_duration()

            # Log to standard logger
            desc = get_step_description(step, company=company, **(metadata or {}))
            logger.info(f"[Process] {company} | {step.value} | {desc}")

            # Try database write
            if self._db_available and self._client:
                return self._write_to_database(record)
            else:
                return self._write_to_file(record)

        except Exception as e:
            logger.error(f"Process logger failed: {e} - Step: {step.value}")
            return False

    def _write_to_database(self, record: ProcessLogRecord) -> bool:
        """Write process log record to Supabase."""
        try:
            row = record.model_dump(exclude_none=False)
            self._client.table(PROCESS_LOG_TABLE).insert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"Database process log write failed: {e}, falling back to file")
            return self._write_to_file(record)

    def _write_to_file(self, record: ProcessLogRecord) -> bool:
        """Write process log record to local JSON file (fallback)."""
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            file_path = self._fallback_dir / f"process_{date_str}.jsonl"

            with open(file_path, "a", encoding="utf-8") as f:
                json.dump(record.model_dump(), f)
                f.write("\n")

            return True
        except Exception as e:
            logger.error(f"File process log write failed: {e}")
            return False

    def get_logs_for_run(
        self,
        run_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all process logs for a specific run.

        Args:
            run_id: Run correlation ID
            limit: Maximum number of results

        Returns:
            List of process log records
        """
        if not self._db_available or not self._client:
            logger.warning("Database not available for process log queries")
            return []

        try:
            query = (
                self._client.table(PROCESS_LOG_TABLE)
                .select("*")
                .eq("run_id", run_id)
                .order("started_at", desc=False)
                .limit(limit)
            )

            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Process log query failed: {e}")
            return []

    def get_logs_for_company(
        self,
        company: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent process logs for a company.

        Args:
            company: Company name
            limit: Maximum number of results

        Returns:
            List of process log records
        """
        if not self._db_available or not self._client:
            logger.warning("Database not available for process log queries")
            return []

        try:
            query = (
                self._client.table(PROCESS_LOG_TABLE)
                .select("*")
                .eq("company", company)
                .order("created_at", desc=True)
                .limit(limit)
            )

            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Process log query failed: {e}")
            return []


def get_process_logger() -> ProcessLogger:
    """
    Get the global ProcessLogger instance.

    Returns:
        Global ProcessLogger singleton

    Example:
        >>> process_logger = get_process_logger()
        >>> run_id = process_logger.generate_run_id()
        >>> process_logger.log_step(run_id, ProcessStep.CRAWL_START, "Dropbox", "jobs.dropbox.com")
    """
    global _process_logger
    if _process_logger is None:
        _process_logger = ProcessLogger()
    return _process_logger
