"""
Daily Planner - Elias's internal planning system.

Gives Elias a sense of purpose each day:
- Morning: Generate prioritized task list
- Throughout day: Track progress, adapt to events
- Evening: Summary, notes for tomorrow

Tim's vision: "day starts- Elias plans his day and creates todo list"
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import PrereqResolver for resolving task prerequisites
try:
    from planning.prereq_resolver import (
        PrereqResolver,
        ResolvedTask,
        ResolutionResult,
        get_prereq_resolver,
    )
    HAS_PREREQ_RESOLVER = True
except ImportError:
    HAS_PREREQ_RESOLVER = False

# Import constants for default locations
try:
    from constants import DEFAULT_LOCATIONS
except ImportError:
    DEFAULT_LOCATIONS = {"shipping_bin": (71, 14), "water_pond": (72, 31)}

logger = logging.getLogger(__name__)

DEFAULT_PERSIST_PATH = "logs/daily_plan.json"


class TaskPriority(Enum):
    CRITICAL = 1  # Must do today (crops dying, etc.)
    HIGH = 2      # Important (watering, harvesting)
    MEDIUM = 3    # Should do (clearing, expanding)
    LOW = 4       # Nice to have (social, exploration)


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DailyTask:
    """A single task in Elias's daily plan."""
    id: str
    description: str
    category: str  # farming, social, exploration, etc.
    priority: int  # 1-4 (lower = higher priority)
    status: str = "pending"
    target_location: Optional[str] = None
    target_coords: Optional[tuple] = None
    estimated_time: int = 10  # game minutes
    actual_time: int = 0
    skill_override: Optional[str] = None  # Force use of specific skill (e.g., "auto_farm_chores")
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DailyTask":
        return cls(**data)


