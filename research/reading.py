"""
The reading of a research run — what the material holds on the subject, in the
authorities it speaks with, with its weight marked.

A deep report is a document: sections, claims, citations, a method. What the
user asks for when a run finishes is not a document but a READING — the
subject first, then each point with the authority it speaks with, its weight
marked, and what stays open. The vault search already returns one (the reading
frame in `actions/_vault_router.py`); this module is the same reading on the
research path, where it can be COMPOSED AND CHECKED rather than merely asked
for.

Three decisions worth defending:

ONE COMPOSITION, TWO SURFACES.  The reading is composed once, from the outline
the run already produced, and stored on the run (`run.reading`). The spoken
announcement at the end of the run and the synthesis page filed into the vault
are two renderings of that one structure. A reading that is said one way and
filed another is two readings, and the vault would eventually contradict the
voice.

THE VOCABULARY IS CLOSED.  An authority outside the five (Scripture, Tradition,
magisterial teaching, scholarship, practice and custom) or a weight outside the
four (defined, commonly held, disputed, one author's opinion) is not a reading,
it is an improvisation. Validation drops what falls outside, item by item, and
drops the whole reading when nothing valid is left. The sub-agent prompt asks
for the closed sets by name; this module enforces them, so a prompt that is
retuned — or replaced by a user's own `agents/theologian.md` — cannot smuggle
a sixth authority into what gets spoken.

A READING IS NOT A REPORT.  It is composed from the outline the run already
produced, not from the web a second time, so it cannot say anything the report
does not say — and every source number it carries is one the run actually
fetched, checked here the same way `report.sanitise_citations` checks the
prose.
"""
from __future__ import annotations

from . import vocab

# The closed sets. The sub-agent is asked for one of each by name; anything
# outside them is dropped here rather than spoken.
AUTHORITIES = ("scripture", "tradition", "magisterial", "scholarship", "practice")
WEIGHTS = ("defined", "common", "disputed", "opinion")

# A model that answers "Magisterial teaching" or "one author's opinion" has
# understood the frame; it just did not use our word for it. Fold, then match.
_AUTHORITY_ALIASES = {
    "scripture": "scripture", "scriptures": "scripture", "bible": "scripture",
    "ecriture": "scripture", "sainte ecriture": "scripture",
    "tradition": "tradition", "fathers": "tradition", "peres": "tradition",
    "liturgy": "tradition", "liturgie": "tradition",
    "magisterial": "magisterial", "magisterium": "magisterial",
    "magistere": "magisterial", "church teaching": "magisterial",
    "magisterial teaching": "magisterial", "teaching": "magisterial",
    "enseignement magisteriel": "magisterial",
    "scholarship": "scholarship", "academic": "scholarship",
    "scholars": "scholarship", "research": "scholarship",
    "etude": "scholarship", "recherche": "scholarship",
    "practice": "practice", "custom": "practice", "usage": "practice",
    "coutume": "practice", "practice and custom": "practice",
    "usage et coutume": "practice", "observance": "practice",
}

_WEIGHT_ALIASES = {
    "defined": "defined", "define": "defined", "defini": "defined",
    "dogmatic": "defined", "dogmatique": "defined", "settled": "defined",
    "binding": "defined", "obligatoire": "defined",
    "common": "common", "commonly held": "common", "generally held": "common",
    "commun": "common", "communement tenu": "common",
    "disputed": "disputed", "dispute": "disputed", "contested": "disputed",
    "conteste": "disputed", "debated": "disputed",
    "opinion": "opinion", "private opinion": "opinion",
    "subjective": "opinion", "one theologian's opinion": "opinion",
    # The frame's own wording, in its two spellings — `_squeeze` folds the
    # apostrophe away, so "one author's opinion" arrives as "one authors
    # opinion" and must be in the table under that key too.
    "one author's opinion": "opinion", "one authors opinion": "opinion",
    "one author": "opinion", "opinion d'un auteur": "opinion",
    "opinion dun auteur": "opinion", "opinion d un auteur": "opinion",
}

