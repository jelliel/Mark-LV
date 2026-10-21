"""
Drop-in MARK-LIV tool — Theological Second Brain.

Shipped as both an ACTION (actions/, TOOL + handler) and a PLUGIN (plugins/,
PLUGIN + run). Both contracts are defined below, so whichever loader scans
this file first can register it; a second one seeing an already-registered
name is expected to skip.

A local, LLM-maintained knowledge vault for theology, in plain Markdown you
own. It implements the "LLM Wiki" pattern (Karpathy; as used by
NicholasSpisak/second-brain): drop raw sources in, let MARK-LIV compile them
into a structured, interlinked wiki you can browse in Obsidian.

This plugin is deliberately *mechanical*. It reads, writes, indexes, searches
and lints files. The reasoning — what a source says, which entities and
concepts matter, how they relate — stays with the model, which calls these
actions. That keeps the plugin fast, offline and free, and keeps the doctrine
in files you can version and edit.

Layout — in the user's Documents folder, so the vault survives app updates
and is easy to find (override the path in settings or config):

    Documents/Theology/
    ├── raw/                 # your inbox — drop sources here
    │   └── assets/
    ├── wiki/
    │   ├── sources/         # one page per ingested source
    │   ├── entities/        # people, councils, orders, works
    │   ├── concepts/        # doctrines, terms, movements
    │   ├── synthesis/       # comparisons, themes, essays
    │   ├── index.md         # regenerated catalog of every page
    │   └── log.md           # append-only operation record
    └── MEMORY.md            # curated, human-editable project state

`summary` writes MEMORY.md AND mirrors a short version into
memory/long_term.json under projects.theology — which MARK-LIV already
injects into the prompt, so the state of the theology project is always in
context with no change to the frozen app.

Contract follows plugins/_template.py: PLUGIN dict + run(parameters, player,
session_memory) -> str, never raise. Imports are stdlib only, so plugin
discovery can never fail because of this file.
"""

import http.client
import importlib.util
import json
import re
import socket
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

VAULT_DIRNAME = "Theology"          # folder inside the user's Documents
CONFIG_KEY = "theology_vault_path"  # optional override in config/api_keys.json
MAX_READ_CHARS = 6000               # cap for action='read'
SEARCH_SNIPPET = 220                # chars of context per search hit

# kind (singular) -> wiki subdirectory
_KIND_DIRS = {
    "source": "sources",
    "entity": "entities",
    "concept": "concepts",
    "synthesis": "synthesis",
}
# subdirectory -> display label, in index order
_INDEX_ORDER = [
    ("sources", "Sources"),
    ("entities", "Entities"),
    ("concepts", "Concepts"),
    ("synthesis", "Synthesis"),
]

PLUGIN = {
    "name": "theology_brain",
    "description": (
        "Theological second brain: a local Markdown vault of interlinked wiki "
        "pages (sources, entities, concepts, synthesis). Use it whenever the "
        "user works on theology — scripture, the Church Fathers, councils, "
        "doctrine, heresies, theologians, works. "
        "SEARCH IT BEFORE YOU ANSWER a theological question: it holds the "
        "user's own reading, it is local and instant, and it is what the "
        "answer must be based on. If action='search' finds nothing, the vault "
        "says so and a deep research is started in the background — say that "
        "in one sentence and do NOT answer from memory in the meantime. "
        "action='init': create/repair the vault (safe, idempotent). "
        "action='capture': save a source (a file via 'path', or raw text via "
        "'text') into raw/ — do this BEFORE structuring it. "
        "action='read': return the text of a raw source so you can work out "
        "its takeaways. "
        "action='write': create or update a wiki page — pass 'kind' "
        "(source|entity|concept|synthesis), 'title' and the page 'text' you "
        "wrote; the index and log are updated for you. "
        "action='search': find pages by keyword (local, offline) — use it "
        "before answering any theological question you may already have notes "
        "on. "
        "action='list': list pages, and which raw sources are unprocessed. "
        "action='lint': report broken [[wikilinks]], index drift and "
        "unprocessed sources. "
        "action='status': vault path and counts. "
        "action='summary': record the project's current state (a few "
        "sentences) — it is written to MEMORY.md and mirrored into "
        "long_term.json so it stays in your context. Call it after significant "
        "work. "
        "Do NOT use it for facts about the user (that is save_memory or "
        "mem0_memory)."
    ),

    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": ("One of: init, capture, read, write, search, "
                                "list, lint, status, summary."),
            },
            "path": {
                "type": "STRING",
                "description": ("capture/read: path to a source file on disk. "
                                "capture: it is copied into raw/. read: it is "
                                "returned as text."),
            },
            "text": {
                "type": "STRING",
                "description": ("capture: the raw source text to save. "
                                "write: the page body in Markdown. "
                                "summary: the project state, a few sentences."),
            },
            "title": {
                "type": "STRING",
                "description": "write: page title (becomes the [[wikilink]] name).",
            },
            "kind": {
                "type": "STRING",
                "description": ("write/list: source | entity | concept | "
                                "synthesis."),
            },
            "tags": {
                "type": "STRING",
                "description": "write: comma-separated tags.",
            },
            "sources": {
                "type": "STRING",
                "description": ("write: comma-separated raw source filenames "
                                "this page draws on."),
            },
            "query": {
                "type": "STRING",
                "description": "search: words or a phrase to look for.",
            },
            "limit": {
                "type": "NUMBER",
                "description": "search: max hits (default 6, max 20).",
            },
        },
        "required": ["action"],
    },
}


