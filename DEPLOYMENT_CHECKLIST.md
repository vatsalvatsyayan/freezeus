# Deployment Checklist ✅

## Status: Ready to Deploy

All code changes are complete and tested. Follow these steps to deploy:

---

## Step 1: Run Database Migration ⚠️ REQUIRED

**Time**: 2 minutes

### Option A: Via Supabase Dashboard (Recommended)

1. **Open Supabase Dashboard**:
   - Go to: https://supabase.com/dashboard/project/kzkhhxmktwrxbyimylrn/sql/new

2. **Copy SQL**:
   - Open file: `RUN_THIS_MIGRATION.sql`
   - Copy entire contents

3. **Run Migration**:
   - Paste SQL into the editor
   - Click "RUN" button (bottom right)

4. **Verify Success**:
   - You should see 5 rows in the result table:
     - `apply_url`
     - `country`
     - `job_id`
     - `role_number`
     - `weekly_hours`

### Option B: Quick Copy-Paste

```sql
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS weekly_hours VARCHAR(50),
ADD COLUMN IF NOT EXISTS apply_url TEXT,
ADD COLUMN IF NOT EXISTS job_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS role_number VARCHAR(50);

-- Verify
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'jobs'
  AND column_name IN ('country', 'weekly_hours', 'apply_url', 'job_id', 'role_number')
ORDER BY column_name;
```

---

## Step 2: Push Code to GitHub

**After migration succeeds:**

```bash
# Verify you're on logic-update branch
git branch --show-current

# Push changes
git push origin logic-update
```

---

## Step 3: Test Locally (Optional but Recommended)

```bash
# Create test URL
echo "https://slack.com/careers" > configs/test_single.txt

# Run crawler
python -m src.crawler.multi_capture \
  --urls configs/test_single.txt \
  --with-llm \
  --jobs-max 10

# Check output
cat out/slack.com/llm/*.jobs.json | python3 -m json.tool | head -100
```

**Verify in output:**
- ✅ job_url starts with `https://`
- ✅ country field is populated
- ✅ team_or_category uses standard values

---

## Step 4: Monitor First Production Run

After GitHub Actions runs the crawler (every 6 hours), check:

```sql
-- Check for complete URLs
SELECT COUNT(*) as incomplete_urls
FROM jobs
WHERE first_seen_at > NOW() - INTERVAL '6 hours'
  AND job_url NOT LIKE 'http%';
-- Expected: 0

-- Check country population
SELECT
  COUNT(*) as total,
  COUNT(country) as with_country,
  ROUND(100.0 * COUNT(country) / COUNT(*), 2) as country_rate
FROM jobs
WHERE first_seen_at > NOW() - INTERVAL '6 hours';
-- Expected: country_rate > 90%

-- View sample of new jobs
SELECT
  title,
  job_url,
  country,
  team_or_category,
  first_seen_at
FROM jobs
WHERE first_seen_at > NOW() - INTERVAL '6 hours'
ORDER BY first_seen_at DESC
LIMIT 10;
```

---

## Rollback Plan (If Needed)

If something goes wrong:

```bash
# Revert code
git checkout src/llm/llm_helper.py
git checkout src/db/supabase_client.py
git checkout configs/llm_extraction_prompt.txt

# Delete bad data (optional)
# See MIGRATION_INSTRUCTIONS.md for SQL

# Force push
git push origin logic-update --force
```

---

## What Changed

✅ **Code Changes** (Commit: 342cf2e):
- URL normalization (relative → absolute)
- External LLM prompt
- Enhanced database upsert
- first_seen_at/last_seen_at tracking
- Country field extraction
- JSONB data extraction

✅ **Database Changes** (After migration):
- New columns: country, weekly_hours, apply_url, job_id, role_number
- New index: idx_jobs_country

---

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Complete URLs | 96.9% | 100% ✅ |
| Country field | 0% | ~95%+ ✅ |
| Job descriptions | 0% in main field | ~75%+ ✅ |
| first_seen_at accuracy | Overwritten | Preserved ✅ |

---

## Checklist

- [ ] **Database migration completed** (verified 5 new columns)
- [ ] **Code pushed to GitHub** (`git push origin logic-update`)
- [ ] **Local test run** (optional - recommended)
- [ ] **Monitor first production run**

---

## Files to Reference

- [RUN_THIS_MIGRATION.sql](RUN_THIS_MIGRATION.sql) - Copy-paste SQL migration
- [MIGRATION_INSTRUCTIONS.md](MIGRATION_INSTRUCTIONS.md) - Detailed migration guide
- [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) - Complete status report
- [docs/analysis/NEXT_STEPS_README.md](docs/analysis/NEXT_STEPS_README.md) - Full documentation

---

## Current Status

✅ Code: **COMPLETE** (committed to logic-update)
⏳ Migration: **PENDING** (you run this)
⏳ Deployment: **PENDING** (after migration)

**Next action: Run the database migration using the SQL above** ⬆️
