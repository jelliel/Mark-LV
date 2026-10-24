"""
Declarative skills — Markdown files that change how a run reasons.

DeerFlow's skills are folders with a SKILL.md and optional scripts, loaded on
demand so a hundred of them cost nothing until one is used. This is the same
idea without the machinery: one flat `.md` per skill, a tiny frontmatter, and
the body injected into the planner and writer prompts **only when selected**.

Two things make it useful rather than decorative:

  SELECTION IS THE MODEL'S JOB.  The planner sees a catalogue of names and
  one-line "when" hints, and returns the ones this topic needs. A run about
  council Christology selects the theology critique; a run about database
  engines selects technical due diligence; a run about a contested number
  selects fact-check. Nothing is loaded because it might be relevant.

  USER SKILLS WIN.  Drop a file with the same name into
  `Documents/Mark LV Research/skills/` and it replaces the shipped one — tuning
  a skill does not mean editing the application's own folder.

Frontmatter is parsed by hand: PyYAML is not a dependency of this app, and a
skill loader is not a reason to add one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
MAX_BODY_CHARS = 3500


@dataclass
class Skill:
    name: str
    description: str
    when: str
    body: str
    path: Path | None = None
    builtin: bool = True

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "when": self.when, "path": str(self.path or ""),
                "builtin": self.builtin}


def _parse(path: Path, builtin: bool) -> Skill | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[Research] skill unreadable {path.name}: {e}")
        return None
    meta: dict[str, str] = {}
    body = raw
    match = _FRONTMATTER.match(raw.lstrip("\ufeff"))
    if match:
        body = raw.lstrip("\ufeff")[match.end():]
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    name = (meta.get("name") or path.stem).strip().lower()
    name = re.sub(r"[^a-z0-9_-]+", "-", name).strip("-") or path.stem.lower()
    body = body.strip()
    if not body:
        return None
    return Skill(name=name,
                 description=(meta.get("description") or "").strip(),
                 when=(meta.get("when") or meta.get("use-when") or "").strip(),
                 body=body[:MAX_BODY_CHARS],
                 path=path, builtin=builtin)


def _scan(folder: Path, builtin: bool) -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith(("_", ".")):
            continue
        skill = _parse(path, builtin)
        if skill:
            found[skill.name] = skill
    return found


def discover(root: Path | None = None) -> dict[str, Skill]:
    """Bundled skills, then the user's — a user file of the same name wins."""
    skills = _scan(config.bundled_skills_dir(), builtin=True)
    for name, skill in _scan(config.skills_dir(root), builtin=False).items():
        if name in skills:
            print(f"[Research] skill '{name}' overridden by {skill.path}")
        skills[name] = skill
    return skills


def catalog(skills: dict[str, Skill]) -> str:
    """The compact list the planner reads. Names and one line each, nothing
    more: the body is what costs tokens, and it is not loaded yet."""
    lines = []
    for skill in sorted(skills.values(), key=lambda s: s.name):
        hint = skill.when or skill.description
        lines.append(f"- {skill.name}: {hint}".strip())
    return "\n".join(lines)


def resolve(names, skills: dict[str, Skill]) -> list[Skill]:
    """Names to skills, ignoring anything the planner invented."""
    picked: list[Skill] = []
    seen = set()
    for raw in names or []:
        if isinstance(raw, dict):
            raw = raw.get("name", "")
        name = str(raw or "").strip().lower()
        if not name or name in seen:
            continue
        skill = skills.get(name)
        if skill is None:
            print(f"[Research] planner asked for an unknown skill: {name}")
            continue
        seen.add(name)
        picked.append(skill)
    return picked


def prompt_block(picked: list[Skill]) -> str:
    """The text a selected skill contributes to a prompt. Empty when none."""
    if not picked:
        return ""
    chunks = ["## Skills for this run",
              "Apply all of them. Where two disagree, the one that demands "
              "more evidence wins."]
    for skill in picked:
        chunks.append(f"\n### Skill: {skill.name}\n{skill.body}")
    return "\n".join(chunks)


def list_lines(skills: dict[str, Skill]) -> list[str]:
    """For the voice tool's 'skills' action."""
    return [f"{s.name} — {s.description or s.when} ({'shipped' if s.builtin else 'yours'})"
            for s in sorted(skills.values(), key=lambda s: s.name)]
