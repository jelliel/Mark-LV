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
import re
from dataclasses import dataclass, field
from pathlib import Path

AGENTS_DIR_KEY = "theology_agents_dir"   # optional override in config/api_keys.json
_BRIEF_CHARS   = 900                     # persona size handed to the model
_NAME_PREFIX   = "agent-"

@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    path: Path | None = field(default=None, compare=False)

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "tools": list(self.tools), "builtin": self.builtin,
                "path": str(self.path or "")}


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
    except Exception as e:
        print(f"[Agents] agent unreadable {path.name}: {e}")
        return None
    if not brief or brief.strip() == "":
        return None
    return AgentProfile(name=_clean_name(path.stem), description=brief, path=path)


def discover_agents(agents_dir=None, logger=print) -> list[AgentProfile]:
    """Every agent profile in the folder, sorted by name. Top level only —
    subfolders such as 'AI Prompts' hold prompt collections, not agents."""
    root = Path(agents_dir) if agents_dir else get_agents_dir()
    if not root.is_dir():
        logger(f"[Agents] folder not found: {root}")
        return []
    profiles = []
    for path in sorted(root.glob("*.md")):
        if path.name.startswith(("_", ".")):
            continue
        profile = _profile_from_path(path)
        if profile is None:
            logger(f"[Agents] skipped (no name/brief): {path.name}")
            continue
        if profile.name in [p.name for p in profiles]:
            logger(f"[Agents] duplicate agent name: {profile.name}")
            continue
        profiles.append(profile)
    logger(f"[Agents] {root} -> {len(profiles)} agent(s)")
    return profiles


def get_agents_dir() -> Path:
    """The agent folder as configured, or Desktop/Agents by default."""
    override = None  # TODO: read from config if needed
    if override:
        return Path(str(override)).expanduser()
    return Path.home() / "Desktop" / "Agents"


# ── Per-agent learning pipeline ────────────────────────────────────────────

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

    doc = vault / "_self_knowledge.md"
    doc.parent.mkdir(parents=True, exist_ok=True)

    lines = [("# MARK-LIV Theology — Self-Knowledge of the Team"),
             (""),
             ("_Identity section written by hand. The AUTO blocks are regenerated "
              "after each ingestion — never edited by hand. (Pattern: a living "
              "\"self-knowledge\" doc, AUTO blocks marked by HTML comments, "
              "refreshed metadata never touching the hand-written sections.)_"),
             ("## Identity"),
             ("MARK-LIV compiles the sources ingested by the user into a linked "
              "theology vault (sources, entities, concepts). A team of specialist agents "
              "reads each source through its own specialty and writes attributed pages. "
              "This document is the team's shared self-image: what the brain knows, "
              "who wrote what, and what it just learned."),
             (""),
             ("<!-- AUTO-START: status -->"),
             (f"## Vault schema — {sum(counts.values())} page(s), {n_raw} raw source(s)"),
             (""),
             ("<!-- AUTO-START: agents -->"),
             ("## Agents of the team"),
             (""),
    ]
    if profiles:
        for profile in profiles:
            brief = (profile.description or "")[:120]
            lines.append(f"- **{profile.name}** — {brief}")
    else:
        lines.append("- _(none at present)_")
    lines += ["",
                "<!-- AUTO-END: agents -->",
                "",
                "<!-- AUTO-START: contributions -->",
                "## Pages written per agent",
                ""]
    if profiles:
        for name, n in sorted(_agent_contribution_counts(bridge, vault, profiles).items(),
                              key=lambda kv: -kv[1]):
            lines.append(f"- {name}: {n} page(s) tagged")
    else:
        lines.append("- _(no agent has written yet)_")
    lines += ["",
                "<!-- AUTO-END: contributions -->",
                "",
                "<!-- AUTO-START: recent -->",
                "## Latest learning",
                ""]
    # Insert crossover blocks before AUTO-END: recent
    if hasattr(bridge, "_crossover_topics") and bridge._crossover_topics:
        co = bridge._crossover_topics
        lines.append("<!-- Crossover references from inter-agent knowledge web -->")
        for agent_name, topics in co.items():
            lines.append(f"## {agent_name} — See also (from other agents)")
            novel_all = set()
            for other_name, other_topics in co.items():
                if other_name != agent_name:
                    novel_all.update(other_topics)
            for topic in sorted(novel_all)[:3]:
                lines.append(f"- {topic}")
            lines.append("")
    lines += ["",
              "<!-- AUTO-END: recent -->",
              "",
              "## Deeper",
              "",
              "- Full index: `wiki/index.md` — chronological operations: `wiki/log.md`.",
              "- User project state (hand-written, yours): `MEMORY.md`.",
              ""]
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


# ── The per-agent learning pipeline ──────────────────────────────────────────

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

    # ── Inter-agent crossover ──────────────────────────────────────────────
    # Each agent's writing is enriched by referencing other agents' previous
    # contributions, creating a compounding knowledge effect across the team.
    # This section runs after all agents have finished, weaving together
    # the self-knowledge doc so subsequent sessions benefit from the compounded
    # knowledge.

    # Build crossover references: each agent's pages reference other agents'
    # previously written topics, creating a knowledge web.
    if profiles:
        # Read existing vault pages to discover what each agent has already written
        agent_topics: dict[str, set[str]] = {}
        for agent in profiles:
            agent_topics[agent.name] = set()
            try:
                vault = bridge._vault()
                for _dirname, p in bridge._iter_pages(vault):
                    meta, body = bridge._read_page(p)
                    tags = str(meta.get("tags") or "").lower()
                    # Check if this page is tagged with this agent's name
                    if re.search(r"\b" + re.escape(agent.name.lower()) + r"\b", tags):
                        # Extract concept/entity tags from the page body
                        concept_tags = re.findall(r"concept:\s*(\S+)", body, re.I)
                        entity_tags = re.findall(r"entity:\s*(\S+)", body, re.I)
                        agent_topics[agent.name].update(concept_tags)
                        agent_topics[agent.name].update(entity_tags)
            except Exception as e:
                print(f"[Agents] crossover topic scan failed for {agent.name}: {e}")

        # Generate crossover references: each agent gets a 'See also' block
        # referencing other agents' topics, and vice versa
        crossover_lines: list[str] = []
        for agent in profiles:
            my_topics = agent_topics.get(agent.name, set())
            others_topics = set()
            for other in profiles:
                if other.name != agent.name:
                    others_topics.update(agent_topics.get(other.name, set()))
            # Topics this agent hasn't covered but others have
            novel = others_topics - my_topics
            if novel:
                crossover_lines.append(f"## {agent.name} — See also")
                for topic in sorted(novel)[:5]:  # top 5 novel topics
                    crossover_lines.append(f"- {topic}")
                crossover_lines.append("")

        # Insert crossover blocks into the self-knowledge doc before the AUTO-END: recent
        # We'll embed them via the self-knowledge refresh; the refresh function
        # will prepend these before <!-- AUTO-END: recent -->
        # Store the crossover data in the bridge's persistent state for the next run
        try:
            if not hasattr(bridge, "_crossover_topics"):
                bridge._crossover_topics = {}
            bridge._crossover_topics = agent_topics
        except Exception as e:
            print(f"[Agents] crossover state save failed: {e}")
    else:
        crossover_applied = False

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