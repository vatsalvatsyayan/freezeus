"""
Pydantic models for structured error logging.

This module defines type-safe error record models with automatic validation
and classification to ensure consistency across the error logging system.
"""

import json
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ErrorComponent(str, Enum):
    """System components that can generate errors."""
    CRAWLER = "crawler"
    LLM = "llm"
    DATABASE = "db"
    UTILS = "utils"
    CONFIG = "config"
    UNKNOWN = "unknown"


class ErrorSeverity(str, Enum):
    """Error severity levels matching logging standards."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorType(str, Enum):
    """
    Categorized error types for classification.

    This enum provides a standardized taxonomy of errors across the system.
    New error types should be added here to maintain consistency.
    """
    # Validation errors
    VALIDATION_ERROR = "validation_error"
    SCHEMA_ERROR = "schema_error"

    # Network/API errors
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"

    # Parsing errors
    PARSE_ERROR = "parse_error"
    JSON_ERROR = "json_error"
    HTML_ERROR = "html_error"

    # Database errors
    DB_CONNECTION_ERROR = "db_connection_error"
    DB_QUERY_ERROR = "db_query_error"
    DB_UPSERT_ERROR = "db_upsert_error"

    # Browser/Crawler errors
    BROWSER_ERROR = "browser_error"
    NAVIGATION_ERROR = "navigation_error"
    ELEMENT_NOT_FOUND = "element_not_found"

    # File system errors
    FILE_ERROR = "file_error"
    PATH_ERROR = "path_error"

    # Configuration errors
    CONFIG_ERROR = "config_error"
    ENV_ERROR = "env_error"

    # Unknown/uncategorized
    UNKNOWN = "unknown"


class ErrorStage:
    """
    Standardized stage names for error logging.

    Use these constants to ensure consistency across the codebase.
    """
    # Crawler stages
    NAVIGATE_SEED = "navigate_seed"
    EXPAND_IN_PAGE = "expand_in_page"
    PAGINATE = "paginate"
    SNAPSHOT = "snapshot"
    REDUCE_HTML = "reduce_html"
    SAVE_FILES = "save_files"
    CLICK_LOAD_MORE = "click_load_more"
    CLICK_NEXT_PAGE = "click_next_page"
    WAIT_FOR_JOBS = "wait_for_jobs"
    SCROLL_TO_BOTTOM = "scroll_to_bottom"
    DETECT_JOBS = "detect_jobs"
    EXTRACT_HREFS = "extract_hrefs"
    CHECK_PROGRESS = "check_progress"

    # LLM stages
    LOAD_HTML = "load_html"
    CALL_LLM = "call_llm"
    PARSE_JSON = "parse_json"
    NORMALIZE_JOBS = "normalize_jobs"
    DEDUPE_JOBS = "dedupe_jobs"

    # Database stages
    VALIDATE_PAGE = "validate_page"
    VALIDATE_JOB = "validate_job"
    CHECK_EXISTING = "check_existing"
    UPSERT_JOBS = "upsert_jobs"
    UPSERT_FROM_EXTRACTOR = "upsert_from_extractor"
    CONNECT_DB = "connect_db"

    # Config stages
    LOAD_CONFIG = "load_config"
    VALIDATE_CONFIG = "validate_config"


class ErrorRecord(BaseModel):
    """
    Structured error record for database insertion.

    This model validates all error data before logging to ensure consistency
    and prevent logging errors from causing additional failures.
    """
    # Required fields
    component: ErrorComponent = Field(..., description="System component")
    stage: str = Field(..., min_length=1, max_length=100, description="Processing stage")
    error_type: ErrorType = Field(..., description="Error category")
    severity: ErrorSeverity = Field(default=ErrorSeverity.ERROR, description="Severity level")
    domain: str = Field(..., min_length=1, max_length=255, description="Source domain")
    message: str = Field(..., min_length=1, description="Human-readable error message")

    # Optional context
    url: Optional[str] = Field(None, max_length=2048, description="Specific URL if applicable")
    exception_type: Optional[str] = Field(None, max_length=255, description="Exception class name")
    stack_trace: Optional[str] = Field(None, description="Stack trace for unexpected errors")

    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

    # Timestamp (auto-populated)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Error timestamp"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,  # Store enum values, not enum objects
    )

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        """Ensure stage is not empty and normalized."""
        if not v or not v.strip():
            return "unknown"
        return v.strip().lower().replace(" ", "_")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not empty."""
        if not v or not v.strip():
            return "No error message provided"
        # Truncate to reasonable length
        return v.strip()[:5000]

    @field_validator("metadata")
    @classmethod
    def sanitize_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to ensure it's JSON-serializable.

        Converts non-serializable types to strings.
        """
        sanitized = {}
        for key, value in v.items():
            try:
                # Test JSON serializability
                json.dumps(value)
                sanitized[key] = value
            except (TypeError, ValueError):
                # Convert to string if not serializable
                sanitized[key] = str(value)
        return sanitized

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        component: ErrorComponent,
        stage: str,
        domain: str,
        url: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        error_type: Optional[ErrorType] = None,
        include_stack_trace: bool = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ErrorRecord":
        """
        Create ErrorRecord from an exception with automatic classification.

        Args:
            exc: The exception that occurred
            component: System component where error occurred
            stage: Processing stage
            domain: Source domain
            url: Optional specific URL
            severity: Error severity (default: ERROR)
            error_type: Optional explicit error type (auto-detected if None)
            include_stack_trace: Whether to include full stack trace (auto if None)
            metadata: Additional context

        Returns:
            ErrorRecord instance ready for logging

        Example:
            >>> try:
            ...     validate_job(job_data)
            ... except ValidationError as e:
            ...     record = ErrorRecord.from_exception(
            ...         e,
            ...         component=ErrorComponent.DATABASE,
            ...         stage=ErrorStage.VALIDATE_JOB,
            ...         domain="jobs.dropbox.com",
            ...         metadata={"job_url": job_data.get("job_url")}
            ...     )
        """
        # Auto-detect error type if not provided
        if error_type is None:
            error_type = cls._classify_exception(exc)

        # Build error message
        message = str(exc) or f"{type(exc).__name__} occurred"

        # Get exception type name
        exception_type = f"{type(exc).__module__}.{type(exc).__name__}"

        # Auto-determine if stack trace should be included
        if include_stack_trace is None:
            include_stack_trace = cls._should_include_stack(exc, severity)

        # Capture stack trace for unexpected errors
        stack_trace = None
        if include_stack_trace:
            try:
                stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                # Truncate to 10KB
                if len(stack_trace) > 10000:
                    stack_trace = stack_trace[:10000] + "\n... (truncated)"
            except Exception:
                stack_trace = None

        # Merge metadata
        final_metadata = metadata or {}

        return cls(
            component=component,
            stage=stage,
            error_type=error_type,
            severity=severity,
            domain=domain,
            url=url,
            message=message,
            exception_type=exception_type,
            stack_trace=stack_trace,
            metadata=final_metadata,
        )

    @staticmethod
    def _classify_exception(exc: Exception) -> ErrorType:
        """
        Automatically classify exception into ErrorType.

        Uses exception type and message patterns to determine category.
        """
        exc_name = type(exc).__name__.lower()
        exc_msg = str(exc).lower()

        # Validation errors
        if "validation" in exc_name or "schema" in exc_name:
            return ErrorType.VALIDATION_ERROR

        # Network/timeout errors
        if "timeout" in exc_name or "timeout" in exc_msg:
            return ErrorType.TIMEOUT
        if "connection" in exc_name:
            return ErrorType.CONNECTION_ERROR
        if "http" in exc_name or "status" in exc_msg:
            return ErrorType.HTTP_ERROR
        if "429" in exc_msg or "rate limit" in exc_msg:
            return ErrorType.RATE_LIMIT

        # Parsing errors
        if "json" in exc_name:
            return ErrorType.JSON_ERROR
        if "parse" in exc_name:
            return ErrorType.PARSE_ERROR

        # Database errors
        if "database" in exc_name or "sql" in exc_name or "postgres" in exc_name:
            return ErrorType.DB_QUERY_ERROR

        # Browser errors
        if "playwright" in exc_name or "browser" in exc_name:
            return ErrorType.BROWSER_ERROR
        if "element" in exc_name or "selector" in exc_msg:
            return ErrorType.ELEMENT_NOT_FOUND

        # File errors
        if "file" in exc_name or "io" in exc_name:
            return ErrorType.FILE_ERROR

        # Default
        return ErrorType.UNKNOWN

    @staticmethod
    def _should_include_stack(exc: Exception, severity: ErrorSeverity) -> bool:
        """
        Determine if stack trace should be included based on exception type and severity.

        Expected errors (validation, not-found) don't need stacks.
        Unexpected errors (system crashes, bugs) do.
        """
        # Always include for critical errors
        if severity == ErrorSeverity.CRITICAL:
            return True

        # Skip for warnings and info
        if severity in (ErrorSeverity.WARNING, ErrorSeverity.INFO, ErrorSeverity.DEBUG):
            return False

        # Expected error types - no stack trace needed
        EXPECTED_ERRORS = (
            'ValidationError',
            'FileNotFoundError',
            'KeyError',
            'ValueError',
            'TimeoutError',
        )

        error_type = type(exc).__name__
        return error_type not in EXPECTED_ERRORS