# ── paths & configuration ───────────────────────────────────────────────────

def _base_dir() -> Path:
    """Same rule the app uses: next to the exe when frozen, else this project.

    A copy bundled under _internal/ resolves to the app root, not _internal/,
    so the vault and memory paths are identical whichever copy loads it.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    here = Path(__file__).resolve().parent.parent
    if here.name == "_internal":
        here = here.parent
    return here


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_config() -> dict:
    return _read_json(_base_dir() / "config" / "api_keys.json")


def _default_vault() -> Path:
    return Path.home() / "Documents" / VAULT_DIRNAME


def _vault() -> Path:
    override = _load_config().get(CONFIG_KEY)
    if isinstance(override, str) and override.strip():
        return Path(override.strip()).expanduser()
    return _default_vault()


def _today() -> str:
    return date.today().isoformat()


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "page"


def _split_list(raw: str) -> list[str]:
    """'a, b , c' -> ['a', 'b', 'c']; [] for empty."""
    if not isinstance(raw, str):
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _fmt_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


# ── page read/write ─────────────────────────────────────────────────────────

def _read_page(path: Path) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Tolerant — never raises."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return {}, ""
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2]
    return meta, body.strip()


def _page_title(path: Path, meta: dict) -> str:
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _write_page_file(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{fm}\n---\n\n{body.strip()}\n", encoding="utf-8")


def _iter_pages(vault: Path):
    """Yield (kind_dir_name, path) for every wiki page."""
    for dirname, _ in _INDEX_ORDER:
        folder = vault / "wiki" / dirname
        if folder.is_dir():
            for p in sorted(folder.glob("*.md")):
                yield dirname, p


# ── the shared tokenizer ────────────────────────────────────────────────────
# research/vocab.py holds the one definition of what a word is: how it is
# folded, which ones are framing rather than subject, and which two names are
# the same word. It lives in the research package because the gap trigger
# measures with it too, and both sides must measure the same way.

_VOCAB = None
_ROUTER = None


def _vocab():
    """research/vocab.py, loaded by path — actions/ is not a package and the
    app root is not guaranteed to be on sys.path. Loaded once per process."""
    global _VOCAB
    if _VOCAB is not None:
        return _VOCAB
    path = _base_dir() / "research" / "vocab.py"
    spec = importlib.util.spec_from_file_location("markliv_vocab", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vocab"] = module
    spec.loader.exec_module(module)
    _VOCAB = module
    return module


def vault_router():
    """actions/_vault_router.py — the consultation the application makes
    before the model answers. Loaded by path, once per process.

    It lives beside this module because it needs the vault's pages and the
    shared vocabulary; it is not an action itself (the file starts with an
    underscore, so the loader never treats it as one)."""
    global _ROUTER
    if _ROUTER is not None:
        return _ROUTER
    path = Path(__file__).resolve().with_name("_vault_router.py")
    spec = importlib.util.spec_from_file_location("markliv_vault_router", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vault_router"] = module
    spec.loader.exec_module(module)
    _ROUTER = module
    return module


# ── the page index ──────────────────────────────────────────────────────────
# Every page, read once and kept until the vault changes. The search and the
# coverage measurement both need the whole vault: reading it twice, from two
# places, is what made a search that found a page and a gap check that
# called it a gap possible in the first place.

_PAGE_INDEX: dict[str, tuple] = {}


def page_index(vault: Path) -> list[dict]:
    """Every wiki page as {dir, path, title, body}, cached until it changes.

    The cache is keyed on the pages themselves — path, modification time and
    size — so a page that was written a second ago is re-read, and a vault
    nobody touched costs one stat per page instead of one read per page."""
    key = str(vault)
    try:
        signature = tuple(
            (str(p), p.stat().st_mtime_ns, p.stat().st_size)
            for _d, p in _iter_pages(vault))
    except OSError:
        return []
    cached = _PAGE_INDEX.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    pages = []
    for dirname, path in _iter_pages(vault):
        meta, body = _read_page(path)
        pages.append({"dir": dirname, "path": path,
                      "title": _page_title(path, meta), "body": body})
    _PAGE_INDEX[key] = (signature, pages)
    return pages


def clear_page_index(vault: Path | None = None) -> None:
    """Drop the cached pages — after a write, so the next read sees it."""
    if vault is None:
        _PAGE_INDEX.clear()
    else:
        _PAGE_INDEX.pop(str(vault), None)


def page_index_stamp(vault: Path):
    """A cheap fingerprint of the vault's pages.

    A measurement cached against an older fingerprint would be a measurement
    of a vault that no longer exists, so anything that caches a verdict caches
    it against this."""
    cached = _PAGE_INDEX.get(str(vault))
    return cached[0] if cached else None


def reindex_page(vault: Path, path: Path) -> None:
    """Keep the cached index in step with a page that was just written.

    Without this, every write invalidates the whole cache and the next read
    parses the vault again — and an ingestion that writes ninety pages would
    parse it ninety times. One page is re-read, the rest is untouched."""
    cached = _PAGE_INDEX.get(str(vault))
    if cached is None:
        return
    _signature, pages = cached
    try:
        meta, body = _read_page(path)
        title = _page_title(path, meta)
    except Exception:
        return
    entry = {"dir": path.parent.name, "path": path, "title": title, "body": body}
    for index, page in enumerate(pages):
        if page["path"] == path:
            pages[index] = entry
            break
    else:
        pages.append(entry)
    try:
        signature = tuple(
            (str(p), p.stat().st_mtime_ns, p.stat().st_size)
            for _d, p in _iter_pages(vault))
    except OSError:
        return
    _PAGE_INDEX[str(vault)] = (signature, pages)


def _first_line_summary(body: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(">") or line.startswith("**"):
            continue
        line = re.sub(r"[*_`\[\]]", "", line)
        return (line[:117] + "…") if len(line) > 120 else line
    return ""


# ── index & log ─────────────────────────────────────────────────────────────

def _rebuild_index(vault: Path) -> int:
    """Regenerate wiki/index.md from the pages on disk. Returns page count."""
    lines = ["# Theology — Index", "",
             f"_Regenerated {_today()} by MARK-LIV._", ""]
    count = 0
    for dirname, label in _INDEX_ORDER:
        folder = vault / "wiki" / dirname
        pages = sorted(folder.glob("*.md")) if folder.is_dir() else []
        lines.append(f"## {label}")
        if not pages:
            lines.append("- _(none yet)_")
        for p in pages:
            meta, body = _read_page(p)
            title = _page_title(p, meta)
            summary = _first_line_summary(body)
            lines.append(f"- [[{title}]] — {summary}" if summary else f"- [[{title}]]")
            count += 1
        lines.append("")
    (vault / "wiki" / "index.md").write_text("\n".join(lines).rstrip() + "\n",
                                             encoding="utf-8")
    return count


def _append_log(vault: Path, kind: str, message: str) -> None:
    logp = vault / "wiki" / "log.md"
    logp.parent.mkdir(parents=True, exist_ok=True)
    if not logp.exists():
        logp.write_text("# Theology — Log\n\nChronological record of operations.\n",
                        encoding="utf-8")
    with logp.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## [{_today()}] {kind} — {message}\n")


def _scaffold(vault: Path) -> list[str]:
    """Create the vault skeleton. Returns the list of things created."""
    created = []
    for rel in ("raw", "raw/assets", "wiki/sources", "wiki/entities",
                "wiki/concepts", "wiki/synthesis"):
        d = vault / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")
    if not (vault / "wiki" / "index.md").exists():
        _rebuild_index(vault)
    if not (vault / "wiki" / "log.md").exists():
        _append_log(vault, "init", "vault created")
    if not (vault / "MEMORY.md").exists():
        (vault / "MEMORY.md").write_text(
            "# Theology — Project State\n\n"
            "_Curated by MARK-LIV. Edit freely; this file is yours._\n\n"
            "## Current focus\n\n_(nothing recorded yet — ask MARK-LIV to run a "
            "summary after your next session)_\n",
            encoding="utf-8")
        created.append("MEMORY.md")
    return created


# ── wikilinks ───────────────────────────────────────────────────────────────

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def _wikilinks(body: str) -> list[str]:
    return [m.strip() for m in _WIKILINK_RE.findall(body)]


def _title_map(vault: Path) -> dict[str, Path]:
    """lower-cased page title -> path, for wikilink resolution."""
    mapping: dict[str, Path] = {}
    for _, path in _iter_pages(vault):
        meta, _ = _read_page(path)
        mapping[_page_title(path, meta).lower()] = path
        mapping.setdefault(path.stem.replace("-", " ").lower(), path)
    return mapping


# ── actions ─────────────────────────────────────────────────────────────────

def _action_init(vault: Path) -> str:
    created = _scaffold(vault)
    if created:
        _append_log(vault, "init", f"created {', '.join(created)}")
    pages = _rebuild_index(vault)
    n_raw = len([p for p in (vault / "raw").glob("*") if p.is_file()])
    tail = f"created {', '.join(created)}. " if created else "already in place. "
    return f"Theology vault at {vault} — {tail}{pages} page(s), {n_raw} raw source(s)."


def _action_capture(vault: Path, params: dict) -> str:
    _scaffold(vault)
    raw_dir = vault / "raw"
    src = str(params.get("path") or "").strip()
    text = str(params.get("text") or "")

    if src:
        p = Path(src).expanduser()
        if not p.is_file():
            return f"capture: file not found: {src}"
        target = raw_dir / p.name
        try:
            target.write_bytes(p.read_bytes())
        except Exception as e:
            return f"capture failed reading {src}: {e}"
        _append_log(vault, "capture", target.name)
        return f"Captured '{target.name}' into raw/ ({target}). Structure it with action='write'."

    if text.strip():
        title = str(params.get("title") or "").strip()
        name = (_slugify(title) if title else "note-" + _today()) + ".md"
        target = raw_dir / name
        if target.exists():
            name = _slugify(title or "note") + "-" + date.today().strftime("%H%M") + ".md"
            target = raw_dir / name
        target.write_text(text, encoding="utf-8")
        _append_log(vault, "capture", name)
        return f"Captured raw text as '{name}' in raw/."

    return "capture needs either 'path' (a file) or 'text' (raw content)."


def _action_read(vault: Path, params: dict) -> str:
    _scaffold(vault)
    target = str(params.get("path") or "").strip()
    if not target:
        return "read needs 'path' — a raw source file."
    p = Path(target).expanduser()
    if not p.is_file():
        candidate = vault / "raw" / Path(target).name
        if candidate.is_file():
            p = candidate
        else:
            return f"read: not found: {target}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"read failed: {e}"
    if len(content) > MAX_READ_CHARS:
        content = (content[:MAX_READ_CHARS]
                   + f"\n\n… [truncated at {MAX_READ_CHARS} chars of "
                     f"{len(content)}; read the file directly for the rest]")
    return f"--- {p.name} ---\n{content}"


def _action_write(vault: Path, params: dict) -> str:
    _scaffold(vault)
    title = str(params.get("title") or "").strip()
    kind = str(params.get("kind") or "").strip().lower()
    body = str(params.get("text") or "").strip()

    if not title:
        return "write needs 'title'."
    if kind not in _KIND_DIRS:
        return "write needs 'kind' one of: source, entity, concept, synthesis."
    if not body:
        return "write needs 'text' — the Markdown body of the page."

    folder = vault / "wiki" / _KIND_DIRS[kind]
    path = folder / (_slugify(title) + ".md")
    tags = _split_list(params.get("tags"))
    sources = _split_list(params.get("sources"))
    existing_meta, existing_body = _read_page(path)

    if path.exists():
        merged_body = existing_body + f"\n\n## Update — {_today()}\n{body}"
        meta = existing_meta or {
            "title": title, "kind": kind,
            "created": _today(),
        }
        if tags:
            meta["tags"] = _fmt_list(tags)
        if sources:
            meta["sources"] = _fmt_list(sources)
        meta["updated"] = _today()
        _write_page_file(path, meta, merged_body)
        action = "updated"
    else:
        meta = {
            "title": title,
            "kind": kind,
            "tags": _fmt_list(tags),
            "sources": _fmt_list(sources),
            "created": _today(),
            "updated": _today(),
        }
        _write_page_file(path, meta, body)
        action = "created"

    _rebuild_index(vault)
    _append_log(vault, f"write/{kind}", f"{action} [[{title}]]")
    _xerj_push(path)                     # indexation à la volée (best effort)
    reindex_page(vault, path)            # the cached index stays in step
    refresh_context_mirror()             # the prompt's table of contents
    total = sum(1 for _ in _iter_pages(vault))
    return f"{action} {kind} page [[{title}]] at {path}. Vault now has {total} page(s)."


# ── XERJ live indexing (optional, config: xerj_url) ─────────────────────────

_XERJ_URL_KEY = "xerj_url"
_XERJ_WIKI    = "ax-vault-wiki"
_XERJ_BACKOFF = 60.0          # seconds of skipping while the node is down
_xerj_block_until = 0.0
_xerj_index_ready = False     # index créé une fois par process
_xerj_conn    = None          # HTTP persistante (une nouvelle connexion
                              # coûte ~2 s sur ce node — jamais par écriture)


def _xerj_ensure_index(url: str) -> None:
    """Crée ax-vault-wiki (corps semantic_text) si besoin. Un 400/409 veut
    dire « déjà là » et est ignoré."""
    global _xerj_index_ready
    if _xerj_index_ready:
        return
    mapping = {"mappings": {"properties": {
        "body": {"type": "semantic_text"},
        "title": {"type": "text"},
        "kind": {"type": "keyword"},
        "tags": {"type": "keyword"},
        "sources": {"type": "keyword"},
        "updated": {"type": "date"},
    }}}
    try:
        req = urllib.request.Request(
            f"{url}/{_XERJ_WIKI}", data=json.dumps(mapping).encode("utf-8"),
            headers={"content-type": "application/json"}, method="PUT")
        urllib.request.urlopen(req, timeout=6.0).close()
    except Exception:
        pass                      # déjà existant → OK
    _xerj_index_ready = True


def _xerj_url() -> str:
    url = str(_load_config().get(_XERJ_URL_KEY) or "").strip()
    return url.rstrip("/") if url else ""


def _xerj_alive(url: str) -> bool:
    try:
        from urllib.parse import urlsplit
        netloc = urlsplit(url).netloc
        host, _, port = netloc.partition(":")
        socket.create_connection((host, int(port or 9200)), timeout=1.2).close()
        return True
    except Exception:
        return False


def _xerj_push(path: Path) -> None:
    """Index UNE page wiki fraîchement écrite dans ax-vault-wiki (corps
    sémantique auto-embeddé). Best effort : nœud absent → pause de 60 s
    plutôt qu'un timeout sur chaque écriture ; failure ne JAMAIS faire
    remonter dans l'écriture du vault."""
    global _xerj_block_until
    url = _xerj_url()
    if not url or time.monotonic() < _xerj_block_until:
        return
    if not _xerj_alive(url):
        _xerj_block_until = time.monotonic() + _XERJ_BACKOFF
        print("[TheologyBrain] XERJ down — live indexing paused 60 s")
        return
    _xerj_ensure_index(url)
    global _xerj_conn
    try:
        meta, body = _read_page(path)
        doc = {
            "title":   _page_title(path, meta) or path.stem,
            "kind":    str(meta.get("kind") or ""),
            "tags":    str(meta.get("tags") or ""),
            "sources": str(meta.get("sources") or ""),
            "updated": str(meta.get("updated") or _today()),
            "body":    body or "",
        }
        if _xerj_conn is None:
            _xerj_conn = http.client.HTTPConnection(
                url.split("//", 1)[1], timeout=6.0)
            _xerj_ensure_index(url)
        if _xerj_conn.sock is not None:
            try:
                _xerj_conn.sock.setsockopt(socket.IPPROTO_TCP,
                                           socket.TCP_NODELAY, 1)
            except Exception:
                pass
        _xerj_conn.request(
            "PUT", f"/{_XERJ_WIKI}/_doc/{_slugify(doc['title'])}",
            body=json.dumps(doc), headers={"content-type": "application/json"})
        _xerj_conn.getresponse().read()
        # Cherchable immédiatement (le flush XERJ est différé sinon) — ~0 ms.
        _xerj_conn.request("POST", f"/{_XERJ_WIKI}/_refresh")
        _xerj_conn.getresponse().read()
    except Exception as e:
        _xerj_conn = None               # connexion morte → recréée au prochain push
        print(f"[TheologyBrain] XERJ push failed: {e}")


