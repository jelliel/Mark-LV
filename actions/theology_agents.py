"""
MARK-LIV — theology agents bridge.

Scans the user's agent folder (default: Desktop/Agents, override with the
`theology_agents_dir` key in config/api_keys.json) into AgentProfile objects,
so the ingestion window can list them and which one to hand a source to.

Each profile is an .md file: the file name gives the agent's name, and the
first paragraphs give its brief — the persona handed to the structuring model
in file_processor._theology_structure(persona=...). learn_with_agents() then
runs the same theology_brain vault pipeline, once per selected agent: every
agent reads the source through its own specialty and writes its own pages
(attribution line + agent tag), so the vault can merge different readings of
the same source on one page.

Stdlib only, and file_processor is loaded by path (actions/ is not a package)
the same way file_processor loads theology_brain.
"""

import importlib.util
import json
import re
from dataclasses import dataclass
from pathlib import Path

AGENTS_DIR_KEY = "theology_agents_dir"   # optional override in config/api_keys.json
_BRIEF_CHARS   = 900                     # persona size handed to the model
_NAME_PREFIX   = "agent-"


@dataclass
class AgentProfile:
    name: str      # display name, e.g. "Apologète Catholique"
    path: Path     # the .md file
    brief: str     # first paragraphs, its specialty


def _config_value(key: str):
    config = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    try:
        return json.loads(config.read_text(encoding="utf-8")).get(key)
    except Exception:
        return None


def get_agents_dir() -> Path:
    """The agent folder as configured, or Desktop/Agents by default."""
    override = _config_value(AGENTS_DIR_KEY)
    if override:
        return Path(str(override)).expanduser()
    return Path.home() / "Desktop" / "Agents"


# ── Profile parsing ──────────────────────────────────────────────────────────

def _clean_name(stem: str) -> str:
    name = stem.strip()
    if name.lower().startswith(_NAME_PREFIX):
        name = name[len(_NAME_PREFIX):]
    return name.replace("-", " ").replace("_", " ").strip() or stem


def _brief_from_text(text: str) -> str:
    """The persona: first meaningful paragraphs, headings stripped, capped.

    A YAML frontmatter (--- ... ---) is skipped, headings '##'/'#' are turned
    into plain lines, and the result is trimmed to _BRIEF_CHARS on a sentence
    or line boundary so the model never sees a cut-off word.
    """
    text = re.sub(r"\r\n?", "\n", text)
    if text.startswith("---"):                     # YAML frontmatter
        end = text.find("\n---", 3)
        if end != -1 and end < _BRIEF_CHARS * 4:
            text = text[end + 4:]
    out, seen = [], 0
    for raw_line in text.split("\n"):
        line = re.sub(r"^#{1,6}\s*", "", raw_line).strip()
        if not line or re.fullmatch(r"[-*:_\[\]()|<>\\/~]+", line):
            continue
        if "```" in line:
            continue                               # code fences are not persona
        out.append(line)
        seen += len(line) + 1
        if seen >= _BRIEF_CHARS:
            break
    brief = " \n".join(out)
    if len(brief) > _BRIEF_CHARS:
        cut = brief[:_BRIEF_CHARS]
        for sep in (". ", ".\n", "! ", "? "):
            last = cut.rfind(sep)
            if last > _BRIEF_CHARS // 2:
                cut = cut[:last + 1]
                break
        brief = cut.rstrip() + " …"
    return brief


