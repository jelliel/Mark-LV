"""
MARK-LIV action — XERJ (local Elasticsearch-compatible AI search).

Recherche locale pour agents (binaire unique, hors-ligne) qui rend le second
cerveau cherchable PAR LE SENS : recall sémantique sur les sources ingérées
(ax-docs) et sur le wiki (ax-vault-wiki, corps Markdown indexé — le parseur
autoindex ne capture pas les .md), mémoire d'agent par signification
('/_memory/<ns>'), plus backfill/reindex.

Stdlib uniquement (urllib). Nœud http://localhost:9200 par défaut
(config: xerj_url, xerj_memory_namespace, xerj_bin). JAMAIS de blocage :
si le nœud est arrêté, repli sur theology_brain (local, instantané).

Demandes naturelles : « cherche dans tout le vault par le sens », « souviens-toi
que … », « qu'as-tu retenu sur X ? », « état de XERJ », « ré-indexe le vault ».
"""

import http.client
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

_URL_KEY    = "xerj_url"
_NS_KEY     = "xerj_memory_namespace"
_BIN_KEY    = "xerj_bin"
_WIKI_INDEX = "ax-vault-wiki"


def _config() -> dict:
    path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _base_url() -> str:
    return str(_config().get(_URL_KEY) or "http://localhost:9200").rstrip("/")


def _namespace() -> str:
    return str(_config().get(_NS_KEY) or "markliv")


def _clip(body: str, limit: int = 420) -> str:
    body = " ".join(str(body or "").split())
    return body[:limit] + ("…" if len(body) > limit else "")


# Un SEUL client HTTP persistant et sans délai Nagle : sur cette machine,
# chaque nouvelle connexion coûte ~2 s (delayed-ACK vs serveur) — la première
# requête du backfill subissait ce délai × pages, et le test dépassait 300 s.
_es_conn = None
_es_url = ""


def _conn(timeout: float = 8.0):
    global _es_conn, _es_url
    url = _base_url()
    if _es_conn is None or _es_url != url:
        _es_conn, _es_url = http.client.HTTPConnection(url.split("//", 1)[1],
                                                       timeout=timeout), url
    if _es_conn.sock is not None:
        try:
            _es_conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
    return _es_conn


def _http(method: str, path: str, payload=None, timeout: float = 8.0):
    """Requête ES sur la connexion persistante ; recréée après toute erreur."""
    global _es_conn
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"content-type": "application/json"} if data else {}
    for attempt in (1, 2):
        try:
            conn = _conn(timeout)
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except Exception:
                return raw
        except Exception:
            _es_conn = None                 # connexion morte → re-créée
            if attempt == 2:
                raise


