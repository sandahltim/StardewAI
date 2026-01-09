"""Commentary generator with personality templates."""

from __future__ import annotations

import random
from typing import Dict, Optional

from .personalities import DEFAULT_PERSONALITY, PERSONALITIES


class CommentaryGenerator:
    def __init__(self, personality: str = DEFAULT_PERSONALITY):
        self.personality = personality if personality in PERSONALITIES else DEFAULT_PERSONALITY
        self._last_milestone = None

    def set_personality(self, personality: str) -> None:
        if personality in PERSONALITIES:
            self.personality = personality

    def get_personalities(self) -> Dict[str, Dict[str, list]]:
        return PERSONALITIES

    def generate(self, action: Optional[str], state: Optional[Dict], mood: str = "") -> str:
        personality = PERSONALITIES.get(self.personality, PERSONALITIES[DEFAULT_PERSONALITY])
        tag = self._select_tag(action, state)
        options = personality.get(tag) or personality.get("action") or ["{action}."]
        template = random.choice(options)
        action_text = self._format_action(action, state)
        text = template.format(action=action_text, mood=mood)
        return text.strip()

    def _select_tag(self, action: Optional[str], state: Optional[Dict]) -> str:
        if not state:
            return "action" if action else "idle"
        time = state.get("time") or {}
        hour = time.get("hour")
        weather = time.get("weather") or state.get("weather")
        player = state.get("player") or {}
        energy = player.get("energy")
        max_energy = player.get("maxEnergy") or player.get("max_energy")
        if weather and str(weather).lower() == "rainy":
            return "rain"
        if hour is not None and hour >= 22:
            return "late"
        if energy is not None and max_energy:
            if max_energy > 0 and energy / max_energy <= 0.25:
                return "low_energy"
        milestone = self._detect_milestone(state)
        if milestone:
            self._last_milestone = milestone
            return "milestone"
        if not action or action == "wait":
            return "idle"
        return "action"

    def _detect_milestone(self, state: Dict) -> Optional[str]:
        stats = state.get("stats") or {}
        harvested = stats.get("crops_harvested_count") or state.get("crops_harvested_count")
        if harvested and harvested != self._last_milestone:
            return f"harvest_{harvested}"
        money = (state.get("player") or {}).get("money")
        if money and money >= 1000 and self._last_milestone != "money_1000":
            return "money_1000"
        return None

    def _format_action(self, action: Optional[str], state: Optional[Dict]) -> str:
        if not action:
            return "waiting"
        action_lower = action.replace("_", " ").strip().lower()
        if action_lower == "use tool":
            tool = (state or {}).get("player", {}).get("currentTool") or "tool"
            return f"using the {tool}"
        if action_lower == "move":
            return "moving around"
        if action_lower == "harvest":
            return "harvesting crops"
        if action_lower == "water":
            return "watering crops"
        return action_lower
