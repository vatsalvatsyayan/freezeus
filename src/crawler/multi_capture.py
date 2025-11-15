# src/crawler/multi_capture.py
# Headed multi-site capture with robust "progress" detection + optional Gemini batch postpass.
# Saves an HTML set for EVERY visited state:
#   - p001, p002, ... for Next/numbered pagination
#   - expanded for infinite scroll / load-more
# Outputs split under out/<domain>/{full,reduced_focus,reduced_lite,meta,signals}/
# If --with-llm is enabled, AFTER the crawl completes, it also writes per-page JSON via Gemini:
#   - out/<domain>/llm/<base>.<page_id>.jobs.json
#   - out/<domain>/<seed_base>.llm_manifest.json (unchanged from crawl)

import asyncio, re, time, json, random, hashlib, argparse, sys, unicodedata, traceback
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, Page

# Load env locally (no system env requirement)
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# === LLM helpers (batch will run AFTER crawl if --with-llm is passed) ===
from src.llm.llm_helper import extract_all_focus_htmls

BASE_OUT = Path("out")
BASE_OUT.mkdir(exist_ok=True, parents=True)

# -------------------
# Politeness / runtime knobs
# -------------------
PER_DOMAIN_DELAY = (8, 15)       # s between seeds on same domain
MAX_RETRIES       = 3
NAV_TIMEOUT_MS    = 45_000
BLOCK_RESOURCE_TYPES = {"media", "font", "image"}  # keep CSS/JS/XHR

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
]

# -------------------
# Reducers
# -------------------
REDUCE_FOCUS_JS = r"""
() => {
  // --- helper: detect job-like links ---
  function looksLikeJobHref(href) {
    if (!href) return false;
    href = String(href).toLowerCase();
    // Vendor patterns
    if (href.includes('greenhouse.io')
      || href.includes('myworkdayjobs.com')
      || href.includes('ashbyhq.com')
      || href.includes('lever.co')
      || href.includes('smartrecruiters.com')
      || href.includes('jobvite.com')
      || href.includes('boards.eu.greenhouse.io')
    ) return true;

    // Generic joby paths
    if (href.includes('/jobs/')
      || href.includes('/job/')
      || href.includes('/careers/')
      || href.includes('/career/')
      || href.includes('/positions/')
      || href.includes('/position/')
      || href.includes('gh_jid=')
      || href.includes('gh_src=')
    ) return true;

    return false;
  }

  const IGNORE = new WeakSet();
  { // mark banners/overlays on live DOM
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
    const toMark = [];
    while (walker.nextNode()) {
      const el = walker.currentNode;
      const cs = getComputedStyle(el);
      const fixed = cs.position === 'fixed';
      const hidden = cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0;
      const idcl = (el.id + " " + (el.className || "")).toLowerCase();
      const bannerish = /cookie|consent|newsletter|subscribe|sign-?up|login|advert|promo|overlay|modal|toast|social|gdpr/.test(idcl);
      if (hidden || (fixed && bannerish)) toMark.push(el);
    }
    toMark.forEach(el => IGNORE.add(el));
  }

  // clone & strip noisy tags
  const root = document.documentElement.cloneNode(true);
  root.querySelectorAll('script, style, noscript, template').forEach(n => n.remove());
  root.querySelectorAll('*').forEach(n => {
    const id = n.id; const cls = n.className || '';
    if (!id && !cls) return;
    const live = id ? document.getElementById(id) : null;
    if (live && live.className === cls && IGNORE.has(live)) n.remove();
  });

  function scoreContainer(el) {
    const text = (el.innerText || '').trim();
    const textLen = text.length;
    const links = Array.from(el.querySelectorAll('a'));
    const linkTextLen = links.reduce((a,b)=> a + ((b.innerText||'').length), 0);
    const linkDensity = textLen ? (linkTextLen / textLen) : 0;
    const hcount = el.querySelectorAll('h1,h2,h3').length;
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const isMain = (tag === 'main') || (role === 'main') || (tag === 'article');

    // Does this container look like it holds job links?
    let hasJobLinks = false;
    for (const a of links) {
      const href = a.getAttribute('href') || '';
      if (looksLikeJobHref(href)) {
        hasJobLinks = true;
        break;
      }
    }

    let repetition = 0;
    if (el.children && el.children.length > 3) {
      const firstTag = el.children[0].tagName;
      const sameTagSiblings = Array.from(el.children).filter(c => c.tagName === firstTag).length;
      repetition = sameTagSiblings / el.children.length;
    }
    const looksNav = ['nav','header','footer'].includes(tag) || role === 'navigation' || role === 'banner' || role === 'contentinfo';

    let score = 0;
    score += Math.log2(1 + textLen);
    score += isMain ? 3 : 0;
    score += hcount ? 1.5 : 0;
    score += repetition * 2;
    score -= linkDensity * 2;
    score -= looksNav ? 2 : 0;

    // Big positive bias for containers that look like job lists
    if (hasJobLinks) {
      score += 25;   // <- this is the crucial boost
    }

    return { score, textLen, linkDensity, hcount, isMain, looksNav, hasJobLinks };
  }

  // candidate containers
  const candidates = Array.from(root.querySelectorAll('main,#content,article,section,div'))
    .filter(el => (el.innerText || '').trim().length > 200);

  const scored = candidates.map(el => ({ el, s: scoreContainer(el) }))
                           .sort((a,b) => b.s.score - a.s.score);

  // Keep more than before to avoid dropping entire job sections (was 3)
  const TOP_N = Math.min(10, scored.length);
  const top = scored.slice(0, TOP_N);

  const kept = top.map(t => ({
    html: t.el.outerHTML.replace(/\s{2,}/g, ' ').replace(/>\s+</g, '><'),
    signals: t.s
  }));

  return {
    reduced_html: '<!doctype html><meta charset="utf-8"><title>'+document.title+'</title>' + kept.map(k=>k.html).join('\n'),
    kept_signals: kept.map(k=>k.signals),
    meta: {
      kept_count: kept.length,
      total_candidates: scored.length,
      url: location.href,
      title: document.title
    }
  };
}
"""

