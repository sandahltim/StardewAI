"""
Obstacle Manager - Tool-aware obstacle clearing system.

Centralizes all obstacle/tool logic so pathfinding, batch watering, and
other systems use consistent rules for what can be cleared.

Usage:
    from planning.obstacle_manager import can_clear_obstacle, get_tool_level, OBSTACLE_REQUIREMENTS

    can_clear, reason, skill = can_clear_obstacle(inventory, "Stump")
    # Returns: (False, "needs Copper Axe (have Basic)", None)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# =============================================================================
# Tool Upgrade Levels
# =============================================================================
TOOL_LEVELS = {
    0: "Basic",
    1: "Copper",
    2: "Steel",
    3: "Gold",
    4: "Iridium"
}

# =============================================================================
# Obstacle Requirements
# =============================================================================
# Maps obstacle types to (tool_type, min_upgrade_level, clear_skill)
# tool_type: Name of tool needed (Axe, Pickaxe, Scythe, etc.)
# min_upgrade_level: 0=Basic, 1=Copper, 2=Steel, 3=Gold, 4=Iridium
# clear_skill: Skill name to use, or None if no quick-clear available

OBSTACLE_REQUIREMENTS: Dict[str, Tuple[Optional[str], int, Optional[str]]] = {
    # ===================
    # Basic tool obstacles (level 0) - can clear with starter tools
    # ===================
    "Weeds": ("Scythe", 0, "clear_weeds"),
    "Fiber": ("Scythe", 0, "clear_weeds"),
    "Grass": ("Scythe", 0, "clear_weeds"),
    "Twig": ("Axe", 0, "clear_wood"),
    "Wood": ("Axe", 0, "clear_wood"),
    "Stone": ("Pickaxe", 0, "clear_stone"),

    # ===================
    # Copper tool obstacles (level 1)
    # ===================
    "Stump": ("Axe", 1, None),           # Large stump - needs Copper Axe
    "Boulder": ("Pickaxe", 1, None),     # Large boulder - needs Copper Pickaxe

    # ===================
    # Steel tool obstacles (level 2)
    # ===================
    "Hardwood Stump": ("Axe", 2, None),  # Hardwood stump
    "Log": ("Axe", 2, None),             # Large log blocking path
    "Large Rock": ("Pickaxe", 2, None),  # Large rock/meteorite
    "Meteorite": ("Pickaxe", 3, None),   # Meteorite needs Gold pickaxe

    # ===================
    # Trees (special case - can clear but takes many hits)
    # ===================
    "Tree": ("Axe", 0, None),            # Can chop but slow, skip in batch ops
    "FruitTree": (None, 99, None),       # Cannot be chopped

    # ===================
    # Impassable terrain (no tool can clear)
    # ===================
    "wall": (None, 99, None),
    "water": (None, 99, None),
    "map_edge": (None, 99, None),
    "Cliff": (None, 99, None),
    "Bush": (None, 99, None),
    "Building": (None, 99, None),
    "Farmhouse": (None, 99, None),
    "Barn": (None, 99, None),
    "Coop": (None, 99, None),
    "Silo": (None, 99, None),
    "Well": (None, 99, None),

    # ===================
    # Decorative/special tiles (skip, don't try to clear)
    # ===================
    "Path": (None, 99, None),           # Decorative paths - don't clear
    "Flooring": (None, 99, None),       # Decorative flooring
    "GrassTile": (None, 99, None),      # Animal grass - leave for animals
    "Fence": (None, 99, None),          # Player-placed fences
    "Gate": (None, 99, None),           # Player-placed gates
    "Sprinkler": (None, 99, None),      # Don't clear sprinklers!
    "Scarecrow": (None, 99, None),      # Don't clear scarecrows
}

# Quick lookup sets for common checks
IMPASSABLE_OBSTACLES = {
    name for name, (tool, level, _) in OBSTACLE_REQUIREMENTS.items()
    if tool is None or level >= 99
}

BASIC_CLEARABLE = {
    name for name, (tool, level, skill) in OBSTACLE_REQUIREMENTS.items()
    if tool is not None and level == 0 and skill is not None
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_tool_level(inventory: List[Dict[str, Any]], tool_type: str) -> int:
    """
    Get upgrade level of a tool from inventory.

    Args:
        inventory: List of inventory items from game state
        tool_type: Tool name to find (e.g., "Axe", "Pickaxe")

    Returns:
        Upgrade level (0-4), or -1 if tool not found
    """
    if not inventory:
        return -1

    tool_type_lower = tool_type.lower()
    for item in inventory:
        if item and item.get("type") == "tool":
            name = item.get("name", "").lower()
            # Match tool type (e.g., "axe" in "Copper Axe")
            if tool_type_lower in name:
                return item.get("quality", 0)
    return -1


def get_tool_level_name(level: int) -> str:
    """Get human-readable name for tool level."""
    return TOOL_LEVELS.get(level, f"level {level}")


def can_clear_obstacle(inventory: List[Dict[str, Any]], obstacle: str) -> Tuple[bool, str, Optional[str]]:
    """
    Check if agent can clear an obstacle with current tools.

    Args:
        inventory: List of inventory items from game state
        obstacle: Name of the obstacle (e.g., "Stump", "Stone", "wall")

    Returns:
        Tuple of (can_clear, reason, skill_name):
        - can_clear: True if obstacle can be cleared
        - reason: Human-readable explanation
        - skill_name: Skill to use for clearing, or None

    Examples:
        >>> can_clear_obstacle(inv, "Stone")
        (True, "can clear", "clear_stone")

        >>> can_clear_obstacle(inv, "Stump")  # with basic axe
        (False, "needs Copper Axe (have Basic)", None)

        >>> can_clear_obstacle(inv, "water")
        (False, "impassable terrain", None)
    """
    if not obstacle:
        return (False, "no obstacle specified", None)

    # Look up requirements
    req = OBSTACLE_REQUIREMENTS.get(obstacle)
    if not req:
        # Unknown obstacle - log and assume can't clear
        logger.debug(f"Unknown obstacle type: {obstacle}")
        return (False, f"unknown obstacle: {obstacle}", None)

    tool_type, min_level, skill = req

    # Check if it's impassable terrain
    if tool_type is None:
        return (False, "impassable terrain", None)

    # Check if we have the tool
    current_level = get_tool_level(inventory, tool_type)
    if current_level < 0:
        return (False, f"no {tool_type} in inventory", None)

    # Check if tool is upgraded enough
    if current_level < min_level:
        needed = get_tool_level_name(min_level)
        have = get_tool_level_name(current_level)
        return (False, f"needs {needed} {tool_type} (have {have})", None)

    # Can clear!
    return (True, "can clear", skill)


def get_required_upgrade(obstacle: str) -> Optional[Tuple[str, int]]:
    """
    Get the tool upgrade needed to clear an obstacle.

    Args:
        obstacle: Name of the obstacle

    Returns:
        Tuple of (tool_type, min_level) or None if impassable
    """
    req = OBSTACLE_REQUIREMENTS.get(obstacle)
    if not req or req[0] is None:
        return None
    return (req[0], req[1])


def is_quick_clearable(obstacle: str, inventory: List[Dict[str, Any]]) -> bool:
    """
    Check if obstacle can be quickly cleared (has a skill and we have the tool).
    Used for batch operations where we only want to clear simple debris.
    """
    can_clear, _, skill = can_clear_obstacle(inventory, obstacle)
    return can_clear and skill is not None


def classify_blocker(blocker: str, inventory: List[Dict[str, Any]]) -> str:
    """
    Classify a blocker for pathfinding decisions.

    Returns one of:
        - "clear": Can quickly clear with skill
        - "slow_clear": Can clear but takes time (trees)
        - "upgrade_needed": Need better tools
        - "impassable": Cannot clear ever
        - "unknown": Unrecognized blocker
    """
    if not blocker:
        return "unknown"

    req = OBSTACLE_REQUIREMENTS.get(blocker)
    if not req:
        return "unknown"

    tool_type, min_level, skill = req

    if tool_type is None:
        return "impassable"

    current_level = get_tool_level(inventory, tool_type)

    if current_level < min_level:
        return "upgrade_needed"

    if skill:
        return "clear"
    else:
        return "slow_clear"


# =============================================================================
# Pathfinding Integration
# =============================================================================

def should_path_around(blocker: str, inventory: List[Dict[str, Any]], allow_slow_clear: bool = False) -> bool:
    """
    Determine if pathfinding should go around an obstacle rather than through it.

    Args:
        blocker: The obstacle name
        inventory: Current inventory
        allow_slow_clear: If True, will attempt to clear trees/stumps even if slow

    Returns:
        True if should path around, False if should attempt to clear
    """
    classification = classify_blocker(blocker, inventory)

    if classification in ("impassable", "upgrade_needed", "unknown"):
        return True

    if classification == "slow_clear" and not allow_slow_clear:
        return True

    return False


def get_blocking_info(blocker: str, inventory: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get detailed information about why something is blocking.
    Useful for VLM prompts and debugging.

    Returns dict with:
        - blocker: Original blocker name
        - classification: clear/slow_clear/upgrade_needed/impassable/unknown
        - can_clear: Boolean
        - reason: Human-readable explanation
        - skill: Skill to use if clearable
        - upgrade_hint: What upgrade would help (if applicable)
    """
    can_clear, reason, skill = can_clear_obstacle(inventory, blocker)
    classification = classify_blocker(blocker, inventory)

    result = {
        "blocker": blocker,
        "classification": classification,
        "can_clear": can_clear,
        "reason": reason,
        "skill": skill,
        "upgrade_hint": None
    }

    # Add upgrade hint if applicable
    if classification == "upgrade_needed":
        upgrade = get_required_upgrade(blocker)
        if upgrade:
            tool, level = upgrade
            result["upgrade_hint"] = f"Upgrade {tool} to {get_tool_level_name(level)}"

    return result