def _action_search(vault: Path, params: dict) -> str:
    _scaffold(vault)
    query = str(params.get("query") or "").strip()
    if not query:
        return "search needs 'query'."
    try:
        limit = int(params.get("limit") or 6)
    except (TypeError, ValueError):
        limit = 6
    limit = max(1, min(limit, 20))

    vocab = _vocab()
    # The same terms the gap measurement uses: a search and a coverage check
    # that disagree are how a question gets answered twice.
    terms = vocab.subject_terms(query)
    if not terms:
        return f"search: '{query}' has no searchable terms."

    hits = []
    for page in page_index(vault):
        counts, _title_words = vocab.page_tokens(page["title"], page["body"])
        matched = [t for t in terms if t in counts]
        if not matched:
            continue
        score = sum(counts[t] for t in matched)
        # snippet around the first matching term, in the ORIGINAL text so the
        # accents and the case the user wrote stay intact
        snippet = ""
        span = vocab.find_span(page["body"], set(matched))
        if span:
            start = max(0, span[0] - 60)
            end = max(span[1], start + SEARCH_SNIPPET)
            snippet = page["body"][start:end].replace("\n", " ").strip()
        hits.append((score, page["dir"], page["title"], page["path"], snippet))

    if not hits:
        unprocessed = [p.name for p in (vault / "raw").glob("*")
                       if p.is_file() and p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")]
        extra = (f" {len(unprocessed)} raw source(s) present but not yet "
                 f"structured — run action='list'." if unprocessed else "")
        return f"No wiki page matches '{query}'.{extra}"

    hits.sort(key=lambda h: (-h[0], h[2].lower()))
    lines = [f"{len(hits)} match(es) for '{query}':"]
    for score, dirname, title, path, snippet in hits[:limit]:
        lines.append(f"\n- [[{title}]]  ({dirname}, score {score}) — {path}")
        if snippet:
            lines.append(f"  …{snippet}…")
    return "\n".join(lines)


def _unprocessed_sources(vault: Path) -> list[str]:
    raw = vault / "raw"
    if not raw.is_dir():
        return []
    ingested = set()
    for p in (vault / "wiki" / "sources").glob("*.md") if (vault / "wiki" / "sources").is_dir() else []:
        meta, _ = _read_page(p)
        for src in _split_list(meta.get("sources", "").strip("[]")):
            ingested.add(src.lower())
        ingested.add(p.stem.lower())
    skip = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    out = []
    for p in sorted(raw.glob("*")):
        if p.is_file() and p.suffix.lower() not in skip and p.name.lower() not in ingested:
            out.append(p.name)
    return out


def _action_list(vault: Path, params: dict) -> str:
    _scaffold(vault)
    kind = str(params.get("kind") or "").strip().lower()
    lines = []
    for dirname, label in _INDEX_ORDER:
        if kind and _KIND_DIRS.get(kind) != dirname:
            continue
        folder = vault / "wiki" / dirname
        pages = sorted(folder.glob("*.md")) if folder.is_dir() else []
        lines.append(f"{label} ({len(pages)}):")
        for p in pages:
            meta, _ = _read_page(p)
            lines.append(f"  - [[{_page_title(p, meta)}]] — {p.name}")
        if not pages:
            lines.append("  - _(none)_")
        lines.append("")
    unprocessed = _unprocessed_sources(vault)
    if unprocessed:
        lines.append(f"Unprocessed raw sources ({len(unprocessed)}):")
        lines.extend(f"  - {n}" for n in unprocessed)
    else:
        lines.append("No unprocessed raw sources.")
    return "\n".join(lines).rstrip()


def _action_lint(vault: Path) -> str:
    _scaffold(vault)
    title_map = _title_map(vault)
    titles = set(title_map.keys())

    broken = []
    for dirname, path in _iter_pages(vault):
        meta, body = _read_page(path)
        for link in _wikilinks(body):
            if link.lower() not in titles:
                broken.append(f"  - [[{link}]] in {dirname}/{path.name}")

    expected = sum(1 for _ in _iter_pages(vault))
    index_path = vault / "wiki" / "index.md"
    index_entries = 0
    if index_path.exists():
        index_entries = len(_WIKILINK_RE.findall(index_path.read_text(encoding="utf-8")))
    index_drift = expected != index_entries

    unprocessed = _unprocessed_sources(vault)

    report = [f"Lint — vault at {vault}",
              f"- pages: {expected}, index entries: {index_entries}"
              + (" — DRIFT (run action='init' or any 'write' to rebuild)"
                 if index_drift else " — consistent"),
              f"- broken [[wikilinks]]: {len(broken)}"]
    if broken:
        report.extend(broken)
    report.append(f"- unprocessed raw sources: {len(unprocessed)}")
    if unprocessed:
        report.extend(f"  - {n}" for n in unprocessed)
    if not broken and not index_drift and not unprocessed:
        report.append("All clean.")
    return "\n".join(report)


# ── the brain's self-knowledge ───────────────────────────────────────────────

def _vault_context(vault: Path, max_titles: int = 40) -> str:
    """WHAT THE BRAIN ALREADY KNOWS, compact — handed to the structuring
    agents so they cross-link instead of duplicating. Titles are listed
    newest first per kind. Pure read: never writes, never fails."""
    try:
        sections = []
        for dirname, label in _INDEX_ORDER:
            folder = vault / "wiki" / dirname
            titles = []
            if folder.is_dir():
                for p in sorted(folder.glob("*.md"),
                                key=lambda p: p.stat().st_mtime, reverse=True):
                    meta, _body = _read_page(p)
                    titles.append(_page_title(p, meta))
            if titles:
                shown = titles[:max_titles]
                extra = len(titles) - len(shown)
                sections.append(
                    f"{label} ({len(titles)}): " + ", ".join(shown)
                    + (f" (+{extra} plus anciens)" if extra > 0 else ""))
        return "\n".join(sections) if sections else "(vault vide — première source)"
    except Exception as e:
        print(f"[TheologyBrain] vault context failed: {e}")
        return ""


def vault_context(max_titles: int = 40) -> str:
    """Public form for callers that hold this module (plain load-by-path)."""
    return _vault_context(_vault(), max_titles)


def update_context_mirror(text: str) -> str:
    """Update ONLY the long_term.json mirror (prompt injection) — MEMORY.md is
    hand-written and is never touched here. Returns a short status."""
    text = (text or "").replace("\n", " ").strip()[:600]
    if not text:
        return "nothing to mirror"
    try:
        lt = _base_dir() / "memory" / "long_term.json"
        data = _read_json(lt)
        projects = data.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        projects["theology"] = {"value": text, "updated": _today()}
        data["projects"] = projects
        lt.parent.mkdir(parents=True, exist_ok=True)
        lt.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                      encoding="utf-8")
        return f"context mirror updated (long_term.json)"
    except Exception as e:
        return f"mirror failed: {e}"


