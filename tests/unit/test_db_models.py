"""
Unit tests for database Pydantic models.

Tests validation, serialization, and model construction.
"""

import pytest
from pydantic import ValidationError
from src.db.models import (
    JobPosting,
    JobRecord,
    JobExtra,
    PageData,
)


class TestJobExtra:
    """Tests for JobExtra model."""

    def test_create_with_standard_fields(self):
        """Test creating JobExtra with standard fields."""
        extra = JobExtra(
            job_description="Great opportunity",
            weekly_hours=40,
            apply_url="https://example.com/apply"
        )
        assert extra.job_description == "Great opportunity"
        assert extra.weekly_hours == 40
        assert extra.apply_url == "https://example.com/apply"

    def test_allows_extra_fields(self):
        """Test that extra fields are allowed."""
        extra = JobExtra(
            job_description="Test",
            custom_field="custom value",
            another_field=123
        )
        assert extra.job_description == "Test"
        # Extra fields should be accessible
        assert hasattr(extra, "custom_field")


class TestJobPosting:
    """Tests for JobPosting model."""

    def test_create_with_required_fields(self):
        """Test creating job with minimum required fields."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Software Engineer"
        )
        assert job.job_url == "https://example.com/job/123"
        assert job.title == "Software Engineer"
        assert job.seniority_level == "Unknown"
        assert job.seniority_bucket == "unknown"
        assert job.country == "Unknown"

    def test_create_with_all_fields(self):
        """Test creating job with all fields populated."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Senior Software Engineer",
            company="Acme Corp",
            location="San Francisco, CA",
            country="USA",
            team_or_category="Engineering",
            employment_type="Full-time",
            office_or_remote="Hybrid",
            seniority_level="Senior",
            seniority_bucket="senior",
            date_posted_raw="2026-01-01",
            job_description="Build great software",
            weekly_hours=40,
            apply_url="https://example.com/apply/123",
            job_id="JOB-123",
            role_number="REQ-456"
        )
        assert job.title == "Senior Software Engineer"
        assert job.company == "Acme Corp"
        assert job.seniority_bucket == "senior"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from strings."""
        job = JobPosting(
            job_url="  https://example.com/job/123  ",
            title="  Software Engineer  "
        )
        assert job.job_url == "https://example.com/job/123"
        assert job.title == "Software Engineer"

    def test_validates_job_url_not_empty(self):
        """Test that empty job_url raises error."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            JobPosting(job_url="", title="Test")

    def test_validates_job_url_not_whitespace(self):
        """Test that whitespace-only job_url raises error."""
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            JobPosting(job_url="   ", title="Test")

    def test_validates_seniority_bucket(self):
        """Test that invalid seniority_bucket defaults to unknown."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            seniority_bucket="invalid_value"
        )
        assert job.seniority_bucket == "unknown"

    def test_seniority_bucket_allowed_values(self):
        """Test all valid seniority_bucket values."""
        allowed = ["intern", "entry", "mid", "senior", "director_vp", "executive", "unknown"]
        for bucket in allowed:
            job = JobPosting(
                job_url=f"https://example.com/job/{bucket}",
                title="Test",
                seniority_bucket=bucket
            )
            assert job.seniority_bucket == bucket

    def test_location_list_to_string(self):
        """Test that location list is converted to string."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            location=["San Francisco", "New York", "Remote"]
        )
        assert job.location == "San Francisco, New York, Remote"

    def test_location_string_preserved(self):
        """Test that location string is preserved."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            location="San Francisco, CA"
        )
        assert job.location == "San Francisco, CA"

    def test_location_empty_list(self):
        """Test that empty location list becomes empty string."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            location=[]
        )
        # Empty list converts to empty string, which is then empty
        assert job.location == "" or job.location is None

    def test_extra_fields_dict(self):
        """Test that extra fields are stored in dict."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            extra={"custom_field": "value", "another": 123}
        )
        assert job.extra == {"custom_field": "value", "another": 123}


class TestJobRecord:
    """Tests for JobRecord model."""

    def test_create_job_record(self):
        """Test creating JobRecord with all required fields."""
        record = JobRecord(
            job_url="https://example.com/job/123",
            title="Engineer",
            last_seen_at="2026-01-08T12:00:00Z",
            source_domain="example.com"
        )
        assert record.job_url == "https://example.com/job/123"
        assert record.source_domain == "example.com"
        assert record.seniority_level == "Unknown"
        assert record.seniority_bucket == "unknown"

    def test_from_job_posting(self):
        """Test creating JobRecord from JobPosting."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Software Engineer",
            company="Acme",
            seniority_bucket="mid"
        )

        record = JobRecord.from_job_posting(
            job=job,
            domain="example.com",
            source_url="https://example.com/careers",
            page_title="Careers at Acme"
        )

        assert record.job_url == job.job_url
        assert record.title == job.title
        assert record.company == job.company
        assert record.seniority_bucket == "mid"
        assert record.source_domain == "example.com"
        assert record.source_page_url == "https://example.com/careers"
        assert record.source_page_title == "Careers at Acme"
        assert record.last_seen_at is not None

    def test_from_job_posting_preserves_first_seen(self):
        """Test that from_job_posting can preserve first_seen_at."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer"
        )

        first_seen = "2026-01-01T00:00:00Z"
        record = JobRecord.from_job_posting(
            job=job,
            domain="example.com",
            first_seen_at=first_seen
        )

        assert record.first_seen_at == first_seen

    def test_from_job_posting_sets_timestamps(self):
        """Test that from_job_posting sets last_seen_at automatically."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer"
        )

        record = JobRecord.from_job_posting(
            job=job,
            domain="example.com"
        )

        assert record.last_seen_at is not None
        assert "T" in record.last_seen_at  # ISO format


