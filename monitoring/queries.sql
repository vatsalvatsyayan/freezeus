-- ================================================================
-- Freezeus Error Monitoring Queries
-- ================================================================
-- These queries help identify patterns and debug issues in the
-- job scraping pipeline by analyzing the error_logs table.
--
-- Execute these in Supabase SQL Editor or via psql
-- ================================================================

-- ================================================================
-- 1. QUICK HEALTH CHECK
-- ================================================================

-- Recent error count by severity (last 24 hours)
SELECT
  severity,
  COUNT(*) as error_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM error_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY severity
ORDER BY
  CASE severity
    WHEN 'critical' THEN 1
    WHEN 'error' THEN 2
    WHEN 'warning' THEN 3
    WHEN 'info' THEN 4
    ELSE 5
  END;

-- Top 10 failing domains (last 7 days)
SELECT
  domain,
  COUNT(*) as error_count,
  COUNT(DISTINCT error_type) as unique_error_types,
  MAX(created_at) as latest_error
FROM error_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY domain
ORDER BY error_count DESC
LIMIT 10;


-- ================================================================
-- 2. COMPONENT-SPECIFIC ANALYSIS
-- ================================================================

-- Crawler errors by stage (identify bottlenecks)
SELECT
  stage,
  error_type,
  COUNT(*) as occurrences,
  COUNT(DISTINCT domain) as affected_domains,
  MAX(created_at) as latest_occurrence
FROM error_logs
WHERE component = 'crawler'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY stage, error_type
ORDER BY occurrences DESC;

-- LLM extraction failures
SELECT
  stage,
  error_type,
  COUNT(*) as failures,
  COUNT(DISTINCT domain) as affected_domains,
  AVG(LENGTH(message)) as avg_message_length
FROM error_logs
WHERE component = 'llm'
  AND severity IN ('error', 'critical')
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY stage, error_type
ORDER BY failures DESC;

-- Database validation errors (data quality issues)
SELECT
  stage,
  error_type,
  domain,
  COUNT(*) as validation_errors,
  MAX(created_at) as latest_error,
  (metadata->>'page_title')::text as page_title
FROM error_logs
WHERE component = 'db'
  AND error_type = 'validation_error'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY stage, error_type, domain, (metadata->>'page_title')::text
ORDER BY validation_errors DESC
LIMIT 20;


-- ================================================================
-- 3. DOMAIN-SPECIFIC DEBUGGING
-- ================================================================

-- Full error history for a specific domain
-- Replace 'jobs.apple.com' with your domain
SELECT
  created_at,
  component,
  stage,
  error_type,
  severity,
  message,
  url,
  exception_type,
  metadata
FROM error_logs
WHERE domain = 'jobs.apple.com'
ORDER BY created_at DESC
LIMIT 50;

-- Error timeline for a domain (hourly breakdown)
SELECT
  DATE_TRUNC('hour', created_at) as hour,
  component,
  COUNT(*) as error_count
FROM error_logs
WHERE domain = 'jobs.dropbox.com'
  AND created_at > NOW() - INTERVAL '48 hours'
GROUP BY DATE_TRUNC('hour', created_at), component
ORDER BY hour DESC;


-- ================================================================
-- 4. ERROR TYPE ANALYSIS
-- ================================================================

-- Most common timeout errors
SELECT
  component,
  stage,
  domain,
  COUNT(*) as timeout_count,
  MAX(created_at) as latest,
  (metadata->>'nav_timeout_ms')::int as timeout_setting
FROM error_logs
WHERE error_type = 'timeout'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY component, stage, domain, (metadata->>'nav_timeout_ms')::int
ORDER BY timeout_count DESC
LIMIT 20;

-- JSON parsing failures (LLM issues)
SELECT
  domain,
  COUNT(*) as parse_failures,
  MAX(created_at) as latest_failure,
  AVG((metadata->>'response_length')::int) as avg_response_length,
  STRING_AGG(DISTINCT (metadata->>'page_title')::text, ', ') as affected_pages
FROM error_logs
WHERE error_type = 'json_error'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY domain
ORDER BY parse_failures DESC;

-- Browser/navigation errors (sites that might be blocking)
SELECT
  domain,
  error_type,
  COUNT(*) as error_count,
  MAX(created_at) as latest,
  MODE() WITHIN GROUP (ORDER BY message) as most_common_message
FROM error_logs
WHERE error_type IN ('browser_error', 'navigation_error', 'timeout')
  AND component = 'crawler'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY domain, error_type
ORDER BY error_count DESC
LIMIT 20;


-- ================================================================
-- 5. TREND ANALYSIS
-- ================================================================

-- Error rate over time (daily)
SELECT
  DATE_TRUNC('day', created_at) as day,
  component,
  error_type,
  COUNT(*) as error_count
FROM error_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at), component, error_type
ORDER BY day DESC, error_count DESC;

