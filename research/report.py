"""
Turning the pieces into a document someone can read and check.

Three jobs, in this order:

CITATIONS ARE VALIDATED.  The writer is told to cite `[3]`; a model under
pressure will cite `[12]` in a report with nine sources, or invent `[4][5]` where
the notes only carry `[4]`. Every marker is parsed, ranges are expanded, and a
number that does not exist is removed from the text rather than silently left to
point at nothing. A report that cites a source that isn't there is worse than one
that cites fewer.

THE STRUCTURE IS OURS, NOT THE MODEL'S.  Header, TL;DR, sections, limits,
sources, method. The writer writes prose; it does not get to decide that this
report has no source list.

THE LANGUAGE IS THE USER'S.  Labels follow the language the planner detected,
not the language this file was written in.
"""
from __future__ import annotations

import re
from datetime import datetime

_LABELS = {
    "fr": {
        "tldr": "En bref", "sources": "Sources", "limits": "Contradictions et limites",
        "open": "Ce qui reste ouvert", "method": "Méthode", "accessed": "consulté le",
        "confidence": "Confiance dans les preuves",
        "no_sources": "Aucune source consultable n'a été trouvée.",
        "agents": "sous-agents", "round": "tour", "rounds": "tours",
        "page": "page lue", "pages": "pages lues", "source": "source",
        "sources_word": "sources",
        "skills": "compétences appliquées", "duration": "durée",
        "no_page": "pas de page citable", "unread": "page non lisible, résumé seul",
        "pdf": "PDF non extrait, résumé seul",
    },
    "en": {
        "tldr": "TL;DR", "sources": "Sources", "limits": "Contradictions and limits",
        "open": "What remains open", "method": "Method", "accessed": "accessed",
        "confidence": "Confidence in the evidence",
        "no_sources": "No citable source was found.",
        "agents": "sub-agents", "round": "round", "rounds": "rounds",
        "page": "page read", "pages": "pages read", "source": "source",
        "sources_word": "sources",
        "skills": "skills applied", "duration": "duration",
        "no_page": "no citable page", "unread": "page unreadable, abstract only",
        "pdf": "PDF not extracted, abstract only",
    },
}


def labels(language: str) -> dict:
    lang = (language or "").lower()
    return _LABELS["fr"] if lang.startswith("fr") else _LABELS["en"]


def sanitise_citations(text: str, max_n: int) -> tuple[str, dict]:
    """Keep only citation numbers that exist. Returns `(text, stats)`.

    Ranges (`[1-3]`) are expanded because a writer that means three sources
    should not produce one marker the reader cannot follow."""
    stats = {"kept": 0, "dropped": []}
    if max_n <= 0:
        return text, stats

    def repl(match: re.Match) -> str:
        inner = match.group(1)
        nums: list[int] = []
        for token in re.split(r"[,;]", inner):
            token = token.strip()
            if not token:
                continue
            rng = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", token)
            if rng:
                a, b = int(rng.group(1)), int(rng.group(2))
                if a <= b and b - a <= 12:
                    nums.extend(range(a, b + 1))
                continue
            if token.isdigit():
                nums.append(int(token))
        keep = []
        for n in nums:
            if 1 <= n <= max_n:
                if n not in keep:
                    keep.append(n)
            elif n not in stats["dropped"]:
                stats["dropped"].append(n)
        if not keep:
            return ""
        stats["kept"] += len(keep)
        return "".join(f"[{n}]" for n in keep)

    # One or two digits only: `[2024]` is a year in a sentence, not a citation,
    # and eating it would damage the prose this function exists to protect.
    pattern = r"\[([0-9]{1,2}(?:[,;\s\-–]+[0-9]{1,2})*)\]"
    return re.sub(pattern, repl, text or ""), stats


def _strip_loose_headings(text: str) -> str:
    """Remove a heading the writer added, and any Sources section of its own."""
    text = re.sub(r"^\s*#{1,6}\s+.+\n", "", text or "", count=1)
    text = re.split(r"\n#{1,3}\s*(?:Sources|Références|References)\s*\n",
                    text, maxsplit=1)[0]
    return text.strip()


