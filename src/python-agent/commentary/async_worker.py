"""Async commentary worker - runs in background thread.

This prevents TTS and UI updates from blocking the agent's action loop.
Agent pushes events to a queue; worker processes them independently.
"""

import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .generator import CommentaryGenerator
from .tts import PiperTTS


@dataclass
class CommentaryEvent:
    """Event pushed to commentary queue."""
    action_type: str
    state: Dict[str, Any]
    vlm_monologue: str
    timestamp: float


class AsyncCommentaryWorker:
    """Background worker for commentary and TTS.
    
    Architecture:
        Agent Loop → Queue → Worker Thread → TTS + UI
        
    The agent just pushes events and continues - zero blocking.
    """
    
    def __init__(
        self,
        ui_callback: Optional[Callable] = None,
        tts_cooldown: float = 10.0,  # Increased from 4.0 - buffer for TTS completion
    ):
        self.generator = CommentaryGenerator()
        self.tts = PiperTTS()
        self.ui_callback = ui_callback
        self.tts_cooldown = tts_cooldown
        
        self._queue: queue.Queue[Optional[CommentaryEvent]] = queue.Queue(maxsize=10)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_tts_time = 0.0
        
        # Settings from UI (updated via set_settings)
        self._tts_enabled = True
        self._voice_override: Optional[str] = None
        self._volume = 1.0
        
    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logging.info("Commentary worker started")
        
    def stop(self) -> None:
        """Stop the worker thread gracefully."""
        if not self._running:
            return
            
        self._running = False
        self._queue.put(None)  # Poison pill to wake up worker
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logging.info("Commentary worker stopped")
        
    def push(
        self,
        action_type: str,
        state: Dict[str, Any],
        vlm_monologue: str = "",
    ) -> None:
        """Push event to queue (non-blocking).
        
        If queue is full, drops the event silently - commentary
        shouldn't slow down the agent.
        """
        if not self._running:
            return
            
        event = CommentaryEvent(
            action_type=action_type,
            state=state,
            vlm_monologue=vlm_monologue,
            timestamp=time.time(),
        )
        
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Drop event - better to skip commentary than block agent
            pass
            
    def set_settings(
        self,
        tts_enabled: Optional[bool] = None,
        voice: Optional[str] = None,
        volume: Optional[float] = None,
    ) -> None:
        """Update settings from UI (thread-safe)."""
        if tts_enabled is not None:
            self._tts_enabled = tts_enabled
        if voice is not None:
            self._voice_override = voice
            self.generator.set_voice(voice)
        if volume is not None:
            self._volume = volume
            
    def _worker_loop(self) -> None:
        """Main worker loop - processes events from queue."""
        while self._running:
            try:
                event = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            if event is None:  # Poison pill
                break
                
            try:
                self._process_event(event)
            except Exception as e:
                logging.error(f"Commentary worker error: {e}")
                
    def _process_event(self, event: CommentaryEvent) -> None:
        """Process a single commentary event."""
        # Skip stale events (older than 5 seconds)
        if time.time() - event.timestamp > 5.0:
            return
            
        # Get display text for UI
        ui_text = self.generator.get_display_text(
            event.action_type,
            event.state,
            vlm_monologue=event.vlm_monologue,
        )
        
        # Get TTS text - only returns if NEW
        tts_text = self.generator.generate(
            event.action_type,
            event.state,
            vlm_monologue=event.vlm_monologue,
        )
        
        # Update UI (if callback set)
        # Only send text/personality - NOT tts_enabled/volume (causes UI pulsing)
        if self.ui_callback and ui_text:
            try:
                self.ui_callback(
                    text=ui_text,
                    personality=self.generator.personality,
                )
            except Exception:
                pass  # UI errors shouldn't crash worker
                
        # TTS (with cooldown)
        if self._should_speak(tts_text):
            self._speak(tts_text)
            
    def _should_speak(self, text: str) -> bool:
        """Check if we should speak this text."""
        if not text:
            return False
        if not self._tts_enabled:
            return False
        if not self.tts.available:
            return False
            
        # Cooldown check
        current_time = time.time()
        if (current_time - self._last_tts_time) < self.tts_cooldown:
            return False
            
        return True
        
    def _speak(self, text: str) -> None:
        """Speak text via TTS."""
        # Clean text for TTS
        clean_text = re.sub(r'["\'\*\_\#\`\[\]\(\)\{\}]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if not clean_text:
            return
            
        # Get voice
        voice = self._voice_override
        if not voice:
            voice = self.generator.get_voice()
            
        # Speak (already non-blocking in PiperTTS)
        if self.tts.speak(clean_text, voice=voice):
            self._last_tts_time = time.time()
            logging.info(f"🔊 TTS: {clean_text[:50]}...")
