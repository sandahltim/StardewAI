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
    current_target_index: int = 0
    
    @property
    def remaining(self) -> int:
        return self.total_targets - self.completed_targets - self.failed_targets
    
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
        # Event-driven commentary
        self._event_queue: List[Tuple[CommentaryEvent, str]] = []
        self._last_row: Optional[int] = None  # Track row changes
        self._milestone_hits: Set[CommentaryEvent] = set()  # Track which milestones triggered

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
    ) -> bool:
        """
        Initialize executor with a new task.
        
        Returns True if task has targets, False if nothing to do.
        """
        self.targets = self.target_gen.generate(
            task_type, game_state, player_pos, strategy
        )
        
        if not self.targets:
            logger.info(f"TaskExecutor: No targets for {task_type}")
            self.state = TaskState.TASK_COMPLETE
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
        
        # If not adjacent (distance > 1), need to move
        if distance > 1:
            self.state = TaskState.MOVING_TO_TARGET
            return self._create_move_action(player_pos, target, dx, dy)
        
        # Adjacent or on target - execute skill
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
                logger.info(f"💧 Watering can empty ({water_level}/{water_max}) - need to refill first")
                
                # Determine direction to water source from surroundings
                target_direction = "south"  # Default - water is usually south on farm
                if surroundings:
                    dirs = surroundings.get("directions", {})
                    # Find water direction from landmarks
                    landmarks = data.get("landmarks", {})
                    water_info = landmarks.get("water", {})
                    if water_info.get("direction"):
                        target_direction = water_info.get("direction", "south").lower()
                
                return ExecutorAction(
                    action_type="refill_watering_can",
                    params={"target_direction": target_direction},
                    reason=f"Watering can empty - refilling before watering crops",
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
    ) -> ExecutorAction:
        """Create move action toward target (stop 1 tile away)."""
        # Determine primary direction (larger delta first for efficiency)
        if abs(dy) > abs(dx):
            direction = "south" if dy > 0 else "north"
            # Move to 1 tile away
            tiles = abs(dy) - 1 if abs(dy) > 1 else 0
        else:
            direction = "east" if dx > 0 else "west"
            tiles = abs(dx) - 1 if abs(dx) > 1 else 0
        
        # At least 1 tile
        tiles = max(1, tiles)
        
        return ExecutorAction(
            action_type="move",
            params={"direction": direction, "tiles": tiles},
            target=target,
            reason=f"Moving {direction} toward target at ({target.x}, {target.y})"
        )
    
    def _create_skill_action(
        self,
        player_pos: Tuple[int, int],
        target: Target,
        dx: int,
        dy: int,
    ) -> ExecutorAction:
        """Create skill action when adjacent to target."""
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
        
        return ExecutorAction(
            action_type=skill_name,
            params={"target_direction": direction},
            target=target,
            reason=f"Executing {skill_name} on target at ({target.x}, {target.y})"
        )
    
    def _get_skill_for_target(self, target: Target) -> str:
        """Determine which skill to use for this target."""
        if self.progress is None:
            return "interact"
        
        task_type = self.progress.task_type
        
        # Debris needs specific tool based on type
        if task_type == "clear_debris":
            debris_name = target.metadata.get("name", "")
            return self.DEBRIS_SKILLS.get(debris_name, "clear_weeds")
        
        # All other tasks have direct mapping
        return self.TASK_TO_SKILL.get(task_type, "interact")
    
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
    
    def is_complete(self) -> bool:
        """Check if current task is done."""
        return self.state in (TaskState.TASK_COMPLETE, TaskState.IDLE)
    
    def is_active(self) -> bool:
        """Check if actively executing a task."""
        return self.state in (TaskState.MOVING_TO_TARGET, TaskState.EXECUTING_AT_TARGET)
    
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