def refresh_context_mirror() -> str:
    """What the vault holds, in one line, where the model will read it.

    A model cannot look for what it does not know exists. The mirror is the
    vault's table of contents in the prompt: the assistant sees the subjects
    it has notes on, and can decide to ask the vault before answering from
    memory — which is the only way the vault ever gets read at all.

    The instruction comes first, because the line is truncated to what fits:
    a table of contents cut in half teaches nothing. And the subjects listed
    are the concepts, the entities and the syntheses — the raw sources are
    documents the user owns, not subjects to ask about."""
    try:
        vault = _vault()
        pages = page_index(vault)
        if not pages:
            return "nothing to mirror"
        counts: dict[str, int] = {}
        subjects: list[str] = []
        for page in pages:
            counts[page["dir"]] = counts.get(page["dir"], 0) + 1
            if page["dir"] != "sources":      # a source is a document, not a subject
                subjects.append(page["title"])
        parts = [f"{counts.get(d, 0)} {label.lower()}"
                 for d, label in _INDEX_ORDER if counts.get(d)]
        shown = ", ".join(subjects[:16])
        more = f" (+{len(subjects) - 16} autres)" if len(subjects) > 16 else ""
        text = (f"Theology vault: {len(pages)} pages ({', '.join(parts)}). "
                f"Search it before answering a theological question from "
                f"memory. Subjects: {shown}{more}.")
        return update_context_mirror(text)
    except Exception as e:
        print(f"[TheologyBrain] mirror refresh failed: {e}")
        return ""


