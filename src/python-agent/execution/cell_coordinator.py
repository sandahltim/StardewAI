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

import logging
from dataclasses import dataclass, field
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

    # Tool slots
    HOE_SLOT = 1
    WATERING_CAN_SLOT = 2

    def __init__(self, plan: CellFarmingPlan):
        """
        Initialize with a farming plan.

        Args:
            plan: CellFarmingPlan from FarmSurveyor
        """
        self.plan = plan
        self.current_index = 0
        self.completed_cells: Set[Tuple[int, int]] = set()
        self.current_action_index = 0
        self._current_cell_actions: List[CellAction] = []

        logger.info(f"CellCoordinator: Initialized with {len(plan.cells)} cells")

    def is_complete(self) -> bool:
        """Check if all cells have been processed."""
        return self.current_index >= len(self.plan.cells)

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
                params={"slot": self.HOE_SLOT},
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
                params={"slot": self.WATERING_CAN_SLOT},
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

    def skip_cell(self, cell: CellPlan, reason: str = ""):
        """
        Skip a cell (e.g., blocked by NPC) and move to next.

        Args:
            cell: Cell to skip
            reason: Why it was skipped
        """
        logger.warning(f"CellCoordinator: Skipping ({cell.x},{cell.y}): {reason}")
        self.completed_cells.add((cell.x, cell.y))
        self.current_index += 1
        self.current_action_index = 0
        self._current_cell_actions = []

    def get_progress(self) -> Tuple[int, int]:
        """Get (completed, total) cell counts."""
        return (len(self.completed_cells), len(self.plan.cells))

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
