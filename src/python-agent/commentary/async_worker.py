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
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .generator import CommentaryGenerator
from .tts import PiperTTS
from .coqui_tts import CoquiTTS


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
        tts_backend: str = "coqui",  # "coqui" or "piper"
    ):
        self.generator = CommentaryGenerator()
        self.ui_callback = ui_callback
        
        # Try Coqui first (better quality), fall back to Piper
        if tts_backend == "coqui":
            self.tts = CoquiTTS()
            if not self.tts.available:
                logging.warning("Coqui TTS not available, falling back to Piper")
                self.tts = PiperTTS()
        else:
            self.tts = PiperTTS()
            
        logging.info(f"TTS backend: {type(self.tts).__name__}")
        
        self._queue: queue.Queue[Optional[CommentaryEvent]] = queue.Queue(maxsize=50)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Settings from UI (updated via set_settings)
        self._tts_enabled = True
        self._voice_override: Optional[str] = None
        self._volume = 1.0
        self._coqui_voice: Optional[str] = None
        
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
        coqui_voice: Optional[str] = None,
    ) -> None:
        """Update settings from UI (thread-safe)."""
        if tts_enabled is not None:
            self._tts_enabled = tts_enabled
        if voice is not None:
            self._voice_override = voice
            self.generator.set_voice(voice)
        if volume is not None:
            self._volume = volume
        if coqui_voice is not None:
            self._coqui_voice = coqui_voice
            # Update CoquiTTS voice file if using Coqui backend
            if isinstance(self.tts, CoquiTTS):
                voice_path = Path(f"/home/tim/StardewAI/assets/voices/{coqui_voice}.wav")
                if voice_path.exists():
                    self.tts.voice_file = voice_path
                    logging.info(f"Coqui voice changed to: {coqui_voice}")
            
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
        # Don't skip stale events - let TTS keep flowing continuously
        # Old events still have valid commentary worth speaking
            
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
                
        # TTS (blocks until complete to prevent overlap)
        if self._should_speak(tts_text):
            self._speak(tts_text)
        else:
            # Debug: why didn't we speak?
            if not tts_text:
                logging.debug(f"🔇 TTS skip: generator returned empty (filtered as duplicate)")
            elif not self._tts_enabled:
                logging.info(f"🔇 TTS skip: TTS disabled")
            elif not self.tts.available:
                logging.info(f"🔇 TTS skip: TTS not available")
            
    def _should_speak(self, text: str) -> bool:
        """Check if we should speak this text."""
        if not text:
            return False
        if not self._tts_enabled:
            return False
        if not self.tts.available:
            return False
        return True
        
    def _speak(self, text: str) -> None:
        """Speak text via TTS (blocks until complete to prevent overlap)."""
        # Clean text for TTS
        clean_text = re.sub(r'["\*\_\#\`\[\]\(\)\{\}\\\\]', '', text)  # Keep apostrophes for contractions
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if not clean_text:
            return
            
        # Get voice
        voice = self._voice_override
        if not voice:
            voice = self.generator.get_voice()
            
        # Speak (blocks until complete - runs on worker thread so doesn't affect agent)
        if self.tts.speak(clean_text, voice=voice):
            logging.info(f"🔊 TTS: {clean_text[:50]}...")