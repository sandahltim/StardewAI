"""Optional Piper TTS integration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


class PiperTTS:
    # Voice model paths - check common locations
    VOICE_DIRS = [
        Path("/Gary/models/piper"),  # Shared voice collection
        Path.home() / ".local/share/piper-voices",
        Path("/usr/share/piper-voices"),
    ]

    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice
        self.piper_path = self._find_piper()
        self.model_path = self._find_model(voice)
        self.available = self.piper_path is not None and self.model_path is not None
        self.enabled = True  # Can be toggled by UI
        self._current_process: Optional[subprocess.Popen] = None  # Track active TTS

    def _find_piper(self) -> Optional[Path]:
        """Find piper binary - check venv first, then PATH."""
        # Check venv bin directory (same location as python interpreter)
        venv_piper = Path(sys.executable).parent / "piper"
        if venv_piper.exists():
            return venv_piper
        # Fall back to PATH
        path_piper = shutil.which("piper")
        if path_piper:
            return Path(path_piper)
        return None

    def _find_model(self, voice: str) -> Optional[Path]:
        """Find the .onnx model file for a voice."""
        for voice_dir in self.VOICE_DIRS:
            model_file = voice_dir / f"{voice}.onnx"
            if model_file.exists():
                return model_file
        return None

    def _kill_current(self) -> None:
        """Kill any currently playing TTS to prevent overlap."""
        if self._current_process is not None:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=0.5)
            except Exception:
                try:
                    self._current_process.kill()
                except Exception:
                    pass
            self._current_process = None

    def speak(self, text: str, voice: Optional[str] = None) -> bool:
        """Speak text using Piper TTS (non-blocking). Returns True if started."""
        if not self.available or not self.enabled:
            return False

        # Kill any previous TTS to prevent overlap
        self._kill_current()

        # Sanitize text for shell
        safe_text = text.replace('"', '\\"').replace("'", "\\'")

        model = self.model_path
        if voice and voice != self.voice:
            alt_model = self._find_model(voice)
            if alt_model:
                model = alt_model

        # Non-blocking: use Popen instead of run so agent doesn't wait for speech
        cmd = f'echo "{safe_text}" | {self.piper_path} --model {model} --output-raw | aplay -r 22050 -f S16_LE -q'
        try:
            self._current_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def toggle(self, enabled: bool) -> None:
        """Enable/disable TTS."""
        self.enabled = enabled

    @classmethod
    def list_voices(cls) -> list[str]:
        """List all available voice names."""
        voices = []
        for voice_dir in cls.VOICE_DIRS:
            if voice_dir.exists():
                for model in voice_dir.glob("*.onnx"):
                    voice_name = model.stem
                    if voice_name not in voices:
                        voices.append(voice_name)
        return sorted(voices)
