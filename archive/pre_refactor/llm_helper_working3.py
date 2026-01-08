# src/llm/llm_helper.py
import os, json, re, time, math
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from urllib.parse import urlparse
from datetime import datetime

# Always load project .env locally (no system env requirement)
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

try:
    import google.generativeai as genai
except ImportError as e:
    raise RuntimeError("google-generativeai not installed. pip install google-generativeai>=0.8.0") from e

# Optional lenient JSON parser (won't be required; used if present)
try:
    import json5  # pip install json5
except Exception:
    json5 = None

# Try Supabase client (optional – crawl must still work without it)
try:
    from db.supabase_client import get_supabase
except Exception:
    get_supabase = None  # type: ignore

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

# Supabase options
SUPABASE_ENABLED = os.getenv("SUPABASE_ENABLED", "1") not in {"0", "false", "False"}
SUPABASE_JOBS_TABLE = os.getenv("SUPABASE_JOBS_TABLE", "jobs")

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
- Do not invent information.

For each job, extract these fields (omit if not present):
- title
- job_url (absolute if available; otherwise the href as-is)
- location (string or list)
- team_or_category
- employment_type (e.g., Full-time, Part-time, Internship, Contract)
- date_posted
- requisition_id
- office_or_remote (Remote / Hybrid / Onsite)
- seniority_level (e.g., Early-career/Junior, Mid-level, Senior, Staff, Principal, Executive, Intern)
- job_description (short summary of the role based on the visible text near the job)

- extra (a flat key-value map for any other clearly relevant fields)

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
      "location": "...",
      "team_or_category": "...",
      "employment_type": "...",
      "date_posted": "...",
      "requisition_id": "...",
      "office_or_remote": "...",
      "seniority_level": "...",
      "job_description": "...",
      "extra": { "...": "..." }
    }
  ]
}

