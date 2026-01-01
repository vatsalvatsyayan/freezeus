#!/usr/bin/env python3
"""
Check if the new columns exist in the database schema.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.supabase_client import get_supabase

def check_schema():
    """Check if migration columns exist."""
    client = get_supabase()
    if not client:
        print("❌ Supabase client not initialized. Check your .env file.")
        return

    print("=" * 80)
    print("CHECKING DATABASE SCHEMA")
    print("=" * 80)
    print()

    try:
        # Query information_schema to check for columns
        result = client.rpc('exec', {
            'query': '''
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'jobs'
                  AND column_name IN ('country', 'weekly_hours', 'apply_url', 'job_id', 'role_number', 'first_seen_at', 'last_seen_at')
                ORDER BY column_name;
            '''
        }).execute()

        if result.data:
            print("Found columns:")
            for col in result.data:
                print(f"  - {col['column_name']:20} ({col['data_type']:15}) nullable={col['is_nullable']}")

        # Check which columns are missing
        expected_cols = {'country', 'weekly_hours', 'apply_url', 'job_id', 'role_number', 'first_seen_at', 'last_seen_at'}
        found_cols = {col['column_name'] for col in result.data} if result.data else set()
        missing_cols = expected_cols - found_cols

        print()
        if missing_cols:
            print(f"⚠️  Missing columns: {', '.join(sorted(missing_cols))}")
            print()
            print("You need to run the migration SQL manually.")
            print("See: docs/analysis/add_country_column.sql")
        else:
            print("✅ All required columns exist!")

    except Exception as e:
        print(f"Error checking schema: {e}")
        print()
        print("Attempting direct table query to check columns...")

        try:
            # Try to query the table directly to see what columns exist
            result = client.from_('jobs').select('*').limit(1).execute()
            if result.data and len(result.data) > 0:
                print("\nFound these columns in jobs table:")
                for col in sorted(result.data[0].keys()):
                    print(f"  - {col}")

                # Check for new columns
                has_country = 'country' in result.data[0]
                has_first_seen = 'first_seen_at' in result.data[0]
                has_last_seen = 'last_seen_at' in result.data[0]

                print()
                if has_country and has_first_seen and has_last_seen:
                    print("✅ Migration appears to be complete!")
                else:
                    print("⚠️  Some columns may be missing. Please run migration manually.")
                    print("See: docs/analysis/add_country_column.sql")
        except Exception as e2:
            print(f"❌ Could not query table: {e2}")

if __name__ == "__main__":
    check_schema()
