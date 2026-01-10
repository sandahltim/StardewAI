"""Execute skill action sequences."""
from __future__ import annotations

import asyncio
from string import Formatter
from typing import Any, Dict, Iterable, List, Optional

from .models import ExecutionResult, Skill


class SkillExecutor:
    def __init__(self, action_executor: Any):
        self.action_executor = action_executor

    async def execute(self, skill: Skill, params: dict, state: Dict) -> ExecutionResult:
        actions_taken: List[str] = []
        for action in skill.actions:
            action_type = action.action_type
            resolved = self._resolve_params(action.params, params)
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
        # Handle select_item_type: find slot by item type (e.g., "seed", "tool")
        if action_type == "select_item_type":
            item_type = params.get("type", params.get("value", ""))
            slot = self._find_slot_by_type(state, item_type)
            if slot is None:
                return False
            return await self._dispatch("select_slot", {"slot": slot}, state)
        executor = self.action_executor
        if hasattr(executor, "execute_action"):
            return bool(executor.execute_action(action_type, params))
        if hasattr(executor, "execute"):
            return bool(executor.execute({"action_type": action_type, "params": params}))
        if callable(executor):
            return bool(executor(action_type, params))
        return False

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
