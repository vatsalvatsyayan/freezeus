# src/llm/llm_helper.py
import os, json, time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from urllib.parse import urljoin  # Still needed for other URL operations

# Import utilities from refactored modules
from src.utils.url_utils import normalize_job_url
from src.core.logging import get_logger
from src.llm.parsers import (
    parse_json_robust,
    normalize_and_dedupe,
)

# Always load project .env locally (no system env requirement)
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# Initialize logger
logger = get_logger(__name__)

try:
    import google.generativeai as genai
except ImportError as e:
    raise RuntimeError("google-generativeai not installed. pip install google-generativeai>=0.8.0") from e

# ---------------- Config (env-driven) ----------------
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY missing. Put it in configs/.env (e.g., GEMINI_API_KEY=... )")

genai.configure(api_key=API_KEY)

MAX_HTML_CHARS   = int(os.getenv("LLM_MAX_HTML_CHARS", "250000"))  # trim very large pages
MAX_RETRIES      = int(os.getenv("LLM_MAX_RETRIES", "2"))          # extra retries beyond first
RETRY_BASE_SLEEP = float(os.getenv("LLM_RETRY_BASE_SLEEP", "1.6")) # seconds, exponential backoff
VERBOSE          = os.getenv("LLM_VERBOSE", "1") not in {"0", "false", "False"}
OVERWRITE        = os.getenv("LLM_OVERWRITE", "0") in {"1", "true", "True"}

# ---------------- Supabase wiring ----------------
_SUPABASE_IMPORTED_OK = False
_SUPABASE_IMPORT_ERR: Optional[Exception] = None

try:
    # this is your file: src/db/supabase_client.py
    from src.db.supabase_client import upsert_jobs_for_page, is_supabase_enabled
    _SUPABASE_IMPORTED_OK = True
except Exception as e:
    _SUPABASE_IMPORTED_OK = False
    _SUPABASE_IMPORT_ERR = e

# ---------------- Helper Functions ----------------
def load_extraction_prompt() -> str:
    """Load extraction prompt from configs file with fallback to default."""
    prompt_path = Path("configs/llm_extraction_prompt.txt")
    if prompt_path.exists():
        try:
            return prompt_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"[LLM] Warning: Failed to load prompt file: {e}. Using default.")
    return PROMPT_PREFIX  # Fallback to hardcoded

# NOTE: normalize_job_url is now imported from src.utils.url_utils
# The function has been moved to a shared utility module

# ---------------- Prompt ----------------
PROMPT_PREFIX = """You are an expert at parsing career and job listing websites.
Your input is a reduced HTML fragment that contains the job listings section of a single page.

Goal:
- Extract every UNIQUE job posting from the HTML.
- Preserve the same order in which jobs appear on the page.

Rules:
- Include only real jobs; ignore UI like “Load more”, “Apply”, “Next page”, filters, or search controls.
- Deduplicate: sites sometimes render the same list twice (e.g., SSR + JS re-render, or desktop + mobile).
  Consider jobs duplicates if they share the same job_url, requisition_id, or (title + location) pair.
  Keep only one canonical copy: the version with the most fields filled (date, location, category, etc.).
- Normalize whitespace and strip HTML tags from text fields.
- Do not invent information that clearly contradicts the page, but you MAY infer reasonable details
  (like seniority level or employment type) from the job title and description when they are implied.

For each job, extract these fields (omit if not present), EXCEPT for the seniority fields which must always be included:
- title
- job_url (absolute if available; otherwise the href as-is)
- company (employer name, e.g., Meta, Airbnb; infer from page branding if needed)
- location (string or list)
- team_or_category
- employment_type (e.g., Full-time, Part-time, Internship, Contract). Infer from text when strongly implied.
- date_posted
- requisition_id
- office_or_remote (Remote / Hybrid / Onsite)
- seniority_level: short human-readable label, e.g. "Intern", "New Grad", "Junior", "Mid-level",
  "Senior", "Staff", "Principal", "Director", "VP", "C-level", or "Unknown".
- seniority_bucket: ONE of the following EXACT strings:
    - "intern"       → internships, co-op, apprenticeship
    - "entry"        → new grad, early career, university grad, level 1–2, "junior"
    - "mid"          → mid-level IC roles (e.g., Software Engineer 2–3)
    - "senior"       → senior/staff/principal IC roles (e.g., "Senior", "Staff", "Principal")
    - "director_vp"  → director, head of X, VP
    - "executive"    → CxO, president, founder, very top leadership
    - "unknown"      → when the seniority truly cannot be inferred from the page
- extra (a flat key-value map for any other clearly relevant fields, such as:
  - "job_id"
  - "job_family"
  - "job_function"
  - "job_description" (short text or snippet)
  - "apply_url"
  - or anything else useful that appears in the HTML)

Important:
- Always include BOTH "seniority_level" and "seniority_bucket" for every job:
  - If you are unsure, set seniority_level to "Unknown" and seniority_bucket to "unknown".
- Prefer using what the page says explicitly. If the title or description clearly implies the level
  (for example "University Grad", "New Grad", "Staff Software Engineer", "Director of Engineering"),
  infer the appropriate seniority_level and seniority_bucket.

Also include top-level metadata:
- source_url — the source page URL if provided
- page_title — the page title or heading if available

Output STRICTLY this JSON (no commentary, no markdown fences):

{
  "source_url": "...",
  "page_title": "...",
  "jobs": [
    {
      "title": "...",
      "job_url": "...",
      "company": "...",
      "location": "...",
      "team_or_category": "...",
      "employment_type": "...",
      "date_posted": "...",
      "requisition_id": "...",
      "office_or_remote": "...",
      "seniority_level": "...",
      "seniority_bucket": "...",
      "extra": { "...": "..." }
    }
  ]
}

If a field (other than seniority_level and seniority_bucket) is unknown, omit it entirely
(do not output null or empty strings). For seniority_level and seniority_bucket, always include them;
use "Unknown" / "unknown" when they cannot be inferred."""

