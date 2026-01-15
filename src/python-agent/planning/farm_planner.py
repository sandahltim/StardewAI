"""
Farm Layout Planner - Intelligent placement for scarecrows, sprinklers, chests.

Calculates optimal positions to maximize coverage while minimizing items placed.
Used by placement skills to know WHERE to place items, not just HOW.

Usage:
    from planning.farm_planner import get_farm_layout_plan, calculate_scarecrow_positions

    plan = get_farm_layout_plan(farm_state)
    # Returns: {"scarecrows": [...], "chests": [...], "coverage": {...}}
"""

import logging
import math
from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Scarecrow protection radius (tiles) - confirmed from Stardew wiki
SCARECROW_RADIUS = 8

# Sprinkler coverage patterns (tiles relative to sprinkler position)
SPRINKLER_PATTERNS = {
    "Basic": [(0, -1), (0, 1), (-1, 0), (1, 0)],  # 4 cardinal tiles
    "Quality": [  # 3x3 area around sprinkler
        (-1, -1), (0, -1), (1, -1),
        (-1, 0), (1, 0),
        (-1, 1), (0, 1), (1, 1)
    ],
    "Iridium": [  # 5x5 area around sprinkler
        (dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
        if not (dx == 0 and dy == 0)
    ]
}

# Strategic chest locations (relative to landmarks)
CHEST_PURPOSES = {
    "shipping": "Near shipping bin for overflow",
    "seeds": "Near farmhouse for planting supplies",
    "materials": "Near crafting area for wood/stone",
    "crops": "Near fields for harvest overflow"
}

# Known farm landmarks (Standard Farm layout)
FARM_LANDMARKS = {
    "farmhouse_door": (64, 15),
    "shipping_bin": (71, 14),
    "cave": (34, 6),
    "greenhouse_area": (28, 12),
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PlannedScarecrow:
    """A planned scarecrow placement."""
    x: int
    y: int
    covers_crops: int
    covered_positions: Set[Tuple[int, int]] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "covers_crops": self.covers_crops,
            "radius": SCARECROW_RADIUS
        }


@dataclass
class PlannedChest:
    """A planned chest placement."""
    x: int
    y: int
    purpose: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "purpose": self.purpose
        }


@dataclass
class FarmLayoutPlan:
    """Complete farm layout plan."""
    scarecrows: List[PlannedScarecrow] = field(default_factory=list)
    chests: List[PlannedChest] = field(default_factory=list)
    sprinklers: List[Dict] = field(default_factory=list)  # Future

    def get_coverage_stats(self, total_crops: int) -> Dict[str, Any]:
        protected = set()
        for sc in self.scarecrows:
            protected.update(sc.covered_positions)

        protected_count = len(protected)
        percentage = (protected_count / total_crops * 100) if total_crops > 0 else 0

        return {
            "protected_crops": protected_count,
            "total_crops": total_crops,
            "percentage": round(percentage, 1),
            "scarecrows_needed": len(self.scarecrows)
        }

    def to_dict(self, total_crops: int = 0) -> Dict[str, Any]:
        return {
            "scarecrows": [sc.to_dict() for sc in self.scarecrows],
            "chests": [ch.to_dict() for ch in self.chests],
            "sprinklers": self.sprinklers,
            "coverage": self.get_coverage_stats(total_crops)
        }


# =============================================================================
# Scarecrow Positioning
# =============================================================================