def _action_status(vault: Path) -> str:
    exists = vault.exists()
    _scaffold(vault)
    counts = {}
    for dirname, label in _INDEX_ORDER:
        folder = vault / "wiki" / dirname
        counts[label] = len(list(folder.glob("*.md"))) if folder.is_dir() else 0
    n_raw = len([p for p in (vault / "raw").glob("*") if p.is_file()])
    total = sum(counts.values())
    mem = vault / "MEMORY.md"
    state = "present" if mem.exists() else "absent"
    head = "Vault ready" if exists else "Vault created"
    parts = ", ".join(f"{k}: {v}" for k, v in counts.items())
    return (f"{head} — {vault}\n"
            f"{total} page(s) ({parts})\n"
            f"{n_raw} raw source(s); MEMORY.md {state}.")


def _action_summary(vault: Path, params: dict) -> str:
    _scaffold(vault)
    text = str(params.get("text") or "").strip()
    mem = vault / "MEMORY.md"

    if not text:
        current = mem.read_text(encoding="utf-8") if mem.exists() else ""
        return f"Current theology project state ({mem}):\n{current.strip()}"

    mem.write_text(
        "# Theology — Project State\n\n"
        f"_Updated {_today()} by MARK-LIV._\n\n"
        "## Current focus\n\n" + text + "\n\n"
        "## Recent activity\n\nSee `wiki/log.md`. Index: `wiki/index.md`.\n",
        encoding="utf-8")

    # Mirror a compact form into long_term.json so it is always in context.
    mirrored = False
    try:
        lt = _base_dir() / "memory" / "long_term.json"
        data = _read_json(lt)
        projects = data.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        projects["theology"] = {"value": text.replace("\n", " ")[:600],
                                "updated": _today()}
        data["projects"] = projects
        lt.parent.mkdir(parents=True, exist_ok=True)
        lt.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                      encoding="utf-8")
        mirrored = True
    except Exception as e:
        mirrored = f"could not mirror to long_term.json: {e}"

    _append_log(vault, "summary", "project state updated")
    where = ("also mirrored to memory/long_term.json (always in prompt)"
             if mirrored is True else str(mirrored))
    return f"Recorded project state in {mem}; {where}."