# ---------------- Small print helper ----------------
def _log(msg: str):
    if VERBOSE:
        print(f"[LLM] {msg}", flush=True)

# ---------------- Helpers ----------------
def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _truncate_html(html_text: str) -> Tuple[str, bool]:
    if MAX_HTML_CHARS and len(html_text) > MAX_HTML_CHARS:
        return html_text[:MAX_HTML_CHARS], True
    return html_text, False

# NOTE: Parser functions (_strip_ws, _richness_score, _canon_loc, _sig, _omit_empty,
# _normalize_seniority_fields, _normalize_and_dedupe, sanitize_json_text, parse_json_robust)
# have been moved to src.llm.parsers and are imported at the top of this file.

# ---------------- Robust LLM call with retries + fixer ----------------
def _gen_with_retries(model_name: str, prompt: str, gen_config: Dict[str, Any]):
    model = genai.GenerativeModel(model_name)
    tries = MAX_RETRIES + 1
    last_err = None
    for i in range(tries):
        try:
            _log(f"call attempt {i+1}: gemini → JSON")
            return model.generate_content(prompt, generation_config=gen_config)
        except Exception as e:
            last_err = e
            sleep = RETRY_BASE_SLEEP * (2 ** i)  # exponential backoff
            _log(f"call failed (attempt {i+1}/{tries}): {e}. backoff {sleep:.1f}s")
            time.sleep(sleep)
    raise last_err

def _fix_to_json_via_model(model_name: str, bad_text: str) -> Optional[Dict[str, Any]]:
    """Second-chance: ask the model to convert previous output into valid JSON per schema."""
    try:
        model = genai.GenerativeModel(model_name)
        fixer_prompt = (
            "You will be given text that should be JSON but may be malformed.\n"
            "Return ONLY valid JSON that conforms to this structure (omit unknown fields except seniority fields):\n"
            '{ "source_url": "...", "page_title": "...", "jobs": [ { "title": "...", "job_url": "...", '
            '"company": "...", "location": "...", "team_or_category": "...", "employment_type": "...", '
            '"date_posted": "...", "requisition_id": "...", "office_or_remote": "...", '
            '"seniority_level": "...", "seniority_bucket": "...", "extra": { } } ] }\n\n'
            "For seniority_bucket use exactly one of: intern, entry, mid, senior, director_vp, executive, unknown.\n"
            "Text:\n" + bad_text
        )
        resp = model.generate_content(
            fixer_prompt,
            generation_config={
                "temperature": 0.0,
                "candidate_count": 1,
                "response_mime_type": "application/json",
            },
        )
        txt = (getattr(resp, "text", None) or "").strip()
        return parse_json_robust(txt)
    except Exception as e:
        _log(f"fixer failed: {e}")
        return None

def _llm_call(model_name: str, html_text: str, source_url: str, page_title: str) -> dict:
    html_text, was_trunc = _truncate_html(html_text)
    if was_trunc:
        _log(f"html truncated to {len(html_text):,} chars (budget={MAX_HTML_CHARS:,}).")

    # Load prompt from file (with fallback to hardcoded)
    prompt_text = load_extraction_prompt()

    # Nudge model to stay on one line (reduces quote/newline glitches)
    prompt = (
        f"{prompt_text}\n\n"
        "Return compact JSON on a single line if possible.\n\n"
        "=== HTML START ===\n" + html_text + "\n=== HTML END ===\n"
    )

    gen_config: Dict[str, Any] = {
        "temperature": 0.0,
        "candidate_count": 1,
        "response_mime_type": "application/json",
    }

    resp = _gen_with_retries(model_name, prompt, gen_config)
    text = (getattr(resp, "text", None) or "").strip()

    # Parse with repair pipeline
    try:
        data = parse_json_robust(text)
    except Exception:
        _log("primary parse failed; attempting LLM fixer")
        fixed = _fix_to_json_via_model(model_name, text)
        if fixed is None:
            # Last resort: return minimal valid envelope with error
            _log("fixer failed; returning empty jobs JSON with error note")
            return {
                "source_url": source_url or "",
                "page_title": page_title or "",
                "jobs": [],
                "error": "LLM returned non-JSON output; sanitizer+fixer failed"
            }
        data = fixed

    # Seed top-level fields (LLM may omit)
    data.setdefault("source_url", source_url or "")
    data.setdefault("page_title", page_title or "")
    data.setdefault("jobs", [])
    return data

