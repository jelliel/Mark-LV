"""
Drop-in MARK-LIV plugin — mem0 (mem0 Platform) semantic long-term memory.

Why this exists: save_memory / recall_memory keep a flat keyed JSON file. That
is fast and fine for one-line facts, but it is blind to meaning — a search for
"my sister" finds nothing if the file says "older sibling". mem0 stores whole
sentences, extracts them itself, merges what is repeated, drops what is
contradicted, and brings them back by similarity.

This plugin speaks the mem0 REST API directly (the exact calls the official
SDK makes), so the frozen app gains nothing new to import: `requests` when it
is there, `urllib` otherwise. No mem0 package, no sidecar, no rebuild.

Setup — one of these three, then it works:
  1. ⚙ Settings -> MEM0  (API key field + TEST CONNECTION button)
  2. "mem0_api_key": "mem0-..." in config/api_keys.json
  3. MEM0_API_KEY environment variable
Free key: https://app.mem0.ai  ->  Settings -> API Keys.

Contract follows plugins/_template.py: PLUGIN dict + run(parameters, player,
session_memory) -> str, never raise. Every import below is stdlib, so plugin
discovery itself can never fail because of this file.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

NAMESPACE   = "mem0"            # ⚙ settings namespace == plugin_config key
DEFAULT_HOST = "https://api.mem0.ai"
HTTP_TIMEOUT = 30               # fact extraction runs a model server-side
MAX_LIST     = 40               # lines returned by action='list'
MAX_FORGET   = 5                # max deletions when matching by text
FORGET_SCORE = 0.70             # confidence required before deleting by text

PLUGIN = {
    "name": "mem0_memory",
    "description": (
        "Long-term semantic memory (mem0). Stores whole sentences about the "
        "user and finds them again by MEANING, not by keyword. Always silent — "
        "never announce that you are saving or looking something up. "
        "action='save' (text in English): anything personal worth keeping for "
        "months — preferences, projects, people, relationships, plans, history, "
        "things said once and needed later. "
        "action='search' (query): BEFORE saying you do not know something "
        "personal, before answering a question about the user's past, when "
        "they ask what you remember about them, and to enrich any answer about "
        "their life, work or tastes. "
        "action='forget': when a stored fact is wrong, outdated or replaced "
        "(pass memory_id from a search/list result, or text to match). "
        "action='list': when they ask what you remember in full. "
        "action='import': one-off migration of the existing memory file into "
        "mem0 (already done automatically once — only needed to redo it). "
        "Do NOT use it for quick keyed facts (that is save_memory) nor for "
        "keys listed under [ALSO REMEMBERED] in your prompt (that is "
        "recall_memory)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: save, search, forget, list, import.",
            },
            "text": {
                "type": "STRING",
                "description": (
                    "save: the facts to store, in English, one or two short "
                    "declarative sentences (e.g. 'The user's sister is named "
                    "Ayse. The user prefers dark roast coffee.'). "
                    "forget: the stored fact to delete when no memory_id is "
                    "given. import: 'force' to import again."
                ),
            },
            "query": {
                "type": "STRING",
                "description": (
                    "search: what to look up — a question or keywords, in "
                    "whatever language the user used."
                ),
            },
            "memory_id": {
                "type": "STRING",
                "description": "forget: exact memory id returned by search/list.",
            },
        },
        "required": ["action"],
    },
}


# ── paths & configuration ───────────────────────────────────────────────────

def _base_dir() -> Path:
    """Same rule the app uses: next to the exe when frozen, else this project."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _pick(*values, default: str = "") -> str:
    """First non-empty string wins — so an empty ⚙ field never masks a key
    stored elsewhere."""
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _load_config() -> dict:
    """Merged view: ⚙ Settings (plugin_config.mem0) > api_keys.json > environment."""
    file_cfg = _read_json(_base_dir() / "config" / "api_keys.json")
    ui_cfg = (file_cfg.get("plugin_config") or {}).get(NAMESPACE)
    ui_cfg = ui_cfg if isinstance(ui_cfg, dict) else {}
    return {
        "api_key": _pick(ui_cfg.get("api_key"),
                         file_cfg.get("mem0_api_key"),
                         os.getenv("MEM0_API_KEY")),
        "user_id": _pick(ui_cfg.get("user_id"),
                         file_cfg.get("mem0_user_id"),
                         default="markliv"),
        "host":    _pick(ui_cfg.get("host"),
                         file_cfg.get("mem0_host"),
                         default=DEFAULT_HOST).rstrip("/"),
    }