-- New vs recurring errors (domains that started failing recently)
WITH recent_errors AS (
  SELECT DISTINCT domain, MIN(created_at) as first_error
  FROM error_logs
  WHERE severity IN ('error', 'critical')
  GROUP BY domain
)
SELECT
  domain,
  first_error,
  CASE
    WHEN first_error > NOW() - INTERVAL '7 days' THEN 'New (< 7 days)'
    WHEN first_error > NOW() - INTERVAL '30 days' THEN 'Recent (< 30 days)'
    ELSE 'Recurring (> 30 days)'
  END as error_age,
  (SELECT COUNT(*) FROM error_logs WHERE domain = recent_errors.domain) as total_errors
FROM recent_errors
ORDER BY first_error DESC;


-- ================================================================
-- 6. METADATA ANALYSIS
-- ================================================================

-- Analyze timeout configurations
SELECT
  (metadata->>'nav_timeout_ms')::int as timeout_ms,
  COUNT(*) as timeout_errors,
  COUNT(DISTINCT domain) as affected_domains,
  ROUND(AVG((metadata->>'attempt')::int), 1) as avg_retry_attempt
FROM error_logs
WHERE error_type = 'timeout'
  AND metadata->>'nav_timeout_ms' IS NOT NULL
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY (metadata->>'nav_timeout_ms')::int
ORDER BY timeout_errors DESC;

-- Job validation failures (data quality patterns)
SELECT
  (metadata->>'job_title')::text as failing_job_title,
  domain,
  COUNT(*) as validation_failures,
  MAX(message) as error_message
FROM error_logs
WHERE stage = 'validate_job'
  AND metadata->>'job_title' IS NOT NULL
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY (metadata->>'job_title')::text, domain
ORDER BY validation_failures DESC
LIMIT 20;


-- ================================================================
-- 7. SUCCESS RATE ESTIMATION
-- ================================================================

-- Domains without errors (recently crawled, working fine)
-- Note: This requires comparing with your jobs table
SELECT
  j.domain,
  COUNT(DISTINCT j.job_url) as jobs_found,
  COALESCE(e.error_count, 0) as errors,
  ROUND(COUNT(DISTINCT j.job_url)::numeric / NULLIF(COALESCE(e.error_count, 0), 0), 2) as jobs_per_error
FROM jobs j
LEFT JOIN (
  SELECT domain, COUNT(*) as error_count
  FROM error_logs
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY domain
) e ON j.domain = e.domain
WHERE j.last_seen_at > NOW() - INTERVAL '7 days'
GROUP BY j.domain, e.error_count
ORDER BY errors ASC, jobs_found DESC
LIMIT 20;


-- ================================================================
-- 8. CRITICAL ALERTS
-- ================================================================

-- Critical errors requiring immediate attention
SELECT
  created_at,
  domain,
  component,
  stage,
  error_type,
  message,
  url,
  exception_type,
  metadata
FROM error_logs
WHERE severity = 'critical'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;

-- Domains failing completely (all recent attempts failed)
WITH domain_stats AS (
  SELECT
    domain,
    COUNT(*) as total_errors,
    COUNT(DISTINCT DATE_TRUNC('hour', created_at)) as error_hours,
    MIN(created_at) as first_error,
    MAX(created_at) as latest_error,
    COUNT(DISTINCT error_type) as unique_error_types
  FROM error_logs
  WHERE created_at > NOW() - INTERVAL '48 hours'
  GROUP BY domain
)
SELECT *
FROM domain_stats
WHERE error_hours >= 4  -- Failing for multiple hours
  AND total_errors >= 10  -- Multiple failures
ORDER BY total_errors DESC;


-- ================================================================
-- 9. PERFORMANCE INSIGHTS
-- ================================================================

-- Average errors per domain by component
SELECT
  component,
  COUNT(DISTINCT domain) as affected_domains,
  COUNT(*) as total_errors,
  ROUND(COUNT(*)::numeric / COUNT(DISTINCT domain), 2) as errors_per_domain
FROM error_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY component
ORDER BY errors_per_domain DESC;

-- Error frequency by day of week (identify patterns)
SELECT
  TO_CHAR(created_at, 'Day') as day_of_week,
  EXTRACT(DOW FROM created_at) as dow_num,
  COUNT(*) as error_count,
  COUNT(DISTINCT domain) as affected_domains
FROM error_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY day_of_week, dow_num
ORDER BY dow_num;


-- ================================================================
-- 10. CLEANUP & MAINTENANCE
-- ================================================================

-- Delete old debug/info logs (keep only warnings and above)
-- CAUTION: Uncomment only when ready to delete
-- DELETE FROM error_logs
-- WHERE severity IN ('debug', 'info')
--   AND created_at < NOW() - INTERVAL '30 days';

-- Archive old errors (move to archive table)
-- CAUTION: Create error_logs_archive table first
-- INSERT INTO error_logs_archive
-- SELECT * FROM error_logs
-- WHERE created_at < NOW() - INTERVAL '90 days';
--
-- DELETE FROM error_logs
-- WHERE created_at < NOW() - INTERVAL '90 days';

-- Get table size and row count
SELECT
  COUNT(*) as total_errors,
  MIN(created_at) as oldest_error,
  MAX(created_at) as newest_error,
  pg_size_pretty(pg_total_relation_size('error_logs')) as table_size
FROM error_logs;
