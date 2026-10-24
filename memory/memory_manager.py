import json
import re
from datetime import datetime
from pathlib import Path
import sys

from threading import Lock

# ── Memory store location ───────────────────────────────────────────────────
MEMORY_PATH      = Path(__file__).resolve().parent.parent / "memory" / "long_term.json"
_lock            = Lock()

# ── Core memory budget ──────────────────────────────────────────────────────
MEMORY_MAX_CHARS  = 200_000
PROMPT_CORE_CHARS = 900
PROMPT_INDEX_CHARS = 420
PROMPT_MAX_PER_CATEGORY = 6

# ── Why there are two very different numbers here ────────────────────────────
# There used to be one: MEMORY_MAX_CHARS = 2200, applied to the whole store. It
# was a *storage* limit, and it existed only because the entire memory was
# pasted into the system prompt on every connect — so growing the memory grew
# every single request. When it filled, _trim_to_limit() deleted the oldest
# entries and printed one line to a console nobody reads. A memory described as
# "deeply remembers projects, preferences and personal context" was in practice
# two pages long, and quietly forgot your sister's name after a few weeks.
# Storage and prompt budget are now separate concerns:
#   MEMORY_MAX_CHARS  — a runaway guard, not a feature limit. Nothing normal
#                       reaches it; a bug writing in a loop does.
#   PROMPT_CORE_CHARS — what actually rides in the system prompt every session.
#                       Smaller than the old whole-memory dump, so sessions
#                       start *faster* than before, not slower.
# Everything above the core stays on disk and is fetched on demand by the
# recall_memory tool — see search_memory() and format_memory_for_prompt().
# ── End of budget section ───────────────────────────────────────────────────

# ── Theological metadata persistence ────────────────────────────────────────
# Cross-session continuity: remember doctrine, authority, category patterns
# so subsequent sessions benefit from prior theological analysis.

def ensure_theological_dir() -> None:
    """Ensure the theological metadata directory exists."""
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

def save_theological_metadata(metadata: dict) -> None:
    """Persist theological metadata to long_term.json for cross-session continuity.

    Stores doctrine, authority weight, category, and query patterns so subsequent
    sessions can benefit from prior theological analysis without re-spending quota.
    """
    ensure_theological_dir()
    try:
        lt = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        lt = {}
    lt["theological_metadata"] = metadata
    # Track the query that produced this metadata
    q = metadata.get("query", "")
    if q:
        lt["last_theological_query"] = q[:300]
    # Track patterns for smarter routing
    patterns = metadata.get("patterns", {})
    if patterns:
        lt.setdefault("theological_patterns", {}).update(patterns)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(
        json.dumps(lt, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def _load_long_term() -> dict:
    """Read long_term.json safely, returning {} when absent or unparseable."""
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_theological_metadata() -> dict:
    """Load previously saved theological metadata from long_term.json."""
    lt = _load_long_term()
    return lt.get("theological_metadata", {})

def get_last_theological_query() -> str:
    """Get the last theological query that was processed."""
    lt = _load_long_term()
    return lt.get("last_theological_query", "")

def get_theological_patterns() -> dict:
    """Get stored theological patterns for smarter routing."""
    lt = _load_long_term()
    return lt.get("theological_patterns", {})


# ── Session memory ─────────────────────────────────────────────────────────────