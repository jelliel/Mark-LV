"""
Multi-provider LLM abstraction.

LLMProvider   — generate(messages, model, temperature) -> str
                stream(messages, model, temperature)   -> iterator[str]
MistralProvider — stdlib urllib caller for
                  https://api.mistral.ai/v1/chat/completions (no SDK, no new
                  dependency).

The Gemini ladder stays in core/gemini.py; this module is for providers that are
not Gemini. The Mistral key is read from config/api_keys.json under
"mistral_api_key".
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

_BASE = Path(__file__).resolve().parent.parent
_KEY_FILE = _BASE / "config" / "api_keys.json"

_MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
_REQUEST_TIMEOUT_S = 60


class LLMProvider:
    """A chat-completion provider."""

    def generate(self, messages: list[dict], model: str = "mistral-small-latest",
                 temperature: float = 0.7) -> str:
        """One non-streaming completion. Returns the assistant's text."""
        raise NotImplementedError

    def stream(self, messages: list[dict], model: str = "mistral-small-latest",
               temperature: float = 0.7) -> Iterator[str]:
        """Yield text chunks as they arrive. Default yields the whole reply."""
        raise NotImplementedError


def _api_key() -> str:
    """The Mistral key from config/api_keys.json. Never raises."""
    try:
        data = json.loads(_KEY_FILE.read_text(encoding="utf-8"))
        return str(data.get("mistral_api_key") or "")
    except Exception:
        return ""


class MistralProvider(LLMProvider):
    """Mistral chat-completions over stdlib urllib."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or _api_key()

    def generate(self, messages: list[dict], model: str = "mistral-small-latest",
                 temperature: float = 0.7) -> str:
        if not self.api_key:
            raise RuntimeError(
                "no Mistral API key is configured in config/api_keys.json "
                '(add "mistral_api_key")'
            )
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        return self._post(body, stream=False)

    def stream(self, messages: list[dict], model: str = "mistral-small-latest",
               temperature: float = 0.7) -> Iterator[str]:
        if not self.api_key:
            raise RuntimeError(
                "no Mistral API key is configured in config/api_keys.json "
                '(add "mistral_api_key")'
            )
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        yield from self._post(body, stream=True)

    # ── network ──────────────────────────────────────────────────────────

    def _post(self, body: dict, stream: bool):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            _MISTRAL_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_S)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Mistral API {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Mistral API unreachable: {e}") from e

        with resp:
            raw = resp.read().decode("utf-8")

        if stream:
            yield from self._sse(raw)
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Mistral API returned non-JSON: {raw[:300]}"
            ) from None

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"Mistral API returned no choices: {raw[:300]}")
        message = (choices[0] or {}).get("message") or {}
        return message.get("content", "") or ""

    @staticmethod
    def _sse(raw: str) -> Iterator[str]:
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                return
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            delta = (obj.get("choices") or [{}])[0].get("delta", {})
            chunk = delta.get("content")
            if chunk:
                yield chunk


def demo() -> None:
    """Self-check: shape of the abstraction, no network unless a key exists."""
    p = MistralProvider()
    assert isinstance(p, LLMProvider)
    if not p.api_key:
        print("core.llm: OK (no Mistral key configured — network skipped)")
        return
    out = p.generate([{"role": "user", "content": "reply with exactly: ok"}],
                     temperature=0.0)
    assert out.strip().lower() == "ok", repr(out)
    print("core.llm: OK — Mistral responded:", out)


if __name__ == "__main__":
    demo()