def get_crops_in_radius(center: Tuple[int, int], radius: int,
                         crop_positions: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
    """
    Get all crops within circular radius of center point.
    Uses actual circular distance (not Manhattan).
    """
    cx, cy = center
    covered = set()

    for crop_pos in crop_positions:
        cx2, cy2 = crop_pos
        # Euclidean distance for circular radius
        distance = math.sqrt((cx2 - cx) ** 2 + (cy2 - cy) ** 2)
        if distance <= radius:
            covered.add(crop_pos)

    return covered


def is_valid_placement(pos: Tuple[int, int],
                       blocked_tiles: Set[Tuple[int, int]],
                       crop_positions: Set[Tuple[int, int]]) -> bool:
    """
    Check if position is valid for placing a scarecrow.
    Cannot place on: crops, existing objects, buildings.
    """
    if pos in blocked_tiles:
        return False
    if pos in crop_positions:
        return False
    return True


def calculate_scarecrow_positions(
    crop_positions: Set[Tuple[int, int]],
    blocked_tiles: Set[Tuple[int, int]],
    existing_scarecrows: List[Tuple[int, int]] = None
) -> List[PlannedScarecrow]:
    """
    Calculate optimal scarecrow positions using greedy set cover.

    Algorithm:
    1. Start with all crops unprotected
    2. For each candidate position, count how many unprotected crops it would cover
    3. Place scarecrow at position that covers the most
    4. Repeat until all crops are protected

    Args:
        crop_positions: Set of (x, y) tuples for all crops
        blocked_tiles: Set of (x, y) tuples that cannot have scarecrows
        existing_scarecrows: Already placed scarecrows to account for

    Returns:
        List of PlannedScarecrow objects
    """
    if not crop_positions:
        logger.info("No crops to protect")
        return []

    existing_scarecrows = existing_scarecrows or []

    # Track which crops are already protected
    protected_crops: Set[Tuple[int, int]] = set()
    for sc_pos in existing_scarecrows:
        covered = get_crops_in_radius(sc_pos, SCARECROW_RADIUS, crop_positions)
        protected_crops.update(covered)

    # Crops still needing protection
    unprotected = crop_positions - protected_crops

    if not unprotected:
        logger.info(f"All {len(crop_positions)} crops already protected by existing scarecrows")
        return []

    planned: List[PlannedScarecrow] = []

    # Generate candidate positions: area around crops
    # Search within radius of any crop
    candidates: Set[Tuple[int, int]] = set()
    for crop_x, crop_y in crop_positions:
        for dx in range(-SCARECROW_RADIUS, SCARECROW_RADIUS + 1):
            for dy in range(-SCARECROW_RADIUS, SCARECROW_RADIUS + 1):
                candidate = (crop_x + dx, crop_y + dy)
                if is_valid_placement(candidate, blocked_tiles, crop_positions):
                    candidates.add(candidate)

    logger.info(f"Evaluating {len(candidates)} candidate positions for {len(unprotected)} unprotected crops")

    # Greedy set cover
    while unprotected:
        best_pos = None
        best_coverage: Set[Tuple[int, int]] = set()
        best_count = 0

        for candidate in candidates:
            coverage = get_crops_in_radius(candidate, SCARECROW_RADIUS, unprotected)
            if len(coverage) > best_count:
                best_count = len(coverage)
                best_coverage = coverage
                best_pos = candidate

        if best_pos is None or best_count == 0:
            logger.warning(f"Cannot cover {len(unprotected)} remaining crops - no valid positions")
            break

        # Place scarecrow at best position
        planned.append(PlannedScarecrow(
            x=best_pos[0],
            y=best_pos[1],
            covers_crops=best_count,
            covered_positions=best_coverage
        ))

        # Update tracking
        unprotected -= best_coverage
        candidates.discard(best_pos)  # Can't place another here

        logger.debug(f"Planned scarecrow at {best_pos} covering {best_count} crops, "
                    f"{len(unprotected)} remaining")

    logger.info(f"Planned {len(planned)} scarecrows to protect {len(crop_positions)} crops")
    return planned


# =============================================================================
# Chest Positioning
# =============================================================================

def calculate_chest_locations(
    blocked_tiles: Set[Tuple[int, int]],
    crop_positions: Set[Tuple[int, int]],
    purposes: List[str] = None
) -> List[PlannedChest]:
    """
    Calculate strategic chest positions.

    Args:
        blocked_tiles: Tiles that cannot have chests
        crop_positions: Where crops are (don't place on crops)
        purposes: Which chest types needed ("shipping", "seeds", etc.)

    Returns:
        List of PlannedChest objects
    """
    purposes = purposes or ["shipping", "seeds"]
    planned: List[PlannedChest] = []

    # Preferred positions for each purpose
    preferred = {
        "shipping": (69, 14),   # 2 tiles west of shipping bin
        "seeds": (66, 15),     # Near farmhouse door
        "materials": (60, 18), # South of farmhouse
        "crops": (58, 20),     # In farming area
    }

    for purpose in purposes:
        if purpose not in preferred:
            continue

        target = preferred[purpose]

        # If target blocked, search nearby
        final_pos = find_nearby_valid(target, blocked_tiles, crop_positions, search_radius=5)

        if final_pos:
            planned.append(PlannedChest(
                x=final_pos[0],
                y=final_pos[1],
                purpose=purpose
            ))
            # Add to blocked so next chest doesn't overlap
            blocked_tiles.add(final_pos)
        else:
            logger.warning(f"Could not find valid position for {purpose} chest near {target}")

    return planned


def find_nearby_valid(
    target: Tuple[int, int],
    blocked: Set[Tuple[int, int]],
    crops: Set[Tuple[int, int]],
    search_radius: int = 5
) -> Optional[Tuple[int, int]]:
    """Find valid position near target, spiraling outward."""
    tx, ty = target

    # Check target first
    if target not in blocked and target not in crops:
        return target

    # Spiral outward
    for r in range(1, search_radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) == r or abs(dy) == r:  # Only check perimeter
                    pos = (tx + dx, ty + dy)
                    if pos not in blocked and pos not in crops:
                        return pos

    return None


# =============================================================================
# Main API
# =============================================================================

def get_farm_layout_plan(farm_state: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate complete farm layout plan from current farm state.

    This is the main API for UI and agent integration.

    Args:
        farm_state: Response from /farm endpoint. If None, returns empty plan.

    Returns:
        Dict with scarecrows, chests, sprinklers, and coverage stats.
    """
    if farm_state is None:
        return {
            "status": "no_state",
            "message": "No farm state provided",
            "scarecrows": [],
            "chests": [],
            "sprinklers": [],
            "coverage": {"protected_crops": 0, "total_crops": 0, "percentage": 0}
        }

    # Extract data (handle wrapper format)
    data = farm_state.get("data") or farm_state

    # Get crop positions
    crops = data.get("crops", [])
    crop_positions: Set[Tuple[int, int]] = set()
    for crop in crops:
        x, y = crop.get("x"), crop.get("y")
        if x is not None and y is not None:
            crop_positions.add((x, y))

    # Get blocked tiles (objects, buildings, etc.)
    blocked_tiles: Set[Tuple[int, int]] = set()

    for obj in data.get("objects", []):
        x, y = obj.get("x"), obj.get("y")
        if x is not None and y is not None:
            blocked_tiles.add((x, y))

    for clump in data.get("resourceClumps", []):
        x, y = clump.get("x"), clump.get("y")
        width = clump.get("width", 2)
        height = clump.get("height", 2)
        if x is not None and y is not None:
            for dx in range(width):
                for dy in range(height):
                    blocked_tiles.add((x + dx, y + dy))

    # Get existing scarecrows
    existing_scarecrows: List[Tuple[int, int]] = []
    for obj in data.get("objects", []):
        if "scarecrow" in obj.get("name", "").lower():
            x, y = obj.get("x"), obj.get("y")
            if x is not None and y is not None:
                existing_scarecrows.append((x, y))

    # Calculate placements
    scarecrows = calculate_scarecrow_positions(
        crop_positions, blocked_tiles, existing_scarecrows
    )

    chests = calculate_chest_locations(
        blocked_tiles.copy(),  # Copy so we don't mutate
        crop_positions,
        purposes=["shipping", "seeds"]
    )

    # Build plan
    plan = FarmLayoutPlan(
        scarecrows=scarecrows,
        chests=chests,
        sprinklers=[]  # Future: add when we have mining
    )

    result = plan.to_dict(total_crops=len(crop_positions))
    result["status"] = "ok"
    result["existing_scarecrows"] = len(existing_scarecrows)

    logger.info(f"Farm layout plan: {len(scarecrows)} scarecrows, {len(chests)} chests, "
               f"coverage {result['coverage']['percentage']}%")

    return result


def get_next_placement(farm_state: Dict[str, Any], item_type: str) -> Optional[Tuple[int, int]]:
    """
    Get the next recommended placement position for an item.

    Used by placement skills to know WHERE to place.

    Args:
        farm_state: Current farm state from /farm
        item_type: "scarecrow", "chest", or "sprinkler"

    Returns:
        (x, y) position or None if no placement needed
    """
    plan = get_farm_layout_plan(farm_state)

    if item_type == "scarecrow":
        scarecrows = plan.get("scarecrows", [])
        if scarecrows:
            return (scarecrows[0]["x"], scarecrows[0]["y"])

    elif item_type == "chest":
        chests = plan.get("chests", [])
        if chests:
            return (chests[0]["x"], chests[0]["y"])

    return None


# =============================================================================
# Placement Planning Integration
# =============================================================================

def get_placement_sequence(
    farm_state: Dict[str, Any],
    item_type: str,
    player_pos: Tuple[int, int]
) -> Optional[Dict[str, Any]]:
    """
    Get full placement sequence: where to go + how to place.

    This is the main integration point for agent/skills.

    Args:
        farm_state: Current farm state from /farm
        item_type: "scarecrow", "chest", or "sprinkler"
        player_pos: Current player (x, y) position

    Returns:
        Dict with:
        - target_pos: (x, y) where to navigate to
        - place_direction: direction to face when placing
        - place_pos: (x, y) where item will end up
        - reason: why this position was chosen

        Or None if no placement needed.
    """
    plan = get_farm_layout_plan(farm_state)

    if plan.get("status") != "ok":
        return None

    placements = plan.get(f"{item_type}s", [])  # scarecrows, chests, sprinklers
    if not placements:
        return None

    # Get first recommended placement
    placement = placements[0]
    target_x, target_y = placement["x"], placement["y"]

    # Calculate best position to stand and direction to face
    # Try all 4 adjacent positions, pick closest to player
    px, py = player_pos
    candidates = [
        ((target_x, target_y + 1), "north"),  # Stand south, face north
        ((target_x, target_y - 1), "south"),  # Stand north, face south
        ((target_x - 1, target_y), "east"),   # Stand west, face east
        ((target_x + 1, target_y), "west"),   # Stand east, face west
    ]

    # Sort by distance to player
    candidates.sort(key=lambda c: abs(c[0][0] - px) + abs(c[0][1] - py))

    stand_pos, direction = candidates[0]

    return {
        "target_pos": stand_pos,
        "place_direction": direction,
        "place_pos": (target_x, target_y),
        "reason": placement.get("purpose") or f"covers {placement.get('covers_crops', 0)} crops",
        "item_type": item_type
    }


def get_planting_layout(
    farm_state: Dict[str, Any],
    num_seeds: int = 15,
    near_pos: Tuple[int, int] = None
) -> List[Tuple[int, int]]:
    """
    Get optimal positions for planting seeds.

    Prefers contiguous blocks near existing crops or player.
    Returns positions sorted for efficient walking order.

    Args:
        farm_state: Current farm state
        num_seeds: How many seeds to plant
        near_pos: Prefer positions near this location

    Returns:
        List of (x, y) positions to plant at, row-by-row order
    """
    data = farm_state.get("data") or farm_state

    # Get existing crop positions to plant near them
    crops = data.get("crops", [])
    crop_positions = {(c["x"], c["y"]) for c in crops if c.get("x") and c.get("y")}

    # Get tilled tiles (available for planting)
    tilled = data.get("tilledTiles", [])
    available = []
    for tile in tilled:
        x, y = tile.get("x"), tile.get("y")
        if x is not None and y is not None:
            if (x, y) not in crop_positions:  # Not already planted
                available.append((x, y))

    if not available:
        return []

    # If we have a reference position, sort by distance
    if near_pos:
        ref_x, ref_y = near_pos
        available.sort(key=lambda p: abs(p[0] - ref_x) + abs(p[1] - ref_y))
    else:
        # Sort row-by-row (top to bottom, left to right)
        available.sort(key=lambda p: (p[1], p[0]))

    return available[:num_seeds]


# =============================================================================
# Singleton Instance
# =============================================================================

_cached_plan: Optional[Dict[str, Any]] = None
_cached_crop_count: int = 0


def get_cached_plan(farm_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get layout plan with caching (invalidates when crop count changes).
    """
    global _cached_plan, _cached_crop_count

    data = farm_state.get("data") or farm_state
    current_crops = len(data.get("crops", []))

    if _cached_plan is None or current_crops != _cached_crop_count:
        _cached_plan = get_farm_layout_plan(farm_state)
        _cached_crop_count = current_crops

    return _cached_plan


def clear_plan_cache():
    """Clear cached plan (call when significant farm changes occur)."""
    global _cached_plan, _cached_crop_count
    _cached_plan = None
    _cached_crop_count = 0


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Mock farm state
    test_state = {
        "crops": [
            {"x": 54, "y": 18}, {"x": 55, "y": 18}, {"x": 56, "y": 18},
            {"x": 54, "y": 19}, {"x": 55, "y": 19}, {"x": 56, "y": 19},
            {"x": 54, "y": 20}, {"x": 55, "y": 20}, {"x": 56, "y": 20},
            {"x": 70, "y": 18}, {"x": 71, "y": 18}, {"x": 72, "y": 18},
        ],
        "objects": [
            {"x": 64, "y": 14, "name": "Shipping Bin"},
        ],
        "resourceClumps": []
    }

    print("Testing farm layout planner...")
    plan = get_farm_layout_plan(test_state)

    print(f"\nResult:")
    print(f"  Scarecrows needed: {len(plan['scarecrows'])}")
    for sc in plan['scarecrows']:
        print(f"    - ({sc['x']}, {sc['y']}) covers {sc['covers_crops']} crops")

    print(f"  Chests: {len(plan['chests'])}")
    for ch in plan['chests']:
        print(f"    - ({ch['x']}, {ch['y']}) for {ch['purpose']}")

    print(f"  Coverage: {plan['coverage']['percentage']}%")