REDUCE_LITE_JS = r"""
() => {
  const root = document.documentElement.cloneNode(true);
  root.querySelectorAll('script, style, noscript, template').forEach(n => n.remove());
  const html = root.outerHTML.replace(/\s{2,}/g, ' ').replace(/>\s+</g, '><');
  return '<!doctype html><meta charset="utf-8">' + html;
}
"""

# -------------------
# Helpers
# -------------------
KEYWORD_RE = re.compile(r"(job|jobs|career|opening|openings|position|positions|role|roles|req|requisition|opportunit)", re.I)

def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()

def site_dir(domain: str) -> Path:
    p = BASE_OUT / domain
    p.mkdir(exist_ok=True, parents=True)
    return p

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def _slug_last_segment(u: str, fallback: str = "page", max_len: int = 40) -> str:
    segs = [s for s in urlparse(u).path.split('/') if s] or [fallback]
    s = segs[-1]
    s = re.sub(r"^\d+[-_]*", "", s)
    s = re.sub(r"[-_]*\d+$", "", s) or fallback
    s = unicodedata.normalize("NFKD", s).lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s or fallback)[:max_len]

def _short_hash(u: str) -> str:
    return hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]

def base_name_for(url: str, title: Optional[str] = None) -> str:
    seg = _slug_last_segment(url, fallback="index")
    if seg in ("index", "page") and title:
        t = unicodedata.normalize("NFKD", title).lower()
        t = re.sub(r"[^a-z0-9\-]+", "-", t)
        seg = (re.sub(r"-{2,}", "-", t).strip("-") or "page")[:40]
    return f"{seg}__{_short_hash(url)}"

