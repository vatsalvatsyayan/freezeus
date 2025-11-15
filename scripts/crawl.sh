#!/usr/bin/env bash
set -euo pipefail

# --- Config you might tweak ---
URLS_FILE="configs/urls.txt"   # one URL per line
PYTHON="${PYTHON:-python}"     # or ".venv/bin/python" if you prefer

# --- Sanity checks ---
if [ ! -f "$URLS_FILE" ]; then
  echo "ERROR: $URLS_FILE not found. Create it with one careers URL per line."
  exit 1
fi
if [ ! -f "configs/.env" ]; then
  echo "ERROR: configs/.env not found. Put your GEMINI_API_KEY (and other keys) there."
  exit 1
fi

# --- (first time only) ensure Playwright browsers are installed ---
$PYTHON - <<'PY'
import sys, subprocess
try:
    import playwright  # noqa
    # install browsers if missing (idempotent)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
except Exception as e:
    print("Playwright not installed? Run: pip install -r requirements.txt", e)
    sys.exit(1)
PY

# --- Run headed + with-LLM ---
echo "Running crawler in HEADED mode with LLM postpass…"
$PYTHON -m src.crawler.multi_capture \
  --urls "$URLS_FILE" \
  --headed \
  --with-llm

echo "Done. Check the 'out/<domain>/' folders for full/reduced HTML and 'llm/*.jobs.json'."