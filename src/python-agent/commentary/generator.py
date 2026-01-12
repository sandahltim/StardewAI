"""Commentary generator - VLM-driven inner monologue.

Rusty's voice comes from the VLM, not templates.
This module just passes through VLM output and handles TTS.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .rusty_character import TTS_VOICES, DEFAULT_VOICE, get_voice_id


class CommentaryGenerator:
    """Pass through Rusty's VLM-generated inner monologue."""

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice if voice in TTS_VOICES else DEFAULT_VOICE
        self._last_monologue = ""
        self._last_spoken = ""  # Track what TTS already said to avoid repeats

    def set_voice(self, voice: str) -> None:
        """Set the TTS voice (cosmetic only - doesn't change personality)."""
        if voice in TTS_VOICES:
            self.voice = voice

    # Legacy compatibility - personality maps to voice now
    def set_personality(self, personality: str) -> None:
        """Legacy method - now just sets voice."""
        self.set_voice(personality)

    @property
    def personality(self) -> str:
        """Legacy property - returns current voice."""
        return self.voice

    def get_voice(self) -> str:
        """Get TTS voice ID for current voice setting."""
        return get_voice_id(self.voice)

    def get_voices(self) -> Dict[str, Dict[str, str]]:
        """Get all available TTS voices."""
        return TTS_VOICES

    def generate(self, action: Optional[str], state: Optional[Dict], vlm_monologue: str = "") -> str:
        """Get commentary - only return NEW VLM monologue, never repeat.
        
        Args:
            action: Current action type
            state: Game state dict
            vlm_monologue: Inner monologue from VLM response (preferred)
        
        Returns:
            Commentary text for display/TTS, or empty string if nothing new
        """
        # Only use VLM monologue if it's NEW (different from last spoken)
        if vlm_monologue and vlm_monologue.strip():
            monologue = vlm_monologue.strip()
            if monologue != self._last_spoken:
                self._last_monologue = monologue
                self._last_spoken = monologue
                return monologue
            # Same as last time - return empty to skip TTS
            return ""

        # No VLM monologue - return empty (don't fall back to descriptions for TTS)
        return ""
    
    def get_display_text(self, action: Optional[str], state: Optional[Dict], vlm_monologue: str = "") -> str:
        """Get text for UI display (can repeat, just for visual)."""
        if vlm_monologue and vlm_monologue.strip():
            return vlm_monologue.strip()
        if self._last_monologue:
            return self._last_monologue
        if action:
            return self._simple_description(action, state)
        return "..."

    def _simple_description(self, action: str, state: Optional[Dict]) -> str:
        """Simple, non-template action description as fallback."""
        action_lower = action.lower().replace("_", " ")
        
        # Just describe what's happening - no personality
        if "plant" in action_lower:
            return "Planting seeds..."
        if "water" in action_lower:
            return "Watering..."
        if "harvest" in action_lower:
            return "Harvesting..."
        if "clear" in action_lower:
            return "Clearing debris..."
        if "till" in action_lower:
            return "Tilling soil..."
        if "move" in action_lower:
            return "Moving..."
        if "bed" in action_lower or "sleep" in action_lower:
            return "Time for bed..."
        
        return f"{action_lower.capitalize()}..."

    def reset_session_stats(self) -> None:
        """Reset for new day - clear cached monologues."""
        self._last_monologue = ""
        self._last_spoken = ""