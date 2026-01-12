# Monitoring & Error Dashboard

Production-level error monitoring and analytics for the Freezeus job scraping pipeline.

## 📁 Contents

```
monitoring/
├── README.md              # This file
├── error_dashboard.py     # Interactive error analytics dashboard
└── queries.sql            # SQL queries for Supabase analysis
```

## 🎯 Purpose

The monitoring system tracks all failures across the entire pipeline:
- **Crawler**: Navigation timeouts, blocked requests, click failures, HTML reduction errors
- **LLM**: JSON parsing failures, API errors, extraction issues
- **Database**: Validation errors, upsert failures, connection issues

With comprehensive error logs, you can:
- ✅ Identify which companies are failing and why
- ✅ Debug specific domains without manual testing
- ✅ Track error trends over time
- ✅ Optimize retry strategies and timeouts
- ✅ Scale your company list confidently

---

## 🚀 Quick Start

### View Error Dashboard

```bash
# Full dashboard (summary + domain breakdown + critical errors)
python monitoring/error_dashboard.py

# Filter by domain
python monitoring/error_dashboard.py --domain jobs.apple.com

# Show only recent errors
python monitoring/error_dashboard.py --hours 24

# Show detailed report for a specific domain
python monitoring/error_dashboard.py --detail jobs.dropbox.com

# Filter by component
python monitoring/error_dashboard.py --component crawler

# Filter by severity
python monitoring/error_dashboard.py --severity critical

# Export to CSV for analysis
python monitoring/error_dashboard.py --export csv
```

### Run SQL Queries

Execute queries from `queries.sql` in:
1. **Supabase Dashboard** → SQL Editor
2. **psql** command line
3. **Python** using `supabase.table().execute()`

---

## 📊 Error Dashboard Features

### 1. **Error Summary**
- Total errors by severity (critical, error, warning)
- Breakdown by component (crawler, llm, db)
- Top error types
- Time range analysis

### 2. **Errors by Company/Domain**
Shows which companies have the most issues:
```
Domain                                   Errors   Top Issue
------------------------------------------------------------------------------
jobs.dropbox.com                         45       timeout
careers.google.com                       32       json_error
apply.workable.com                       28       validation_error
...
```

### 3. **Errors by Pipeline Stage**
Identifies bottlenecks in your pipeline:
```
Stage                                            Errors   Domains
------------------------------------------------------------------------------
crawler:navigate_seed                            120      45
llm:parse_json                                   89       32
db:validate_job                                  67       28
...
```

### 4. **Critical Errors**
Lists recent critical/error severity issues with full context:
- Timestamp
- Domain
- Component → Stage
- Error type
- Message
- URL

---

## 🔍 Common Use Cases

### Use Case 1: Debug a Specific Company

```bash
# Get detailed error report
python monitoring/error_dashboard.py --detail jobs.apple.com
```

**Output includes:**
- Total error count
- Error timeline (last 10 errors)
- Breakdown by component
- Breakdown by pipeline stage
- Breakdown by error type
- Full details of most recent error

### Use Case 2: Find All Timeout Errors

```sql
-- In Supabase SQL Editor
SELECT domain, stage, COUNT(*) as timeout_count
FROM error_logs
WHERE error_type = 'timeout'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY domain, stage
ORDER BY timeout_count DESC;
```

### Use Case 3: Identify LLM Parse Failures

```bash
python monitoring/error_dashboard.py --component llm --hours 48
```

Or use SQL:
```sql
SELECT domain, COUNT(*) as parse_failures
FROM error_logs
WHERE error_type = 'json_error' AND component = 'llm'
GROUP BY domain
ORDER BY parse_failures DESC;
```

### Use Case 4: Track Error Trends

```bash
# Export last 7 days to CSV for charting
python monitoring/error_dashboard.py --hours 168 --export csv
```

Then analyze in Excel/Sheets/Pandas.

### Use Case 5: Find Healthy Domains (No Errors)

```sql
-- Domains with successful jobs and minimal errors
SELECT
  j.domain,
  COUNT(DISTINCT j.job_url) as jobs_found,
  COALESCE(e.error_count, 0) as errors
FROM jobs j
LEFT JOIN (
  SELECT domain, COUNT(*) as error_count
  FROM error_logs
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY domain
) e ON j.domain = e.domain
WHERE j.last_seen_at > NOW() - INTERVAL '7 days'
GROUP BY j.domain, e.error_count
HAVING COALESCE(e.error_count, 0) < 5
ORDER BY jobs_found DESC;
```

