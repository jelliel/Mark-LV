"""
dashboard/mindmap.py — assembles the "Living Mind" skeleton.

Pure assembly function: takes explicit sources (the theology vault bridge, the
agent profiles, the session history), returns a flat list of nodes and edges
plus a stats block. Every region is built inside its own try, so a broken
source empties THAT region only and records `"error"` in the stats — it never
returns a 500 and never fakes data.

Regions (mirrors the living-mind vision):
  core      — Theologicus itself
  memory    — the vault's pages, wired by tag co-occurrence (no embeddings here)
  agents    — the theology agent team
  knowledge — the always-loaded self-knowledge doc
  tools     — the action registry

Node ids are namespaced by prefix so the frontend can route on them:
  core:theologicus, mem:<slug>, agent:<slug>, know:<slug>, tool:<name>
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# ── Region colours (from the living-mind palette) ────────────────────────────
REGION_COLORS = {
    "core":      "#2DD4A8",   # teal
    "memory":    "#A78BFA",   # violet
    "working":   "#67E8F9",   # cyan
    "agents":    "#E88FB3",   # rose
    "knowledge": "#F5A524",   # amber
    "tools":     "#8B93A1",   # slate
}

MAX_MEMORY_NODES = 400        # ponytail: cap the population, tell the user
SIM_TOP_K        = 3          # nearest neighbours per memory
SIM_THRESHOLD    = 0.35       # "these are about the same thing" starts here


def _hash_id(text: str) -> str:
    """FNV-1a-ish stable hash → a hex string. Same input, same id, always."""
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return h[:12]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "")).strip("-").lower()
    return s[:60] or "untitled"


def _freshness(path: Path) -> float:
    """Exponential decay on age: 0.5 ** (age_days / 30), floored at 0.15.

    Recent memories burn brighter than old ones. No timestamp → 1.0 for all
    (equal brightness), never an invented age."""
    try:
        import time
        mtime = path.stat().st_mtime
        age_days = max(0.0, (time.time() - mtime) / 86400.0)
        return max(0.15, 0.5 ** (age_days / 30.0))
    except Exception:
        return 1.0


def _tokens(text: str) -> set[str]:
    """Lowercased word set, stopwords dropped. Used for tag co-occurrence."""
    stop = {"the", "and", "for", "with", "that", "this", "from", "des", "les",
            "une", "est", "dans", "pour", "que", "qui", "sur", "par", "avec"}
    words = re.findall(r"[\wà-ÿ]{3,}", str(text or "").lower())
    return {w for w in words if w not in stop}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── Region builders ──────────────────────────────────────────────────────────

def _build_core() -> tuple[list[dict], list[dict]]:
    nodes = [{
        "id": "core:theologicus",
        "type": "core",
        "region": "core",
        "label": "THEOLOGICUS",
        "color": REGION_COLORS["core"],
        "size": 3.0,
        "freshness": 1.0,
        "extra": {"kind": "agent core"},
    }]
    return nodes, []


def _build_agents(profiles) -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    for p in profiles or []:
        name = getattr(p, "name", None) or str(p)
        desc = getattr(p, "description", "") or ""
        nid = f"agent:{_slug(name)}"
        nodes.append({
            "id": nid,
            "type": "agent",
            "region": "agents",
            "label": name,
            "color": REGION_COLORS["agents"],
            "size": 1.6,
            "freshness": 1.0,
            "extra": {"specialty": desc[:200]},
        })
        edges.append({
            "source": "core:theologicus", "target": nid,
            "kind": "trunk", "weight": 1.0,
        })
    return nodes, edges


def _build_memory(bridge, vault: Path) -> tuple[list[dict], list[dict], dict]:
    """Vault pages as memory nodes, wired by tag/title co-occurrence.

    No embedding index exists in this project — the edges are lexical, and the
    stats say so honestly rather than passing them off as semantic."""
    nodes, edges = [], []
    stats = {"total": 0, "shown": 0, "edges_kind": "lexical"}
    if bridge is None or vault is None:
        return nodes, edges, stats

    try:
        pages = list(bridge._iter_pages(vault))
    except Exception:
        return nodes, edges, stats

    stats["total"] = len(pages)
    # Cap the population — sort by freshness so the newest survive the cut.
    try:
        pages.sort(key=lambda p: _freshness(p[1]), reverse=True)
    except Exception:
        pass
    pages = pages[:MAX_MEMORY_NODES]
    stats["shown"] = len(pages)

    token_sets: dict[str, set[str]] = {}
    for dirname, path in pages:
        try:
            meta, body = bridge._read_page(path)
        except Exception:
            continue
        title = str(meta.get("title") or path.stem)
        tags = str(meta.get("tags") or "")
        # Co-occurrence key set: the title's words plus its tags.
        toks = _tokens(title) | {t.strip().lower() for t in tags.split(",") if t.strip()}
        nid = f"mem:{_hash_id(str(path))}"
        token_sets[nid] = toks
        nodes.append({
            "id": nid,
            "type": "memory",
            "region": "memory",
            "label": title[:70],
            "color": REGION_COLORS["memory"],
            "size": 1.0,
            "freshness": _freshness(path),
            "extra": {
                "kind": dirname,
                "tags": tags[:120],
                "path": str(path),
                "body_preview": str(body or "")[:200],
            },
        })

    # Similarity edges: top-K neighbours above the threshold, deduped.
    ids = list(token_sets.keys())
    seen_pairs: set[tuple[str, str]] = set()
    for i, a in enumerate(ids):
        scored = []
        for b in ids[i + 1:]:
            score = _jaccard(token_sets[a], token_sets[b])
            if score >= SIM_THRESHOLD:
                scored.append((score, b))
        scored.sort(reverse=True)
        for score, b in scored[:SIM_TOP_K]:
            pair = (a, b)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            edges.append({
                "source": a, "target": b,
                "kind": "similarity", "weight": round(score, 3),
            })

    # Degree → size (well-connected pages are physically bigger).
    degree: dict[str, int] = {}
    for e in edges:
        if e["kind"] == "similarity":
            degree[e["source"]] = degree.get(e["source"], 0) + 1
            degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes:
        if n["region"] == "memory":
            n["size"] = 1.0 + 0.35 * degree.get(n["id"], 0)

    # The three highest-degree pages get recall trunks back to the core.
    trunks = sorted(
        (n for n in nodes if n["region"] == "memory"),
        key=lambda n: degree.get(n["id"], 0), reverse=True,
    )[:3]
    if not trunks:
        # Sparse web: pad with the freshest pages so recall always flows core-ward.
        trunks = [n for n in nodes if n["region"] == "memory"][:3]
    for n in trunks:
        edges.append({
            "source": "core:theologicus", "target": n["id"],
            "kind": "recall", "weight": 1.0,
        })
    return nodes, edges, stats


def _build_knowledge(bridge, vault: Path) -> tuple[list[dict], list[dict]]:
    """The always-loaded self-knowledge doc — one node, if it exists."""
    nodes, edges = [], []
    if bridge is None or vault is None:
        return nodes, edges
    try:
        doc = vault / "_self_knowledge.md"
        if not doc.exists():
            return nodes, edges
        nodes.append({
            "id": "know:self-knowledge",
            "type": "knowledge",
            "region": "knowledge",
            "label": "_self_knowledge.md",
            "color": REGION_COLORS["knowledge"],
            "size": 1.4,
            "freshness": _freshness(doc),
            "extra": {"path": str(doc)},
        })
        edges.append({
            "source": "core:theologicus", "target": "know:self-knowledge",
            "kind": "trunk", "weight": 1.0,
        })
    except Exception:
        pass
    return nodes, edges


def _build_tools(registry) -> tuple[list[dict], list[dict]]:
    """The action registry — the agent's capability inventory."""
    nodes, edges = [], []
    if registry is None:
        return nodes, edges
    try:
        names = list(registry.list_for_ui()) if hasattr(registry, "list_for_ui") else []
    except Exception:
        names = []
    for entry in names:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "")
            desc = str(entry.get("description") or "")
        else:
            name = str(entry)
            desc = ""
        if not name:
            continue
        nid = f"tool:{_slug(name)}"
        nodes.append({
            "id": nid,
            "type": "tool",
            "region": "tools",
            "label": name[:50],
            "color": REGION_COLORS["tools"],
            "size": 0.8,
            "freshness": 1.0,
            "extra": {"description": desc[:160]},
        })
        edges.append({
            "source": "core:theologicus", "target": nid,
            "kind": "trunk", "weight": 0.6,
        })
    return nodes, edges


