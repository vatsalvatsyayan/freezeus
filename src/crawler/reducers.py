"""
HTML reduction scripts for crawler.

This module contains JavaScript code executed in the browser to reduce
HTML pages to their essential job-listing content.

Two reduction strategies:
- FOCUS: Keeps job-heavy containers with scoring algorithm
- LITE: Strips scripts/styles but keeps all content
"""

# Focused reduction - keeps only high-scoring containers (especially job listings)
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

# Lite reduction - strips scripts/styles but keeps all visible content
REDUCE_LITE_JS = r"""
() => {
  const root = document.documentElement.cloneNode(true);
  root.querySelectorAll('script, style, noscript, template').forEach(n => n.remove());
  const html = root.outerHTML.replace(/\s{2,}/g, ' ').replace(/>\s+</g, '><');
  return '<!doctype html><meta charset="utf-8">' + html;
}
"""
