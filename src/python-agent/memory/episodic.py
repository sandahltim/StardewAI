"""
Episodic memory for Rusty using ChromaDB.
Stores personal experiences - things learned by doing.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

# Store ChromaDB data in project data directory
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "chromadb"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Memory types that should always be stored
ALWAYS_REMEMBER = [
    "npc_interaction",  # Any NPC gift/talk
    "item_obtained",    # New item types
    "location_first",   # First visit to area
    "death",            # Always remember deaths
    "tool_upgrade",     # Tool improvements
]

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """ChromaDB-backed episodic memory for game experiences."""

    def __init__(self, collection_name: str = "rusty_memories"):
        """Initialize ChromaDB client and collection."""
        self.client = chromadb.PersistentClient(
            path=str(DATA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Rusty's episodic memories from Stardew Valley"}
        )
        logger.info(f"EpisodicMemory initialized with {self.collection.count()} memories")

    def store(
        self,
        text: str,
        memory_type: str,
        location: str = "",
        npc: str = "",
        item: str = "",
        outcome: str = "",
        game_day: str = "",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a new memory.

        Args:
            text: Natural language description of the experience
            memory_type: One of npc_interaction, discovery, task_result, death, notable
            location: Game location where this happened
            npc: NPC involved (if any)
            item: Item involved (if any)
            outcome: positive, negative, neutral
            game_day: In-game day (e.g., "Spring 5 Y1")
            extra_metadata: Additional metadata

        Returns:
            Memory ID
        """
        memory_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        metadata = {
            "type": memory_type,
            "location": location,
            "npc": npc,
            "item": item,
            "outcome": outcome,
            "game_day": game_day,
            "timestamp": datetime.now().isoformat(),
        }

        if extra_metadata:
            metadata.update(extra_metadata)

        # Filter out empty values for cleaner storage
        metadata = {k: v for k, v in metadata.items() if v}

        self.collection.add(
            ids=[memory_id],
            documents=[text],
            metadatas=[metadata]
        )

        logger.debug(f"Stored memory {memory_id}: {text[:50]}...")
        return memory_id

    def query(
        self,
        query_text: str,
        n_results: int = 3,
        memory_type: Optional[str] = None,
        location: Optional[str] = None,
        npc: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query for relevant memories.

        Args:
            query_text: Search query (semantic search)
            n_results: Number of results to return
            memory_type: Filter by memory type
            location: Filter by location
            npc: Filter by NPC

        Returns:
            List of memories with text, metadata, and distance
        """
        where_filter = {}
        if memory_type:
            where_filter["type"] = memory_type
        if location:
            where_filter["location"] = location
        if npc:
            where_filter["npc"] = npc

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter if where_filter else None
        )

        memories = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "id": results["ids"][0][i] if results["ids"] else None
                })

        return memories

    def get_recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get most recent memories (by timestamp)."""
        # ChromaDB doesn't have built-in sorting, so we get all and sort
        all_results = self.collection.get(
            include=["documents", "metadatas"]
        )

        if not all_results["ids"]:
            return []

        memories = []
        for i, mem_id in enumerate(all_results["ids"]):
            memories.append({
                "id": mem_id,
                "text": all_results["documents"][i],
                "metadata": all_results["metadatas"][i] if all_results["metadatas"] else {}
            })

        # Sort by timestamp descending
        memories.sort(
            key=lambda m: m["metadata"].get("timestamp", ""),
            reverse=True
        )

        return memories[:n]

    def count(self) -> int:
        """Return total number of memories."""
        return self.collection.count()

    def clear(self):
        """Clear all memories (use with caution!)."""
        # Delete and recreate collection
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.create_collection(
            name="rusty_memories",
            metadata={"description": "Rusty's episodic memories from Stardew Valley"}
        )
        logger.warning("All episodic memories cleared")


# Singleton instance for easy access
_memory: Optional[EpisodicMemory] = None


def get_memory() -> EpisodicMemory:
    """Get or create the singleton EpisodicMemory instance."""
    global _memory
    if _memory is None:
        _memory = EpisodicMemory()
    return _memory


def should_remember(memory_type: str, outcome: str = "", reasoning: str = "") -> bool:
    """
    Determine if an experience should be stored.

    Auto-store for ALWAYS_REMEMBER types.
    Conditional store if VLM reasoning suggests importance.
    """
    if memory_type in ALWAYS_REMEMBER:
        return True

    if outcome in ["negative", "failed"]:
        return True

    # Check if VLM marked as important
    importance_markers = ["remember this", "notable", "important", "first time"]
    reasoning_lower = reasoning.lower()
    if any(marker in reasoning_lower for marker in importance_markers):
        return True

    return False