def _build_working(session_log) -> tuple[list[dict], list[dict]]:
    """Recent conversation turns as a small working-memory ring."""
    nodes, edges = [], []
    turns = list(session_log or [])[-12:]
    for i, turn in enumerate(turns):
        if isinstance(turn, dict):
            text = str(turn.get("text") or "")
        else:
            text = str(turn)
        text = text.strip()
        if not text:
            continue
        nid = f"thread:{_hash_id(text + str(i))}"
        nodes.append({
            "id": nid,
            "type": "thread",
            "region": "working",
            "label": text[:60],
            "color": REGION_COLORS["working"],
            "size": 0.9,
            "freshness": 1.0,
            "extra": {"text": text[:300]},
        })
        edges.append({
            "source": "core:theologicus", "target": nid,
            "kind": "trunk", "weight": 0.8,
        })
    return nodes, edges


# ── The assembly function ────────────────────────────────────────────────────

def build_skeleton(bridge=None, vault=None, profiles=None, registry=None,
                   session_log=None) -> dict:
    """Assemble the mind-map skeleton. Every region is isolated in its try."""
    regions = []
    nodes: list[dict] = []
    edges: list[dict] = []
    stats: dict = {"memory_total": 0, "memory_shown": 0, "sources": 0,
                   "regions": {}}

    def _region(name: str, fn) -> None:
        try:
            r_nodes, r_edges = fn()
            nodes.extend(r_nodes)
            edges.extend(r_edges)
            regions.append({
                "name": name,
                "color": REGION_COLORS.get(name, "#8B93A1"),
                "count": len(r_nodes),
            })
            stats["regions"][name] = "ok"
        except Exception as e:
            stats["regions"][name] = f"error: {e}"
            regions.append({
                "name": name,
                "color": REGION_COLORS.get(name, "#8B93A1"),
                "count": 0,
            })

    _region("core", lambda: _build_core())
    _region("agents", lambda: _build_agents(profiles))

    # The memory region returns a third value (its own stats) — handle it apart.
    try:
        m_nodes, m_edges, m_stats = _build_memory(bridge, vault)
        nodes.extend(m_nodes)
        edges.extend(m_edges)
        regions.append({"name": "memory",
                        "color": REGION_COLORS["memory"],
                        "count": len(m_nodes)})
        stats["regions"]["memory"] = "ok"
        stats["memory_total"] = m_stats["total"]
        stats["memory_shown"] = m_stats["shown"]
        stats["memory_edges"] = m_stats["edges_kind"]
    except Exception as e:
        stats["regions"]["memory"] = f"error: {e}"
        regions.append({"name": "memory",
                        "color": REGION_COLORS["memory"], "count": 0})

    _region("knowledge", lambda: _build_knowledge(bridge, vault))
    _region("working", lambda: _build_working(session_log))
    _region("tools", lambda: _build_tools(registry))

    stats["sources"] = len(nodes)
    stats["edges"] = len(edges)
    return {
        "regions": regions,
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }


if __name__ == "__main__":
    # Smoke check: an empty skeleton is still a valid skeleton.
    s = build_skeleton()
    assert s["stats"]["sources"] >= 1, "the core node must always exist"
    assert any(r["name"] == "core" for r in s["regions"])
    print(f"OK — {s['stats']['sources']} nodes, {s['stats']['edges']} edges, "
          f"regions: {list(s['stats']['regions'])}")
