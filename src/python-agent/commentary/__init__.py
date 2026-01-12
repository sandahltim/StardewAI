"""Commentary package - Elias's voice for streaming.

VLM generates inner monologue. TTS speaks it.
No templates, just Elias being Elias.
"""

from .generator import CommentaryGenerator
from .elias_character import (
    ELIAS_CHARACTER,
    INNER_MONOLOGUE_PROMPT,
    TTS_VOICES,
    DEFAULT_VOICE,
    get_voice_id,
    get_voice_list,
)
from .coqui_tts import CoquiTTS
from .tts import PiperTTS  # Keep for fallback
from .async_worker import AsyncCommentaryWorker

# Legacy exports for backward compatibility
# RUSTY_CHARACTER now points to ELIAS_CHARACTER
RUSTY_CHARACTER = ELIAS_CHARACTER
DEFAULT_PERSONALITY = DEFAULT_VOICE
PERSONALITY_VOICES = {k: v["id"] for k, v in TTS_VOICES.items()}
PERSONALITIES = {}  # Empty - templates are gone

__all__ = [
    "CommentaryGenerator",
    "CoquiTTS",
    "PiperTTS",
    "AsyncCommentaryWorker",
    # New exports
    "ELIAS_CHARACTER",
    "RUSTY_CHARACTER",  # Legacy alias
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
