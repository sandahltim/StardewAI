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

import requests

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
    seed_slot: int = 5  # Inventory slot containing seeds
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
    5. Filter unreachable cells via /check-path API
    """

    # SMAPI API endpoint
    SMAPI_URL = "http://localhost:8790"

    # Known farm coordinates (from SMAPI data)
    FARMHOUSE_DOOR = (64, 15)  # Player exits farmhouse here
    SCAN_RADIUS = 50  # Tiles around farmhouse to consider (farm is 80x80)
    PLAYER_SCAN_RADIUS = 15  # Radius when centered on player position

    # Tool slots for debris clearing
    DEBRIS_TOOL_SLOTS = {
        "Weeds": 4,   # Scythe
        "Stone": 3,   # Pickaxe
        "Twig": 0,    # Axe
        "Wood": 0,    # Axe
        "Grass": 4,   # Scythe
        "Log": 0,     # Axe
        "Stump": 0,   # Axe
    }

    # Non-clearable obstacles (skip immediately)
    NON_CLEARABLE = {"Tree", "Boulder", "Bush", "Building", "Fence", "Water"}

    def is_cell_reachable(
        self,
        player_pos: Tuple[int, int],
        cell_pos: Tuple[int, int],
        timeout: float = 0.5,
    ) -> bool:
        """
        Check if a cell is reachable from player position using SMAPI pathfinding.

        Args:
            player_pos: Current player (x, y) tile position
            cell_pos: Target cell (x, y) tile position
            timeout: Request timeout in seconds

        Returns:
            True if a path exists, False otherwise
        """
        try:
            response = requests.get(
                f"{self.SMAPI_URL}/check-path",
                params={
                    "startX": player_pos[0],
                    "startY": player_pos[1],
                    "endX": cell_pos[0],
                    "endY": cell_pos[1],
                },
                timeout=timeout,
            )
            if response.status_code == 200:
                data = response.json().get("data", {})
                return data.get("reachable", False)
            return False
        except requests.RequestException as e:
            logger.warning(f"Pathfinding check failed: {e}")
            # Fall back to True to avoid blocking all cells if API is down
            return True

    def is_action_position_valid(
        self,
        player_pos: Tuple[int, int],
        cell_pos: Tuple[int, int],
        tiles: Dict[Tuple[int, int], "TileState"],
        timeout: float = 0.5,
    ) -> bool:
        """
        Check if action position for a cell is valid (static terrain only).

        For tilling/planting, the player stands at (X, Y+1) facing north to act on (X, Y).

        IMPORTANT: Only filter by STATIC impassable terrain (water, cliffs, buildings).
        Do NOT filter by debris - agent clears debris dynamically as it works.
        Do NOT use live pathfinding - debris blocks paths but we clear it.

        Args:
            player_pos: Current player (x, y) tile position (unused, kept for API compat)
            cell_pos: Target cell (x, y) to act on
            tiles: Tile state map from survey()
            timeout: Request timeout in seconds (unused)

        Returns:
            True if action position has passable terrain, False if water/cliff/building
        """
        x, y = cell_pos
        action_pos = (x, y + 1)  # Stand south of target, face north

        # Session 132: Exclude cells too close to farmhouse door
        # After warping from FarmHouse, player spawns at FARMHOUSE_DOOR (64, 15)
        # If action_pos is at/near spawn point, pathfinding gets confused
        door_x, door_y = self.FARMHOUSE_DOOR
        door_dist = abs(action_pos[0] - door_x) + abs(action_pos[1] - door_y)
        if door_dist < 2:
            # Action position too close to farmhouse door - skip this cell
            return False

        # Only filter by STATIC impassable terrain - agent clears debris dynamically
        action_tile = tiles.get(action_pos)
        if action_tile:
            # Water and cliffs are permanently impassable
            if action_tile.state in ("water", "cliff"):
                return False

        # Also check the target cell itself
        target_tile = tiles.get(cell_pos)
        if target_tile:
            if target_tile.state in ("water", "cliff"):
                return False

        return True

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

        # Process ResourceClumps (large stumps, logs, boulders - need tool upgrades)
        # These are 2x2 tiles and block farming until cleared with upgraded tools
        resource_clumps = data.get("resourceClumps", [])
        clump_tiles = 0
        for clump in resource_clumps:
            x, y = clump.get("x"), clump.get("y")
            width = clump.get("width", 2)
            height = clump.get("height", 2)
            clump_type = clump.get("type", "Obstacle")

            if x is None or y is None:
                continue

            # Mark all tiles covered by this clump as blocked
            for dx in range(width):
                for dy in range(height):
                    tile_x, tile_y = x + dx, y + dy
                    tiles[(tile_x, tile_y)] = TileState(
                        x=tile_x, y=tile_y,
                        state="blocked",
                        debris_type=clump_type,
                        can_till=False,  # Needs tool upgrade to clear
                    )
                    clump_tiles += 1

        logger.info(f"FarmSurveyor: Mapped {len(tiles)} tiles "
                   f"(crops={len(crops)}, tilled={len(tilled)}, objects={len(objects)}, "
                   f"clumps={len(resource_clumps)} blocking {clump_tiles} tiles)")

        return tiles

    def find_contiguous_patches(
        self,
        tiles: Dict[Tuple[int, int], TileState],
        center: Tuple[int, int] = None,
        scan_radius: Optional[int] = None,
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
            scan_radius: Custom scan radius (default: SCAN_RADIUS)

        Returns:
            List of patches, each patch is list of (x, y) coords.
            Sorted by size (largest first).
        """
        if center is None:
            center = self.FARMHOUSE_DOOR

        radius = scan_radius if scan_radius is not None else self.SCAN_RADIUS

        visited: Set[Tuple[int, int]] = set()
        patches: List[List[Tuple[int, int]]] = []

        # Scan area around center
        min_x = center[0] - radius
        max_x = center[0] + radius
        min_y = center[1] - radius
        max_y = center[1] + radius

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

        # Sort by proximity to center (nearest patch first)
        # Calculate min distance from any cell in patch to center
        def patch_distance(patch: List[Tuple[int, int]]) -> int:
            return min(abs(x - center[0]) + abs(y - center[1]) for x, y in patch)

        patches.sort(key=patch_distance)

        logger.info(f"FarmSurveyor: Found {len(patches)} patches, "
                   f"sizes: {[len(p) for p in patches[:5]]}, "
                   f"distances: {[patch_distance(p) for p in patches[:5]]}")

        return patches

    def find_optimal_cells(
        self,
        tiles: Dict[Tuple[int, int], TileState],
        seed_count: int,
        center: Tuple[int, int] = None,
        scan_radius: Optional[int] = None,
        check_reachability: bool = True,
    ) -> List[CellPlan]:
        """
        Find optimal cells for farming based on contiguous patches.

        Strategy:
        1. Find contiguous patches via BFS
        2. Select from patches (nearest first)
        3. Filter unreachable cells via /check-path API
        4. Order cells row-by-row for minimal travel

        Args:
            tiles: Tile state map from survey()
            seed_count: Number of seeds to plant
            center: Center point for search (also used as pathfinding start)
            scan_radius: Custom scan radius (smaller = avoid cliff issues)
            check_reachability: If True, use SMAPI pathfinding to filter unreachable cells

        Returns:
            Ordered list of CellPlan objects (only reachable cells)
        """
        if center is None:
            center = self.FARMHOUSE_DOOR

        radius = scan_radius if scan_radius is not None else self.SCAN_RADIUS

        # PRIORITY 1: Existing tilled tiles (ready for planting, no work needed)
        # These may be isolated and not in contiguous patches
        tilled_cells: List[Tuple[int, int]] = []
        for (x, y), state in tiles.items():
            if state.state == "tilled":
                # Check within scan radius
                if abs(x - center[0]) <= radius and abs(y - center[1]) <= radius:
                    tilled_cells.append((x, y))

        # Sort tilled by distance to center
        tilled_cells.sort(key=lambda c: abs(c[0] - center[0]) + abs(c[1] - center[1]))

        if tilled_cells:
            logger.info(f"FarmSurveyor: Found {len(tilled_cells)} existing tilled tiles (priority)")

        # PRIORITY 2: Debris patches that can be cleared and tilled
        patches = self.find_contiguous_patches(tiles, center, scan_radius)

        if not patches and not tilled_cells:
            logger.warning("FarmSurveyor: No tillable patches or tilled tiles found!")
            return []

        # Collect candidate cells: tilled first, then patches
        candidate_cells: List[Tuple[int, int]] = list(tilled_cells)
        patch_assignments: Dict[Tuple[int, int], int] = {}

        # Gather 3x the cells we need to account for unreachable filtering
        target_candidates = seed_count * 3

        for patch_id, patch in enumerate(patches):
            if len(candidate_cells) >= target_candidates:
                break

            # Sort patch cells by distance to center
            sorted_patch = sorted(patch, key=lambda c: abs(c[0] - center[0]) + abs(c[1] - center[1]))

            for cell in sorted_patch:
                if len(candidate_cells) >= target_candidates:
                    break
                candidate_cells.append(cell)
                patch_assignments[cell] = patch_id

        logger.info(f"FarmSurveyor: {len(candidate_cells)} candidates ({len(tilled_cells)} tilled + {len(candidate_cells) - len(tilled_cells)} from patches)")

        # Filter unreachable cells using SMAPI pathfinding
        # CRITICAL: Check action position (X, Y+1) not just the cell (X, Y)!
        # Player stands at Y+1 to till/plant the cell at Y
        if check_reachability and candidate_cells:
            reachable_cells: List[Tuple[int, int]] = []
            unreachable_count = 0

            for cell in candidate_cells:
                if len(reachable_cells) >= seed_count:
                    break  # We have enough

                # Check if action position (X, Y+1) is reachable AND passable
                if self.is_action_position_valid(center, cell, tiles):
                    reachable_cells.append(cell)
                else:
                    unreachable_count += 1

            if unreachable_count > 0:
                logger.info(f"FarmSurveyor: Filtered {unreachable_count} cells with unreachable action positions")

            selected_cells = reachable_cells
        else:
            # No reachability check - just take first N cells
            selected_cells = candidate_cells[:seed_count]

        # Global sort: row-by-row walking order
        selected_cells.sort(key=lambda c: (c[1], c[0]))

        logger.info(f"FarmSurveyor: Selected {len(selected_cells)} reachable cells: "
                   f"{[(c[0], c[1]) for c in selected_cells[:8]]}...")

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
        seed_slot: int = 5,
        player_pos: Optional[Tuple[int, int]] = None,
    ) -> CellFarmingPlan:
        """
        Create complete cell farming plan.

        This is the main entry point - combines survey, patch finding,
        and cell selection into a single plan.

        Args:
            farm_state: Response from /farm endpoint
            seed_count: Number of seeds to plant
            seed_type: Type of seeds to assign to cells
            seed_slot: Inventory slot containing seeds
            player_pos: Player position - used as center for cell selection
                       (selects cells near player to avoid cliff navigation issues)

        Returns:
            CellFarmingPlan with ordered cells
        """
        # Survey the farm
        tiles = self.survey(farm_state)

        # Find optimal cells - prefer existing tilled ground near farmhouse
        # Only use player position if they're close to farmhouse
        if player_pos:
            dist_to_house = abs(player_pos[0] - self.FARMHOUSE_DOOR[0]) + abs(player_pos[1] - self.FARMHOUSE_DOOR[1])
            if dist_to_house <= self.PLAYER_SCAN_RADIUS:
                # Player is near farmhouse - use player position
                center = player_pos
                scan_radius = self.PLAYER_SCAN_RADIUS
                logger.info(f"FarmSurveyor: Player near house, using position {player_pos} with radius {scan_radius}")
            else:
                # Player is far from farmhouse - use farmhouse to find existing tilled ground
                center = self.FARMHOUSE_DOOR
                scan_radius = self.SCAN_RADIUS
                logger.info(f"FarmSurveyor: Player far from house ({dist_to_house} tiles), using farmhouse center")
        else:
            center = self.FARMHOUSE_DOOR
            scan_radius = self.SCAN_RADIUS

        # Use SMAPI pathfinding to filter unreachable cells (fixes cliff navigation)
        cells = self.find_optimal_cells(
            tiles, seed_count, center, scan_radius, check_reachability=True
        )

        # Assign seed type/slot and calculate estimates
        total_energy = 0
        for cell in cells:
            cell.seed_type = seed_type
            cell.seed_slot = seed_slot
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
                   f"energy={total_energy}, time={estimated_time}s, seed_slot={seed_slot}")

        return plan


# Singleton instance
_farm_surveyor: Optional[FarmSurveyor] = None


def get_farm_surveyor() -> FarmSurveyor:
    """Get the singleton FarmSurveyor instance."""
    global _farm_surveyor
    if _farm_surveyor is None:
        _farm_surveyor = FarmSurveyor()
    return _farm_surveyor