def _canon_url(seed: str, href: str) -> Optional[str]:
    try:
        absu = urljoin(seed, href)
        u = urlparse(absu)
        qs = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
              if k.lower() not in {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","gclid","fbclid"}]
        newu = u._replace(query=urlencode(qs), fragment="")
        return urlunparse((newu.scheme.lower(), newu.netloc.lower(), newu.path, newu.params, newu.query, ""))
    except Exception:
        return None

async def ordered_job_hrefs(page: Page, seed_url: str, cap: int = 60) -> List[str]:
    anchors = await page.eval_on_selector_all(
        "main a[href], article a[href], section a[href], div a[href]",
        "els => els.map(a => ({href:a.getAttribute('href')||'',text:a.innerText||''}))"
    )
    out: List[str] = []
    for a in anchors:
        href = (a.get("href") or "").strip()
        text = (a.get("text") or "").strip()
        if not href:
            continue
        if KEYWORD_RE.search(href) or KEYWORD_RE.search(text):
            cu = _canon_url(seed_url, href)
            if cu:
                out.append(cu)
                if len(out) >= cap:
                    break
    return out

async def job_list_len(page: Page) -> int:
    try:
        li = await page.locator('[role="listitem"]').count()
        if li >= 5:
            return li
        cards = await page.locator("article, li, div[class*='card'], div[class*='result']").count()
        return cards
    except Exception:
        return 0

async def page_text_fingerprint(page: Page, cap: int = 50) -> str:
    try:
        texts = await page.eval_on_selector_all(
            "main [role='listitem'], main article, main li, section [role='listitem'], section article",
            f"els => els.slice(0,{cap}).map(e => (e.innerText||'').trim()).join('\\n\\n')"
        )
        return sha1(texts or "")
    except Exception:
        return ""

async def normalized_url_tuple(page: Page) -> str:
    try:
        u = urlparse(page.url)
        qs = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
              if k.lower() not in {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","gclid","fbclid"}]
        return urlunparse((u.scheme.lower(), u.netloc.lower(), u.path, u.params, urlencode(qs), ""))
    except Exception:
        return page.url

async def scroll_height(page: Page) -> int:
    try:
        return await page.evaluate("()=>(document.scrollingElement||document.documentElement).scrollHeight|0")
    except Exception:
        return 0

async def scroll_to_bottom_until_stable(page: Page,
                                        max_rounds: int = 20,
                                        wait_ms: int = 800,
                                        min_delta: int = 200) -> None:
    """
    Aggressively scrolls to the bottom of the page until the scroll height stops
    increasing (or max_rounds is hit). This is meant to trigger infinite-scroll
    / lazy-load behavior (e.g. Dropbox all-jobs).
    """
    try:
        last_h = await scroll_height(page)
        stable_rounds = 0

        for _ in range(max_rounds):
            await page.evaluate(
                "() => window.scrollTo(0, (document.scrollingElement || document.documentElement).scrollHeight)"
            )
            await page.wait_for_timeout(wait_ms)

            h = await scroll_height(page)
            if h - last_h < min_delta:
                stable_rounds += 1
            else:
                stable_rounds = 0
            last_h = h

            if stable_rounds >= 2:
                break
    except Exception:
        # Never kill the crawl just because scrolling failed
        return

async def results_fingerprint(page: Page, seed_url: str) -> dict:
    hrefs = await ordered_job_hrefs(page, seed_url, cap=80)
    hrefs_hash = sha1("\n".join(hrefs))
    text_hash = await page_text_fingerprint(page, cap=60)
    count = await job_list_len(page)
    first = hrefs[0] if hrefs else ""
    last = hrefs[-1] if hrefs else ""
    url_norm = await normalized_url_tuple(page)
    sh = await scroll_height(page)
    fp = {
        "url": url_norm,
        "hrefs_hash": hrefs_hash,
        "text_hash": text_hash,
        "count": count,
        "first": first,
        "last": last,
        "scroll_h": sh,
    }
    return fp

def progressed(before: dict, after: dict) -> Tuple[bool, List[str]]:
    diffs: List[str] = []
    for k in ("url", "hrefs_hash", "text_hash", "count", "first", "last"):
        if before.get(k) != after.get(k):
            diffs.append(k)
    return (len(diffs) > 0), diffs

# ========= SPA-friendly "jobs ready" waits =========
JOB_READY_SELECTORS = [
    "[role='listitem']",
    "ul[role='list'] > li",
    "article[data-job-id]",
    "div[class*='job-card']",
    "div[class*='result']",
    "a[href*='/job/']", "a[href*='/jobs/']", "a[href*='/careers/']",
    "a[href*='job?']", "a[href*='jobs?']"
]

async def _has_any(page: Page, selectors: list) -> bool:
    for sel in selectors:
        try:
            if await page.locator(sel).first.count():
                return True
        except Exception:
            pass
    return False

async def wait_for_jobs_or_timeout(page: Page, seed_url: str, max_wait_ms: int = 35000) -> bool:
    start = time.time()
    for t in (10_000, 6_000):
        try:
            await page.wait_for_load_state("networkidle", timeout=t)
        except Exception:
            pass
        await page.wait_for_timeout(400)
        if await _has_any(page, JOB_READY_SELECTORS):
            return True
        if len(await ordered_job_hrefs(page, seed_url)) > 0:
            return True
    while (time.time() - start) * 1000 < max_wait_ms:
        if await _has_any(page, JOB_READY_SELECTORS):
            return True
        if len(await ordered_job_hrefs(page, seed_url)) > 0:
            return True
        await page.mouse.wheel(0, random.randint(1500, 3000))
        await page.wait_for_timeout(600)
    return False
# ===================================================

# -------------------
# Output layout
# -------------------
TYPE_DIRS = {
    "full": "full",
    "focus": "reduced_focus",
    "lite": "reduced_lite",
    "meta": "meta",
    "signals": "signals",
}

def ensure_type_dirs(domain: str) -> Dict[str, Path]:
    root = site_dir(domain)
    out: Dict[str, Path] = {}
    for k, sub in TYPE_DIRS.items():
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        out[k] = d
    # also ensure LLM dir exists (output lives there)
    (root / "llm").mkdir(parents=True, exist_ok=True)
    return out

def build_paths(domain: str, base: str, page_id: str) -> Dict[str, Path]:
    dirs = ensure_type_dirs(domain)
    return {
        "full":    dirs["full"]    / f"{base}.{page_id}.html",
        "focus":   dirs["focus"]   / f"{base}.{page_id}.html",
        "lite":    dirs["lite"]    / f"{base}.{page_id}.html",
        "meta":    dirs["meta"]    / f"{base}.{page_id}.json",
        "signals": dirs["signals"] / f"{base}.{page_id}.json",
    }

def write_manifest(domain: str, seed_base: str, entries: List[dict], mode: str, stop_reason: str, cfg: dict):
    root = site_dir(domain)
    for e in entries:
        if "files" in e:
            e["files"] = {k: str(v) for k, v in e["files"].items()}
    (root / f"{seed_base}.manifest.json").write_text(
        json.dumps({
            "seed_base": seed_base,
            "mode": mode,
            "stop_reason": stop_reason,
            "pages": entries,
            "config": cfg,
            "ts": int(time.time())
        }, ensure_ascii=False, indent=2),
        "utf-8"
    )

def write_outputs(domain: str, url: str, full_html: str, red_focus: str, red_lite: str, signals: list, meta: dict, page_id: str) -> Dict[str, Path]:
    title = (meta.get("reduce_meta") or {}).get("title") or meta.get("title")
    base  = base_name_for(url, title)
    paths = build_paths(domain, base, page_id)
    meta = dict(meta or {})
    meta["sha1"] = sha1(full_html or "")
    meta["url"] = url
    meta["page_id"] = page_id
    paths["full"].write_text(full_html or "", "utf-8")
    paths["focus"].write_text(red_focus or "", "utf-8")
    paths["lite"].write_text(red_lite or "", "utf-8")
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    if signals:
        paths["signals"].write_text(json.dumps(signals, ensure_ascii=False, indent=2), "utf-8")
    print(f"[saved] {domain}  {paths['full'].name}")
    return paths

# -------------------
# Browser ctx (headed)
# -------------------
@asynccontextmanager
async def domain_context(pw, domain: str, headed: bool):
    storage_file = site_dir(domain) / "_storage_state.json"
    browser = await pw.chromium.launch(
        headless=not headed,
        args=["--disable-blink-features=AutomationControlled"]
    )
    ctx_kwargs: Dict[str, object] = {
        "user_agent": random.choice(UA_POOL),
        "viewport": {"width": random.randint(1280, 1440), "height": random.randint(720, 900)},
        "locale": "en-US",
        "java_script_enabled": True,
    }
    if storage_file.exists():
        ctx_kwargs["storage_state"] = json.loads(storage_file.read_text("utf-8"))
    context = await browser.new_context(**ctx_kwargs)
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    async def _route(route):
        if route.request.resource_type in BLOCK_RESOURCE_TYPES:
            return await route.abort()
        return await route.continue_()

    await context.route("**/*", _route)
    try:
        yield context
    finally:
        try:
            state = await context.storage_state()
            storage_file.write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass
        await context.close()
        await browser.close()

# -------------------
# Snapshot helpers (NO navigation)
# -------------------
async def snapshot_current(page: Page) -> Tuple[str, str, str, list, dict]:
    for t in (20_000, 8_000):
        try:
            await page.wait_for_load_state("networkidle", timeout=t)
        except Exception:
            pass
    await page.wait_for_timeout(random.randint(700, 1200))
    full_html = await page.content()
    focus = await page.evaluate(REDUCE_FOCUS_JS)
    red_focus = focus.get("reduced_html", "")
    signals = focus.get("kept_signals", [])
    meta_reduce = focus.get("meta", {})
    red_lite = await page.evaluate(REDUCE_LITE_JS)
    meta = {
        "url": page.url,
        "ts": int(time.time()),
        "title": meta_reduce.get("title"),
        "reduce_meta": meta_reduce,
    }
    return full_html, red_focus, red_lite, signals, meta

# --------- wait for jobs before first snapshot ---------
async def navigate_seed(page: Page, url: str):
    meta = {"url": url, "ts": int(time.time())}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[nav] {url} (attempt {attempt})")
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            code = resp.status if resp else 0
            meta["status"] = code
            if code in (200, 304):
                ready = await wait_for_jobs_or_timeout(page, url, max_wait_ms=35_000)
                if not ready:
                    print("[seed] jobs not visible yet; proceeding but capture may be sparse")
                else:
                    # ensure we trigger any lazy-load / infinite-scroll content before first snapshot
                    await scroll_to_bottom_until_stable(page, max_rounds=20, wait_ms=800, min_delta=200)
                return await snapshot_current(page)
            if code in (403, 429, 503):
                backoff = (2 ** attempt) + random.random() * 3
                print(f"[backoff] {code}→sleep {backoff:.1f}s")
                await page.wait_for_timeout(int(backoff * 1000))
                continue
            break
        except Exception as e:
            meta["error"] = str(e)[:300]
            backoff = (2 ** attempt) + random.random() * 2
            print(f"[error] {e}→sleep {backoff:.1f}s")
            await page.wait_for_timeout(int(backoff * 1000))
    return None, None, None, [], meta

# -------------------
# Clicking
# -------------------
async def try_click_load_more(page: Page) -> bool:
    sel = "button:visible, a:visible"
    patterns = [
        r"\b(load more|show more|view more|more results|see more|show all)\b",
        r"\b(more jobs|more openings|show \d+\s*more|display more|load next|load additional|fetch more)\b",
    ]
    try:
        loc = page.locator(sel)
        count = await loc.count()
        for i in range(min(count, 140)):
            el = loc.nth(i)
            try:
                txt = (await el.inner_text(timeout=300)).strip()
            except Exception:
                continue
            if any(re.search(p, txt, re.I) for p in patterns):
                if await el.is_enabled() and await el.is_visible():
                    await el.click()
                    print(f"[click] load-more: {txt[:60]}")
                    await wait_for_jobs_or_timeout(page, page.url, max_wait_ms=12_000)
                    await page.wait_for_timeout(random.randint(700, 1300))
                    return True
    except Exception:
        pass
    return False

async def click_next_page(page: Page) -> bool:
    """
    Try very hard to click a 'Next page' control.

    Strategy:
      1. Use Playwright's accessibility API: any button/link whose accessible
         name contains 'next' (e.g. 'Next', 'Next page', 'Next results').
      2. Fall back to common CSS selectors (rel=next, arrows in nav, etc.).
    """
    # ---- 1) Accessibility-based (most robust, works with icon-only buttons) ----
    try:
        # Any *button* whose accessible name contains 'next'
        btn = page.get_by_role("button", name=re.compile(r"next", re.I)).first
        if await btn.count():
            if await btn.is_visible() and await btn.is_enabled():
                await btn.click()
                print("[click] next: role=button name~=next")
                await page.wait_for_timeout(random.randint(900, 1600))
                return True
    except Exception:
        pass

    try:
        # Any *link* (anchor) whose accessible name contains 'next'
        link = page.get_by_role("link", name=re.compile(r"next", re.I)).first
        if await link.count():
            if await link.is_visible() and await link.is_enabled():
                await link.click()
                print("[click] next: role=link name~=next")
                await page.wait_for_timeout(random.randint(900, 1600))
                return True
    except Exception:
        pass

    # ---- 2) CSS fallbacks (older sites, non-semantic markup) ----
    candidates = [
        # aria-label / rel based
        'button[aria-label*="Next"]',
        'a[aria-label*="Next"]',
        '[role="button"][aria-label*="Next"]',
        'a[rel="next"]',

        # explicit "Next page" / "Next results"
        'button[aria-label*="Next page"]',
        'a[aria-label*="Next page"]',
        'button[aria-label*="Next results"]',
        'a[aria-label*="Next results"]',

        # generic nav arrows
        'nav button:has-text(">")',
        'nav a:has-text(">")',
        'nav button:has-text("›")',
        'nav a:has-text("›")',
        'nav button:has-text("»")',
        'nav a:has-text("»")',
    ]

    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible() and await loc.is_enabled():
                await loc.click()
                print(f"[click] next: {sel}")
                await page.wait_for_timeout(random.randint(900, 1600))
                return True
        except Exception:
            continue

    return False

# -------------------
# LLM hook (batch, after crawl)
# -------------------
def llm_batch_postpass(out_root: Path, domains_to_process: Optional[List[str]] = None):
    """
    Walk out/<domain>/reduced_focus and run Gemini extraction for each domain.
    Skips files that already have llm/<base>.jobs.json (handled in helper).
    Any error for a given domain is logged and skipped; the batch continues.
    """
    out_root = Path(out_root)
    if domains_to_process:
        candidates = [out_root / d for d in domains_to_process]
    else:
        candidates = [p for p in out_root.iterdir() if p.is_dir() and (p / "reduced_focus").exists()]

    total = 0
    for domain_dir in candidates:
        print(f"\n=== LLM batch: {domain_dir.name} ===")
        try:
            written_paths = extract_all_focus_htmls(domain_dir)
            for p in written_paths:
                print(f"[LLM saved] {p}")
            total += len(written_paths)
        except Exception as e:
            print(f"[LLM error] domain {domain_dir.name} failed: {e}")
            traceback.print_exc()
            # continue with next domain
            continue
    print(f"\n[LLM batch done] Wrote {total} JSON files")

# -------------------
# Seed crawl
# -------------------
async def crawl_seed(page: Page, seed_url: str,
                     jobs_max=100, time_budget=75, pages_max=3,
                     loadmore_max=5, scroll_max=20, no_change_cap=2):

    # p001
    full_html, red_focus, red_lite, signals, meta = await navigate_seed(page, seed_url)
    domain = domain_of(seed_url)
    if not full_html:
        write_outputs(domain, seed_url, full_html or "", red_focus or "", red_lite or "", signals, meta, page_id="p001")
        return

    write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id="p001")

    seed_base = base_name_for(seed_url, meta.get("title"))
    entries = [{
        "page_id": "p001",
        "files": build_paths(domain, seed_base, "p001"),
        "counts": {"unique_jobs": len(await ordered_job_hrefs(page, seed_url)), "list_len": await job_list_len(page)},
        "ts": int(time.time())
    }]

    # ----- In-page expansion (load-more / infinite)
    start = time.time()
    clicks = 0
    scrolls = 0
    no_change_rounds = 0
    grew_any = False
    stop_reason = "none"
    prev_fp = await results_fingerprint(page, seed_url)

    async def progress_and_update(tag: str):
        nonlocal grew_any, prev_fp, no_change_rounds
        cur_fp = await results_fingerprint(page, seed_url)
        ok, diffs = progressed(prev_fp, cur_fp)
        print(f"[check] {tag} → progress={ok} diffs={diffs or []} count={cur_fp['count']}")
        if ok:
            grew_any = True
            no_change_rounds = 0
            prev_fp = cur_fp
        else:
            no_change_rounds += 1
        return ok

    while True:
        if len(await ordered_job_hrefs(page, seed_url)) >= jobs_max:
            stop_reason = "jobs_cap"
            break
        if (time.time() - start) >= time_budget:
            stop_reason = "time"
            break
        progressed_something = False

        if clicks < loadmore_max and await try_click_load_more(page):
            clicks += 1
            if await progress_and_update("load-more"):
                progressed_something = True

        if not progressed_something and scrolls < scroll_max:
            await page.mouse.wheel(0, random.randint(2500, 6000))
            await page.wait_for_timeout(random.randint(900, 1400))
            await wait_for_jobs_or_timeout(page, seed_url, max_wait_ms=3000)
            scrolls += 1
            if await progress_and_update(f"scroll {scrolls}/{scroll_max}"):
                progressed_something = True

        if progressed_something:
            continue
        if no_change_rounds >= no_change_cap:
            stop_reason = "no_change"
            break

    if grew_any:
        # final safety: make sure we've fully scrolled to bottom before expanded snapshot
        await scroll_to_bottom_until_stable(page, max_rounds=10, wait_ms=800, min_delta=200)

        full_html, red_focus, red_lite, signals, meta = await snapshot_current(page)
        write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id="expanded")
        entries.append({
            "page_id": "expanded",
            "files": build_paths(domain, seed_base, "expanded"),
            "counts": {"unique_jobs": len(await ordered_job_hrefs(page, seed_url)), "list_len": await job_list_len(page)},
            "ts": int(time.time())
        })
        write_manifest(domain, seed_base, entries, mode="in_page", stop_reason=stop_reason, cfg={
            "jobs_max": jobs_max, "time_budget": time_budget, "loadmore_max": loadmore_max, "scroll_max": scroll_max, "no_change_cap": no_change_cap
        })
        return

    # ----- Classic pagination (Next)
    print("[paginate] switching to next-page loop…")
    pages_seen = 1
    stop_reason = "pages_cap"
    while pages_seen < pages_max:
        before = await results_fingerprint(page, seed_url)
        clicked = await click_next_page(page)
        if not clicked:
            stop_reason = "no_next"
            break

        ok = False
        for _ in range(20):
            await wait_for_jobs_or_timeout(page, seed_url, max_wait_ms=4000)
            await page.wait_for_timeout(400)
            after = await results_fingerprint(page, seed_url)
            ok, _ = progressed(before, after)
            if ok:
                break
        if not ok:
            stop_reason = "no_change"
            print("[paginate] next produced no change")
            break

        full_html, red_focus, red_lite, signals, meta = await snapshot_current(page)
        pages_seen += 1
        pid = f"p{pages_seen:03d}"
        write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id=pid)
        entries.append({
            "page_id": pid,
            "files": build_paths(domain, seed_base, pid),
            "counts": {"unique_jobs": len(await ordered_job_hrefs(page, seed_url)), "list_len": await job_list_len(page)},
            "ts": int(time.time())
        })
        await page.wait_for_timeout(random.randint(1200, 2400))

    write_manifest(
        domain,
        seed_base,
        entries,
        mode="pagination",
        stop_reason=stop_reason if pages_seen < pages_max else "pages_cap",
        cfg={"pages_max": pages_max},
    )

