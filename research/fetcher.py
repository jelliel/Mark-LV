"""
Reading one page, safely and without a browser.

DeerFlow gives its readers fetch tools — Jina, Firecrawl, Tavily, Browserless,
Crawl4AI — and every one of them is a hosted service with a key. The pitch of
this app is that a research run costs nothing beyond the Gemini key the user
already has, so the fetcher is `requests` plus `BeautifulSoup`, both already
installed.

What that buys and what it costs:

  BUYS    full article text instead of the 200-character snippet a search
          engine hands back, which is the difference between a report that cites
          a page and one that cites a headline.
  COSTS   no JavaScript. A page that renders its body client-side comes back
          empty. The engine treats an empty fetch as "abstract only" and passes
          the search snippet instead, so the source degrades rather than
          disappearing.

SSRF policy: only http(s), and only hosts that resolve entirely to public
addresses. A model that is talked into fetching `http://127.0.0.1:8000/...`
should not be able to read the machine it is running on.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from .util import clip, iso_now

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Theologicus-Research/1.0")
MAX_BYTES = 2_500_000
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan")


@dataclass
class Page:
    url: str
    final_url: str = ""
    title: str = ""
    text: str = ""
    status: int = 0
    content_type: str = ""
    fetched_at: str = ""
    error: str = ""
    truncated: bool = field(default=False)

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error

    def as_source(self, n: int, snippet: str = "") -> dict:
        return {
            "n": n,
            "url": self.final_url or self.url,
            "requested": self.url,
            "title": self.title or (snippet[:120] if snippet else self.url),
            "chars": len(self.text),
            "error": self.error,
            "fetched_at": self.fetched_at,
            "snippet": snippet[:400],
        }


def _public_ip(ip: ipaddress._BaseAddress) -> bool:
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def public_url_error(url: str) -> str:
    """`""` when the URL may be fetched, otherwise the reason it may not.

    DNS is resolved here rather than left to requests so a hostname pointing at
    a private address is refused before a socket is opened."""
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return "unparseable URL"
    if parsed.scheme not in ("http", "https"):
        return "only http(s) URLs are fetched"
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "no host in URL"
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        return "private host is not fetched"
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    candidates = [literal] if literal else []
    if not candidates:
        try:
            for info in socket.getaddrinfo(host, None):
                addr = str(info[4][0]).split("%")[0]
                try:
                    candidates.append(ipaddress.ip_address(addr))
                except ValueError:
                    continue
        except OSError as e:
            return f"DNS lookup failed ({e})"
    if not candidates:
        return "host did not resolve"
    if any(not _public_ip(ip) for ip in candidates):
        return "host resolves to a private address"
    return ""


def normalise_url(url: str) -> str:
    """Drop the fragment, the trailing slash and the default port, so two links
    to the same page are counted as one source."""
    try:
        p = urlparse((url or "").strip())
    except Exception:
        return url or ""
    if not p.netloc:
        return url or ""
    netloc = p.netloc.lower()
    if netloc.endswith(":80") and p.scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and p.scheme == "https":
        netloc = netloc[:-4]
    path = re.sub(r"/{2,}", "/", p.path).rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), netloc, path, "", p.query, ""))


_NOISE_TAGS = ("script", "style", "noscript", "nav", "footer", "header", "aside",
               "form", "svg", "iframe", "button", "select", "option", "canvas",
               "video", "audio", "dialog", "template")
_NOISE_LINES = re.compile(
    r"^(accept (all|necessary)|cookie(s)?( policy| settings)?|subscribe|sign in|"
    r"log in|advertisement|share (this|on)|jump to (content|navigation)|"
    r"menu|search|skip to content)\b", re.I)
_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "blockquote", "pre", "td",
               "figcaption")


def html_to_text(html: str) -> tuple[str, str]:
    """`(title, text)` from a page, in reading order.

    Boilerplate is removed by tag rather than by heuristics, because a
    heuristic that drops short lines also drops "No." — the most useful line on
    a statistics page."""
    try:
        from bs4 import BeautifulSoup
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html or "")
        return "", " ".join(text.split())

    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    main = soup.find("article") or soup.find("main") or soup.body or soup
    parts: list[str] = []
    seen: set[str] = set()
    for el in main.find_all(_BLOCK_TAGS):
        # A <p> inside an <li> would otherwise appear once as the item and once
        # as the paragraph. The list item is the better rendering.
        if el.name in ("p", "blockquote") and el.find_parent(("li", "blockquote")):
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text or len(text) < 12:
            continue
        if _NOISE_LINES.match(text):
            continue
        key = text.lower()[:160]
        if key in seen:
            continue
        seen.add(key)
        if el.name in ("h1", "h2", "h3", "h4"):
            parts.append("## " + text)
        elif el.name == "li":
            parts.append("- " + text)
        elif el.name == "blockquote":
            parts.append("> " + text)
        elif el.name == "pre":
            parts.append("```\n" + text[:1200] + "\n```")
        else:
            parts.append(text)
    text = "\n\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title.strip(), text


def fetch(url: str, timeout: float = 12.0, max_chars: int = 4000,
          session=None) -> Page:
    """Download and flatten one page. Never raises; the error travels in the
    Page so the caller can decide whether a snippet is enough."""
    import requests

    reason = public_url_error(url)
    if reason:
        return Page(url=url, error=reason, fetched_at=iso_now())

    sess = session or requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,fr;q=0.8,*;q=0.5",
    }
    try:
        with sess.get(url, headers=headers, timeout=(6, timeout), stream=True,
                      allow_redirects=True) as resp:
            status = resp.status_code
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if status >= 400:
                return Page(url=url, status=status, content_type=ctype,
                            error=f"HTTP {status}", fetched_at=iso_now())
            if ctype and not (ctype.startswith("text/") or ctype in
                              ("application/xhtml+xml", "application/json",
                               "application/xml")):
                return Page(url=url, status=status, content_type=ctype,
                            error=f"unsupported content type: {ctype}",
                            fetched_at=iso_now())
            raw = bytearray()
            for chunk in resp.iter_content(65536):
                raw.extend(chunk)
                if len(raw) >= MAX_BYTES:
                    break
            encoding = resp.encoding or resp.apparent_encoding or "utf-8"
            body = bytes(raw).decode(encoding, errors="replace")
            final = str(resp.url)
    except Exception as e:
        return Page(url=url, error=f"{type(e).__name__}: {e}",
                    fetched_at=iso_now())

    looks_html = "html" in ctype or body.lstrip()[:15].lower().startswith(
        ("<!doctype", "<html"))
    if looks_html:
        title, text = html_to_text(body)
    else:
        title, text = "", re.sub(r"\s+", " ", body).strip()

    clipped = clip(text, max_chars)
    return Page(url=url, final_url=final, title=title, text=clipped,
                status=status, content_type=ctype,
                fetched_at=iso_now(), truncated=len(clipped) < len(text),
                error="" if clipped else "page had no readable text")
