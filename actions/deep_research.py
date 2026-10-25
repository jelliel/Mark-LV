"""
Theologicus action — deep research (the DeerFlow loop, natively).

One tool, several verbs, because a voice user should not have to learn a
different tool for each stage of the same job:

    run      start an investigation in the background  (default)
    status   where it is, how long it has been going
    list     recent runs on this machine
    show     the report, on the HUD and on disk
    open     the report in the system's default app
    resume   rebuild the report from the notes already on disk — no searching
    cancel   stop the run at the next safe point
    skills   the declarative skills a run can apply
    agents   the sub-agents that will do the reading

WHY IT NEVER BLOCKS THE TURN.  A deep run reads a dozen pages and writes five
sections; it takes minutes, not seconds. `_execute_tool` awaits a blocking tool,
so a blocking deep_research would freeze the conversation for the whole run —
no interruption, no question, no "stop". The tool therefore returns in
milliseconds and the engine runs on its own thread. It is declared NON_BLOCKING
with SILENT scheduling: the result of "started" is not worth a spoken turn, and
the completion is announced through `speak()` like a plugin's progress channel,
which is exactly what `plugin_say` was built for.

The thread, the HUD progress and the spoken headline live in `research/jobs.py`,
not here: the theology vault starts runs through the same manager when it cannot
answer a question, and two entry points that each owned a job registry would
happily run two engines at once. This file keeps the *words*; that one keeps the
*thread*.

Cancellation is cooperative and checked between stages, between pages and
between sections — never inside a request, so a cancel cannot corrupt a run.
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))


def _api():
    """The research package, imported on use.

    `actions/` is scanned at every launch; a module that pulls a package
    importing requests, bs4 and the Gemini SDK at import time would be paid for
    by every boot, including the boots where nobody researches anything."""
    package = importlib.import_module("research")
    for name in ("config", "engine", "jobs", "skills", "store", "subagents",
                 "theology"):
        importlib.import_module(f"research.{name}")
    return package


def _wants_vault(params: dict) -> bool:
    """True when the report should end up in the theology vault.

    The automatic gap trigger always files its report there. A run the user
    asked for keeps its own report unless it is about something the vault
    holds — then it is filed too, and the next question about that subject is
    answered locally instead of bought again."""
    value = params.get("vault")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return False


# A run filed into the vault must be governed by the theology discipline, or
# the vault would receive a report that never learned to tell a council's
# definition from a scholar's reading of it — and the synthesis page it becomes
# would carry no reading at all. Requesting the skill is what composes one.
_VAULT_SKILLS = ("sourced-brief", "theology-source-critique")


def _limit(params: dict, default: int = 8) -> int:
    try:
        return max(1, min(30, int(params.get("limit") or default)))
    except (TypeError, ValueError):
        return default


# ── handlers ────────────────────────────────────────────────────────────────

def deep_research(parameters: dict, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "run").strip().lower()
    research = _api()
    jobs = research.jobs

    if action in ("run", "start", "research"):
        topic = " ".join(str(params.get("topic") or "").split())
        if not topic:
            return "Indique un sujet : « lance une recherche approfondie sur … »."
        language = str(params.get("language") or "").strip() or \
            str(research.config.setting("research_language") or "auto")
        raw_skills = params.get("skills") or []
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        filed = _wants_vault(params)
        if filed:
            raw_skills = list(raw_skills) + [s for s in _VAULT_SKILLS
                                             if s not in raw_skills]
        try:
            on_done = research.theology.ingest if filed else None
            run_id, error = jobs.start(
                topic, depth=str(params.get("depth") or "standard"),
                language=language, skills=raw_skills,
                player=player, speak=speak, source="voice", on_done=on_done)
        except Exception as e:
            return f"Impossible de démarrer la recherche : {type(e).__name__}: {e}"
        if error:
            return error
        note = (" Le rapport sera versé dans le vault théologique, comme page "
                "de synthèse." if filed else "")
        return (f"Recherche profonde lancée ({str(params.get('depth') or 'standard')}) "
                f"sur « {topic} ». Run {run_id}. Je te préviens dès que le rapport "
                f"est prêt — tu peux continuer à me parler entre-temps.{note}")

    if action == "status":
        active = jobs.active()
        if active:
            run = active["run"]
            elapsed = int(time.time() - active["started"])
            return (f"En cours : « {run.topic} » — {run.stage or run.status}, "
                    f"{len(run.sources)} sources, {len(run.notes)} notes, "
                    f"{elapsed // 60} min {elapsed % 60:02d} s.")
        run = research.store.load_run(str(params.get("run_id") or "")) \
            or research.store.latest_run()
        if run is None:
            return "Aucune recherche sur cette machine pour l'instant."
        return (f"Dernier run : « {run.title or run.topic} » — {run.status}, "
                f"{len(run.sources)} sources, {int(run.duration_s)} s."
                + (f" Rapport : {run.report_path}" if run.report_path else "")
                + (f" Erreur : {run.error}" if run.error else ""))

    if action == "list":
        runs = research.store.list_runs(limit=_limit(params))
        if not runs:
            return "Aucune recherche enregistrée pour l'instant."
        lines = ["Recherches récentes :"]
        for row in runs:
            lines.append(f"- {row['created'][:16].replace('T', ' ')} · "
                         f"{row['status']} · {row['sources']} sources · "
                         f"{row['title'][:70]}")
        lines.append("Dis « montre le rapport » pour l'ouvrir sur l'écran.")
        return "\n".join(lines)

    if action in ("show", "open", "report"):
        run = research.store.load_run(str(params.get("run_id") or "")) \
            or research.store.latest_run()
        if run is None:
            return "Aucun rapport disponible."
        if not run.report_path or not Path(run.report_path).exists():
            notes = research.store.read_notes(run)
            if notes:
                return (f"Le rapport n'est pas encore écrit, mais {len(notes)} "
                        f"notes sont sur le disque. Dis « reprends la recherche » "
                        f"pour le régénérer sans relire les pages.")
            return "Ce run n'a produit ni rapport ni notes."
        text = Path(run.report_path).read_text(encoding="utf-8", errors="replace")
        if action == "open":
            try:
                import os
                if sys.platform.startswith("win"):
                    os.startfile(run.report_path)          # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", run.report_path])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", run.report_path])
            except Exception as e:
                return f"Impossible d'ouvrir le fichier ({e}) — il est ici : {run.report_path}"
        if player:
            try:
                player.show_content(f"RAPPORT — {(run.title or run.topic)[:32]}", text)
                player.write_log(f"[Research] rapport affiché : {run.report_path}")
            except Exception:
                pass
        head = text[:1200]
        return (f"Rapport « {run.title} » ({len(text)} caractères, "
                f"{len(run.sources)} sources) :\n\n{head}\n\n"
                f"Fichier complet : {run.report_path}")

    if action in ("resume", "continue"):
        run = research.store.load_run(str(params.get("run_id") or "")) \
            or research.store.latest_run()
        if run is None:
            return "Aucun run à reprendre."
        if run.report_path and Path(run.report_path).exists() and \
                str(params.get("force") or "").lower() not in ("true", "1", "yes"):
            return (f"Le rapport de « {run.title} » existe déjà : {run.report_path}. "
                    f"Ajoute force=true pour le réécrire à partir des notes.")
        try:
            on_done = research.theology.ingest if _wants_vault(params) else None
            run_id, error = jobs.resume(run.id, player=player, speak=speak,
                                        on_done=on_done)
        except Exception as e:
            return f"Reprise impossible : {type(e).__name__}: {e}"
        if error:
            return error
        return (f"Je réécris le rapport de « {run.title} » à partir des "
                f"{len(run.notes)} notes déjà sur le disque — sans relire les "
                f"pages. Je te préviens quand c'est prêt.")

    if action in ("cancel", "stop"):
        job = jobs.cancel()
        if job is None:
            return "Aucune recherche en cours."
        run = job["run"]
        if player:
            try:
                player.write_log(f"[Research] annulation demandée — {run.id}")
            except Exception:
                pass
        return (f"J'arrête la recherche sur « {run.topic} » au prochain point sûr. "
                f"Les {len(run.sources)} sources déjà lues sont conservées et le "
                f"run pourra être repris.")

    if action == "skills":
        skills = research.skills.discover()
        if not skills:
            return "Aucune compétence de recherche installée."
        lines = ["Compétences de recherche disponibles :"]
        lines += [f"- {line}" for line in research.skills.list_lines(skills)]
        lines.append("Elles s'appliquent automatiquement selon le sujet, ou "
                     "impose-les avec le paramètre skills.")
        return "\n".join(lines)

    if action == "agents":
        agents = research.subagents.discover()
        lines = ["Sous-agents de recherche :"]
        lines += [f"- {line}" for line in research.subagents.list_lines(agents)]
        lines.append("Ajoute un .md dans « Mark LV Research/agents » pour les "
                     "retoucher ou en créer un.")
        return "\n".join(lines)

    return ("Action inconnue. Utilise : run, status, list, show, open, resume, "
            "cancel, skills, agents.")


TOOL = {
    "name": "deep_research",
    "description": (
        "Deep multi-agent research that writes a cited Markdown report: plans "
        "sub-questions, searches, reads full pages, reconciles contradictions, "
        "and saves a sourced document to disk and the HUD. Runs in the "
        "background — the conversation stays live. Use it for a written "
        "multi-source investigation ('deep research', 'recherche approfondie', "
        "'rapport complet', 'due diligence', 'state of the art', 'compare X and "
        "Y thoroughly', 'the evidence on…'), not for a single fact. "
        "action='run' (default, needs 'topic'; optional depth quick|standard|deep, "
        "language); 'status'; 'list'; 'show'; 'open'; 'resume' (rewrite from saved "
        "notes, no searching); 'cancel'; 'skills'; 'agents'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "run (default) | status | list | show | open | "
                               "resume | cancel | skills | agents",
            },
            "topic": {
                "type": "STRING",
                "description": "What to investigate, as the user framed it. "
                               "Required for action='run'.",
            },
            "depth": {
                "type": "STRING",
                "description": "quick (3 questions, ~8 pages, 1 round) | "
                               "standard (5 questions, ~18 pages, 2 rounds) | "
                               "deep (7 questions, ~30 pages, 3 rounds + "
                               "critique). Default standard.",
            },
            "language": {
                "type": "STRING",
                "description": "Language the report is written in, e.g. 'fr'. "
                               "Default: follow the topic and the configured "
                               "preference.",
            },
            "skills": {
                "type": "STRING",
                "description": "Optional comma-separated skill names to force, "
                               "e.g. 'fact-check,theology-source-critique'. The "
                               "planner chooses its own when this is omitted.",
            },
            "run_id": {
                "type": "STRING",
                "description": "Target a specific run for status/show/open/resume.",
            },
            "vault": {
                "type": "STRING",
                "description": "'true' to file the finished report into the "
                               "theology vault as a synthesis page, so the next "
                               "question on that subject is answered from the "
                               "vault instead of the web. Use it for a "
                               "theological subject the user is building a "
                               "second brain on.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "How many runs action='list' returns (default 8).",
            },
            "force": {
                "type": "STRING",
                "description": "'true' to let action='resume' overwrite an "
                               "existing report.",
            },
        },
        "required": [],
    },
    "handler": deep_research,
    "behavior": "NON_BLOCKING",
    "scheduling": "SILENT",
}