class _Mem0Error(Exception):
    """Carries a message meant to be spoken back, never a traceback."""


# ── REST layer ──────────────────────────────────────────────────────────────

def _request(cfg: dict, method: str, path: str,
             body: dict | None = None, params: dict | None = None) -> dict:
    """One call to mem0. Returns the parsed JSON object or raises _Mem0Error."""
    if not cfg.get("api_key"):
        raise _Mem0Error(
            "no API key configured. Set it in Settings (MEM0), or "
            "'mem0_api_key' in config/api_keys.json, or MEM0_API_KEY. "
            "Free key: https://app.mem0.ai")

    url = cfg["host"] + path
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    headers = {
        "Authorization": "Token " + cfg["api_key"],
        "Content-Type": "application/json",
        "Mem0-User-ID": cfg["user_id"],
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None

    status: int | None = None
    text = ""
    try:
        import requests                                    # bundled in the app
        resp = requests.request(method, url, headers=headers,
                                data=data, timeout=HTTP_TIMEOUT)
        status, text = resp.status_code, resp.text or ""
    except ImportError:
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            raise _Mem0Error(f"cannot reach {cfg['host']}: {e}")
    except _Mem0Error:
        raise
    except Exception as e:                                 # requests-level failure
        raise _Mem0Error(f"cannot reach {cfg['host']}: {e}")

    payload = {}
    if text:
        try:
            parsed = json.loads(text)
            payload = parsed if isinstance(parsed, dict) else {}
        except Exception:
            payload = {}

    if status is None or status >= 400:
        detail = payload.get("detail") or payload.get("error") or ""
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail)
        detail = str(detail).strip() or (text[:200].strip() if text else "empty reply")
        if status in (401, 403):
            raise _Mem0Error(f"API key rejected ({status}): {detail}")
        raise _Mem0Error(f"error {status}: {detail}")
    return payload


def _items(payload: dict) -> list[dict]:
    """mem0 answers {results: [...]}, {count, results} or {memories: [...]}."""
    if not isinstance(payload, dict):
        return []
    for key in ("results", "memories", "events"):
        val = payload.get(key)
        if isinstance(val, list):
            return [i for i in val if isinstance(i, dict)]
    return []


def _fmt(item: dict) -> str:
    """One memory as a short line: the text, then its id when useful."""
    return str(item.get("memory") or "").strip()


# ── actions ─────────────────────────────────────────────────────────────────

def _action_save(cfg: dict, params: dict) -> str:
    text = str(params.get("text") or "").strip()
    if not text:
        return "mem0 save needs 'text' — the facts to store, written in English."
    payload = _request(cfg, "POST", "/v3/memories/add/", {
        "messages": [{"role": "user", "content": text}],
        "user_id": cfg["user_id"],
    })
    items = _items(payload)
    saved = [m for m in (_fmt(i) for i in items) if m]
    if not saved:
        return "Nothing new was stored — mem0 already had those facts."
    n = len(saved)
    return (f"Stored {n} memor{'y' if n == 1 else 'ies'}: "
            + "; ".join(saved))


