"""
Finding pages without adding a search provider.

`actions/web_search.py` already knows how to reach DuckDuckGo (with the
`ddgs` package the app installs) and how to fall back to Gemini's grounded
search. Reusing it means a research run inherits the quota circuit breaker that
file maintains — grounded search has a small separate quota, and a research run
that spent it in the first thirty seconds would break the user's ordinary
searches for the rest of the afternoon.

Results are dictionaries of `{title, snippet, url}`. Ranking is local and
deliberately boring: a page with a real snippet from a domain nobody has used
yet beats a social-media post with none. The intelligence belongs in the
researcher sub-agent, which sees the final list and decides what to read.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .fetcher import normalise_url

_BASE = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
_WEB = None

# Domains that answer a search query without answering the question. They are
# not dropped outright — a paper is occasionally only discussed there — but they
# sort last, which is usually enough for the per-question budget.
_LOW_VALUE = ("facebook.", "twitter.", "x.com", "instagram.", "pinterest.",
              "tiktok.", "reddit.com/r/", "quora.", "linkedin.com/posts")


def _web_search_module():
    """Load actions/web_search.py by path — `actions/` is not a package."""
    global _WEB
    with _LOCK:
        if _WEB is not None:
            return _WEB
        path = _BASE / "actions" / "web_search.py"
        spec = importlib.util.spec_from_file_location("research_web_search", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["research_web_search"] = module
        spec.loader.exec_module(module)
        _WEB = module
        return module


def _clean(results) -> list[dict]:
    out = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or "").strip()
        snippet = str(r.get("snippet") or r.get("body") or "").strip()
        url = str(r.get("url") or r.get("href") or "").strip()
        if not (title or snippet):
            continue
        if url and not url.lower().startswith(("http://", "https://")):
            url = ""
        out.append({"title": title, "snippet": snippet, "url": url})
    return out


def ddg(query: str, max_results: int = 6) -> list[dict]:
    try:
        results = _web_search_module()._ddg_search(query, max_results=max_results)
        return _clean(results)
    except Exception as e:
        print(f"[Research] search failed for {query!r}: {type(e).__name__}: {e}")
        return []


def grounded(query: str) -> list[dict]:
    """Gemini grounded search, as a single abstract-shaped result.

    It has no URLs of its own in the text it returns, so it is carried as one
    source with an empty URL: the researcher can still quote it, and the report
    labels it "answer without a citable page" rather than inventing a link."""
    try:
        text = _web_search_module()._gemini_search(
            f"Research query. Answer with specific facts, names, dates and "
            f"figures, and say plainly where the answer is uncertain: {query}")
        text = str(text or "").strip()
    except Exception as e:
        print(f"[Research] grounded search unavailable: {type(e).__name__}: {e}")
        return []
    if not text:
        return []
    return [{"title": f"Grounded answer — {query[:80]}",
             "snippet": re.sub(r"\s+", " ", text)[:2400], "url": ""}]


def rank(results: list[dict], limit: int) -> list[dict]:
    """Deduplicate by URL and order by how much a reader can actually use.

    Snippet length is the only signal available locally, and it correlates with
    a page that exists rather than a redirect. Domain diversity is enforced
    while taking: three pages from one site are three views of one argument."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    buckets = {"good": [], "weak": []}
    for r in results:
        url = normalise_url(r.get("url") or "")
        title = (r.get("title") or "").strip().lower()
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
        elif title and title in seen_titles:
            continue
        if title:
            seen_titles.add(title)
        score = len(r.get("snippet") or "")
        if not url:
            score -= 400            # grounded answer: useful, never first
        if any(bad in (url or "").lower() for bad in _LOW_VALUE):
            score -= 300
        if url.startswith("https://"):
            score += 20
        buckets["good" if score >= 120 else "weak"].append((score, r))

    ordered = [r for _, r in sorted(buckets["good"], key=lambda t: -t[0])]
    ordered += [r for _, r in sorted(buckets["weak"], key=lambda t: -t[0])]

    picked, domains = [], {}
    for r in ordered:
        if len(picked) >= limit:
            break
        host = normalise_url(r.get("url") or "").split("/")[2] if r.get("url") else ""
        if host and domains.get(host, 0) >= 2:
            continue
        if host:
            domains[host] = domains.get(host, 0) + 1
        picked.append(r)
    return picked


def search(query: str, max_results: int = 6, grounded_fallback: bool = True) -> list[dict]:
    """DuckDuckGo first; grounded search only when it returned nothing.

    The order is the lesson `_news()` in web_search.py already learned: DDG is
    free and unmetered, grounding is neither. `grounded_fallback=False` lets the
    research engine spend that quota once per *question* instead of once per
    query — a deep run issues fourteen queries, and fourteen grounded calls
    would drain a quota the user needs for ordinary searches."""
    results = ddg(query, max_results=max_results)
    if not results and grounded_fallback:
        results = grounded(query)
    return rank(results, max_results)


def search_many(queries: list[str], per_query: int = 5,
                max_workers: int = 3) -> list[dict]:
    """Several queries at once, de-duplicated across them."""
    queries = [q.strip() for q in queries if str(q or "").strip()][:8]
    if not queries:
        return []
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(queries))) as pool:
        for batch in pool.map(lambda q: search(q, per_query), queries):
            out.extend(batch)
    return rank(out, per_query * max(1, len(queries)))
