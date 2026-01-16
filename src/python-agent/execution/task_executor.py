"""
Task Executor - Deterministic task execution with spatial targeting.

Sits between Daily Planner and Skill Executor:
    Daily Planner → Task Executor → Skill Executor

Provides systematic, row-by-row execution instead of chaotic VLM decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from execution.target_generator import SortStrategy, Target, TargetGenerator

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """State machine for task execution."""
    IDLE = "idle"                    # No task active
    MOVING_TO_TARGET = "moving"      # Walking to next target
    EXECUTING_AT_TARGET = "executing"  # Performing action at target
    NEEDS_REFILL = "needs_refill"    # Watering can empty, need to refill first
    TASK_COMPLETE = "complete"       # All targets done
    INTERRUPTED = "interrupted"      # Higher priority task available
    BLOCKED = "blocked"              # 0 targets generated (pathfinding failed, need to retry)      # Higher priority task available


class CommentaryEvent(Enum):
    """Events that trigger VLM commentary."""
    TASK_STARTED = "task_started"
    MILESTONE_25 = "milestone_25"
    MILESTONE_50 = "milestone_50"
    MILESTONE_75 = "milestone_75"
    TASK_COMPLETE = "task_complete"
    TARGET_FAILED = "target_failed"
    ROW_CHANGE = "row_change"
    FALLBACK_TICK = "fallback_tick"


@dataclass
class TaskProgress:
    """Progress tracking for current task."""
    task_id: str
    task_type: str
    total_targets: int
    completed_targets: int = 0
    failed_targets: int = 0
    skipped_targets: int = 0  # Targets skipped due to stale state (already tilled/watered)
    current_target_index: int = 0
    
    @property
    def remaining(self) -> int:
        return self.total_targets - self.completed_targets - self.failed_targets - self.skipped_targets
    
    @property
    def progress_pct(self) -> float:
        if self.total_targets == 0:
            return 100.0
        return (self.completed_targets / self.total_targets) * 100
    
    def to_context(self) -> str:
        """Format for VLM context injection."""
        return (
            f"CURRENT TASK: {self.task_type} "
            f"({self.completed_targets}/{self.total_targets} done, "
            f"{self.remaining} remaining)"
        )


@dataclass
class ExecutorAction:
    """Action to execute - either move or skill."""
    action_type: str              # "move" or skill name like "water_crop"
    params: Dict[str, Any] = field(default_factory=dict)
    target: Optional[Target] = None
    reason: str = ""              # For logging/commentary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to format expected by skill executor."""
        return {
            "type": self.action_type,
            **self.params
        }


