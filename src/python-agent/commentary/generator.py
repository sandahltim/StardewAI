"""Commentary generator with rich context awareness."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .personalities import DEFAULT_PERSONALITY, PERSONALITIES


class CommentaryGenerator:
    """Generate Rusty's commentary based on game state and actions."""

    def __init__(self, personality: str = DEFAULT_PERSONALITY):
        self.personality = personality if personality in PERSONALITIES else DEFAULT_PERSONALITY
        self._last_milestone = None
        self._action_counts: Dict[str, int] = {}
        self._session_crops_planted = 0
        self._session_crops_watered = 0
        self._session_debris_cleared = 0

    def set_personality(self, personality: str) -> None:
        if personality in PERSONALITIES:
            self.personality = personality

    def get_personalities(self) -> Dict[str, Dict[str, List[str]]]:
        return PERSONALITIES

    def generate(self, action: Optional[str], state: Optional[Dict], mood: str = "") -> str:
        """Generate commentary with full context awareness."""
        personality = PERSONALITIES.get(self.personality, PERSONALITIES[DEFAULT_PERSONALITY])

        # Extract rich context
        ctx = self._build_context(action, state)

        # Track action for variety
        if action:
            self._action_counts[action] = self._action_counts.get(action, 0) + 1
            self._update_session_stats(action)

        # Select appropriate tag and template
        tag = self._select_tag(action, state, ctx)
        options = personality.get(tag) or personality.get("action") or ["{action}."]
        template = random.choice(options)

        # Format with rich context
        text = self._format_template(template, ctx)
        return text.strip()

    def _build_context(self, action: Optional[str], state: Optional[Dict]) -> Dict[str, Any]:
        """Build rich context dictionary for template formatting."""
        ctx = {
            "action": self._format_action(action, state),
            "action_raw": action or "waiting",
            "day": 1,
            "season": "Spring",
            "time": "6:00am",
            "hour": 6,
            "energy_pct": 100,
            "energy_word": "full",
            "weather": "sunny",
            "location": "Farm",
            "tool": "nothing",
            "crop_count": 0,
            "planted_today": self._session_crops_planted,
            "watered_today": self._session_crops_watered,
            "cleared_today": self._session_debris_cleared,
            "nth": self._ordinal(self._action_counts.get(action, 1) if action else 1),
            "count": self._action_counts.get(action, 1) if action else 1,
        }

        if not state:
            return ctx

        # Time info
        time_data = state.get("time") or {}
        ctx["day"] = time_data.get("day") or state.get("day") or 1
        ctx["season"] = time_data.get("season") or state.get("season") or "Spring"
        ctx["time"] = time_data.get("time") or "6:00am"
        ctx["hour"] = time_data.get("hour") or 6
        ctx["weather"] = (time_data.get("weather") or state.get("weather") or "sunny").lower()

        # Player info
        player = state.get("player") or {}
        energy = player.get("energy") or 100
        max_energy = player.get("maxEnergy") or player.get("max_energy") or 100
        ctx["energy_pct"] = int((energy / max_energy) * 100) if max_energy > 0 else 100
        ctx["energy_word"] = self._energy_word(ctx["energy_pct"])
        ctx["tool"] = player.get("currentTool") or "nothing"
        ctx["location"] = state.get("location") or player.get("location") or "Farm"

        # Crop info
        crops = state.get("crops") or []
        ctx["crop_count"] = len(crops) if isinstance(crops, list) else 0

        # Stats from rusty memory
        stats = state.get("stats") or {}
        ctx["total_harvested"] = stats.get("crops_harvested_count") or 0
        ctx["total_planted"] = stats.get("crops_planted_count") or 0

        return ctx

    def _update_session_stats(self, action: str) -> None:
        """Track session-level stats for commentary variety."""
        action_lower = action.lower() if action else ""
        if "plant" in action_lower:
            self._session_crops_planted += 1
        elif "water" in action_lower:
            self._session_crops_watered += 1
        elif "clear" in action_lower:
            self._session_debris_cleared += 1

    def _select_tag(self, action: Optional[str], state: Optional[Dict], ctx: Dict) -> str:
        """Select template tag based on context."""
        if not state:
            return "action" if action else "idle"

        # Priority checks
        if ctx["weather"] == "rainy":
            return "rain"
        if ctx["hour"] >= 22:
            return "late"
        if ctx["energy_pct"] <= 25:
            return "low_energy"

        # Farm plan active?
        farm_plan = state.get("farm_plan") or {}
        if farm_plan.get("active"):
            return "farm_plan"

        # Milestone check
        milestone = self._detect_milestone(state, ctx)
        if milestone:
            self._last_milestone = milestone
            return "milestone"

        # Action-specific tags
        if action:
            action_lower = action.lower()
            if "plant" in action_lower:
                return "planting"
            if "water" in action_lower:
                return "watering"
            if "harvest" in action_lower:
                return "harvesting"
            if "clear" in action_lower or "till" in action_lower:
                return "clearing"
            if "move" in action_lower:
                return "moving"
            if "bed" in action_lower or "sleep" in action_lower:
                return "bedtime"

        if not action or action == "wait":
            return "idle"

        return "action"

    def _detect_milestone(self, state: Dict, ctx: Dict) -> Optional[str]:
        """Detect milestone events."""
        stats = state.get("stats") or {}
        harvested = stats.get("crops_harvested_count") or state.get("crops_harvested_count")
        if harvested and harvested != self._last_milestone:
            return f"harvest_{harvested}"

        money = (state.get("player") or {}).get("money")
        if money and money >= 1000 and self._last_milestone != "money_1000":
            return "money_1000"

        # First plant of the day
        if ctx["planted_today"] == 1 and self._last_milestone != "first_plant":
            return "first_plant"

        return None

    def _format_action(self, action: Optional[str], state: Optional[Dict]) -> str:
        """Format action into readable text."""
        if not action:
            return "waiting"

        action_lower = action.replace("_", " ").strip().lower()

        # Specific formatting
        if action_lower == "use tool":
            tool = (state or {}).get("player", {}).get("currentTool") or "tool"
            return f"using the {tool}"
        if "plant" in action_lower:
            return "planting seeds"
        if "water" in action_lower:
            return "watering crops"
        if "harvest" in action_lower:
            return "harvesting"
        if "clear_weeds" in action_lower:
            return "clearing weeds"
        if "clear_stone" in action_lower:
            return "breaking stones"
        if "clear_wood" in action_lower:
            return "chopping wood"
        if "till" in action_lower:
            return "tilling soil"
        if action_lower == "move":
            return "moving"

        return action_lower

    def _format_template(self, template: str, ctx: Dict[str, Any]) -> str:
        """Safely format template with context."""
        try:
            return template.format(**ctx)
        except KeyError:
            # Fallback for missing keys
            return template.format(action=ctx.get("action", "farming"))

    def _energy_word(self, pct: int) -> str:
        """Convert energy percentage to word."""
        if pct >= 80:
            return "full"
        if pct >= 50:
            return "good"
        if pct >= 25:
            return "low"
        return "exhausted"

    def _ordinal(self, n: int) -> str:
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
        if 11 <= (n % 100) <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    def reset_session_stats(self) -> None:
        """Reset session stats (call at start of new day)."""
        self._session_crops_planted = 0
        self._session_crops_watered = 0
        self._session_debris_cleared = 0
        self._action_counts.clear()
