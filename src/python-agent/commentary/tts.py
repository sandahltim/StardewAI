"""Optional Piper TTS integration."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class PiperTTS:
    # Voice model paths - check common locations
    VOICE_DIRS = [
        Path.home() / ".local/share/piper-voices",
        Path("/usr/share/piper-voices"),
    ]

    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice
        self.piper_available = shutil.which("piper") is not None
        self.model_path = self._find_model(voice)
        self.available = self.piper_available and self.model_path is not None
        self.enabled = True  # Can be toggled by UI

    def _find_model(self, voice: str) -> Optional[Path]:
        """Find the .onnx model file for a voice."""
        for voice_dir in self.VOICE_DIRS:
            model_file = voice_dir / f"{voice}.onnx"
            if model_file.exists():
                return model_file
        return None

    def speak(self, text: str, voice: Optional[str] = None) -> bool:
        """Speak text using Piper TTS. Returns True if successful."""
        if not self.available or not self.enabled:
            return False

        # Sanitize text for shell
        safe_text = text.replace('"', '\\"').replace("'", "\\'")

        model = self.model_path
        if voice and voice != self.voice:
            alt_model = self._find_model(voice)
            if alt_model:
                model = alt_model

        cmd = f'echo "{safe_text}" | piper --model {model} --output-raw | aplay -r 22050 -f S16_LE -q'
        try:
            subprocess.run(cmd, shell=True, check=False, timeout=30)
            return True
        except subprocess.TimeoutExpired:
            return False

    def toggle(self, enabled: bool) -> None:
        """Enable/disable TTS."""
        self.enabled = enabled