---

## 📋 Error Types Reference

### Crawler Errors

| Error Type | Stage | Meaning | Fix |
|------------|-------|---------|-----|
| `timeout` | `navigate_seed` | Page took >45s to load | Increase `NAV_TIMEOUT_MS` or site is blocking |
| `browser_error` | `reduce_html` | JavaScript reduction failed | Check if site uses unusual DOM structure |
| `timeout` | `wait_for_jobs` | No job listings detected | Site might load jobs dynamically - increase wait time |
| `navigation_error` | `navigate_seed` | Page failed to load | Site might be down or blocking crawler |
| `element_not_found` | `click_load_more` | "Load More" button not found | Site uses custom pagination selectors |
| `element_not_found` | `click_next_page` | "Next" button not found | Site uses infinite scroll instead of pagination |

### LLM Errors

| Error Type | Stage | Meaning | Fix |
|------------|-------|---------|-----|
| `json_error` | `parse_json` | Gemini returned invalid JSON | LLM hallucinated - reduce HTML size or improve prompt |
| `api_error` | `call_llm` | Gemini API failed | Check API key, quota, or network |
| `timeout` | `call_llm` | LLM took too long | Reduce HTML input size |
| `rate_limit` | `call_llm` | Hit API rate limit | Add delays between requests |

### Database Errors

| Error Type | Stage | Meaning | Fix |
|------------|-------|---------|-----|
| `validation_error` | `validate_job` | Job data missing required fields | LLM extracted incomplete data |
| `validation_error` | `validate_page` | Page structure invalid | LLM returned wrong format |
| `db_upsert_error` | `upsert_jobs` | Failed to save to Supabase | Check database connection or schema |
| `db_query_error` | `check_existing` | Failed to query existing jobs | Database connection issue |

---

## 📈 SQL Queries Reference

The `queries.sql` file contains 10 categories of pre-built queries:

### 1. **Quick Health Check**
- Recent error count by severity
- Top 10 failing domains

### 2. **Component-Specific Analysis**
- Crawler errors by stage
- LLM extraction failures
- Database validation errors

### 3. **Domain-Specific Debugging**
- Full error history for a domain
- Error timeline (hourly breakdown)

### 4. **Error Type Analysis**
- Timeout errors
- JSON parsing failures
- Browser/navigation errors

### 5. **Trend Analysis**
- Error rate over time (daily)
- New vs recurring errors

### 6. **Metadata Analysis**
- Timeout configuration analysis
- Job validation failure patterns

### 7. **Success Rate Estimation**
- Domains without errors
- Jobs per error ratio

### 8. **Critical Alerts**
- Critical errors requiring attention
- Domains failing completely

### 9. **Performance Insights**
- Errors per domain by component
- Error frequency by day of week

### 10. **Cleanup & Maintenance**
- Delete old logs
- Archive errors
- Table size stats

---

## 🛠️ Error Logging Integration

### How Errors Are Logged

The error logging system is integrated throughout the codebase:

**Crawler Module:**
- [src/crawler/navigation.py](../src/crawler/navigation.py) - Navigation failures, HTML reduction errors
- [src/crawler/page_analyzer.py](../src/crawler/page_analyzer.py) - Job detection timeouts
- [src/crawler/multi_capture.py](../src/crawler/multi_capture.py) - Top-level crawl failures

**LLM Module:**
- [src/llm/extractor.py](../src/llm/extractor.py) - JSON parse failures, Supabase upsert from extractor

**Database Module:**
- [src/db/supabase_client.py](../src/db/supabase_client.py) - Validation errors, upsert failures

### Error Logger API

