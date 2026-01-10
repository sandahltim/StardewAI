"""
Lesson Memory - Learn from failures and successful corrections.

The VLM makes mistakes (blocked paths, wrong tool, etc.). This module tracks
what failed and what worked, feeding lessons back to future VLM calls.

Example lesson:
  "west from porch → blocked by farmhouse → went south first"
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default UI server URL
DEFAULT_UI_URL = "http://localhost:9001"


class LessonMemory:
    """Track mistakes and successful corrections for VLM learning."""

    def __init__(self, persist_path: Optional[str] = None, ui_url: Optional[str] = None):
        """
        Initialize lesson memory.

        Args:
            persist_path: Path to JSON file for persistence.
                         Defaults to logs/lessons.json
            ui_url: URL of UI server for real-time notifications.
                   Defaults to http://localhost:9001
        """
        self.lessons: list[dict] = []
        self.session_count = 0

        if persist_path is None:
            persist_path = "logs/lessons.json"
        self.persist_path = Path(persist_path)

        self.ui_url = ui_url or DEFAULT_UI_URL

        # Load existing lessons if file exists
        self._load()

    def record_failure(
        self,
        attempted: str,
        blocked_by: str,
        position: Optional[tuple[int, int]] = None,
        location: Optional[str] = None,
    ) -> int:
        """
        Record a failed action attempt.

        Args:
            attempted: What the VLM tried to do (e.g., "move west")
            blocked_by: What blocked it (e.g., "farmhouse", "water")
            position: Optional (x, y) tile position
            location: Optional location name (e.g., "Farm")

        Returns:
            Lesson ID for later updating with recovery
        """
        lesson = {
            "id": len(self.lessons),
            "attempted": attempted,
            "blocked_by": blocked_by,
            "position": position,
            "location": location,
            "recovery": None,
            "timestamp": datetime.now().isoformat(),
            "applied_count": 0,
        }
        self.lessons.append(lesson)
        self.session_count += 1

        logger.info(f"Lesson recorded: {attempted} → blocked by {blocked_by}")

        # Persist and notify UI
        self._persist()
        self._notify_ui()

        return lesson["id"]

    def record_recovery(self, lesson_id: int, recovery: str):
        """
        Update a lesson with what worked after the failure.

        Args:
            lesson_id: ID returned from record_failure
            recovery: What action succeeded (e.g., "went south first")
        """
        if 0 <= lesson_id < len(self.lessons):
            self.lessons[lesson_id]["recovery"] = recovery
            logger.info(f"Lesson {lesson_id} updated: → {recovery} worked")
            self._persist()
            self._notify_ui()

    def get_context(self, max_lessons: int = 5) -> str:
        """
        Get lessons formatted for VLM context.

        Args:
            max_lessons: Maximum number of recent lessons to include

        Returns:
            Formatted string of lessons, or empty string if none
        """
        # Get lessons with recoveries (completed lessons are most valuable)
        completed = [l for l in self.lessons if l.get("recovery")]

        # Also include recent failures without recovery (might still be useful)
        pending = [l for l in self.lessons if not l.get("recovery")][-2:]

        # Prioritize completed lessons, then add pending
        relevant = completed[-max_lessons:] + pending
        relevant = relevant[-max_lessons:]  # Trim to max

        if not relevant:
            return ""

        lines = []
        for lesson in relevant:
            # Handle old lesson format gracefully
            attempted = lesson.get("attempted", lesson.get("action", "unknown"))
            blocked = lesson.get("blocked_by", lesson.get("blocker", "unknown"))
            recovery = lesson.get("recovery")

            if not attempted or not blocked:
                continue  # Skip malformed lessons

            if recovery:
                lines.append(f"• {attempted} → blocked by {blocked} → {recovery}")
            else:
                lines.append(f"• {attempted} → blocked by {blocked} (no recovery yet)")

        return "\n".join(lines)

    def get_lesson_for_situation(
        self,
        direction: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Optional[str]:
        """
        Find a relevant lesson for the current situation.

        Args:
            direction: Direction being attempted (e.g., "west")
            location: Current location name

        Returns:
            Relevant lesson string, or None
        """
        for lesson in reversed(self.lessons):
            if not lesson.get("recovery"):
                continue

            # Match by direction if specified
            if direction and direction in lesson["attempted"]:
                return f"{lesson['attempted']} → {lesson['recovery']}"

            # Match by location if specified
            if location and lesson.get("location") == location:
                return f"{lesson['attempted']} → {lesson['recovery']}"

        return None

    def mark_applied(self, lesson_id: int):
        """Mark that a lesson was used in VLM context."""
        if 0 <= lesson_id < len(self.lessons):
            self.lessons[lesson_id]["applied_count"] += 1

    def clear_session(self):
        """Clear lessons from current session (keep persistent ones)."""
        self.session_count = 0
        # Could filter by timestamp to keep only older lessons
        # For now, just reset the counter
        logger.info("Session lessons cleared")

    def clear_all(self):
        """Clear all lessons."""
        self.lessons = []
        self.session_count = 0
        self._persist()
        logger.info("All lessons cleared")

    def get_stats(self) -> dict:
        """Get lesson statistics."""
        completed = sum(1 for l in self.lessons if l.get("recovery"))
        return {
            "total": len(self.lessons),
            "completed": completed,
            "pending": len(self.lessons) - completed,
            "session_count": self.session_count,
            "applied_total": sum(l.get("applied_count", 0) for l in self.lessons),
        }

    def _load(self):
        """Load lessons from persistence file."""
        if self.persist_path.exists():
            try:
                with open(self.persist_path) as f:
                    data = json.load(f)
                self.lessons = data.get("lessons", [])
                logger.info(f"Loaded {len(self.lessons)} lessons from {self.persist_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load lessons: {e}")
                self.lessons = []

    def _persist(self):
        """Save lessons to persistence file."""
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_path, "w") as f:
                json.dump({"lessons": self.lessons}, f, indent=2)
        except IOError as e:
            logger.warning(f"Could not persist lessons: {e}")

    def _notify_ui(self):
        """Notify UI server of lesson update via POST."""
        try:
            url = f"{self.ui_url}/api/lessons/update"
            payload = self.to_api_format()
            response = requests.post(url, json=payload, timeout=1.0)
            if response.status_code == 200:
                logger.debug(f"UI notified of lesson update")
            else:
                logger.debug(f"UI notification failed: {response.status_code}")
        except requests.RequestException as e:
            # UI might not be running - don't spam warnings
            logger.debug(f"Could not notify UI: {e}")

    def to_api_format(self) -> dict:
        """Format for API response (used by UI)."""
        return {
            "lessons": [
                {
                    "id": l["id"],
                    "text": self._format_lesson(l),
                    "has_recovery": bool(l.get("recovery")),
                    "applied_count": l.get("applied_count", 0),
                }
                for l in self.lessons[-10:]  # Last 10 for UI
            ],
            "count": self.session_count,
            "stats": self.get_stats(),
        }

    def _format_lesson(self, lesson: dict) -> str:
        """Format a single lesson for display."""
        # Handle old lesson format gracefully
        attempted = lesson.get("attempted", lesson.get("action", "unknown"))
        blocked = lesson.get("blocked_by", lesson.get("blocker", "unknown"))
        recovery = lesson.get("recovery")

        if not attempted or not blocked:
            return "malformed lesson"

        if recovery:
            return f"{attempted} → blocked by {blocked} → {recovery}"
        return f"{attempted} → blocked by {blocked}"


# Singleton instance for easy access
_lesson_memory: Optional[LessonMemory] = None


def get_lesson_memory() -> LessonMemory:
    """Get or create the singleton LessonMemory instance."""
    global _lesson_memory
    if _lesson_memory is None:
        _lesson_memory = LessonMemory()
    return _lesson_memory
