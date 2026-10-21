"""
MARK-LIV action — theology self-knowledge drift check.

Le pattern self-knowledge : le code (le vault) est la source, le doc
(Theology/self/mark-liv-theology.md) n'est qu'un rendu, et chaque ingestion
re-rend le doc. Le vérificateur de dérive attrape le moment où une référence
du doc devient fausse — page renommée, agent retiré, compte périmé — et le
signale AVANT que l'assistant ne se fie à un résumé devenu faux.

Demande naturelle : « vérifie la dérive du brain », « le doc est à jour ? ».
"""

import importlib.util
from pathlib import Path


def _modules():
    actions = Path(__file__).resolve()
    spec = importlib.util.spec_from_file_location(
        "selfcheck_file_processor", actions.with_name("file_processor.py"))
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    bridge = fp._theology_brain_module()
    agents = fp._load_theology_agents()
    return agents, bridge


def theology_self_check(parameters: dict, player=None) -> str:
    parameters = parameters or {}
    action = str(parameters.get("action") or "check").strip().lower()
    agents, bridge = _modules()
    if agents is None or bridge is None:
        return "Modules théologie introuvables — vérification impossible."
    try:
        bridge.run({"action": "init"})
    except Exception:
        pass

    profiles = agents.discover_agents()
    if action in ("refresh", "re-render", "regen"):
        doc = agents.refresh_self_knowledge(bridge, profiles)
        note = f"doc ré-généré ({doc}). " if doc else "doc non ré-généralisable. "
    else:
        note = ""

    findings = agents.check_drift(bridge, profiles)
    if not findings:
        return (note + "Dérive : 0 — le doc de self-knowledge est aligné sur "
                f"le vault et les {len(profiles)} agents.")
    lines = [f"Dérive : {len(findings)} constat(s)."]
    lines += [f"- {f}" for f in findings[:12]]
    if len(findings) > 12:
        lines.append(f"- … et {len(findings) - 12} autre(s)")
    lines.append("Un rafraîchissement (action='refresh') re-rend le doc et "
                 "relsève la plupart de ces constats.")
    if player:
        try:
            player.write_log(f"[SelfCheck] {len(findings)} dérive(s) du doc self-knowledge")
        except Exception:
            pass
    return "\n".join(lines)


TOOL = {
    "name": "theology_self_check",
    "description": (
        "Checks Mark-LIV's theology second brain for self-knowledge drift: "
        "dead [[page]] references, ghost agent names, per-agent contribution "
        "counts that no longer match the vault, missing structure pieces. "
        "Use when the user asks whether the brain's self-knowledge doc is up "
        "to date, asks to 'check the brain for drift', or after deleting/"
        "renaming vault pages. action='refresh' first re-renders the "
        "self-knowledge doc from the vault, then reports what is still off."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'check' (default) | 'refresh' — refresh re-renders "
                               "the doc from the vault before checking.",
            },
        },
        "required": [],
    },
    "handler": theology_self_check,
}
