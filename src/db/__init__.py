"""
Database module for Freezeus backend.

This module handles all database operations including:
- Pydantic models for data validation
- Supabase client for database operations
- Schema definitions and migrations
"""

from src.db.models import (
    JobPosting,
    JobRecord,
    JobExtra,
    PageData,
)

from src.db.supabase_client import (
    get_supabase,
    is_supabase_enabled,
    upsert_jobs_for_page,
)

__all__ = [
    # Models
    "JobPosting",
    "JobRecord",
    "JobExtra",
    "PageData",
    # Client functions
    "get_supabase",
    "is_supabase_enabled",
    "upsert_jobs_for_page",
]
