"""
A run on disk — plan, sources, notes, report — and a way back into it.

A deep run is not one call; it is a plan, a dozen pages, five sets of notes and
a report written one section at a time. If any of that lived only in a thread's
memory, a crash at minute three would cost the whole run and a cancelled run
would leave nothing behind.

    runs/20261021-181500-council-of-ephesus/
    ├── run.json          state, plan, sources, events — rewritten at each stage
    ├── pages/            flattened page text, so resume never re-fetches
    ├── notes/            one Markdown note per researcher, per round
    └── report.md         the deliverable

`run.json` is written atomically (research/util.atomic_write), so a power cut
leaves the previous stage readable rather than a half-file that cannot load.

The index is not a file. `list_runs()` scans the run folders and sorts by date:
an index file is a second source of truth that goes stale the moment a folder is
moved, and scanning thirty small JSON files costs less than the bug it prevents.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config
from .util import atomic_write, iso_now, read_json, slugify, stamp, write_json

@dataclass
class Run:
    id: str
    topic: str
    depth: str = "standard"
    language: str = "auto"
    status: str = "pending"
    stage: str = ""
    created: str = field(default_factory=iso_now)
    updated: str = field(default_factory=iso_now)
    title: str = ""
    plan: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    agents: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    seen_urls: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    outline: dict = field(default_factory=dict)
    critique: dict = field(default_factory=dict)
    # The reading, composed from the outline and checked against the closed
    # vocabulary of authorities and weights (research/reading.py). Empty for a
    # non-theological run, and for a run whose reading would not check out.
    reading: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    report_path: str = ""
    error: str = ""
    duration_s: float = 0.0
    dir: str = ""

    # ── lifecycle ────────────────────────────────────────────────────────────
    def set_stage(self, status: str, stage: str) -> None:
        self.status = status
        self.stage = stage
        self.touch()

    def touch(self) -> None:
        self.updated = iso_now()

    def add_event(self, stage: str, message: str) -> None:
        self.events.append({"t": iso_now(), "stage": stage, "message": message})
        self.events = self.events[-80:]
        self.touch()

    @property
    def path(self) -> Path:
        return Path(self.dir)

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def summary(self) -> dict:
        return {
            "id": self.id, "title": self.title or self.topic,
            "topic": self.topic, "status": self.status, "stage": self.stage,
            "created": self.created, "duration_s": round(self.duration_s, 1),
            "sources": len(self.sources), "depth": self.depth,
            "path": self.dir, "report_path": self.report_path,
            "error": self.error,
        }

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict, folder: Path) -> "Run":
        known = {f for f in cls.__dataclass_fields__}       # type: ignore[attr-defined]
        run = cls(**{k: v for k, v in (data or {}).items() if k in known})
        run.dir = str(folder)
        return run


# ── creation / persistence ──────────────────────────────────────────────────

def create_run(topic: str, depth: str = "standard", language: str = "auto",
               root: Path | None = None) -> Run:
    topic = " ".join(str(topic or "").split())
    base_id = f"{stamp()}-{slugify(topic)}"
    run_id = base_id
    # Two runs of the same topic in the same second must not share a folder —
    # the second would append its sources to the first run's list.
    suffix = 2
    while (config.runs_dir(root) / run_id).exists():
        run_id = f"{base_id}-{suffix}"
        suffix += 1
    folder = config.runs_dir(root) / run_id
    (folder / "pages").mkdir(parents=True, exist_ok=True)
    (folder / "notes").mkdir(parents=True, exist_ok=True)
    run = Run(id=run_id, topic=topic, depth=depth, language=language,
              dir=str(folder), title=topic[:120])
    save(run)
    return run


def save(run: Run) -> None:
    run.touch()
    write_json(Path(run.dir) / "run.json", run.to_dict())


def load_run(run_id: str, root: Path | None = None) -> Run | None:
    run_id = str(run_id or "").strip()
    if not run_id:
        return latest_run(root)
    folder = config.runs_dir(root) / run_id
    data = read_json(folder / "run.json")
    if not isinstance(data, dict):
        return None
    return Run.from_dict(data, folder)


def list_runs(limit: int = 20, root: Path | None = None) -> list[dict]:
    folder = config.runs_dir(root)
    rows = []
    for child in folder.iterdir():
        if not child.is_dir():
            continue
        data = read_json(child / "run.json")
        if not isinstance(data, dict):
            continue
        run = Run.from_dict(data, child)
        rows.append(run.summary())
    rows.sort(key=lambda r: r.get("created", ""), reverse=True)
    return rows[:max(1, limit)]


def latest_run(root: Path | None = None) -> Run | None:
    rows = list_runs(limit=1, root=root)
    if not rows:
        return None
    return load_run(rows[0]["id"], root)


# ── notes / pages ───────────────────────────────────────────────────────────

def page_cache_path(run: Run, n: int) -> Path:
    return Path(run.dir) / "pages" / f"{n:03d}.txt"


def cache_page(run: Run, n: int, text: str) -> None:
    try:
        atomic_write(page_cache_path(run, n), text)
    except OSError as e:
        print(f"[Research] could not cache page {n}: {e}")


def cached_page(run: Run, n: int) -> str:
    try:
        return page_cache_path(run, n).read_text(encoding="utf-8")
    except OSError:
        return ""


def save_note(run: Run, label: str, agent: str, question: str, text: str) -> dict:
    label = slugify(label, 40) or "note"
    path = Path(run.dir) / "notes" / f"{label}.md"
    try:
        atomic_write(path, text)
    except OSError as e:
        print(f"[Research] could not save note {label}: {e}")
    meta = {"label": label, "agent": agent, "question": question,
            "path": str(path), "chars": len(text)}
    run.notes.append(meta)
    return meta


def read_notes(run: Run) -> list[dict]:
    """Notes with their text, for analysis or a resume that has no network."""
    out = []
    for meta in run.notes:
        path = Path(meta.get("path") or "")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        out.append({**meta, "text": text})
    return out


def write_report(run: Run, markdown: str) -> Path:
    path = Path(run.dir) / "report.md"
    atomic_write(path, markdown)
    run.report_path = str(path)
    return path


# ── long-term memory bridge ─────────────────────────────────────────────────

def remember(run: Run) -> str:
    """Leave one short line in long_term.json so a later sentence like "the
    report we did on Ephesus" resolves without the user naming a path.

    Deliberately terse: the memory prompt is a budget, and a run that is already
    on disk does not need its findings repeated inside the prompt."""
    thesis = str((run.outline or {}).get("thesis") or "").strip()
    text = f"{run.title or run.topic} — {len(run.sources)} sources, " \
           f"{run.created[:10]}. {thesis[:170]} Report: {run.report_path}"
    try:
        from memory import memory_manager
        memory_manager.update_memory(
            {"projects": {"research": {"value": re.sub(r"\s+", " ", text).strip()}}})
        return "remembered"
    except Exception as e:
        print(f"[Research] could not write to long-term memory: {e}")
        return "not remembered"
