"""
Utility functions for Gemini API calls with AFC deprecation fix.

Provides backward-compatible wrapper that uses Chat.send_message (recommended)
with fallback to generate_content (deprecated but still works).
"""

import logging
from typing import Optional, Any, Callable, Union

logger = logging.getLogger(__name__)


def _create_session_if_needed(client) -> str:
    """Create or return a session ID for Chat API usage.

    In a real implementation, you'd maintain session state. For now,
    we use a simple approach.
    """
    # Session management would be handled by the caller or framework
    # This is a placeholder for the Chat.send_message pattern
    return "session_current"


def call_with_afc_fallback(
    client,
    prompt: str,
    tier: str = "smart",
    timeout_ms: int = 60000,
    use_chat_api: bool = True,
) -> Optional[Any]:
    """Call Gemini with Automatic Function Calling using recommended approach.

    Recommended: use Chat.send_message to avoid AFC deprecation warning.
    Falls back to generate_content if chat API is unavailable.

    Args:
        client: Configured genai.Client
        prompt: The prompt/contents to send
        tier: Reasoning tier (fast/smart)
        timeout_ms: Timeout in milliseconds
        use_chat_api: Whether to try Chat.send_message first

    Returns:
        Response text or None
    """
    from core import gemini as gemini_core

    if use_chat_api:
        try:
            # Recommended approach: Chat.send_message
            session_id = _create_session_if_needed(client)
            response = client.chats.send_message(
                session_id=session_id,
                message=prompt,
            )
            # Extract text from response
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'get("text")):
                return response.get("text")
            # Try to convert to string if it's an object
            return str(response)
        except Exception as e:
            logger.warning(f"Chat.send_message failed: {e}, falling back to generate_content")
            # Fall through to deprecated approach

    # Deprecated but still working approach: generate_content
    try:
        tier_enum = gemini_core.FAST if tier == "fast" else gemini_core.SMART
        resp = gemini_core.call(
            contents=prompt,
            tier=tier_enum,
            timeout_ms=timeout_ms,
        )
        if resp is None:
            return None
        if hasattr(resp, 'text'):
            return resp.text
        return str(resp) if resp else None
    except Exception as e:
        logger.error(f"generate_content also failed: {e}")
        return None


# Convenience wrapper for code_helper usage
def safe_generate_content(client, prompt: str, tier: str = "smart") -> Optional[str]:
    """Safe Gemini content generation with AFC deprecation protection.

    Uses the recommended Chat.send_message approach, with fallback.
    """
    return call_with_afc_fallback(client, prompt, tier=tier, use_chat_api=True)


# Example usage pattern for code_helper.py
"""
# Instead of:
#   resp = gemini.call(contents, tier=tier, timeout_ms=60000)
#   return resp.text

# Use:
#   from gemini_afc_fix import safe_generate_content
#   resp = safe_generate_content(client, prompt, tier="smart")
#   if resp is None:
#       raise RuntimeError("every Gemini model on the ladder failed")
#   return resp
"""

# For dev_agent.py and file_processor.py, use the same pattern:
"""
# Replace:
#   response = model.generate_content(prompt)
# With:
#   from gemini_afc_fix import safe_generate_content
#   response = safe_generate_content(client, prompt, tier="smart")
#   if response is None:
#       raise RuntimeError("every Gemini model on the ladder failed")
#   return response.text
"""