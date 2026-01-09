#!/usr/bin/env bash
set -euo pipefail

# ================================================================
# Freezeus Job Crawler - Local Development Script
# ================================================================
# Runs the crawler in headed mode with LLM extraction enabled.
# Use this for local testing and debugging.
#
# For headless/production runs, use:
#   python -m src.crawler.multi_capture --urls configs/urls.txt --headless --with-llm
# ================================================================

echo "================================================"
echo "Freezeus Job Crawler - Local Development Mode"
echo "================================================"
echo ""

# --- Config ---
URLS_FILE="${URLS_FILE:-configs/urls.txt}"
PYTHON="${PYTHON:-python}"
ENV_FILE="configs/.env"

# --- Sanity checks ---
echo "[1/5] Checking configuration files..."

if [ ! -f "$URLS_FILE" ]; then
  echo "❌ ERROR: $URLS_FILE not found"
  echo "   Create it with one careers URL per line, e.g.:"
  echo "   https://example.com/careers"
  echo "   https://another.com/jobs"
  exit 1
fi

URL_COUNT=$(grep -v '^#' "$URLS_FILE" | grep -v '^[[:space:]]*$' | wc -l | tr -d ' ')
echo "   ✓ Found $URL_COUNT URL(s) in $URLS_FILE"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ ERROR: $ENV_FILE not found"
  echo "   Copy configs/.env.example to configs/.env and fill in your API keys"
  exit 1
fi

# Check for required API key
if ! grep -q "GEMINI_API_KEY=." "$ENV_FILE"; then
  echo "❌ ERROR: GEMINI_API_KEY not set in $ENV_FILE"
  echo "   Get your API key from: https://makersuite.google.com/app/apikey"
  exit 1
fi

echo "   ✓ Configuration file found: $ENV_FILE"

# --- Check Python environment ---
echo ""
echo "[2/5] Checking Python environment..."

if ! $PYTHON -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>/dev/null; then
  echo "⚠️  WARNING: Python 3.13+ recommended, found: $($PYTHON --version)"
fi

# --- Check dependencies ---
echo ""
echo "[3/5] Checking Python dependencies..."

if ! $PYTHON -c "import playwright" 2>/dev/null; then
  echo "❌ ERROR: Playwright not installed"
  echo "   Install dependencies with: pip install -r requirements.txt"
  exit 1
fi

if ! $PYTHON -c "import google.generativeai" 2>/dev/null; then
  echo "❌ ERROR: google-generativeai not installed"
  echo "   Install dependencies with: pip install -r requirements.txt"
  exit 1
fi

echo "   ✓ All Python dependencies installed"

# --- Ensure Playwright browsers are installed ---
echo ""
echo "[4/5] Checking Playwright browsers..."

if ! $PYTHON -c "from pathlib import Path; import sys; sys.exit(0 if (Path.home() / '.cache' / 'ms-playwright').exists() else 1)" 2>/dev/null; then
  echo "   Installing Playwright Chromium browser (one-time setup)..."
  $PYTHON -m playwright install chromium
else
  echo "   ✓ Playwright browsers installed"
fi

# --- Run crawler ---
echo ""
echo "[5/5] Starting crawler..."
echo "   Mode: HEADED (browser will be visible)"
echo "   LLM: ENABLED (will extract jobs after crawling)"
echo "   URLs: $URL_COUNT from $URLS_FILE"
echo ""
echo "Press Ctrl+C to stop the crawler at any time"
echo "================================================"
echo ""

$PYTHON -m src.crawler.multi_capture \
  --urls "$URLS_FILE" \
  --headed \
  --with-llm

# --- Success ---
echo ""
echo "================================================"
echo "✅ Crawl completed successfully!"
echo "================================================"
echo ""
echo "Results saved to:"
echo "  • Full HTML:        out/<domain>/full/*.html"
echo "  • Reduced HTML:     out/<domain>/reduced_focus/*.html"
echo "  • Extracted Jobs:   out/<domain>/llm/*.jobs.json"
echo "  • Manifests:        out/<domain>/*.manifest.json"
echo ""
echo "Next steps:"
echo "  • Check out/ directory for crawl results"
echo "  • Check logs/ for detailed logs"
echo "  • Check Supabase for database records (if enabled)"
echo ""