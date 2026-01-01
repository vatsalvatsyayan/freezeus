-- ============================================================================
-- DATABASE MIGRATION - Run this in Supabase SQL Editor
-- ============================================================================
--
-- Instructions:
-- 1. Go to: https://supabase.com/dashboard/project/kzkhhxmktwrxbyimylrn
-- 2. Click "SQL Editor" in left sidebar
-- 3. Click "New Query"
-- 4. Copy and paste this entire file
-- 5. Click "Run" button
-- 6. Verify you see 5 rows in the result at the bottom
--
-- ============================================================================

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

-- ============================================================================
-- VERIFICATION - You should see 5 rows below after running
-- ============================================================================

SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'jobs'
  AND column_name IN ('country', 'weekly_hours', 'apply_url', 'job_id', 'role_number')
ORDER BY column_name;

-- ============================================================================
-- Expected Result: 5 rows showing the new columns
-- ============================================================================
--  column_name  | data_type          | is_nullable
-- --------------+--------------------+-------------
--  apply_url    | text               | YES
--  country      | character varying  | YES
--  job_id       | character varying  | YES
--  role_number  | character varying  | YES
--  weekly_hours | character varying  | YES
-- ============================================================================
