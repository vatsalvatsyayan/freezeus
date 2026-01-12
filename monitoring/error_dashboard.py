#!/usr/bin/env python3
"""
Error Dashboard for Freezeus Job Scraping Pipeline

Queries Supabase error_logs table and displays comprehensive error analytics.
Helps identify which companies are failing and why.

Usage:
    python monitoring/error_dashboard.py                    # Full dashboard
    python monitoring/error_dashboard.py --domain apple.com  # Filter by domain
    python monitoring/error_dashboard.py --hours 24         # Last 24 hours only
    python monitoring/error_dashboard.py --export csv       # Export to CSV
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path("configs/.env"), override=True)


def get_supabase_client():
    """Initialize Supabase client."""
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase package not installed. Run: pip install supabase")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in configs/.env")
        sys.exit(1)

    return create_client(url, key)


def query_errors(
    client,
    domain: Optional[str] = None,
    hours: Optional[int] = None,
    component: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Query error logs with optional filters.

    Args:
        client: Supabase client
        domain: Filter by domain
        hours: Only errors from last N hours
        component: Filter by component (crawler, llm, db)
        severity: Filter by severity
        limit: Maximum results

    Returns:
        List of error records
    """
    table_name = os.getenv("ERROR_LOG_TABLE", "error_logs")
    query = client.table(table_name).select("*")

    if domain:
        query = query.eq("domain", domain)

    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.gte("created_at", cutoff.isoformat())

    if component:
        query = query.eq("component", component)

    if severity:
        query = query.eq("severity", severity)

    query = query.order("created_at", desc=True).limit(limit)

    try:
        result = query.execute()
        return result.data
    except Exception as e:
        print(f"ERROR querying database: {e}")
        return []


def print_header(title: str, width: int = 80):
    """Print formatted section header."""
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def print_summary(errors: List[Dict[str, Any]]):
    """Print high-level error summary."""
    print_header("📊 ERROR SUMMARY")

    if not errors:
        print("✅ No errors found!")
        return

    total = len(errors)
    print(f"Total Errors: {total}")

    # By severity
    by_severity = Counter(e["severity"] for e in errors)
    print("\nBy Severity:")
    for severity in ["critical", "error", "warning", "info", "debug"]:
        count = by_severity.get(severity, 0)
        if count > 0:
            pct = (count / total) * 100
            print(f"  {severity.upper():<10} {count:>5} ({pct:>5.1f}%)")

    # By component
    by_component = Counter(e["component"] for e in errors)
    print("\nBy Component:")
    for comp, count in by_component.most_common():
        pct = (count / total) * 100
        print(f"  {comp:<10} {count:>5} ({pct:>5.1f}%)")

    # By error type
    by_type = Counter(e["error_type"] for e in errors)
    print("\nTop Error Types:")
    for error_type, count in by_type.most_common(10):
        pct = (count / total) * 100
        print(f"  {error_type:<25} {count:>5} ({pct:>5.1f}%)")

    # Time range
    if errors:
        first = datetime.fromisoformat(errors[-1]["created_at"].replace("Z", "+00:00"))
        last = datetime.fromisoformat(errors[0]["created_at"].replace("Z", "+00:00"))
        print(f"\nTime Range:")
        print(f"  First: {first.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Last:  {last.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Span:  {(last - first).total_seconds() / 3600:.1f} hours")


def print_by_domain(errors: List[Dict[str, Any]]):
    """Print errors grouped by domain."""
    print_header("🏢 ERRORS BY COMPANY/DOMAIN")

    if not errors:
        return

    # Group by domain
    by_domain = defaultdict(lambda: {"total": 0, "by_type": Counter(), "by_component": Counter(), "latest": None})

    for error in errors:
        domain = error["domain"]
        by_domain[domain]["total"] += 1
        by_domain[domain]["by_type"][error["error_type"]] += 1
        by_domain[domain]["by_component"][error["component"]] += 1
        if not by_domain[domain]["latest"]:
            by_domain[domain]["latest"] = error["created_at"]

    # Sort by error count
    sorted_domains = sorted(by_domain.items(), key=lambda x: x[1]["total"], reverse=True)

    print(f"\n{'Domain':<40} {'Errors':<8} {'Top Issue':<30}")
    print("-" * 80)

    for domain, stats in sorted_domains[:30]:  # Top 30
        top_type = stats["by_type"].most_common(1)[0][0] if stats["by_type"] else "unknown"
        print(f"{domain:<40} {stats['total']:<8} {top_type:<30}")


def print_by_stage(errors: List[Dict[str, Any]]):
    """Print errors grouped by pipeline stage."""
    print_header("🔄 ERRORS BY PIPELINE STAGE")

    if not errors:
        return

    # Group by component -> stage
    by_stage = defaultdict(lambda: {"count": 0, "domains": set()})

    for error in errors:
        key = f"{error['component']}:{error['stage']}"
        by_stage[key]["count"] += 1
        by_stage[key]["domains"].add(error["domain"])

    # Sort by count
    sorted_stages = sorted(by_stage.items(), key=lambda x: x[1]["count"], reverse=True)

    print(f"\n{'Stage':<50} {'Errors':<8} {'Domains':<8}")
    print("-" * 80)

    for stage, stats in sorted_stages[:20]:  # Top 20
        print(f"{stage:<50} {stats['count']:<8} {len(stats['domains']):<8}")


