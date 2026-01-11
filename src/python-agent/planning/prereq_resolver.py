"""
Prerequisite Resolver for Task Planning.

Resolves prerequisites for tasks UPFRONT during morning planning,
returning an ordered execution queue with all prereqs baked in.

This replaces runtime precondition checking - prereqs are resolved
once at planning time, not checked every tick during execution.

Example flow:
  Raw tasks: [water_crops, plant_seeds]

  water_crops needs:
    - watering can has water → if empty, insert refill_watering_can

  plant_seeds needs:
    - seeds in inventory → if none:
      - has money? → insert [go_pierre, buy_seeds]
      - no money? → can sell? → insert ship_item before buy
      - can't sell? → note in memory, skip this task chain

  Resolved queue: [refill_watering_can, water_crops, go_pierre, buy_seeds, plant_seeds]
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class PrereqStatus(Enum):
    """Status of a prerequisite check."""
    MET = "met"              # Prereq satisfied, no action needed
    NEEDS_ACTION = "action"  # Prereq needs action(s) to satisfy
    UNRESOLVABLE = "unresolvable"  # Cannot be satisfied (no money, etc.)


@dataclass
class PrereqAction:
    """An action needed to satisfy a prerequisite."""
    action_type: str           # e.g., "refill_watering_can", "go_to_pierre"
    task_type: str             # What TaskExecutor task type this maps to
    description: str           # Human-readable description
    params: Dict[str, Any] = field(default_factory=dict)
    estimated_time: int = 5    # Game minutes


@dataclass
class ResolvedTask:
    """A task with its prerequisites resolved."""
    original_task_id: str      # ID from DailyTask
    task_type: str             # e.g., "water_crops", "refill_watering_can"
    description: str
    is_prereq: bool = False    # True if this is a prerequisite action
    prereq_for: Optional[str] = None  # Which task this is a prereq for
    params: Dict[str, Any] = field(default_factory=dict)
    estimated_time: int = 10


@dataclass
class ResolutionResult:
    """Result of resolving all tasks."""
    resolved_queue: List[ResolvedTask]
    skipped_tasks: List[Tuple[str, str]]  # (task_id, reason)
    notes_for_memory: List[str]  # Things to remember for future


class PrereqResolver:
    """
    Resolves prerequisites for tasks during morning planning.

    Takes raw tasks from DailyPlanner, checks what resources are needed,
    and returns an ordered queue with all prerequisite actions baked in.
    """

    # Seed prices for money calculations
    SEED_PRICES = {
        "parsnip": 20,
        "potato": 50,
        "cauliflower": 80,
        "green bean": 60,
        "kale": 70,
        "melon": 80,
        "blueberry": 80,
        "corn": 150,
        "tomato": 50,
        "pumpkin": 100,
        "cranberry": 240,
        "eggplant": 20,
        "grape": 60,
        "radish": 40,
    }

    # Crops that should NOT be sold (reserved for bundles, gifts, etc.)
    RESERVED_CROPS = [
        # Community center bundles - Spring
        "Parsnip", "Green Bean", "Cauliflower", "Potato",
        # Community center bundles - Summer
        "Melon", "Blueberry", "Hot Pepper", "Tomato",
        # Community center bundles - Fall
        "Corn", "Eggplant", "Pumpkin",
        # Quality crops (keep gold/iridium quality)
        # Note: This is simplified - could check quality level
    ]

    def __init__(self):
        self.resolution_notes: List[str] = []

    def resolve(
        self,
        tasks: List[Any],  # List of DailyTask objects
        game_state: Dict[str, Any],
    ) -> ResolutionResult:
        """
        Resolve all tasks and return ordered execution queue.

        Args:
            tasks: Raw tasks from DailyPlanner (sorted by priority)
            game_state: Current game state for resource checking

        Returns:
            ResolutionResult with resolved queue, skipped tasks, and memory notes
        """
        self.resolution_notes = []
        resolved_queue: List[ResolvedTask] = []
        skipped_tasks: List[Tuple[str, str]] = []

        # Extract game state data
        data = game_state.get("data") or game_state
        player = data.get("player", {})
        inventory = player.get("inventory", [])
        money = player.get("money", 0)
        watering_can_water = player.get("wateringCanWater", 0)
        watering_can_max = player.get("wateringCanMax", 40)

        logger.info(f"🔧 PrereqResolver: Resolving {len(tasks)} tasks")
        logger.info(f"   Resources: money={money}g, water={watering_can_water}/{watering_can_max}")

        for task in tasks:
            task_id = task.id if hasattr(task, 'id') else str(task)
            task_desc = task.description if hasattr(task, 'description') else str(task)

            # Determine task type from description
            task_type = self._infer_task_type(task_desc)

            if not task_type:
                # Unknown task type - pass through as-is
                resolved_queue.append(ResolvedTask(
                    original_task_id=task_id,
                    task_type="unknown",
                    description=task_desc,
                    estimated_time=task.estimated_time if hasattr(task, 'estimated_time') else 10,
                ))
                continue

            # Check prerequisites for this task type
            prereqs, status, reason = self._check_prereqs(
                task_type=task_type,
                game_state=game_state,
                player=player,
                inventory=inventory,
                money=money,
                watering_can_water=watering_can_water,
            )

            if status == PrereqStatus.UNRESOLVABLE:
                # Cannot satisfy prereqs - skip this task
                logger.warning(f"⚠️ Skipping '{task_desc}': {reason}")
                skipped_tasks.append((task_id, reason))
                self.resolution_notes.append(f"Could not do '{task_desc}': {reason}")
                continue

            # Add prerequisite actions first
            for prereq in prereqs:
                resolved_queue.append(ResolvedTask(
                    original_task_id=f"{task_id}_prereq",
                    task_type=prereq.task_type,
                    description=prereq.description,
                    is_prereq=True,
                    prereq_for=task_id,
                    params=prereq.params,
                    estimated_time=prereq.estimated_time,
                ))
                logger.info(f"   + Prereq: {prereq.description}")

            # Add the main task
            resolved_queue.append(ResolvedTask(
                original_task_id=task_id,
                task_type=task_type,
                description=task_desc,
                estimated_time=task.estimated_time if hasattr(task, 'estimated_time') else 10,
            ))

        logger.info(f"🔧 PrereqResolver: Queue has {len(resolved_queue)} items ({len(skipped_tasks)} skipped)")

        return ResolutionResult(
            resolved_queue=resolved_queue,
            skipped_tasks=skipped_tasks,
            notes_for_memory=self.resolution_notes,
        )

    def _infer_task_type(self, description: str) -> Optional[str]:
        """Infer task type from description."""
        desc_lower = description.lower()

        if "water" in desc_lower and "crop" in desc_lower:
            return "water_crops"
        elif "harvest" in desc_lower:
            return "harvest_crops"
        elif "plant" in desc_lower and "seed" in desc_lower:
            return "plant_seeds"
        elif "ship" in desc_lower or "sell" in desc_lower:
            return "ship_items"
        elif "clear" in desc_lower and "debris" in desc_lower:
            return "clear_debris"
        elif "buy" in desc_lower and "seed" in desc_lower:
            return "buy_seeds"
        elif "refill" in desc_lower and "water" in desc_lower:
            return "refill_watering_can"
        elif "till" in desc_lower or "hoe" in desc_lower:
            return "till_soil"

        return None

    def _check_prereqs(
        self,
        task_type: str,
        game_state: Dict[str, Any],
        player: Dict[str, Any],
        inventory: List[Dict[str, Any]],
        money: int,
        watering_can_water: int,
    ) -> Tuple[List[PrereqAction], PrereqStatus, str]:
        """
        Check prerequisites for a specific task type.

        Returns:
            Tuple of (prereq_actions, status, reason)
        """
        prereqs: List[PrereqAction] = []

        if task_type == "water_crops":
            # Need water in watering can
            if watering_can_water <= 0:
                prereqs.append(PrereqAction(
                    action_type="refill_watering_can",
                    task_type="refill_watering_can",
                    description="Refill watering can at water source",
                    params={"target_direction": "south"},  # Default, water usually south
                    estimated_time=5,
                ))
            return prereqs, PrereqStatus.MET if not prereqs else PrereqStatus.NEEDS_ACTION, ""

        elif task_type == "plant_seeds":
            # Need seeds in inventory
            seeds = [i for i in inventory if i and "seed" in i.get("name", "").lower()]
            if not seeds:
                # No seeds - need to buy
                # Check if we have money
                cheapest_seed_price = min(self.SEED_PRICES.values())  # 20g for parsnip

                if money >= cheapest_seed_price:
                    # Have money - go buy seeds
                    prereqs.append(PrereqAction(
                        action_type="go_to_pierre",
                        task_type="navigate",
                        description="Go to Pierre's shop",
                        params={"destination": "SeedShop"},
                        estimated_time=10,
                    ))
                    prereqs.append(PrereqAction(
                        action_type="buy_seeds",
                        task_type="buy_seeds",
                        description="Buy seeds from Pierre",
                        params={},
                        estimated_time=5,
                    ))
                else:
                    # No money - can we sell something?
                    sellable = self._find_sellable_items(inventory)
                    if sellable:
                        prereqs.append(PrereqAction(
                            action_type="ship_items",
                            task_type="ship_items",
                            description=f"Ship {sellable[0]} to earn money for seeds",
                            params={"item": sellable[0]},
                            estimated_time=5,
                        ))
                        prereqs.append(PrereqAction(
                            action_type="go_to_pierre",
                            task_type="navigate",
                            description="Go to Pierre's shop",
                            params={"destination": "SeedShop"},
                            estimated_time=10,
                        ))
                        prereqs.append(PrereqAction(
                            action_type="buy_seeds",
                            task_type="buy_seeds",
                            description="Buy seeds from Pierre",
                            params={},
                            estimated_time=5,
                        ))
                    else:
                        # Can't sell anything - unresolvable
                        return [], PrereqStatus.UNRESOLVABLE, "No seeds, no money, nothing to sell"

            return prereqs, PrereqStatus.MET if not prereqs else PrereqStatus.NEEDS_ACTION, ""

        elif task_type == "harvest_crops":
            # No prereqs for harvesting (just need harvestable crops, already checked)
            return [], PrereqStatus.MET, ""

        elif task_type == "ship_items":
            # No prereqs - if we have items to ship, we can ship
            return [], PrereqStatus.MET, ""

        elif task_type == "clear_debris":
            # Clearing is low priority, no prereqs but should have tools
            # (tools are always in inventory slot 0-3)
            return [], PrereqStatus.MET, ""

        elif task_type == "till_soil":
            # Need hoe equipped - but skill handles that
            return [], PrereqStatus.MET, ""

        # Default: no prereqs
        return [], PrereqStatus.MET, ""

    def _find_sellable_items(self, inventory: List[Dict[str, Any]]) -> List[str]:
        """
        Find items that can be sold (not reserved for bundles/gifts).

        Returns list of item names that are safe to sell.
        """
        sellable = []

        for item in inventory:
            if not item:
                continue

            name = item.get("name", "")
            stack = item.get("stack", 0)

            if stack <= 0:
                continue

            # Skip reserved crops
            if name in self.RESERVED_CROPS:
                # Only skip if we have 1 or fewer (keep at least 1 for bundles)
                if stack <= 1:
                    continue
                # Can sell extras
                sellable.append(name)
            elif name and not name.endswith("Seeds"):
                # Non-reserved, non-seed items can be sold
                sellable.append(name)

        return sellable

    def get_queue_summary(self, result: ResolutionResult) -> str:
        """Get human-readable summary of resolved queue."""
        lines = [f"📋 Resolved {len(result.resolved_queue)} tasks:"]

        for i, task in enumerate(result.resolved_queue, 1):
            prefix = "  ↳ " if task.is_prereq else f"{i}. "
            lines.append(f"{prefix}{task.description}")

        if result.skipped_tasks:
            lines.append(f"\n⚠️ Skipped {len(result.skipped_tasks)} tasks:")
            for task_id, reason in result.skipped_tasks:
                lines.append(f"  - {task_id}: {reason}")

        return "\n".join(lines)


# Singleton instance
_prereq_resolver: Optional[PrereqResolver] = None


def get_prereq_resolver() -> PrereqResolver:
    """Get the singleton PrereqResolver instance."""
    global _prereq_resolver
    if _prereq_resolver is None:
        _prereq_resolver = PrereqResolver()
    return _prereq_resolver
