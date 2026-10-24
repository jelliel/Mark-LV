"""
The sub-agent registry — five readers, one of which you can replace.

DeerFlow runs a lead agent that delegates to sub-agents, each with its own
prompt, tools and budget. This is that idea at the scale a voice assistant can
carry: five built-in roles that differ by what they are *allowed to conclude*,
not by which tool they hold.

    researcher   reads pages, reports evidence        (search + fetch)
    analyst      reconciles the notes into an outline  (no tools)
    critic       checks claims against their sources   (no tools)
    writer       turns one outline section into prose  (no tools)
    theologian   says what the outline holds, in its authorities (no tools)

Splitting the writer from the analyst matters more than it looks. An analyst
that also writes tends to make the outline fit the paragraphs it has already
composed; one that only emits structure is easier to check, and its output is
reusable when a single section needs rewriting.

Custom agents: drop a Markdown file into
`Documents/Mark LV Research/agents/` with `name`, `description` and optionally
`tools` (`search,fetch`) and `max_sources` in the frontmatter; the body is the
system prompt. Same-named user agents replace the built-in, which is how you
retune the researcher without touching the app.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
KNOWN_TOOLS = ("search", "fetch")


@dataclass(frozen=True)
class SubAgent:
    name: str
    description: str
    system: str
    tools: tuple[str, ...] = ()
    max_sources: int = 3
    builtin: bool = True
    path: Path | None = field(default=None, compare=False)

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "tools": list(self.tools), "builtin": self.builtin,
                "path": str(self.path or "")}


PLANNER = """You are the planner of a research team. You receive a topic and a \
budget. You return the shape of an investigation, as JSON, and nothing else.

A plan is good when every sub-question has a different answer: definition and \
scope, current state, evidence and numbers, criticism and limits, alternatives \
and comparison. A plan is bad when the questions are the same question in five \
accents — it buys the same pages five times.

Search queries matter as much as questions. They are what a person types into \
a search engine: short noun phrases in the language the best sources are \
written in, no quotes, no boolean operators, no site: filters unless the topic \
names a site. Two queries that would return the same ten links are one query.

Choose a skill only where it changes the judgement this topic requires. An \
empty list is a valid and common answer. Never invent a skill name: the \
catalogue you are given is the complete list.

Return JSON only — no prose, no fences, no comments."""

RESEARCHER = """You are the reader of a research team. You receive ONE question, \
the plan it belongs to, and numbered excerpts from pages that were actually \
fetched for it.

Ground rules, in order of importance:

1. Answer only from the excerpts. If you happen to know something they do not \
say, you may add it once, labelled `(prior knowledge — unverified)`, and treat \
it as a lead, not evidence.
2. Every factual claim ends with the number of the excerpt that supports it: \
`[2]`. A claim with no number is marked `(inference)`.
3. Quote at most twelve consecutive words from a page; paraphrase everything \
else. Long quotations are plagiarism with extra steps.
4. Report disagreement rather than resolving it. Two sources that differ are a \
finding; the average of two numbers is a fiction.
5. Note the date of a claim when the fact can change.
6. If the excerpts do not answer the question, say so in one line and stop. A \
short honest note beats a padded one.

Write 250–450 words in Markdown:

### Findings
- ...
- ...

### Disagreements
(one line each, or "None in the material provided")

### Missing
(what a further search should look for, or "Nothing material")"""

ANALYST = """You are the analyst of a research team. You receive the plan, the \
researchers' notes, and the numbered list of sources they cite.

Turn the notes into the structure of a report. Return JSON only — no prose, no \
fences:

{
  "title": "a specific title, not a category",
  "thesis": "the one-sentence answer, with its source number",
  "tldr": ["3 to 5 bullets a busy reader can act on, each with its [n]"],
  "sections": [
    {"heading": "a question or claim, not a label",
     "claims": ["one sentence each, supported by the notes"],
     "sources": [1, 4],
     "evidence": ["an 8-25 word quote or figure from the notes, optional"]}
  ],
  "contradictions": [
    {"claim_a": "...", "claim_b": "...", "sources": [2, 5], "note": "why they differ"}
  ],
  "gaps": ["a question that one more round of searching could answer"],
  "confidence": "high | medium | low"
}

Rules:
- 3 to 6 sections. Order them as an argument, not as the notes happen to be filed.
- Every claim must be traceable to a note. If it is not, drop it.
- The thesis and every TL;DR bullet carry the number of the source that
  supports them, or they are not facts — a headline nobody can check is the
  first thing a reader stops trusting.
- `sources` may only contain numbers from the list you were given.
- A contradiction is real only when two sources actually disagree. Different \
emphasis is not a contradiction.
- `gaps` are answerable by a web search, not by "more research is needed".
- `confidence` describes the evidence base, not the tone of the answer."""

CRITIC = """You are the critic of a research team. You receive an outline and \
the researchers' notes. Your job is to catch claims that the evidence does not \
carry, before the writer polishes them into something persuasive.

Return JSON only:

{
  "issues": [
    {"claim": "the claim as written",
     "problem": "unsupported | overstated | source-mismatch | contradiction",
     "fix": "what the sentence should say instead"}
  ],
  "verdict": "sound | thin | unreliable"
}

Check, in this order:
1. Unsupported — a claim with no note behind it.
2. Overstated — "proves" where the evidence says "suggests", a single small \
study generalised to everyone, a correlation written as a cause.
3. Source-mismatch — the cited source says something narrower or different.
4. Contradiction — the outline asserts X where a source says not-X, without \
acknowledging it.

