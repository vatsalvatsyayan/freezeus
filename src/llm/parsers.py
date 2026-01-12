"""
JSON parsing and data cleaning utilities for LLM job extraction.

This module provides robust JSON parsing with fallback strategies,
data normalization, and deduplication for job listings.
"""

import re
import json
from typing import Dict, Any, List, Tuple, Optional
from src.core.logging import get_logger

logger = get_logger(__name__)

# Optional lenient JSON parser
try:
    import json5  # pip install json5
except ImportError:
    json5 = None

# ---------------- JSON Repair Utilities ----------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_SMART_QUOTES = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201C": '"',
    "\u201D": '"',
    "\u00AB": '"',
    "\u00BB": '"'
}
_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def sanitize_json_text(text: str) -> str:
    """
    Best-effort cleanups for common JSON issues.

    Removes markdown code fences, replaces smart quotes,
    removes control characters, and fixes trailing commas.

    Args:
        text: Raw JSON text that may have formatting issues

    Returns:
        Cleaned JSON text string

    Example:
        >>> sanitize_json_text('```json\\n{"key": "value",}\\n```')
        '{"key": "value"}'
    """
    t = text.strip()

    # Strip code fences (```json ... ```)
    t = _FENCE_RE.sub("", t)

    # Replace smart quotes with standard ASCII quotes
    for k, v in _SMART_QUOTES.items():
        t = t.replace(k, v)

    # Remove control characters
    t = _CTRL_RE.sub("", t)

    # Remove trailing commas before ] or }
    t = re.sub(r",(\s*[\]\}])", r"\1", t)

    return t.strip()


def parse_json_robust(text: str) -> Dict[str, Any]:
    """
    Parse JSON text with multiple fallback strategies.

    Tries in order:
    1. Standard json.loads()
    2. Sanitize + json.loads()
    3. json5.loads() if available
    4. Brace-slice + retry parse

    Args:
        text: JSON text to parse

    Returns:
        Parsed JSON as dictionary

    Raises:
        ValueError: If all parsing strategies fail

    Example:
        >>> parse_json_robust('{"jobs": []}')
        {'jobs': []}
    """
    # Strategy 1: Try strict JSON first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: Sanitize + strict JSON
    t2 = sanitize_json_text(text)
    try:
        return json.loads(t2)
    except Exception:
        pass

    # Strategy 3: json5 if available (handles trailing commas, comments, etc.)
    if json5 is not None:
        try:
            return json5.loads(t2)
        except Exception:
            pass

    # Strategy 4: Extract content between first { and last }
    start = t2.find("{")
    end = t2.rfind("}")
    if start >= 0 and end > start:
        sliced = t2[start:end+1]

        # Try strict JSON on slice
        try:
            return json.loads(sliced)
        except Exception:
            # Try json5 on slice if available
            if json5 is not None:
                try:
                    return json5.loads(sliced)
                except Exception:
                    pass

    # Strategy 5: Give up
    logger.error(f"Failed to parse JSON after all strategies. Text preview: {text[:200]}...")
    raise ValueError("Unparseable JSON after all fallback strategies")


# ---------------- Data Normalization Helpers ----------------

def _strip_ws(val: Any) -> Any:
    """
    Recursively strip and normalize whitespace in strings, lists, and dicts.

    Args:
        val: Value to normalize (can be str, list, dict, or other)

    Returns:
        Value with normalized whitespace
    """
    if isinstance(val, str):
        # Replace all whitespace sequences with single space
        return re.sub(r"\s+", " ", val).strip()
    if isinstance(val, list):
        return [_strip_ws(v) for v in val if (isinstance(v, (str, int, float)) or v)]
    if isinstance(val, dict):
        return {k: _strip_ws(v) for k, v in val.items()}
    return val


def _richness_score(job: Dict[str, Any]) -> int:
    """
    Calculate how "rich" a job dict is (how many fields are filled).

    Used for deduplication to keep the version with most information.

    Args:
        job: Job dictionary

    Returns:
        Integer score (higher = more fields filled)
    """
    keys = [
        "title",
        "job_url",
        "company",
        "location",
        "team_or_category",
        "employment_type",
        "date_posted",
        "requisition_id",
        "office_or_remote",
        "seniority_level",
        "seniority_bucket",
    ]

    # Count non-empty standard fields
    score = sum(1 for k in keys if k in job and job[k] not in (None, "", [], {}))

    # Add bonus points for extra fields (capped at 3)
    if isinstance(job.get("extra"), dict) and job["extra"]:
        score += min(3, len(job["extra"]))

    return score


def _canon_loc(loc: Any) -> str:
    """
    Canonicalize location field to a single string.

    Args:
        loc: Location as string or list of strings

    Returns:
        Normalized location string
    """
    if isinstance(loc, list):
        # Join list items with commas
        return ", ".join([_strip_ws(x) for x in loc if isinstance(x, str) and _strip_ws(x)])
    if isinstance(loc, str):
        return _strip_ws(loc)
    return ""


