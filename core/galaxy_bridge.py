"""
Galaxy visualization bridge for JARVIS core
Handles communication between Python/JARVIS and the TypeScript/Vite/Three.js visualization
"""

import json
import threading
import time
import queue
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GalaxyBridge:
    """Bridge between JARVIS core and galaxy visualization"""

    def __init__(self, galaxy_dir: Path):
        self.galaxy_dir = galaxy_dir
        self.is_running = False
        self.update_queue = queue.Queue()
        self.current_state = 'idle'
        self.audio_levels = {
            'voice': 0.0,
            'bass': 0.0,
            'treble': 0.0
        }
        self._update_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the bridge update thread"""
        if self.is_running:
            return

        self.is_running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info("Galaxy bridge started")

    def stop(self):
        """Stop the bridge update thread"""
        self.is_running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=1.0)
        logger.info("Galaxy bridge stopped")

    def set_state(self, state: str):
        """Set the current AI state"""
        valid_states = ['idle', 'arming', 'listening', 'thinking', 'speaking', 'error']
        if state in valid_states:
            self.current_state = state
            self._queue_update({'type': 'state', 'state': state})
            logger.debug(f"Galaxy state set to: {state}")
        else:
            logger.warning(f"Invalid galaxy state: {state}")

    def set_audio_levels(self, voice: float, bass: float, treble: float):
        """Set audio levels from microphone/playback"""
        self.audio_levels = {
            'voice': max(0.0, min(1.0, voice)),
            'bass': max(0.0, min(1.0, bass)),
            'treble': max(0.0, min(1.0, treble))
        }
        self._queue_update({
            'type': 'audio',
            'levels': self.audio_levels
        })
        logger.debug(f"Audio levels updated: {self.audio_levels}")

    def _queue_update(self, data: Dict[str, Any]):
        """Queue an update to be sent to the visualization"""
        try:
            self.update_queue.put_nowait(data)
        except queue.Full:
            logger.warning("Galaxy update queue full, dropping update")

    def _update_loop(self):
        """Main update loop - runs in background thread"""
        while self.is_running:
            try:
                # Get update with timeout to allow checking is_running
                try:
                    update = self.update_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # In a real implementation, this would send data to the web view
                # via WebSocket, Qt property system, or similar mechanism
                # For now, we'll just log the updates
                logger.debug(f"Galaxy update: {update}")

                # TODO: Implement actual communication mechanism
                # Options:
                # 1. WebSocket server that the TypeScript app connects to
                # 2. Qt properties that the web view polls via QtWebEngine IPC
                # 3. File-based communication (temporary files in temp directory)
                # 4. Custom Qt signal/slot mechanism

            except Exception as e:
                logger.error(f"Error in galaxy bridge update loop: {e}")
                time.sleep(0.1)  # Prevent tight loop on error

    def get_galaxy_url(self) -> str:
        """Get the URL to load the galaxy visualization"""
        # This would point to the built or dev server version
        # In development: http://localhost:5173
        # In production: file:// or qrc:// URL to built assets
        return "http://localhost:5173"  # Dev server URL

    def is_available(self) -> bool:
        """Check if the galaxy visualization is available"""
        # Check if the galaxy directory exists and has required files
        package_json = self.galaxy_dir / "package.json"
        return package_json.exists()


def create_galaxy_bridge(galaxy_dir: Optional[Path] = None) -> GalaxyBridge:
    """Factory function to create a galaxy bridge"""
    if galaxy_dir is None:
        # Default to galaxy directory in current workspace
        galaxy_dir = Path(__file__).parent.parent / "galaxy"

    return GalaxyBridge(galaxy_dir)