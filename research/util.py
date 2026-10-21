"""Small shared helpers — slugs, timestamps, text trimming, atomic writes."""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(text: str, max_len: int = 48) -> str:
    """A filename that survives every OS and every topic.

    Accents are folded rather than dropped, so a French topic keeps its words:
    "Théologie comparée" becomes "theologie-comparee"."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].strip("-") or "research")


def clip(text: str, limit: int, marker: str = " …") -> str:
    """Trim to `limit` characters at a paragraph, sentence or word boundary.

    A model reading a page that stops mid-word will quote the fragment, so the
    cut lands on the last full sentence whenever there is one."""
    text = str(text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    head = text[:limit]
    for sep in ("\n\n", ". ", "! ", "? ", "; ", " "):
        cut = head.rfind(sep)
        if cut >= limit * 0.55:
            return head[:cut + len(sep)].rstrip() + marker
    return head.rstrip() + marker


def atomic_write(path: Path, text: str) -> None:
    """Write through a temporary file in the same folder, then replace.

    A run is saved at every stage; a power cut mid-save must leave the previous
    state readable rather than a half-written JSON file that resume cannot
    parse."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-",
                               suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: Path, data) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default
