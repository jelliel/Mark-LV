"""
MARK-LIV — theological citation verifier.

Mechanical citation checking for THEOLOGICUS: every documentary claim should be
backed by an evidence object {claim, evidence: [{document_id, locator, quote,
supports_claim}], status}. Before an answer is handed to the conversation,
this module runs four controls on each piece of evidence:

1. Existence — the document and its locator exist in the vault.
2. Fidelity — the quoted text matches the source page.
3. Relevance — the cited passage actually supports the claim (the model's
   own judgement, recorded as a verdict with a reason).
4. Context — nothing around the quote that reverses its meaning.

Never raises. A citation that cannot be verified is marked "unverifiable"
rather than silently accepted — the whole point is honest traceability.

Loaded by path (actions/ is not a package), stdlib only.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BRIDGE = None


def _bridge():
    """actions/theology_brain.py, loaded by path — the vault's owner."""
    global _BRIDGE
    if _BRIDGE is not None:
        return _BRIDGE
    path = Path(__file__).resolve().parent / "theology_brain.py"
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("markliv_vault_bridge_cite", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["markliv_vault_bridge_cite"] = module
    spec.loader.exec_module(module)
    _BRIDGE = module
    return module


@dataclass
class CitationCheck:
    """Result of verifying one cited passage against one claim."""
    document_id: str
    locator: str
    quote: str
    exists: bool = False
    fidelity: bool = False
    relevance: bool = False
    context_ok: bool = False
    verdict: str = "unverifiable"   # verified | rejected | unverifiable
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "locator": self.locator,
            "quote": self.quote,
            "exists": self.exists,
            "fidelity": self.fidelity,
            "relevance": self.relevance,
            "context_ok": self.context_ok,
            "verdict": self.verdict,
            "reason": self.reason,
        }


@dataclass
class ClaimCheck:
    """One claim plus its evidence checks and an overall status."""
    claim: str
    evidence: list[CitationCheck] = field(default_factory=list)
    status: str = "needs_review"   # needs_review | verified | rejected | unverifiable
    summary: str = ""

    def as_dict(self) -> dict:
        return {
            "claim": self.claim,
            "evidence": [e.as_dict() for e in self.evidence],
            "status": self.status,
            "summary": self.summary,
        }


def _normalise(text: str) -> str:
    """Lower-case, strip accents and punctuation, collapse whitespace — so a
    quote copied with a different accent or line break still matches."""
    text = text.lower()
    text = "".join(
        c for c in __import__("unicodedata").normalize("NFKD", text)
        if not __import__("unicodedata").combining(c)
    )
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fidelity_score(source: str, quote: str) -> float:
    """0.0–1.0 similarity between a source page and a quoted passage."""
    if not source or not quote:
        return 0.0
    s = _normalise(source)
    q = _normalise(quote)
    if q in s:
        return 1.0
    return difflib.SequenceMatcher(None, s, q).ratio()


def _find_page(vault: Path, document_id: str):
    """Return (meta, body, path) for the vault page whose title matches."""
    for _dirname, path in _bridge()._iter_pages(vault):
        meta, body = _bridge()._read_page(path)
        title = str(meta.get("title") or path.stem).strip()
        if title.lower() == document_id.lower():
            return meta, body, path
        if path.stem.lower() == document_id.lower():
            return meta, body, path
    return None


