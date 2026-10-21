"""
MARK-LIV action — brain panel (état du second cerveau).

Une fenêtre qui montre ce que le brain sait VRAIMENT, mesuré sur dis au à
l'instant : comptes par type, raw sources, l'équipe d'agents et combien de
pages chacun a écrites, les derniers apprentissages du log, l'état du doc
de self-knowledge et les dérives éventuelles. Bouton « Rafraîchir » qui
re-rend le doc et vérifie la dérive sur-le-champ.

Demande naturelle : « état du second cerveau », « que sait le brain ? »,
« montre-moi le vault ».
"""

import importlib.util
from pathlib import Path


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
    """Tout ce que la fenêtre affiche, mesuré maintenant — jamais stocké.
    Les contributions passent par le compteur unique de theology_agents,
    pour matcher exactement le doc de self-knowledge et sa dérive."""
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
        "path": vault,
        "total": total, "counts": counts, "n_raw": n_raw,
        "profiles": profiles, "contributions": contributions,
        "log_tail": log_tail, "doc_state": doc_state, "findings": findings,
    }


def _xload_qt():
    from PyQt6.QtCore import QMetaObject, QObject, Qt, QThread, pyqtSlot
    from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                                 QPlainTextEdit, QPushButton, QVBoxLayout)
    return (QMetaObject, QObject, Qt, QThread, pyqtSlot, QApplication, QDialog,
            QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)


def brain_panel(parameters: dict, player=None) -> str:
    """Ouvre la fenêtre d'état du second cerveau. Retourne un résumé texte."""
    try:
        (QMetaObject, QObject, Qt, QThread, pyqtSlot,
         QApplication, QDialog, QHBoxLayout, QLabel,
         QPlainTextEdit, QPushButton, QVBoxLayout) = _xload_qt()
    except Exception as e:
        return f"Fenêtre Qt indisponible : {e}"
    app = QApplication.instance()
    if app is None:
        return "Pas d'application graphique en cours — panneau impossible."

    agents, bridge = _modules()
    if agents is None or bridge is None:
        return "Modules théologie introuvables — panneau impossible."
    try:
        bridge.run({"action": "init"})
    except Exception:
        pass
    data = _collect(agents, bridge, agents.discover_agents())

    class Panel(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("MARK-LIV — État du second cerveau")
            self.setMinimumWidth(560)
            box = QVBoxLayout(self)
            head = QLabel(f"<b>{data['total']} page(s)</b> — "
                          f"{data['counts']['sources']} source(s), "
                          f"{data['counts']['entities']} entité(s), "
                          f"{data['counts']['concepts']} concept(s), "
                          f"{data['counts']['synthesis']} synthèse(s) — "
                          f"{data['n_raw']} raw source(s)")
            head.setWordWrap(True)
            box.addWidget(head)
            box.addWidget(QLabel(f"Vault : {data['path']}"))
            box.addWidget(QLabel(f"Doc self-knowledge : {data['doc_state']}"))

            drift = data["findings"]
            if drift:
                drift_text = ("⚠ Dérive (" + str(len(drift)) + ") :\n"
                              + "\n".join("— " + f for f in drift[:10]))
            else:
                drift_text = "✓ Dérive : 0 — doc de self-knowledge aligné."
            self.drift_label = QLabel(drift_text.replace("\n", "<br>"))
            self.drift_label.setWordWrap(True)
            box.addWidget(self.drift_label)

            box.addWidget(QLabel("<b>Agents et contributions</b>"))
            self.members = QPlainTextEdit()
            self.members.setReadOnly(True)
            self.members.setMinimumHeight(150)
            self._fill_members(data)
            box.addWidget(self.members, 1)

            box.addWidget(QLabel("<b>Derniers apprentissages (log)</b>"))
            self.logview = QPlainTextEdit()
            self.logview.setReadOnly(True)
            self.logview.setPlainText(data["log_tail"] or "(log vide)")
            self.logview.setMinimumHeight(110)
            box.addWidget(self.logview, 1)

            row = QHBoxLayout()
            row.addStretch(1)
            refresh = QPushButton("Rafraîchir le self-knowledge")
            refresh.clicked.connect(self._refresh)
            row.addWidget(refresh)
            close = QPushButton("Fermer")
            close.clicked.connect(self.accept)
            row.addWidget(close)
            box.addLayout(row)

        def _fill_members(self, d):
            lines = [f"• {p.name} — {d['contributions'].get(p.name, 0)} page(s) taggée(s)"
                     for p in (d["profiles"] or [])]
            self.members.setPlainText("\n".join(lines) or "(aucun agent trouvé)")

        def _refresh(self):
            try:
                doc = agents.refresh_self_knowledge(bridge, data["profiles"])
                fresh = _collect(agents, bridge, data["profiles"])
                data.update(fresh)
                self._fill_members(data)
                drift = data["findings"]
                self.drift_label.setText(
                    (f"⚠ Dérive ({len(drift)}) :<br>" + "<br>".join(
                        "— " + f for f in drift[:10]))
                    if drift else "✓ Dérive : 0 — doc de self-knowledge aligné.")
                self.logview.setPlainText(data["log_tail"] or "(log vide)")
                if player:
                    try:
                        player.write_log(f"[BrainPanel] doc ré-généré ({doc or 'échec'})")
                    except Exception:
                        pass
            except Exception as e:
                self.drift_label.setText(f"Rafraîchissement en échec : {e}")

    keep_alive = []

    def show_panel():
        panel = Panel()
        panel.show()
        panel.raise_()
        panel.activateWindow()
        if player:
            try:
                player.write_log("[BrainPanel] état du second cerveau affiché")
            except Exception:
                pass
        panel.exec()
        keep_alive.append(panel)

    if QThread.currentThread() == app.thread():
        show_panel()
    else:
        class _OnGuiThread(QObject):
            @pyqtSlot()
            def run(self):
                show_panel()
        caller = _OnGuiThread()
        keep_alive.append(caller)
        caller.moveToThread(app.thread())
        QMetaObject.invokeMethod(caller, "run", Qt.ConnectionType.QueuedConnection)

    return (f"Second cerveau : {data['total']} page(s), {data['n_raw']} raw source(s), "
            f"{len(data['profiles'])} agent(s), "
            f"dérive : {len(data['findings'])}.")


TOOL = {
    "name": "brain_panel",
    "description": (
        "Opens the second-brain state window for Mark-LIV's theology vault: "
        "live page counts (sources/entities/concepts/synthesis), raw sources, "
        "the agent team with each agent's page count, the latest learning log, "
        "the self-knowledge doc state and any drift findings. Use when the "
        "user asks 'état du second cerveau', 'what does the brain know', "
        "'montre-moi le vault', or wants to see/heal the vault's "
        "self-knowledge doc. The refresh button re-renders the doc and "
        "re-checks drift immediately."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "handler": brain_panel,
}
