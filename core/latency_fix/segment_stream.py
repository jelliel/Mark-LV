"""
Latency fix for Mark-LV voice assistant
Implements per-sentence streaming LLM→TTS→playback pipeline
Based on natural-convo.md specification
"""

import asyncio
import time
import uuid
import threading
from typing import Dict, Optional, Callable, Any, List
from collections import OrderedDict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class SpeechSegment:
    """Represents a sentence segment for TTS"""
    segment_id: str
    base_turn_id: str
    seq: int
    text: str
    is_final: bool
    timestamp: float
    auto_continue: bool = False

class SegmentManager:
    """Manages speech segments with TTL cleanup"""

    def __init__(self, ttl_seconds: float = 120.0):
        self.ttl_seconds = ttl_seconds
        self.segments: Dict[str, tuple] = {}  # segment_id -> (text, expiry_time)
        self._lock = threading.Lock()

    def record_segment(self, segment_id: str, text: str) -> None:
        """Record segment text with expiry"""
        now = time.monotonic()
        expiry = now + self.ttl_seconds

        with self._lock:
            # Lazy cleanup of expired segments
            expired = [sid for sid, (_, exp) in self.segments.items() if exp < now]
            for sid in expired:
                self.segments.pop(sid, None)

            self.segments[segment_id] = (text, expiry)

    def get_segment_text(self, segment_id: str) -> Optional[str]:
        """Get segment text if not expired"""
        now = time.monotonic()

        with self._lock:
            # Cleanup expired segments
            expired = [sid for sid, (_, exp) in self.segments.items() if exp < now]
            for sid in expired:
                self.segments.pop(sid, None)

            if segment_id in self.segments:
                text, _ = self.segments[segment_id]
                return text
        return None

    def cleanup(self) -> None:
        """Cleanup all expired segments"""
        now = time.monotonic()
        with self._lock:
            expired = [sid for sid, (_, exp) in self.segments.items() if exp < now]
            for sid in expired:
                self.segments.pop(sid, None)

class SpeechSegmentEmitter:
    """Handles emitting speech segments over WebSocket"""

    def __init__(self, websocket_send_func: Callable):
        self.send_func = websocket_send_func
        self.segment_counter = 0
        self.base_turn_id: Optional[str] = None
        self.held_text: Optional[str] = None
        self.held_seq: Optional[int] = None
        self.turn_start_time: Optional[float] = None
        self.segment_manager = SegmentManager()

    def start_turn(self) -> str:
        """Start a new turn and return base_turn_id"""
        self.base_turn_id = uuid.uuid4().hex
        self.segment_counter = 0
        self.held_text = None
        self.held_seq = None
        self.turn_start_time = time.monotonic()
        logger.info(f"Started turn {self.base_turn_id}")
        return self.base_turn_id

    async def process_sentence(self, sentence: str) -> None:
        """Process a sentence using hold-one-ahead pattern"""
        if not self.base_turn_id:
            raise RuntimeError("No active turn - call start_turn() first")

        current_seq = self.segment_counter

        # If we're holding a previous sentence, emit it as non-final
        if self.held_text is not None:
            await self._emit_segment(
                self.held_text,
                self.held_seq,
                is_final=False
            )

        # Hold the current sentence
        self.held_text = sentence
        self.held_seq = current_seq
        self.segment_counter += 1

        # Still forward transcript for UI (existing behavior)
        await self.send_func({
            "type": "transcript_delta",
            "text": sentence
        })

    async def end_turn(self, auto_continue: bool = False) -> None:
        """End the current turn, flushing any held sentence as final"""
        if self.base_turn_id is None:
            return

        if self.held_text is not None:
            await self._emit_segment(
                self.held_text,
                self.held_seq,
                is_final=True,
                auto_continue=auto_continue
            )

        # Reset turn state
        self.base_turn_id = None
        self.held_text = None
        self.held_seq = None
        self.turn_start_time = None

    async def _emit_segment(self, text: str, seq: int, is_final: bool, auto_continue: bool = False) -> None:
        """Emit a speech segment"""
        if not self.base_turn_id:
            return

        segment_id = f"{self.base_turn_id}::{seq}"

        # Record segment for TTS lookup
        self.segment_manager.record_segment(segment_id, text)

        # Emit segment event
        await self.send_func({
            "type": "speak_segment",
            "turn_id": segment_id,
            "base_turn_id": self.base_turn_id,
            "seq": seq,
            "is_final": is_final,
            "auto_continue": auto_continue if is_final else False,
        })

        # Log latency metric
        if self.turn_start_time:
            latency = time.monotonic() - self.turn_start_time
            logger.info(
                f"speak_segment base={self.base_turn_id} seq={seq} "
                f"chars={len(text)} t_since_turn_start={latency:.2f}s "
                f"final={is_final}"
            )

    def get_segment_text(self, segment_id: str) -> Optional[str]:
        """Get text for a segment ID"""
        return self.segment_manager.get_segment_text(segment_id)

    def cleanup(self) -> None:
        """Cleanup expired segments"""
        self.segment_manager.cleanup()

