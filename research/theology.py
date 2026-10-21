"""
When the vault cannot answer, it goes and finds out — and files the answer.

The theology vault is the first place a theological question should be answered
from: it is local, it is the user's own reading, and it costs nothing. Its
weakness is the same as its strength — it only knows what was put in it. Until
now a miss produced "No wiki page matches", the model improvised from general
knowledge, and nothing was learned.

This module closes that loop:

    the vault is searched
      → coverage is measured (pages, term coverage, raw sources)
        → a real gap starts a deep research run, off-thread
          → the finished report is written back as a `synthesis` page

Four things are deliberately conservative:

**A GAP IS MEASURED, NOT GUESSED — AND THE QUESTION IS MEASURED AS A SUBJECT.**
The framing of a request ("peux-tu m'expliquer…") and the generic scaffolding
("l'histoire de…") are removed before anything is compared, because a question
that mentions a word the vault does not have is not a hole in the vault — it is
a hole in the phrasing. The subject of what is left is the term the vault
carries in a TITLE: a page titled "Chalcédoine" is a page written about
Chalcédoine. Zero pages is a gap; a page that only happens to contain the word
is a gap; two pages that between them cover the question's terms are not. The
tests pin every one of those cases.

**NOBODY PAYS FOR THE SAME QUESTION TWICE.**  A query that already started a run
is on a cooldown (30 minutes by default) — and the cooldown is written down, so
closing the app is not a way to buy the same report again, and asking the same
question in different words is the same question. Only one run may be active at
a time — the same one the voice tool uses, through `research/jobs.py` — and a
gap that arrives while a run is paying for the web is queued, not dropped. A
daily ceiling (3 by default) bounds the whole thing: a gap is a trigger, not a
purchase order.

**AN EMPTY VAULT DOES NOT TRIGGER.**  A vault with no pages at all is a brain
nobody uses yet, not a brain with a hole; auto-researching the first search of a
fresh install would be a surprise, not a feature.

**A RAW SOURCE IS A LEAD, NOT A HOLE.**  If the text is already in `raw/` but
not structured yet, the cheap next move is to process what the user owns — not
to buy a web report on top of it.

Everything returns a string and never raises: this is called from inside another
tool, and a broken integration must not turn "I found nothing" into "the tool
crashed".
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config, jobs, vocab

_BRIDGE = None
_ROUTER = None


def _router():
    """`actions/_vault_router.py`, loaded by path — `actions/` is not a package.

    The measurement lives there, in the light layer, because the application
    has to be able to ask the vault a question WITHOUT importing the research
    engine: the router is what makes "the vault is consulted before the answer"
    structural instead of a request to the model. One implementation, one
    verdict — the router's and this module's can never disagree."""
    global _ROUTER
    if _ROUTER is not None:
        return _ROUTER
    path = Path(__file__).resolve().parent.parent / "actions" / "_vault_router.py"
    spec = importlib.util.spec_from_file_location("markliv_vault_router", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vault_router"] = module
    spec.loader.exec_module(module)
    _ROUTER = module
    return module


# The words themselves — the grammar, the framing of a request, and the words
# that have two names across languages — live in `research/vocab.py`, because
# the vault's own search has to measure exactly what this measures. A gap
# check that disagrees with the search is how a question gets answered twice:
# once locally, then again for money.


# ── the vault, loaded without importing the app ─────────────────────────────

def _bridge():
    """`actions/theology_brain.py`, loaded by path — `actions/` is not a package
    and importing it as one would depend on the process's working directory."""
    global _BRIDGE
    if _BRIDGE is not None:
        return _BRIDGE
    path = Path(__file__).resolve().parent.parent / "actions" / "theology_brain.py"
    spec = importlib.util.spec_from_file_location("research_theology_brain", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["research_theology_brain"] = module
    spec.loader.exec_module(module)
    _BRIDGE = module
    return module


def _vault(vault: Path | str | None = None) -> Path:
    return Path(vault) if vault else Path(_bridge()._vault())


# ── measuring coverage ──────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Lower-case, accent-folded: "Nicée" and "nicee" are the same term."""
    return vocab.fold(text)


def _terms(query: str) -> list[str]:
    """The words the question is actually about.

    The framing of the request — "peux-tu m'expliquer", "raconte-moi" — is
    removed, and the words that have two names across languages are folded
    together, so a page titled "Council of Nicaea" answers "concile de
    Nicée". Both sides of the comparison use this one function."""
    return vocab.subject_terms(query)


@dataclass
class Coverage:
    query: str
    pages: int = 0
    hits: int = 0
    best_title: str = ""
    best_score: int = 0
    best_coverage: float = 0.0
    terms: int = 0
    raw_hits: int = 0
    gap: bool = False
    reason: str = ""
    subject: str = ""          # the term the question is really about

    def describe(self) -> str:
        bits = [f"{self.hits} page(s) sur {self.pages}"]
        if self.hits:
            bits.append(f"meilleure couverture {int(self.best_coverage * 100)}%"
                        + (f" ([[{self.best_title}]])" if self.best_title else ""))
        if self.subject:
            bits.append(f"sujet : {self.subject}")
        if self.raw_hits:
            bits.append(f"{self.raw_hits} source(s) brute(s) non structurée(s)")
        if self.reason:
            bits.append(self.reason)
        return ", ".join(bits)


def coverage(query: str, vault: Path | str | None = None) -> Coverage:
    """How well the vault answers this question, and whether that is a gap.

    The question is asked of the vault as a SUBJECT, not as a bag of words.
    "peux-tu m'expliquer le concile de Chalcédoine" is about one thing, and a
    vault that holds that thing answers it — whatever else the sentence
    contains.

    The subject of a question is the term the vault carries in a TITLE: a page
    titled "Chalcédoine" is a page written about Chalcédoine, while a page
    that mentions it once in a paragraph is not. The other terms of the
    question must be somewhere in the vault, and then the vault answers; a
    subject it cannot find in any title — and no page that covers the question
    besides — is a hole.

    The measurement itself is the router's — the same one the application uses
    when it consults the vault before the model answers. One implementation, so
    the verdict that spends money and the verdict the user sees cannot drift
    apart."""
    try:
        measured = _router().measure(query, vault)
    except Exception as e:
        print(f"[Theology] coverage check failed: {type(e).__name__}: {e}")
        return Coverage(query=str(query or ""), reason="vault illisible")
    return Coverage(
        query=measured.get("query", str(query or "")),
        pages=measured.get("pages", 0),
        hits=measured.get("hits", 0),
        best_title=measured.get("best_title", ""),
        best_score=measured.get("best_score", 0),
        best_coverage=measured.get("best_coverage", 0.0),
        terms=len(measured.get("terms", [])),
        raw_hits=measured.get("raw_hits", 0),
        gap=bool(measured.get("gap", False)),
        reason=measured.get("reason", ""),
        subject=measured.get("subject", ""),
    )


# ── policy ──────────────────────────────────────────────────────────────────

def enabled() -> bool:
    value = config.setting("theology_auto_research", True)
    return str(value).strip().lower() not in ("false", "0", "no", "off", "")


def _cooldown() -> float:
    try:
        return max(0.0, float(config.setting("theology_auto_research_cooldown",
                                             1800) or 0))
    except (TypeError, ValueError):
        return 1800.0


def _daily_cap() -> int:
    """How many automatic runs the vault may start in one day.

    A gap is a trigger, not a purchase order. Without a ceiling, a user who
    asks ten questions the vault cannot answer wakes up to ten reports bought
    with their own quota — and nobody told them that was going to happen."""
    try:
        return max(0, int(config.setting("theology_auto_research_max_per_day",
                                         3) or 0))
    except (TypeError, ValueError):
        return 3


def _key(query: str) -> str:
    """The identity of a question: its subject, not its wording.

    "peux-tu m'expliquer le concile de Chalcédoine" and "concile de
    Chalcédoine" are the same question, and the vault must not pay for both."""
    return " ".join(_terms(query)) or _norm(query)


# ── the state that survives a restart ───────────────────────────────────────
# The cooldown used to live in RAM, so closing the app and opening it again
# was enough to buy the same report twice — and asking the same question in
# different words was enough to buy it at all. The state now lives beside the
# vault it protects, in one small file, and says what was asked, when, and
# what is still waiting.

_STATE_FILE = ".gaps.json"
_STATE: dict[str, dict] = {}


def _state(vault: Path) -> dict:
    """The trigger's memory for one vault: what was asked, when, what is
    waiting, how much has been spent today."""
    key = str(vault)
    state = _STATE.get(key)
    if state is not None:
        return state
    state = {"seen": {}, "runs": [], "pending": {}, "cap_notified": False}
    try:
        data = json.loads((Path(vault) / _STATE_FILE).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            seen = data.get("seen")
            runs = data.get("runs")
            pending = data.get("pending")
            if isinstance(seen, dict):
                state["seen"] = {str(k): float(v) for k, v in seen.items()
                                 if isinstance(v, (int, float))}
            if isinstance(runs, list):
                state["runs"] = [float(r) for r in runs if isinstance(r, (int, float))]
            if isinstance(pending, dict):
                state["pending"] = {str(k): str(v) for k, v in pending.items()
                                    if str(v)}
            state["cap_notified"] = bool(data.get("cap_notified"))
    except Exception:
        pass
    _STATE[key] = state
    return state


def _save_state(vault: Path) -> None:
    state = _STATE.get(str(vault))
    if state is None:
        return
    try:
        path = Path(vault) / _STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Theology] could not write the trigger state: {e}")


def _within_cooldown(state: dict, key: str) -> bool:
    last = state.get("seen", {}).get(key, 0.0)
    return (time.time() - last) < _cooldown()


def _runs_today(state: dict) -> int:
    today = time.localtime()[:3]
    return sum(1 for ts in state.get("runs", [])
               if time.localtime(ts)[:3] == today)


def _cap_reached(state: dict) -> bool:
    cap = _daily_cap()
    return cap > 0 and _runs_today(state) >= cap


def _mark(state: dict, key: str) -> None:
    now = time.time()
    state.setdefault("seen", {})[key] = now
    state.setdefault("runs", []).append(now)
    state["runs"] = state["runs"][-50:]        # the ledger stays small
    state["cap_notified"] = False


def reset_state() -> None:
    """Tests, and a user who wants a fresh trigger after changing settings.

    Clears the memory AND what was written to disk: a deliberate reset means
    the next question may trigger a run again, whatever was asked before."""
    for key in list(_STATE):
        state = _STATE.pop(key)
        try:
            (Path(key) / _STATE_FILE).unlink(missing_ok=True)
        except Exception:
            pass
        state.clear()


# ── the trigger ─────────────────────────────────────────────────────────────

def _serve_pending(state: dict, root: Path, player, speak, source: str,
                   depth: str | None, language: str | None) -> str:
    """Start the oldest gap that waited for another run. "" when there is
    none to serve."""
    pending = state.get("pending") or {}
    for pkey, pquery in list(pending.items()):
        if _within_cooldown(state, pkey):
            continue
        if _cap_reached(state):
            return ""
        cov = coverage(pquery, vault=root)
        if not cov.gap:
            state["pending"].pop(pkey, None)
            _save_state(root)
            continue
        depth = str(depth or config.setting("theology_auto_research_depth",
                                            "standard") or "standard")
        language = str(language or config.setting("theology_auto_research_language",
                                                 "auto") or "auto")
        run_id, error = jobs.start(
            pquery, depth=depth, language=language,
            skills=["sourced-brief", "theology-source-critique"],
            player=player, speak=speak, source=source, on_done=ingest)
        if error or not run_id:
            print(f"[Theology] queued gap not started: {error}")
            return ""
        _mark(state, pkey)
        state["pending"].pop(pkey, None)
        _save_state(root)
        return (f"Lacune du vault (question en attente) : {cov.describe()}. "
                f"Recherche profonde lancée en arrière-plan (run {run_id}, "
                f"{depth}) ; son rapport sera versé au vault comme page de "
                f"synthèse. Dis-le à l'utilisateur en une phrase, et n'invente "
                f"pas la réponse en attendant.")
    return ""


def maybe_start(query: str, player=None, speak=None,
                vault: Path | str | None = None,
                source: str = "vault", depth: str | None = None,
                language: str | None = None) -> str:
    """Start a run if the vault cannot answer. Returns a note to append to the
    tool's own output, or `""` when nothing was started.

    The note is written for the model, not for the user: it says what happened
    and what to tell them, in the same style as the other tool results."""
    query = " ".join(str(query or "").split())
    if not query or not enabled():
        return ""
    if not _terms(query):
        return ""

    root = _vault(vault)
    state = _state(root)
    key = _key(query)

    if jobs.active() is not None:
        # One run at a time — but the gap is not lost: it waits, and is served
        # when the run that is already paying for the web is over.
        if coverage(query, vault).gap:
            pending = state.setdefault("pending", {})
            if key not in pending:
                pending[key] = query
                _save_state(root)
                print(f"[Theology] gap queued behind the running job: {query}")
        return ""

    # A gap that waited behind another run is served first: it was found
    # before this question, and the user has not been told about it yet.
    served = _serve_pending(state, root, player, speak, source, depth, language)
    if served:
        return served

    cov = coverage(query, vault)
    if not cov.gap:
        return ""

    if _within_cooldown(state, key):
        return ""

    if _cap_reached(state):
        if state.get("cap_notified"):
            return ""
        state["cap_notified"] = True
        _save_state(root)
        return (f"Lacune du vault : {cov.describe()}. Le plafond quotidien de "
                f"recherches automatiques est atteint ({_daily_cap()}) — "
                f"aucune recherche n'est lancée. Dis-le à l'utilisateur en une "
                f"phrase, sans inventer la réponse.")

    depth = str(depth or config.setting("theology_auto_research_depth",
                                        "standard") or "standard")
    language = str(language or config.setting("theology_auto_research_language",
                                             "auto") or "auto")
    run_id, error = jobs.start(
        query, depth=depth, language=language,
        skills=["sourced-brief", "theology-source-critique"],
        player=player, speak=speak, source=source, on_done=ingest)
    if error or not run_id:
        print(f"[Theology] auto research not started: {error}")
        return ""
    _mark(state, key)
    state.setdefault("pending", {}).pop(key, None)
    _save_state(root)
    return (
        f"Lacune du vault : {cov.describe()}. "
        f"Recherche profonde lancée en arrière-plan (run {run_id}, {depth}) ; "
        f"elle lira des sources externes et versera son rapport dans le vault "
        f"comme page de synthèse. Dis-le à l'utilisateur en une phrase, et "
        f"n'invente pas la réponse en attendant.")


def start_and_report(query: str, player=None, speak=None,
                     vault: Path | str | None = None,
                     source: str = "vault-router") -> str:
    """Start a run for a question the vault cannot answer, and say so.

    This is the route the application takes when it has already established
    that the question is theological and the vault is silent on it — the
    research is started without the model having to ask, and the conversation
    is told what is happening. "" when nothing was started."""
    note = maybe_start(query, player=player, speak=speak, vault=vault,
                       source=source)
    if not note:
        return ""
    run_id = ""
    match = re.search(r"run ([0-9A-Za-z._-]+)", note)
    if match:
        run_id = f" (run {match.group(1)})"
    return ("[VAULT] The theology vault holds nothing on this question, and a "
            f"deep research is running in the background{run_id}. It will read "
            "outside sources and file its report in the vault as a synthesis "
            "page. Say that to the user in one sentence, in their own "
            "language, and do not invent the answer in the meantime.")


# ── the loop back ───────────────────────────────────────────────────────────

def _strip_frontmatter(text: str) -> str:
    text = str(text or "")
    if text.lstrip().startswith("---"):
        start = text.find("---")
        end = text.find("\n---", start + 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def ingest(run, vault: Path | str | None = None) -> str:
    """Write a finished run's report into the vault as a synthesis page.

    Called by `research/jobs.py` on the worker thread after the announcement, so
    a completed automatic run costs one file write and one XERJ upsert, and the
    next search for the same question hits the vault instead of the web."""
    if getattr(run, "status", "") != "done" or not getattr(run, "report_path", ""):
        return ""
    try:
        raw = Path(run.report_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Rapport illisible pour le vault : {e}"

    body = _strip_frontmatter(raw)
    body = re.sub(r"^#\s+.+\n+", "", body, count=1).strip()
    if not body:
        return ""

    outline = getattr(run, "outline", {}) or {}
    topic = str(getattr(run, "topic", "") or "").strip()
    title = str(outline.get("title") or getattr(run, "title", "") or
                topic).strip()[:140]

    # The page must carry the subject in its TITLE, or the next question about
    # it will read the report as a passing mention and go and buy it again.
    # A report titled "Recherche sur l'Église" filed under "concile de
    # Chalcédoine" would close no loop at all.
    if topic:
        subjects = set(vocab.subject_terms(topic))
        in_title = {vocab.canonical(w) for w in vocab.tokens(title)}
        if subjects and not (subjects & in_title):
            title = f"{title} — {topic}"[:140]

    urls = [str(s.get("url")) for s in (getattr(run, "sources", []) or [])
            if s.get("url")]
    attribution = (
        f"> **Recherche automatique** — déclenchée par une lacune du vault sur "
        f"« {getattr(run, 'topic', '')} » ({len(getattr(run, 'sources', []) or [])} "
        f"sources, {date.today().isoformat()}). Run `{run.id}` — rapport complet : "
        f"`{run.report_path}`")

    try:
        # `_action_write` rather than `run()`: the vault is passed explicitly
        # (the tests use a temporary one) and the plugin wrapper adds nothing.
        out = _bridge()._action_write(_vault(vault), {
            "kind": "synthesis",
            "title": title,
            "text": attribution + "\n\n" + body,
            "sources": ", ".join(urls[:12]),
            "tags": "auto-research, deep-research",
        })
    except Exception as e:
        print(f"[Theology] could not file the report: {type(e).__name__}: {e}")
        return ""
    return f"Rapport versé au vault : {out}"