# -------------------
# Domain loop (returns list of domains processed)
# -------------------
async def crawl(urls: List[str], headed: bool,
                jobs_max=100, time_budget=75, pages_max=3,
                loadmore_max=5, scroll_max=20, no_change_cap=2) -> List[str]:
    by_domain: Dict[str, List[str]] = {}
    for u in urls:
        by_domain.setdefault(domain_of(u), []).append(u)

    processed_domains: List[str] = []
    async with async_playwright() as pw:
        for domain, durls in by_domain.items():
            print(f"\n=== Domain: {domain} ({len(durls)} seeds) ===")
            try:
                async with domain_context(pw, domain, headed=headed) as ctx:
                    processed_domains.append(domain)
                    page = await ctx.new_page()
                    for url in durls:
                        print(f"[seed] {domain} → {url}")
                        start = time.time()
                        try:
                            await crawl_seed(page, url, jobs_max, time_budget, pages_max, loadmore_max, scroll_max, no_change_cap)
                        except Exception as e:
                            print(f"[error] seed failed for {url}: {e}")
                            traceback.print_exc()
                            # move to next URL in this domain
                            continue

                        await page.wait_for_timeout(random.randint(PER_DOMAIN_DELAY[0] * 1000, PER_DOMAIN_DELAY[1] * 1000))
                        if (time.time() - start) < 4:
                            await page.wait_for_timeout(random.randint(2000, 4000))
            except Exception as e:
                print(f"[domain error] aborting domain {domain} due to exception: {e}")
                traceback.print_exc()
                # do NOT add to processed_domains if everything blew up before any seed
                # (we only appended inside the with-block)
                continue
    return processed_domains