# =============================================================================
# Tool Upgrade Tracking
# =============================================================================

class UpgradeTracker:
    """
    Tracks when tools need upgrading based on repeated blocking encounters.

    Usage:
        tracker = UpgradeTracker()
        tracker.record_blocked("Stump", inventory)  # When blocked by obstacle

        if tracker.should_suggest_upgrade("Axe"):
            goal = tracker.get_upgrade_goal("Axe")  # "Upgrade Axe to Copper"
    """

    def __init__(self, threshold: int = 5):
        """
        Args:
            threshold: Number of times blocked before suggesting upgrade
        """
        self.threshold = threshold
        self._blocked_counts: Dict[str, int] = {}  # tool_type -> blocked count
        self._suggested_upgrades: set = set()  # Already suggested upgrades

    def record_blocked(self, blocker: str, inventory: List[Dict[str, Any]]) -> Optional[str]:
        """
        Record being blocked by an obstacle that needs a tool upgrade.

        Returns:
            Upgrade suggestion if threshold reached, None otherwise
        """
        classification = classify_blocker(blocker, inventory)
        if classification != "upgrade_needed":
            return None

        upgrade = get_required_upgrade(blocker)
        if not upgrade:
            return None

        tool_type, min_level = upgrade
        self._blocked_counts[tool_type] = self._blocked_counts.get(tool_type, 0) + 1

        count = self._blocked_counts[tool_type]
        logger.debug(f"Blocked by {blocker} (needs {tool_type} upgrade): {count}/{self.threshold}")

        if count >= self.threshold and tool_type not in self._suggested_upgrades:
            self._suggested_upgrades.add(tool_type)
            return self.get_upgrade_goal(tool_type, min_level)

        return None

    def should_suggest_upgrade(self, tool_type: str) -> bool:
        """Check if we should suggest upgrading a tool."""
        count = self._blocked_counts.get(tool_type, 0)
        return count >= self.threshold and tool_type not in self._suggested_upgrades

    def get_upgrade_goal(self, tool_type: str, min_level: Optional[int] = None) -> str:
        """Get the goal description for upgrading a tool."""
        if min_level is None:
            # Find the most commonly blocking level for this tool
            for blocker, (t, level, _) in OBSTACLE_REQUIREMENTS.items():
                if t == tool_type and level > 0:
                    min_level = level
                    break
            min_level = min_level or 1

        level_name = get_tool_level_name(min_level)
        return f"Upgrade {tool_type} to {level_name}"

    def get_all_suggested_upgrades(self) -> List[str]:
        """Get list of all tools that should be upgraded."""
        suggestions = []
        for tool_type, count in self._blocked_counts.items():
            if count >= self.threshold:
                # Find minimum level needed for this tool
                for blocker, (t, level, _) in OBSTACLE_REQUIREMENTS.items():
                    if t == tool_type and level > 0:
                        suggestions.append(self.get_upgrade_goal(tool_type, level))
                        break
        return suggestions

    def clear_tool(self, tool_type: str) -> None:
        """Clear tracking for a tool (e.g., after upgrading)."""
        self._blocked_counts.pop(tool_type, None)
        self._suggested_upgrades.discard(tool_type)

    def reset(self) -> None:
        """Reset all tracking (e.g., new game day)."""
        self._blocked_counts.clear()
        self._suggested_upgrades.clear()


