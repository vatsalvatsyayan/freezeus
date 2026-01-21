"""
Pydantic models for structured process logging.

This module defines type-safe process log models with automatic validation
to ensure consistency across the process logging system.
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ProcessStep(str, Enum):
    """
    Process step types for job crawling pipeline.

    These represent the 6 major steps in the crawl -> extract -> save flow.
    """
    CRAWL_START = "crawl_start"
    CRAWL_COMPLETE = "crawl_complete"
    HTML_EXTRACTED = "html_extracted"
    LLM_START = "llm_start"
    LLM_COMPLETE = "llm_complete"
    DB_COMPLETE = "db_complete"


class ProcessStatus(str, Enum):
    """Process execution status."""
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessLogRecord(BaseModel):
    """
    Structured process log record for database insertion.

    This model validates all process log data before logging to ensure
    consistency and enable reliable querying.
    """
    # Correlation
    run_id: str = Field(..., min_length=1, description="UUID correlating steps in a crawl session")

    # Step identification
    step: ProcessStep = Field(..., description="Process step type")
    company: str = Field(..., min_length=1, max_length=255, description="Company name")
    domain: str = Field(..., min_length=1, max_length=255, description="Domain being crawled")

    # Timing
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Step start timestamp (ISO 8601)"
    )
    completed_at: Optional[str] = Field(None, description="Step completion timestamp (ISO 8601)")
    duration_seconds: Optional[float] = Field(None, ge=0, description="Duration in seconds")

    # Status and metadata
    status: ProcessStatus = Field(
        default=ProcessStatus.SUCCESS,
        description="Execution status"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (job counts, file sizes, etc.)"
    )

    # Audit timestamp
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Log creation timestamp"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    @field_validator("company")
    @classmethod
    def validate_company(cls, v: str) -> str:
        """Ensure company is not empty."""
        if not v or not v.strip():
            return "Unknown"
        return v.strip()[:255]

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Ensure domain is not empty and normalized."""
        if not v or not v.strip():
            return "unknown"
        return v.strip().lower()[:255]

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
                json.dumps(value)
                sanitized[key] = value
            except (TypeError, ValueError):
                sanitized[key] = str(value)
        return sanitized

    def calculate_duration(self) -> Optional[float]:
        """
        Calculate duration from started_at and completed_at timestamps.

        Returns:
            Duration in seconds, or None if completed_at is not set
        """
        if not self.completed_at:
            return None

        try:
            start = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
            end = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
            return round((end - start).total_seconds(), 3)
        except Exception:
            return None


# Human-readable step descriptions
STEP_DESCRIPTIONS = {
    ProcessStep.CRAWL_START: "Crawling {company} company",
    ProcessStep.CRAWL_COMPLETE: "Finished Crawling",
    ProcessStep.HTML_EXTRACTED: "Extracted HTML",
    ProcessStep.LLM_START: "Sending reduced_html to Gemini",
    ProcessStep.LLM_COMPLETE: "Gemini process complete, found {jobs_found} jobs",
    ProcessStep.DB_COMPLETE: "Database save complete, saved {jobs_saved} jobs",
}


def get_step_description(step: ProcessStep, **kwargs) -> str:
    """
    Get human-readable description for a step.

    Args:
        step: Process step
        **kwargs: Context for formatting (e.g., company, jobs_found)

    Returns:
        Formatted description string
    """
    template = STEP_DESCRIPTIONS.get(step, str(step))
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template
