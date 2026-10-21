"""
One research job at a time, shared by the voice tool and the gap trigger.

A run is started from two places now: the user asking for one, and the theology
vault noticing that it cannot answer a question. Both must obey the same rules —
one run at a time, progress on the HUD, a spoken headline at the end, a cancel
that actually reaches the engine — so the job manager lives here instead of
inside the voice action. The action keeps the *words*; this module keeps the
*thread*.

The completion hook is the reason this is a module and not thirty lines in
`actions/deep_research.py`: the theology bridge files the finished report back
into the vault, and it needs to run on the same thread that just finished the
run, after the announcement, without either entry point knowing about the other.

`on_done(run)` is called once, never raises out of the worker, and is passed the
finished Run so an integration can read the report path, the sources and the
outline without re-reading run.json.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from . import config, engine, store

TERMINAL = ("done", "failed", "cancelled")
_MAX_JOBS = 12

_STAGE_LABEL = {
    "planning": "plan",
    "researching": "recherche",
    "analysing": "analyse",
    "critiquing": "critique",
    "writing": "rédaction",
    "done": "terminé",
    "failed": "échec",
    "cancelled": "annulé",
}

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_LAST = ""


# ── registry ────────────────────────────────────────────────────────────────

def get(run_id: str) -> dict | None:
    with _LOCK:
        return _JOBS.get(str(run_id or ""))


def active() -> dict | None:
    """The job that currently owns the engine, if any.

    A job counts as active while its thread lives **or** while its run has not
    reached a terminal state. The second half closes the window between
    registering a job and starting its thread, during which two triggers in the
    same second would both have been accepted."""
    with _LOCK:
        for job in _JOBS.values():
            thread = job.get("thread")
            run = job.get("run")
            if (thread and thread.is_alive()) or \
                    (run is not None and run.status not in TERMINAL):
                return job
    return None


def last_job() -> dict | None:
    with _LOCK:
        return _JOBS.get(_LAST)


def cancel() -> dict | None:
    job = active()
    if job is None:
        return None
    job["cancel"].set()
    return job


def _register(run_id: str, job: dict) -> None:
    global _LAST
    with _LOCK:
        if len(_JOBS) >= _MAX_JOBS:
            for old_id, old in list(_JOBS.items()):
                thread = old.get("thread")
                run = old.get("run")
                finished = (thread is None or not thread.is_alive()) and \
                    (run is None or run.status in TERMINAL)
                if finished and old_id != run_id:
                    _JOBS.pop(old_id, None)
                    if len(_JOBS) < _MAX_JOBS:
                        break
        _JOBS[run_id] = job
        _LAST = run_id


# ── HUD + voice ─────────────────────────────────────────────────────────────

def progress_text(run) -> str:
    lines = [f"{run.title or run.topic}",
             f"{_STAGE_LABEL.get(run.status, run.status)} · "
             f"{len(run.sources)} sources · {len(run.notes)} notes",
             ""]
    for event in run.events[-10:]:
        lines.append(f"{event.get('t', '')[11:19]}  {event.get('message', '')}")
    if run.report_path:
        lines += ["", f"Rapport : {run.report_path}"]
    return "\n".join(lines)


def _progress(player, run, message: str) -> None:
    if not player:
        return
    try:
        player.write_log(f"[Research] {message}")
        player.show_content(f"RECHERCHE — {(run.title or run.topic)[:30]}",
                            progress_text(run))
    except Exception:
        pass


def announce(run, player=None, speak=None, voice: bool = True) -> None:
    """Say the run has finished, once, without reading the report aloud."""
    done = run.status == "done" and bool(run.report_path)
    if player:
        try:
            if done:
                text = Path(run.report_path).read_text(encoding="utf-8",
                                                       errors="replace")
                player.show_content(f"RAPPORT — {(run.title or run.topic)[:32]}", text)
            player.write_log(
                f"[Research] {run.status} — {len(run.sources)} sources — "
                f"{run.report_path or run.error}")
        except Exception as e:
            print(f"[Research] UI update failed: {e}")
    if not (voice and speak):
        return
    try:
        if done:
            speak(
                f"[RESEARCH_DONE] The research on '{run.title}' finished. "
                f"{len(run.sources)} sources were gathered and the report is on "
                f"screen. Tell the user the three most important findings in "
                f"their own language, one short sentence each, then say the "
                f"full report is at {run.report_path}. Do not read the report "
                f"aloud.")
        elif run.status == "cancelled":
            speak(f"[RESEARCH_DONE] The research on '{run.title}' was cancelled "
                  f"after {len(run.sources)} sources. The notes are saved and can "
                  f"be resumed.")
        else:
            speak(f"[RESEARCH_DONE] The research on '{run.title}' failed: "
                  f"{run.error}. {len(run.sources)} sources were saved and the "
                  f"run can be resumed.")
    except Exception as e:
        print(f"[Research] could not announce completion: {e}")


def _finish(run, player, speak, voice: bool,
            on_done: Callable | None) -> None:
    announce(run, player, speak, voice)
    if on_done is None:
        return
    try:
        result = on_done(run)
        if result and player:
            player.write_log(f"[Research] {result}")
    except Exception as e:                     # an integration must not kill the thread
        print(f"[Research] completion hook failed: {type(e).__name__}: {e}")


# ── starting ────────────────────────────────────────────────────────────────

def start(topic: str, depth: str = "standard", language: str = "auto",
          skills: list[str] | None = None, player=None, speak=None,
          voice: bool | None = None, on_done: Callable | None = None,
          source: str = "voice") -> tuple[str, str]:
    """`(run_id, error)`. The run is on its own thread before this returns."""
    topic = " ".join(str(topic or "").split())
    if not topic:
        return "", "Indique un sujet : « lance une recherche approfondie sur … »."
    running = active()
    if running:
        run = running["run"]
        return "", (f"Une recherche est déjà en cours sur « {run.topic} » "
                    f"({len(run.sources)} sources). Dis « annule la recherche » "
                    f"pour l'arrêter, ou « état de la recherche » pour savoir où "
                    f"elle en est.")
    depth = str(depth or "standard").strip().lower()
    if depth not in engine.DEPTHS:
        depth = "standard"
    if voice is None:
        voice = bool(config.setting("research_voice_summary", True))
    run, eng = engine.start(topic, depth=depth, language=language,
                            requested_skills=skills)
    eng.on_event = lambda stage, message: _progress(player, run, message)
    job = {"run": run, "engine": eng, "cancel": eng.cancel,
           "started": time.time(), "source": source, "on_done": on_done}
    job["thread"] = threading.Thread(
        target=lambda: _finish(eng.run(), player, speak, bool(voice), on_done),
        name=f"research-{run.id}", daemon=True)
    _register(run.id, job)
    job["thread"].start()
    return run.id, ""


def resume(run_id: str = "", player=None, speak=None, voice: bool | None = None,
           on_done: Callable | None = None) -> tuple[str, str]:
    """Rebuild a report from the notes already on disk, off-thread."""
    running = active()
    if running:
        return "", (f"Une recherche tourne déjà sur « {running['run'].topic} » — "
                    f"attends qu'elle finisse ou annule-la avant d'en reprendre une.")
    run = store.load_run(run_id) if str(run_id or "").strip() else store.latest_run()
    if run is None:
        return "", "Aucun run à reprendre."
    if not store.read_notes(run):
        return "", "Ce run n'a pas de notes : il n'y a rien à reprendre."
    if voice is None:
        voice = bool(config.setting("research_voice_summary", True))
    eng = engine.ResearchEngine(run)
    eng.on_event = lambda stage, message: _progress(player, run, message)
    job = {"run": run, "engine": eng, "cancel": eng.cancel,
           "started": time.time(), "source": "resume", "on_done": on_done}
    job["thread"] = threading.Thread(
        target=lambda: _finish(eng.resume(), player, speak, bool(voice), on_done),
        name=f"research-resume-{run.id}", daemon=True)
    _register(run.id, job)
    job["thread"].start()
    return run.id, ""