```python
from src.core.error_logger import get_error_logger
from src.core.error_models import ErrorComponent, ErrorSeverity, ErrorType, ErrorStage

error_logger = get_error_logger()

# Log an exception (auto-classifies error type)
try:
    result = risky_operation()
except Exception as e:
    error_logger.log_exception(
        e,
        component=ErrorComponent.CRAWLER,
        stage=ErrorStage.NAVIGATE_SEED,
        domain="jobs.example.com",
        url="https://jobs.example.com/careers",
        metadata={"timeout_ms": 45000}
    )

# Or log manually
error_logger.log_error(
    component=ErrorComponent.LLM,
    stage=ErrorStage.PARSE_JSON,
    error_type=ErrorType.JSON_ERROR,
    domain="jobs.example.com",
    message="LLM returned malformed JSON",
    severity=ErrorSeverity.ERROR,
    metadata={"response_preview": response[:500]}
)
```

### Error Stages

All error stages are defined in [src/core/error_models.py](../src/core/error_models.py):

**Crawler Stages:**
- `NAVIGATE_SEED` - Initial page navigation
- `EXPAND_IN_PAGE` - Load more / infinite scroll
- `PAGINATE` - Clicking "Next" buttons
- `SNAPSHOT` - Taking page snapshot
- `REDUCE_HTML` - JavaScript reduction
- `CLICK_LOAD_MORE` - Clicking load more buttons
- `CLICK_NEXT_PAGE` - Clicking pagination
- `WAIT_FOR_JOBS` - Waiting for job listings to load
- `SCROLL_TO_BOTTOM` - Infinite scroll attempts
- `DETECT_JOBS` - Job link detection
- `CHECK_PROGRESS` - Page progress detection

**LLM Stages:**
- `CALL_LLM` - Gemini API call
- `PARSE_JSON` - JSON parsing
- `NORMALIZE_JOBS` - Job normalization
- `DEDUPE_JOBS` - Deduplication

**Database Stages:**
- `VALIDATE_PAGE` - Page data validation
- `VALIDATE_JOB` - Job data validation
- `CHECK_EXISTING` - Query existing jobs
- `UPSERT_JOBS` - Insert/update jobs
- `UPSERT_FROM_EXTRACTOR` - Upsert from LLM extractor

---

## 🔔 Setting Up Alerts (Optional)

### Supabase Webhooks

Set up webhooks to get notified of critical errors:

1. Go to Supabase Dashboard → Database → Webhooks
2. Create webhook on `error_logs` table
3. Filter: `severity = 'critical'`
4. Send to Slack, Discord, or email service

### Example: Slack Notification

```sql
-- Create webhook function
CREATE OR REPLACE FUNCTION notify_slack_on_critical_error()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM net.http_post(
    url := 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
    body := json_build_object(
      'text', '🚨 Critical Error: ' || NEW.domain || ' - ' || NEW.message
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
CREATE TRIGGER critical_error_slack_notification
  AFTER INSERT ON error_logs
  FOR EACH ROW
  WHEN (NEW.severity = 'critical')
  EXECUTE FUNCTION notify_slack_on_critical_error();
```

---

## 📊 Sample Dashboard Output

```
================================================================================
 📊 ERROR SUMMARY
================================================================================
Total Errors: 247

By Severity:
  CRITICAL        12 ( 4.9%)
  ERROR          89 (36.0%)
  WARNING       146 (59.1%)

By Component:
  crawler       145 (58.7%)
  llm            67 (27.1%)
  db             35 (14.2%)

Top Error Types:
  timeout                         98 (39.7%)
  json_error                      45 (18.2%)
  validation_error                32 (13.0%)
  browser_error                   28 (11.3%)
  navigation_error                24 ( 9.7%)

Time Range:
  First: 2026-01-07 10:23:45 UTC
  Last:  2026-01-09 15:42:12 UTC
  Span:  53.3 hours

================================================================================
 🏢 ERRORS BY COMPANY/DOMAIN
================================================================================

Domain                                   Errors   Top Issue
------------------------------------------------------------------------------
jobs.dropbox.com                         45       timeout
careers.google.com                       32       json_error
apply.workable.com                       28       validation_error
jobs.lever.co                            24       browser_error
greenhouse.io                            18       navigation_error
...

================================================================================
 🔄 ERRORS BY PIPELINE STAGE
================================================================================

Stage                                            Errors   Domains
------------------------------------------------------------------------------
crawler:navigate_seed                            98       38
llm:parse_json                                   45       22
db:validate_job                                  32       18
crawler:wait_for_jobs                            28       15
crawler:reduce_html                              24       12
...

================================================================================
 🚨 CRITICAL & ERROR SEVERITY ISSUES
================================================================================

[CRITICAL] 2026-01-09 15:30:22
  Domain:    jobs.dropbox.com
  Component: crawler → navigate_seed
  Type:      timeout
  Message:   Failed to load https://jobs.dropbox.com/all-jobs after 3 attempts
  URL:       https://jobs.dropbox.com/all-jobs

[ERROR] 2026-01-09 14:15:10
  Domain:    careers.google.com
  Component: llm → parse_json
  Type:      json_error
  Message:   Primary JSON parse failed, attempting fixer
  URL:       https://careers.google.com/jobs/results/

...
```