class TaskExecutor:
    """
    Deterministic task execution engine.
    
    Converts high-level tasks into ordered spatial targets,
    then provides one action at a time until task complete.
    
    Usage:
        executor = TaskExecutor()
        executor.set_task("water_crops", game_state, player_pos)
        
        while not executor.is_complete():
            action = executor.get_next_action(player_pos, surroundings)
            if action:
                success = execute(action)
                executor.report_result(success)
    """
    
    # Map task types to skill names
    TASK_TO_SKILL = {
        "water_crops": "water_crop",
        "harvest_crops": "harvest_crop",
        "clear_debris": None,  # Determined by debris type
        "till_soil": "till_soil",
        "plant_seeds": "plant_seed",
        "ship_items": "ship_item",
        "navigate": None,  # No skill - just movement to destination
        "refill_watering_can": "refill_watering_can",
        "buy_seeds": "buy_seeds",  # Generic - uses seed_type param from prereq resolver
        # Mining - Session 122
        "mining": "warp_to_mine",  # First step: get to mine, then VLM handles break_rock/use_ladder
    }
    
    # Map debris names to clearing skills
    DEBRIS_SKILLS = {
        "Stone": "clear_stone",
        "Weeds": "clear_weeds",
        "Twig": "clear_wood",
        "Wood": "clear_wood",
    }
    
    def __init__(self, target_generator: Optional[TargetGenerator] = None):
        self.target_gen = target_generator or TargetGenerator()
        self.state = TaskState.IDLE
        self.targets: List[Target] = []
        self.current_index: int = 0
        self.progress: Optional[TaskProgress] = None
        self.tick_count: int = 0  # For hybrid VLM mode
        self._consecutive_failures: int = 0
        self._max_failures: int = 3  # Give up on target after 3 failures
        self._task_params: Optional[Dict[str, Any]] = None  # Params from PrereqResolver
        # Event-driven commentary
        self._event_queue: List[Tuple[CommentaryEvent, str]] = []
        self._last_row: Optional[int] = None  # Track row changes
        self._milestone_hits: Set[CommentaryEvent] = set()  # Track which milestones triggered
        # Stuck detection for movement
        self._last_move_pos: Optional[Tuple[int, int]] = None
        self._stuck_count: int = 0
        self._max_stuck: int = 3  # Try to clear obstacle after 3 stuck attempts
        self._clearing_obstacle: bool = False  # Currently clearing an obstacle

    def _queue_event(self, event: CommentaryEvent, context: str = "") -> None:
        """Queue a commentary event for VLM to react to."""
        self._event_queue.append((event, context))
        logger.debug(f"TaskExecutor: Queued event {event.value}: {context}")

    def _check_milestone(self) -> None:
        """Check if we've hit a progress milestone."""
        if self.progress is None or self.progress.total_targets == 0:
            return

        pct = self.progress.progress_pct

        if pct >= 25 and CommentaryEvent.MILESTONE_25 not in self._milestone_hits:
            self._milestone_hits.add(CommentaryEvent.MILESTONE_25)
            self._queue_event(
                CommentaryEvent.MILESTONE_25,
                f"Quarter done! {self.progress.completed_targets}/{self.progress.total_targets}"
            )
        elif pct >= 50 and CommentaryEvent.MILESTONE_50 not in self._milestone_hits:
            self._milestone_hits.add(CommentaryEvent.MILESTONE_50)
            self._queue_event(
                CommentaryEvent.MILESTONE_50,
                f"Halfway there! {self.progress.completed_targets}/{self.progress.total_targets}"
            )
        elif pct >= 75 and CommentaryEvent.MILESTONE_75 not in self._milestone_hits:
            self._milestone_hits.add(CommentaryEvent.MILESTONE_75)
            self._queue_event(
                CommentaryEvent.MILESTONE_75,
                f"Almost done! {self.progress.completed_targets}/{self.progress.total_targets}"
            )

    def set_task(
        self,
        task_id: str,
        task_type: str,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        strategy: SortStrategy = SortStrategy.ROW_BY_ROW,
        task_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Initialize executor with a new task.

        Args:
            task_params: Optional params from PrereqResolver (e.g., destination coords)

        Returns True if task has targets, False if nothing to do (blocked or no targets).
        """
        self._task_params = task_params
        self.targets = self.target_gen.generate(
            task_type, game_state, player_pos, strategy, task_params
        )
        
        if not self.targets:
            logger.info(f"TaskExecutor: No targets for {task_type} - marking BLOCKED (not complete)")
            # Don't mark as complete! Mark as blocked so it can be retried later
            # This fixes the bug where water task completes with 0 targets from FarmHouse
            self.state = TaskState.BLOCKED
            self.progress = TaskProgress(
                task_id=task_id,
                task_type=task_type,
                total_targets=0,
            )
            return False
        
        self.current_index = 0
        self.tick_count = 0
        self._consecutive_failures = 0
        self.state = TaskState.MOVING_TO_TARGET

        # Reset event tracking for new task
        self._event_queue.clear()
        self._milestone_hits.clear()
        self._last_row = self.targets[0].y if self.targets else None

        self.progress = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            total_targets=len(self.targets),
        )

        # Queue task started event
        self._queue_event(
            CommentaryEvent.TASK_STARTED,
            f"Starting {task_type} with {len(self.targets)} targets"
        )

        logger.info(
            f"🎯 TaskExecutor: Started {task_type} with {len(self.targets)} targets "
            f"(strategy={strategy.value})"
        )
        return True
    
    def get_next_action(
        self,
        player_pos: Tuple[int, int],
        surroundings: Optional[Dict[str, Any]] = None,
        game_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[ExecutorAction]:
        """
        Get the next deterministic action to execute.
        
        Returns None if task is complete or no action needed.
        Checks preconditions (e.g., watering can full) before execution.
        """
        if self.state in (TaskState.IDLE, TaskState.TASK_COMPLETE, TaskState.INTERRUPTED):
            return None

        if self.current_index >= len(self.targets):
            self.state = TaskState.TASK_COMPLETE
            return None

        # If already in NEEDS_REFILL state, don't spam precondition actions
        # Instead, check if we're now adjacent to water - if so, do the refill
        if self.state == TaskState.NEEDS_REFILL:
            is_adjacent_to_water = False
            target_direction = "south"
            if surroundings:
                dirs = surroundings.get("directions", {})
                for direction in ["north", "south", "east", "west"]:
                    dir_data = dirs.get(direction, {})
                    blocker = dir_data.get("blocker", "")
                    tiles_until = dir_data.get("tilesUntilBlocked", 99)
                    if blocker and "water" in blocker.lower() and tiles_until == 0:
                        is_adjacent_to_water = True
                        target_direction = direction
                        break
                nearest_water = surroundings.get("nearestWater", {})
                if not is_adjacent_to_water and nearest_water.get("distance", 99) <= 1:
                    is_adjacent_to_water = True
                    target_direction = nearest_water.get("direction", "south").lower()

            if is_adjacent_to_water:
                # Now adjacent! Return refill action and move to normal state
                logger.info(f"💧 Now adjacent to water - refilling")
                self.state = TaskState.EXECUTING_AT_TARGET
                return ExecutorAction(
                    action_type="refill_watering_can",
                    params={"target_direction": target_direction},
                    reason=f"Refilling watering can (arrived at water)",
                )
            else:
                # Still waiting for pathfinding - return None to let agent poll
                logger.debug(f"💧 NEEDS_REFILL: waiting for arrival at water...")
                return None

        # Check preconditions before executing task
        prereq_action = self._check_preconditions(game_state, surroundings)
        if prereq_action:
            self.state = TaskState.NEEDS_REFILL
            return prereq_action
        
        self.tick_count += 1
        target = self.targets[self.current_index]

        # Check for row change (moving to new y coordinate)
        if self._last_row is not None and target.y != self._last_row:
            self._queue_event(
                CommentaryEvent.ROW_CHANGE,
                f"Moving to row {target.y}"
            )
            self._last_row = target.y

        # Calculate distance to target
        dx = target.x - player_pos[0]
        dy = target.y - player_pos[1]
        distance = abs(dx) + abs(dy)

        # Check if player is indoors - need to warp to Farm first
        if game_state:
            data = game_state.get("data") or game_state
            location = data.get("location", {})
            location_name = location.get("name", "") if isinstance(location, dict) else ""

            # For location-based navigate tasks: if at destination location, complete immediately
            # This fixes the bug where player exits FarmHouse to Farm but task still targets old coords
            if target.target_type == "warp" and target.metadata.get("destination"):
                dest_location = target.metadata["destination"]
                if location_name == dest_location:
                    logger.info(f"🎯 Navigate complete: arrived at {dest_location} location")
                    if self.progress:
                        self.progress.completed_targets += 1
                    self.current_index += 1
                    self._check_milestone()
                    if self.current_index >= len(self.targets):
                        self.state = TaskState.TASK_COMPLETE
                        self._queue_event(
                            CommentaryEvent.TASK_COMPLETE,
                            f"Arrived at {dest_location}"
                        )
                        logger.info(f"✅ TaskExecutor: Navigate task COMPLETE")
                        return None
                    return None

            if location_name and location_name not in ("Farm", ""):
                # Special case: At SeedShop with no seeds = stay to buy seeds first
                if location_name == "SeedShop":
                    inventory = data.get("inventory", [])
                    has_seeds = any(
                        item and "seed" in item.get("name", "").lower()
                        for item in inventory if item
                    )
                    if not has_seeds:
                        # Don't warp to Farm - need to buy seeds first
                        logger.info(f"🛒 At SeedShop with no seeds - skipping Farm warp, need to buy")
                        # Clear current task and let VLM override handle buy_seeds
                        self.state = TaskState.INTERRUPTED
                        return None

                # Player is indoors, warp to Farm to navigate to outdoor target
                logger.info(f"🚪 Player in {location_name}, warping to Farm first")
                self.state = TaskState.MOVING_TO_TARGET
                return ExecutorAction(
                    action_type="warp",
                    params={"location": "Farm"},
                    target=target,
                    reason=f"Exiting {location_name} to reach target at ({target.x}, {target.y})"
                )

        # If not adjacent (distance > 1), need to move
        if distance > 1:
            # Stuck detection: check if position hasn't changed
            if self._last_move_pos == player_pos and self.state == TaskState.MOVING_TO_TARGET:
                self._stuck_count += 1
                logger.warning(f"TaskExecutor: Stuck at {player_pos} ({self._stuck_count}/{self._max_stuck})")

                # After max stuck attempts, try to clear obstacle
                if self._stuck_count >= self._max_stuck:
                    clear_action = self._try_clear_obstacle(player_pos, target, dx, dy, surroundings)
                    if clear_action:
                        logger.info(f"🪓 TaskExecutor: Clearing obstacle to reach target")
                        self._stuck_count = 0  # Reset after attempting clear
                        return clear_action
                    else:
                        # No clearable obstacle - skip this target
                        logger.warning(f"TaskExecutor: Can't clear path, skipping target at ({target.x}, {target.y})")
                        self._stuck_count = 0
                        self.current_index += 1
                        if self.progress:
                            self.progress.failed_targets += 1
                        if self.current_index >= len(self.targets):
                            self.state = TaskState.TASK_COMPLETE
                            return None
                        # Try next target
                        self._last_move_pos = None
                        return None
            else:
                # Position changed, reset stuck counter
                self._stuck_count = 0

            self._last_move_pos = player_pos
            self.state = TaskState.MOVING_TO_TARGET
            return self._create_move_action(player_pos, target, dx, dy, surroundings)

        # Check if this task type requires a skill at target
        skill_name = self._get_skill_for_target(target)
        if skill_name is None:
            # No skill needed (e.g., navigate) - just reaching target completes it
            logger.info(f"🎯 Navigate complete: reached ({target.x}, {target.y})")
            # Manually complete this target (report_result only works for EXECUTING_AT_TARGET)
            if self.progress:
                self.progress.completed_targets += 1
            self.current_index += 1
            self._check_milestone()
            # Check if there are more targets
            if self.current_index >= len(self.targets):
                self.state = TaskState.TASK_COMPLETE
                self._queue_event(
                    CommentaryEvent.TASK_COMPLETE,
                    f"Reached destination"
                )
                logger.info(f"✅ TaskExecutor: Navigate task COMPLETE")
                return None
            # Return None to advance to next target on next tick
            return None

        # Adjacent or on target - validate target is still valid before executing
        skip_reason = self._should_skip_target(target, game_state, surroundings)
        if skip_reason:
            logger.info(f"⏭️ TaskExecutor: Skipping target ({target.x}, {target.y}) - {skip_reason}")
            self.current_index += 1
            if self.progress:
                self.progress.skipped_targets = getattr(self.progress, 'skipped_targets', 0) + 1
            self._check_milestone()
            if self.current_index >= len(self.targets):
                self.state = TaskState.TASK_COMPLETE
                self._queue_event(
                    CommentaryEvent.TASK_COMPLETE,
                    f"Task complete ({skip_reason} on last target)"
                )
                return None
            # Return None to advance to next target on next tick
            return None

        # Execute skill
        self.state = TaskState.EXECUTING_AT_TARGET
        return self._create_skill_action(player_pos, target, dx, dy)
    
    def _check_preconditions(
        self,
        game_state: Optional[Dict[str, Any]],
        surroundings: Optional[Dict[str, Any]],
    ) -> Optional[ExecutorAction]:
        """
        Check if preconditions are met for current task.
        
        Returns an action to satisfy precondition if not met, None if OK.
        
        Preconditions:
        - water_crops: watering can must have water
        - plant_seeds: must have seeds in inventory (future)
        """
        if not self.progress:
            return None
        
        task_type = self.progress.task_type
        
        # Extract player data from game state
        data = (game_state.get("data") or game_state) if game_state else {}
        player = data.get("player", {})
        
        if task_type == "water_crops":
            # Check watering can water level
            water_level = player.get("wateringCanWater", 0)
            water_max = player.get("wateringCanMax", 40)

            if water_level <= 0:
                logger.info(f"💧 Watering can empty ({water_level}/{water_max}) - need to refill")

                # First check if we're adjacent to water
                is_adjacent_to_water = False
                target_direction = "south"  # Default direction

                if surroundings:
                    # Check each direction for water
                    dirs = surroundings.get("directions", {})
                    for direction in ["north", "south", "east", "west"]:
                        dir_data = dirs.get(direction, {})
                        blocker = dir_data.get("blocker", "")
                        tiles_until = dir_data.get("tilesUntilBlocked", 99)
                        if blocker and "water" in blocker.lower() and tiles_until == 0:
                            is_adjacent_to_water = True
                            target_direction = direction
                            break

                    # Also check nearestWater
                    nearest_water = surroundings.get("nearestWater", {})
                    if not is_adjacent_to_water and nearest_water.get("distance", 99) <= 1:
                        is_adjacent_to_water = True
                        target_direction = nearest_water.get("direction", "south").lower()

                if is_adjacent_to_water:
                    # Adjacent to water - refill directly
                    logger.info(f"💧 Adjacent to water ({target_direction}) - refilling can")
                    return ExecutorAction(
                        action_type="refill_watering_can",
                        params={"target_direction": target_direction},
                        reason=f"Watering can empty - refilling (adjacent to water)",
                    )
                else:
                    # NOT adjacent to water - navigate there first
                    logger.info(f"💧 Not adjacent to water - navigating to water source first")
                    return ExecutorAction(
                        action_type="navigate_to_water",
                        params={},
                        reason=f"Watering can empty - navigating to water source",
                    )
        
        # Future: add plant_seeds check for seeds in inventory
        # Future: add clear_debris check for appropriate tools
        
        return None  # All preconditions met
    
    def _create_move_action(
        self,
        player_pos: Tuple[int, int],
        target: Target,
        dx: int,
        dy: int,
        surroundings: Optional[Dict[str, Any]] = None,
    ) -> ExecutorAction:
        """Create move action toward target (stop 1 tile away).

        Uses move_to for direct A* pathfinding via SMAPI - much faster than step-by-step.
        Calculates adjacent position to stop at (for skill execution).
        """
        # Calculate adjacent position (1 tile from target, toward player)
        # Pick the adjacent tile that's closest to player
        adjacent_positions = [
            (target.x - 1, target.y),  # west of target
            (target.x + 1, target.y),  # east of target
            (target.x, target.y - 1),  # north of target
            (target.x, target.y + 1),  # south of target
        ]

        # Find closest adjacent position to player
        best_pos = adjacent_positions[0]
        best_dist = abs(player_pos[0] - best_pos[0]) + abs(player_pos[1] - best_pos[1])
        for pos in adjacent_positions[1:]:
            dist = abs(player_pos[0] - pos[0]) + abs(player_pos[1] - pos[1])
            if dist < best_dist:
                best_dist = dist
                best_pos = pos

        return ExecutorAction(
            action_type="move_to",
            params={"x": best_pos[0], "y": best_pos[1]},
            target=target,
            reason=f"Pathfinding to adjacent ({best_pos[0]}, {best_pos[1]}) for target ({target.x}, {target.y})"
        )
    
    def _should_skip_target(
        self,
        target: Target,
        game_state: Optional[Dict[str, Any]],
        surroundings: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Check if target should be skipped based on current state.
        
        Returns reason string if should skip, None if target is valid.
        This prevents phantom failures from stale targets.
        """
        if not game_state and not surroundings:
            return None  # Can't validate without state
        
        task_type = self.progress.task_type if self.progress else ""
        
        # For till tasks: check if tile is already tilled
        if task_type == "till_soil":
            # Check surroundings for tile state
            if surroundings:
                tiles = surroundings.get("data", {}).get("tiles", [])
                if not tiles:
                    tiles = surroundings.get("tiles", [])
                for tile in tiles:
                    if tile.get("x") == target.x and tile.get("y") == target.y:
                        if tile.get("isTilled"):
                            return "already_tilled"
                        break
        
        # For water tasks: check if crop exists and is already watered
        if task_type == "water_crops":
            # game_state is already the "data" content from /state endpoint
            crops = game_state.get("location", {}).get("crops", []) if game_state else []
            crop_found = False
            for crop in crops:
                if crop.get("x") == target.x and crop.get("y") == target.y:
                    crop_found = True
                    if crop.get("isWatered"):
                        return "already_watered"
                    break
            # If no crop at target position, target is stale
            if not crop_found:
                return "no_crop_at_target"

        # For harvest tasks: check if crop exists and is ready
        if task_type == "harvest_crops":
            # game_state is already the "data" content from /state endpoint
            crops = game_state.get("location", {}).get("crops", []) if game_state else []
            crop_found = False
            for crop in crops:
                if crop.get("x") == target.x and crop.get("y") == target.y:
                    crop_found = True
                    if not crop.get("isReadyForHarvest"):
                        return "not_ready_for_harvest"
                    break
            if not crop_found:
                return "no_crop_at_target"

        # For plant tasks: check if tile already has a crop
        if task_type == "plant_seeds":
            if surroundings:
                tiles = surroundings.get("data", {}).get("tiles", [])
                if not tiles:
                    tiles = surroundings.get("tiles", [])
                for tile in tiles:
                    if tile.get("x") == target.x and tile.get("y") == target.y:
                        if tile.get("isOccupied") or tile.get("hasCrop"):
                            return "already_planted"
                        break
        
        return None  # Target is valid

    def _create_skill_action(
        self,
        player_pos: Tuple[int, int],
        target: Target,
        dx: int,
        dy: int,
    ) -> ExecutorAction:
        """Create skill action when adjacent to target."""
        # Check if direction is specified in target metadata (e.g., refill tasks)
        direction = target.metadata.get("target_direction")

        if not direction:
            # Determine facing direction (toward target)
            if dx == 0 and dy == 0:
                # Standing on target - pick a direction (shouldn't happen often)
                direction = "south"
            elif abs(dx) >= abs(dy):
                direction = "east" if dx > 0 else "west"
            else:
                direction = "south" if dy > 0 else "north"

        # Get skill name based on task and target
        skill_name = self._get_skill_for_target(target)

        # Build params - start with direction, merge task params if any
        params = {"target_direction": direction}
        if self._task_params:
            # Merge task params (e.g., seed_type, quantity for buy_seeds)
            params.update(self._task_params)

        return ExecutorAction(
            action_type=skill_name,
            params=params,
            target=target,
            reason=f"Executing {skill_name} on target at ({target.x}, {target.y})"
        )
    
    def _get_skill_for_target(self, target: Target) -> Optional[str]:
        """Determine which skill to use for this target. Returns None for navigate tasks."""
        if self.progress is None:
            return "interact"

        task_type = self.progress.task_type

        # Check if target has explicit skill in metadata (e.g., warp targets)
        if target.metadata.get("skill"):
            return target.metadata["skill"]

        # Debris needs specific tool based on type
        if task_type == "clear_debris":
            debris_name = target.metadata.get("name", "")
            return self.DEBRIS_SKILLS.get(debris_name, "clear_weeds")

        # Navigate returns None - no skill needed
        skill = self.TASK_TO_SKILL.get(task_type)
        if skill is None and task_type not in self.TASK_TO_SKILL:
            # Unknown task type - fallback to interact
            return "interact"
        return skill  # May be None for navigate  # May be None for navigate

    def _try_clear_obstacle(
        self,
        player_pos: Tuple[int, int],
        target: Target,
        dx: int,
        dy: int,
        surroundings: Optional[Dict[str, Any]],
    ) -> Optional[ExecutorAction]:
        """
        Check if there's a clearable obstacle blocking the path and return action to clear it.

        Returns ExecutorAction to clear obstacle, or None if no clearable obstacle found.
        """
        if not surroundings:
            return None

        # Determine which direction we're trying to move
        if abs(dy) > abs(dx):
            direction = "south" if dy > 0 else "north"
        else:
            direction = "east" if dx > 0 else "west"

        # Get objects from surroundings
        data = surroundings.get("data") or surroundings
        nearby = data.get("nearby", {})
        objects = nearby.get("objects", [])

        # Calculate position in the direction we want to move
        offset = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
        check_x = player_pos[0] + offset[direction][0]
        check_y = player_pos[1] + offset[direction][1]

        # Clearable obstacles and their tools
        CLEARABLE = {
            "Tree": "clear_tree",      # Axe
            "Stone": "clear_stone",    # Pickaxe
            "Weeds": "clear_weeds",    # Scythe
            "Twig": "clear_wood",      # Axe
            "Wood": "clear_wood",      # Axe
            "Grass": "clear_weeds",    # Scythe
        }

        # Check if there's a clearable obstacle at that position
        for obj in objects:
            obj_x = obj.get("x", obj.get("tileX", -1))
            obj_y = obj.get("y", obj.get("tileY", -1))
            obj_name = obj.get("name", "")

            if obj_x == check_x and obj_y == check_y:
                if obj_name in CLEARABLE:
                    skill = CLEARABLE[obj_name]
                    logger.info(f"🪓 Found clearable obstacle: {obj_name} at ({obj_x}, {obj_y})")
                    return ExecutorAction(
                        action_type=skill,
                        params={"target_direction": direction},
                        target=Target(x=obj_x, y=obj_y, target_type="obstacle", metadata={"name": obj_name}),
                        reason=f"Clearing {obj_name} blocking path to target"
                    )
                else:
                    logger.debug(f"Non-clearable obstacle: {obj_name} at ({obj_x}, {obj_y})")

        return None

    def report_result(self, success: bool, error: Optional[str] = None) -> None:
        """
        Report result of last action execution.
        
        Updates progress and advances to next target on success.
        """
        if self.progress is None:
            return
        
        if success:
            self._consecutive_failures = 0

            # Only count as complete if we were executing (not moving)
            if self.state == TaskState.EXECUTING_AT_TARGET:
                self.progress.completed_targets += 1
                self.current_index += 1
                logger.info(
                    f"TaskExecutor: Target complete "
                    f"({self.progress.completed_targets}/{self.progress.total_targets})"
                )

                # Check for milestone events
                self._check_milestone()

                # Check if all done
                if self.current_index >= len(self.targets):
                    self.state = TaskState.TASK_COMPLETE
                    self._queue_event(
                        CommentaryEvent.TASK_COMPLETE,
                        f"Finished {self.progress.task_type}! "
                        f"{self.progress.completed_targets} done, {self.progress.failed_targets} failed"
                    )
                    logger.info(f"✅ TaskExecutor: Task {self.progress.task_type} COMPLETE")
                else:
                    self.state = TaskState.MOVING_TO_TARGET
        else:
            self._consecutive_failures += 1
            logger.warning(
                f"TaskExecutor: Action failed ({self._consecutive_failures}/{self._max_failures}): {error}"
            )

            # Give up on this target after too many failures
            if self._consecutive_failures >= self._max_failures:
                self.progress.failed_targets += 1
                self.current_index += 1
                self._consecutive_failures = 0

                self._queue_event(
                    CommentaryEvent.TARGET_FAILED,
                    f"Couldn't complete target, moving on ({self.progress.failed_targets} failed so far)"
                )
                logger.warning(
                    f"TaskExecutor: Skipping target after {self._max_failures} failures"
                )

                if self.current_index >= len(self.targets):
                    self.state = TaskState.TASK_COMPLETE
                    self._queue_event(
                        CommentaryEvent.TASK_COMPLETE,
                        f"Finished {self.progress.task_type}! "
                        f"{self.progress.completed_targets} done, {self.progress.failed_targets} failed"
                    )
    
    def interrupt(self, reason: str = "") -> None:
        """Interrupt current task (for priority switching)."""
        if self.state not in (TaskState.IDLE, TaskState.TASK_COMPLETE):
            logger.info(f"TaskExecutor: Interrupted - {reason}")
            self.state = TaskState.INTERRUPTED

    def clear(self) -> None:
        """Reset executor to idle state, clearing all task data."""
        self.state = TaskState.IDLE
        self.targets = []
        self.current_index = 0
        self.progress = None
        self.tick_count = 0
        self._consecutive_failures = 0
        self._task_params = None
        self._event_queue.clear()
        self._last_row = None
        self._milestone_hits.clear()
        self._last_move_pos = None
        self._stuck_count = 0
        self._clearing_obstacle = False
        logger.debug("TaskExecutor: Cleared")

    def is_complete(self) -> bool:
        """Check if current task is done."""
        return self.state in (TaskState.TASK_COMPLETE, TaskState.IDLE)

    def is_blocked(self) -> bool:
        """Check if current task is blocked (0 targets, needs retry from different position)."""
        return self.state == TaskState.BLOCKED
    
    def is_active(self) -> bool:
        """Check if actively executing a task."""
        # Include NEEDS_REFILL to prevent task restart during precondition handling
        return self.state in (TaskState.MOVING_TO_TARGET, TaskState.EXECUTING_AT_TARGET, TaskState.NEEDS_REFILL)
    
    def should_vlm_comment(self, interval: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Check if VLM should provide commentary this tick.

        Event-driven: VLM comments when something interesting happens,
        or every N ticks as fallback.

        Returns:
            (should_comment, event_context) - event_context is None for fallback ticks
        """
        # Priority 1: Pending events (interesting things happened)
        if self._event_queue:
            event, context = self._event_queue.pop(0)
            logger.info(f"🎭 Commentary trigger: {event.value} - {context}")
            return True, f"[{event.value}] {context}"

        # Priority 2: Fallback interval (keep commentary flowing)
        if self.tick_count % interval == 0:
            return True, None

        return False, None

    def get_pending_event(self) -> Optional[Tuple[CommentaryEvent, str]]:
        """Get next pending event without consuming it (for logging/UI)."""
        if self._event_queue:
            return self._event_queue[0]
        return None

    def has_pending_events(self) -> bool:
        """Check if there are events waiting to trigger commentary."""
        return len(self._event_queue) > 0
    
    def get_current_target(self) -> Optional[Target]:
        """Get the current target being worked on."""
        if 0 <= self.current_index < len(self.targets):
            return self.targets[self.current_index]
        return None
    
    def get_context_for_vlm(self) -> str:
        """
        Get task context string for VLM prompt injection.
        
        Returns focused context about current task and progress.
        """
        if self.progress is None:
            return ""
        
        lines = [
            f"🎯 {self.progress.to_context()}",
        ]
        
        target = self.get_current_target()
        if target:
            lines.append(f"   Next: ({target.x}, {target.y}) - {target.target_type}")
        
        # Show next few targets
        remaining = self.targets[self.current_index:self.current_index + 3]
        if len(remaining) > 1:
            coords = ", ".join(f"({t.x},{t.y})" for t in remaining[1:])
            lines.append(f"   Queue: {coords}")
        
        return "\n".join(lines)
    
    def to_api_format(self) -> Dict[str, Any]:
        """Format for UI API consumption."""
        return {
            "state": self.state.value,
            "progress": {
                "task_id": self.progress.task_id if self.progress else None,
                "task_type": self.progress.task_type if self.progress else None,
                "total": self.progress.total_targets if self.progress else 0,
                "completed": self.progress.completed_targets if self.progress else 0,
                "failed": self.progress.failed_targets if self.progress else 0,
                "remaining": self.progress.remaining if self.progress else 0,
                "percent": self.progress.progress_pct if self.progress else 0,
            } if self.progress else None,
            "current_target": {
                "x": self.targets[self.current_index].x,
                "y": self.targets[self.current_index].y,
                "type": self.targets[self.current_index].target_type,
            } if self.targets and self.current_index < len(self.targets) else None,
            "tick_count": self.tick_count,
        }
