#!/usr/bin/env python3
"""
Run database migration using Supabase client.
Adds columns for improved data quality.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.supabase_client import get_supabase

def run_migration():
    """Run the database migration by executing SQL statements."""
    print("=" * 80)
    print("DATABASE MIGRATION: Adding columns for future data quality")
    print("=" * 80)
    print()

    client = get_supabase()
    if not client:
        print("❌ Supabase client not initialized. Check your .env file.")
        return False

    migrations = [
        ("Adding country column", "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country VARCHAR(100);"),
        ("Creating country index", "CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);"),
        ("Adding weekly_hours column", "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS weekly_hours VARCHAR(50);"),
        ("Adding apply_url column", "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS apply_url TEXT;"),
        ("Adding job_id column", "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_id VARCHAR(100);"),
        ("Adding role_number column", "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS role_number VARCHAR(50);"),
    ]

    for description, sql in migrations:
        print(f"{description}...", end=" ")
        try:
            # Use raw SQL execution via PostgREST
            response = client.postgrest.session.post(
                f"{client.supabase_url}/rest/v1/rpc/exec",
                json={"query": sql},
                headers=client.postgrest.headers
            )

            # Try alternative approach - direct table modification won't work
            # We need to use Supabase's SQL editor or direct postgres connection
            print("⚠️  (requires manual execution)")

        except Exception as e:
            print(f"⚠️  ({e})")

    print()
    print("=" * 80)
    print("MIGRATION NOTES")
    print("=" * 80)
    print()
    print("Supabase Python client doesn't support direct DDL execution.")
    print("You need to run the migration manually via Supabase Dashboard.")
    print()
    print("Steps:")
    print("1. Go to: https://supabase.com/dashboard/project/kzkhhxmktwrxbyimylrn")
    print("2. Click 'SQL Editor' in left sidebar")
    print("3. Click 'New Query'")
    print("4. Paste the SQL below:")
    print()
    print("-" * 80)
    print("""
-- Add country column for location filtering
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country VARCHAR(100);

-- Create index for fast filtering by country
CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);

-- Add additional fields from raw_extra (for future extraction)
ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS weekly_hours VARCHAR(50),
ADD COLUMN IF NOT EXISTS apply_url TEXT,
ADD COLUMN IF NOT EXISTS job_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS role_number VARCHAR(50);

-- Verify columns were added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'jobs'
  AND column_name IN ('country', 'weekly_hours', 'apply_url', 'job_id', 'role_number')
ORDER BY column_name;
""")
    print("-" * 80)
    print()
    print("5. Click 'Run' button")
    print("6. Verify you see 5 rows in the result")
    print()
    print("Or copy the SQL from: docs/analysis/add_country_column.sql")
    print()

    return False  # Manual migration required

if __name__ == "__main__":
    run_migration()
    sys.exit(0)  # Don't fail - just inform user
