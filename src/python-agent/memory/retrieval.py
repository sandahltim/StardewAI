"""
Combined memory retrieval for VLM prompt injection.
Pulls from both game knowledge (SQLite) and episodic memory (ChromaDB).
"""
import logging
from typing import Any, Dict, List, Optional

from .episodic import get_memory
from .game_knowledge import get_npc_info, get_crop_info

logger = logging.getLogger(__name__)


def get_context_for_vlm(
    location: str = "",
    nearby_npcs: Optional[List[str]] = None,
    current_goal: str = "",
    game_day: str = "",
    n_memories: int = 3
) -> str:
    """
    Get relevant context to inject into VLM prompt.

    Combines:
    - Game knowledge (NPC preferences, crop info)
    - Episodic memories (past experiences)

    Returns formatted string for prompt injection.
    """
    sections = []

    # Game knowledge for nearby NPCs
    if nearby_npcs:
        npc_info_parts = []
        for npc_name in nearby_npcs[:3]:  # Limit to 3 NPCs
            info = get_npc_info(npc_name)
            if info:
                loved = info.get("loved_gifts", [])[:3]  # Top 3 loved gifts
                liked = info.get("liked_gifts", [])[:2]  # Top 2 liked
                hated = info.get("hated_gifts", [])[:2]  # Top 2 hated

                parts = [f"{npc_name}"]
                if loved:
                    parts.append(f"loves: {', '.join(loved)}")
                if liked:
                    parts.append(f"likes: {', '.join(liked)}")
                if hated:
                    parts.append(f"hates: {', '.join(hated)}")

                # Check if today is their birthday
                birthday = info.get("birthday", "")
                if birthday and game_day and birthday.lower() in game_day.lower():
                    parts.append("🎂 TODAY IS THEIR BIRTHDAY!")

                npc_info_parts.append(" | ".join(parts))

        if npc_info_parts:
            sections.append("NEARBY NPC INFO:\n" + "\n".join(f"- {p}" for p in npc_info_parts))

    # Episodic memories
    memory = get_memory()
    if memory.count() > 0:
        # Build query from context
        query_parts = []
        if location:
            query_parts.append(location)
        if nearby_npcs:
            query_parts.extend(nearby_npcs[:2])
        if current_goal:
            query_parts.append(current_goal)

        query = " ".join(query_parts) if query_parts else "recent experience"

        memories = memory.query(query, n_results=n_memories)
        if memories:
            memory_texts = []
            for m in memories:
                text = m["text"]
                meta = m.get("metadata", {})
                day = meta.get("game_day", "")
                if day:
                    text = f"[{day}] {text}"
                memory_texts.append(text)

            sections.append("PAST EXPERIENCE:\n" + "\n".join(f"- {t}" for t in memory_texts))

    if not sections:
        return ""

    return "\n\n".join(sections)


def format_memory_for_storage(
    action: str,
    result: str,
    location: str,
    npc: Optional[str] = None,
    item: Optional[str] = None,
    reasoning: str = ""
) -> str:
    """Format an action result into a natural language memory."""
    parts = []

    if npc:
        if "gave" in action.lower() or "gift" in action.lower():
            parts.append(f"Gave {item or 'something'} to {npc}.")
        elif "talk" in action.lower():
            parts.append(f"Talked to {npc}.")
        else:
            parts.append(f"Interacted with {npc}.")

        if "love" in result.lower():
            parts.append("They loved it!")
        elif "like" in result.lower():
            parts.append("They liked it.")
        elif "hate" in result.lower() or "dislike" in result.lower():
            parts.append("They didn't like it.")
    else:
        parts.append(f"{action} at {location}.")
        if result:
            parts.append(f"Result: {result}")

    return " ".join(parts)
