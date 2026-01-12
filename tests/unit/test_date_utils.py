"""
Unit tests for date utility functions.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.utils.date_utils import (
    get_current_timestamp,
    format_date,
    parse_date,
    parse_relative_date,
    is_recent_date,
)


class TestGetCurrentTimestamp:
    """Tests for get_current_timestamp function."""

    def test_returns_iso_format(self):
        """Test that timestamp is in ISO format."""
        ts = get_current_timestamp()
        # Should be parseable as ISO format
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        assert isinstance(dt, datetime)

    def test_includes_timezone(self):
        """Test that timestamp includes timezone info."""
        ts = get_current_timestamp()
        assert '+' in ts or 'Z' in ts or ts.endswith('+00:00')


class TestFormatDate:
    """Tests for format_date function."""

    def test_default_format(self):
        """Test default YYYY-MM-DD format."""
        dt = datetime(2026, 1, 8, 12, 30, 45)
        result = format_date(dt)
        assert result == "2026-01-08"

    def test_custom_format(self):
        """Test custom format string."""
        dt = datetime(2026, 1, 8, 12, 30, 45)
        result = format_date(dt, fmt="%Y/%m/%d")
        assert result == "2026/01/08"

    def test_with_time(self):
        """Test formatting with time."""
        dt = datetime(2026, 1, 8, 12, 30, 45)
        result = format_date(dt, fmt="%Y-%m-%d %H:%M:%S")
        assert result == "2026-01-08 12:30:45"


class TestParseDate:
    """Tests for parse_date function."""

    @pytest.mark.parametrize("date_str,expected_year,expected_month,expected_day", [
        ("2026-01-08", 2026, 1, 8),
        ("2026/01/08", 2026, 1, 8),
        ("08-01-2026", 2026, 1, 8),
        ("08/01/2026", 2026, 1, 8),
        ("January 8, 2026", 2026, 1, 8),
        ("Jan 8, 2026", 2026, 1, 8),
    ])
    def test_parse_various_formats(self, date_str, expected_year, expected_month, expected_day):
        """Test parsing various date formats."""
        dt = parse_date(date_str)
        assert dt is not None
        assert dt.year == expected_year
        assert dt.month == expected_month
        assert dt.day == expected_day

    def test_parse_with_time(self):
        """Test parsing date with time."""
        dt = parse_date("2026-01-08T12:30:45")
        assert dt is not None
        assert dt.year == 2026
        assert dt.hour == 12

    def test_parse_invalid_returns_none(self):
        """Test that invalid date string returns None."""
        assert parse_date("not-a-date") is None
        assert parse_date("") is None
        assert parse_date("99/99/9999") is None

    def test_parse_none_returns_none(self):
        """Test that None input returns None."""
        assert parse_date(None) is None


class TestParseRelativeDate:
    """Tests for parse_relative_date function."""

    def test_parse_today(self):
        """Test parsing 'today'."""
        dt = parse_relative_date("today")
        assert dt is not None
        # Should be within last minute
        assert is_recent_date(dt, days=1)

    def test_parse_yesterday(self):
        """Test parsing 'yesterday'."""
        dt = parse_relative_date("yesterday")
        assert dt is not None
        # Should be about 1 day ago
        age = datetime.now(timezone.utc) - dt
        assert 0.9 <= age.days <= 1.1

    def test_parse_days_ago(self):
        """Test parsing 'N days ago'."""
        dt = parse_relative_date("3 days ago")
        assert dt is not None
        age = datetime.now(timezone.utc) - dt
        assert 2.9 <= age.days <= 3.1

    def test_parse_weeks_ago(self):
        """Test parsing 'N weeks ago'."""
        dt = parse_relative_date("2 weeks ago")
        assert dt is not None
        age = datetime.now(timezone.utc) - dt
        assert 13 <= age.days <= 15

    def test_parse_invalid_returns_none(self):
        """Test that invalid relative string returns None."""
        assert parse_relative_date("not-relative") is None
        assert parse_relative_date("") is None


class TestIsRecentDate:
    """Tests for is_recent_date function."""

    def test_recent_date_is_recent(self):
        """Test that a recent date is identified as recent."""
        now = datetime.now(timezone.utc)
        assert is_recent_date(now, days=30) is True

    def test_old_date_is_not_recent(self):
        """Test that an old date is not recent."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        assert is_recent_date(old, days=30) is False

    def test_boundary_date(self):
        """Test date exactly at the boundary."""
        boundary = datetime.now(timezone.utc) - timedelta(days=29.5)  # Just inside boundary
        assert is_recent_date(boundary, days=30) is True

    def test_naive_datetime_handled(self):
        """Test that naive datetime (no timezone) is handled."""
        now = datetime.now()  # Naive datetime
        # Should not raise exception
        result = is_recent_date(now, days=30)
        assert isinstance(result, bool)
