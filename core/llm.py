"""
Multi-provider LLM abstraction — one door for every model call.

LLMProvider   — generate(messages, model, temperature) -> str
                stream(messages, model, temperature)   -> iterator[str]
GeminiProvider — wraps core/gemini.py's measured ladder (no new client).
MistralProvider — stdlib urllib caller for
                  https://api.mistral.ai/v1/chat/completions (no SDK, no new
                  dependency) with its own measured model ladder and per-model
                  cooldowns.

generate() / stream() below route to the provider named in
config/api_keys.json ("llm_provider": "gemini" | "mistral" | "auto"),
defaulting to Gemini when nothing is set. The Gemini ladder in
core/gemini.py stays the default for the app; Mistral is an opt-in rung.

Keys live in config/api_keys.json: "gemini_api_key", "mistral_api_key".
"""

from __future__ import annotations

import json
import sys
import time
import threading
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


# ── Mistral model ladder, tiered ────────────────────────────────────────────
# Same measured-ladder pattern as core/gemini.py: fastest first, strongest last.
# A rung that errors is cooldowned (300s for quota, 30min for unavailable) and
# skipped on the next attempt. Two tiers match gemini.FAST / gemini.SMART so
# the caller picks the right strength for the job.
#
# Free-tier models only (no paywall surprises):
#   fast — short classification, extraction, one-line decisions
#   smart — reasoning, generation, long documents
#
# Cooldown maps to real Mistral behavior: 429 = quota exhausted, 503 = overloaded.

_FAST_MODELS = (
    "mistral-nemo",           # best free-tier speed/power balance (2024)
    "mistral-small-latest",   # small, fast, reliable
    "mistral-embed",          # embedding-only; kept as last-resort placeholder
)
_SMART_MODELS = (
    "mistral-large-latest",   # strongest free-tier (2024)
    "mistral-nemo",           # high-performing middle ground
    "mistral-small-latest",   # fallback when the big one is busy
)


def _tier(tier: str) -> tuple[str, ...]:
    """Return the model ladder for a tier string."""
    t = str(tier).lower()
    if t == "fast":
        return _FAST_MODELS
    return _SMART_MODELS


# ── Cooldown tracking for failed Mistral models ─────────────────────────────
_cooldown: dict[str, float] = {}
_cooldown_lock = threading.Lock()
_COOLDOWN_QUOTA_S = 300
_COOLDOWN_BUSY_S = 1800
_GONE_S = 6 * 3600


def _is_quota_error(err: str) -> bool:
    low = err.lower()
    return "429" in err or "resource_exhausted" in low or "rate_limit" in low


def _is_busy_error(err: str) -> bool:
    low = err.lower()
    return ("503" in err or "unavailable" in low
            or "overloaded" in low or "deadline_exceeded" in low)


def _is_gone_error(err: str) -> bool:
    low = err.lower()
    return "404" in err or "not found" in low or "does not exist" in low


def _cool(model: str, seconds: float) -> None:
    with _cooldown_lock:
        _cooldown[model] = time.monotonic() + seconds


def _cooling(model: str) -> bool:
    with _cooldown_lock:
        until = _cooldown.get(model)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(model, None)
        return False


def _record_mistral_failure(model: str, err: Exception) -> None:
    msg = str(err)
    if _is_quota_error(msg):
        _cool(model, _COOLDOWN_QUOTA_S)
        print(f"[Mistral] {model}: out of quota — cooling {_COOLDOWN_QUOTA_S // 60}min")
    elif _is_gone_error(msg):
        _cool(model, _GONE_S)
        print(f"[Mistral] {model}: unavailable — set aside")
    elif _is_busy_error(msg):
        _cool(model, _COOLDOWN_BUSY_S)
        print(f"[Mistral] {model}: busy — cooling {_COOLDOWN_BUSY_S // 60}min")


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
    """Mistral chat-completions over stdlib urllib with auto-ladder fallback."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or _api_key("mistral")

    def generate(self, messages: list[dict], model: str = "",
                 temperature: float = 0.7, tier: str = "") -> str:
        if not self.api_key:
            raise RuntimeError(
                "no Mistral API key is configured in config/api_keys.json "
                '(add "mistral_api_key")'
            )
        # Resolve model ladder based on tier parameter
        if model:
            models_to_try = [model]
        else:
            t = str(tier).lower() if tier else "smart"
            models_to_try = [m for m in _tier(t) if not _cooling(m)]
            if not models_to_try:
                models_to_try = list(_tier(t))  # force try all if all cooling

        last_error = ""
        for try_model in models_to_try:
            body = {
                "model": try_model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            }
            try:
                result = self._post(body, stream=False)
                _log(f"mistral:{try_model}", True)
                return result
            except Exception as e:
                last_error = str(e)[:200]
                _record_mistral_failure(try_model, e)
                _log(f"mistral:{try_model}", False, last_error[:60])
        raise RuntimeError(f"Mistral all models failed: {last_error}")

    def stream(self, messages: list[dict], model: str = "",
               temperature: float = 0.7, tier: str = "") -> Iterator[str]:
        if not self.api_key:
            raise RuntimeError(
                "no Mistral API key is configured in config/api_keys.json "
                '(add "mistral_api_key")'
            )
        if model:
            models_to_try = [model]
        else:
            t = str(tier).lower() if tier else "smart"
            models_to_try = [m for m in _tier(t) if not _cooling(m)]
            if not models_to_try:
                models_to_try = list(_tier(t))

        last_error = ""
        for try_model in models_to_try:
            body = {
                "model": try_model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
            try:
                chunks = list(self._post(body, stream=True))
                _log(f"mistral:{try_model}", True, f"{len(chunks)} chunks")
                yield from chunks
                return
            except Exception as e:
                last_error = str(e)[:200]
                _record_mistral_failure(try_model, e)
                _log(f"mistral:{try_model}", False, last_error[:60])
        raise RuntimeError(f"Mistral all models failed: {last_error}")

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
