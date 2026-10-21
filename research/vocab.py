"""
One tokenizer for the theology vault — the words a question and a page share.

The vault is searched in two places (`theology_brain` for the model,
`research/theology.py` for the gap trigger) and the two used to disagree: one
folded accents and dropped stopwords, the other did neither, and neither knew
that "Nicée" and "Nicaea" are the same council. A search that found a page and
a coverage check that called it a gap is how the assistant ends up buying a
report it already owns.

This module is the single place where a word becomes a term:

    fold()        "Chalcédoine" -> "chalcedoine"
    tokens()      "peux-tu m'expliquer" -> peux, tu, m, expliquer
    canonical()   "nicee" -> "nicaea", "conciles" -> "council"
    subject_terms()  the words a question is actually ABOUT

Three ideas do the work:

**THE ASK IS NOT THE SUBJECT.**  "peux-tu m'expliquer le concile de Chalcédoine"
carries four words and only two of them are about anything. The framing verbs
(explique, raconte, penses…) and the grammar words are removed before the
question is measured, because a question that mentions a word the vault does
not have is not a gap in the vault — it is a gap in the phrasing.

**A WORD CAN HAVE TWO NAMES.**  The vault is bilingual by nature: the user
writes in French, the sources are often in Latin, English or Greek. The alias
table folds the equivalents together so a page titled "Council of Nicaea"
answers "concile de Nicée" — and, just as importantly, so the *same* rule
applies to the page and to the question.

**A SUBJECT IS A PROPER NOUN WHEN THERE IS ONE.**  The name of a council, a
council father or a doctrine is capitalised mid-sentence; the modifiers around
it are not. "le concile de Chalcédoine et ses conséquences" is about
Chalcédoine, and "conséquences" must not decide whether the vault is
sufficient.

Nothing here touches the filesystem or the network: pure text in, pure text
out, so both callers can use it without a dependency on the app.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Letters only: apostrophes and hyphens split, so "l'Église" gives
# "l" and "eglise", "peux-tu" gives "peux" and "tu".
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_FOLDED_RE = re.compile(r"[0-9a-z]+")

# ── grammar words ────────────────────────────────────────────────────────────
# Words that carry no subject. Removed before a question is measured, so
# "what is the council of Nicaea" and "concile de Nicée" score the same.
STOPWORDS = {
    # French
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "ou", "en",
    "dans", "sur", "pour", "par", "avec", "sans", "que", "qui", "quoi", "quel",
    "quelle", "quels", "quelles", "qu", "est", "sont", "etait", "ete", "a", "au",
    "aux", "ce", "cet", "cette", "ces", "il", "elle", "on", "nous", "vous",
    "ils", "elles", "son", "sa", "ses", "leur", "leurs", "plus", "moins",
    "chez", "entre", "vers", "selon", "apres", "avant", "lors", "tout",
    "tous", "toute", "toutes", "meme", "aussi", "ainsi", "donc", "car",
    "comment", "pourquoi", "quand", "ne", "pas", "ni", "non", "oui", "peu",
    "beaucoup", "tres", "bien", "tout", "tous", "autre", "autres", "meme",
    "si", "sinon", "car", "donc", "or", "ni", "entre", "contre", "vers",
    "depuis", "jusqu", "malgre", "afin", "comme", "tel", "telle", "ceci",
    "cela", "celui", "celle", "ceux", "celles", "n", "s", "l", "j", "t", "y",
    # English
    "the", "an", "of", "and", "or", "in", "on", "for", "with", "without",
    "what", "which", "who", "whom", "how", "why", "is", "are", "was", "were",
    "be", "been", "to", "from", "by", "about", "does", "do", "did", "can",
    "could", "should", "would", "this", "that", "these", "those", "its",
    "their", "there", "here", "than", "then", "into", "not", "but", "have",
    "has", "had", "you", "your", "our", "we", "they", "them", "he", "she",
    "his", "her", "its", "at", "as", "so", "if", "any", "all", "also", "more",
    "most", "such", "very", "just", "only", "own", "same", "too", "s", "t",
}

# ── the framing of a request ────────────────────────────────────────────────
# The words that make it a REQUEST rather than a subject. "peux-tu m'expliquer
# le concile de Chalcédoine" is about one thing; these are the words that say
# it politely. They are dropped from the question, never from the page — a page
# that happens to use them is still a page.
FRAMING = {
    # French — the verb of the ask
    "explique", "expliques", "expliquez", "expliquer", "expliquons",
    "raconte", "racontes", "racontez", "raconter", "racontemoi",
    "pense", "penses", "pensez", "penser", "penserais", "pensees",
    "dis", "dites", "dire", "dismoi", "donne", "donnes", "donner", "donnemoi",
    "montre", "montres", "montrer", "montremoi",
    "resume", "resumes", "resumer", "resumemoi",
    "analyse", "analyses", "analyser", "commente", "commenter",
    "compare", "compares", "comparer", "comparee",
    "detaille", "detaille", "detailler", "developpe", "developper",
    "presente", "presentes", "presenter", "presente",
    "parle", "parles", "parler", "parlemoi", "discute", "discuter",
    "resume", "synthetise", "synthetiser", "reformule", "reformuler",
    "tudique", "tudiques", "etudie", "etudier", "cherche", "chercher",
    "traduis", "traduire", "traduction",
    # French — the courtesy around it
    "moi", "toi", "nous", "vous", "ton", "ta", "tes", "notre", "nos",
    "votre", "vos", "leur", "leurs", "sil", "plait", "silteplait", "stp",
    "merci", "salut", "bonjour", "bonsoir", "madame", "monsieur", "sirs",
    "sers", "peux", "peut", "peux-tu", "voudrais", "voudrais-tu", "jailmerais",
    "jaimerais", "repose",
    # English — the same moves
    "explain", "explains", "explaining", "tell", "tells", "telling",
    "describe", "describes", "describing", "summarize", "summarise",
    "summarizes", "summarizing", "analyze", "analyse", "analyzes",
    "analysing", "analyzing", "compare", "compares", "comparing", "give",
    "gives", "giving", "show", "shows", "showing", "think", "thinks",
    "thinking", "say", "says", "saying", "talk", "talks", "please", "thanks",
    "thank", "hello", "hi", "hey", "could", "would", "should", "can", "want",
    "need", "like", "maybe", "perhaps", "let", "lets", "tell", "remind",
    "regarding", "relating", "concerning", "talking", "going", "wanna",
    "gonna", "know", "wonder", "wondering", "curious", "remind",
}

# ── one word, two names ─────────────────────────────────────────────────────
# The vault is bilingual by nature: the question is French, the source may be
# Latin, English or Greek, the page title may be in any of them. These are the
# pairs that must count as the same word on BOTH sides of the comparison.
# Keys are already folded (accents removed, lower case).
ALIASES = {
    # councils
    "nicee": "nicaea", "nicaea": "nicaea", "nikee": "nicaea", "nicea": "nicaea",
    "chalcedoine": "chalcedon", "chalcedon": "chalcedon",
    "chalcedonia": "chalcedon", "calcedoine": "chalcedon",
    "ephese": "ephesus", "ephesus": "ephesus",
    "constantinople": "constantinople", "nicee2": "nicaea",
    # the fathers
    "augustin": "augustine", "augustine": "augustine",
    "jerome": "jerome", "ambroise": "ambrose", "ambrose": "ambrose",
    "gregoire": "gregory", "gregory": "gregory", "basile": "basil",
    "basil": "basil", "maxime": "maximus", "maxime2": "maximus",
    "leon": "leo", "leon1": "leo", "athanase": "athanasius",
    "athanasius": "athanasius", "cyran": "cyrian", "cyrian": "cyrian",
    "anselme": "anselm", "anselm": "anselm", "hilarin": "hilarion",
    "irenee": "irenaeus", "irenaeus": "irenaeus", "origin": "origen",
    "origene": "origen", "origene2": "origen", "palamas": "palamas",
    "scholastique": "scholastic", "scholastic": "scholastic",
    # institutions and creeds
    "concile": "council", "council": "council", "conciles": "council",
    "eglise": "church", "church": "church", "ecclesia": "church",
    "catholique": "catholic", "catholic": "catholic",
    "catholicisme": "catholicism", "catholicism": "catholicism",
    "orthodoxe": "orthodox", "orthodox": "orthodox",
    "orthodoxie": "orthodoxy", "orthodoxy": "orthodoxy",
    "protestant": "protestant", "protestantisme": "protestantism",
    "protestantism": "protestantism", "christianisme": "christianity",
    "christianity": "christianity", "christian": "christian",
    "theologie": "theology", "theology": "theology",
    "dogme": "dogma", "dogma": "dogma", "doctrine": "doctrine",
    "credo": "creed", "creed": "creed", "symbole": "creed",
    "catECHisme": "catechism", "catechisme": "catechism", "catechism": "catechism",
    "pape": "pope", "pope": "pope", "eveque": "bishop", "bishop": "bishop",
    "cardinal": "cardinal", "archeveque": "archbishop",
    "archbishop": "archbishop", "synode": "synod", "synod": "synod",
    "decret": "decree", "decree": "decree", "canon": "canon",
    "canonique": "canonical", "canonical": "canonical",
    # the Christian deposit
    "trinite": "trinity", "trinity": "trinity", "trinitaire": "trinitarian",
    "trinitarian": "trinitarian", "christologie": "christology",
    "christology": "christology", "mariologie": "mariology",
    "mariology": "mariology", "soteriologie": "soteriology",
    "soteriology": "soteriology", "pneumatologie": "pneumatology",
    "pneumatology": "pneumatology", "ecumenisme": "ecumenism",
    "ecumenism": "ecumenism", "oecumenique": "ecumenical",
    "oecumenical": "ecumenical", "heresie": "heresy", "heresy": "heresy",
    "eucharistie": "eucharist", "eucharist": "eucharist",
    "bapteme": "baptism", "baptism": "baptism",
    "sacrement": "sacrament", "sacrament": "sacrament", "penitence": "penance",
    "apostolique": "apostolic", "apostolic": "apostolic",
    "pentecote": "pentecost", "pentecost": "pentecost",
    "kerygme": "kerygma", "kerygma": "kerygma", "exegese": "exegesis",
    "exegesis": "exegesis", "hermeneutique": "hermeneutics",
    "hermeneutics": "hermeneutics", "theodicee": "theodicy",
    "theodicy": "theodicy", "mystere": "mystery", "mystery": "mystery",
    "sacre": "sacred", "sacred": "sacred", "liturgie": "liturgy",
    "liturgy": "liturgy", "legende": "legend", "legend": "legend",
    "salut": "salvation", "salvation": "salvation", "grace": "grace",
    "homoousios": "homoousios", "homoousie": "homoousios",
    "ousia": "ousia", "hypostase": "hypostasis", "incarnation": "incarnation",
    "redemption": "redemption", "immaculee": "immaculate", "immaculate": "immaculate",
    "assumption": "assumption", "paradis": "paradise", "paradise": "paradise",
    "juge": "judgment", "jugement": "judgment", "judgment": "judgment",
    "revelation": "revelation", "apocalypse": "apocalypse",
    "eschatologie": "eschatology", "eschatology": "eschatology",
    "angelologie": "angelology", "angelology": "angelology",
    "demonologie": "demonology", "demonology": "demonology",
    "christ": "christ", "jesus": "jesus", "marie": "mary", "mary": "mary",
    "paul": "paul", "pierre": "peter", "peter": "peter", "jean": "john",
    "john": "john", "luc": "luke", "luke": "luke", "marc": "mark", "mark": "mark",
    "matthieu": "matthew", "matthew": "matthew", "moise": "moses",
    "moses": "moses", "adam": "adam", "eve": "eve", "noe": "noah",
    "noah": "noah", "abraham": "abraham", "david": "david", "salomon": "solomon",
    "solomon": "solomon", "isaie": "isaiah", "isaiah": "isaiah",
    "jeremie": "jeremiah", "jeremiah": "jeremiah", "ezechiel": "ezekiel",
    "daniel": "daniel", "osias": "hosea", "amos": "amos", "job": "job",
    "salme": "psalm", "psaumes": "psalm", "psalm": "psalm",
    "proverbes": "proverb", "proverb": "proverb", "ecclesiaste": "ecclesiastes",
    "cantique": "canticle", "cantique1": "canticle", "apocalypse1": "apocalypse",
}


# ── the scaffolding of a question ───────────────────────────────────────────
# The nouns that make a question WIDE rather than about something: "the
# history of the council of Chalcédoine" asks about Chalcédoine, and the
# missing word "history" must not make the vault look like a hole. They are
# dropped from the question — like the framing verbs — but unlike the verbs
# they are not part of the request: they are part of the subject, only
# generic.
GENERIC = {
    # French
    "histoire", "histoires", "contexte", "contextes", "enjeu", "enjeux",
    "consequence", "consequences", "portee", "origine", "origines",
    "deroulement", "epoque", "epoques", "difference", "differences",
    "lien", "liens", "rapport", "rapports", "temoignage", "temoignages",
    "experience", "avenir", "passe", "present", "situation", "situations",
    "problematique", "question", "questions", "reponse", "reponses",
    "fondamentaux", "notion", "notions", "concept", "concepts", "idee",
    "idees", "interet", "interets", "limite", "limites", "definition",
    "definitions", "explication", "explications", "presentation",
    "introduction", "conclusion", "partie", "parties", "chapitre", "chapitres",
    "volume", "volumes", "ouvrage", "ouvrages", "livre", "livres", "auteur",
    "auteurs", "ecrivain", "traducteur", "edition", "editions", "texte",
    "textes", "source", "sources", "reference", "references", "biblio",
    "bibliographie", "analyse", "analyses", "etude", "etudes", "recherche",
    "recherches", "travail", "travaux", "article", "articles", "revue",
    "journal", "colloque", "conference", "these", "plan", "sommaire",
    "precision", "precisions", "apercu", "tour", "horizon", "moment",
    "moments", "periode", "periodes", "siecle", "siecles", "temps", "annee",
    "annees", "jour", "jours", "arriere-plan", "fond", "cadre", "perspective",
    "perspectives", "approche", "approches", "methode", "methodes",
    "structure", "element", "elements", "impact", "role", "portee2",
    # English
    "history", "histories", "context", "contexts", "issue", "issues",
    "consequence", "consequences", "significance", "origin", "origins",
    "period", "periods", "difference", "differences", "link", "links",
    "relationship", "relationships", "testimony", "experience", "future",
    "past", "situation", "question", "questions", "answer", "answers",
    "fundamental", "fundamentals", "notion", "notions", "concept", "concepts",
    "idea", "ideas", "interest", "interests", "limit", "limits", "definition",
    "definitions", "explanation", "explanations", "introduction",
    "conclusion", "part", "chapter", "volume", "work", "works", "book",
    "books", "author", "authors", "writer", "edition", "editions", "text",
    "texts", "source", "sources", "reference", "references", "bibliography",
    "analysis", "analyses", "study", "studies", "research", "article",
    "articles", "journal", "conference", "paper", "summary", "overview",
    "era", "century", "year", "years", "day", "background", "role", "impact",
    "perspective", "perspectives", "aspect", "aspects", "framework",
    "approach", "approaches", "method", "methods", "structure", "element",
    "elements", "significance2", "tour2", "plan2",
}


def fold(text) -> str:
    """Lower-case, accent-folded: "Nicée" and "nicee" are the same word."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def tokens(text) -> list[str]:
    """The folded words of a text, in order."""
    return _FOLDED_RE.findall(fold(text))