def _theology_brain():
    try:
        import importlib.util
        path = Path(__file__).resolve().with_name("theology_brain.py")
        spec = importlib.util.spec_from_file_location("xerj_theology_brain", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[Xerj] theology_brain load failed: {e}")
        return None


def _fmt_semantic(resp) -> str:
    hits = (resp or {}).get("hits", {}).get("hits", [])
    if not hits:
        return "Aucun passage trouvé."
    lines = []
    for h in hits:
        src = h.get("_source") or {}
        lines.append(f"- [[{src.get('title')}]] ({src.get('kind')}, score "
                     f"{h.get('_score', 0):.2f}) — {_clip(src.get('body'))}")
    return "\n".join(lines)


def _fallback(query: str, reason: str, player=None, speak=None) -> str:
    bridge = _theology_brain()
    if bridge is None:
        return f"XERJ injoignable ({reason}) et theology_brain introuvable."
    # The vault search itself decides whether this is a gap worth a deep run
    # and appends the note; passing player/speak keeps the announcement alive.
    local = bridge.run({"action": "search", "query": query},
                       player=player, speak=speak)
    return (f"XERJ injoignable ({reason}) — repli sur la recherche locale du "
            f"vault :\n{local}")


def _maybe_auto_research(out: str, query: str, player=None, speak=None) -> str:
    """Semantic search found nothing — let the vault-gap trigger decide."""
    try:
        root = Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from research import theology as bridge
        note = bridge.maybe_start(query, player=player, speak=speak,
                                  source="xerj")
    except Exception as e:
        print(f"[Xerj] auto-research bridge failed: {e}")
        return out
    return (out + "\n\n" + note) if note else out


def _ensure_wiki_index() -> None:
    mapping = {"mappings": {"properties": {
        "body":  {"type": "semantic_text"},
        "title": {"type": "text"},
        "kind":  {"type": "keyword"},
        "tags":  {"type": "keyword"},
        "sources": {"type": "keyword"},
        "updated": {"type": "date"},
    }}}
    try:
        _http("PUT", f"/{_WIKI_INDEX}", mapping, timeout=8.0)
    except Exception:
        pass                      # déjà existant → 400, sans gravité


def _wiki_upsert(tb, page_path: Path) -> bool:
    """Indexe (ou ré-indexe) UNE page wiki dans ax-vault-wiki. Best effort."""
    try:
        meta, body = tb._read_page(page_path)
        doc = {
            "title":   tb._page_title(page_path, meta) or page_path.stem,
            "kind":    str(meta.get("kind") or ""),
            "tags":    str(meta.get("tags") or ""),
            "sources": str(meta.get("sources") or ""),
            "updated": str(meta.get("updated") or tb._today()),
            "body":    body or "",
        }
        _ensure_wiki_index()
        _http("PUT", f"/{_WIKI_INDEX}/_doc/{tb._slugify(doc['title'])}",
              doc, timeout=8.0)
        return True
    except Exception as e:
        print(f"[Xerj] wiki upsert failed for {page_path.name}: {e}")
        return False


def xerj_search(parameters: dict, player=None, speak=None) -> str:
    parameters = parameters or {}
    action = str(parameters.get("action") or "semantic").strip().lower()
    query  = str(parameters.get("query") or "").strip()
    kind   = str(parameters.get("kind") or "any").strip().lower()
    limit  = max(int(parameters.get("limit") or 5), 1)

    # ── status : aucune requête requise ──────────────────────────────────
    if action == "status":
        try:
            health = _http("GET", "/_cluster/health", timeout=5.0)
            return (f"XERJ en ligne sur {_base_url()} — cluster "
                    f"{health.get('status')} ({health.get('number_of_nodes')} "
                    f"nœud(s)) ; indexes ax-docs (sources brutes), ax-wiki "
                    f"(frontmatter), {_WIKI_INDEX} (pages wiki, sémantique).")
        except Exception as e:
            return (f"XERJ injoignable sur {_base_url()} ({e}) — Mark LV "
                    "retombe sur la recherche locale du vault.")

    # ── backfill wiki : le parseur autoindex ignore le corps des .md ─────
    if action == "backfill":
        tb = _theology_brain()
        if tb is None:
            return "theology_brain introuvable — backfill impossible."
        n = 0
        for _dirname, page in tb._iter_pages(tb._vault()):
            n += 1 if _wiki_upsert(tb, page) else 0
        try:
            _http("POST", f"/{_WIKI_INDEX}/_refresh", timeout=8.0)
        except Exception:
            pass
        return f"Backfill wiki : {n} page(s) indexée(s) dans {_WIKI_INDEX}."

    # ── re-autoindex CLI des sources brutes (ax-docs) ────────────────────
    if action == "reindex":
        tb = _theology_brain()
        vault = str(tb._vault()) if tb else \
            str(Path.home() / "Documents" / "Theology")
        exe = str(_config().get(_BIN_KEY) or
                  os.path.join(os.environ.get("LOCALAPPDATA", ""),
                               "Programs", "xerj", "xerj.exe") or "xerj")
        try:
            out = subprocess.run([exe, "autoindex", vault],
                                 capture_output=True, text=True,
                                 creationflags=getattr(subprocess,
                                                       "CREATE_NO_WINDOW", 0),
                                 timeout=600)
            tail = (out.stdout or out.stderr or "").strip().splitlines()
            return "Re-autoindex : " + (tail[-1] if tail else "terminé.")
        except FileNotFoundError:
            return ("xerj introuvable (config xerj_bin) — re-autoindex "
                    "impossible ; l'indexation wiki à la volée reste active.")
        except Exception as e:
            return f"Re-autoindex en échec : {e}"

    query_needed = {"semantic", "search", "recherche", "remember", "memory_store",
                    "retiens", "recall", "memory_recall", "souviens"}
    if action not in query_needed:
        return (f"action inconnue '{action}' — actions : semantic/search (par "
                "le sens), remember, recall, status, backfill, reindex.")
    if not query:
        return "xerj_search a besoin d'un 'query' pour cette action."

    # ── recherche (recall par le sens) ───────────────────────────────────
    if action in ("semantic", "search", "recherche"):
        try:
            if kind in ("raw", "docs", "documents"):
                resp = _http("POST", "/ax-docs/_search", {
                    "size": limit,
                    "_source": ["body"],         # body_vector exclu
                    "query": {"semantic": {"field": "body", "query": query}},
                })
                hits = (resp or {}).get("hits", {}).get("hits", [])
                if not hits:
                    return _maybe_auto_research("Aucun passage.", query,
                                                player, speak)
                lines = [f"- {h.get('_score', 0):.2f} — "
                         f"{_clip(((h.get('_source') or {}).get('body')) or '(passage)')}"
                         for h in hits]
                return "Passages (sources brutes) :\n" + "\n".join(lines)
            resp = _http("POST", f"/{_WIKI_INDEX}/_search", {
                "size": limit,
                "query": {"semantic": {"field": "body", "query": query}},
            })
            out = _fmt_semantic(resp)
            if out.startswith("Aucun passage"):
                return _maybe_auto_research(out, query, player, speak)
            return out
        except Exception as e:
            return _fallback(query, str(e), player=player, speak=speak)

    # ── mémoire d'agent (namespace durable, recall par le sens) ──────────
    if action in ("remember", "memory_store", "retiens"):
        try:
            resp = _http("POST", f"/_memory/{_namespace()}",
                         {"text": query, "metadata": {"kind": "markliv"}})
            return (f"Retenu ({resp.get('id')}) dans '{_namespace()}' : "
                    f"{_clip(query, 140)}")
        except Exception as e:
            return f"Mémoire XERJ indisponible ({e}) — rien retenu."

    if action in ("recall", "memory_recall", "souviens"):
        try:
            resp = _http("POST", f"/_memory/{_namespace()}/_recall",
                         {"query": query, "semantic": True, "k": max(limit, 5)})
            hits = resp.get("hits", [])
            if not hits:
                return f"Rien de retenu dans '{_namespace()}' à ce sujet."
            return "\n".join(f"- {h.get('score', 0):.2f} {h.get('text', '')}"
                             for h in hits)
        except Exception as e:
            return f"Mémoire XERJ indisponible ({e})."

    return (f"action inconnue '{action}' — actions : semantic/search (par le "
            "sens), remember, recall, status, backfill, reindex.")


TOOL = {
    "name": "xerj_search",
    "description": (
        "Local semantic search over everything Mark-LIV ingested - powered by "
        "XERJ, an offline Elasticsearch-compatible engine (localhost:9200). "
        "Use it to recall theology vault passages and raw documents BY MEANING "
        "(action='semantic': default searches the vault wiki pages, "
        "kind='raw' searches the ingested docx/pdf passages; queries in French "
        "work though the sources are French), to store durable agent memories "
        "(action='remember') and recall them by meaning in later sessions "
        "(action='recall'), check the engine (action='status'), backfill the "
        "wiki pages (action='backfill') or re-run the raw autoindex "
        "(action='reindex'). Falls back to the vault's local keyword search "
        "automatically when the engine is not running. "
        "ROUTE: for a theological question, search the vault with "
        "theology_brain FIRST (it is instant and local), and use this tool "
        "when that search came back thin - it finds pages by meaning, not by "
        "word. Then, and only then, the web."
    ),

    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": ("semantic (default) | remember | recall | "
                                "status | backfill | reindex"),
            },
            "query": {
                "type": "STRING",
                "description": ("Search text, any language (semantic handles "
                                "meaning); for remember: the fact to keep."),
            },
            "kind": {
                "type": "STRING",
                "description": ("'raw'/'docs' → raw ingested documents "
                                "(docx/pdf passages); default → vault wiki "
                                "pages."),
            },
            "limit": {
                "type": "INTEGER",
                "description": "Max results (default 5).",
            },
        },
        "required": [],
    },
    "handler": xerj_search,
}
