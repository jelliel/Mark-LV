"""
Every model call the research engine makes, funnelled through core/gemini.py.

There is deliberately no model name in this file, and no second SDK client.
`core/gemini.py` already owns the measured ladder, the per-model cooldowns and
the deadline every call carries; a research engine that opened its own client
would be the sixteenth file that did that, and the first to hang when an alias
went unwell.

The three tiers used here:

    gemini.FAST    triage, query writing, short classification
    gemini.SMART   reading notes, analysis, the report
    gemini.SEARCH  grounded search fallback (REST only — no Live equivalent)

`ask()` returns "" rather than raising when every rung is out of quota. A
research run that loses its writer still has a plan, sources and notes; the
engine degrades to a report built from those instead of losing the run.
"""
from __future__ import annotations

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))


def _gemini():
    from core import gemini          # imported late: keeps boot discovery cheap
    return gemini


def available() -> bool:
    """Whether a key is configured at all. A run without one is pointless, and
    saying so in one line beats fifteen failed calls."""
    try:
        return bool(_gemini().api_key())
    except Exception:
        return False


def ask(prompt: str, tier: str = "", timeout_ms: int = 60_000,
        system: str = "", default: str = "") -> str:
    """One generation, reduced to text. Never raises."""
    g = _gemini()
    config = {"system_instruction": system} if system else None
    try:
        return g.text(prompt, tier=tier or g.SMART, config=config,
                      timeout_ms=timeout_ms, default=default)
    except Exception as e:
        print(f"[Research] LLM call failed: {type(e).__name__}: {e}")
        return default


def ask_json(prompt: str, tier: str = "", timeout_ms: int = 60_000,
             system: str = "", default=None):
    """One generation parsed as JSON, tolerating fences and prose around it."""
    g = _gemini()
    config = {"system_instruction": system} if system else None
    try:
        return g.as_json(prompt, tier=tier or g.SMART, config=config,
                         timeout_ms=timeout_ms, default=default)
    except Exception as e:
        print(f"[Research] LLM JSON call failed: {type(e).__name__}: {e}")
        return default
