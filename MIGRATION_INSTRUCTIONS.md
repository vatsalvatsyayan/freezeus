# Database Migration Required

## Status

✅ **Code changes complete** - All Python code has been updated
⚠️  **Database migration pending** - New columns need to be added manually

## Current Database State

The database already has these columns (good news!):
- `first_seen_at` ✅
- `last_seen_at` ✅
- `seniority_bucket` ✅
- `job_description` ✅

**Missing columns** that need to be added:
- `country` - For filtering jobs by country
- `weekly_hours` - Working hours info
- `apply_url` - Direct application URL
- `job_id` - Internal company job ID
- `role_number` - Requisition/role number

## How to Run the Migration

### Option 1: Via Supabase Dashboard (Recommended)

1. Go to https://supabase.com/dashboard/project/kzkhhxmktwrxbyimylrn
2. Click on "SQL Editor" in the left sidebar
3. Create a new query
4. Copy and paste the SQL below:

```sql
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
```

5. Click "Run" button
6. Verify you see 5 rows in the result (confirming all columns were added)

### Option 2: Via psql Command Line

If you have psql installed:

```bash
# Get your database connection string from Supabase dashboard
# Then run:
psql "<your-connection-string>" < docs/analysis/add_country_column.sql
```

### Option 3: Via Direct SQL Connection

Use any PostgreSQL client (DBeaver, pgAdmin, etc.) and run the SQL from the file:
`docs/analysis/add_country_column.sql`

## After Migration

Once the migration is complete, you can:

1. **Test locally** (optional but recommended):
   ```bash
   # Test on a single domain
   python -m src.crawler.multi_capture \
     --urls configs/test_single.txt \
     --with-llm \
     --jobs-max 10
   ```

2. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Implement future data quality improvements"
   git push origin logic-update
   ```

3. **Deploy**: The GitHub Actions crawler will automatically use the new code on next run

## What Will Happen After Migration

- ✅ All new jobs will have complete URLs (no more `/careers/jobs/123`)
- ✅ Country field will be populated for every job
- ✅ Team categories will be standardized
- ✅ Job descriptions extracted to main column (instead of JSONB)
- ✅ `first_seen_at` will be preserved (not overwritten on re-crawl)
- ✅ `last_seen_at` will track when job was last seen

## Existing Data

- ✅ **No impact** - 2,099 existing jobs remain unchanged
- ✅ New columns will be NULL for old jobs
- ✅ Frontend compatibility maintained - all existing queries work