# -------------------
# CLI
# -------------------
def read_urls_from_file(path: Path) -> List[str]:
    out: List[str] = []
    for line in path.read_text("utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    seen = set()
    dedup: List[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Headed multi-page capture with optional Gemini batch extraction.")
    ap.add_argument("--urls", required=True, help="Path to a file with one URL per line")
    ap.add_argument("--headed", action="store_true", default=True, help="Run headed (default ON)")
    ap.add_argument("--headless", action="store_true", default=False, help="Force headless (overrides --headed)")
    ap.add_argument("--with-llm", action="store_true", help="After crawl completes, run Gemini on all reduced_focus HTMLs saved")
    ap.add_argument("--jobs-max", type=int, default=100)
    ap.add_argument("--time-budget", type=int, default=75)
    ap.add_argument("--pages-max", type=int, default=3)
    ap.add_argument("--loadmore-max", type=int, default=5)
    ap.add_argument("--scroll-max", type=int, default=20)
    ap.add_argument("--no-change-cap", type=int, default=2)
    args = ap.parse_args()

    url_file = Path(args.urls)
    if not url_file.exists():
        print(f"[error] URLs file not found: {url_file}", file=sys.stderr)
        sys.exit(1)

    targets = read_urls_from_file(url_file)
    if not targets:
        print("[error] No URLs found in file.", file=sys.stderr)
        sys.exit(1)

    headed = args.headed and not args.headless

    try:
        # First: crawl (headed unless --headless)
        domains_done = asyncio.run(crawl(
            targets, headed=headed,
            jobs_max=args.jobs_max, time_budget=args.time_budget, pages_max=args.pages_max,
            loadmore_max=args.loadmore_max, scroll_max=args.scroll_max, no_change_cap=args.no_change_cap
        ))
    except KeyboardInterrupt:
        print("\n[abort] KeyboardInterrupt – stopping crawl.")
        sys.exit(1)
    except Exception as e:
        print(f"[fatal] uncaught error during crawl: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Then: LLM batch postpass over domains we just touched
    if args.with_llm and domains_done:
        try:
            llm_batch_postpass(BASE_OUT, domains_to_process=domains_done)
        except KeyboardInterrupt:
            print("\n[abort] KeyboardInterrupt – stopping LLM batch.")
        except Exception as e:
            print(f"[fatal] uncaught error during LLM batch: {e}")
            traceback.print_exc()