def singular(word: str) -> str:
    """The singular of an English/French noun, conservatively.

    Only a trailing "s" is removed, and never from a word ending in "ss",
    "us" or "is" — so "conciles" gives "concile", "natures" gives "nature",
    and "cross", "jesus" and "locus" keep their shape."""
    w = str(word or "")
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def canonical(word: str) -> str:
    """The form two words must share to be considered the same word.

    Singular first, then the alias table: "Nicee" and "Nicaea" and "Nicees"
    all end up on the same key, on the page side and on the question side."""
    w = singular(str(word or ""))
    return ALIASES.get(w, ALIASES.get(str(word or ""), w))


def is_framing(word: str) -> bool:
    return str(word or "") in FRAMING or str(word or "") in STOPWORDS


def is_generic(word: str) -> bool:
    """A word that widens a question instead of naming its subject."""
    return str(word or "") in GENERIC


def subject_terms(query, limit: int = 8) -> list[str]:
    """The words a question is actually about, canonical and deduplicated.

    Grammar words, the framing of the request and the generic scaffolding are
    removed; what is left is the subject, in the form both sides of a
    comparison must use."""
    out: list[str] = []
    for word in tokens(query):
        if len(word) < 3 or word in STOPWORDS or word in FRAMING or word in GENERIC:
            continue
        canon = canonical(word)
        if len(canon) < 3 or canon in out:
            continue
        out.append(canon)
    return out[:limit]


