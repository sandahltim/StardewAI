from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InventoryItem:
    slot: int
    name: str
    stack: int
    category: str  # "tool", "seed", "crop", "resource", etc.


class InventoryManager:
    """
    Manages inventory slot lookups and tool/item organization.
    Pure state reader - no side effects.
    """

    TOOL_SLOTS = {
        "Axe": 0,
        "Hoe": 1,
        "Watering Can": 2,
        "Pickaxe": 3,
        "Scythe": 4,
    }

    _TOOL_NAMES = {name.lower(): name for name in TOOL_SLOTS}

    def __init__(self, inventory: List[Optional[Dict[str, Any]]]):
        """Parse inventory from SMAPI /state response."""
        self.items: List[Optional[InventoryItem]] = []
        self._parse(inventory)

    def _parse(self, inventory: List[Optional[Dict[str, Any]]]) -> None:
        self.items = [None] * len(inventory)
        for slot, entry in enumerate(inventory):
            if not entry:
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            stack = int(entry.get("stack") or 1)
            category = self._categorize(entry, name)
            self.items[slot] = InventoryItem(
                slot=slot,
                name=name,
                stack=stack,
                category=category,
            )

    def _categorize(self, entry: Dict[str, Any], name: str) -> str:
        raw_category = entry.get("category")
        if isinstance(raw_category, str) and raw_category.strip():
            return raw_category.strip().lower()
        lower = name.lower()
        if "seed" in lower or name == "Mixed Seeds":
            return "seed"
        if lower in self._TOOL_NAMES or any(tool in lower for tool in self._TOOL_NAMES):
            return "tool"
        if entry.get("type"):
            return str(entry.get("type")).lower()
        return "resource"

    def find_item(self, name: str) -> Optional[int]:
        """Find slot containing item by name (case-insensitive partial match)."""
        if not name:
            return None
        needle = name.lower()
        for item in self.items:
            if not item:
                continue
            if needle in item.name.lower():
                return item.slot
        return None

    def find_seeds(self) -> List[Tuple[int, str, int]]:
        """Find all seed items. Returns [(slot, name, stack), ...]"""
        seeds: List[Tuple[int, str, int]] = []
        for item in self.items:
            if not item:
                continue
            if item.category == "seed":
                seeds.append((item.slot, item.name, item.stack))
        return seeds

    def find_tool(self, tool_name: str) -> Optional[int]:
        """Find slot for a specific tool."""
        if not tool_name:
            return None
        needle = tool_name.lower()
        for item in self.items:
            if not item:
                continue
            if item.category != "tool":
                continue
            if needle in item.name.lower():
                return item.slot
        return None

    def get_seed_priority(self) -> Optional[Tuple[int, str]]:
        """Get (slot, name) of highest-priority seed to plant."""
        seeds = self.find_seeds()
        if not seeds:
            return None
        priorities = ["parsnip", "potato", "cauliflower"]
        for name in priorities:
            matching = [seed for seed in seeds if name in seed[1].lower()]
            if matching:
                slot, seed_name, _stack = max(matching, key=lambda s: s[2])
                return slot, seed_name
        slot, seed_name, _stack = max(seeds, key=lambda s: s[2])
        return slot, seed_name

    def total_seeds(self) -> int:
        """Count total seeds across all slots."""
        return sum(stack for _slot, _name, stack in self.find_seeds())

    def get_tool_mapping(self) -> Dict[str, int]:
        """Build actual tool→slot mapping from current inventory."""
        mapping: Dict[str, int] = {}
        for tool_name in self.TOOL_SLOTS:
            slot = self.find_tool(tool_name)
            if slot is not None:
                mapping[tool_name] = slot
        return mapping
