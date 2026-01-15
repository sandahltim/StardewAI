"""
Rusty Memory - Character persistence across sessions.

Rusty is a self-aware AI farmer. This module tracks:
- Episodic memory: What happened (events, actions, outcomes)
- Character state: Mood, confidence, growth over time
- NPC relationships: Who Rusty knows and how they interact

Without this, Rusty forgets everything between sessions - personality exists
but no continuity. This gives Rusty a past.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_UI_URL = "http://localhost:9001"
DEFAULT_PERSIST_PATH = "logs/rusty_state.json"


class RustyMemory:
    """Character memory persistence for Rusty the AI farmer."""

    def __init__(
        self,
        persist_path: Optional[str] = None,
        ui_url: Optional[str] = None,
    ):
        """
        Initialize Rusty's memory.

        Args:
            persist_path: Path to JSON file for persistence.
            ui_url: URL of UI server for real-time notifications.
        """
        self.persist_path = Path(persist_path or DEFAULT_PERSIST_PATH)
        self.ui_url = ui_url or DEFAULT_UI_URL

        # Episodic memory - recent events
        self.episodic: List[Dict[str, Any]] = []

        # NPC relationships - name -> relationship data
        self.relationships: Dict[str, Dict[str, Any]] = {}

        # Character state - Rusty's internal state
        self.character_state: Dict[str, Any] = {
            "confidence": 0.5,  # 0.0 to 1.0
            "mood": "neutral",  # neutral, content, frustrated, tired, proud, curious
            "days_farming": 0,
            "total_harvests": 0,
            "total_failures": 0,
            "favorite_activities": [],  # Discovered through success
            "current_concerns": [],  # Active worries or goals
            "memorable_moments": [],  # High-impact events to reference
        }

        # Session tracking
        self.session_start: Optional[str] = None
        self.current_day: int = 0
        self.current_season: str = "spring"

        # Load existing state
        self._load()

    # ─────────────────────────────────────────────────────────────────
    # Episodic Memory
    # ─────────────────────────────────────────────────────────────────

    def record_event(
        self,
        event_type: str,
        description: str,
        outcome: str = "neutral",
        importance: int = 1,
        location: Optional[str] = None,
        npc: Optional[str] = None,
    ) -> None:
        """
        Record something that happened.

        Args:
            event_type: Category (action, harvest, meeting, failure, discovery, etc.)
            description: What happened in plain language
            outcome: "success", "failure", "neutral"
            importance: 1-5 (5 = memorable, 1 = routine)
            location: Where it happened
            npc: NPC involved (if any)
        """
        event = {
            "type": event_type,
            "description": description,
            "outcome": outcome,
            "importance": importance,
            "location": location,
            "npc": npc,
            "day": self.current_day,
            "season": self.current_season,
            "timestamp": datetime.now().isoformat(),
        }

        self.episodic.append(event)

        # Update character state based on outcome
        if outcome == "success":
            self._adjust_confidence(0.02 * importance)
            self.character_state["total_harvests"] += 1 if event_type == "harvest" else 0
        elif outcome == "failure":
            self._adjust_confidence(-0.03 * importance)
            self.character_state["total_failures"] += 1

        # High importance events become memorable moments
        if importance >= 4:
            self._add_memorable_moment(description)

        # Track NPC interaction
        if npc:
            self.record_npc_interaction(npc, event_type, outcome)

        # Trim old events (keep last 100)
        if len(self.episodic) > 100:
            self.episodic = self.episodic[-100:]

        logger.info(f"Event recorded: {event_type} - {description[:50]}")
        self._persist()

    def get_recent_events(self, count: int = 10, event_type: Optional[str] = None) -> List[Dict]:
        """Get recent events, optionally filtered by type."""
        events = self.episodic
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return events[-count:]

    def get_today_summary(self) -> str:
        """Summarize what happened today."""
        today_events = [
            e for e in self.episodic
            if e["day"] == self.current_day and e["season"] == self.current_season
        ]

        if not today_events:
            return "Nothing notable happened yet today."

        summaries = []
        for e in today_events[-5:]:  # Last 5 events
            summaries.append(e["description"])

        return " | ".join(summaries)

    # ─────────────────────────────────────────────────────────────────
    # Character State
    # ─────────────────────────────────────────────────────────────────

    def _adjust_confidence(self, delta: float) -> None:
        """Adjust confidence within bounds [0.1, 0.95]."""
        new_conf = self.character_state["confidence"] + delta
        self.character_state["confidence"] = max(0.1, min(0.95, new_conf))

    def _add_memorable_moment(self, description: str) -> None:
        """Add to memorable moments (keep last 20)."""
        moments = self.character_state["memorable_moments"]
        moment = {
            "description": description,
            "day": self.current_day,
            "season": self.current_season,
        }
        moments.append(moment)
        if len(moments) > 20:
            self.character_state["memorable_moments"] = moments[-20:]

    def update_mood(self, mood: str, reason: Optional[str] = None) -> None:
        """
        Update Rusty's mood.

        Valid moods: neutral, content, frustrated, tired, proud, curious, anxious
        """
        valid_moods = ["neutral", "content", "frustrated", "tired", "proud", "curious", "anxious"]
        if mood in valid_moods:
            old_mood = self.character_state["mood"]
            self.character_state["mood"] = mood
            if old_mood != mood:
                logger.debug(f"Mood changed: {old_mood} -> {mood}" + (f" ({reason})" if reason else ""))
                self._persist()

    def add_favorite_activity(self, activity: str) -> None:
        """Add to favorite activities if not already present."""
        favorites = self.character_state["favorite_activities"]
        if activity not in favorites:
            favorites.append(activity)
            if len(favorites) > 10:
                self.character_state["favorite_activities"] = favorites[-10:]
            logger.info(f"New favorite activity: {activity}")
            self._persist()

    def add_concern(self, concern: str) -> None:
        """Add a current concern/goal."""
        concerns = self.character_state["current_concerns"]
        if concern not in concerns:
            concerns.append(concern)
            if len(concerns) > 5:
                self.character_state["current_concerns"] = concerns[-5:]
            self._persist()

    def resolve_concern(self, concern: str) -> None:
        """Remove a resolved concern."""
        concerns = self.character_state["current_concerns"]
        if concern in concerns:
            concerns.remove(concern)
            self._persist()

    def get_confidence_level(self) -> str:
        """Get confidence as a descriptive string."""
        conf = self.character_state["confidence"]
        if conf >= 0.8:
            return "very confident"
        elif conf >= 0.6:
            return "confident"
        elif conf >= 0.4:
            return "somewhat confident"
        elif conf >= 0.2:
            return "uncertain"
        else:
            return "struggling"

    # ─────────────────────────────────────────────────────────────────
    # NPC Relationships
    # ─────────────────────────────────────────────────────────────────

    def record_npc_interaction(
        self,
        npc_name: str,
        interaction_type: str,
        outcome: str = "neutral",
        notes: Optional[str] = None,
    ) -> None:
        """
        Record an interaction with an NPC.

        Args:
            npc_name: NPC's name
            interaction_type: greeting, gift, help, conversation, etc.
            outcome: success, failure, neutral
            notes: Additional context
        """
        if npc_name not in self.relationships:
            self.relationships[npc_name] = {
                "first_met": {
                    "day": self.current_day,
                    "season": self.current_season,
                },
                "interaction_count": 0,
                "positive_interactions": 0,
                "negative_interactions": 0,
                "last_interaction": None,
                "notes": [],
                "friendship_level": "stranger",  # stranger, acquaintance, friend, close_friend
            }

        rel = self.relationships[npc_name]
        rel["interaction_count"] += 1
        rel["last_interaction"] = {
            "type": interaction_type,
            "day": self.current_day,
            "season": self.current_season,
        }

        if outcome == "success":
            rel["positive_interactions"] += 1
        elif outcome == "failure":
            rel["negative_interactions"] += 1

        if notes:
            rel["notes"].append(notes)
            if len(rel["notes"]) > 10:
                rel["notes"] = rel["notes"][-10:]

        # Update friendship level based on interactions
        self._update_friendship_level(npc_name)

        logger.debug(f"NPC interaction: {npc_name} ({interaction_type})")
        self._persist()

    def _update_friendship_level(self, npc_name: str) -> None:
        """Update friendship level based on interaction history."""
        rel = self.relationships.get(npc_name)
        if not rel:
            return

        positive = rel["positive_interactions"]
        total = rel["interaction_count"]

        if total >= 20 and positive >= 15:
            rel["friendship_level"] = "close_friend"
        elif total >= 10 and positive >= 7:
            rel["friendship_level"] = "friend"
        elif total >= 3:
            rel["friendship_level"] = "acquaintance"
        else:
            rel["friendship_level"] = "stranger"

    def get_npc_relationship(self, npc_name: str) -> Optional[Dict[str, Any]]:
        """Get relationship data for an NPC."""
        return self.relationships.get(npc_name)

    def get_known_npcs(self) -> List[str]:
        """Get list of NPCs Rusty has met."""
        return list(self.relationships.keys())

    def get_friendship_context(self, npc_name: str) -> str:
        """Get relationship context for VLM prompt."""
        rel = self.relationships.get(npc_name)
        if not rel:
            return f"I haven't met {npc_name} yet."

        level = rel["friendship_level"]
        interactions = rel["interaction_count"]
        positive = rel["positive_interactions"]

        context = f"{npc_name}: {level} ({interactions} interactions, {positive} positive)"

        if rel["notes"]:
            context += f" - Notes: {rel['notes'][-1]}"

        return context

    # ─────────────────────────────────────────────────────────────────
    # Day/Session Management
    # ─────────────────────────────────────────────────────────────────

    def start_session(self, day: int, season: str) -> None:
        """Start a new session, updating day tracking."""
        self.session_start = datetime.now().isoformat()
        self.current_day = day
        self.current_season = season

        # Check if it's a new day
        if day > 0:
            old_days = self.character_state.get("days_farming", 0)
            # This is simplified - in reality we'd track year too
            self.character_state["days_farming"] = max(old_days, day)

        logger.info(f"Session started: {season} Day {day}")
        self._persist()

    def end_day(self) -> None:
        """Called at end of game day - consolidate memories."""
        # Mood tends toward neutral over time
        current_mood = self.character_state["mood"]
        if current_mood in ["frustrated", "anxious"]:
            self.update_mood("neutral", reason="day ended, mood reset")
        elif current_mood == "proud":
            self.update_mood("content", reason="pride fading to contentment")

        self._persist()

    # ─────────────────────────────────────────────────────────────────
    # Context Generation (for VLM prompts)
    # ─────────────────────────────────────────────────────────────────

    def get_context_for_prompt(self) -> str:
        """
        Generate context string for inclusion in VLM prompt.

        Returns a concise summary of Rusty's state for the AI to use.
        """
        lines = []

        # Character state
        mood = self.character_state["mood"]
        confidence = self.get_confidence_level()
        days = self.character_state["days_farming"]

        lines.append(f"Elias's state: {mood}, {confidence} (Day {days} of farming)")

        # Recent memorable moments
        moments = self.character_state["memorable_moments"]
        if moments:
            recent = moments[-2:]  # Last 2
            lines.append("Recent memories: " + "; ".join(m["description"] for m in recent))

        # Current concerns
        concerns = self.character_state["current_concerns"]
        if concerns:
            lines.append(f"On my mind: {', '.join(concerns)}")

        # Favorites
        favorites = self.character_state["favorite_activities"]
        if favorites:
            lines.append(f"I enjoy: {', '.join(favorites[:3])}")

        return "\n".join(lines)

    def get_npc_context(self, npc_name: str) -> str:
        """Get NPC-specific context for VLM prompt."""
        rel = self.relationships.get(npc_name)
        if not rel:
            return f"I don't know {npc_name} yet - this is our first meeting."

        level = rel["friendship_level"]
        positive = rel["positive_interactions"]
        negative = rel["negative_interactions"]

        if level == "close_friend":
            tone = f"{npc_name} is a close friend. We've had many good interactions."
        elif level == "friend":
            tone = f"{npc_name} is a friend. We get along well."
        elif level == "acquaintance":
            tone = f"I know {npc_name} a bit. We've talked a few times."
        else:
            tone = f"I barely know {npc_name}."

        if negative > positive:
            tone += " Things have been rocky though."
        elif positive > 5:
            tone += " They seem to like me."

        return tone

    # ─────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load state from persistence file."""
        if not self.persist_path.exists():
            logger.info("No existing Rusty memory found, starting fresh")
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            self.episodic = data.get("episodic", [])
            self.relationships = data.get("relationships", {})
            self.character_state = {
                **self.character_state,  # Defaults
                **data.get("character_state", {}),  # Saved values
            }
            self.current_day = data.get("current_day", 0)
            self.current_season = data.get("current_season", "spring")

            logger.info(
                f"Loaded Rusty memory: {len(self.episodic)} events, "
                f"{len(self.relationships)} NPCs, "
                f"Day {self.current_day} {self.current_season}"
            )
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load Rusty memory: {e}")

    def _persist(self) -> None:
        """Save state to persistence file."""
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "episodic": self.episodic,
                "relationships": self.relationships,
                "character_state": self.character_state,
                "current_day": self.current_day,
                "current_season": self.current_season,
                "last_saved": datetime.now().isoformat(),
            }

            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)

        except IOError as e:
            logger.warning(f"Could not persist Rusty memory: {e}")

    def _notify_ui(self) -> None:
        """Notify UI server of memory update (if endpoint exists)."""
        try:
            url = f"{self.ui_url}/api/rusty/memory"
            payload = self.to_api_format()
            response = requests.post(url, json=payload, timeout=1.0)
            if response.status_code == 200:
                logger.debug("UI notified of memory update")
        except requests.RequestException:
            # UI might not have this endpoint yet - that's fine
            pass

    def to_api_format(self) -> Dict[str, Any]:
        """Format for API response (used by UI)."""
        return {
            "character_state": self.character_state,
            "recent_events": self.episodic[-10:],
            "known_npcs": list(self.relationships.keys()),
            "relationship_count": len(self.relationships),
            "context": self.get_context_for_prompt(),
        }


# ─────────────────────────────────────────────────────────────────
# Singleton with auto-refresh
# ─────────────────────────────────────────────────────────────────

_rusty_memory: Optional[RustyMemory] = None
_rusty_last_mtime: float = 0


def get_rusty_memory() -> RustyMemory:
    """Get or create the singleton RustyMemory instance.

    Auto-refreshes from disk if the file has been modified by another process
    (e.g., agent writes new memory, UI server needs to see it).
    """
    global _rusty_memory, _rusty_last_mtime

    persist_path = Path(DEFAULT_PERSIST_PATH)

    # Check if file has been modified since last load
    if persist_path.exists():
        current_mtime = persist_path.stat().st_mtime
        if _rusty_memory is not None and current_mtime > _rusty_last_mtime:
            logger.info(f"🧠 Rusty memory file changed, reloading...")
            _rusty_memory._load()
            _rusty_last_mtime = current_mtime

    if _rusty_memory is None:
        _rusty_memory = RustyMemory()
        if persist_path.exists():
            _rusty_last_mtime = persist_path.stat().st_mtime

    return _rusty_memory
