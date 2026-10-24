"""
Multi-provider LLM abstraction — one door for every model call.

LLMProvider   — generate(messages, model, temperature) -> str
                stream(messages, model, temperature)   -> iterator[str]
GeminiProvider — wraps core/gemini.py's measured ladder (no new client).
MistralProvider — stdlib urllib caller for
                  https://api.mistral.ai/v1/chat/completions (no SDK, no new
                  dependency).

generate() / stream() below route to the provider named in
config/api_keys.json ("llm_provider": "gemini" | "mistral" | "auto"),
defaulting to Gemini when nothing is set. The Gemini ladder in
core/gemini.py stays the default for the app; Mistral is an opt-in rung.

Keys live in config/api_keys.json: "gemini_api_key", "mistral_api_key".
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))
_KEY_FILE = _BASE / "config" / "api_keys.json"

_MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
_REQUEST_TIMEOUT_S = 60


class LLMProvider:
    """A chat-completion provider."""

    def generate(self, messages: list[dict], model: str = "",
                 temperature: float = 0.7) -> str:
        """One non-streaming completion. Returns the assistant's text."""
        raise NotImplementedError

    def stream(self, messages: list[dict], model: str = "",
               temperature: float = 0.7) -> Iterator[str]:
        """Yield text chunks as they arrive. Default yields the whole reply."""
        raise NotImplementedError


def _load_config() -> dict:
    """Read config/api_keys.json. Never raises."""
    try:
        return json.loads(_KEY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def provider_name() -> str:
    """Configured provider: "gemini", "mistral", or "auto" (default gemini)."""
    return str(_load_config().get("llm_provider", "auto")).lower()


def _api_key(provider: str) -> str:
    """The configured key for a provider. Never raises."""
    cfg = _load_config()
    if provider == "mistral":
        return str(cfg.get("mistral_api_key") or "")
    return str(cfg.get("gemini_api_key") or "")


class GeminiProvider(LLMProvider):
    """Wrap core/gemini.py's ladder so it speaks the same interface as Mistral.

    No new client, no new dependency — gemini.text / gemini.as_json already own
    timeouts, cooldowns and the measured model ladder. A bare string message
    list is flattened to a single prompt for the one-shot call.
    """

    def __init__(self, api_key: str | None = None):
        self._key = api_key

    def generate(self, messages: list[dict], model: str = "",
                 temperature: float = 0.7) -> str:
        from core import gemini

        prompt = _messages_to_prompt(messages)
        config = {"system_instruction": messages[0]["content"]} if messages \
            and messages[0].get("role") == "system" else None
        return gemini.text(
            prompt,
            tier=gemini.SMART if model in ("", "smart") else gemini.FAST,
            config=config,
            timeout_ms=60_000,
            key=self._key or gemini.api_key(),
        )

    def stream(self, messages: list[dict], model: str = "",
               temperature: float = 0.7) -> Iterator[str]:
        """Non-streaming — yields the whole reply in one chunk."""
        yield self.generate(messages, model, temperature)


def _messages_to_prompt(messages: list[dict]) -> str:
    """Flatten a chat message list to a single string for one-shot callers."""
    parts = []
    for m in messages:
        role = str(m.get("role", "user")).upper()
        content = str(m.get("content", ""))
        parts.append(f"{role}: {content}")
    return "\n".join(parts).strip()


class MistralProvider(LLMProvider):
    """Mistral chat-completions over stdlib urllib."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or _api_key("mistral")

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


# ── Single entry point ──────────────────────────────────────────────────

_PROVIDERS: dict[str, LLMProvider] = {}
_LAST_USED: str | None = None


def _provider(name: str) -> LLMProvider:
    if name not in _PROVIDERS:
        if name == "mistral":
            _PROVIDERS[name] = MistralProvider()
        else:
            _PROVIDERS[name] = GeminiProvider()
    return _PROVIDERS[name]


def _log(provider: str, ok: bool, detail: str = "") -> None:
    global _LAST_USED
    if ok:
        _LAST_USED = provider
        print(f"[LLM] {provider} answered{(' — ' + detail) if detail else ''}")
    else:
        print(f"[LLM] {provider} failed{(' — ' + detail) if detail else ''}")


def generate(messages: list[dict], model: str = "",
             temperature: float = 0.7, provider: str = "") -> str:
    """One completion through the configured provider.

    `provider` overrides the config ("gemini" | "mistral"). Empty → config,
    empty config → "auto" → gemini with mistral fallback if no Gemini key.

    If the chosen provider errors, the other one is tried automatically —
    never return a hard failure when a backup key can answer.
    """
    name = provider or provider_name()
    if name == "auto":
        if _api_key("gemini"):
            name = "gemini"
        elif _api_key("mistral"):
            name = "mistral"
        else:
            name = "gemini"

    tried = [name]
    backup = "mistral" if name == "gemini" else "gemini"
    if not _api_key(backup):
        backup = None

    last_error = ""
    for candidate in tried + ([backup] if backup else []):
        try:
            out = _provider(candidate).generate(messages, model, temperature)
            _log(candidate, True, f"{len(out)} chars")
            return out
        except Exception as e:
            last_error = str(e)[:200]
            _log(candidate, False, last_error)
    raise RuntimeError(
        "no LLM provider answered"
        + (f" (last error: {last_error})" if last_error else "")
    )


def stream(messages: list[dict], model: str = "",
           temperature: float = 0.7, provider: str = "") -> Iterator[str]:
    name = provider or provider_name()
    if name == "auto":
        if _api_key("gemini"):
            name = "gemini"
        elif _api_key("mistral"):
            name = "mistral"
        else:
            name = "gemini"

    backup = "mistral" if name == "gemini" else "gemini"
    if not _api_key(backup):
        backup = None

    last_error = ""
    for candidate in [name] + ([backup] if backup else []):
        try:
            chunks = list(_provider(candidate).stream(messages, model, temperature))
            _log(candidate, True, f"{len(chunks)} chunks")
            yield from chunks
            return
        except Exception as e:
            last_error = str(e)[:200]
            _log(candidate, False, last_error)
    raise RuntimeError(
        "no LLM provider answered"
        + (f" (last error: {last_error})" if last_error else "")
    )


def last_provider() -> str | None:
    """Name of the provider that answered the most recent call, if any."""
    return _LAST_USED


def check_configured() -> tuple[bool, str]:
    """Startup health check: is at least one LLM key configured?"""
    have_gemini = bool(_api_key("gemini"))
    have_mistral = bool(_api_key("mistral"))
    if have_gemini and have_mistral:
        return True, "gemini + mistral configured"
    if have_gemini:
        return True, "gemini configured (mistral as backup)"
    if have_mistral:
        return True, "mistral configured (gemini as backup)"
    return False, ("no LLM key configured — add gemini_api_key and/or "
                   "mistral_api_key to config/api_keys.json")


def demo() -> None:
    """Self-check: imports cleanly; no network unless a key exists."""
    assert issubclass(GeminiProvider, LLMProvider)
    assert issubclass(MistralProvider, LLMProvider)
    if not _api_key("gemini") and not _api_key("mistral"):
        print("core.llm: OK (no key configured — network skipped)")
        return
    out = generate([{"role": "user", "content": "reply with exactly: ok"}],
                   temperature=0.0)
    print("core.llm: OK — responded:", out)


if __name__ == "__main__":
    demo()