def _source_line(src: dict, lang: str) -> str:
    """One source, with the reason it is weaker when it is.

    The raw fetch error stays in run.json. A reader needs to know *that* a page
    was not read — not which internal branch refused it."""
    lab = labels(lang)
    title = (src.get("title") or src.get("url") or "Source").strip()
    title = re.sub(r"\s+", " ", title)[:160]
    url = (src.get("url") or "").strip()
    date = (src.get("fetched_at") or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    notes = []
    if not url:
        notes.append(lab["no_page"])
    elif not src.get("chars"):
        error = str(src.get("error") or "").lower()
        notes.append(lab["pdf"] if "pdf" in error else lab["unread"])
    suffix = f" — {lab['accessed']} {date}" if url else ""
    if notes:
        suffix += f" ({'; '.join(notes)})"
    if url:
        return f"{src.get('n', 0)}. [{title}]({url}){suffix}"
    return f"{src.get('n', 0)}. {title}{suffix}"


def render(run, sections: list[tuple[str, str]], meta: dict | None = None) -> str:
    """Assemble the final Markdown. `sections` is `[(heading, prose), …]`."""
    meta = meta or {}
    lang = (run.outline or {}).get("language") or run.language or "en"
    lab = labels(lang)
    max_n = max((int(s.get("n", 0)) for s in run.sources), default=0)

    outline = run.outline or {}
    title = (outline.get("title") or run.title or run.topic).strip()
    thesis = (outline.get("thesis") or "").strip()

    stats = {"kept": 0, "dropped": []}
    tldr: list[str] = []
    for raw in (outline.get("tldr") or []):
        item = str(raw).strip()
        if not item:
            continue
        item, st = sanitise_citations(item, max_n)
        stats["kept"] += st["kept"]
        stats["dropped"] += [n for n in st["dropped"] if n not in stats["dropped"]]
        tldr.append(item)
    if thesis:
        thesis, st = sanitise_citations(thesis, max_n)
        stats["kept"] += st["kept"]
        stats["dropped"] += [n for n in st["dropped"] if n not in stats["dropped"]]

    clean_sections = []
    for heading, prose in sections:
        body = _strip_loose_headings(prose)
        body, st = sanitise_citations(body, max_n)
        stats["kept"] += st["kept"]
        stats["dropped"] += [n for n in st["dropped"] if n not in stats["dropped"]]
        if body.strip():
            clean_sections.append((heading.strip(), body.strip()))

    head = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        f"topic: {run.topic}",
        f"depth: {run.depth}",
        f"sources: {len(run.sources)}",
        f"confidence: {(outline.get('confidence') or 'unknown')}",
        f"agents: {', '.join(meta.get('agents') or []) or 'researcher, analyst, writer'}",
        f"skills: {', '.join(run.skills or []) or 'none'}",
        "tags: [research]",
        "---",
        "",
        f"# {title}",
        "",
    ]
    if thesis:
        head += [f"> **{lab['tldr']}** — {thesis}", ""]
    if tldr:
        head += [f"- {item}" for item in tldr[:6]]
        head.append("")

    body_lines = list(head)
    for heading, prose in clean_sections:
        body_lines += [f"## {heading}", "", prose, ""]

    contradictions = outline.get("contradictions") or []
    gaps = [str(g) for g in (outline.get("gaps") or []) if str(g).strip()]
    if contradictions or gaps:
        body_lines += [f"## {lab['limits']}", ""]
        for c in contradictions[:12]:
            a = str(c.get("claim_a") or "").strip()
            b = str(c.get("claim_b") or "").strip()
            note = str(c.get("note") or "").strip()
            nums = "".join(f"[{int(n)}]" for n in (c.get("sources") or [])
                           if isinstance(n, (int, str)) and str(n).isdigit()
                           and 1 <= int(n) <= max_n)
            if a and b:
                body_lines.append(f"- **{a}** / **{b}** {nums} — {note}".rstrip(" —"))
        if gaps:
            body_lines.append("")
            body_lines.append(f"### {lab['open']}")
            body_lines += [f"- {g}" for g in gaps[:8]]
        body_lines.append("")

    body_lines += [f"## {lab['sources']}", ""]
    if run.sources:
        body_lines += [_source_line(s, lang) for s in
                       sorted(run.sources, key=lambda s: int(s.get("n", 0)))]
    else:
        body_lines.append(lab["no_sources"])
    body_lines.append("")

    agents = meta.get("agents") or ["researcher", "analyst", "writer"]
    rounds = int(meta.get("rounds", 1) or 1)
    read = sum(1 for s in run.sources if s.get("chars"))
    n_sources = len(run.sources)
    method = (
        f"{len(agents)} {lab['agents']} ({', '.join(agents)}), "
        f"{rounds} {lab['round'] if rounds == 1 else lab['rounds']}, "
        f"{n_sources} {lab['source'] if n_sources == 1 else lab['sources_word']}, "
        f"{read} {lab['page'] if read == 1 else lab['pages']}"
    )
    if run.skills:
        method += f", {lab['skills']}: {', '.join(run.skills)}"
    if run.duration_s:
        method += f", {lab['duration']} {int(run.duration_s // 60)}m{int(run.duration_s % 60):02d}"
    if stats["dropped"]:
        method += (f". {len(stats['dropped'])} citation(s) invalide(s) retirée(s) "
                   f"({', '.join(str(n) for n in stats['dropped'][:8])})") if lang.startswith("fr") else \
                  (f". {len(stats['dropped'])} invalid citation(s) removed "
                   f"({', '.join(str(n) for n in stats['dropped'][:8])})")
    body_lines += [f"## {lab['method']}", "", method, ""]

    return "\n".join(body_lines).strip() + "\n"