def _profile_from_path(path: Path) -> AgentProfile | None:
    try:
        brief = _brief_from_text(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not brief:
        return None
    return AgentProfile(name=_clean_name(path.stem), path=path, brief=brief)


def discover_agents(agents_dir=None, logger=print) -> list[AgentProfile]:
    """Every agent profile in the folder, sorted by name. Top level only —
    subfolders such as 'AI Prompts' hold prompt collections, not agents."""
    root = Path(agents_dir) if agents_dir else get_agents_dir()
    if not root.is_dir():
        logger(f"[Agents] folder not found: {root}")
        return []
    profiles = []
    for path in sorted(root.glob("*.md")):
        profile = _profile_from_path(path)
        if profile is None:
            logger(f"[Agents] skipped (no readable brief): {path.name}")
            continue
        profiles.append(profile)
    logger(f"[Agents] {root} -> {len(profiles)} agent(s)")
    return profiles


# ── The team's living self-knowledge doc ─────────────────────────────

_SELF_DOC = Path("self") / "mark-liv-theology.md"
_IDENTITY = """# MARK-LIV Theology — Self-Knowledge of the Team

_Identity section written by hand. The AUTO blocks are regenerated after each
ingestion — never edited by hand. (Pattern: a living "self-knowledge" doc,
AUTO blocks marked by HTML comments, refreshed metadata never touching the
hand-written sections.)_

## Identity

MARK-LIV compiles the sources ingested by the user into a linked theology
vault (sources, entities, concepts). A team of specialist agents reads each
source through its own specialty and writes attributed pages. This document
is the team's shared self-image: what the brain knows, who wrote what,
and what it just learned.
"""


def _agent_contribution_counts(bridge, vault, profiles) -> dict[str, int]:
    """Pages tagged per agent, counted ONE way for everyone (writer, checker
    and panel must agree or the doc will drift-fail against itself).
    Word-boundary match, so 'Apologete' never claims pages tagged
    'Apologete Catholique'."""
    counts = {p.name: 0 for p in profiles}
    if not profiles:
        return counts
    hay = None
    try:
        for _dirname, p in bridge._iter_pages(vault):
            meta, _body = bridge._read_page(p)
            hay = " ".join(str(meta.get("tags") or "").lower().split())
            if not hay:
                continue
            for profile in profiles:
                if re.search(r"\b" + re.escape(profile.name.lower()) + r"\b", hay):
                    counts[profile.name] += 1
    except Exception as e:
        print(f"[Agents] contribution recount failed: {e}")
    return counts


def refresh_self_knowledge(bridge, profiles, recent=[]) -> str:
    """Regenerate the team's self-knowledge doc inside the vault.

    Only the AUTO blocks are rewritten; the hand-written identity survives
    a round-trip untouched. AUTO blocks:
      status           — page counts per kind + raw sources
      agents           — the profiles the team currently comprises
      contributions    — pages tagged per agent, so each agent knows its own work
      recent learning  — the last ingested sources and what came of them
    Returns the doc path, empty string when the vault is unavailable.
    """
    try:
        vault = bridge._vault()
        counts = {}
        agent_pages = _agent_contribution_counts(bridge, vault, profiles)
        for dirname, path in bridge._iter_pages(vault):
            counts[dirname] = counts.get(dirname, 0) + 1
        n_raw = len([p for p in (vault / "raw").glob("*") if p.is_file()])
    except Exception as e:
        print(f"[Agents] self-knowledge refresh skipped: {e}")
        return ""

    doc = vault / _SELF_DOC
    doc.parent.mkdir(parents=True, exist_ok=True)

    lines = [("\n<!-- AUTO-START: status -->"),
             f"## Vault schema — {sum(counts.values())} page(s), {n_raw} raw source(s)",
             ""]
    for kind in ("sources", "entities", "concepts", "synthesis"):
        lines.append(f"- {kind}: {counts.get(kind, 0)}")
    lines += ["", "<!-- AUTO-END: status -->", "",
              "<!-- AUTO-START: agents -->", "## Agents of the team", ""]
    if profiles:
        for profile in profiles:
            brief = " ".join((profile.brief or "").split())[:120]
            lines.append(f"- **{profile.name}** — {brief}")
    else:
        lines.append("- _(none at present)_")
    lines += ["", "<!-- AUTO-END: agents -->", "",
              "<!-- AUTO-START: contributions -->", "## Pages written per agent", ""]
    if profiles:
        for name, n in sorted(agent_pages.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {name}: {n} page(s) tagged")
    else:
        lines.append("- _(no agent has written yet)_")
    lines += ["", "<!-- AUTO-END: contributions -->", "",
              "<!-- AUTO-START: recent -->", "## Latest learning", ""]
    lines += [f"- {r}" for r in recent[:12]] or ["- _(nothing yet)_"]
    lines += ["", "<!-- AUTO-END: recent -->",
              "", "## Deeper", "",
              "- Full index: `wiki/index.md` — chronological operations: `wiki/log.md`.",
              "- User project state (hand-written, yours): `MEMORY.md`.", ""]
    auto = "\n".join(lines)

    # Round-trip: the existing file's non-AUTO content survives untouched.
    if doc.exists():
        text = doc.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"\n<!-- AUTO-START: \w+ -->.*?<!-- AUTO-END: \w+ -->\n",
                      "", text, flags=re.DOTALL)
        out = text.strip() + "\n\n" + auto
    else:
        out = _IDENTITY + "\n" + auto
    try:
        doc.write_text(out, encoding="utf-8")
        return str(doc)
    except Exception as e:
        print(f"[Agents] self-knowledge doc write failed: {e}")
        return ""


# ── Drift checker ────────────────────────────────────────────────────────────

def check_drift(bridge, profiles=None) -> list[str]:
    """Vérifie le doc de self-knowledge contre la réalité du vault et du
    dossier d'agents : toute référence [[Titre]], tout nom d'agent et tout
    compte de contribution doivent encore être vrais. Retourne une liste de
    constats de dérive (liste vide = doc aligné). Ne modifie rien."""
    findings: list[str] = []
    try:
        vault = bridge._vault()
    except Exception as e:
        return [f"vault inaccessible : {e}"]
    doc = vault / _SELF_DOC
    if not doc.exists():
        return ["doc de self-knowledge absent — un rafraîchissement le créera"]
    text = doc.read_text(encoding="utf-8", errors="replace")
    if profiles is None:
        profiles = discover_agents()

    titles = set()
    try:
        for _dirname, p in bridge._iter_pages(vault):
            meta, _body = bridge._read_page(p)
            titles.add(bridge._page_title(p, meta))
    except Exception as e:
        findings.append(f"lecture du vault impossible : {e}")
    for match in re.finditer(r"\[\[([^\]\]()]+)\]\]", text):
        ref = match.group(1).strip()
        if ref and ref not in titles:
            findings.append(f"référence morte [[{ref}]] — page absente du vault")

    known = {p.name for p in profiles}
    for match in re.finditer(r"^- \*\*(.+?)\*\*", text, flags=re.MULTILINE):
        name = match.group(1).strip()
        if known and name not in known:
            findings.append(f"agent fantôme « {name} » — profil absent du dossier d'agents")

    stated = dict(re.findall(r"^- (.+?): (\d+) page\(s\) tagged$",
                             text, flags=re.MULTILINE))
    if stated:
        actual = _agent_contribution_counts(bridge, vault, profiles or [])
        for name, n in stated.items():
            try:
                n_int = int(n)
            except ValueError:
                findings.append(f"compte illisible pour {name} : {n}")
                continue
            real = actual.get(name, 0)
            if n_int != real:
                findings.append(f"compte périmé pour {name} : {n_int} dans le doc, "
                                f"{real} réel dans le vault")

    for rel in ("wiki/index.md", "wiki/log.md", "MEMORY.md"):
        if not (vault / rel).exists():
            findings.append(f"pièce structurelle absente : {rel}")
    return findings


def refresh_context_mirror(bridge, pages, new_titles, sources) -> str:
    """Slim self-knowledge slice for the assistant's prompt (long_term.json):
    a few factual sentences about what the brain now knows, so questions about
    an ingested topic get an instant, grounded answer next turn."""
    try:
        heads = ", ".join(new_titles[:6])
        text = (f"Theology vault: {pages} linked pages over {sources} ingested "
                f"source(s). Recently learned: {heads}.")
        if hasattr(bridge, "update_context_mirror"):
            return bridge.update_context_mirror(text)
        return "mirror helper absent"
    except Exception as e:
        return f"mirror failed: {e}"


# ── The per-agent learning pipeline ──────────────────────────────────────────

def _load_file_processor():
    """Load actions/file_processor.py by path (actions/ is not a package)."""
    try:
        path = Path(__file__).resolve().with_name("file_processor.py")
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("markliv_file_processor", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[Agents] could not load file_processor: {e}")
        return None


def learn_with_agents(paths, profiles, player=None, step=None) -> str:
    """Hand each source to each selected agent, one by one.

    For every (file, agent) pairing the agent reads the text through its own
    persona and writes its pages into the theology_brain vault — a source page
    tagged with its name, plus its entities and concepts, each body starting
    with an 'Agent: <name>' attribution line. step(done, total, label) reports
    progress to the ingestion window. Never raises.
    """
    fp = _load_file_processor()
    if fp is None:
        return "Apprentissage par agents : file_processor introuvable."
    bridge = fp._theology_brain_module()
    if bridge is None:
        return ("Apprentissage par agents : theology_brain introuvable — "
                "impossible d'écrire dans le vault.")
    try:
        bridge.run({"action": "init"})
    except Exception as e:
        print(f"[Agents] vault init failed: {e}")

    total_units = max(len(paths) * len(profiles), 1)
    done = 0
    totals = {"source": 0, "entity": 0, "concept": 0}
    processed, failed = [], []
    new_titles: list[str] = []
    agent_failed: dict[str, int] = {}

    # The brain's state BEFORE this ingestion: every selected agent sees this
    # snapshot, so it cross-links to existing pages instead of inventing
    # near-duplicates. This is the vault teaching its agents, batch by batch.
    vault_context = ""
    try:
        vault_context = bridge.vault_context() if hasattr(bridge, "vault_context") else ""
    except Exception as e:
        print(f"[Agents] vault context unavailable: {e}")

    for path in paths:
        if step:
            try:
                step(done, total_units, f"{path.name} — lecture")
            except Exception:
                pass
        try:
            bridge.run({"action": "capture", "path": str(path)})
        except Exception as e:
            print(f"[Agents] capture failed for {path.name}: {e}")

        text = fp._extract_source_text(path)
        if not text.strip():
            failed.append(f"{path.name} (aucun texte exploitable)")
            continue

        for index, agent in enumerate(profiles, 1):
            if step:
                try:
                    step(done, total_units, f"{agent.name} — {path.name} — structuration")
                except Exception:
                    pass
            data = fp._theology_structure(text, path.name, persona=agent,
                                          vault_context=vault_context)
            written = 0
            if isinstance(data, dict) and data:
                src = data.get("source")
                if isinstance(src, dict) and str(src.get("title") or "").strip():
                    new_titles.append(str(src["title"]).strip())
                try:
                    written = fp._write_structure(
                        bridge, data, f"{path.name} — {agent.name}", totals,
                        agent_name=agent.name)
                except Exception as e:
                    print(f"[Agents] write failed for {agent.name}/{path.name}: {e}")
            if written:
                processed.append(f"{agent.name} → {path.name} ({written} page(s))")
                if player:
                    try:
                        player.write_log(
                            f"[Agents] {agent.name}: {path.name} → {written} page(s)")
                    except Exception:
                        pass
            else:
                agent_failed[agent.name] = agent_failed.get(agent.name, 0) + 1
                if player:
                    try:
                        player.write_log(
                            f"[Agents] {agent.name}: rien écrit pour {path.name}")
                    except Exception:
                        pass
            done += 1
            if step:
                try:
                    step(done, total_units, f"{agent.name} — {path.name} — terminé")
                except Exception:
                    pass

    pages = totals["source"] + totals["entity"] + totals["concept"]

    # Self-improvement, batch end: the team's doc re-renders and the prompt
    # mirror learns the new state, so the next question about these topics
    # gets a grounded answer without any re-ingestion.
    self_doc = refresh_self_knowledge(bridge, profiles, recent=processed)
    mirror = refresh_context_mirror(bridge, pages, new_titles, len(paths))
    summary = (f"Apprentissage par agents ({len(profiles)} × {len(paths)} source(s)) : "
               f"{pages} page(s) écrite(s) — {totals['source']} source(s), "
               f"{totals['entity']} entité(s), {totals['concept']} concept(s).")
    if processed:
        shown = " | ".join(processed[:12])
        if len(processed) > 12:
            shown += f" | … et {len(processed) - 12} autres"
        summary += " " + shown + "."
    if failed:
        summary += " Sources sans texte : " + ", ".join(failed) + "."
    if agent_failed:
        worst = ", ".join(f"{name} ({n})" for name, n in
                          sorted(agent_failed.items(), key=lambda kv: -kv[1])[:5])
        summary += f" Structurations sans résultat : {worst}."
    if self_doc:
        summary += f" Self-knowledge mise à jour ({self_doc}) ; {mirror}."
    return summary