# Global upgrade tracker instance
_upgrade_tracker: Optional[UpgradeTracker] = None

def get_upgrade_tracker() -> UpgradeTracker:
    """Get or create the global upgrade tracker."""
    global _upgrade_tracker
    if _upgrade_tracker is None:
        _upgrade_tracker = UpgradeTracker()
    return _upgrade_tracker


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    # Test with mock inventory (basic tools)
    test_inventory = [
        {"name": "Axe", "type": "tool", "quality": 0},
        {"name": "Pickaxe", "type": "tool", "quality": 0},
        {"name": "Scythe", "type": "tool", "quality": 0},
    ]

    print("Testing obstacle manager with basic tools:\n")

    test_obstacles = ["Stone", "Weeds", "Stump", "Boulder", "Log", "water", "wall"]

    for obs in test_obstacles:
        can_clear, reason, skill = can_clear_obstacle(test_inventory, obs)
        status = "✅" if can_clear else "❌"
        print(f"{status} {obs}: {reason}" + (f" (use {skill})" if skill else ""))

    print("\n--- With Copper Axe ---\n")
    test_inventory[0]["quality"] = 1  # Upgrade axe to copper

    for obs in ["Stump", "Log", "Hardwood Stump"]:
        can_clear, reason, skill = can_clear_obstacle(test_inventory, obs)
        status = "✅" if can_clear else "❌"
        print(f"{status} {obs}: {reason}")
