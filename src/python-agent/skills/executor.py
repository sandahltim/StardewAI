"""Execute skill action sequences."""
from __future__ import annotations

import asyncio
import importlib
import logging
from string import Formatter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import ExecutionResult, Skill, SkillPlanning


class SkillExecutor:
    def __init__(self, action_executor: Any):
        self.action_executor = action_executor

    def _call_planner(
        self, planning: SkillPlanning, state: Dict
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Call the planner module to get placement sequence.

        Returns:
            (success, plan_result, error_message)
        """
        try:
            # Import planner module dynamically
            module = importlib.import_module(f"planning.{planning.planner}")
            func = getattr(module, planning.function)

            # Get player position from state
            player = state.get("player", {})
            player_pos = (player.get("tileX", 0), player.get("tileY", 0))

            # Get farm state if needed
            farm_state = state.get("farm", state)

            # Call planner function with args
            result = func(farm_state, planning.args.get("item_type", ""), player_pos)

            if result is None:
                return False, None, "Planner returned no placement needed"

            logging.info(f"   📍 Planner result: {result}")
            return True, result, None

        except ImportError as e:
            return False, None, f"Failed to import planner: {e}"
        except AttributeError as e:
            return False, None, f"Planner function not found: {e}"
        except Exception as e:
            return False, None, f"Planner error: {e}"

    def _apply_planned_values(
        self, actions: List, plan_result: Dict[str, Any]
    ) -> List:
        """Apply planned values to action params.

        Transforms actions that use {planned_*} placeholders with actual values
        from the planner result.
        """
        from copy import deepcopy
        from .models import SkillAction

        modified = []
        for action in actions:
            action_copy = SkillAction(
                action_type=action.action_type,
                params=deepcopy(action.params)
            )

            # Handle move_to with planned position
            if action.action_type == "move_to":
                value = action.params.get("value", "")
                if "{planned_target_pos}" in str(value):
                    target_pos = plan_result.get("target_pos", (0, 0))
                    # target_pos is a tuple (x, y) from farm_planner
                    # SMAPIController.execute expects flat x, y params
                    if isinstance(target_pos, (list, tuple)) and len(target_pos) >= 2:
                        action_copy.params = {"x": target_pos[0], "y": target_pos[1]}
                    elif isinstance(target_pos, dict):
                        action_copy.params = {
                            "x": target_pos.get("x", 0),
                            "y": target_pos.get("y", 0)
                        }

            # Handle face/place_item with planned direction
            elif action.action_type in ("face", "place_item"):
                for key, value in action.params.items():
                    if "{planned_direction}" in str(value):
                        direction = plan_result.get("place_direction", "south")
                        action_copy.params[key] = direction

            modified.append(action_copy)

        return modified

    async def execute(self, skill: Skill, params: dict, state: Dict) -> ExecutionResult:
        actions_taken: List[str] = []
        logging.debug(f"   ⚙️ Skill executor: {skill.name} with {len(skill.actions)} actions")

        # Handle planning-required skills
        actions_to_execute = skill.actions
        if skill.requires_planning and skill.planning:
            logging.info(f"   📐 Skill requires planning, calling {skill.planning.planner}.{skill.planning.function}")
            success, plan_result, error = self._call_planner(skill.planning, state)
            if not success:
                recovery = self._get_recovery(skill, "no_plan")
                return ExecutionResult(
                    success=False,
                    actions_taken=actions_taken,
                    error=error or "Planning failed",
                    recovery_skill=recovery,
                )
            # Apply planned values to actions
            actions_to_execute = self._apply_planned_values(skill.actions, plan_result)

        for i, action in enumerate(actions_to_execute):
            action_type = action.action_type
            resolved = self._resolve_params(action.params, params)
            logging.info(f"      [{i+1}/{len(actions_to_execute)}] {action_type}: {resolved}")
            success = await self._dispatch(action_type, resolved, state)
            actions_taken.append(f"{action_type} {resolved}".strip())
            if not success:
                error = f"action_failed: {action_type}"
                recovery = self._get_recovery(skill, "action_failed")
                return ExecutionResult(
                    success=False,
                    actions_taken=actions_taken,
                    error=error,
                    recovery_skill=recovery,
                )
        return ExecutionResult(success=True, actions_taken=actions_taken)

    def _resolve_params(self, params: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._format(value, values)
            else:
                resolved[key] = value
        return resolved

    def _format(self, template: str, values: Dict[str, Any]) -> str:
        formatter = Formatter()
        return formatter.vformat(template, (), values)

    async def _dispatch(self, action_type: str, params: Dict[str, Any], state: Optional[Dict] = None) -> bool:
        if action_type == "wait":
            duration = params.get("value", params.get("seconds", 0.5))
            await asyncio.sleep(float(duration))
            return True
        # Add delay after face action to let turn animation complete
        if action_type == "face":
            executor = self.action_executor
            if hasattr(executor, "execute_action"):
                result = bool(executor.execute_action(action_type, params))
            elif hasattr(executor, "execute"):
                result = bool(executor.execute({"action_type": action_type, "params": params}))
            elif callable(executor):
                result = bool(executor(action_type, params))
            else:
                result = False
            await asyncio.sleep(0.15)  # Wait for turn animation
            return result
        # Handle select_item_type: normalize params and pass to mod (mod handles inventory scanning)
        if action_type == "select_item_type":
            item_type = params.get("type", params.get("value", ""))
            params = {"type": item_type}  # Normalize params for mod API
            # Fall through to executor below
        # Handle pathfind_to: translate to move action with target
        if action_type == "pathfind_to":
            target = params.get("target", "")
            stop_adjacent = params.get("stop_adjacent", False)
            # For nearest_water, get water coordinates from state/surroundings
            if target == "nearest_water":
                nearest_water = (state or {}).get("surroundings", {}).get("nearestWater", {})
                if not nearest_water or not nearest_water.get("x"):
                    logging.warning("No nearest water found in surroundings")
                    return False
                x, y = nearest_water.get("x"), nearest_water.get("y")
                logging.info(f"Pathfinding to nearest water at ({x}, {y})")
                return await self._dispatch("move", {"x": x, "y": y, "stop_adjacent": stop_adjacent}, state)
            # For other targets, try to use the target as coordinates
            logging.warning(f"pathfind_to target '{target}' not supported")
            return False
        executor = self.action_executor
        if hasattr(executor, "execute_action"):
            result = bool(executor.execute_action(action_type, params))
        elif hasattr(executor, "execute"):
            result = bool(executor.execute({"action_type": action_type, "params": params}))
        elif callable(executor):
            result = bool(executor(action_type, params))
        else:
            return False
        # Add delay after use_tool to let tool animation complete
        if action_type == "use_tool":
            await asyncio.sleep(0.2)  # Wait for tool swing animation
        return result

    def _find_slot_by_type(self, state: Optional[Dict], item_type: str) -> Optional[int]:
        """Find first inventory slot containing item of given type."""
        if not state:
            return None
        inventory = state.get("inventory", [])
        for item in inventory:
            if item and item.get("type") == item_type:
                return item.get("slot")
        return None

    def _get_recovery(self, skill: Skill, failure_type: str) -> Optional[str]:
        if not skill.on_failure:
            return None
        if failure_type in skill.on_failure:
            return skill.on_failure[failure_type].get("recovery_skill")
        if "default" in skill.on_failure:
            return skill.on_failure["default"].get("recovery_skill")
        # Fallback to first entry
        first = next(iter(skill.on_failure.values()), None)
        if isinstance(first, dict):
            return first.get("recovery_skill")
        return None