def _sig(job: Dict[str, Any]) -> str:
    """
    Generate signature for job deduplication.

    Uses job_url if present, else requisition_id, else title+location.

    Args:
        job: Job dictionary

    Returns:
        Unique signature string
    """
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
    """
    Remove keys with None or empty values from dictionary.

    Recursively processes nested dicts. Keeps non-empty strings
    like "unknown" so those survive.

    Args:
        d: Dictionary to clean

    Returns:
        Dictionary with empty values removed
    """
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


def normalize_seniority_fields(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize seniority fields to canonical values.

    Maps various seniority bucket values to standard set:
    - intern, entry, mid, senior, director_vp, executive, unknown

    Args:
        job: Job dictionary with seniority fields

    Returns:
        Job dictionary with normalized seniority fields

    Example:
        >>> job = {"seniority_bucket": "jr", "seniority_level": ""}
        >>> normalize_seniority_fields(job)
        {'seniority_bucket': 'entry', 'seniority_level': 'Unknown'}
    """
    # Normalize bucket to canonical values
    raw_bucket = (job.get("seniority_bucket") or "").strip().lower()

    bucket_map = {
        "intern": "intern",
        "internship": "intern",
        "co-op": "intern",
        "coop": "intern",
        "entry": "entry",
        "new grad": "entry",
        "new_grad": "entry",
        "junior": "entry",
        "jr": "entry",
        "mid": "mid",
        "mid-level": "mid",
        "mid level": "mid",
        "midlevel": "mid",
        "senior": "senior",
        "sr": "senior",
        "staff": "senior",
        "principal": "senior",
        "director": "director_vp",
        "vp": "director_vp",
        "vice president": "director_vp",
        "head": "director_vp",
        "executive": "executive",
        "cxo": "executive",
        "c-level": "executive",
        "c level": "executive",
        "ceo": "executive",
        "cto": "executive",
        "cfo": "executive",
    }

    normalized_bucket = None
    if raw_bucket:
        # Try to map to canonical value
        normalized_bucket = bucket_map.get(raw_bucket)

        # If not in map, check if already canonical
        if not normalized_bucket and raw_bucket in {
            "intern", "entry", "mid", "senior", "director_vp", "executive", "unknown"
        }:
            normalized_bucket = raw_bucket

    # Default to "unknown" if nothing matched
    if not normalized_bucket:
        normalized_bucket = "unknown"

    job["seniority_bucket"] = normalized_bucket

    # Normalize seniority_level: keep LLM's value or default to "Unknown"
    lvl = (job.get("seniority_level") or "").strip()
    if not lvl:
        lvl = "Unknown"
    job["seniority_level"] = lvl

    return job


def normalize_and_dedupe(parsed: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Normalize and deduplicate job listings from LLM output.

    Performs:
    - Whitespace normalization
    - Seniority field normalization
    - Empty field removal
    - Location canonicalization
    - Deduplication by job signature (URL, requisition_id, or title+location)

    When duplicates found, keeps the version with most fields filled.

    Args:
        parsed: Raw parsed JSON from LLM with "jobs" list

    Returns:
        Tuple of (cleaned_data, stats_dict) where:
        - cleaned_data: Normalized and deduped JSON
        - stats_dict: {"input_jobs": int, "deduped_out": int, "duplicates_removed": int}

    Example:
        >>> parsed = {"jobs": [{"title": "SWE", "job_url": "x"}, {"title": "SWE", "job_url": "x"}]}
        >>> cleaned, stats = normalize_and_dedupe(parsed)
        >>> stats["duplicates_removed"]
        1
    """
    src_url = _strip_ws(parsed.get("source_url") or "")
    page_title = _strip_ws(parsed.get("page_title") or "")
    jobs_in = parsed.get("jobs") or []

    if not isinstance(jobs_in, list):
        logger.warning(f"Expected jobs to be list, got {type(jobs_in)}")
        jobs_in = []

    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    dupes = 0

    for raw in jobs_in:
        if not isinstance(raw, dict):
            logger.debug(f"Skipping non-dict job entry: {type(raw)}")
            continue

        # Normalize whitespace
        job = _strip_ws(raw)

        # Normalize seniority before omitting empties
        # (we want "Unknown"/"unknown" to be kept)
        job = normalize_seniority_fields(job)

        # Remove empty fields
        job = _omit_empty(job)

        # Canonicalize location
        if "location" in job:
            loc = job["location"]
            job["location"] = _canon_loc(loc) if loc else None
            if not job["location"]:
                job.pop("location", None)

        # Generate signature for deduplication
        sig = _sig(job) or f"idx::{len(order)}"

        if sig not in seen:
            # First occurrence
            seen[sig] = job
            order.append(sig)
        else:
            # Duplicate found - keep the richer version
            dupes += 1
            a = seen[sig]
            b = job
            seen[sig] = a if _richness_score(a) >= _richness_score(b) else b

    jobs_out = [seen[s] for s in order]

    stats = {
        "input_jobs": len(jobs_in),
        "deduped_out": len(jobs_out),
        "duplicates_removed": dupes
    }

    logger.info(f"Dedupe stats: in={stats['input_jobs']} → out={stats['deduped_out']} (removed {stats['duplicates_removed']})")

    return {
        "source_url": src_url,
        "page_title": page_title,
        "jobs": jobs_out
    }, stats
