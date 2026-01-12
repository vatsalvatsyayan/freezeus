"""
Centralized error logging system with Supabase integration.

This module provides a fail-safe error logger that:
- Logs errors to Supabase with structured schema
- Falls back to local file logging on database failures
- Uses Pydantic validation for type safety
- Follows singleton pattern for global access
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv

from src.core.logging import get_logger
from src.core.error_models import (
    ErrorRecord,
    ErrorComponent,
    ErrorSeverity,
    ErrorType,
    ErrorStage,
)

# Load environment
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

logger = get_logger(__name__)

# Configuration
ERROR_LOG_TABLE = os.getenv("ERROR_LOG_TABLE", "error_logs")
ERROR_LOG_FALLBACK_DIR = Path(os.getenv("ERROR_LOG_FALLBACK_DIR", "logs/errors"))

# Singleton instance
_error_logger: Optional["ErrorLogger"] = None


class ErrorLogger:
    """
    Centralized error logger with database and file fallback.

    This class provides a simple, reliable API for logging errors across
    the entire application. It automatically handles database failures by
    falling back to local file logging.

    Usage:
        >>> logger = get_error_logger()
        >>> logger.log_error(
        ...     component=ErrorComponent.CRAWLER,
        ...     stage=ErrorStage.NAVIGATE_SEED,
        ...     error_type=ErrorType.TIMEOUT,
        ...     domain="jobs.dropbox.com",
        ...     message="Navigation timeout after 45s",
        ...     url="https://jobs.dropbox.com/all-jobs",
        ...     metadata={"timeout_ms": 45000}
        ... )
    """

    def __init__(self):
        """Initialize error logger with database connection."""
        self._client = None
        self._db_available = False
        self._fallback_dir = ERROR_LOG_FALLBACK_DIR
        self._fallback_dir.mkdir(exist_ok=True, parents=True)

        # Try to initialize database connection
        self._init_database()

    def _init_database(self) -> None:
        """Initialize Supabase client for error logging."""
        try:
            from supabase import create_client

            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

            if not url or not key:
                logger.warning("Error logging: Supabase credentials missing, using file fallback")
                return

            self._client = create_client(url, key)
            self._db_available = True
            logger.info("Error logging initialized with Supabase")

        except ImportError:
            logger.warning("Error logging: supabase package not installed, using file fallback")
        except Exception as e:
            logger.warning(f"Error logging: Database init failed ({e}), using file fallback")

    def log_error(
        self,
        component: ErrorComponent,
        stage: str,
        error_type: ErrorType,
        domain: str,
        message: str,
        url: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        exception_type: Optional[str] = None,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log an error to the database.

        This method never raises exceptions - it will fall back to file logging
        if database write fails.

        Args:
            component: System component
            stage: Processing stage
            error_type: Error category
            domain: Source domain
            message: Human-readable error message
            url: Optional specific URL
            severity: Error severity (default: ERROR)
            exception_type: Exception class name
            stack_trace: Full stack trace (for unexpected errors)
            metadata: Additional context

        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Create and validate error record
            record = ErrorRecord(
                component=component,
                stage=stage,
                error_type=error_type,
                severity=severity,
                domain=domain,
                url=url,
                message=message,
                exception_type=exception_type,
                stack_trace=stack_trace,
                metadata=metadata or {},
            )

            # Try database write
            if self._db_available and self._client:
                return self._write_to_database(record)
            else:
                return self._write_to_file(record)

        except Exception as e:
            # Fail-safe: If error logging itself fails, log to standard logger
            logger.error(f"Error logger failed: {e} - Original error: {message}")
            return False

    def log_exception(
        self,
        exc: Exception,
        component: ErrorComponent,
        stage: str,
        domain: str,
        url: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        error_type: Optional[ErrorType] = None,
        include_stack_trace: bool = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Log an exception with automatic classification.

        This is a convenience method that uses ErrorRecord.from_exception()
        to automatically extract error details.

        Args:
            exc: The exception to log
            component: System component
            stage: Processing stage
            domain: Source domain
            url: Optional specific URL
            severity: Error severity (default: ERROR)
            error_type: Optional explicit error type (auto-detected if None)
            include_stack_trace: Whether to include stack trace (auto if None)
            metadata: Additional context

        Returns:
            True if logged successfully, False otherwise

        Example:
            >>> try:
            ...     page.goto(url, timeout=45000)
            ... except TimeoutError as e:
            ...     error_logger.log_exception(
            ...         e,
            ...         component=ErrorComponent.CRAWLER,
            ...         stage=ErrorStage.NAVIGATE_SEED,
            ...         domain=domain_of(url),
            ...         url=url,
            ...     )
        """
        try:
            # Create error record from exception
            record = ErrorRecord.from_exception(
                exc=exc,
                component=component,
                stage=stage,
                domain=domain,
                url=url,
                severity=severity,
                error_type=error_type,
                include_stack_trace=include_stack_trace,
                metadata=metadata,
            )

            # Try database write
            if self._db_available and self._client:
                return self._write_to_database(record)
            else:
                return self._write_to_file(record)

        except Exception as e:
            logger.error(f"Error logger failed: {e} - Original exception: {type(exc).__name__}")
            return False

    def _write_to_database(self, record: ErrorRecord) -> bool:
        """Write error record to Supabase."""
        try:
            row = record.model_dump(exclude_none=False)
            self._client.table(ERROR_LOG_TABLE).insert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"Database error write failed: {e}, falling back to file")
            # Fallback to file
            return self._write_to_file(record)

    def _write_to_file(self, record: ErrorRecord) -> bool:
        """Write error record to local JSON file (fallback)."""
        try:
            # Create date-based file (using UTC for consistency)
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            file_path = self._fallback_dir / f"errors_{date_str}.jsonl"

            # Append as JSON line
            with open(file_path, "a", encoding="utf-8") as f:
                json.dump(record.model_dump(), f)
                f.write("\n")

            return True
        except Exception as e:
            logger.error(f"File error write failed: {e}")
            return False

    def get_errors_for_domain(
        self,
        domain: str,
        limit: int = 100,
        severity: Optional[ErrorSeverity] = None,
        component: Optional[ErrorComponent] = None,
    ) -> list:
        """
        Retrieve recent errors for a domain.

        Args:
            domain: Domain to query
            limit: Maximum number of results
            severity: Filter by severity
            component: Filter by component

        Returns:
            List of error records
        """
        if not self._db_available or not self._client:
            logger.warning("Database not available for error queries")
            return []

        try:
            query = self._client.table(ERROR_LOG_TABLE).select("*").eq("domain", domain)

            if severity:
                query = query.eq("severity", severity.value)
            if component:
                query = query.eq("component", component.value)

            query = query.order("created_at", desc=True).limit(limit)

            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error query failed: {e}")
            return []


# Singleton accessor
def get_error_logger() -> ErrorLogger:
    """
    Get the global ErrorLogger instance.

    Returns:
        Global ErrorLogger singleton

    Example:
        >>> error_logger = get_error_logger()
        >>> error_logger.log_error(...)
    """
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger
