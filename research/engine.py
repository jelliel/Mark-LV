"""
The loop: plan, read, reconcile, check, write.

Shape of a run — the same five stages DeerFlow's graph encodes, in one thread
pool instead of LangGraph:

    1  plan      the topic becomes 3-7 sub-questions, each with search queries,
                 plus the skills that should govern this run
    2  research  per round: search in parallel → allocate a global source
                 number per URL → fetch in parallel → one reader per question
    3  analyse   notes become one outline: claims, sources, contradictions,
                 gaps, confidence
    4  critique  (deep runs) claims are checked against the evidence and
                 corrected before they can be polished
    5  read      (theological runs) what the outline holds is said as a
                 reading: subject, each item in its authority, each with its
                 weight marked — checked before it is spoken or filed
    6  write     one call per section, so a long report never depends on a
                 single model reply arriving intact

Three decisions worth defending:

GLOBAL SOURCE NUMBERS.  Sources are numbered once, in the coordinator, before
anyone reads them. A reader cannot invent `[7]` because the page it read is
`[7]`; a section writer cannot cite a source the run never fetched, because the
report module strips the marker. Citation integrity is structural, not a
request in a prompt.

TWO PHASES PER ROUND.  Search first, then allocate, then fetch. It looks like an
extra step and it is what makes numbering honest: fetch-on-demand inside each
reader thread would give two readers the same page under two numbers and the
report would cite one page twice.

GAPS DRIVE THE NEXT ROUND.  Round two is not "search again". It is the analyst's
own list of unanswered questions, capped at three. If the first round answered
everything, the run stops early and says so — the budget is spent on what is
missing, not on repetition.
"""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from . import config, llm, reading as reading_mod, report as report_mod
from . import search as search_mod
from . import skills as skills_mod, store, subagents as subagents_mod
from .fetcher import fetch as default_fetch, normalise_url
from .util import clip

DEPTHS: dict[str, dict] = {
    "quick": {"questions": 3, "per_question": 2, "rounds": 1, "budget": 8,
              "critic": False, "parallel": 3, "note_chars": 2200},
    "standard": {"questions": 5, "per_question": 3, "rounds": 2, "budget": 18,
                 "critic": False, "parallel": 4, "note_chars": 2800},
    "deep": {"questions": 7, "per_question": 4, "rounds": 3, "budget": 30,
             "critic": True, "parallel": 5, "note_chars": 3200},
}

_TODAY = "%Y-%m-%d"


class Cancelled(Exception):
    """Raised between stages and between pages, never inside a request."""


@dataclass
class Deps:
    """Everything the engine touches outside itself — injected so the tests can
    drive a whole run without a network or a model."""
    ask: Callable = llm.ask
    ask_json: Callable = llm.ask_json
    search: Callable = search_mod.search
    fetch: Callable = default_fetch
    available: Callable = llm.available


def _normalise_plan(data, topic: str, language: str) -> dict:
    """Coerce whatever the planner returned into the shape the engine needs.

    A model that answers with a bare list of questions, or with `queries` as a
    single string, is not a failure — it is a plan in a different jacket."""
    plan = data if isinstance(data, dict) else {}
    questions = []
    raw_questions = plan.get("sub_questions") or plan.get("questions") or []
    if isinstance(raw_questions, str):
        raw_questions = [raw_questions]
    for item in raw_questions:
        if isinstance(item, str):
            q, queries = item.strip(), [item.strip()]
        elif isinstance(item, dict):
            q = str(item.get("question") or item.get("q") or "").strip()
            raw_q = item.get("queries") or item.get("query") or []
            if isinstance(raw_q, str):
                raw_q = [raw_q]
            queries = [str(x).strip() for x in raw_q if str(x).strip()]
        else:
            continue
        if not q:
            continue
        questions.append({"question": q, "queries": (queries or [q])[:3]})

    if not questions:
        questions = _fallback_questions(topic)

    detected = str(plan.get("language") or "").strip().lower()[:2]
    if language and language != "auto":
        detected = language.lower()[:2]
    if not re.fullmatch(r"[a-z]{2}", detected or ""):
        detected = _guess_language(topic)

    picked_skills = []
    for item in plan.get("skills") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if str(name or "").strip():
            picked_skills.append(str(name).strip().lower())

    return {
        "title": str(plan.get("title") or topic).strip()[:160],
        "objective": str(plan.get("objective") or "").strip(),
        "sub_questions": questions[:10],
        "skills": picked_skills[:4],
        "language": detected,
        "keywords": [str(k) for k in (plan.get("keywords") or [])][:12],
    }


