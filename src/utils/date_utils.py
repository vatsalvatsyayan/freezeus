"""
Date utility functions for Freezeus backend.

This module provides date parsing, formatting, and manipulation utilities.
"""

from datetime import datetime, timezone
from typing import Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO format with UTC timezone.

    Returns:
        ISO formatted timestamp string

    Example:
        >>> ts = get_current_timestamp()
        >>> ts.endswith('Z') or '+' in ts
        True
    """
    return datetime.now(timezone.utc).isoformat()


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """
    Format datetime object to string.

    Args:
        dt: Datetime object to format
        fmt: Format string (default: YYYY-MM-DD)

    Returns:
        Formatted date string

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2026, 1, 8, 12, 0, 0)
        >>> format_date(dt)
        '2026-01-08'
    """
    return dt.strftime(fmt)


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string to datetime object.

    Tries multiple common formats. Returns None if parsing fails.

    Args:
        date_str: Date string to parse

    Returns:
        Datetime object or None if parsing fails

    Example:
        >>> dt = parse_date("2026-01-08")
        >>> dt.year
        2026

        >>> parse_date("invalid") is None
        True
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()

    # Common formats to try
    formats = [
        "%Y-%m-%d",              # 2026-01-08
        "%Y/%m/%d",              # 2026/01/08
        "%d-%m-%Y",              # 08-01-2026
        "%d/%m/%Y",              # 08/01/2026
        "%m/%d/%Y",              # 01/08/2026
        "%Y-%m-%dT%H:%M:%S",     # 2026-01-08T12:00:00
        "%Y-%m-%d %H:%M:%S",     # 2026-01-08 12:00:00
        "%B %d, %Y",             # January 8, 2026
        "%b %d, %Y",             # Jan 8, 2026
        "%d %B %Y",              # 8 January 2026
        "%d %b %Y",              # 8 Jan 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    logger.debug(f"Could not parse date: {date_str}")
    return None


def parse_relative_date(relative_str: str) -> Optional[datetime]:
    """
    Parse relative date strings like "2 days ago", "1 week ago".

    Args:
        relative_str: Relative date string

    Returns:
        Datetime object or None if parsing fails

    Example:
        >>> # Hard to test precisely, but should return recent date
        >>> dt = parse_relative_date("1 day ago")
        >>> dt is not None
        True
    """
    if not relative_str:
        return None

    relative_str = relative_str.lower().strip()
    now = datetime.now(timezone.utc)

    # Handle "today", "yesterday"
    if "today" in relative_str:
        return now
    if "yesterday" in relative_str:
        from datetime import timedelta
        return now - timedelta(days=1)

    # Try to extract number and unit
    import re
    match = re.search(r'(\d+)\s*(day|week|month|year)s?\s*ago', relative_str)
    if match:
        from datetime import timedelta
        num = int(match.group(1))
        unit = match.group(2)

        if unit == "day":
            return now - timedelta(days=num)
        elif unit == "week":
            return now - timedelta(weeks=num)
        elif unit == "month":
            return now - timedelta(days=num * 30)  # Approximate
        elif unit == "year":
            return now - timedelta(days=num * 365)  # Approximate

    logger.debug(f"Could not parse relative date: {relative_str}")
    return None


def is_recent_date(dt: datetime, days: int = 30) -> bool:
    """
    Check if a datetime is recent (within specified days).

    Args:
        dt: Datetime to check
        days: Number of days to consider "recent"

    Returns:
        True if date is within the last N days

    Example:
        >>> now = datetime.now(timezone.utc)
        >>> is_recent_date(now, days=30)
        True
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)

    # Make dt timezone-aware if it isn't
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age = now - dt
    return age <= timedelta(days=days)