class TestPageData:
    """Tests for PageData model."""

    def test_create_page_data(self):
        """Test creating PageData with basic fields."""
        page = PageData(
            source_url="https://example.com/careers",
            page_title="Careers",
            jobs=[]
        )
        assert page.source_url == "https://example.com/careers"
        assert page.page_title == "Careers"
        assert page.jobs == []

    def test_create_with_defaults(self):
        """Test creating PageData with defaults."""
        page = PageData()
        assert page.source_url == ""
        assert page.page_title == ""
        assert page.jobs == []

    def test_validate_jobs_success(self):
        """Test validating jobs successfully."""
        page = PageData(
            jobs=[
                {"job_url": "https://example.com/job/1", "title": "Job 1"},
                {"job_url": "https://example.com/job/2", "title": "Job 2"},
            ]
        )
        validated = page.validate_jobs()
        assert len(validated) == 2
        assert all(isinstance(j, JobPosting) for j in validated)

    def test_validate_jobs_failure(self):
        """Test that invalid job raises ValueError."""
        page = PageData(
            jobs=[
                {"job_url": "", "title": "Invalid"},  # Empty job_url
            ]
        )
        with pytest.raises(ValueError, match="Job 0 validation failed"):
            page.validate_jobs()

    def test_validate_jobs_partial_failure(self):
        """Test that first invalid job stops validation."""
        page = PageData(
            jobs=[
                {"job_url": "https://example.com/job/1", "title": "Valid"},
                {"job_url": "", "title": "Invalid"},  # Will fail here
                {"job_url": "https://example.com/job/3", "title": "Also Valid"},
            ]
        )
        with pytest.raises(ValueError, match="Job 1 validation failed"):
            page.validate_jobs()


class TestModelSerialization:
    """Tests for model serialization and deserialization."""

    def test_job_posting_to_dict(self):
        """Test converting JobPosting to dict."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer",
            company="Acme"
        )
        data = job.model_dump()
        assert data["job_url"] == "https://example.com/job/123"
        assert data["title"] == "Engineer"
        assert data["company"] == "Acme"

    def test_job_posting_to_dict_exclude_none(self):
        """Test excluding None values from dict."""
        job = JobPosting(
            job_url="https://example.com/job/123",
            title="Engineer"
            # company is None
        )
        data = job.model_dump(exclude_none=True)
        assert "company" not in data
        assert "job_url" in data

    def test_job_record_to_dict(self):
        """Test converting JobRecord to dict."""
        record = JobRecord(
            job_url="https://example.com/job/123",
            title="Engineer",
            last_seen_at="2026-01-08T12:00:00Z",
            source_domain="example.com"
        )
        data = record.model_dump()
        assert data["job_url"] == "https://example.com/job/123"
        assert data["source_domain"] == "example.com"

    def test_job_posting_from_dict(self):
        """Test creating JobPosting from dict."""
        data = {
            "job_url": "https://example.com/job/123",
            "title": "Engineer",
            "company": "Acme",
            "seniority_bucket": "mid"
        }
        job = JobPosting(**data)
        assert job.job_url == data["job_url"]
        assert job.title == data["title"]
        assert job.seniority_bucket == "mid"
