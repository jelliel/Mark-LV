"""
Gemini calls that do not trip the automatic-function-calling deprecation.

`client.chats.create(model=…).send_message(…)` is the route the SDK now
recommends; `client.models.generate_content(…)` still answers, but it is the
one on its way out. The wrapper tries the chat route first and falls back to
the ladder in `core/gemini.py` — the ladder is the app's resilience, so it is
what answers when the chat route cannot.

**IT RETURNS THE RESPONSE OBJECT, NOT THE TEXT.** The SDK's response carries
`.text`, `.candidates` and the grounding metadata, and every caller in this
codebase expects that object — a wrapper that returned a plain string would
turn `response.text` into an AttributeError at the first call. The text is
one attribute away, and the object is the thing worth keeping.

The module lives at the application root rather than in `actions/`, because
`actions/` is not a package: it is loaded by path, so a relative import from
one of its files cannot resolve. The one file that uses it loads it by path
too, and falls back to the plain call when it is absent.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def call_with_afc_fallback(
    client,
    prompt: str,
    tier: str = "smart",
    timeout_ms: int = 60000,
    use_chat_api: bool = True,
) -> Optional[Any]:
    """Call Gemini, preferring the chat route. Returns the response object.

    Args:
        client: Configured genai.Client
        prompt: The prompt/contents to send
        tier: Reasoning tier (fast/smart)
        timeout_ms: Timeout in milliseconds
        use_chat_api: Whether to try the chat route first

    Returns:
        The SDK's response object (it has `.text`), or None when no route
        answered.
    """
    from core import gemini as gemini_core

    if use_chat_api and client is not None:
        # The chat route needs a model of its own — it cannot walk the
        # ladder — so it is opened with the first model of the tier that is
        # not cooling. Anything that is not the SDK's chat API is simply not
        # there, and then the ladder answers.
        model = gemini_core.first_model(tier if tier in ("fast", "smart")
                                        else gemini_core.SMART)
        if model:
            try:
                chat = client.chats.create(model=model)
                return chat.send_message(message=prompt)
            except Exception as e:
                logger.info("chat route unavailable on %s (%s) — using the ladder",
                            model, type(e).__name__)

    # The ladder: the model fallback, the timeout, the quota cooldowns.
    try:
        tier_enum = gemini_core.FAST if tier == "fast" else gemini_core.SMART
        return gemini_core.call(contents=prompt, tier=tier_enum,
                                timeout_ms=timeout_ms)
    except Exception as e:
        logger.error("every Gemini route failed: %s", e)
        return None


def safe_generate_content(client, prompt: str, tier: str = "smart") -> Optional[Any]:
    """One generation, the way the rest of the app expects it back.

    Returns the SDK's response object, so `response.text` works — which is how
    every caller in `actions/code_helper.py` reads it.
    """
    return call_with_afc_fallback(client, prompt, tier=tier,
                                  use_chat_api=True)
