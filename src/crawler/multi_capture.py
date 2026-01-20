# src/crawler/multi_capture.py
# Headed multi-site capture with robust "progress" detection + optional Gemini batch postpass.
# Saves an HTML set for EVERY visited state:
#   - p001, p002, ... for Next/numbered pagination
#   - expanded for infinite scroll / load-more
# Outputs split under out/<domain>/{full,reduced_focus,reduced_lite,meta,signals}/
# If --with-llm is enabled, AFTER the crawl completes, it also writes per-page JSON via Gemini:
#   - out/<domain>/llm/<base>.<page_id>.jobs.json
#   - out/<domain>/<seed_base>.llm_manifest.json (unchanged from crawl)

import asyncio
import time
import json
import random
import argparse
import sys
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page

# Load env locally (no system env requirement)
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# === Import refactored utilities ===
from src.crawler.url_utils import domain_of, site_dir, base_name_for
from src.crawler.page_analyzer import (
    ordered_job_hrefs,
    job_list_len,
    results_fingerprint,
    progressed,
    wait_for_jobs_or_timeout,
)
from src.crawler.navigation import (
    snapshot_current,
    navigate_seed,
    try_click_load_more,
    click_next_page,
)
from src.crawler.file_manager import (
    build_paths,
    write_outputs,
    write_manifest,
    read_urls_from_file,
)

# === LLM helpers (batch will run AFTER crawl if --with-llm is passed) ===
from src.llm.llm_helper import extract_all_focus_htmls

# === Error logging ===
from src.core.error_logger import get_error_logger
from src.core.error_models import ErrorComponent, ErrorSeverity, ErrorType, ErrorStage

# === Process logging ===
from src.core.process_logger import get_process_logger
from src.core.process_models import ProcessStep

# === URL utilities ===
from src.utils.url_utils import extract_company_name

BASE_OUT = Path("out")
BASE_OUT.mkdir(exist_ok=True, parents=True)

# -------------------
# Politeness / runtime knobs
# -------------------
PER_DOMAIN_DELAY = (8, 15)       # s between seeds on same domain
BLOCK_RESOURCE_TYPES = {"media", "font", "image"}  # keep CSS/JS/XHR

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
]


