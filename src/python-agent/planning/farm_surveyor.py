"""
Farm Surveyor - Surveys farm state and plans optimal cell farming.

Uses /farm endpoint to get complete farm data, then:
1. Builds 2D tile state map
2. Finds contiguous tillable patches via BFS
3. Selects optimal cells for available seeds
4. Creates ordered cell plan for execution

Design decisions:
- Contiguous patch selection (minimizes inter-cell travel)
- Debris type detection (correct tool per cell)
- Partial cell handling (skip completed steps)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Import constants for tool slots
try:
    from constants import TOOL_SLOTS, DEBRIS_TOOLS
except ImportError:
    TOOL_SLOTS = {"Axe": 0, "Hoe": 1, "Watering Can": 2, "Pickaxe": 3, "Scythe": 4}
    DEBRIS_TOOLS = {"Weeds": "Scythe", "Stone": "Pickaxe", "Twig": "Axe", "Wood": "Axe"}

logger = logging.getLogger(__name__)


@dataclass
class TileState:
    """State of a single farm tile."""
    x: int
    y: int
    state: str  # "clear", "debris", "tilled", "planted", "watered"
    debris_type: Optional[str] = None  # "Stone", "Weeds", "Twig", "Wood"
    crop_name: Optional[str] = None
    is_watered: bool = False
    can_till: bool = False


@dataclass
class CellPlan:
    """Plan for a single farming cell."""
    x: int
    y: int
    needs_clear: bool = False
    needs_till: bool = False
    needs_plant: bool = False
    needs_water: bool = False
    debris_type: Optional[str] = None
    clear_tool_slot: int = 4  # Default to scythe
    seed_type: str = "Parsnip Seeds"
    patch_id: int = 0
    target_direction: str = "north"  # Direction to face when working


@dataclass
class CellFarmingPlan:
    """Complete plan for cell-by-cell farming."""
    cells: List[CellPlan] = field(default_factory=list)
    total_energy: int = 0
    estimated_time: int = 0
    patch_count: int = 0


class FarmSurveyor:
    """
    Surveys farm and creates optimal cell farming plans.

    Uses /farm endpoint data to:
    1. Build tile state map from crops, objects, tilled tiles
    2. Find contiguous tillable regions via BFS
    3. Select best cells based on seed count
    4. Create ordered execution plan
    """

    # Known farm coordinates (from SMAPI data)
    FARMHOUSE_DOOR = (64, 15)  # Player exits farmhouse here
    SCAN_RADIUS = 25  # Tiles around farmhouse to consider

    # Tool slots for debris clearing
    DEBRIS_TOOL_SLOTS = {
        "Weeds": 4,   # Scythe
        "Stone": 3,   # Pickaxe
        "Twig": 0,    # Axe
        "Wood": 0,    # Axe
        "Grass": 4,   # Scythe
    }

    def survey(self, farm_state: Dict[str, Any]) -> Dict[Tuple[int, int], TileState]:
        """
        Build tile state map from /farm endpoint data.

        Args:
            farm_state: Response from /farm endpoint (with or without wrapper)

        Returns:
            Dict mapping (x, y) to TileState
        """
        # Handle wrapper format
        data = farm_state.get("data") or farm_state

        tiles: Dict[Tuple[int, int], TileState] = {}

        # Process crops (planted tiles)
        crops = data.get("crops", [])
        for crop in crops:
            x, y = crop.get("x"), crop.get("y")
            if x is None or y is None:
                continue
            tiles[(x, y)] = TileState(
                x=x, y=y,
                state="watered" if crop.get("isWatered") else "planted",
                crop_name=crop.get("cropName"),
                is_watered=bool(crop.get("isWatered")),
            )

        # Process tilled tiles (empty soil)
        tilled = data.get("tilledTiles", [])
        for tile in tilled:
            x, y = tile.get("x"), tile.get("y")
            if x is None or y is None:
                continue
            # Don't overwrite if already has crop
            if (x, y) not in tiles:
                tiles[(x, y)] = TileState(
                    x=x, y=y,
                    state="tilled",
                    can_till=False,  # Already tilled
                )

        # Process objects (debris)
        objects = data.get("objects", [])
        debris_types = {"Stone", "Weeds", "Twig", "Wood", "Boulder", "Stump"}
        for obj in objects:
            x, y = obj.get("x"), obj.get("y")
            if x is None or y is None:
                continue
            obj_name = obj.get("name", "")
            obj_type = obj.get("type", "")

            # Check if it's debris
            if obj_name in debris_types or obj_type in ("Litter", "debris"):
                tiles[(x, y)] = TileState(
                    x=x, y=y,
                    state="debris",
                    debris_type=obj_name,
                    can_till=True,  # After clearing, can till
                )
            else:
                # Other objects (crafting, furniture) - not tillable
                tiles[(x, y)] = TileState(
                    x=x, y=y,
                    state="blocked",
                    can_till=False,
                )

        logger.info(f"FarmSurveyor: Mapped {len(tiles)} tiles "
                   f"(crops={len(crops)}, tilled={len(tilled)}, objects={len(objects)})")

        return tiles

    def find_contiguous_patches(
        self,
        tiles: Dict[Tuple[int, int], TileState],
        center: Tuple[int, int] = None,
    ) -> List[List[Tuple[int, int]]]:
        """
        Find contiguous patches of tillable tiles using BFS.

        A tile is "tillable" if:
        - It's clear ground (not in tiles dict = can till)
        - It's debris (can clear then till)
        - It's already tilled (can skip to plant)

        Args:
            tiles: Tile state map from survey()
            center: Center point for search (default: farmhouse door)

        Returns:
            List of patches, each patch is list of (x, y) coords.
            Sorted by size (largest first).
        """
        if center is None:
            center = self.FARMHOUSE_DOOR

        visited: Set[Tuple[int, int]] = set()
        patches: List[List[Tuple[int, int]]] = []

        # Scan area around center
        min_x = center[0] - self.SCAN_RADIUS
        max_x = center[0] + self.SCAN_RADIUS
        min_y = center[1] - self.SCAN_RADIUS
        max_y = center[1] + self.SCAN_RADIUS

        def is_tillable(x: int, y: int) -> bool:
            """Check if tile can be used for farming."""
            # Only within scan radius
            if not (min_x <= x <= max_x and min_y <= y <= max_y):
                return False

            if (x, y) in tiles:
                state = tiles[(x, y)].state
                # Debris can be cleared and tilled, tilled can be planted
                return state in ("debris", "tilled")
            # Not in tiles dict = unknown, don't assume it's tillable
            # SMAPI doesn't tell us which tiles are actual farmable ground
            return False

        def bfs_patch(start: Tuple[int, int]) -> List[Tuple[int, int]]:
            """BFS to find connected tillable tiles."""
            if start in visited or not is_tillable(start[0], start[1]):
                return []

            patch = []
            queue = deque([start])

            while queue:
                x, y = queue.popleft()
                if (x, y) in visited:
                    continue
                if not is_tillable(x, y):
                    continue

                visited.add((x, y))
                patch.append((x, y))

                # Add neighbors (4-directional)
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if (nx, ny) not in visited and min_x <= nx <= max_x and min_y <= ny <= max_y:
                        queue.append((nx, ny))

            return patch

        # Find patches starting from tiles near center
        search_order = []
        for dy in range(-self.SCAN_RADIUS, self.SCAN_RADIUS + 1):
            for dx in range(-self.SCAN_RADIUS, self.SCAN_RADIUS + 1):
                x, y = center[0] + dx, center[1] + dy
                search_order.append((abs(dx) + abs(dy), x, y))

        # Sort by distance from center (nearest first)
        search_order.sort()

        for _, x, y in search_order:
            if (x, y) not in visited:
                patch = bfs_patch((x, y))
                if len(patch) >= 3:  # Minimum patch size
                    patches.append(patch)

        # Sort by patch size (largest first)
        patches.sort(key=len, reverse=True)

        logger.info(f"FarmSurveyor: Found {len(patches)} patches, "
                   f"sizes: {[len(p) for p in patches[:5]]}")

        return patches

    def find_optimal_cells(
        self,
        tiles: Dict[Tuple[int, int], TileState],
        seed_count: int,
        center: Tuple[int, int] = None,
    ) -> List[CellPlan]:
        """
        Find optimal cells for farming based on contiguous patches.

        Strategy:
        1. Find contiguous patches via BFS
        2. Select from largest patch first
        3. If not enough, add from next patches
        4. Order cells row-by-row within patch for minimal travel

        Args:
            tiles: Tile state map from survey()
            seed_count: Number of seeds to plant
            center: Center point for search

        Returns:
            Ordered list of CellPlan objects
        """
        if center is None:
            center = self.FARMHOUSE_DOOR

        patches = self.find_contiguous_patches(tiles, center)

        if not patches:
            logger.warning("FarmSurveyor: No tillable patches found!")
            return []

        selected_cells: List[Tuple[int, int]] = []
        patch_assignments: Dict[Tuple[int, int], int] = {}

        # Select from patches until we have enough cells
        for patch_id, patch in enumerate(patches):
            if len(selected_cells) >= seed_count:
                break

            # Sort patch cells row-by-row (y asc, x asc)
            sorted_patch = sorted(patch, key=lambda c: (c[1], c[0]))

            for cell in sorted_patch:
                if len(selected_cells) >= seed_count:
                    break
                selected_cells.append(cell)
                patch_assignments[cell] = patch_id

        # Build CellPlan objects
        cell_plans = []
        for x, y in selected_cells:
            tile_state = tiles.get((x, y))

            # Determine what operations this cell needs
            needs_clear = False
            needs_till = True
            debris_type = None
            clear_tool_slot = 4

            if tile_state:
                if tile_state.state == "debris":
                    needs_clear = True
                    debris_type = tile_state.debris_type
                    clear_tool_slot = self.DEBRIS_TOOL_SLOTS.get(debris_type, 4)
                elif tile_state.state == "tilled":
                    needs_till = False  # Already tilled
                elif tile_state.state in ("planted", "watered"):
                    needs_till = False
                    # Could still add to plan for watering

            cell_plans.append(CellPlan(
                x=x, y=y,
                needs_clear=needs_clear,
                needs_till=needs_till,
                needs_plant=True,
                needs_water=True,
                debris_type=debris_type,
                clear_tool_slot=clear_tool_slot,
                patch_id=patch_assignments.get((x, y), 0),
            ))

        logger.info(f"FarmSurveyor: Selected {len(cell_plans)} cells, "
                   f"needs_clear={sum(1 for c in cell_plans if c.needs_clear)}, "
                   f"needs_till={sum(1 for c in cell_plans if c.needs_till)}")

        return cell_plans

    def create_farming_plan(
        self,
        farm_state: Dict[str, Any],
        seed_count: int,
        seed_type: str = "Parsnip Seeds",
    ) -> CellFarmingPlan:
        """
        Create complete cell farming plan.

        This is the main entry point - combines survey, patch finding,
        and cell selection into a single plan.

        Args:
            farm_state: Response from /farm endpoint
            seed_count: Number of seeds to plant
            seed_type: Type of seeds to assign to cells

        Returns:
            CellFarmingPlan with ordered cells
        """
        # Survey the farm
        tiles = self.survey(farm_state)

        # Find optimal cells
        cells = self.find_optimal_cells(tiles, seed_count)

        # Assign seed type and calculate estimates
        total_energy = 0
        for cell in cells:
            cell.seed_type = seed_type
            # Energy estimate: clear(2) + till(2) + plant(0) + water(2)
            energy = 0
            if cell.needs_clear:
                energy += 2
            if cell.needs_till:
                energy += 2
            if cell.needs_water:
                energy += 2
            total_energy += energy

        # Time estimate: ~5 seconds per cell (including movement)
        estimated_time = len(cells) * 5

        plan = CellFarmingPlan(
            cells=cells,
            total_energy=total_energy,
            estimated_time=estimated_time,
            patch_count=len(set(c.patch_id for c in cells)),
        )

        logger.info(f"FarmSurveyor: Created plan with {len(cells)} cells, "
                   f"energy={total_energy}, time={estimated_time}s")

        return plan


# Singleton instance
_farm_surveyor: Optional[FarmSurveyor] = None


def get_farm_surveyor() -> FarmSurveyor:
    """Get the singleton FarmSurveyor instance."""
    global _farm_surveyor
    if _farm_surveyor is None:
        _farm_surveyor = FarmSurveyor()
    return _farm_surveyor