def _action_search(cfg: dict, params: dict) -> str:
    query = str(params.get("query") or "").strip()
    if not query:
        return "mem0 search needs 'query'."
    payload = _request(cfg, "POST", "/v3/memories/search/", {
        "query": query,
        "filters": {"user_id": cfg["user_id"]},
    })
    items = _items(payload)
    lines = []
    for it in items[:8]:
        text = _fmt(it)
        if not text:
            continue
        score = it.get("score")
        if isinstance(score, (int, float)):
            lines.append(f"- {text}   [{float(score):.2f}] [{it.get('id', '')}]")
        else:
            lines.append(f"- {text}   [{it.get('id', '')}]")
    if not lines:
        return f"No stored memory matches '{query}'."
    return f"{len(lines)} match(es) for '{query}':\n" + "\n".join(lines)


def _action_forget(cfg: dict, params: dict) -> str:
    memory_id = str(params.get("memory_id") or "").strip()
    if memory_id:
        _request(cfg, "DELETE", f"/v1/memories/{urllib.parse.quote(memory_id, safe='')}/")
        return f"Deleted memory {memory_id}."

    needle = str(params.get("text") or params.get("query") or "").strip()
    if not needle:
        return ("mem0 forget needs either 'memory_id' (from a search or list) "
                "or 'text' naming the fact to delete.")
    payload = _request(cfg, "POST", "/v3/memories/search/", {
        "query": needle,
        "filters": {"user_id": cfg["user_id"]},
    })
    hits = []
    for it in _items(payload):
        score = it.get("score")
        if isinstance(score, (int, float)) and float(score) >= FORGET_SCORE:
            hits.append(it)
        if len(hits) >= MAX_FORGET:
            break
    if not hits:
        closest = _action_search(cfg, {"query": needle})
        return ("Nothing was confident enough to delete. Closest candidates — "
                "re-send with a memory_id to remove one:\n" + closest)
    deleted = []
    for it in hits:
        _request(cfg, "DELETE", f"/v1/memories/{urllib.parse.quote(str(it.get('id')), safe='')}/")
        deleted.append(_fmt(it))
    n = len(deleted)
    return (f"Deleted {n} memor{'y' if n == 1 else 'ies'}: " + "; ".join(deleted))


def _action_list(cfg: dict, params: dict) -> str:
    payload = _request(cfg, "POST", f"/v3/memories/?page_size={MAX_LIST}", {
        "filters": {"user_id": cfg["user_id"]},
    })
    items = _items(payload)
    lines = [f"- {_fmt(i)}   [{i.get('id', '')}]" for i in items if _fmt(i)]
    total = payload.get("count")
    if not lines:
        return "No memories stored yet."
    head = f"{total if isinstance(total, int) else len(lines)} stored, showing {len(lines)}:"
    return head + "\n" + "\n".join(lines)


def _long_term_facts() -> list[str]:
    """Flatten memory/long_term.json into importable sentences. 'monitors' is
    app state (what to watch on the web), not a fact about the user — skipped."""
    data = _read_json(_base_dir() / "memory" / "long_term.json")
    facts = []
    for category, entries in data.items():
        if category == "monitors" or not isinstance(entries, dict):
            continue
        for key, val in entries.items():
            value = val.get("value") if isinstance(val, dict) else val
            if isinstance(value, str) and value.strip():
                facts.append(f"{category}: {key} = {value.strip()}")
    return facts


def _action_import(cfg: dict, params: dict) -> str:
    stamp = _base_dir() / "memory" / ".mem0_imported"
    force = str(params.get("text") or "").strip().lower() == "force"
    if stamp.exists() and not force:
        try:
            when = stamp.read_text(encoding="utf-8").strip() or "earlier"
        except Exception:
            when = "earlier"
        return (f"Already imported on {when}. Send text='force' to import "
                f"memory/long_term.json again.")
    facts = _long_term_facts()
    if not facts:
        _stamp(stamp)
        return "No facts found in memory/long_term.json — nothing to import."
    body = ("Import these facts about the user, one per line:\n"
            + "\n".join(f"- {f}" for f in facts))
    _action_save(cfg, {"text": body})
    _stamp(stamp)
    return f"Imported {len(facts)} facts from memory/long_term.json into mem0."


