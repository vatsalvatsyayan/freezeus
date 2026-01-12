"""
Prompt management for LLM job extraction.

This module handles loading and managing extraction prompts for the LLM.
"""

from pathlib import Path
from src.core.logging import get_logger

logger = get_logger(__name__)

# Default extraction prompt
DEFAULT_PROMPT = """You are an expert at parsing career and job listing websites.
Your input is a reduced HTML fragment that contains the job listings section of a single page.

Goal:
- Extract every UNIQUE job posting from the HTML.
- Preserve the same order in which jobs appear on the page.

Rules:
- Include only real jobs; ignore UI like "Load more", "Apply", "Next page", filters, or search controls.
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


def load_extraction_prompt(prompt_path: Path = None) -> str:
    """
    Load extraction prompt from file with fallback to default.

    Args:
        prompt_path: Optional path to custom prompt file.
                    Defaults to configs/llm_extraction_prompt.txt

    Returns:
        Prompt text string

    Example:
        >>> prompt = load_extraction_prompt()
        >>> "You are an expert" in prompt
        True
    """
    if prompt_path is None:
        prompt_path = Path("configs/llm_extraction_prompt.txt")

    if prompt_path.exists():
        try:
            content = prompt_path.read_text(encoding='utf-8')
            logger.info(f"Loaded extraction prompt from {prompt_path}")
            return content
        except Exception as e:
            logger.warning(f"Failed to load prompt from {prompt_path}: {e}. Using default.")
            return DEFAULT_PROMPT
    else:
        logger.debug(f"Prompt file not found at {prompt_path}. Using default.")
        return DEFAULT_PROMPT


def get_default_prompt() -> str:
    """
    Get the default extraction prompt.

    Returns:
        Default prompt text

    Example:
        >>> prompt = get_default_prompt()
        >>> "seniority_bucket" in prompt
        True
    """
    return DEFAULT_PROMPT
