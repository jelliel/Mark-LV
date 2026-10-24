"""
MARK-LIV action — brain panel (état du second cerveau).

Ouvre le panneau Theologicus dans l'application (pas de navigateur),
et affiche les données du vault en temps réel.

Demande naturelle : « état du second cerveau », « que sait le brain ? »,
« montre-moi le vault ».
"""

import importlib.util
import json
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent


def _modules():
    actions = Path(__file__).resolve()
    spec = importlib.util.spec_from_file_location(
        "panel_file_processor", actions.with_name("file_processor.py"))
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    bridge = fp._theology_brain_module()
    agents = fp._load_theology_agents()
    return agents, bridge


def _collect(agents, bridge, profiles) -> dict:
    """Tout ce que le panneau affiche, mesuré maintenant — jamais stocké."""
    vault = bridge._vault()
    counts = {kind: 0 for kind in ("sources", "entities", "concepts", "synthesis")}
    contributions: dict[str, int] = agents._agent_contribution_counts(
        bridge, vault, profiles)
    for dirname, p in bridge._iter_pages(vault):
        counts[dirname] = counts.get(dirname, 0) + 1
    n_raw = len([p for p in (vault / "raw").glob("*") if p.is_file()])
    log_tail = ""
    logp = vault / "wiki" / "log.md"
    if logp.exists():
        lines = logp.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        log_tail = "\n".join(lines[-14:])
    doc = vault / agents._SELF_DOC
    doc_state = f"présent ({doc})" if doc.exists() else "ABSENT — un rafraîchissement le créera"
    findings = agents.check_drift(bridge, profiles)
    total = sum(counts.values())
    return {
        "path": str(vault),
        "total": total, "counts": counts, "n_raw": n_raw,
        "profiles": [p.name for p in profiles] if profiles else [],
        "contributions": contributions,
        "log_tail": log_tail, "doc_state": doc_state, "findings": findings,
    }


def brain_panel(parameters: dict, player=None) -> str:
    """Ouvre le panneau Theologicus dans l'application."""
    agents, bridge = _modules()
    if agents is None or bridge is None:
        return "Modules théologie introuvables — panneau impossible."
    try:
        bridge.run({"action": "init"})
    except Exception:
        pass

    data = _collect(agents, bridge, agents.discover_agents())

    # Ouvrir le panneau dans l'application (pas de navigateur)
    if player is not None:
        try:
            player.show_brain_panel(data)
        except Exception as e:
            print(f"[BrainPanel] in-app panel failed: {e}")
            return "Erreur lors de l'ouverture du panneau Theologicus."

    return (f"Second cerveau : {data['total']} page(s), {data['n_raw']} raw source(s), "
            f"{len(data['profiles'])} agent(s), "
            f"dérive : {len(data['findings'])}. Panneau Theologicus ouvert.")


TOOL = {
    "name": "brain_panel",
    "description": (
        "Opens the second-brain state window for Mark-LIV's theology vault: "
        "live page counts (sources/entities/concepts/synthesis), raw sources, "
        "the agent team with each agent's page count, the latest learning log, "
        "the self-knowledge doc state and any drift findings. Use when the "
        "user asks 'état du second cerveau', 'what does the brain know', "
        "'montre-moi le vault', or wants to see/heal the vault's "
        "self-knowledge doc."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "handler": brain_panel,
}