# -------------------
# Browser ctx (headed)
# -------------------
@asynccontextmanager
async def domain_context(pw, domain: str, headed: bool):
    """
    Create a browser context for a domain with state persistence.

    Args:
        pw: Playwright instance
        domain: Domain name
        headed: Whether to run browser in headed mode

    Yields:
        Browser context instance
    """
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
# LLM hook (batch, after crawl)
# -------------------
def llm_batch_postpass(out_root: Path, domains_to_process: Optional[List[str]] = None, run_id: Optional[str] = None):
    """
    Walk out/<domain>/reduced_focus and run Gemini extraction for each domain.
    Skips files that already have llm/<base>.jobs.json (handled in helper).
    Any error for a given domain is logged and skipped; the batch continues.

    Args:
        out_root: Root output directory (typically Path("out"))
        domains_to_process: Optional list of domain names to process
        run_id: Optional run ID for process logging correlation
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
            written_paths = extract_all_focus_htmls(domain_dir, run_id=run_id)
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
                     jobs_max=200, time_budget=75, pages_max=3,
                     loadmore_max=5, scroll_max=20, no_change_cap=2,
                     run_id: Optional[str] = None, company: Optional[str] = None):
    """
    Crawl a single seed URL with pagination/infinite scroll support.

    Captures multiple page states:
    - p001: Initial page load
    - expanded: After load-more/scroll actions
    - p002, p003, etc.: Pagination clicks

    Args:
        page: Playwright page instance
        seed_url: Starting URL
        jobs_max: Stop after finding this many job links
        time_budget: Maximum seconds for expansion phase
        pages_max: Maximum pagination pages to visit
        loadmore_max: Maximum load-more clicks
        scroll_max: Maximum scroll attempts
        no_change_cap: Stop after N rounds with no change
        run_id: Optional run ID for process logging correlation
        company: Optional company name for logging
    """
    domain = domain_of(seed_url)
    company_name = company or extract_company_name(domain)
    process_logger = get_process_logger()

    # Log Step 1: CRAWL_START
    if run_id:
        process_logger.log_step(
            run_id=run_id,
            step=ProcessStep.CRAWL_START,
            company=company_name,
            domain=domain,
            metadata={"url": seed_url, "jobs_max": jobs_max, "time_budget": time_budget, "pages_max": pages_max}
        )

    # p001
    full_html, red_focus, red_lite, signals, meta = await navigate_seed(page, seed_url)
    if not full_html:
        write_outputs(domain, seed_url, full_html or "", red_focus or "", red_lite or "", signals, meta, page_id="p001")
        return

    write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id="p001")

    # Log Step 3: HTML_EXTRACTED (after p001)
    if run_id:
        process_logger.log_step(
            run_id=run_id,
            step=ProcessStep.HTML_EXTRACTED,
            company=company_name,
            domain=domain,
            metadata={"page_id": "p001", "html_length": len(full_html)}
        )

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
        print(f"[check] {tag} → progress={ok} diffs={diffs or []} count={cur_fp['job_count']}")
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
            stop_reason = "stable"
            break
        # Final fallback: wait a bit
        await page.wait_for_timeout(random.randint(1500, 2500))
        if no_change_rounds >= no_change_cap:
            stop_reason = "stable"
            break

    # If content grew via load-more/scroll, snapshot as "expanded"
    if grew_any:
        full_html, red_focus, red_lite, signals, meta = await snapshot_current(page)
        write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id="expanded")
        entries.append({
            "page_id": "expanded",
            "files": build_paths(domain, seed_base, "expanded"),
            "counts": {"unique_jobs": len(await ordered_job_hrefs(page, seed_url)), "list_len": await job_list_len(page)},
            "ts": int(time.time())
        })

    write_manifest(
        domain,
        seed_base,
        entries,
        mode="expansion",
        stop_reason=stop_reason,
        cfg={"jobs_max": jobs_max, "time_budget": time_budget, "loadmore_max": loadmore_max, "scroll_max": scroll_max},
    )

    # ----- Pagination (Next clicks)
    pages_seen = 1
    prev_fp = await results_fingerprint(page, seed_url)
    no_change_rounds = 0

    while pages_seen < pages_max:
        if not await click_next_page(page):
            stop_reason = "no_next"
            break

        await page.wait_for_timeout(random.randint(1500, 2500))
        await wait_for_jobs_or_timeout(page, seed_url, max_wait_ms=10000)

        cur_fp = await results_fingerprint(page, seed_url)
        ok, diffs = progressed(prev_fp, cur_fp)
        print(f"[check] pagination p{pages_seen+1:03d} → progress={ok} diffs={diffs}")

        if ok:
            pages_seen += 1
            page_id = f"p{pages_seen:03d}"
            full_html, red_focus, red_lite, signals, meta = await snapshot_current(page)
            write_outputs(domain, seed_url, full_html, red_focus, red_lite, signals, meta, page_id=page_id)
            entries.append({
                "page_id": page_id,
                "files": build_paths(domain, seed_base, page_id),
                "counts": {"unique_jobs": len(await ordered_job_hrefs(page, seed_url)), "list_len": await job_list_len(page)},
                "ts": int(time.time())
            })
            prev_fp = cur_fp
            no_change_rounds = 0
        else:
            no_change_rounds += 1
            if no_change_rounds >= 2:
                stop_reason = "pagination_stable"
                break

    write_manifest(
        domain,
        seed_base,
        entries,
        mode="pagination",
        stop_reason=stop_reason if pages_seen < pages_max else "pages_cap",
        cfg={"pages_max": pages_max},
    )

    # Log Step 2: CRAWL_COMPLETE
    if run_id:
        process_logger.log_step(
            run_id=run_id,
            step=ProcessStep.CRAWL_COMPLETE,
            company=company_name,
            domain=domain,
            metadata={"pages_seen": pages_seen, "stop_reason": stop_reason, "entries_count": len(entries)}
        )


# -------------------
# Domain loop (returns list of domains processed)
# -------------------
async def crawl(urls: List[str], headed: bool,
                jobs_max=100, time_budget=75, pages_max=3,
                loadmore_max=5, scroll_max=20, no_change_cap=2) -> tuple[List[str], str]:
    """
    Crawl multiple URLs, grouping by domain.

    Args:
        urls: List of seed URLs to crawl
        headed: Whether to run browser in headed mode
        jobs_max: Maximum job links to find per seed
        time_budget: Maximum seconds for expansion phase
        pages_max: Maximum pagination pages per seed
        loadmore_max: Maximum load-more clicks
        scroll_max: Maximum scroll attempts
        no_change_cap: Stop after N rounds with no change

    Returns:
        Tuple of (list of domain names processed, run_id for process logging)
    """
    by_domain: Dict[str, List[str]] = {}
    for u in urls:
        by_domain.setdefault(domain_of(u), []).append(u)

    # Generate run_id for this crawl session
    process_logger = get_process_logger()
    run_id = process_logger.generate_run_id()

    processed_domains: List[str] = []
    async with async_playwright() as pw:
        for domain, durls in by_domain.items():
            print(f"\n=== Domain: {domain} ({len(durls)} seeds) ===")
            # Extract company name from domain
            company_name = extract_company_name(domain)
            try:
                async with domain_context(pw, domain, headed=headed) as ctx:
                    processed_domains.append(domain)
                    page = await ctx.new_page()
                    for url in durls:
                        print(f"[seed] {domain} → {url}")
                        start = time.time()
                        try:
                            await crawl_seed(page, url, jobs_max, time_budget, pages_max, loadmore_max, scroll_max, no_change_cap, run_id=run_id, company=company_name)
                        except Exception as e:
                            print(f"[error] seed failed for {url}: {e}")
                            traceback.print_exc()
                            # Log crawl seed failure
                            get_error_logger().log_exception(
                                e,
                                component=ErrorComponent.CRAWLER,
                                stage=ErrorStage.NAVIGATE_SEED,
                                domain=domain,
                                url=url,
                                severity=ErrorSeverity.ERROR,
                                metadata={
                                    "jobs_max": jobs_max,
                                    "time_budget": time_budget,
                                    "pages_max": pages_max,
                                }
                            )
                            # move to next URL in this domain
                            continue

                        await page.wait_for_timeout(random.randint(PER_DOMAIN_DELAY[0] * 1000, PER_DOMAIN_DELAY[1] * 1000))
                        if (time.time() - start) < 4:
                            await page.wait_for_timeout(random.randint(2000, 4000))
            except Exception as e:
                print(f"[domain error] aborting domain {domain} due to exception: {e}")
                traceback.print_exc()
                # Log domain-level failure
                get_error_logger().log_exception(
                    e,
                    component=ErrorComponent.CRAWLER,
                    stage="crawl_domain",
                    domain=domain,
                    url=durls[0] if durls else "",
                    severity=ErrorSeverity.CRITICAL,
                    metadata={
                        "seeds_count": len(durls),
                        "seeds": durls[:3],  # Log first 3 URLs
                    }
                )
                # do NOT add to processed_domains if everything blew up before any seed
                # (we only appended inside the with-block)
                continue
    return processed_domains, run_id


# -------------------
# CLI
# -------------------
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

    run_id = None
    try:
        # First: crawl (headed unless --headless)
        domains_done, run_id = asyncio.run(crawl(
            targets, headed=headed,
            jobs_max=args.jobs_max, time_budget=args.time_budget, pages_max=args.pages_max,
            loadmore_max=args.loadmore_max, scroll_max=args.scroll_max, no_change_cap=args.no_change_cap
        ))
        print(f"\n[crawl complete] run_id={run_id}")
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
            llm_batch_postpass(BASE_OUT, domains_to_process=domains_done, run_id=run_id)
        except KeyboardInterrupt:
            print("\n[abort] KeyboardInterrupt – stopping LLM batch.")
        except Exception as e:
            print(f"[LLM batch error] {e}")
            traceback.print_exc()