_LABELS = {
    "fr": {
        "section": "Lecture théologique",
        "subject": "Sujet",
        "open": "Ce que la lecture ne tranche pas",
        "authority": {
            "scripture": "Écriture", "tradition": "Tradition",
            "magisterial": "Enseignement magistériel", "scholarship": "Recherche",
            "practice": "Usage et coutume",
        },
        "weight": {
            "defined": "défini", "common": "communément tenu",
            "disputed": "disputé", "opinion": "opinion d'un auteur",
        },
    },
    "en": {
        "section": "Theological reading",
        "subject": "Subject",
        "open": "What the reading does not settle",
        "authority": {
            "scripture": "Scripture", "tradition": "Tradition",
            "magisterial": "Magisterial teaching", "scholarship": "Scholarship",
            "practice": "Practice and custom",
        },
        "weight": {
            "defined": "defined", "common": "commonly held",
            "disputed": "disputed", "opinion": "one author's opinion",
        },
    },
}

MAX_ITEMS = 8
MAX_OPEN = 6
MAX_CLAIM = 400
MAX_REFERENCE = 200
MAX_SUBJECT = 200


def labels(language: str) -> dict:
    return _LABELS["fr"] if str(language or "").lower().startswith("fr") \
        else _LABELS["en"]


def language_of(run) -> str:
    """The language the report was written in — the reading is written in it
    too, so the two can be read side by side."""
    outline = getattr(run, "outline", None) or {}
    lang = str(outline.get("language") or getattr(run, "language", "") or "en")
    return "fr" if lang.lower().startswith("fr") else "en"


def available(run) -> bool:
    """Whether this run is a theological one at all.

    The reading names authorities that only exist in theology, so it is
    composed only for a run governed by the theology discipline — which is
    what the vault trigger always requests, and what the planner selects for a
    doctrinal or historical topic. A run on anything else is announced as it
    always was: a few findings, in the user's language."""
    return "theology-source-critique" in (getattr(run, "skills", None) or [])


def for_run(run) -> dict:
    """The run's checked reading, or `{}` — the shape every caller renders."""
    reading = getattr(run, "reading", None)
    return reading if isinstance(reading, dict) else {}


def carried(run) -> bool:
    """True when the run has a reading worth saying or filing."""
    reading = for_run(run)
    return bool(reading.get("subject") and reading.get("items"))


def _squeeze(value) -> str:
    """Fold, then strip the apostrophes and squeeze the spaces.

    "one author's opinion" and "one author s opinion" and "one authors
    opinion" are one answer to one question; a model that picks the second
    spelling has understood the frame and should not be dropped for it."""
    text = vocab.fold(value).strip()
    text = text.replace("'", "").replace("\u2019", "")
    return " ".join(text.split())


def _canonical(value, options, aliases: dict) -> str:
    """Fold a model's wording onto one of the closed options, or `""`."""
    folded = _squeeze(value)
    if not folded:
        return ""
    squeezed = {_squeeze(k): v for k, v in aliases.items()}
    if folded in squeezed and squeezed[folded] in options:
        return squeezed[folded]
    # "Magisterial teaching (document, date, level)" — the option is the start
    for option in options:
        if folded == option or folded.startswith(option + " "):
            return option
    for alias, option in squeezed.items():
        if option in options and (folded == alias or folded.startswith(alias + " ")):
            return option
    return ""


def _name(lab: dict, kind: str, value) -> str:
    """The label for an authority or a weight — and never a KeyError.

    `validate` is what closes the vocabulary; this is what keeps a reading
    that was built by hand, or loaded from a run written before it, from
    crashing the announcement. An unrecognised value is said as it came."""
    return lab[kind].get(value, str(value or ""))


def _numbers(value, known: set[int]) -> list[int]:
    """Only source numbers the run actually fetched, in order, without repeats."""
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        value = [value]
    out: list[int] = []
    for item in value if isinstance(value, (list, tuple)) else []:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n in known and n not in out:
            out.append(n)
    return out


def validate(raw, run) -> dict | None:
    """Whatever the model returned, turned into a reading — or nothing.

    Nothing is repaired and nothing is invented: an item missing an authority,
    a weight, a reference or a real source number is dropped, and if no item
    survives, there is no reading. The run still has its report; what it loses
    is the claim to have been read theologically."""
    if not isinstance(raw, dict):
        return None
    subject = " ".join(str(raw.get("subject") or "").split())
    if not subject:
        return None
    known = {int(s.get("n", 0)) for s in (getattr(run, "sources", None) or [])}
    items = []
    for entry in raw.get("items") or []:
        if not isinstance(entry, dict):
            continue
        claim = " ".join(str(entry.get("claim") or "").split())
        authority = _canonical(entry.get("authority"), AUTHORITIES, _AUTHORITY_ALIASES)
        weight = _canonical(entry.get("weight"), WEIGHTS, _WEIGHT_ALIASES)
        reference = " ".join(str(entry.get("reference") or "").split())
        cited = _numbers(entry.get("sources"), known)
        if not (claim and authority and reference and weight and cited):
            continue
        items.append({"claim": claim[:MAX_CLAIM], "authority": authority,
                      "reference": reference[:MAX_REFERENCE], "weight": weight,
                      "sources": cited})
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        return None
    open_items = [" ".join(str(x).split())[:MAX_CLAIM]
                  for x in raw.get("open") or [] if str(x).strip()]
    return {"subject": subject[:MAX_SUBJECT], "items": items,
            "open": open_items[:MAX_OPEN]}