# ── ⚙ Settings hook ─────────────────────────────────────────────────────────

def _test_vault(values: dict):
    """Called by the settings UI: returns (ok, message)."""
    vault = _vault()
    if isinstance(values, dict):
        override = values.get(CONFIG_KEY)
        if isinstance(override, str) and override.strip():
            vault = Path(override.strip()).expanduser()
    try:
        _scaffold(vault)
        total = sum(1 for _ in _iter_pages(vault))
        return True, f"Vault ready at {vault} — {total} page(s) ✓"
    except Exception as e:
        return False, f"vault unusable: {e}"


PLUGIN_SETTINGS = {
    "namespace": "theology_brain",
    "title": "THEOLOGY BRAIN — LOCAL MARKDOWN VAULT",
    "fields": [
        {"key": CONFIG_KEY, "label": "Vault path (leave blank for default)",
         "type": "text",
         "placeholder": str(_default_vault())},
        {"key": "theology_auto_research",
         "label": "Deep research when the vault cannot answer",
         "type": "toggle", "default": True},
        {"key": "theology_auto_research_max_per_day",
         "label": "Automatic researches per day (0 = no limit)",
         "type": "text", "default": "3"},
        {"key": "theology_auto_research_cooldown",
         "label": "Seconds before the same question may trigger again "
                  "(1800 = 30 min)",
         "type": "text", "default": "1800"},
        {"key": "theology_auto_research_depth",
         "label": "Depth of an automatic run",
         "type": "choice", "default": "standard",
         "options": ["quick", "standard", "deep"]},
        {"key": "theology_auto_research_language",
         "label": "Language of the reports (auto follows the topic)",
         "type": "text", "default": "auto"},
    ],
    "action": {"label": "CHECK VAULT", "run": _test_vault},
}


