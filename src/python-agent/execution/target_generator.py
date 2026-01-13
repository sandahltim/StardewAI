from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SortStrategy(Enum):
    ROW_BY_ROW = "row_by_row"      # y asc, x asc - like reading a book
    NEAREST_FIRST = "nearest"      # Manhattan distance from player
    SPIRAL_OUT = "spiral"          # Center outward (future)


@dataclass
class Target:
    x: int
    y: int
    target_type: str              # "crop", "debris", "tile", "object"
    metadata: Dict[str, Any]      # crop_name, is_watered, etc.


class TargetGenerator:
    """
    Generates sorted target lists for task execution.
    Pure function - no side effects, no state.
    """

    def generate(
        self,
        task_type: str,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        strategy: SortStrategy = SortStrategy.ROW_BY_ROW,
        task_params: Optional[Dict[str, Any]] = None,
    ) -> List[Target]:
        """
        Main entry point. Dispatches to task-specific generators.

        Args:
            task_type: "water_crops", "harvest_crops", "clear_debris",
                      "till_soil", "plant_seeds", "navigate", "refill_watering_can"
            game_state: From SMAPI /state endpoint
            player_pos: (x, y) current player position
            strategy: How to sort targets
            task_params: Optional params from PrereqResolver (e.g., destination coords)

        Returns:
            Ordered list of Target objects
        """
        # Multi-target tasks (scan game state)
        dispatch = {
            "water_crops": self._generate_water_targets,
            "harvest_crops": self._generate_harvest_targets,
            "clear_debris": self._generate_debris_targets,
            "till_soil": self._generate_till_targets,
            "plant_seeds": self._generate_plant_targets,
        }
        
        # Single-target tasks (use params)
        if task_type == "ship_items":
            return self._generate_ship_targets(game_state, player_pos)
        elif task_type == "buy_seeds":
            # Buy seeds at current location (should already be at Pierre's)
            return [Target(
                x=player_pos[0],
                y=player_pos[1],
                target_type="buy",
                metadata={"action": "buy_parsnip_seeds"},
            )]
        elif task_type == "navigate":
            return self._generate_navigate_target(player_pos, task_params)
        elif task_type == "refill_watering_can":
            return self._generate_refill_target(game_state, player_pos, task_params)
        elif task_type == "till_soil":
            # Till needs task_params for target_count
            return self._generate_till_targets(game_state, player_pos, strategy, task_params)
        elif task_type == "clear_debris":
            # Clear debris may have target_count limit from prereq
            return self._generate_debris_targets(game_state, player_pos, strategy, task_params)

        generator = dispatch.get(task_type)
        if not generator:
            return []
        return generator(game_state, player_pos, strategy)

    def _extract_crops(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract crops from game state (handles both wrapped and unwrapped formats)."""
        # Handle both {success, data, error} wrapper and direct {location, player, ...} format
        data = state.get("data") or state
        # Try data.location.crops first (actual SMAPI structure)
        location = data.get("location") or {}
        crops = location.get("crops")
        if crops:
            return crops
        # Fallback to data.crops (for tests/simple format)
        return data.get("crops") or []

    def _generate_water_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
    ) -> List[Target]:
        """Get unwatered crops from state, sort by strategy."""
        crops = self._extract_crops(state)
        targets: List[Target] = []
        for crop in crops:
            if crop.get("isWatered"):
                continue
            x = crop.get("x")
            y = crop.get("y")
            if x is None or y is None:
                continue
            targets.append(Target(
                x=int(x),
                y=int(y),
                target_type="crop",
                metadata={
                    "crop_name": crop.get("cropName"),
                    "is_watered": bool(crop.get("isWatered")),
                    "is_ready": bool(crop.get("isReadyForHarvest")),
                },
            ))
        return self._sort_targets(targets, pos, strategy)

    def _generate_harvest_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
    ) -> List[Target]:
        """Get ready crops from state where isReadyForHarvest=True."""
        crops = self._extract_crops(state)
        targets: List[Target] = []
        for crop in crops:
            if not crop.get("isReadyForHarvest"):
                continue
            x = crop.get("x")
            y = crop.get("y")
            if x is None or y is None:
                continue
            targets.append(Target(
                x=int(x),
                y=int(y),
                target_type="crop",
                metadata={
                    "crop_name": crop.get("cropName"),
                    "is_watered": bool(crop.get("isWatered")),
                    "is_ready": bool(crop.get("isReadyForHarvest")),
                },
            ))
        return self._sort_targets(targets, pos, strategy)

    def _extract_objects(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract objects from game state (handles both wrapped and unwrapped formats)."""
        data = state.get("data") or state
        # Try data.location.objects first (actual SMAPI structure)
        location = data.get("location") or {}
        objects = location.get("objects")
        if objects:
            return objects
        # Fallback to data.objects (for tests/simple format)
        return data.get("objects") or []

    def _generate_debris_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
        task_params: Optional[Dict[str, Any]] = None,
    ) -> List[Target]:
        """Get debris objects (Stone, Weeds, Twig) from state."""
        objects = self._extract_objects(state)
        targets: List[Target] = []
        # Debris in SMAPI has type="Litter" or we check by name
        debris_names = {"Stone", "Weeds", "Twig", "Wood"}
        for obj in objects:
            obj_type = obj.get("type", "")
            obj_name = obj.get("name", "")
            # Match by type="Litter" or type="debris" or name in debris list
            if obj_type not in ("Litter", "debris") and obj_name not in debris_names:
                continue
            x = obj.get("x")
            y = obj.get("y")
            if x is None or y is None:
                continue
            targets.append(Target(
                x=int(x),
                y=int(y),
                target_type="debris",
                metadata={
                    "name": obj_name,
                    "type": obj_type,
                },
            ))

        # Sort targets first (nearest or row-by-row)
        sorted_targets = self._sort_targets(targets, pos, strategy)

        # Limit to target_count if specified (e.g., prereq only needs to clear N tiles)
        target_count = (task_params or {}).get("target_count")
        if target_count and len(sorted_targets) > target_count:
            sorted_targets = sorted_targets[:target_count]

        return sorted_targets

    def _generate_till_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
        task_params: Optional[Dict[str, Any]] = None,
    ) -> List[Target]:
        """
        Get tillable tiles - clear ground that canTill=True.

        If SMAPI doesn't provide tile data, generates fallback targets
        near the farmhouse door (known tillable area on Day 1).
        """
        # First try: use tile data from SMAPI if available
        targets = self._tiles_from_state(
            state,
            predicate=lambda tile: tile.get("canTill") and not tile.get("isTilled"),
        )

        if targets:
            return self._sort_targets(targets, pos, strategy)

        # Fallback: generate targets near player position (just cleared debris there)
        target_count = (task_params or {}).get("target_count", 15)

        # Generate a grid of targets near player (where debris was just cleared)
        # Use player position as center, offset slightly south to avoid standing tile
        base_x, base_y = pos[0] - 2, pos[1] + 1  # Slightly south of player
        targets = []

        for i in range(target_count):
            # Create a 5-wide row pattern
            row = i // 5
            col = i % 5
            x = base_x + col
            y = base_y + row

            targets.append(Target(
                x=x,
                y=y,
                target_type="till",
                metadata={"fallback": True},
            ))

        return self._sort_targets(targets, pos, strategy)

    def _generate_plant_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
    ) -> List[Target]:
        """Get plantable tiles - tilled but empty."""
        targets = self._tiles_from_state(
            state,
            predicate=self._is_plantable_tile,
        )
        return self._sort_targets(targets, pos, strategy)


    def _generate_ship_targets(
        self,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
    ) -> List[Target]:
        """
        Generate target for shipping bin.
        
        Checks inventory for sellable items and creates a single target
        at the shipping bin location if there are items to ship.
        """
        data = game_state.get("data") or game_state
        location = data.get("location") or {}
        inventory = data.get("inventory") or []
        
        # Check if there are sellable items in inventory
        sellable_categories = ["crop", "forage", "artisan"]
        sellable_items = [
            item for item in inventory
            if item and item.get("type") in sellable_categories and item.get("stack", 0) > 0
        ]
        
        if not sellable_items:
            return []
        
        # Get shipping bin location
        shipping_bin = location.get("shippingBin")
        if not shipping_bin:
            # Default Farm shipping bin location
            shipping_bin = {"x": 71, "y": 14}
        
        bin_x = shipping_bin.get("x", 71)
        bin_y = shipping_bin.get("y", 14)
        
        # Calculate total items to ship
        total_stack = sum(item.get("stack", 0) for item in sellable_items)
        item_names = [item.get("name", "item") for item in sellable_items]
        
        return [Target(
            x=bin_x,
            y=bin_y,
            target_type="ship",
            metadata={
                "items": item_names,
                "total_stack": total_stack,
                "sellable_items": sellable_items,
            },
        )]

    def _generate_navigate_target(
        self,
        player_pos: Tuple[int, int],
        task_params: Optional[Dict[str, Any]],
    ) -> List[Target]:
        """
        Generate single target for navigation task.
        
        Destination comes from task_params (set by PrereqResolver).
        For location names (SeedShop, Farm, etc.), returns target at current pos for warp.
        For coords, returns target at destination.
        """
        if not task_params:
            return []
        
        destination = task_params.get("destination", "")
        target_coords = task_params.get("target_coords")
        
        # Known warp destinations - execute warp skill at current position
        WARP_DESTINATIONS = {
            "SeedShop": "go_to_pierre",
            "Farm": "warp_to_farm",
            "Town": "warp_to_town",
            "Beach": "warp_to_beach",
            "Mountain": "warp_to_mountain",
            "Forest": "warp_to_forest",
            "Mine": "warp_to_mine",
        }
        
        if destination in WARP_DESTINATIONS:
            # Return target at current position - warp skill handles transport
            return [Target(
                x=player_pos[0],
                y=player_pos[1],
                target_type="warp",
                metadata={
                    "destination": destination,
                    "skill": WARP_DESTINATIONS[destination],
                },
            )]
        
        # For coordinate-based navigation
        if target_coords:
            if isinstance(target_coords, (list, tuple)) and len(target_coords) >= 2:
                x, y = int(target_coords[0]), int(target_coords[1])
                return [Target(
                    x=x,
                    y=y,
                    target_type="navigate",
                    metadata={"destination": destination},
                )]
        
        return []

    def _generate_refill_target(
        self,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        task_params: Optional[Dict[str, Any]],
    ) -> List[Target]:
        """
        Generate single target for refill watering can task.
        
        Player should already be at water source (navigate completed first).
        Returns target at current position - skill will face water and use tool.
        """
        # Target is current player position (already at water source)
        # The refill_watering_can skill will handle facing the water
        direction = "south"  # Default
        if task_params:
            direction = task_params.get("target_direction", "south")
        
        return [Target(
            x=player_pos[0],
            y=player_pos[1],
            target_type="refill",
            metadata={
                "target_direction": direction,
            },
        )]

    def _tiles_from_state(
        self,
        state: Dict[str, Any],
        predicate,
    ) -> List[Target]:
        tiles = self._extract_tiles(state)
        targets: List[Target] = []
        for tile in tiles:
            if not predicate(tile):
                continue
            x = tile.get("x")
            y = tile.get("y")
            if x is None or y is None:
                continue
            targets.append(Target(
                x=int(x),
                y=int(y),
                target_type="tile",
                metadata=dict(tile),
            ))
        return targets

    def _extract_tiles(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tiles from game state (handles both wrapped and unwrapped formats)."""
        data = state.get("data") or state
        tiles = data.get("tiles")
        if isinstance(tiles, list):
            return tiles
        spatial_tiles = data.get("spatial_map") or data.get("spatialMap")
        if isinstance(spatial_tiles, list):
            return spatial_tiles
        return []

    def _is_plantable_tile(self, tile: Dict[str, Any]) -> bool:
        if tile.get("isTilled") and not tile.get("hasCrop") and not tile.get("crop"):
            return True
        if tile.get("state") == "tilled" and not tile.get("crop"):
            return True
        return False

    def _sort_targets(
        self,
        targets: List[Target],
        player_pos: Tuple[int, int],
        strategy: SortStrategy,
    ) -> List[Target]:
        """Apply sorting strategy to target list."""
        if strategy == SortStrategy.ROW_BY_ROW:
            return sorted(targets, key=lambda t: (t.y, t.x))
        if strategy == SortStrategy.NEAREST_FIRST:
            return sorted(
                targets,
                key=lambda t: abs(t.x - player_pos[0]) + abs(t.y - player_pos[1]),
            )
        return targets
