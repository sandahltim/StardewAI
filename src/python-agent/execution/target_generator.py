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
    ) -> List[Target]:
        """
        Main entry point. Dispatches to task-specific generators.

        Args:
            task_type: "water_crops", "harvest_crops", "clear_debris",
                      "till_soil", "plant_seeds"
            game_state: From SMAPI /state endpoint
            player_pos: (x, y) current player position
            strategy: How to sort targets

        Returns:
            Ordered list of Target objects
        """
        dispatch = {
            "water_crops": self._generate_water_targets,
            "harvest_crops": self._generate_harvest_targets,
            "clear_debris": self._generate_debris_targets,
            "till_soil": self._generate_till_targets,
            "plant_seeds": self._generate_plant_targets,
        }
        generator = dispatch.get(task_type)
        if not generator:
            return []
        return generator(game_state, player_pos, strategy)

    def _extract_crops(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract crops from game state (handles both data.crops and data.location.crops)."""
        data = state.get("data") or {}
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
        """Extract objects from game state (handles both data.objects and data.location.objects)."""
        data = state.get("data") or {}
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
        return self._sort_targets(targets, pos, strategy)

    def _generate_till_targets(
        self,
        state: Dict[str, Any],
        pos: Tuple[int, int],
        strategy: SortStrategy,
    ) -> List[Target]:
        """Get tillable tiles - clear ground that canTill=True."""
        targets = self._tiles_from_state(
            state,
            predicate=lambda tile: tile.get("canTill") and not tile.get("isTilled"),
        )
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
        data = state.get("data") or {}
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
