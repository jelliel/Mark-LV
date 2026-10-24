"""
The vault is consulted BEFORE the assistant answers — not because the model
was asked to, but because the application asks the vault itself.

The assistant has two ways to answer a theological question: from its own
memory, or from the user's own reading. The second is what a second brain is
for, and the first is what makes one pointless: a question answered from
memory is a question the vault never learns, and a question the vault cannot
answer is a question that should be bought once, researched, and filed.

So the question is measured here, in the light layer — no network, no model,
no heavy import — and the application sends what it finds to the conversation
before the model answers:

    a page whose TITLE carries the question  →  those pages, with their text
    a theological question the vault lacks   →  a deep research, started now
    anything else                            →  nothing; the model answers

The measurement is the same one `research/theology.py` uses to decide whether
a gap is a gap, so the two can never disagree: one implementation, one
verdict. That is the whole point of this file — the search the user sees and
the trigger that spends money are the same question, asked the same way.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_VOCAB = None
_BRIDGE = None


def _vocab():
    """research/vocab.py, loaded by path — actions/ is not a package."""
    global _VOCAB
    if _VOCAB is not None:
        return _VOCAB
    path = Path(__file__).resolve().parent.parent / "research" / "vocab.py"
    spec = importlib.util.spec_from_file_location("markliv_vocab", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vocab"] = module
    spec.loader.exec_module(module)
    _VOCAB = module
    return module


def _bridge():
    """actions/theology_brain.py, loaded by path — the vault's owner."""
    global _BRIDGE
    if _BRIDGE is not None:
        return _BRIDGE
    path = Path(__file__).resolve().parent / "theology_brain.py"
    spec = importlib.util.spec_from_file_location("markliv_vault_bridge", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vault_bridge"] = module
    spec.loader.exec_module(module)
    _BRIDGE = module
    return module


# ── what counts as a theological question ───────────────────────────────────
# Only used to decide whether a question the vault does NOT hold is worth a
# research run. A false positive here costs money, so the list is the strong
# one: a council, a father, a doctrine, a text, a school, a heresy. A question
# that only says "église" or "prière" is not enough — the vault stays silent
# and the assistant answers as it would anywhere else.
_STRONG = {
    # councils, fathers, doctors
    "concile", "council", "concilia", "augustin", "augustine", "aquin",
    "aquinas", "anselm", "bonaventure", "ockham", "calvin", "luther",
    "kierkegaard", "suyuti", "tabari", "al-tabari", "samarqandi", "al-ghazali",
    "ghazali", "ibn-kathir", "ibn-khattab", "al-suyuti", "cyran", "irenee",
    "irenaeus", "athanase", "athanasius", "basile", "gregoire", "leon",
    "tertulien", "terulian", "origene", "origen", "ambroise", "jerome",
    "hilarin", "anselm", "gerson", "duns-scotus", "scotus", "gottfried",
    # doctrines
    "dogme", "dogma", "dogmatique", "doctrine", "theologie", "theology",
    "trinité", "trinite", "trinity", "trinitaire", "trinitarian",
    "christologie", "christology", "mariologie", "mariology",
    "soteriologie", "soteriology", "pneumatologie", "pneumatology",
    "ecumenisme", "ecumenism", "homoousios", "homoousie", "apophatique",
    "kalam", "aqida", "adab", "tawhid", "shirk", "monotheisme",
    "polytheisme", "homoousie", "osis", "hypostase", "essence", "nature",
    "communication", "incarnation", "assomption", "immaculée", "virginite",
    "eucharistie", "eucharist", "bapteme", "baptism", "penitence", "sacrement",
    "sacrament", "sacerdoce", "priesthood", "sacerdoce", "imprimatur",
    "excommunication", "schisme", "schism", "heresie", "heresy",
    "gnostique", "gnosticism", "gnose", "gnosis", "arianisme", "arianism",
    "nestorianisme", "monophysitisme", "monophysitism", "pelagianisme",
    "hussite", "hussite", "cathare", "cathars", "inquisition", "jansenisme",
    "quietisme", "molinisme", "semipelagien", "monarche", "soteriologie",
    # schools and movements
    "scolastique", "scholastic", "scolastique", "ultramontain", "ultramontane",
    "catholique", "catholic", "catholicisme", "catholicism", "orthodoxe",
    "orthodox", "orthodoxie", "orthodoxy", "protestant", "protestantisme",
    "protestantism", "lutheranisme", "calvinisme", "anglicanisme",
    "trinitarien", "monophysite", "nestorien", "pelagien", "seminaires",
    "islam", "musulman", "muslim", "christianisme", "christianity",
    "judaïsme", "judaism", "syncretisme", "syncrhetism", "mysticisme",
    "mysticism", "scolastique", "reforme", "reformation", "council",
    # the texts
    "coran", "quran", "al-quran", "hadith", "sunna", "souna", "fiqh", "fatwa",
    "tafsir", "sira", "bida", "bidah", "bidaa", "wahhabi", "wahhabite",
    "salafi", "salafiste", "mu'tazili", "mutazila", "chafi'i", "hanbali",
    "maliki", "sunnite", "sunni", "chiite", "shia", "chiisme", "shiisme",
    "abrogation", "nasikh", "mansukh", "naskh", "polygnomie", "polygamie",
    "polygamy", "hijab", "zakat", "charite", "sacrifice", "apocalypse",
    "revelation", "genese", "genesis", "exode", "levitique", "deuteronome",
    "nombres", "josue", "juges", "royaumes", "chroniques", "esdras",
    "esth er", "job", "proverbes", "ecclesiaste", "cantique", "pseaumes",
    "psalms", "ezechiel", "daniel", "osee", "joel", "amos", "abdias",
    "jon as", "michee", "nahum", "habaquq", "sofonie", "aggee", "zacharie",
    "malachie", "evangile", "gospel", "gospels", "evangiles", "epitre",
    "epistle", "actes", "romains", "corinthiens", "galates", "ephasiens",
    "philippiens", "colossiens", "thesaloniciens", "timothee", "tite",
    "philemon", "hebreux", "jude", "apocalypse", "sermon", "homelie",
    "homilie", "synode", "synod", "encyclique", "encyclical", "catechisme",
    "missel", "liturgie", "eucharist", "exorcisme", "sacrement", "pelerinage",
    "pilgrimage", "heresy", "martyr", "martyrdom", "apostolat", "apostolate",
    "apostolicite", "monastique", "monastic", "benedictin", "jesuite",
    "franciscain", "dominicain", "carthusien", "hesychasme", "hesychasm",
    "hesychaste", "soufisme", "sufism", "sufi", "karmelite", "janseniste",
    # the institutions and the roles
    "pape", "pope", "eveque", "archeveque", "cardinal", "patriarche",
    "pretre", "priest", "imam", "sheikh", "scheikh", "ulama", "mufti",
    "ayatollah", "calife", "caliph", "chancelier", "legat", "nonce",
    "synode", "archimandrite", "ev hierarche", "metropolite", "exarque",
    "prophete", "prophet", "messie", "messiah", "saint", "sainte", "saints",
    "chretien", "chretien", "juif", "jewish", "mohamed", "muhammad",
    "maryam", "ibrahim", "moussa", "sulayman", "ayyub", "yunus", "idris",
    "madrasa", "medrese", "soufi", "waqf", "habous", "ribat", "khanqah",
    "sourate", "surate", "medina", "meque", "makkah", "kaaba", "ramadan",
    "eid", "fitr", "hajj", "omra", "zakat", "waqf", "sabil", "hadd",
    "ghusl", "janab", "najas", "tayammum", "iftar", "suhoor", "tarawih",
    "ottoman", "safavid", "mughal", "abbaside", "fatimide", "umayyad",
    "sanhedrin", "pharisee", "pharisien", "saducee", "samaritain",
    "grec", "greek", "latin", "arabe", "arabic", "hebreu", "hebrew",
    "syriaque", "syriac", "grecque", "armenien", "armenian", "persan",
    "persian", "ottoman", "moyen-age", "medieval", "medievale",
}

# Words that only make sense with the rest of a sentence — a subject term is
# never one of them, and a question made only of them is not a question about
# anything. Kept here rather than in the vocabulary because the router needs
# to recognise them in the RAW text, before the subject is extracted.
_IGNORED = {
    "what", "why", "how", "when", "who", "which", "explain", "tell", "says",
    "said", "think", "thought", "know", "please", "want", "need", "give",
    "show", "summarize", "summarise", "describe", "compare", "analyse",
    "analyze", "do", "does", "did", "can", "could", "would", "should", "is",
    "are", "was", "were", "be", "been", "the", "and", "for", "with", "about",
    "peux", "explique", "raconte", "penses", "dis", "donne", "montre",
    "resume", "parle", "merci", "salut", "bonjour",
}


def _marker_words(text: str) -> set[str]:
    """The significant words of a message, folded, without the framing."""
    vocab = _vocab()
    words = set(vocab.tokens(text))
    return {w for w in words if len(w) > 2 and w not in _IGNORED}


# Questions whose answer is a name, a date or a number. The assistant knows
# those; a sourced report bought with the user's quota would be absurd.
_SIMPLE_FACTS = {
    "qui", "when", "quand", "ou", "où", "combien", "where", "how",
    "howmany", "howmuch", "quel-age", "quelage",
}


def _is_simple_fact(text: str) -> bool:
    """Is this a question the assistant can answer without a report?

    "who is the pope", "when was Chalcédoine" — a name, a date, a number.
    A definition ("what is the homoousios") is NOT one of those: that is
    exactly the kind of question the vault exists to answer, and a sourced
    report is worth its cost."""
    words = [w for w in _vocab().tokens(text) if w]
    if not words:
        return True
    if words[0] not in _SIMPLE_FACTS:
        return False
    return len(words) <= 10


def _is_theological(text: str) -> bool:
    """Is this a question the vault would be the right place to look in?

    Only the strong list counts. A weak signal here would buy a report for a
    question that never needed one, and that is the one mistake this whole
    mechanism cannot afford."""
    if _is_simple_fact(text):
        return False
    words = _marker_words(text)
    if not words:
        return False
    if words & _STRONG:
        return True
    # "Saint Augustin", "Père Lagrange" — a name in the strong list, in a
    # phrase the vocabulary would have thrown away.
    vocab = _vocab()
    for word in vocab.tokens(text):
        if vocab.canonical(word) in _STRONG:
            return True
    return False


# ── the measurement ─────────────────────────────────────────────────────────

_TITLE_TOKENS: dict[str, set[str]] = {}
_MEASURED: dict[tuple, dict] = {}
_MEASURED_MAX = 64
_PAGE_TOKENS: dict[str, tuple] = {}
_TOKENS_STAMP = None


def _page_tokens(page: dict, stamp):
    """The canonical words of a page, counted once.

    The vault is tokenised once per change, not once per question: a
    measurement that re-reads ninety pages for every fragment of speech would
    cost more than the answer it is meant to improve."""
    global _TOKENS_STAMP
    if _TOKENS_STAMP != stamp:
        _PAGE_TOKENS.clear()
        _TOKENS_STAMP = stamp
    key = str(page["path"])
    cached = _PAGE_TOKENS.get(key)
    if cached is None:
        cached = _vocab().page_tokens(page["title"], page["body"])
        _PAGE_TOKENS[key] = cached
    return cached


def _title_terms(title: str) -> set[str]:
    """The canonical words of a page title, cached by title."""
    cached = _TITLE_TOKENS.get(title)
    if cached is None:
        vocab = _vocab()
        cached = {vocab.canonical(w) for w in vocab.tokens(title)}
        _TITLE_TOKENS[title] = cached
    return cached


def measure(query: str, vault=None) -> dict:
    """How well the vault answers this question. The one measurement.

    Returns a plain dict so the light layer (this file) and the research
    engine (which spends money on the verdict) can share it without importing
    each other.

    The measurement is memoised against the vault's fingerprint: a question
    arrives in pieces, and the same words are measured again and again while
    the user is still speaking."""
    vocab = _vocab()
    bridge = _bridge()
    terms = vocab.subject_terms(query)
    if not terms:
        return {"query": str(query or ""), "terms": [], "pages": 0, "hits": 0,
                "best_title": "", "best_score": 0, "best_coverage": 0.0,
                "raw_hits": 0, "gap": False, "reason": "requête trop courte",
                "subject": "", "matches": [], "df": {}, "df_title": {}}
    try:
        root = Path(vault) if vault else Path(bridge._vault())
    except Exception:
        root = None
    key = (str(root), tuple(terms),
           bridge.page_index_stamp(root) if root else None)
    cached = _MEASURED.get(key)
    if cached is not None:
        return cached

    result = {
        "query": str(query or ""), "terms": terms, "pages": 0, "hits": 0,
        "best_title": "", "best_score": 0, "best_coverage": 0.0,
        "raw_hits": 0, "gap": False, "reason": "", "subject": "",
        "matches": [], "df": {}, "df_title": {},
    }
    try:
        if not root.is_dir():
            result["reason"] = "vault introuvable"
            return result
        stamp = bridge.page_index_stamp(root)
        df = {t: 0 for t in terms}
        df_title = {t: 0 for t in terms}
        rows = []
        for page in bridge.page_index(root):
            result["pages"] += 1
            counts, title_words = _page_tokens(page, stamp)
            matched = [t for t in terms if t in counts]
            if not matched:
                continue
            result["hits"] += 1
            for t in matched:
                df[t] += 1
                if t in title_words:
                    df_title[t] += 1
            score = sum(counts[t] for t in matched)
            share = len(matched) / len(terms)
            rows.append({"page": page, "counts": counts, "matched": matched,
                         "score": score, "share": share,
                         "title_words": title_words,
                         "titled": [t for t in matched if t in title_words]})
            if (share, score) > (result["best_coverage"], result["best_score"]):
                result["best_coverage"] = share
                result["best_score"] = score
                result["best_title"] = page["title"]
        result["df"] = df
        result["df_title"] = df_title
        result["matches"] = rows
        result["raw_hits"] = _raw_hits(root, terms)
    except Exception as e:
        print(f"[VaultRouter] measurement failed: {type(e).__name__}: {e}")
        result["reason"] = "vault illisible"
        return result

    _decide(result)
    if len(_MEASURED) >= _MEASURED_MAX:
        _MEASURED.clear()
    _MEASURED[key] = result
    return result


def _raw_hits(vault: Path, terms: list[str]) -> int:
    raw = vault / "raw"
    if not raw.is_dir():
        return 0
    try:
        files = [p for p in raw.glob("*") if p.is_file()][:500]
    except OSError:
        return 0
    vocab = _vocab()
    hits = 0
    for path in files:
        words = {vocab.canonical(w) for w in vocab.tokens(path.stem)}
        if words & set(terms):
            hits += 1
    return hits


def _decide(result: dict) -> None:
    """The verdict, given the counts. One place, used by everyone."""
    if result["pages"] == 0:
        result["reason"] = ("sources brutes non structurées" if result["raw_hits"]
                            else "vault vide")
        return
    if result["hits"] == 0:
        if result["raw_hits"]:
            result["reason"] = "source brute non structurée — à structurer d'abord"
        else:
            result["gap"] = True
            result["reason"] = "aucune page"
        return

    terms = result["terms"]
    df = result["df"]
    df_title = result["df_title"]
    titled = [t for t in terms if df_title.get(t, 0) > 0]
    if titled:
        subject = max(titled, key=lambda t: (df_title.get(t, 0), df.get(t, 0),
                                             len(t)))
        result["subject"] = subject
        missing = [t for t in terms if t != subject and df.get(t, 0) == 0]
        if missing:
            result["gap"] = True
            result["reason"] = "couverture insuffisante"
        return

    vocab = _vocab()
    proper = vocab.proper_terms(result["query"])
    candidates = [t for t in terms if t in proper] or list(terms)
    subject = min(candidates, key=lambda t: (df.get(t, 0), -len(t)))
    result["subject"] = subject
    best = max((r for r in result["matches"] if subject in r["matched"]),
               key=lambda r: (r["share"], r["score"]), default=None)
    if best is None or best["share"] < 1.0:
        result["gap"] = True
        result["reason"] = "mention unique"


# ── the route ───────────────────────────────────────────────────────────────

_EXCERPT = 320


def warm(vault=None) -> bool:
    """Read the vault once, so the first question does not pay for it.

    Fifty milliseconds is nothing in a conversation, but it is a pause in the
    middle of a voice turn — and the vault is read anyway at every start."""
    try:
        bridge = _bridge()
        root = Path(vault) if vault else Path(bridge._vault())
        if not root.is_dir():
            return False
        stamp = bridge.page_index_stamp(root)
        for page in bridge.page_index(root):
            _page_tokens(page, stamp)
        return True
    except Exception as e:
        print(f"[VaultRouter] warm-up failed: {e}")
        return False


_ALL_TITLE_TOKENS: set[str] = set()
_ALL_TOKENS_STAMP = None


def _all_title_tokens(vault) -> set[str]:
    """Every word that appears in a page title, in one set.

    The fast path asks one question — "is any word of this message in some
    title?" — and a set answers it without walking the pages."""
    global _ALL_TOKENS_STAMP
    bridge = _bridge()
    try:
        root = Path(vault) if vault else Path(bridge._vault())
        if not root.is_dir():
            return set()
        stamp = bridge.page_index_stamp(root)
    except Exception:
        return set()
    if _ALL_TOKENS_STAMP == stamp:
        return _ALL_TITLE_TOKENS
    words: set[str] = set()
    try:
        for page in bridge.page_index(root):
            words |= _title_terms(page["title"])
    except Exception:
        return set()
    _ALL_TITLE_TOKENS.clear()
    _ALL_TITLE_TOKENS.update(words)
    _ALL_TOKENS_STAMP = stamp
    return _ALL_TITLE_TOKENS


def _mentions_a_subject(text: str, vault=None) -> bool:
    """Could this message be about something the vault holds?

    A cheap look: the words of the message against the titles of the pages.
    It answers "is this the vault's business" without measuring anything, so
    the ordinary conversation pays almost nothing for the mechanism."""
    vocab = _vocab()
    terms = set(vocab.subject_terms(text))
    if not terms:
        return False
    return bool(terms & _all_title_tokens(vault))


def route(text: str, vault=None) -> dict:
    """What to do with this message, before the model answers it.

    {"kind": "vault", "pages": [...], "context": "..."} — the vault holds
    pages on this; here they are.
    {"kind": "gap", "context": "..."} — a theological question the vault does
    not hold; the research is started by the caller.
    {"kind": "none"} — not the vault's business; say nothing.
    """
    query = " ".join(str(text or "").split())
    if not query:
        return {"kind": "none"}
    # The fast path: neither a religious subject nor anything the vault holds
    # a page about. Most messages end here, and end here cheaply.
    if not (_is_theological(query) or _mentions_a_subject(query, vault)):
        return {"kind": "none"}
    measured = measure(query, vault)
    if not measured["terms"]:
        return {"kind": "none"}

    pages = _relevant_pages(measured)
    if pages:
        return {"kind": "vault", "pages": pages,
                "context": _vault_context(pages), "measured": measured}

    # Nothing in the vault: a religious subject is a hole worth filling, and
    # anything else is none of the vault's business.
    if _is_theological(query):
        return {"kind": "gap", "context": "", "measured": measured}
    return {"kind": "none", "measured": measured}


def _relevant_pages(measured: dict) -> list[dict]:
    """The pages that carry the question: their title holds one of its terms,
    and they come with the text that answers it."""
    out = []
    for row in measured["matches"]:
        page = row["page"]
        titled = row["titled"]
        if not titled:
            continue
        out.append({"title": page["title"], "kind": page["dir"],
                    "text": page["body"][:_EXCERPT].strip()})
    out.sort(key=lambda p: -len(p["title"]))
    return out[:3]


def _vault_context(pages: list[dict]) -> str:
    """What the conversation is told, before the model answers."""
    lines = ["[VAULT] The user's theology vault holds what it has on this:"]
    for page in pages:
        text = " ".join(str(page["text"]).split())
        if len(text) > _EXCERPT:
            text = text[:_EXCERPT].rstrip() + "…"
        lines.append(f"- [[{page['title']}]] ({page['kind']}) — {text}")
    lines.append("Answer from these pages and cite them ([[Page Title]]). "
                 "If they do not settle the question, say so plainly.")
    return "\n".join(lines)