class AudioSegmentPlayer:
    """Handles client-side audio queue and sequential playback"""

    def __init__(self,
                 tts_fetch_func: Callable[[str], Any],
                 audio_play_func: Callable[[Any], Any],
                 on_segment_ended: Optional[Callable] = None,
                 on_turn_complete: Optional[Callable] = None):
        self.tts_fetch = tts_fetch_func
        self.audio_play = audio_play_func
        self.on_segment_ended = on_segment_ended
        self.on_turn_complete = on_turn_complete

        self.audio_queue: List[Dict] = []
        self.currently_playing = False
        self.active_base_turn_id: Optional[str] = None
        self.last_segment_was_final = False
        self.current_fetch_abort: Optional[Any] = None
        self._lock = threading.Lock()

    def handle_speak_segment(self, message: Dict) -> None:
        """Handle incoming speak_segment message"""
        base_turn_id = message.get("base_turn_id")
        turn_id = message.get("turn_id")

        # Start of new turn
        if (not self.audio_queue and not self.currently_playing and
            base_turn_id is not None):
            self.active_base_turn_id = base_turn_id
            # UI: flip to speaking state
            if self.on_segment_ended:  # Reuse for UI notification
                pass  # Would trigger UI speaking state

        # Drop stale segments from interrupted turns
        elif self.active_base_turn_id is not None and base_turn_id != self.active_base_turn_id:
            logger.warning(f"Dropping stale segment {base_turn_id} (expected {self.active_base_turn_id})")
            return

        # Add to queue and pump
        self.audio_queue.append(message)
        self._pump_queue()

    def _pump_queue(self) -> None:
        """Process next segment in queue if not currently playing"""
        if self.currently_playing or not self.audio_queue:
            return

        segment = self.audio_queue.pop(0)
        self.last_segment_was_final = segment.get("is_final", False)
        self.currently_playing = True

        # Fetch and play segment audio (non-blocking)
        asyncio.create_task(self._play_segment_audio(segment["turn_id"]))

    async def _play_segment_audio(self, turn_id: str) -> None:
        """Fetch and play a single segment's audio"""
        try:
            # Create abortable fetch for interruption handling
            # In real implementation, this would use AbortController equivalent
            audio_data = await self.tts_fetch(turn_id)

            # Play audio using existing audio path
            await self.audio_play(audio_data)

            # Handle segment completion
            if self.on_segment_ended:
                self.on_segment_ended()

        except Exception as e:
            # Handle fetch/play errors (including aborts)
            if "AbortError" in str(type(e)) or "cancelled" in str(e).lower():
                logger.info(f"Audio fetch aborted for segment {turn_id}")
            else:
                logger.error(f"Segment playback failed for {turn_id}: {e}")
        finally:
            await self._on_segment_ended()

    async def _on_segment_ended(self) -> None:
        """Handle completion of segment playback"""
        self.currently_playing = False

        if self.audio_queue:
            # Play next segment
            self._pump_queue()
        elif self.last_segment_was_final:
            # Turn is complete
            if self.on_turn_complete:
                self.on_turn_complete()

            # Reset turn state
            self.active_base_turn_id = None
            self.last_segment_was_final = False

    def interrupt(self) -> None:
        """Handle user interrupt (stop speaking)"""
        with self._lock:
            self.audio_queue.clear()
            # In real implementation: abort current fetch
            self.current_fetch_abort = None  # Would abort fetch
            self.currently_playing = False
            self.active_base_turn_id = None
            self.last_segment_was_final = False
            # Audio stop would happen here
            logger.info("Interrupted audio playback")

# Integration helpers for existing Mark-LV code

def create_latency_fix_components(websocket_send_func: Callable,
                                tts_fetch_func: Callable[[str], Any],
                                audio_play_func: Callable[[Any], Any],
                                on_segment_ended: Optional[Callable] = None,
                                on_turn_complete: Optional[Callable] = None) -> Dict[str, Any]:
    """Factory function to create all latency fix components"""
    emitter = SpeechSegmentEmitter(websocket_send_func)
    player = AudioSegmentPlayer(tts_fetch_func, audio_play_func, on_segment_ended, on_turn_complete)

    return {
        "emitter": emitter,
        "player": player,
        "start_turn": emitter.start_turn,
        "process_sentence": emitter.process_sentence,
        "end_turn": emitter.end_turn,
        "handle_speak_segment": player.handle_speak_segment,
        "interrupt": player.interrupt,
        "get_segment_text": emitter.get_segment_text,
        "cleanup": lambda: (emitter.cleanup(), player.audio_queue.clear())
    }

# Example usage pattern for integration into main.py:
"""
# In JarvisLive.__init__ or wherever WebSocket handling is set up:
latency_components = create_latency_fix_components(
    websocket_send_func=lambda msg: self.session.send_client_content(
        turns={"role": "user", "parts": [{"text": str(msg)}]},
        turn_complete=True
    ),
    tts_fetch_func=lambda turn_id: self._fetch_tts_audio(turn_id),  # Your existing TTS function
    audio_play_func=lambda audio_data: self._play_audio_data(audio_data),  # Your existing audio play
    on_segment_ended=lambda: self._on_segment_ended(),  # Your existing segment end handler
    on_turn_complete=lambda: self._on_turn_complete()   # Your existing turn complete handler
)

# In your LLM processing loop where you get sentence chunks:
# Instead of buffering full response, process each sentence as it comes:
await latency_components["process_sentence"](sentence_chunk)

# When LLM stream ends:
await latency_components["end_turn"](auto_continue=False)

# In your WebSocket message handler for incoming messages:
if msg.get("type") == "speak_segment":
    latency_components["handle_speak_segment"](msg)
elif msg.get("type") == "interrupt":  # Or however you detect user interruption
    latency_components["interrupt"]()
"""

# Utility functions for sentence splitting (if needed)
def split_into_sentences(text: str) -> List[str]:
    """Simple sentence splitter - buffer until sentence boundary"""
    import re
    # Split on ., !, ? followed by whitespace or end of string
    # Handle common abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def is_sentence_complete(text: str) -> bool:
    """Check if text ends with sentence boundary"""
    return bool(re.search(r'[.!?](\s|$)', text.strip()))