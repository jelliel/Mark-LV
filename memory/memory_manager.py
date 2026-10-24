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


# ── Bibliographic registry ──────────────────────────────────────────────────
# Stable citation registry: each work gets a document_id with author, work,
# language, edition and locator (book/chapter/section). A locator is stable
# across editions — a page number is not. Vault pages reference their source
# by document_id; the verifier checks fidelity against the registered text.
# Lives in long_term.json under the "bibliographic" key so it survives
# sessions and stays in context like theological_metadata.

def save_bibliographic_entry(entry: dict) -> None:
    """Upsert one bibliographic entry keyed by document_id.

    Expected fields:
      document_id, author, work, language, edition, book, chapter, section,
      text_original, text_fr, source_url, source_type, verification_status
    Only document_id is required; missing fields are stored as-is."""
    ensure_theological_dir()
    lt = _load_long_term()
    lt.setdefault("bibliographic", {})
    doc_id = str(entry.get("document_id", "")).strip()
    if not doc_id:
        raise ValueError("bibliographic entry needs a document_id")
    # Merge with existing entry so partial updates don't wipe fields
    existing = lt["bibliographic"].get(doc_id, {})
    existing.update({k: v for k, v in entry.items() if v is not None})
    lt["bibliographic"][doc_id] = existing
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(
        json.dumps(lt, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_bibliographic_entry(document_id: str) -> dict | None:
    """Return one bibliographic entry by document_id, or None."""
    lt = _load_long_term()
    return lt.get("bibliographic", {}).get(str(document_id))


def list_bibliographic_entries() -> dict:
    """Return every bibliographic entry (document_id -> entry)."""
    lt = _load_long_term()
    return lt.get("bibliographic", {})


def find_bibliographic_entries(query: str) -> list[dict]:
    """Fuzzy search entries by author, work or document_id. Case-insensitive,
    substring match on the normalized text."""
    q = _normalise_text(query)
    if not q:
        return []
    matches = []
    for doc_id, entry in list_bibliographic_entries().items():
        hay = " ".join(str(entry.get(k, "")) for k in
                       ("document_id", "author", "work", "language", "edition"))
        if q in _normalise_text(hay):
            matches.append(entry)
    return matches


def register_vault_source(document_id: str, author: str, work: str,
                          language: str, edition: str,
                          book: str = "", chapter: str = "", section: str = "",
                          text_original: str = "", text_fr: str = "",
                          source_url: str = "", source_type: str = "primary",
                          verification_status: str = "pending") -> None:
    """Convenience: register a vault source as a bibliographic entry.

    This is what links a theology_brain page to a stable, citable work:
    the page's title becomes document_id, and the locator fields give the
    exact passage within the edition."""
    save_bibliographic_entry({
        "document_id": document_id,
        "author": author,
        "work": work,
        "language": language,
        "edition": edition,
        "book": book,
        "chapter": chapter,
        "section": section,
        "text_original": text_original,
        "text_fr": text_fr,
        "source_url": source_url,
        "source_type": source_type,
        "verification_status": verification_status,
    })


def _normalise_text(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace for matching."""
    import unicodedata
    text = str(text).lower()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", text).strip()


# ── Session memory ─────────────────────────────────────────────────────────────