# ── entry point ─────────────────────────────────────────────────────────────

def _maybe_auto_research(query: str, out: str, player, speak) -> str:
    """A search that found nothing is a gap; a gap is worth a run.

    The decision belongs to research/theology.py — coverage, cooldown, the
    one-run-at-a-time rule and the vault write-back all live there, because the
    same trigger is reached from XERJ as well. This function only carries the
    note back to the model. It never raises: a broken bridge must not turn
    "nothing in the vault" into "the tool failed"."""
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from research import theology as bridge
        note = bridge.maybe_start(str(query or ""), player=player, speak=speak,
                                  source="theology_brain")
    except Exception as e:
        print(f"[theology] auto-research bridge failed: {e}")
        return out
    if not note:
        return out
    if player:
        try:
            player.write_log("[theology] lacune du vault — recherche profonde lancée")
        except Exception:
            pass
    return out + "\n\n" + note


def run(parameters: dict, player=None, session_memory=None, speak=None) -> str:
    """
    parameters: the args the model extracted, matching PLUGIN['parameters'].
    Returns a short English string — data for the model, which answers in the
    user's language. Never raises: errors come back as text.
    """
    params = parameters if isinstance(parameters, dict) else {}
    action = str(params.get("action") or "").strip().lower()
    vault = _vault()

    try:
        if not action:
            return ("theology_brain: 'action' is required — one of init, "
                    "capture, read, write, search, list, lint, status, summary.")
        if action == "init":
            out = _action_init(vault)
        elif action == "capture":
            out = _action_capture(vault, params)
        elif action == "read":
            out = _action_read(vault, params)
        elif action == "write":
            out = _action_write(vault, params)
        elif action == "search":
            out = _action_search(vault, params)
        elif action == "list":
            out = _action_list(vault, params)
        elif action == "lint":
            out = _action_lint(vault)
        elif action == "status":
            out = _action_status(vault)
        elif action == "summary":
            out = _action_summary(vault, params)
        else:
            out = (f"theology_brain: unknown action '{action}' — use init, "
                   f"capture, read, write, search, list, lint, status, summary.")
    except Exception as e:
        out = f"theology_brain failed: {e}"

    # A search that came back empty (or thin) is the one place this tool can
    # learn something it did not already know.
    if action == "search" and params.get("query") and \
            not out.startswith(("search needs", "search:")):
        out = _maybe_auto_research(str(params.get("query")), out, player, speak)

    if out.startswith("theology_brain failed") or "failed" in out.split(".")[0]:
        print(f"[theology] {out}")
        if player:
            try:
                player.write_log(f"[theology] {out}")
            except Exception:
                pass
    return out


# ── Action contract (auto-discovered by core/action_loader.py) ───────────────

def theology_brain(parameters=None, response=None,
                   player=None, session_memory=None, speak=None) -> str:
    """Action handler: same work as run(), with the
    (parameters, response, player, session_memory, speak) signature the action
    loader uses."""
    return run(parameters or {}, player=player, session_memory=session_memory,
               speak=speak)


TOOL = {
    "name": "theology_brain",
    "description": PLUGIN["description"],
    "parameters": PLUGIN["parameters"],
    "handler": theology_brain,
}
