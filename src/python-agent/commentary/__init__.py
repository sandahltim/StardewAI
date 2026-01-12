"""Commentary package - Rusty's voice for streaming.

VLM generates inner monologue. TTS speaks it. 
No templates, just Rusty being Rusty.
"""

from .generator import CommentaryGenerator
from .rusty_character import (
    RUSTY_CHARACTER,
    INNER_MONOLOGUE_PROMPT,
    TTS_VOICES,
    DEFAULT_VOICE,
    get_voice_id,
    get_voice_list,
)
from .tts import PiperTTS
from .async_worker import AsyncCommentaryWorker

# Legacy exports for backward compatibility
# These now map to the new voice system
DEFAULT_PERSONALITY = DEFAULT_VOICE
PERSONALITY_VOICES = {k: v["id"] for k, v in TTS_VOICES.items()}
PERSONALITIES = {}  # Empty - templates are gone

__all__ = [
    "CommentaryGenerator",
    "PiperTTS",
    "AsyncCommentaryWorker",
    # New exports
    "RUSTY_CHARACTER",
    "INNER_MONOLOGUE_PROMPT", 
    "TTS_VOICES",
    "DEFAULT_VOICE",
    "get_voice_id",
    "get_voice_list",
    # Legacy (deprecated)
    "DEFAULT_PERSONALITY",
    "PERSONALITY_VOICES",
    "PERSONALITIES",
]