def _stamp(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(datetime.now().strftime("%Y-%m-%d %H:%M"),
                        encoding="utf-8")
    except Exception:
        pass


_IMPORT_TRIED = False


def _maybe_import_old_facts(cfg: dict) -> None:
    """First call after setup pulls the existing JSON store in, once. Failure
    is not fatal and not silent forever: the stamp is only written on success,
    so the next call tries again."""
    global _IMPORT_TRIED
    if _IMPORT_TRIED or not cfg.get("api_key"):
        return
    _IMPORT_TRIED = True
    stamp = _base_dir() / "memory" / ".mem0_imported"
    if stamp.exists() or not (_base_dir() / "memory" / "long_term.json").exists():
        return
    try:
        _action_import(cfg, {})
        print("[mem0] existing long_term.json migrated into mem0")
    except Exception as e:
        print(f"[mem0] auto-import deferred: {e}")


# ── ⚙ Settings test button ──────────────────────────────────────────────────

def _test_connection(values: dict):
    """Called by the settings UI: returns (ok, message)."""
    cfg = _load_config()
    if isinstance(values, dict):
        cfg["api_key"] = _pick(values.get("api_key"), cfg["api_key"])
        cfg["user_id"] = _pick(values.get("user_id"), cfg["user_id"], default="markliv")
        cfg["host"] = _pick(values.get("host"), cfg["host"],
                            default=DEFAULT_HOST).rstrip("/")
    try:
        data = _request(cfg, "GET", "/v1/ping/")
    except _Mem0Error as e:
        return False, str(e)
    except Exception as e:
        return False, f"test failed: {e}"
    who = data.get("user_email") or data.get("user_id") or "ok"
    return True, f"Connected to mem0 as {who} ✓"


PLUGIN_SETTINGS = {
    "namespace": NAMESPACE,
    "title": "MEM0 — SEMANTIC LONG-TERM MEMORY",
    "fields": [
        {"key": "api_key", "label": "Mem0 API key", "type": "password",
         "placeholder": "mem0-…  (app.mem0.ai → API Keys)"},
        {"key": "user_id", "label": "Scope (user_id)", "type": "text",
         "placeholder": "markliv", "default": "markliv"},
        {"key": "host", "label": "API host", "type": "text",
         "placeholder": DEFAULT_HOST, "default": DEFAULT_HOST},
    ],
    "action": {"label": "TEST CONNECTION", "run": _test_connection},
}


# ── entry point ─────────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    parameters: the args Gemini extracted, matching PLUGIN['parameters'].
    Returns a short English string — data for the model, which then answers in
    the user's language. Never raises: errors come back as spoken text.
    """
    params = parameters if isinstance(parameters, dict) else {}
    action = str(params.get("action") or "").strip().lower()
    try:
        if not action:
            return ("mem0_memory: 'action' is required — one of "
                    "save, search, forget, list, import.")
        cfg = _load_config()
        _maybe_import_old_facts(cfg)

        if action == "save":
            out = _action_save(cfg, params)
        elif action == "search":
            out = _action_search(cfg, params)
        elif action == "forget":
            out = _action_forget(cfg, params)
        elif action == "list":
            out = _action_list(cfg, params)
        elif action == "import":
            out = _action_import(cfg, params)
        else:
            out = (f"mem0_memory: unknown action '{action}' — use save, "
                   f"search, forget, list or import.")
    except _Mem0Error as e:
        out = f"Mem0: {e}"
    except Exception as e:
        out = f"mem0_memory failed: {e}"

    if out and ("Mem0:" in out or "failed" in out):
        print(f"[mem0] {out}")
        if player:
            try:
                player.write_log(f"[mem0] {out}")
            except Exception:
                pass
    return out