def proper_terms(query) -> set[str]:
    """The subject terms that the question wrote as a proper name.

    A name is capitalised in the middle of the sentence — the first word is
    skipped, because a sentence starts with a capital whatever it is about.
    This is what separates "le concile de Chalcédoine et ses conséquences"
    (about Chalcédoine) from a question about the consequences themselves."""
    found: set[str] = set()
    words = _WORD_RE.findall(str(query or ""))
    for index, word in enumerate(words):
        if index == 0 or len(word) < 3:
            continue
        if not (word[0].isupper() and word[1:].islower()) and not word.isupper():
            continue
        canon = canonical(fold(word))
        if len(canon) >= 3 and canon not in STOPWORDS and canon not in FRAMING:
            found.add(canon)
    return found


def page_tokens(title, body) -> tuple[Counter, set]:
    """The words of a page, canonical, with how many times each occurs.

    The title's words are kept apart: a subject in a title is a page written
    about that subject, a subject mentioned once in a paragraph is a mention."""
    counts: Counter = Counter()
    for word in tokens(title):
        counts[canonical(word)] += 1
    title_words = set(counts)
    for word in tokens(body):
        counts[canonical(word)] += 1
    return counts, title_words


def find_span(text, wanted: set[str]):
    """Where the first wanted word occurs in the ORIGINAL text.

    The offsets are in the original string, so a snippet cut from them is
    still correct French with its accents — the folding never touches the
    text the user reads."""
    if not wanted:
        return None
    for match in re.finditer(r"[^\W\d_]+", str(text or ""), re.UNICODE):
        canon = canonical(fold(match.group(0)))
        if canon in wanted:
            return match.start(), match.end()
    return None