If a field is unknown, omit it entirely (do not output null or empty strings)."""

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

def _strip_ws(val: Any) -> Any:
    if isinstance(val, str):
        return re.sub(r"\s+", " ", val).strip()
    if isinstance(val, list):
        return [_strip_ws(v) for v in val if (isinstance(v, (str, int, float)) or v)]
    if isinstance(val, dict):
        return {k: _strip_ws(v) for k, v in val.items()}
    return val

def _richness_score(job: Dict[str, Any]) -> int:
    keys = [
        "title","job_url","location","team_or_category","employment_type",
        "date_posted","requisition_id","office_or_remote",
        "seniority_level","job_description",
    ]
    score = sum(1 for k in keys if k in job and job[k] not in (None, "", [], {}))
    if isinstance(job.get("extra"), dict) and job["extra"]:
        score += min(3, len(job["extra"]))
    return score

def _canon_loc(loc: Any) -> str:
    if isinstance(loc, list):
        return ", ".join([_strip_ws(x) for x in loc if isinstance(x, str) and _strip_ws(x)])
    if isinstance(loc, str):
        return _strip_ws(loc)
    return ""

def _sig(job: Dict[str, Any]) -> str:
    url = _strip_ws(job.get("job_url") or "").lower()
    rid = _strip_ws(job.get("requisition_id") or "").lower()
    ttl = _strip_ws(job.get("title") or "").lower()
    loc = _canon_loc(job.get("location"))
    loc = _strip_ws(loc).lower()
    if url:
        return f"url::{url}"
    if rid:
        return f"rid::{rid}"
    return f"tl::{ttl}@@{loc}"

def _omit_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.strip()
            if vv:
                out[k] = vv
        elif isinstance(v, list):
            vv = [x for x in v if x not in (None, "", [], {})]
            if vv:
                out[k] = vv
        elif isinstance(v, dict):
            vv = _omit_empty(v)
            if vv:
                out[k] = vv
        else:
            out[k] = v
    return out

def _normalize_and_dedupe(parsed: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    src_url = _strip_ws(parsed.get("source_url") or "")
    page_title = _strip_ws(parsed.get("page_title") or "")
    jobs_in = parsed.get("jobs") or []
    if not isinstance(jobs_in, list):
        jobs_in = []

    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    dupes = 0

    for raw in jobs_in:
        if not isinstance(raw, dict):
            continue
        job = _strip_ws(raw)
        job = _omit_empty(job)

        if "location" in job:
            loc = job["location"]
            job["location"] = _canon_loc(loc) if loc else None
            if not job["location"]:
                job.pop("location", None)

        sig = _sig(job) or f"idx::{len(order)}"

        if sig not in seen:
            seen[sig] = job
            order.append(sig)
        else:
            dupes += 1
            a = seen[sig]
            b = job
            seen[sig] = a if _richness_score(a) >= _richness_score(b) else b

    jobs_out = [seen[s] for s in order]
    stats = {"input_jobs": len(jobs_in), "deduped_out": len(jobs_out), "duplicates_removed": dupes}
    return {
        "source_url": src_url,
        "page_title": page_title,
        "jobs": jobs_out
    }, stats

# ---------------- JSON repair utilities ----------------
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_SMART_QUOTES = {
    "\u2018":"'", "\u2019":"'", "\u201C":'"', "\u201D":'"',
    "\u00AB":'"', "\u00BB":'"'
}
_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

def _defence_sanitize_json_text(text: str) -> str:
    """Best-effort cleanups for common JSON issues."""
    t = text.strip()
    # Strip code fences
    t = _FENCE_RE.sub("", t)
    # Replace smart quotes
    for k, v in _SMART_QUOTES.items():
        t = t.replace(k, v)
    # Remove control chars
    t = _CTRL_RE.sub("", t)
    # Remove trailing commas: ,] or ,}
    t = re.sub(r",(\s*[\]\}])", r"\1", t)
    return t.strip()

def _parse_any_json(text: str) -> Dict[str, Any]:
    """Try strict json, then lenient fixes, then json5, then brace slice."""
    # 1) strict
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) sanitize + strict
    t2 = _defence_sanitize_json_text(text)
    try:
        return json.loads(t2)
    except Exception:
        pass
    # 3) json5 if available
    if json5 is not None:
        try:
            return json5.loads(t2)
        except Exception:
            pass
    # 4) brace slice
    start = t2.find("{"); end = t2.rfind("}")
    if start >= 0 and end > start:
        sliced = t2[start:end+1]
        # try once more strict then json5
        try:
            return json.loads(sliced)
        except Exception:
            if json5 is not None:
                return json5.loads(sliced)
    # 5) give up
    raise ValueError("unparseable JSON")

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
            "Return ONLY valid JSON that conforms to this structure (omit unknown fields):\n"
            '{ "source_url": "...", "page_title": "...", "jobs": [ { "title": "...", "job_url": "...", '
            '"location": "...", "team_or_category": "...", "employment_type": "...", "date_posted": "...", '
            '"requisition_id": "...", "office_or_remote": "...", "seniority_level": "...", "job_description": "...", "extra": { } } ] }\n\n'
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
        return _parse_any_json(txt)
    except Exception as e:
        _log(f"fixer failed: {e}")
        return None

def _llm_call(model_name: str, html_text: str, source_url: str, page_title: str) -> dict:
    html_text, was_trunc = _truncate_html(html_text)
    if was_trunc:
        _log(f"html truncated to {len(html_text):,} chars (budget={MAX_HTML_CHARS:,}).")

    # Nudge model to stay on one line (reduces quote/newline glitches)
    prompt = (
        f"{PROMPT_PREFIX}\n\n"
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
        data = _parse_any_json(text)
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

# ---------------- Supabase helpers ----------------
def _domain_from_url(u: str) -> str:
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return ""

def _supabase_available() -> bool:
    if not SUPABASE_ENABLED:
        return False
    if get_supabase is None:
        _log("Supabase disabled: get_supabase() not importable")
        return False
    try:
        _ = get_supabase()
        return True
    except Exception as e:
        _log(f"Supabase disabled: get_supabase() failed: {e}")
        return False

def _upsert_jobs_to_supabase(cleaned: Dict[str, Any]) -> None:
    """
    Push jobs into Supabase `jobs` table via upsert(job_url).
    Never raises; logs and returns on error.
    """
    if not _supabase_available():
        return

    client = get_supabase()  # type: ignore
    jobs = cleaned.get("jobs") or []
    if not isinstance(jobs, list) or not jobs:
        _log("Supabase: no jobs to upsert; skipping")
        return

    source_url = cleaned.get("source_url") or ""
    page_title = cleaned.get("page_title") or ""
    domain = _domain_from_url(source_url)
    now_iso = datetime.utcnow().isoformat() + "Z"

    rows: List[Dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_url = job.get("job_url")
        if not job_url:
            # Without job_url we cannot de-duplicate; skip to keep DB clean.
            continue

        row: Dict[str, Any] = {
            "job_url": job_url,
            "source_url": source_url,
            "page_title": page_title,
            "title": job.get("title"),
            "location": job.get("location"),
            "team_or_category": job.get("team_or_category"),
            "employment_type": job.get("employment_type"),
            "date_posted": job.get("date_posted"),
            "requisition_id": job.get("requisition_id"),
            "office_or_remote": job.get("office_or_remote"),
            "seniority_level": job.get("seniority_level"),
            "job_description": job.get("job_description"),
            "extra": job.get("extra") or None,
            # Optional metadata
            "source_domain": domain or None,
            "last_seen_at": now_iso,
        }
        rows.append(row)

    if not rows:
        _log("Supabase: no rows with job_url; nothing to upsert")
        return

    try:
        # on_conflict=job_url ensures we update existing rows instead of inserting duplicates.
        client.table(SUPABASE_JOBS_TABLE).upsert(rows, on_conflict="job_url").execute()
        _log(f"Supabase: upserted {len(rows)} rows into '{SUPABASE_JOBS_TABLE}'")
    except Exception as e:
        _log(f"Supabase upsert failed: {e}")

# ---------------- Public APIs (with progress prints) ----------------
def extract_one_focus_html(domain_dir: Path, focus_html_path: Path, source_url: Optional[str] = "", page_title: Optional[str] = "") -> Path:
    """
    Reads a single reduced_focus HTML file and writes jobs JSON to out/<domain>/llm/<base>.jobs.json
    Returns the path to the written JSON. Never raises; always writes a JSON file.
    Also attempts to upsert jobs into Supabase (if configured).
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
        cleaned, stats = _normalize_and_dedupe(raw)
        _log(f"dedupe stats: in={stats['input_jobs']} → out={stats['deduped_out']} (removed {stats['duplicates_removed']})")
    except Exception as e:
        _log(f"normalize error: {e}; writing unnormalized result")
        cleaned = {
            "source_url": raw.get("source_url", source_url or ""),
            "page_title": raw.get("page_title", page_title or ""),
            "jobs": raw.get("jobs", []),
            "warning": f"normalize_error: {e}"
        }

    # Write to disk
    out_json.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"wrote: {out_json.name}")

    # Push into Supabase (best-effort, non-fatal)
    _upsert_jobs_to_supabase(cleaned)

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