# ---------------- Public APIs (with progress prints) ----------------
def extract_one_focus_html(domain_dir: Path, focus_html_path: Path, source_url: Optional[str] = "", page_title: Optional[str] = "") -> Path:
    """
    Reads a single reduced_focus HTML file and writes jobs JSON to out/<domain>/llm/<base>.jobs.json
    Returns the path to the written JSON. Never raises; always writes a JSON file.
    Also (if Supabase is enabled) upserts all jobs into the DB.
    """
    domain_dir = Path(domain_dir)
    llm_dir = domain_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    base = focus_html_path.stem  # e.g., careers__abcd1234.p001
    out_json = llm_dir / f"{base}.jobs.json"

    if out_json.exists() and not OVERWRITE:
        _log(f"skip (exists): {out_json.name}  (set LLM_OVERWRITE=1 to recompute)")
        return out_json

    _log(f"read: {focus_html_path.name}")
    html_text = _read_text(focus_html_path)

    _log("call: gemini → parse → json")
    try:
        raw = _llm_call(DEFAULT_MODEL, html_text, source_url or "", page_title or "")
    except Exception as e:
        # Extremely defensive: should not happen because _llm_call returns error JSON on failure.
        _log(f"fatal call error: {e}; writing empty envelope")
        raw = {"source_url": source_url or "", "page_title": page_title or "", "jobs": [], "error": str(e)}

    _log("post: normalize + dedupe")
    try:
        cleaned, stats = normalize_and_dedupe(raw)
        _log(f"dedupe stats: in={stats['input_jobs']} → out={stats['deduped_out']} (removed {stats['duplicates_removed']})")
    except Exception as e:
        _log(f"normalize error: {e}; writing unnormalized result")
        cleaned = {
            "source_url": raw.get("source_url", source_url or ""),
            "page_title": raw.get("page_title", page_title or ""),
            "jobs": raw.get("jobs", []),
            "warning": f"normalize_error: {e}"
        }

    # URL normalization post-processing
    domain_name = str(domain_dir.name)
    for job in cleaned.get("jobs", []):
        if job.get("job_url"):
            original = job["job_url"]
            normalized = normalize_job_url(original, source_url, domain_name)
            job["job_url"] = normalized

            # Insert with warning per user preference
            if not normalized or not normalized.startswith('http'):
                _log(f"⚠️  WARNING: Incomplete URL will be inserted: {original} -> {normalized}")

    out_json.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"wrote: {out_json.name}")

    # ---------- Supabase integration ----------
    domain_name = domain_dir.name
    if _SUPABASE_IMPORTED_OK:
        try:
            if is_supabase_enabled():
                _log(f"Supabase: upserting {len(cleaned.get('jobs', []))} jobs for {domain_name}")
                upsert_jobs_for_page(cleaned, domain=domain_name)
            else:
                _log("Supabase: disabled or client init failed (see [SUPABASE] logs).")
        except Exception as e:
            _log(f"Supabase upsert error for {domain_name}: {e}")
    else:
        _log(f"Supabase disabled: import error: {_SUPABASE_IMPORT_ERR}")

    return out_json

def extract_all_focus_htmls(domain_dir: Path) -> List[Path]:
    """
    Walks out/<domain>/reduced_focus/*.html and extracts jobs for each file.
    Prints progress for visibility. Returns list of written JSON paths.
    Never raises; continues on errors.
    """
    domain_dir = Path(domain_dir)
    focus_dir = domain_dir / "reduced_focus"
    meta_dir  = domain_dir / "meta"
    llm_dir   = domain_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    if not focus_dir.exists():
        _log(f"{domain_dir.name}: no reduced_focus/ found, nothing to do.")
        return written

    files = sorted(focus_dir.glob("*.html"))
    _log(f"{domain_dir.name}: found {len(files)} focus HTML files.")
    for idx, f in enumerate(files, 1):
        _log(f"[{idx}/{len(files)}] processing {f.name}")

        src_url = ""
        page_title = ""
        meta_path = meta_dir / f"{f.stem}.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                src_url = meta.get("url", "") or meta.get("source_url", "")
                page_title = meta.get("title") or (meta.get("reduce_meta", {}) or {}).get("title", "")
            except Exception as e:
                _log(f"meta read warn ({meta_path.name}): {e}")

        try:
            outp = extract_one_focus_html(domain_dir, f, src_url, page_title)
            written.append(outp)
        except Exception as e:
            _log(f"unhandled error for {f.name}: {e}. continuing…")

    _log(f"{domain_dir.name}: done. wrote {len(written)} JSON files.")
    return written