# ── the composition ─────────────────────────────────────────────────────────

def prompt(run) -> str:
    """What the theologian is given: the outline the run already produced.

    The notes are deliberately NOT handed over — the outline is the reconciled,
    critiqued version of them, and a reading composed from raw notes would
    carry a claim the critic had already corrected."""
    outline = getattr(run, "outline", None) or {}

    sections = []
    for sec in outline.get("sections") or []:
        claims = "\n".join(f"- {c}" for c in (sec.get("claims") or []))
        sections.append(f"### {sec.get('heading') or 'Section'}\n{claims}")

    contradictions = []
    for c in outline.get("contradictions") or []:
        nums = "".join(f"[{int(n)}]" for n in (c.get("sources") or [])
                       if isinstance(n, int))
        left = " / ".join(x for x in (str(c.get("claim_a") or "").strip(),
                                      str(c.get("claim_b") or "").strip()) if x)
        note = str(c.get("note") or "").strip()
        contradictions.append(f"- {left} {nums} — {note}".rstrip(" —"))

    gaps = "\n".join(f"- {g}" for g in (outline.get("gaps") or []) if str(g).strip())
    sources = "\n".join(
        f"[{s.get('n')}] {s.get('title')} — {s.get('url') or '(no citable page)'}"
        for s in (getattr(run, "sources", None) or []))

    return f"""TOPIC: {getattr(run, 'topic', '')}
REPORT TITLE: {outline.get('title') or getattr(run, 'title', '')}
THESIS: {outline.get('thesis') or '(none)'}
LANGUAGE: {language_of(run)}

OUTLINE (the run's own reconciled findings)
{chr(10).join(sections) or '(none)'}

CONTRADICTIONS LEFT STANDING
{chr(10).join(contradictions) or '(none)'}

OPEN QUESTIONS
{gaps or '(none)'}

SOURCES (the only numbers you may cite)
{sources or '(none)'}"""


# ── the two renderings ──────────────────────────────────────────────────────

def render_markdown(reading, language: str = "en") -> str:
    """The reading as a section — the synthesis page the vault is given."""
    if not reading:
        return ""
    lab = labels(language)
    lines = [f"## {lab['section']}", "",
             f"**{lab['subject']}** — {reading['subject']}", ""]
    for item in reading["items"]:
        cited = "".join(f"[{n}]" for n in (item.get("sources") or []))
        reference = str(item.get("reference") or "").strip()
        lines.append(f"- {item.get('claim', '')} — "
                     f"*{_name(lab, 'authority', item.get('authority'))}*"
                     + (f" ({reference})" if reference else "")
                     + f" — *{_name(lab, 'weight', item.get('weight'))}*{cited}")
    if reading.get("open"):
        lines += ["", f"### {lab['open']}"]
        lines += [f"- {x}" for x in reading["open"]]
    return "\n".join(lines)


def render_speech(reading, language: str = "en") -> str:
    """The reading as it is handed to the voice, ready to be said.

    No Markdown, no citation numbers: the model relays this to the user in
    their own language, and a `[3]` read aloud is a stutter, not a source.
    The report — where every number is — is named separately."""
    if not reading:
        return ""
    lab = labels(language)
    lines = [f"{lab['subject']} : {reading['subject']}."]
    for item in reading["items"]:
        claim = str(item.get("claim") or "").strip()
        reference = str(item.get("reference") or "").strip()
        line = (f"{claim} — {_name(lab, 'authority', item.get('authority'))}"
                + (f" ({reference})" if reference else "")
                + f", {_name(lab, 'weight', item.get('weight'))}.")
        lines.append(line)
    if reading.get("open"):
        lines.append(f"{lab['open']} : " + " ".join(reading["open"]))
    return "\n".join(lines)