def print_critical_errors(errors: List[Dict[str, Any]]):
    """Print critical and error severity issues."""
    print_header("🚨 CRITICAL & ERROR SEVERITY ISSUES")

    critical = [e for e in errors if e["severity"] in ("critical", "error")]

    if not critical:
        print("✅ No critical errors!")
        return

    print(f"\nShowing {len(critical)} critical/error issues (most recent first):\n")

    for error in critical[:20]:  # Show top 20
        timestamp = datetime.fromisoformat(error["created_at"].replace("Z", "+00:00"))
        print(f"[{error['severity'].upper()}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Domain:    {error['domain']}")
        print(f"  Component: {error['component']} → {error['stage']}")
        print(f"  Type:      {error['error_type']}")
        print(f"  Message:   {error['message'][:100]}")
        if error.get('url'):
            print(f"  URL:       {error['url']}")
        print()


def print_domain_detail(errors: List[Dict[str, Any]], domain: str):
    """Print detailed error report for a specific domain."""
    print_header(f"🔍 DETAILED REPORT: {domain}")

    domain_errors = [e for e in errors if e["domain"] == domain]

    if not domain_errors:
        print(f"No errors found for domain: {domain}")
        return

    print(f"\nTotal Errors: {len(domain_errors)}")

    # Timeline
    print("\n📅 Error Timeline (last 10):")
    for error in domain_errors[:10]:
        timestamp = datetime.fromisoformat(error["created_at"].replace("Z", "+00:00"))
        print(f"  {timestamp.strftime('%Y-%m-%d %H:%M:%S')} [{error['severity']:<8}] "
              f"{error['component']}:{error['stage']:<20} → {error['error_type']}")

    # By component
    by_component = Counter(e["component"] for e in domain_errors)
    print("\n🔧 By Component:")
    for comp, count in by_component.most_common():
        print(f"  {comp:<12} {count} errors")

    # By stage
    by_stage = Counter(f"{e['component']}:{e['stage']}" for e in domain_errors)
    print("\n📍 By Stage:")
    for stage, count in by_stage.most_common(10):
        print(f"  {stage:<40} {count} errors")

    # By error type
    by_type = Counter(e["error_type"] for e in domain_errors)
    print("\n⚠️  By Error Type:")
    for error_type, count in by_type.most_common():
        print(f"  {error_type:<30} {count} errors")

    # Recent error details
    print("\n🔎 Most Recent Error Details:")
    latest = domain_errors[0]
    print(f"  Time:       {latest['created_at']}")
    print(f"  Component:  {latest['component']}")
    print(f"  Stage:      {latest['stage']}")
    print(f"  Type:       {latest['error_type']}")
    print(f"  Severity:   {latest['severity']}")
    print(f"  Message:    {latest['message']}")
    if latest.get('url'):
        print(f"  URL:        {latest['url']}")
    if latest.get('exception_type'):
        print(f"  Exception:  {latest['exception_type']}")
    if latest.get('metadata'):
        print(f"  Metadata:   {latest['metadata']}")


def export_csv(errors: List[Dict[str, Any]], output_file: str):
    """Export errors to CSV file."""
    import csv

    if not errors:
        print("No errors to export")
        return

    fields = ["created_at", "domain", "component", "stage", "error_type", "severity",
              "message", "url", "exception_type"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(errors)

    print(f"✅ Exported {len(errors)} errors to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Freezeus Error Dashboard - Analyze pipeline errors from Supabase"
    )
    parser.add_argument("--domain", help="Filter by specific domain")
    parser.add_argument("--hours", type=int, help="Only show errors from last N hours")
    parser.add_argument("--component", choices=["crawler", "llm", "db"], help="Filter by component")
    parser.add_argument("--severity", choices=["critical", "error", "warning", "info", "debug"],
                       help="Filter by severity")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum errors to fetch (default: 1000)")
    parser.add_argument("--export", choices=["csv"], help="Export to file format")
    parser.add_argument("--detail", help="Show detailed report for specific domain")

    args = parser.parse_args()

    # Initialize client
    print("Connecting to Supabase...")
    client = get_supabase_client()

    # Query errors
    print(f"Querying errors (limit={args.limit})...")
    errors = query_errors(
        client,
        domain=args.domain,
        hours=args.hours,
        component=args.component,
        severity=args.severity,
        limit=args.limit
    )

    if not errors:
        print("\n✅ No errors found matching your filters!")
        return

    print(f"Found {len(errors)} errors\n")

    # Export if requested
    if args.export == "csv":
        filename = f"errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_csv(errors, filename)
        return

    # Show detail view if requested
    if args.detail:
        print_domain_detail(errors, args.detail)
        return

    # Show full dashboard
    print_summary(errors)
    print_by_domain(errors)
    print_by_stage(errors)
    print_critical_errors(errors)

    # Helpful tips
    print_header("💡 TIPS")
    print("\nQuery specific domain:")
    print("  python monitoring/error_dashboard.py --detail apple.com")
    print("\nShow only recent errors:")
    print("  python monitoring/error_dashboard.py --hours 24")
    print("\nExport to CSV:")
    print("  python monitoring/error_dashboard.py --export csv")
    print("\nFilter by component:")
    print("  python monitoring/error_dashboard.py --component crawler")
    print()


if __name__ == "__main__":
    main()
