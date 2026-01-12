"""
Pydantic models for database schema validation.

This module defines data models for job postings and related entities
with automatic validation, type checking, and serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class JobExtra(BaseModel):
    """
    Extra fields that may be present in job data.

    This is a flexible model for additional job fields that don't
    fit in the main schema but should be preserved.
    """
    job_description: Optional[str] = None
    weekly_hours: Optional[Union[int, str]] = None
    apply_url: Optional[str] = None
    job_id: Optional[str] = None
    role_number: Optional[str] = None
    job_family: Optional[str] = None
    job_function: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # Allow additional fields


class JobPosting(BaseModel):
    """
    Core job posting model with validation.

    Represents a single job posting with all standard fields.
    Used for validation before database insertion.
    """
    # Required fields
    job_url: str = Field(..., min_length=1, description="Unique job posting URL")
    title: str = Field(..., min_length=1, description="Job title")

    # Company and location
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[Union[str, List[str]]] = Field(None, description="Job location(s)")
    country: str = Field(default="Unknown", description="Country code or name")

    # Job details
    team_or_category: Optional[str] = Field(None, description="Team or job category")
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, etc.")
    office_or_remote: Optional[str] = Field(None, description="Remote, Hybrid, or Onsite")

    # Seniority
    seniority_level: str = Field(default="Unknown", description="Human-readable seniority")
    seniority_bucket: str = Field(
        default="unknown",
        description="Canonical seniority bucket (validated to allowed values)"
    )

    # Dates
    date_posted_raw: Optional[str] = Field(None, description="Raw date posted string")

    # Additional data
    job_description: Optional[str] = Field(None, description="Job description text")
    weekly_hours: Optional[Union[int, str]] = Field(None, description="Weekly hours")
    apply_url: Optional[str] = Field(None, description="Application URL")
    job_id: Optional[str] = Field(None, description="Internal job ID")
    role_number: Optional[str] = Field(None, description="Role/requisition number")

    # Extra fields (JSONB)
    extra: Dict[str, Any] = Field(default_factory=dict, description="Additional fields")

    model_config = ConfigDict(
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on attribute assignment
    )

    @field_validator("seniority_bucket")
    @classmethod
    def validate_seniority_bucket(cls, v: str) -> str:
        """Ensure seniority_bucket is one of the allowed values."""
        allowed = {"intern", "entry", "mid", "senior", "director_vp", "executive", "unknown"}
        if v not in allowed:
            return "unknown"
        return v

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, v: str) -> str:
        """Validate job URL is not empty."""
        if not v or not v.strip():
            raise ValueError("job_url cannot be empty")
        return v.strip()

    @field_validator("location")
    @classmethod
    def normalize_location(cls, v: Optional[Union[str, List[str]]]) -> Optional[str]:
        """Convert location to string format."""
        if v is None:
            return None
        if isinstance(v, list):
            return ", ".join(str(loc) for loc in v if loc)
        return str(v) if v else None


class JobRecord(BaseModel):
    """
    Complete job record for database storage.

    Extends JobPosting with database-specific fields like timestamps
    and source tracking.
    """
    # Core job fields (from JobPosting)
    job_url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    country: str = "Unknown"
    team_or_category: Optional[str] = None
    employment_type: Optional[str] = None
    office_or_remote: Optional[str] = None
    seniority_level: str = "Unknown"
    seniority_bucket: str = "unknown"
    date_posted_raw: Optional[str] = None

    # Extracted fields
    job_description: Optional[str] = None
    weekly_hours: Optional[Union[int, str]] = None
    apply_url: Optional[str] = None
    job_id: Optional[str] = None
    role_number: Optional[str] = None

    # Timestamp fields
    first_seen_at: Optional[str] = Field(None, description="First crawl timestamp")
    last_seen_at: str = Field(..., description="Most recent crawl timestamp")

    # Source tracking
    source_domain: str = Field(..., description="Source domain")
    source_page_url: str = Field(default="", description="Source page URL")
    source_page_title: str = Field(default="", description="Source page title")

    # Raw data storage (JSONB)
    raw_extra: Dict[str, Any] = Field(default_factory=dict)
    raw_job: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    @classmethod
    def from_job_posting(
        cls,
        job: JobPosting,
        domain: str,
        source_url: str = "",
        page_title: str = "",
        first_seen_at: Optional[str] = None,
        last_seen_at: Optional[str] = None,
    ) -> "JobRecord":
        """
        Create JobRecord from JobPosting with additional metadata.

        Args:
            job: JobPosting instance
            domain: Source domain
            source_url: Source page URL
            page_title: Source page title
            first_seen_at: First seen timestamp (None for new jobs)
            last_seen_at: Last seen timestamp (defaults to now)

        Returns:
            JobRecord instance ready for database insertion
        """
        from datetime import datetime, timezone

        if last_seen_at is None:
            last_seen_at = datetime.now(timezone.utc).isoformat()

        return cls(
            # Core fields
            job_url=job.job_url,
            title=job.title,
            company=job.company,
            location=job.location if isinstance(job.location, str) else job.location,
            country=job.country,
            team_or_category=job.team_or_category,
            employment_type=job.employment_type,
            office_or_remote=job.office_or_remote,
            seniority_level=job.seniority_level,
            seniority_bucket=job.seniority_bucket,
            date_posted_raw=job.date_posted_raw,
            # Extracted fields
            job_description=job.job_description,
            weekly_hours=job.weekly_hours,
            apply_url=job.apply_url,
            job_id=job.job_id,
            role_number=job.role_number,
            # Timestamps
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            # Source tracking
            source_domain=domain,
            source_page_url=source_url,
            source_page_title=page_title,
            # Raw data
            raw_extra=job.extra,
            raw_job=job.model_dump(exclude_none=True),
        )


class PageData(BaseModel):
    """
    Model for a page of job listings.

    Represents the output from LLM extraction for a single page.
    """
    source_url: str = Field(default="", description="Source page URL")
    page_title: str = Field(default="", description="Page title")
    jobs: List[Dict[str, Any]] = Field(default_factory=list, description="List of job dicts")

    model_config = ConfigDict(str_strip_whitespace=True)

    def validate_jobs(self) -> List[JobPosting]:
        """
        Validate all jobs in the page and return valid JobPosting instances.

        Returns:
            List of validated JobPosting objects

        Raises:
            ValueError: If any job fails validation
        """
        validated_jobs = []
        for idx, job_dict in enumerate(self.jobs):
            try:
                job = JobPosting(**job_dict)
                validated_jobs.append(job)
            except Exception as e:
                raise ValueError(f"Job {idx} validation failed: {e}") from e
        return validated_jobs
