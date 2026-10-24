"""
Drop-in MARK-LIV plugin — Agent Beacon.

Wraps the `beacon` CLI (https://github.com/Asymptote-Labs/agent-beacon) so
JARVIS can report on AI-agent session capture by voice: endpoint status,
recent traces, and the local dashboard.

Requires the Beacon Endpoint Agent to be installed on this machine and the
`beacon` command on PATH. Local mode recommended (no cloud forwarding):
    beacon endpoint install   # choose Local when prompted
Everything is read-only here — this plugin never changes beacon's state.

Copy-paste this file into plugins/ (already named correctly); MARK-LIV
discovers it automatically at startup. Contract follows plugins/_template.py:
PLUGIN dict + run(parameters, player, session_memory) -> str, never raise.
"""

import json
import shutil
import subprocess
from datetime import datetime

PLUGIN = {
    "name": "agent_beacon",
    "description": (
        "Agent Beacon telemetry: status of AI-agent session capture, recent "
        "agent traces, and the local Beacon dashboard. Use when the user says "
        "'beacon', 'traces d'agents', 'sessions d'agents', 'que vois-tu des "
        "agents' or asks for the agent-activity dashboard. Do NOT use it for "
        "system health (that's system_monitor) or for running coding tasks "
        "(that's dev_agent)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "One of: 'status' (capture on/off, mode, endpoint health), "
                    "'traces' (summary of recent agent sessions), 'dashboard' "
                    "(open the local dashboard in the browser), 'help' (raw "
                    "beacon --help output)."
                ),
            },
            "limit": {
                "type": "NUMBER",
                "description": (
                    "For 'traces': how many recent sessions to summarize "
                    "(default 5, max 20)."
                ),
            },
        },
        "required": ["action"],
    },
}

_TRACE_LIMIT_DEFAULT = 5
_TRACE_LIMIT_MAX = 20
_CLI_TIMEOUT_S = 15


def _run_beacon(args: list[str]) -> tuple[int, str]:
    """Run `beacon ...`, return (returncode, combined output). Never raise."""
    try:
        proc = subprocess.run(
            ["beacon", *args],
            capture_output=True,
            text=True,
            timeout=_CLI_TIMEOUT_S,
            shell=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except FileNotFoundError:
        return 127, "beacon: command not found"
    except subprocess.TimeoutExpired:
        return 124, f"beacon {' '.join(args)}: timed out after {_CLI_TIMEOUT_S}s"
    except OSError as e:
        return 1, f"beacon: {e}"


def _beacon_available() -> bool:
    return shutil.which("beacon") is not None


def _summary_traces(limit: int) -> str:
    code, out = _run_beacon(["traces", "--json", "--last", str(limit)])
    if code == 127:
        return ("Monsieur, Beacon n'est pas installé sur cette machine. "
                "Installez l'agent d'endpoint depuis la page GitHub releases, "
                "puis relancez-moi.")
    if code != 0 or not out:
        return (f"JARVIS: Beacon n'a pas voulu lister les traces "
                f"(code {code}). {out[:200]}" if out else
                f"JARVIS: Beacon a répondu vide (code {code}).")

    sessions = []
    try:
        data = json.loads(out)
        sessions = data.get("traces", data if isinstance(data, list) else [])
    except json.JSONDecodeError:
        # Not JSON — fall back to the raw text, trimmed for speech.
        return f"JARVIS: Beacon répond : {out[:300]}"

    if not sessions:
        return ("JARVIS: Beacon tourne mais n'a capturé aucune session "
                "d'agent pour le moment.")

    lines = []
    for s in sessions[:limit]:
        agent = s.get("agent") or s.get("harness") or "agent inconnu"
        started = s.get("started_at") or s.get("timestamp") or ""
        when = ""
        if started:
            try:
                dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                when = dt.astimezone().strftime("%H:%M")
            except ValueError:
                when = str(started)[:16]
        tools = s.get("tool_calls", s.get("events", 0))
        lines.append(f"{agent} à {when}, {tools} événements" if when
                     else f"{agent}, {tools} événements")
    return ("JARVIS: " + f"{len(lines)} sessions récentes. "
            + ". ".join(lines) + ".")


def _summary_status() -> str:
    code, out = _run_beacon(["endpoint", "status"])
    if code == 127:
        return ("Monsieur, Beacon n'est pas installé. Je peux vous guider : "
                "MSI 'BeaconEndpointAgent' sur la page releases du dépôt "
                "agent-beacon, puis 'beacon endpoint install'.")
    if code != 0:
        return f"JARVIS: Impossible d'interroger l'endpoint Beacon : {out[:200]}"
    low = out.lower()
    if "not running" in low or "stopped" in low:
        return ("JARVIS: L'endpoint Beacon est installé mais arrêté. "
                "Dites 'démarre beacon' pour l'activer.")
    return f"JARVIS: Endpoint Beacon actif. {out[:250]}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    parameters: action (required), limit (optional, traces only).
    player: MARK-LIV instance — player.write_log(...) to log. May be None.
    session_memory: reserved, unused.
    Returns a short spoken string. Never raises.
    """
    action = str(parameters.get("action", "status")).strip().lower()
    try:
        if not _beacon_available():
            return ("Monsieur, la commande beacon est introuvable. Installez "
                    "d'abord l'agent d'endpoint, puis redémarrez-moi pour que "
                    "je la détecte.")

        if action == "status":
            result = _summary_status()
        elif action == "traces":
            try:
                limit = int(parameters.get("limit") or _TRACE_LIMIT_DEFAULT)
            except (TypeError, ValueError):
                limit = _TRACE_LIMIT_DEFAULT
            limit = max(1, min(limit, _TRACE_LIMIT_MAX))
            result = _summary_traces(limit)
        elif action == "dashboard":
            code, out = _run_beacon(["endpoint", "dashboard"])
            if code == 0:
                result = "JARVIS: J'ouvre le tableau de bord Beacon dans votre navigateur."
            elif code == 127:
                result = ("Monsieur, Beacon n'est pas installé, je ne peux pas "
                          "ouvrir le tableau de bord.")
            else:
                result = f"JARVIS: Le tableau de bord n'a pas voulu s'ouvrir : {out[:200]}"
        elif action == "help":
            code, out = _run_beacon(["--help"])
            result = out[:400] if out else f"beacon --help (code {code})"
        else:
            result = (f"JARVIS: Action Beacon inconnue '{action}'. Dites "
                      f"'statut beacon', 'traces d'agents' ou 'tableau de bord beacon'.")

        if player:
            try:
                player.write_log(f"JARVIS: {result}")
            except Exception:
                pass
        return result

    except Exception as e:  # absolute safety net — the loader catches too
        return f"Monsieur, agent_beacon a échoué : {e}"