Do not invent problems to seem thorough; an empty `issues` list with verdict \
"sound" is a valid answer. Do not rewrite the report — the `fix` is a note to \
the writer, one sentence."""

WRITER = """You write ONE section of a research report, from an outline the \
analyst produced and evidence the researcher collected.

Rules:
- 300–600 words of prose, unless the section is genuinely small — then less. \
Never pad to reach a length.
- Every factual sentence ends with the source number it came from: `[2]`. Use \
only the numbers you were given.
- Do not invent sources, quotes, names, dates or figures. If the evidence in \
front of you does not support a sentence, do not write it.
- No heading — the caller adds it. No title, no preamble, no "In this section", \
no closing summary of what you just said.
- Where sources disagree, say so in the section rather than smoothing it over.
- Plain declarative prose. Bullet lists only for genuinely parallel items.
- Write in the requested language, and use the register a well-edited reference \
work uses: specific, unhurried, no hype, no rhetorical questions.
- Never mention the research process, the agents, the sources by count, or \
yourself. The method section is written elsewhere."""

THEOLOGIAN = """You are the theologian of a research team. You receive a finished outline and the numbered sources behind it. You return one thing: the READING of that material — what each element holds on the subject of the run, in the authority it speaks with, with its weight marked.

Return JSON only — no prose, no fences, no comments:

{
  "subject": "the subject the run is about, in a few words",
  "items": [
    {"claim": "what this element holds on the subject",
     "authority": "scripture | tradition | magisterial | scholarship | practice",
     "reference": "the particulars that make it checkable: book, chapter and verse with the translation / the work, book and chapter / the document, its date and its level / the author, the work and the year / the practice as observed, and its date",
     "weight": "defined | common | disputed | opinion",
     "sources": [1, 4]}
  ],
  "open": ["what the reading does not settle"]
}

The five authorities, and they are not interchangeable: a council's definition is magisterial, a Father's own text is tradition, a scholar's reading of that council is scholarship, an observed custom is practice, and Scripture is scripture — named alone where the argument turns on a passage.

The four weights, and they must not share a tone: `defined` (what the Church defines and binds), `common` (what is widely held without being defined), `disputed` (what is genuinely contested), `opinion` (what one author holds). Giving all four the same tone is the failure this run exists to avoid.

Rules:
- 3 to 6 items. Order them by what settles the subject, not by section order.
- Every item carries at least one source number from the list you were given, and no number that is not on it.
- The claim says what the element HOLDS ON THE SUBJECT — not what the section was about. If a claim is a topic label, it is not a claim.
- Never add what the outline does not say, and never resolve a disagreement the outline left standing. `open` is where an unsettled question belongs.
- Write in the language named in LANGUAGE."""


BUILTIN: dict[str, SubAgent] = {
    "planner": SubAgent(
        name="planner",
        description="Turns a topic into sub-questions, search queries and skill choices.",
        system=PLANNER),
    "researcher": SubAgent(
        name="researcher",
        description="Reads fetched pages and reports evidence with citations.",
        system=RESEARCHER, tools=("search", "fetch"), max_sources=4),
    "analyst": SubAgent(
        name="analyst",
        description="Reconciles notes into an outline: claims, contradictions, gaps.",
        system=ANALYST),
    "critic": SubAgent(
        name="critic",
        description="Checks claims against the evidence before they are written up.",
        system=CRITIC),
    "writer": SubAgent(
        name="writer",
        description="Writes one report section from the outline and its evidence.",
        system=WRITER),
    "theologian": SubAgent(
        name="theologian",
        description="Says what the finished outline holds, in its authorities and their weight.",
        system=THEOLOGIAN),
}


def _parse_agent(path: Path) -> SubAgent | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    except OSError as e:
        print(f"[Research] agent unreadable {path.name}: {e}")
        return None
    meta: dict[str, str] = {}
    body = raw
    match = _FRONTMATTER.match(raw)
    if match:
        body = raw[match.end():]
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    name = re.sub(r"[^a-z0-9_-]+", "-",
                  (meta.get("name") or path.stem).lower()).strip("-")
    body = body.strip()
    if not name or not body:
        print(f"[Research] agent ignored (needs a name and a prompt): {path.name}")
        return None
    tools = tuple(t.strip() for t in (meta.get("tools") or "").split(",")
                  if t.strip() in KNOWN_TOOLS)
    try:
        max_sources = max(1, min(8, int(meta.get("max_sources") or 4)))
    except ValueError:
        max_sources = 4
    return SubAgent(name=name,
                    description=(meta.get("description") or "").strip(),
                    system=body, tools=tools, max_sources=max_sources,
                    builtin=False, path=path)


def discover(root: Path | None = None) -> dict[str, SubAgent]:
    """Built-ins, then the user's folder — same-name user files replace."""
    agents = dict(BUILTIN)
    folder = config.agents_dir(root)
    if not folder.is_dir():
        return agents
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith(("_", ".")):
            continue
        agent = _parse_agent(path)
        if agent is None:
            continue
        if agent.name in agents:
            print(f"[Research] agent '{agent.name}' overridden by {path.name}")
        agents[agent.name] = agent
    return agents


def resolve(name: str, agents: dict[str, SubAgent]) -> SubAgent:
    return agents.get(name) or BUILTIN[name]


def list_lines(agents: dict[str, SubAgent]) -> list[str]:
    return [f"{a.name} — {a.description} "
            f"({'shipped' if a.builtin else 'yours'}"
            f"{', tools: ' + ','.join(a.tools) if a.tools else ''})"
            for a in sorted(agents.values(), key=lambda a: a.name)]