---

## 🎓 Best Practices

### 1. **Regular Monitoring**
- Check dashboard daily during development
- Run weekly reports in production
- Set up alerts for critical errors

### 2. **Use Filters**
- Focus on recent errors (`--hours 24`)
- Investigate one component at a time (`--component crawler`)
- Drill down into specific domains (`--detail domain.com`)

### 3. **Export for Analysis**
- Export to CSV for trend analysis
- Create charts in Excel/Sheets
- Track error rates over time

### 4. **Prioritize Fixes**
- Fix critical errors first
- Address systematic failures (affecting many domains)
- Optimize for most common error types

### 5. **Clean Up Old Logs**
- Archive errors older than 90 days
- Delete debug/info logs after 30 days
- Keep warnings/errors/critical indefinitely

---

## 🔗 Related Documentation

- [Error Logging System](../src/core/README.md) - Error logger implementation
- [Database Module](../src/db/README.md) - Database integration
- [Crawler Module](../src/crawler/README.md) - Crawler architecture
- [LLM Module](../src/llm/README.md) - LLM extraction pipeline

---

## 💡 Tips

### Finding Patterns

```bash
# Which domains timeout most often?
python monitoring/error_dashboard.py --hours 168 | grep timeout

# Are LLM failures concentrated in specific domains?
python monitoring/error_dashboard.py --component llm --hours 48

# What's the error distribution by severity?
python monitoring/error_dashboard.py | grep "By Severity" -A 5
```

### Quick Debugging

```bash
# Check if a specific domain is having issues
python monitoring/error_dashboard.py --detail jobs.apple.com

# See if errors are recent or ongoing
python monitoring/error_dashboard.py --hours 24

# Export full history for deep analysis
python monitoring/error_dashboard.py --export csv
```

### SQL Power Users

```sql
-- Custom query: Find domains with >50% error rate
WITH domain_attempts AS (
  SELECT domain, COUNT(*) as attempts
  FROM error_logs
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY domain
),
domain_successes AS (
  SELECT domain, COUNT(DISTINCT job_url) as jobs
  FROM jobs
  WHERE last_seen_at > NOW() - INTERVAL '7 days'
  GROUP BY domain
)
SELECT
  a.domain,
  a.attempts as errors,
  COALESCE(s.jobs, 0) as jobs,
  ROUND(a.attempts::numeric / (a.attempts + COALESCE(s.jobs, 0)) * 100, 2) as error_rate_pct
FROM domain_attempts a
LEFT JOIN domain_successes s ON a.domain = s.domain
WHERE a.attempts > 5
ORDER BY error_rate_pct DESC;
```

---

## 🙋 FAQ

**Q: How long are errors stored?**
A: Forever by default. Use cleanup queries to archive/delete old logs.

**Q: Can I query errors from Python?**
A: Yes! Use `get_error_logger().get_errors_for_domain(domain)` or query Supabase directly.

**Q: Are errors logged if Supabase is down?**
A: Yes! Errors fall back to `logs/errors/errors_YYYYMMDD.jsonl` files.

**Q: Do errors slow down the crawler?**
A: No. Error logging is synchronous but fast (<10ms), and failures are soft.

**Q: Can I add custom error types?**
A: Yes! Add to `ErrorType` enum in [src/core/error_models.py](../src/core/error_models.py).

**Q: How do I export errors to a data warehouse?**
A: Use Supabase's native replication or export via CSV and import.

---

**Happy Monitoring! 🎉**

For questions or issues, check the main [README](../README.md) or create an issue on GitHub.