def _fallback_questions(topic: str) -> list[dict]:
    """When the planner is unreachable, a generic but real set of questions.

    Every one of these is answerable by a search, which is the only property
    that matters here: a run with a mediocre plan still produces a cited
    report, and a run with no plan produces nothing."""
    base = topic.strip().rstrip("?.")
    return [
        {"question": f"What is {base} and what does the term cover?",
         "queries": [base]},
        {"question": f"What is the current state of {base}?",
         "queries": [f"{base} 2026", f"{base} latest developments"]},
        {"question": f"What evidence and figures exist about {base}?",
         "queries": [f"{base} data statistics", f"{base} study"]},
        {"question": f"What are the main criticisms and limits of {base}?",
         "queries": [f"{base} criticism", f"{base} limitations risks"]},
        {"question": f"How does {base} compare with the alternatives?",
         "queries": [f"{base} vs alternatives", f"{base} comparison"]},
    ]


def _guess_language(text: str) -> str:
    """Two-letter guess from the words a topic is actually made of.

    Not a language detector: enough to pick "fr" over "en" for labels when the
    model did not say, using the words that differ most between the two."""
    words = set(re.findall(r"[a-zà-ÿ']+", (text or "").lower()))
    french = {"le", "la", "les", "des", "du", "de", "et", "en", "un", "une",
              "pour", "sur", "dans", "quel", "quelle", "est", "sont", "avec",
              "entre", "théologie", "église", "histoire"}
    hits = len(words & french)
    return "fr" if hits >= 2 else "en"


class ResearchEngine:
    def __init__(self, run: store.Run, deps: Deps | None = None,
                 cancel: threading.Event | None = None,
                 on_event: Callable[[str, str], None] | None = None):
        self.rec = run
        self.deps = deps or Deps()
        self.cancel = cancel or threading.Event()
        self.on_event = on_event
        self.settings = DEPTHS.get(run.depth) or DEPTHS["standard"]
        self.max_parallel = int(config.setting("research_max_parallel")
                                or self.settings["parallel"])
        self.max_chars = int(config.setting("research_max_page_chars") or 4000)
        self.skills = skills_mod.discover()
        self.agents = subagents_mod.discover()
        self._t0 = time.monotonic()

    # ── plumbing ─────────────────────────────────────────────────────────────
    def _save(self) -> None:
        try:
            store.save(self.rec)
        except Exception as e:
            print(f"[Research] could not save run: {e}")

    def _event(self, stage: str, message: str) -> None:
        self.rec.stage = message
        self.rec.add_event(stage, message)
        self._save()
        if self.on_event:
            try:
                self.on_event(stage, message)
            except Exception as e:
                print(f"[Research] progress callback failed: {e}")

    def _check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()

    def _call(self, agent_name: str, prompt: str, tier: str = "", timeout: int = 90_000,
              json_mode: bool = False):
        agent = subagents_mod.resolve(agent_name, self.agents)
        if json_mode:
            return self.deps.ask_json(prompt, tier=tier, timeout_ms=timeout,
                                      system=agent.system)
        return self.deps.ask(prompt, tier=tier, timeout_ms=timeout,
                             system=agent.system)

    # ── stage 1: plan ────────────────────────────────────────────────────────
    def _plan(self) -> None:
        self.rec.set_stage("planning", "planning")
        self._event("planning", "Planning the research")
        requested = [str(s).strip().lower() for s in
                     (self.rec.plan.get("requested_skills") or []) if str(s).strip()]
        catalog = skills_mod.catalog(self.skills)
        prompt = f"""Plan a research run. Today is {time.strftime(_TODAY)}.

TOPIC: {self.rec.topic}
DEPTH: {self.rec.depth} — {self.settings['questions']} sub-questions, about \
{self.settings['per_question']} pages each, {self.settings['rounds']} round(s).

Return JSON only:
{{
  "title": "a specific report title",
  "objective": "one sentence on what this run must settle",
  "language": "two-letter code of the language the report should be written in",
  "keywords": ["terms a search engine should use"],
  "sub_questions": [
    {{"question": "...", "queries": ["search query", "second query"]}}
  ],
  "skills": ["names chosen from the catalogue below"]
}}

Rules:
- Each sub-question must be answerable from public pages. No "interview experts".
- Queries are what a person would type into a search engine, in the language of \
the sources: short, no quotes, no boolean operators, no site: filters unless the \
topic names a site.
- Cover the topic from different angles: definition and scope, current state, \
evidence and numbers, criticism and limits, and alternatives or comparison. \
Skip an angle only when it is meaningless for this topic.
- {self.settings['questions']} sub-questions, at most 3 queries each.
- Choose 1-3 skills only where they genuinely change how this topic is judged. \
An empty list is a valid answer.

SKILL CATALOGUE
{catalog or '(none installed)'}"""
        data = self._call("planner", prompt, json_mode=True, timeout=120_000)
        plan = _normalise_plan(data, self.rec.topic, self.rec.language)

        chosen = skills_mod.resolve(requested + plan["skills"], self.skills)
        if not chosen and len(plan["sub_questions"]) > 1:
            # A report with claims but no sourcing discipline is the failure
            # mode of every generated research summary; this one is not optional.
            chosen = skills_mod.resolve(["sourced-brief"], self.skills)

        self.rec.plan = {**plan, "requested_skills": requested,
                         "rounds": self.settings["rounds"],
                         "budget": self.settings["budget"]}
        self.rec.title = plan["title"]
        self.rec.language = plan["language"]
        self.rec.skills = [s.name for s in chosen]
        self._skills_picked = chosen
        self.rec.agents = ["planner", "researcher", "analyst", "writer"]
        if self.settings["critic"]:
            self.rec.agents.append("critic")
        self._save()
        self._event("planning",
                    f"Plan ready: {len(plan['sub_questions'])} questions, "
                    f"{self.settings['rounds']} round(s), language {plan['language']}")

    # ── stage 2: research ────────────────────────────────────────────────────
    def _research(self, questions: list[dict], round_no: int) -> None:
        per_q = self.settings["per_question"]
        budget = self.settings["budget"]
        remaining = max(0, budget - len(self.rec.sources))
        if remaining <= 0:
            self._event("researching", "Source budget already spent — skipping round")
            return
        self.rec.set_stage("researching", f"round {round_no}")
        self._event("researching",
                    f"Round {round_no}: searching {len(questions)} questions")

        # ---- search (parallel) ----
        def find(question: dict) -> tuple[dict, list[dict]]:
            queries = question["queries"][:2] or [question["question"]]
            found: list[dict] = []
            for query in queries:
                self._check()
                # No per-query grounded fallback: one grounded call per question
                # that found nothing, below, instead of one per query.
                found.extend(self.deps.search(query, max_results=6,
                                              grounded_fallback=False))
            if not found:
                self._check()
                found.extend(self.deps.search(question["question"], max_results=6))
            return question, search_mod.rank(found, per_q * 3)

        candidates: list[tuple[dict, list[dict]]] = []
        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            for question, found in pool.map(find, questions):
                candidates.append((question, found))

        # ---- allocate global source numbers ----
        seen = {normalise_url(u) for u in self.rec.seen_urls if u}
        allocated: list[dict] = []
        for question, found in candidates:
            taken = 0
            for cand in found:
                if taken >= per_q or len(allocated) >= remaining:
                    break
                url = normalise_url(cand.get("url") or "")
                if url and url in seen:
                    continue
                if not url and not (cand.get("snippet") or "").strip():
                    continue
                if url:
                    seen.add(url)
                    self.rec.seen_urls.append(url)
                allocated.append({"question": question, "candidate": cand,
                                  "url": url, "n": len(self.rec.sources) + len(allocated) + 1})
                taken += 1
        if not allocated:
            self._event("researching", f"Round {round_no}: no new pages found")
            return
        self._event("researching",
                    f"Round {round_no}: reading {len(allocated)} pages")

        # ---- fetch (parallel) ----
        def pull(item: dict):
            if not item["url"]:
                return item, None            # a grounded answer has no page to pull
            try:
                return item, self.deps.fetch(item["url"], max_chars=self.max_chars,
                                             timeout=12)
            except Exception as e:
                print(f"[Research] fetch failed: {type(e).__name__}: {e}")
                return item, None

        fetched: dict[int, object] = {}
        with ThreadPoolExecutor(max_workers=min(6, len(allocated))) as pool:
            for item, page in pool.map(pull, allocated):
                self._check()
                fetched[item["n"]] = page

        # ---- register sources in main thread, in allocation order ----
        by_question: dict[str, list[dict]] = {}
        for item in allocated:
            self._check()
            page = fetched.get(item["n"])
            cand = item["candidate"]
            n = item["n"]
            snippet = (cand.get("snippet") or "").strip()
            if page is not None and getattr(page, "text", ""):
                source = page.as_source(n, snippet)
                text = page.text
                store.cache_page(self.rec, n, text)
            else:
                err = getattr(page, "error", "") or ("no URL to fetch" if not item["url"] else "")
                source = {"n": n, "url": item["url"], "requested": item["url"],
                          "title": cand.get("title") or f"Source {n}",
                          "chars": 0, "error": err,
                          "fetched_at": "", "snippet": snippet}
                text = ""
            self.rec.sources.append(source)
            self._save()
            by_question.setdefault(item["question"]["question"], []).append(
                {"n": n, "source": source, "text": text, "snippet": snippet})

        # ---- readers (parallel) ----
        plan_bits = json.dumps({"title": self.rec.plan.get("title"),
                                "objective": self.rec.plan.get("objective")},
                               ensure_ascii=False)

        def read(question: dict):
            group = by_question.get(question["question"]) or []
            if not group:
                return question, ""
            blocks = []
            for entry in group:
                src = entry["source"]
                body = clip(entry["text"], self.max_chars) if entry["text"] else \
                    f"(page could not be read; search abstract only)\n{entry['snippet']}"
                blocks.append(f"[{entry['n']}] {src.get('title')} — {src.get('url')}\n{body}")
            prompt = f"""PLAN: {plan_bits}

QUESTION: {question['question']}
ROUND: {round_no}

NUMBERED EXCERPTS (the only evidence you may cite):
{chr(10).join(blocks)}"""
            return question, self._call("researcher", prompt, timeout=120_000) or ""

        notes_written = 0
        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            for question, note in pool.map(read, questions):
                self._check()
                if not note.strip():
                    continue
                note = clip(note.strip(), self.settings["note_chars"])
                store.save_note(self.rec, f"r{round_no}-q{notes_written + 1}",
                                "researcher", question["question"], note)
                notes_written += 1
        self._save()
        self._event("researching",
                    f"Round {round_no} done: {notes_written} notes, "
                    f"{len(self.rec.sources)} sources read")

    def _research_rounds(self) -> None:
        questions = (self.rec.plan.get("sub_questions") or [])
        outline: dict = {}
        rounds = max(1, int(self.rec.plan.get("rounds") or 1))
        for round_no in range(1, rounds + 1):
            self._check()
            self._research(questions, round_no)
            outline = self._analyse(save=True)
            gaps = [str(g).strip() for g in (outline.get("gaps") or [])
                    if str(g).strip()][:3]
            if round_no >= rounds or not gaps:
                if round_no < rounds and not gaps:
                    self._event("analysing", "No open questions left — stopping early")
                break
            questions = [{"question": gap, "queries": [gap]} for gap in gaps]
            self._event("researching", f"Round {round_no + 1}: following up on "
                                       f"{len(questions)} open question(s)")
        if outline:
            self.rec.outline = outline

    # ── stage 3: analyse ─────────────────────────────────────────────────────
    def _analyse(self, save: bool = True) -> dict:
        self.rec.set_stage("analysing", "analysing")
        notes = store.read_notes(self.rec)
        if not notes:
            return self._fallback_outline([])
        self._event("analysing", f"Reconciling {len(notes)} notes")
        budget = 24_000
        chunks, used = [], 0
        for meta in notes:
            text = meta.get("text") or ""
            share = max(1200, budget // max(1, len(notes)))
            piece = clip(text, share)
            if used + len(piece) > budget:
                piece = clip(piece, max(600, budget - used))
            if not piece:
                break
            used += len(piece)
            chunks.append(f"NOTE — {meta.get('question')}\n{piece}")
        sources = "\n".join(
            f"[{s.get('n')}] {s.get('title')} — {s.get('url') or '(no citable page)'}"
            for s in self.rec.sources)
        prompt = f"""TOPIC: {self.rec.topic}
OBJECTIVE: {self.rec.plan.get('objective') or 'answer the topic'}

SOURCES
{sources}

NOTES
{chr(10).join(chunks)}"""
        outline = self._call("analyst", prompt, json_mode=True, timeout=120_000)
        outline = self._normalise_outline(outline)
        # The analyst's title is the one the report carries, so it is also the
        # one a status line and the spoken announcement should use.
        self.rec.title = outline.get("title") or self.rec.title
        if save:
            self.rec.outline = outline
            self._save()
        return outline

    def _normalise_outline(self, data) -> dict:
        if not isinstance(data, dict):
            print("[Research] analyst returned no usable outline — using the notes")
            fallback = self._fallback_outline(store.read_notes(self.rec))
            fallback["language"] = self.rec.language
            return fallback
        max_n = max((int(s.get("n", 0)) for s in self.rec.sources), default=0)

        def nums(values):
            out = []
            for v in values or []:
                try:
                    n = int(v)
                except (TypeError, ValueError):
                    continue
                if 1 <= n <= max_n and n not in out:
                    out.append(n)
            return out

        sections = []
        for sec in data.get("sections") or []:
            if not isinstance(sec, dict):
                continue
            heading = str(sec.get("heading") or "").strip()
            claims = [str(c).strip() for c in (sec.get("claims") or []) if str(c).strip()]
            if not heading or not claims:
                continue
            evidence = [str(e).strip() for e in (sec.get("evidence") or [])
                        if str(e).strip()]
            sections.append({"heading": heading, "claims": claims[:6],
                             "sources": nums(sec.get("sources")),
                             "evidence": evidence[:4]})
        if not sections:
            fallback = self._fallback_outline(store.read_notes(self.rec))
            sections = fallback["sections"]

        contradictions = []
        for item in data.get("contradictions") or []:
            if not isinstance(item, dict):
                continue
            contradictions.append({
                "claim_a": str(item.get("claim_a") or "").strip()[:240],
                "claim_b": str(item.get("claim_b") or "").strip()[:240],
                "sources": nums(item.get("sources")),
                "note": str(item.get("note") or "").strip()[:300]})

        confidence = str(data.get("confidence") or "unknown").strip().lower()
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        return {
            "title": str(data.get("title") or self.rec.title or self.rec.topic).strip(),
            "thesis": str(data.get("thesis") or "").strip(),
            "tldr": [str(x).strip() for x in (data.get("tldr") or []) if str(x).strip()][:6],
            "sections": sections[:7],
            "contradictions": contradictions[:12],
            "gaps": [str(g).strip() for g in (data.get("gaps") or []) if str(g).strip()][:6],
            "confidence": confidence,
            "language": self.rec.language,
        }

    def _fallback_outline(self, notes: list[dict]) -> dict:
        """A report skeleton assembled from the notes themselves.

        This is the answer when the analyst is out of quota: every heading is a
        question a researcher already answered, and every claim is a bullet that
        already carries its citation. Nothing is invented; the confidence is
        marked low because the reconciliation did not happen."""
        sections = []
        for meta in notes:
            text = meta.get("text") or ""
            bullets = re.findall(r"^\s*[-*]\s+(.+)$", text, re.M)
            bullets = [b.strip() for b in bullets if len(b.strip()) > 30][:5]
            if not bullets:
                continue
            sections.append({"heading": str(meta.get("question") or "Findings").strip(),
                             "claims": bullets, "sources": [], "evidence": []})
        if not sections:
            sections = [{"heading": self.rec.topic,
                         "claims": ["No evidence was gathered for this run."],
                         "sources": [], "evidence": []}]
        first_claim = sections[0]["claims"][0] if sections[0]["claims"] else ""
        return {"title": self.rec.topic, "thesis": first_claim,
                "tldr": [s["claims"][0] for s in sections[:4]],
                "sections": sections[:6], "contradictions": [], "gaps": [],
                "confidence": "low", "language": self.rec.language}

    # ── stage 4: critique ────────────────────────────────────────────────────
    def _critique(self) -> None:
        if not self.settings["critic"]:
            return
        self.rec.set_stage("critiquing", "critiquing")
        notes = store.read_notes(self.rec)
        if not notes:
            return
        self._event("critiquing", "Checking claims against their sources")
        evidence = "\n\n".join(f"{m.get('question')}\n{clip(m.get('text') or '', 1800)}"
                               for m in notes)[:20_000]
        outline = {k: self.rec.outline.get(k) for k in
                   ("title", "thesis", "sections", "contradictions", "confidence")}
        prompt = f"""OUTLINE
{json.dumps(outline, ensure_ascii=False, indent=1)}

EVIDENCE (the notes behind it)
{evidence}"""
        result = self._call("critic", prompt, json_mode=True, timeout=90_000)
        if not isinstance(result, dict):
            return
        self.rec.critique = result
        self._apply_critique(result)
        self._save()

    def _apply_critique(self, critique: dict) -> None:
        """Turn the critic's notes into edits.

        A critique that only prints warnings is a second report nobody reads.
        Each issue is matched to the claim it is about and the claim is replaced
        by the corrected sentence; anything unmatched becomes an open question,
        which is where an unresolved doubt belongs."""
        issues = [i for i in (critique.get("issues") or []) if isinstance(i, dict)]
        if not issues:
            return
        sections = self.rec.outline.get("sections") or []
        unmatched = []
        for issue in issues:
            claim = re.sub(r"\W+", " ", str(issue.get("claim") or "").lower()).strip()
            fix = str(issue.get("fix") or "").strip()
            if not claim:
                continue
            target = None
            for sec in sections:
                for i, existing in enumerate(sec.get("claims") or []):
                    words_a = set(claim.split())
                    words_b = set(re.sub(r"\W+", " ", existing.lower()).split())
                    if not words_b:
                        continue
                    overlap = len(words_a & words_b) / max(1, len(words_b))
                    if overlap >= 0.5:
                        target = (sec, i)
                        break
                if target:
                    break
            if target and fix:
                sec, index = target
                sec["claims"][index] = fix
            else:
                unmatched.append(str(issue.get("claim") or "").strip()[:200])
        if unmatched:
            gaps = self.rec.outline.get("gaps") or []
            gaps.extend(f"À vérifier : {c}" if self.rec.language == "fr"
                        else f"To verify: {c}" for c in unmatched[:4])
            self.rec.outline["gaps"] = gaps[:8]
        if str(critique.get("verdict") or "").lower() == "unreliable":
            self.rec.outline["confidence"] = "low"
        self._event("critiquing",
                    f"Critique applied: {len(issues)} issue(s), "
                    f"verdict {critique.get('verdict') or 'unknown'}")

    # ── stage 5: read ───────────────────────────────────────────────────────────────
    def _read(self) -> None:
        """Compose the reading of what this run established, and check it.

        Only for a run the theology discipline governs: the reading names
        authorities that exist in theology alone, and a reading of a market
        report that classified its evidence as "Tradition" would be a category
        error dressed as a summary.

        The composition is one call; the CHECK is this module's, not the
        model's. `reading.validate` drops any item whose authority or weight
        falls outside the closed sets, or whose sources are numbers the run
        never fetched — and drops the whole reading when nothing valid is left.
        A run whose reading will not check still writes its report; it simply
        is not read back theologically, and says so."""
        if not reading_mod.available(self.rec):
            return
        if not (self.rec.outline or {}).get("sections"):
            return
        self.rec.set_stage("reading", "reading")
        self._event("reading", "Reading what the outline holds, in its authorities")
        prompt = reading_mod.prompt(self.rec)
        raw = self._call("theologian", prompt, json_mode=True, timeout=90_000)
        checked = reading_mod.validate(raw, self.rec)
        if not checked:
            print("[Research] the reading did not check out — the report stands on its own")
            self._event("reading", "Reading discarded: it did not check out")
            return
        self.rec.reading = checked
        self._save()
        self._event("reading", f"Reading: {len(checked['items'])} item(s) on "
                               f"« {checked['subject'][:60]} »")

    # ── stage 6: write ───────────────────────────────────────────────────────
    def _write(self) -> None:
        self.rec.set_stage("writing", "writing")
        outline = self.rec.outline
        sections = outline.get("sections") or []
        if not sections:
            self.rec.outline = outline = self._fallback_outline(store.read_notes(self.rec))
            sections = outline["sections"]
        skills_block = skills_mod.prompt_block(getattr(self, "_skills_picked", [])
                                               or skills_mod.resolve(self.rec.skills, self.skills))
        source_lines = "\n".join(
            f"[{s.get('n')}] {s.get('title')} — {s.get('url') or '(no citable page)'}"
            for s in self.rec.sources) or "(no sources)"
        language = self.rec.language or "en"
        written: list[tuple[str, str]] = []
        total = len(sections)
        for index, section in enumerate(sections, 1):
            self._check()
            self._event("writing", f"Writing section {index}/{total}: "
                                   f"{section['heading'][:60]}")
            claims = "\n".join(f"- {c}" for c in section.get("claims") or [])
            evidence = "\n".join(f"- {e}" for e in section.get("evidence") or [])
            used = ", ".join(str(n) for n in (section.get("sources") or [])) or "(any)"
            prompt = f"""TOPIC: {self.rec.plan.get('title') or self.rec.topic}
REPORT THESIS: {outline.get('thesis') or ''}
SECTION: {section['heading']}
CLAIMS TO ESTABLISH
{claims}
EVIDENCE FROM THE NOTES
{evidence or '(none extracted — work from the claims and the source list)'}
SOURCES (numbers you may cite; the section was built from {used})
{source_lines}

{skills_block}

LANGUAGE: {language}"""

            prose = self._call("writer", prompt, timeout=120_000).strip()
            if not prose:
                prose = "\n".join(
                    f"- {c}" for c in section.get("claims") or []) or \
                    "(This section could not be written.)"
            written.append((section["heading"], prose[:9000]))

        self.rec.duration_s = time.monotonic() - self._t0
        markdown = report_mod.render(
            self.rec, written,
            meta={"agents": self.rec.agents,
                  "rounds": int(self.rec.plan.get("rounds") or 1)})
        path = store.write_report(self.rec, markdown)
        self._save()
        self._event("writing", f"Report saved: {path}")

    # ── driver ───────────────────────────────────────────────────────────────
    def run(self) -> store.Run:
        try:
            if not self.deps.available():
                raise RuntimeError("no Gemini API key is configured")
            self._plan()
            self._research_rounds()
            self._check()
            self._critique()
            self._check()
            self._read()
            self._check()
            self._write()
            self.rec.set_stage("done", "done")
            self.rec.duration_s = time.monotonic() - self._t0
            self._save()
            store.remember(self.rec)
            self._event("done", f"Done in {int(self.rec.duration_s)}s — "
                                f"{len(self.rec.sources)} sources")
        except Cancelled:
            self.rec.status = "cancelled"
            self.rec.error = "cancelled by user"
            self.rec.duration_s = time.monotonic() - self._t0
            self._save()
            self._event("cancelled", "Run cancelled")
        except Exception as e:
            self.rec.status = "failed"
            self.rec.error = f"{type(e).__name__}: {e}"
            self.rec.duration_s = time.monotonic() - self._t0
            self._save()
            self._event("failed", self.rec.error)
            print(f"[Research] run failed: {self.rec.error}")
        return self.rec

    def resume(self) -> store.Run:
        """Rebuild the report from notes already on disk — no fetching.

        This is what a failed or cancelled run is worth keeping for: the pages
        were paid for once, and a writer that timed out does not justify reading
        them again."""
        try:
            notes = store.read_notes(self.rec)
            if not notes:
                raise RuntimeError("this run has no notes to resume from")
            self._event("analysing", "Resuming from the notes on disk")
            self.rec.outline = self._analyse(save=True)
            self._critique()
            self._read()
            self._write()
            self.rec.set_stage("done", "done")
            self.rec.error = ""
            self.rec.duration_s = time.monotonic() - self._t0
            self._save()
            store.remember(self.rec)
        except Cancelled:
            self.rec.status = "cancelled"
            self._save()
        except Exception as e:
            self.rec.status = "failed"
            self.rec.error = f"{type(e).__name__}: {e}"
            self._save()
            print(f"[Research] resume failed: {self.rec.error}")
        return self.rec


# ── module-level entry points (what the voice action calls) ─────────────────

def start(topic: str, depth: str = "standard", language: str = "auto",
          requested_skills: list[str] | None = None,
          deps: Deps | None = None, cancel: threading.Event | None = None,
          on_event: Callable[[str, str], None] | None = None) -> tuple[store.Run, ResearchEngine]:
    """Create a run on disk and hand back the engine, unstarted.

    The caller decides whether to run it in a thread (the voice action does) —
    keeping the engine free of thread policy is what lets the tests run it
    synchronously."""
    depth = str(depth or "standard").lower()
    if depth not in DEPTHS:
        depth = "standard"
    run = store.create_run(topic, depth=depth, language=language)
    run.plan = {"requested_skills": list(requested_skills or [])}
    store.save(run)
    engine = ResearchEngine(run, deps=deps, cancel=cancel, on_event=on_event)
    return run, engine


def resume(run_id: str, deps: Deps | None = None,
           on_event: Callable[[str, str], None] | None = None) -> store.Run | None:
    run = store.load_run(run_id)
    if run is None:
        return None
    return ResearchEngine(run, deps=deps, on_event=on_event).resume()