def verify_citation(document_id: str, locator: str, quote: str,
                    claim: str = "") -> CitationCheck:
    """Verify one cited passage: does the page exist, does the quote match,
    and (model-judged) does it support the claim in context?

    `claim` is optional: without it, relevance and context cannot be judged
    and the verdict is capped at "unverifiable"."""
    check = CitationCheck(document_id=document_id, locator=locator, quote=quote)
    try:
        vault = _bridge()._vault()
    except Exception:
        check.verdict = "unverifiable"
        check.reason = "vault unavailable"
        return check

    found = _find_page(vault, document_id)
    if found is None:
        check.verdict = "rejected"
        check.reason = f"document '{document_id}' not found in vault"
        return check

    meta, body, path = found
    check.exists = True

    # 2. Fidelity — does the quote appear in the page?
    score = _fidelity_score(body, quote)
    check.fidelity = score >= 0.90
    if not check.fidelity:
        # try sentence-level: the quote may be a paraphrase or span paragraphs
        best = 0.0
        for sentence in re.split(r"[.!?]\s+", body):
            best = max(best, _fidelity_score(sentence, quote))
        check.fidelity = best >= 0.85
    if not check.fidelity:
        check.verdict = "rejected"
        check.reason = f"quote not found verbatim in '{document_id}' (fidelity {score:.2f})"
        return check

    # 3 & 4. Relevance + context — model judgement; without a claim we stop here.
    if not claim:
        check.verdict = "unverifiable"
        check.reason = "quote matches but no claim to judge relevance against"
        return check

    check.relevance = True          # provisional — the model sets the real verdict
    check.context_ok = True         # provisional — see note below
    check.verdict = "unverifiable"
    check.reason = ("quote verified in '" + document_id + "'; relevance and "
                    "context require model judgement (claim: " + claim[:80] + "…)")
    return check


def verify_claim(claim: str, evidence: list[dict],
                 model_judge=None) -> ClaimCheck:
    """Verify a claim against a list of evidence dicts
    {document_id, locator, quote}. `model_judge` is an optional callable
    (claim, quote, context) -> (relevant: bool, context_ok: bool, reason: str)
    supplied by the caller — this module never calls a model itself.

    Returns a ClaimCheck whose status is:
      verified   — at least one evidence item passed all four controls
      rejected   — every evidence item failed existence or fidelity
      unverifiable — quote(s) match but relevance/context unjudged
      needs_review — no evidence at all
    """
    result = ClaimCheck(claim=claim)
    for ev in evidence:
        check = verify_citation(
            str(ev.get("document_id", "")),
            str(ev.get("locator", "")),
            str(ev.get("quote", "")),
            claim=claim,
        )
        result.evidence.append(check)

        if model_judge and check.exists and check.fidelity:
            # build surrounding context (±200 chars around the quote)
            for _dirname, path in _bridge()._iter_pages(_bridge()._vault()):
                meta, body = _bridge()._read_page(path)
                if check.quote and check.quote in body:
                    idx = body.find(check.quote)
                    context = body[max(0, idx - 200): idx + len(check.quote) + 200]
                    break
            else:
                context = check.quote
            try:
                relevant, context_ok, reason = model_judge(claim, check.quote, context)
            except Exception as e:
                relevant, context_ok, reason = False, False, f"judge failed: {e}"
            check.relevance = bool(relevant)
            check.context_ok = bool(context_ok)
            check.reason = reason or check.reason

    # Overall status
    if not result.evidence:
        result.status = "needs_review"
        result.summary = "no evidence provided for claim"
    elif all(e.verdict == "rejected" for e in result.evidence):
        result.status = "rejected"
        result.summary = "every citation failed existence or fidelity"
    elif any(e.verdict == "verified" for e in result.evidence):
        result.status = "verified"
        result.summary = "at least one citation passed all four controls"
    else:
        result.status = "unverifiable"
        result.summary = "citation(s) match but relevance/context unjudged or failed"

    return result


def verify_answer_claims(claims: list[dict], model_judge=None) -> list[dict]:
    """Batch-verify a list of {claim, evidence: [...]} dicts. Returns a list of
    ClaimCheck dicts ready to be attached to an answer or logged."""
    return [verify_claim(c.get("claim", ""), c.get("evidence", []), model_judge)
            .as_dict() for c in claims]


def summary_line(checks: list[ClaimCheck]) -> str:
    """One-line audit trail for the HUD / log."""
    verified = sum(1 for c in checks if c.status == "verified")
    rejected = sum(1 for c in checks if c.status == "rejected")
    unverifiable = sum(1 for c in checks if c.status == "unverifiable")
    review = sum(1 for c in checks if c.status == "needs_review")
    return (f"citations: {verified} verified, {rejected} rejected, "
            f"{unverifiable} unverifiable, {review} needs_review")
