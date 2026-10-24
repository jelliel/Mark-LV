"""
MARK-LIV action — brain panel (état du second cerveau).

Ouvre l'interface HTML sci-fi Theologicus dans le navigateur par défaut,
et fournit les données du vault en temps réel via localStorage.

Demande naturelle : « état du second cerveau », « que sait le brain ? »,
« montre-moi le vault ».
"""

import importlib.util
import json
import webbrowser
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
_HTML_PATH = _BASE_DIR / "dashboard" / "static" / "theologicus.html"


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
    """Ouvre l'interface HTML Theologicus avec les données du vault intégrées."""
    agents, bridge = _modules()
    if agents is None or bridge is None:
        return "Modules théologie introuvables — panneau impossible."
    try:
        bridge.run({"action": "init"})
    except Exception:
        pass

    data = _collect(agents, bridge, agents.discover_agents())

    # Lire le template HTML
    if not _HTML_PATH.exists():
        return "Interface HTML Theologicus introuvable."

    html_template = _HTML_PATH.read_text(encoding="utf-8")

    # Inject VAULT_DATA into the template (template has const VAULT_DATA = null;)
    vault_js = f"""
        const VAULT_DATA = {json.dumps(data, indent=2, ensure_ascii=False)};
        function loadVaultData() {{
            renderVaultData(VAULT_DATA);
            addLog('sys', 'Vault chargé: ' + VAULT_DATA.total + ' page(s), ' + VAULT_DATA.n_raw + ' raw');
        }}
        loadVaultData();
    """

    html_content = html_template.replace(
        'const VAULT_DATA = null;',
        vault_js
    )

    # Écrire le HTML généré
    generated_html = _BASE_DIR / "dashboard" / "static" / "theologicus_generated.html"
    try:
        generated_html.write_text(html_content, encoding="utf-8")
    except Exception as e:
        print(f"[BrainPanel] impossible d'écrire le HTML: {e}")
        return "Erreur lors de la génération de l'interface."

    # Ouvrir l'interface dans le navigateur
    webbrowser.open(generated_html.as_uri())

    if player:
        try:
            player.write_log("[BrainPanel] interface Theologicus ouverte")
        except Exception:
            pass

    return (f"Second cerveau : {data['total']} page(s), {data['n_raw']} raw source(s), "
            f"{len(data['profiles'])} agent(s), "
            f"dérive : {len(data['findings'])}. Interface Theologicus ouverte.")


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
