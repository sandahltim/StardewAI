"""Coqui XTTS integration - natural voice synthesis.

Uses XTTS v2 for high-quality voice cloning. Runs on CPU to avoid
competing with VLM for GPU resources. Slower than Piper but much
more natural sounding.

License: CPML (non-commercial) - check https://coqui.ai/cpml for terms
"""

import logging
import os

# Auto-accept Coqui license (non-commercial use)
os.environ['COQUI_TOS_AGREED'] = '1'
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# Lazy import to avoid loading torch until needed
_tts_instance = None


def _get_tts():
    """Lazy-load the TTS model (expensive, do once)."""
    global _tts_instance
    if _tts_instance is None:
        try:
            from TTS.api import TTS
            logging.info("Loading Coqui XTTS v2 model (first time, may download)...")
            # Force CPU to not compete with VLM for GPU
            _tts_instance = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
            logging.info("Coqui XTTS v2 loaded on CPU")
        except Exception as e:
            logging.error(f"Failed to load Coqui TTS: {e}")
            _tts_instance = False  # Mark as failed, don't retry
    return _tts_instance if _tts_instance else None


class CoquiTTS:
    """Text-to-speech using Coqui XTTS v2.
    
    Requires a reference voice file for voice cloning.
    Falls back to default voice if no reference provided.
    """
    
    # Default locations for reference voice
    VOICE_DIRS = [
        Path("/home/tim/StardewAI/assets/voices"),
        Path.home() / ".local/share/stardew-ai/voices",
    ]
    
    DEFAULT_VOICE_FILE = "rusty_reference.wav"
    
    def __init__(self, voice_file: Optional[str] = None):
        """Initialize Coqui TTS.
        
        Args:
            voice_file: Path to reference voice WAV file for cloning.
                       If None, searches default locations.
        """
        self.voice_file = self._find_voice(voice_file)
        self.enabled = True
        self._available = None  # Lazy check
        
    def _find_voice(self, voice_file: Optional[str]) -> Optional[Path]:
        """Find the reference voice file."""
        if voice_file:
            path = Path(voice_file)
            if path.exists():
                return path
                
        # Search default locations
        for voice_dir in self.VOICE_DIRS:
            candidate = voice_dir / self.DEFAULT_VOICE_FILE
            if candidate.exists():
                return candidate
                
        # No reference voice found - will use model's default
        logging.warning("No reference voice found for Coqui TTS - using default voice")
        return None
        
    @property
    def available(self) -> bool:
        """Check if Coqui TTS is available."""
        if self._available is None:
            tts = _get_tts()
            self._available = tts is not None
        return self._available
        
    def speak(self, text: str, voice: Optional[str] = None) -> bool:
        """Speak text using Coqui XTTS (blocking - waits for completion).
        
        Runs on commentary worker thread, so blocking here doesn't
        affect the main agent loop. This prevents TTS overlap.
        
        Args:
            text: Text to speak
            voice: Optional path to different reference voice
            
        Returns:
            True if speech completed successfully
        """
        if not self.available or not self.enabled:
            return False
            
        tts = _get_tts()
        if not tts:
            return False
            
        # Use provided voice or default
        voice_file = voice if voice else self.voice_file
        
        try:
            # Generate to temp file then play
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                
            # Generate speech
            if voice_file and Path(voice_file).exists():
                # Voice cloning mode
                tts.tts_to_file(
                    text=text,
                    speaker_wav=str(voice_file),
                    language="en",
                    file_path=temp_path,
                )
            else:
                # Use model's built-in speaker (less natural but works)
                # XTTS requires a speaker reference, so fall back to a simple approach
                tts.tts_to_file(
                    text=text,
                    language="en", 
                    file_path=temp_path,
                    speaker="Ana Florence",  # Built-in speaker
                )
                
            # Play the audio (blocking)
            subprocess.run(
                ["aplay", "-q", temp_path],
                check=True,
                capture_output=True,
            )
            
            # Cleanup
            os.unlink(temp_path)
            return True
            
        except Exception as e:
            logging.error(f"Coqui TTS error: {e}")
            # Cleanup on error
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except Exception:
                pass
            return False
            
    def toggle(self, enabled: bool) -> None:
        """Enable/disable TTS."""
        self.enabled = enabled