class DailyPlanner:
    """Elias's daily planning and task management system."""

    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = Path(persist_path or DEFAULT_PERSIST_PATH)

        # Current day's plan
        self.current_day: int = 0
        self.current_season: str = "spring"
        self.tasks: List[DailyTask] = []
        self.morning_plan_done: bool = False

        # Resolved task queue (with prereqs baked in)
        # This is the EXECUTION order after PrereqResolver processes raw tasks
        self.resolved_queue: List[Any] = []  # List of ResolvedTask
        self.resolution_notes: List[str] = []  # Memory notes from resolution
        self.skipped_tasks: List[tuple] = []  # (task_id, reason) pairs

        # Day summary (populated at end of day)
        self.day_summary: Dict[str, Any] = {}

        # Notes from previous day
        self.yesterday_notes: str = ""

        # History (last 7 days for context)
        self.history: List[Dict[str, Any]] = []

        self._load()

    # ─────────────────────────────────────────────────────────────────
    # Morning Planning
    # ─────────────────────────────────────────────────────────────────

    def start_new_day(
        self,
        day: int,
        season: str,
        game_state: Dict[str, Any],
        reason_fn: Optional[callable] = None,
        farm_state: Optional[Dict[str, Any]] = None,
        surroundings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Called when a new game day starts. Generates the daily plan.

        Args:
            day: Game day number
            season: Current season
            game_state: Full game state for context
            reason_fn: Optional async function(prompt) -> str for VLM reasoning
            farm_state: Farm-specific state (crops, objects) from /farm endpoint
            surroundings: Optional surroundings data with water/landmark locations

        Returns:
            Elias's morning plan as a string (for VLM context)
        """
        # Archive previous day if exists
        if self.tasks and self.current_day != day:
            self._archive_day()

        self.current_day = day
        self.current_season = season
        self.tasks = []
        self.morning_plan_done = True

        # Generate tasks based on game state (rule-based baseline)
        # Use farm_state if available (works when player is in FarmHouse)
        self._generate_farming_tasks(game_state, farm_state)
        self._generate_crafting_tasks(game_state, farm_state)  # Session 121: Auto-craft essentials
        self._generate_maintenance_tasks(game_state)
        self._generate_social_tasks(game_state)

        # Sort by priority
        self.tasks.sort(key=lambda t: t.priority)

        # VLM-based reasoning (if available) - enhance/reprioritize tasks
        if reason_fn:
            try:
                self._reason_about_plan(game_state, reason_fn)
            except Exception as e:
                logger.warning(f"VLM reasoning failed: {e}")

        # Resolve prerequisites and create execution queue
        self._resolve_prerequisites(game_state, surroundings, farm_state)

        self._persist()
        return self.get_plan_summary()

    def _resolve_prerequisites(
        self,
        game_state: Dict[str, Any],
        surroundings: Optional[Dict[str, Any]] = None,
        farm_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Resolve prerequisites for all tasks and create ordered execution queue.

        This is called AFTER raw tasks are generated. It:
        1. Checks what resources each task needs (water, seeds, money)
        2. Inserts prerequisite actions where needed (refill, buy, sell)
        3. Skips tasks with unresolvable prereqs (notes for memory)

        The resolved_queue is what TaskExecutor should execute.

        Args:
            game_state: Current game state
            surroundings: Optional surroundings data with water location
        """
        if not HAS_PREREQ_RESOLVER:
            logger.warning("PrereqResolver not available - using raw task list")
            # Fallback: convert tasks to simple queue without prereq resolution
            self.resolved_queue = [
                {"task_type": self._infer_task_type(t.description),
                 "description": t.description,
                 "original_task_id": t.id}
                for t in self.tasks
            ]
            return

        try:
            resolver = get_prereq_resolver()
            result = resolver.resolve(self.tasks, game_state, surroundings, farm_state)

            self.resolved_queue = result.resolved_queue
            self.skipped_tasks = result.skipped_tasks
            self.resolution_notes = result.notes_for_memory

            # Log resolution summary
            logger.info(resolver.get_queue_summary(result))

            # Log skipped tasks for user awareness
            for task_id, reason in result.skipped_tasks:
                logger.warning(f"⚠️ Task skipped: {task_id} - {reason}")

        except Exception as e:
            logger.error(f"PrereqResolver failed: {e}")
            # Fallback to raw tasks
            self.resolved_queue = []

    def _infer_task_type(self, description: str) -> str:
        """Infer task type from description (fallback when PrereqResolver unavailable)."""
        desc_lower = description.lower()
        if "water" in desc_lower:
            return "water_crops"
        elif "harvest" in desc_lower:
            return "harvest_crops"
        elif "plant" in desc_lower:
            return "plant_seeds"
        elif "clear" in desc_lower:
            return "clear_debris"
        return "unknown"

    def get_resolved_queue(self) -> List[Any]:
        """Get the resolved task queue for TaskExecutor."""
        return self.resolved_queue

    def get_next_resolved_task(self) -> Optional[Any]:
        """Get the next task from resolved queue (first pending one)."""
        for task in self.resolved_queue:
            # Check if task is not yet completed
            task_id = task.original_task_id if hasattr(task, 'original_task_id') else task.get('original_task_id')
            daily_task = self._find_task(task_id) if task_id else None
            if daily_task and daily_task.status in ("pending", "in_progress"):
                return task
            elif not daily_task:
                # Prereq task - check if already done somehow
                return task
        return None

    def _reason_about_plan(self, game_state: Dict[str, Any], reason_fn: callable) -> None:
        """
        Use VLM to reason about the daily plan.

        This is where compute cycles are spent on intelligent planning:
        - Evaluate task priorities based on context
        - Consider weather, energy, time constraints
        - Predict outcomes and adjust accordingly
        """
        # Handle SMAPI response structure
        data = game_state.get("data") or game_state
        # Build reasoning prompt
        time_data = data.get("time", {})
        player = data.get("player", {})
        crops = data.get("location", {}).get("crops", [])

        energy_pct = int((player.get("energy", 100) / player.get("maxEnergy", 100)) * 100)
        weather = time_data.get("weather", "sunny")

        # Format current tasks for reasoning
        task_list = "\n".join([
            f"- [{t.priority}] {t.description} ({t.category})"
            for t in self.tasks[:10]
        ])

        prompt = f"""You are Elias, planning your day on the farm.

Day {self.current_day}, {self.current_season}
Weather: {weather}
Energy: {energy_pct}%
Crops: {len(crops)} planted

Yesterday's notes: {self.yesterday_notes or 'None'}

Current task list:
{task_list}

Think through:
1. Are the priorities correct given today's conditions?
2. What might go wrong? How to mitigate?
3. What's the most efficient order?
4. Any tasks missing?

Output your reasoning (2-3 sentences), then "FINAL:" followed by any priority changes or new tasks (or "none" if plan is good).
"""

        # Note: This is synchronous for now - could be made async
        # The reason_fn should be the VLM's think method
        try:
            import asyncio
            if asyncio.iscoroutinefunction(reason_fn):
                # Run async function
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context, can't block
                    logger.info("📝 VLM reasoning deferred (async context)")
                    return
                response = loop.run_until_complete(reason_fn(prompt))
            else:
                response = reason_fn(prompt)

            if response:
                logger.info(f"🧠 VLM planning reasoning:\n{response[:500]}")
                self._apply_reasoning(response)
        except Exception as e:
            logger.warning(f"VLM reasoning error: {e}")

    def _apply_reasoning(self, response: str) -> None:
        """Apply VLM reasoning to adjust the plan."""
        # Parse response for priority changes or new tasks
        # Format: "FINAL: reprioritize harvest to CRITICAL" or "FINAL: add task 'check energy'"

        if "FINAL:" not in response:
            return

        final_part = response.split("FINAL:")[-1].strip().lower()

        if "none" in final_part or "good" in final_part:
            return

        # Look for priority changes
        for task in self.tasks:
            task_name = task.description.lower()
            if task_name[:20] in final_part:
                if "critical" in final_part:
                    task.priority = TaskPriority.CRITICAL.value
                    logger.info(f"📈 Reprioritized '{task.description}' to CRITICAL")
                elif "high" in final_part:
                    task.priority = TaskPriority.HIGH.value

        # Re-sort after changes
        self.tasks.sort(key=lambda t: t.priority)

    def _generate_farming_tasks(
        self,
        state: Dict[str, Any],
        farm_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Generate farming-related tasks based on game state.

        STANDARD DAILY ROUTINE (in priority order):
        1. Incomplete from yesterday → complete first
        2. Water crops → CRITICAL - crops die if not watered! DO THIS FIRST!
        3. Harvest ready crops → money and clear space
        4. Ship harvested crops → get money
        5. Plant seeds → grow more crops
        6. Clear debris → expand farm

        Args:
            state: Current game state (player location, inventory)
            farm_state: Optional farm-specific state from /farm endpoint
                       (allows seeing crops when player is in FarmHouse)
        """
        # Handle SMAPI response structure: {success, data: {...}, error}
        # OR already-extracted data: {player, location, time, ...}
        data = state.get("data") or state
        location = data.get("location", {})
        player = data.get("player", {})
        inventory = data.get("inventory", [])  # Inventory is at data level, not player level

        # Get weather for rain detection
        time_data = data.get("time", {})
        weather = time_data.get("weather", "sunny").lower()
        is_rainy = weather in ("rainy", "stormy", "rain", "storm")

        # Use farm_state crops if available (works from FarmHouse)
        # Otherwise fall back to current location crops
        if farm_state and farm_state.get("crops"):
            crops = farm_state.get("crops", [])
            logger.info(f"📊 Using /farm endpoint: {len(crops)} crops on farm")
        else:
            crops = location.get("crops", [])
            logger.debug(f"📊 Using location crops: {len(crops)} (fallback)")

        # PRIORITY 1: Incomplete tasks from yesterday (carried over)
        if self.yesterday_notes and "incomplete" in self.yesterday_notes.lower():
            self.tasks.append(DailyTask(
                id=f"carryover_{self.current_day}_1",
                description="Complete yesterday's unfinished tasks",
                category="farming",
                priority=TaskPriority.CRITICAL.value,
                target_location="Farm",
                estimated_time=30,
                notes=self.yesterday_notes,
            ))

        # PRIORITY 2: Water crops FIRST (CRITICAL - crops die without water!)
        # SKIP on rainy/stormy days - rain waters crops automatically!
        # Exclude harvestable crops - they don't need water, they need harvesting
        unwatered = [c for c in crops if not c.get("isWatered", False) and not c.get("isReadyForHarvest", False)]
        # === CONSOLIDATED FARM CHORES (Batch Operation) ===
        # Instead of separate water/harvest/plant tasks, use ONE batch task
        # that runs auto_farm_chores skill for efficiency

        harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
        seed_items = [item for item in inventory if item and "seed" in item.get("name", "").lower()]
        total_seeds = sum(item.get("stack", 1) for item in seed_items) if seed_items else 0
        money = data.get("player", {}).get("money", 0)

        # Build description of what batch will do
        chore_parts = []
        if harvestable:
            chore_parts.append(f"harvest {len(harvestable)}")
        if unwatered and not is_rainy:
            chore_parts.append(f"water {len(unwatered)}")
        elif is_rainy:
            logger.info(f"🌧️ Rain day - crops watered by rain")
        if total_seeds > 0:
            chore_parts.append(f"plant {total_seeds}")
        elif money >= 20:
            chore_parts.append("buy+plant seeds")

        # Session 125: Diagnostic logging for task creation
        logger.info(f"📊 Farm task check: crops={len(crops)}, harvestable={len(harvestable)}, unwatered={len(unwatered)}, seeds={total_seeds}, money={money}, rainy={is_rainy}")
        logger.info(f"📊 Chore parts: {chore_parts}")
        
        if chore_parts or (money >= 20 and not is_rainy):
            # Always add farm chores task - batch handles buying seeds if needed
            logger.info(f"✅ Creating farm_chores task with skill_override=auto_farm_chores")
            desc = f"Farm chores: {', '.join(chore_parts)}" if chore_parts else "Farm chores (check crops)"
            self.tasks.append(DailyTask(
                id=f"farm_chores_{self.current_day}",
                description=desc,
                category="farming",
                priority=TaskPriority.CRITICAL.value,
                target_location="Farm",
                estimated_time=60,  # Batch handles everything
                skill_override="auto_farm_chores",  # Use batch skill instead of individual actions
            ))

        # Ship task still separate (needs to go to shipping bin)
        sellable_crops = ["Parsnip", "Potato", "Cauliflower", "Green Bean", "Kale", "Melon",
                         "Blueberry", "Corn", "Tomato", "Pumpkin", "Cranberry", "Eggplant", "Grape", "Radish"]
        sellables = [item for item in inventory if item and item.get("name") in sellable_crops and item.get("stack", 0) > 0]
        if sellables:
            total_to_ship = sum(item.get("stack", 0) for item in sellables)
            self.tasks.append(DailyTask(
                id=f"ship_{self.current_day}_1",
                description=f"Ship {total_to_ship} crops at shipping bin",
                category="farming",
                priority=TaskPriority.HIGH.value,
                target_location="Farm",
                target_coords=(71, 14),  # Shipping bin location
                estimated_time=10,
            ))

        # PRIORITY 5: Clear debris if nothing else to do (MEDIUM - expand)
        # This is added in _generate_maintenance_tasks but we note it's last resort

    def _generate_crafting_tasks(
        self,
        state: Dict[str, Any],
        farm_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Generate crafting tasks for essential items.

        Session 121: Auto-craft scarecrow and chest when materials available.

        Essential items:
        - Scarecrow: Protects crops from crows (need 50 wood, 1 coal, 20 fiber)
        - Chest: Storage (need 50 wood)
        """
        # Handle SMAPI response structure
        data = state.get("data") or state
        inventory = data.get("inventory", [])

        # Get farm objects to check what's already placed
        farm_data = farm_state or {}
        farm_objects = farm_data.get("objects", [])

        # Count materials in inventory
        wood_count = 0
        coal_count = 0
        fiber_count = 0
        for item in inventory:
            if not item:
                continue
            name = item.get("name", "").lower()
            stack = item.get("stack", 1)
            if name == "wood":
                wood_count += stack
            elif name == "coal":
                coal_count += stack
            elif name == "fiber":
                fiber_count += stack

        # Check if scarecrow already placed on farm
        has_scarecrow = any(
            "scarecrow" in obj.get("name", "").lower()
            for obj in farm_objects
        )

        # Check if chest already placed on farm
        has_chest = any(
            obj.get("name", "").lower() == "chest"
            for obj in farm_objects
        )

        # SCARECROW: High priority - crows eat crops!
        # Recipe: 50 wood, 1 coal, 20 fiber
        if not has_scarecrow:
            can_craft_scarecrow = wood_count >= 50 and coal_count >= 1 and fiber_count >= 20
            if can_craft_scarecrow:
                self.tasks.append(DailyTask(
                    id=f"craft_scarecrow_{self.current_day}",
                    description="Craft and place scarecrow (have materials!)",
                    category="crafting",
                    priority=TaskPriority.HIGH.value,  # Protect crops from crows
                    target_location="Farm",
                    estimated_time=5,
                    skill_override="craft_scarecrow",
                    notes=f"Materials: {wood_count}/50 wood, {coal_count}/1 coal, {fiber_count}/20 fiber",
                ))
                logger.info(f"📋 Added task: Craft scarecrow (have {wood_count} wood, {coal_count} coal, {fiber_count} fiber)")
            else:
                # Log what's missing for debugging
                missing = []
                if wood_count < 50:
                    missing.append(f"wood ({wood_count}/50)")
                if coal_count < 1:
                    missing.append(f"coal ({coal_count}/1)")
                if fiber_count < 20:
                    missing.append(f"fiber ({fiber_count}/20)")
                logger.debug(f"📋 Need scarecrow but missing: {', '.join(missing)}")

        # CHEST: Medium priority - inventory management
        # Recipe: 50 wood
        if not has_chest:
            can_craft_chest = wood_count >= 50
            if can_craft_chest:
                self.tasks.append(DailyTask(
                    id=f"craft_chest_{self.current_day}",
                    description="Craft and place chest for storage (have wood!)",
                    category="crafting",
                    priority=TaskPriority.MEDIUM.value,
                    target_location="Farm",
                    estimated_time=5,
                    skill_override="craft_chest",
                    notes=f"Materials: {wood_count}/50 wood",
                ))
                logger.info(f"📋 Added task: Craft chest (have {wood_count} wood)")

    def _generate_maintenance_tasks(self, state: Dict[str, Any]) -> None:
        """Generate farm maintenance tasks.
        
        Tasks are added conditionally based on prerequisites:
        - Clear debris: energy > 50%
        - Mining: has pickaxe + energy > 60% + VLM can reprioritize
        """
        # Handle SMAPI response structure
        data = state.get("data") or state
        player = data.get("player", {})
        inventory = data.get("inventory", [])
        time_data = data.get("time", {})
        
        energy = player.get("energy", 100)
        max_energy = player.get("maxEnergy", 100)
        energy_pct = (energy / max_energy * 100) if max_energy > 0 else 100
        hour = time_data.get("hour", 6)
        
        # Session 123: Removed standalone "clear debris" task
        # It had no skill_override and got stuck in VLM loop, blocking mining
        # Debris clearing can be done opportunistically; crops grow fine around debris
        # If needed later, add debris clearing to _batch_farm_chores
        
        # Mining - conditional on having pickaxe and good energy
        # VLM reasoning can reprioritize based on context (weather, goals, etc.)
        has_pickaxe = any(
            item and "pickaxe" in item.get("name", "").lower()
            for item in inventory if item
        )
        
        # Mining prerequisites: pickaxe + energy > 60% + not too late in day
        # Session 125: Relaxed hour check - allow mining until 6 PM (was 2 PM)
        # At 5 PM with 74% energy and nothing else to do, should still mine
        logger.info(f"⛏️ Mining check: has_pickaxe={has_pickaxe}, energy_pct={energy_pct:.0f}%, hour={hour}")
        if has_pickaxe and energy_pct > 60 and hour < 18:
            # Get combat level to suggest appropriate mine depth
            combat_level = player.get("combatLevel", 0)
            target_floors = max(3, min(combat_level + 2, 10))  # 3-10 floors based on level

            # Session 122: Use auto_mine for batch mining (like auto_farm_chores)
            self.tasks.append(DailyTask(
                id=f"mining_{self.current_day}_1",
                description=f"Mine ore in the mines ({target_floors} floors)",
                category="mining",
                priority=TaskPriority.MEDIUM.value,
                target_location="Mine",
                estimated_time=60,
                skill_override="auto_mine",  # Session 122: Batch mining
                notes=f"Batch mining: {target_floors} floors, auto-combat, retreats if low health",
            ))
            logger.info(f"⛏️ Mining task ADDED: {target_floors} floors, skill_override=auto_mine")
        else:
            logger.info(f"⛏️ Mining task SKIPPED: conditions not met")

    def _generate_social_tasks(self, state: Dict[str, Any]) -> None:
        """Generate social/exploration tasks (lower priority)."""
        # Handle SMAPI response structure
        data = state.get("data") or state
        # Only add if we have time (early in day)
        time_data = data.get("time", {})
        hour = time_data.get("hour", 6)

        if hour < 12:  # Morning - might have time for social
            self.tasks.append(DailyTask(
                id=f"explore_{self.current_day}_1",
                description="Explore town or meet neighbors",
                category="social",
                priority=TaskPriority.LOW.value,
                target_location="Town",
                estimated_time=60,
            ))

    # ─────────────────────────────────────────────────────────────────
    # Task Management
    # ─────────────────────────────────────────────────────────────────

    def get_next_task(self) -> Optional[DailyTask]:
        """Get the highest priority pending task."""
        pending = [t for t in self.tasks if t.status == "pending"]
        return pending[0] if pending else None

    def start_task(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        task = self._find_task(task_id)
        if task and task.status == "pending":
            task.status = "in_progress"
            self._persist()
            return True
        return False

    def complete_task(self, task_id: str, notes: str = "") -> bool:
        """Mark a task as completed."""
        task = self._find_task(task_id)
        if task:
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.notes = notes
            self._persist()
            logger.info(f"✅ Task completed: {task.description}")
            return True
        return False

    def fail_task(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as failed."""
        task = self._find_task(task_id)
        if task:
            task.status = "failed"
            task.notes = reason
            self._persist()
            logger.warning(f"❌ Task failed: {task.description} - {reason}")
            return True
        return False

    def skip_task(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as skipped (deprioritized)."""
        task = self._find_task(task_id)
        if task:
            task.status = "skipped"
            task.notes = reason
            self._persist()
            return True
        return False

    def add_task(self, description: str, category: str, priority: int = 3) -> str:
        """Add a new task mid-day (reactive planning)."""
        task_id = f"adhoc_{self.current_day}_{len(self.tasks)}"
        task = DailyTask(
            id=task_id,
            description=description,
            category=category,
            priority=priority,
        )
        self.tasks.append(task)
        self.tasks.sort(key=lambda t: t.priority)
        self._persist()
        return task_id

    def _find_task(self, task_id: str) -> Optional[DailyTask]:
        """Find task by ID."""
        return next((t for t in self.tasks if t.id == task_id), None)

    # ─────────────────────────────────────────────────────────────────
    # End of Day
    # ─────────────────────────────────────────────────────────────────

    def end_day(self, notes_for_tomorrow: str = "") -> Dict[str, Any]:
        """
        Called at end of day. Creates summary and prepares for tomorrow.

        Returns:
            Day summary dict
        """
        completed = [t for t in self.tasks if t.status == "completed"]
        failed = [t for t in self.tasks if t.status == "failed"]
        skipped = [t for t in self.tasks if t.status == "skipped"]
        pending = [t for t in self.tasks if t.status == "pending"]

        self.day_summary = {
            "day": self.current_day,
            "season": self.current_season,
            "tasks_completed": len(completed),
            "tasks_failed": len(failed),
            "tasks_skipped": len(skipped),
            "tasks_pending": len(pending),
            "completion_rate": len(completed) / len(self.tasks) if self.tasks else 0,
            "highlights": [t.description for t in completed[:3]],
            "concerns": [t.description for t in failed + pending],
            "notes_for_tomorrow": notes_for_tomorrow,
        }

        self.yesterday_notes = notes_for_tomorrow
        self._persist()

        logger.info(f"📋 Day {self.current_day} summary: {len(completed)}/{len(self.tasks)} tasks completed")
        return self.day_summary

    def _archive_day(self) -> None:
        """Archive current day to history before starting new day."""
        if not self.tasks:
            return

        archive = {
            "day": self.current_day,
            "season": self.current_season,
            "tasks": [t.to_dict() for t in self.tasks],
            "summary": self.day_summary,
        }
        self.history.append(archive)
        # Keep only last 7 days
        self.history = self.history[-7:]

    # ─────────────────────────────────────────────────────────────────
    # Context for VLM
    # ─────────────────────────────────────────────────────────────────

    def get_plan_summary(self) -> str:
        """Get current plan as formatted string for VLM context."""
        if not self.tasks:
            return "No plan for today yet."

        lines = [f"📋 Day {self.current_day} Plan ({self.current_season}):"]

        # Group by status
        pending = [t for t in self.tasks if t.status == "pending"]
        in_progress = [t for t in self.tasks if t.status == "in_progress"]
        completed = [t for t in self.tasks if t.status == "completed"]

        if in_progress:
            lines.append("▶ CURRENT:")
            for t in in_progress:
                lines.append(f"  • {t.description}")

        if pending:
            lines.append("☐ TODO:")
            for t in pending[:5]:  # Limit to top 5
                priority_icon = "!" * (5 - t.priority) if t.priority < 4 else ""
                lines.append(f"  • {priority_icon}{t.description}")
            if len(pending) > 5:
                lines.append(f"  ... and {len(pending) - 5} more")

        if completed:
            lines.append(f"✓ DONE: {len(completed)} tasks")

        if self.yesterday_notes:
            lines.append(f"📝 Yesterday's note: {self.yesterday_notes}")

        return "\n".join(lines)

    def get_current_focus(self) -> str:
        """Get what Elias should be focused on right now."""
        in_progress = [t for t in self.tasks if t.status == "in_progress"]
        if in_progress:
            return in_progress[0].description

        next_task = self.get_next_task()
        if next_task:
            return next_task.description

        return "All tasks complete for today!"

    # ─────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load planner state from disk."""
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            self.current_day = data.get("current_day", 0)
            self.current_season = data.get("current_season", "spring")
            self.tasks = [DailyTask.from_dict(t) for t in data.get("tasks", [])]
            self.morning_plan_done = data.get("morning_plan_done", False)
            self.day_summary = data.get("day_summary", {})
            self.yesterday_notes = data.get("yesterday_notes", "")
            self.history = data.get("history", [])

            logger.info(f"📋 Loaded daily plan: Day {self.current_day}, {len(self.tasks)} tasks")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load daily plan: {e}")

    def _persist(self) -> None:
        """Save planner state to disk."""
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_day": self.current_day,
                "current_season": self.current_season,
                "tasks": [t.to_dict() for t in self.tasks],
                "morning_plan_done": self.morning_plan_done,
                "day_summary": self.day_summary,
                "yesterday_notes": self.yesterday_notes,
                "history": self.history,
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.warning(f"Could not persist daily plan: {e}")

    def to_api_format(self) -> Dict[str, Any]:
        """Format for API/UI consumption."""
        return {
            "day": self.current_day,
            "season": self.current_season,
            "tasks": [t.to_dict() for t in self.tasks],
            "summary": self.day_summary,
            "focus": self.get_current_focus(),
            "plan_text": self.get_plan_summary(),
            "stats": {
                "total": len(self.tasks),
                "completed": sum(1 for t in self.tasks if t.status == "completed"),
                "pending": sum(1 for t in self.tasks if t.status == "pending"),
                "failed": sum(1 for t in self.tasks if t.status == "failed"),
            },
        }


# Singleton instance with auto-refresh
_daily_planner: Optional[DailyPlanner] = None
_last_file_mtime: float = 0


def get_daily_planner() -> DailyPlanner:
    """Get or create the singleton DailyPlanner instance.

    Auto-refreshes from disk if the file has been modified by another process
    (e.g., agent writes new plan, UI server needs to see it).
    """
    global _daily_planner, _last_file_mtime

    persist_path = Path(DEFAULT_PERSIST_PATH)

    # Check if file has been modified since last load
    if persist_path.exists():
        current_mtime = persist_path.stat().st_mtime
        if _daily_planner is not None and current_mtime > _last_file_mtime:
            logger.info(f"📋 Daily plan file changed, reloading...")
            _daily_planner._load()
            _last_file_mtime = current_mtime

    if _daily_planner is None:
        _daily_planner = DailyPlanner()
        if persist_path.exists():
            _last_file_mtime = persist_path.stat().st_mtime

    return _daily_planner
