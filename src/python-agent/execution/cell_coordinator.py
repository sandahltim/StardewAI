"""
Cell Farming Coordinator - Orchestrates cell-by-cell farming execution.

Takes a CellFarmingPlan from FarmSurveyor and:
1. Yields cells one at a time for processing
2. Builds dynamic action sequences per cell (based on needs)
3. Tracks completion and handles navigation between cells

Design decisions:
- Each cell fully processed before moving to next
- Dynamic actions based on cell flags (skip completed steps)
- Correct tool selection based on debris type
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from planning.farm_surveyor import CellPlan, CellFarmingPlan

logger = logging.getLogger(__name__)


@dataclass
class CellAction:
    """A single action to perform at a cell."""
    action_type: str  # "select_slot", "select_item", "face", "use_tool"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to action dict for controller."""
        if self.action_type == "select_slot":
            return {"select_slot": self.params.get("slot", 0)}
        elif self.action_type == "select_item":
            return {"select_item": self.params.get("item", "")}
        elif self.action_type == "face":
            return {"face": self.params.get("direction", "north")}
        elif self.action_type == "use_tool":
            return {"use_tool": True}
        return {self.action_type: self.params}


class CellFarmingCoordinator:
    """
    Coordinates cell-by-cell farming execution.

    Usage:
        coordinator = CellFarmingCoordinator(cell_plan)

        while not coordinator.is_complete():
            cell = coordinator.get_current_cell()
            if cell:
                # Navigate to cell if not adjacent
                nav_target = coordinator.get_navigation_target(cell, player_pos)
                if player_pos != nav_target:
                    # Navigate first
                    ...

                # Get and execute actions for this cell
                actions = coordinator.get_cell_actions(cell)
                for action in actions:
                    controller.execute(action.to_dict())

                coordinator.mark_cell_complete(cell)
    """

    # Default tool slots
    HOE_SLOT = 1
    WATERING_CAN_SLOT = 2

    def __init__(self, plan: CellFarmingPlan, tool_map: Optional[Dict[str, int]] = None):
        """
        Initialize with a farming plan.

        Args:
            plan: CellFarmingPlan from FarmSurveyor
        """
        self.plan = plan
        tool_map = tool_map or {}
        self.hoe_slot = tool_map.get("Hoe", self.HOE_SLOT)
        self.watering_can_slot = tool_map.get("Watering Can", self.WATERING_CAN_SLOT)
        self.current_index = 0
        self.completed_cells: Set[Tuple[int, int]] = set()
        self.skipped_cells: Dict[Tuple[int, int], str] = {}  # (x,y) → reason
        self.current_action_index = 0
        self._current_cell_actions: List[CellAction] = []

        logger.info(f"CellCoordinator: Initialized with {len(plan.cells)} cells")

    def is_complete(self) -> bool:
        """Check if all cells have been processed."""
        # Use completed_cells set instead of index (works with dynamic nearest selection)
        return len(self.completed_cells) >= len(self.plan.cells)

    def get_current_cell(self) -> Optional[CellPlan]:
        """Get the current cell to process (or None if complete)."""
        if self.is_complete():
            return None
        return self.plan.cells[self.current_index]

    def get_next_cell(self) -> Optional[CellPlan]:
        """Get next unprocessed cell, advancing past completed ones."""
        while self.current_index < len(self.plan.cells):
            cell = self.plan.cells[self.current_index]
            if (cell.x, cell.y) not in self.completed_cells:
                return cell
            self.current_index += 1
        return None

    def get_nearest_cell(self, player_pos: Tuple[int, int]) -> Optional[CellPlan]:
        """
        Get nearest uncompleted cell to player's current position.

        Uses Manhattan distance for efficiency. This creates natural
        movement patterns - always go to closest cell instead of
        following a fixed order.

        Args:
            player_pos: Current (x, y) player position

        Returns:
            Nearest uncompleted cell, or None if all complete
        """
        # Filter to uncompleted cells
        remaining = [
            cell for cell in self.plan.cells
            if (cell.x, cell.y) not in self.completed_cells
        ]

        if not remaining:
            return None

        # Sort by Manhattan distance to player
        def distance(cell: CellPlan) -> int:
            return abs(cell.x - player_pos[0]) + abs(cell.y - player_pos[1])

        remaining.sort(key=distance)
        nearest = remaining[0]

        logger.debug(f"🌱 Nearest cell to {player_pos}: ({nearest.x},{nearest.y}) dist={distance(nearest)}")
        return nearest

    def get_navigation_target(
        self,
        cell: CellPlan,
        player_pos: Tuple[int, int],
    ) -> Tuple[int, int]:
        """
        Get position to stand when working on cell.

        Strategy: Stand south of cell, face north to work.
        This is the most common pattern for farming.

        Args:
            cell: Cell to work on
            player_pos: Current player position

        Returns:
            (x, y) position to navigate to
        """
        # Stand one tile south of the cell
        return (cell.x, cell.y + 1)

    def get_facing_direction(
        self,
        cell: CellPlan,
        player_pos: Tuple[int, int],
    ) -> str:
        """
        Get direction to face when working on cell.

        Args:
            cell: Cell to work on
            player_pos: Current player position (after navigation)

        Returns:
            Direction string: "north", "south", "east", "west"
        """
        dx = cell.x - player_pos[0]
        dy = cell.y - player_pos[1]

        if abs(dx) > abs(dy):
            return "east" if dx > 0 else "west"
        else:
            return "north" if dy < 0 else "south"

    def get_cell_actions(self, cell: CellPlan) -> List[CellAction]:
        """
        Build action sequence for this cell based on its needs.

        This is the core logic - generates only the actions needed:
        - Skip clear if no debris
        - Skip till if already tilled
        - Skip plant if already planted
        - Skip water if already watered

        Args:
            cell: CellPlan with needs_* flags set

        Returns:
            List of CellAction objects to execute in order
        """
        actions: List[CellAction] = []

        # Always face the cell first
        actions.append(CellAction(
            action_type="face",
            params={"direction": cell.target_direction},
        ))

        # Clear debris if needed
        if cell.needs_clear and cell.debris_type:
            actions.append(CellAction(
                action_type="select_slot",
                params={"slot": cell.clear_tool_slot},
            ))
            actions.append(CellAction(
                action_type="use_tool",
            ))
            logger.debug(f"Cell ({cell.x},{cell.y}): Clear {cell.debris_type} with slot {cell.clear_tool_slot}")

        # Till soil if needed
        if cell.needs_till:
            actions.append(CellAction(
                action_type="select_slot",
                params={"slot": self.hoe_slot},
            ))
            actions.append(CellAction(
                action_type="use_tool",
            ))
            logger.debug(f"Cell ({cell.x},{cell.y}): Till soil")

        # Plant seed if needed - use select_slot (not select_item)
        if cell.needs_plant:
            actions.append(CellAction(
                action_type="select_slot",
                params={"slot": cell.seed_slot},
            ))
            actions.append(CellAction(
                action_type="use_tool",
            ))
            logger.debug(f"Cell ({cell.x},{cell.y}): Plant {cell.seed_type} from slot {cell.seed_slot}")

        # Water if needed
        if cell.needs_water:
            actions.append(CellAction(
                action_type="select_slot",
                params={"slot": self.watering_can_slot},
            ))
            actions.append(CellAction(
                action_type="use_tool",
            ))
            logger.debug(f"Cell ({cell.x},{cell.y}): Water")

        logger.info(f"🌱 Cell ({cell.x},{cell.y}) needs {len(actions)} actions")

        return actions

    def mark_cell_complete(self, cell: CellPlan):
        """
        Mark a cell as complete and advance to next.

        Args:
            cell: The completed cell
        """
        self.completed_cells.add((cell.x, cell.y))
        self.current_index += 1
        self.current_action_index = 0
        self._current_cell_actions = []

        remaining = len(self.plan.cells) - len(self.completed_cells)
        logger.info(f"CellCoordinator: Completed ({cell.x},{cell.y}), {remaining} remaining")
        
        # Persist stats for cross-session access
        self._persist_stats()

    def skip_cell(self, cell: CellPlan, reason: str = ""):
        """
        Skip a cell (e.g., blocked by NPC) and move to next.

        Args:
            cell: Cell to skip
            reason: Why it was skipped
        """
        logger.warning(f"CellCoordinator: Skipping ({cell.x},{cell.y}): {reason}")
        self.completed_cells.add((cell.x, cell.y))
        self.skipped_cells[(cell.x, cell.y)] = reason  # Track skip reason
        self.current_index += 1
        self.current_action_index = 0
        self._current_cell_actions = []
        
        # Persist stats for cross-session access
        self._persist_stats()

    def get_progress(self) -> Tuple[int, int]:
        """Get (completed, total) cell counts."""
        return (len(self.completed_cells), len(self.plan.cells))

    def get_daily_summary(self) -> Dict[str, Any]:
        """
        Generate daily summary for end-of-day persistence.

        Returns dict with:
        - cells_completed: Successfully processed cells
        - cells_skipped: Cells skipped with reasons
        - total_cells: Total in plan
        """
        # Count successfully completed (not skipped)
        successful = self.completed_cells - set(self.skipped_cells.keys())

        return {
            "cells_completed": len(successful),
            "cells_skipped": len(self.skipped_cells),
            "skip_reasons": {f"{x},{y}": reason for (x, y), reason in self.skipped_cells.items()},
            "total_cells": len(self.plan.cells),
            "completion_rate": len(successful) / max(1, len(self.plan.cells)),
        }

    def _persist_stats(self) -> None:
        """
        Persist cell farming stats to file for cross-session access.
        
        Called after each cell completion so that go_to_bed in a separate
        agent instance can load these stats for the daily summary.
        """
        successful = self.completed_cells - set(self.skipped_cells.keys())
        
        stats = {
            "cells_completed": len(successful),
            "cells_skipped": len(self.skipped_cells),
            "skip_reasons": {f"{x},{y}": reason for (x, y), reason in self.skipped_cells.items()},
            "total_cells": len(self.plan.cells),
            "completed_coords": [f"{x},{y}" for x, y in successful],
            "skipped_coords": [f"{x},{y}" for x, y in self.skipped_cells.keys()],
        }
        
        stats_path = Path("logs/cell_farming_stats.json")
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)
        
        logger.debug(f"📊 Stats persisted: {len(successful)} completed, {len(self.skipped_cells)} skipped")

    def get_status_summary(self) -> str:
        """Get human-readable status."""
        completed, total = self.get_progress()
        current = self.get_current_cell()
        if current:
            return f"Cell {completed + 1}/{total}: ({current.x},{current.y})"
        return f"Complete: {completed}/{total} cells"

    # --- Action-by-action execution support ---

    def start_cell_execution(self, cell: CellPlan) -> bool:
        """
        Start executing a cell - call before get_next_action().

        Returns True if there are actions to execute.
        """
        self._current_cell_actions = self.get_cell_actions(cell)
        self.current_action_index = 0
        return len(self._current_cell_actions) > 0

    def get_next_action(self) -> Optional[CellAction]:
        """
        Get next action for current cell (for tick-by-tick execution).

        Returns None when all actions for current cell are done.
        """
        if self.current_action_index >= len(self._current_cell_actions):
            return None
        action = self._current_cell_actions[self.current_action_index]
        self.current_action_index += 1
        return action

    def is_cell_execution_complete(self) -> bool:
        """Check if all actions for current cell have been yielded."""
        return self.current_action_index >= len(self._current_cell_actions)


# Singleton instance
_cell_coordinator: Optional[CellFarmingCoordinator] = None


def get_cell_coordinator() -> Optional[CellFarmingCoordinator]:
    """Get the current cell coordinator (if active)."""
    return _cell_coordinator


def set_cell_coordinator(coordinator: Optional[CellFarmingCoordinator]):
    """Set the active cell coordinator."""
    global _cell_coordinator
    _cell_coordinator = coordinator
