"""Check skill preconditions against game state."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import PreconditionResult, Skill, SkillPrecondition


class PreconditionChecker:
    def check(self, skill: Skill, state: Dict) -> PreconditionResult:
        failures: List[str] = []
        suggestions: List[str] = []
        for pre in skill.preconditions:
            ok, message, suggestion = self._check_one(pre, state)
            if not ok:
                failures.append(message)
                if suggestion:
                    suggestions.append(suggestion)
        return PreconditionResult(met=not failures, failures=failures, suggestions=suggestions)

    def _check_one(self, pre: SkillPrecondition, state: Dict) -> Tuple[bool, str, Optional[str]]:
        checker = {
            "adjacent_to": self._adjacent_to,
            "equipped": self._equipped,
            "has_item": self._has_item,
            "resource_above": self._resource_above,
            "location_is": self._location_is,
            "time_between": self._time_between,
        }.get(pre.type)
        if not checker:
            return False, f"Unknown precondition: {pre.type}", None
        return checker(pre.params, state)

    def _player_pos(self, state: Dict) -> Tuple[Optional[int], Optional[int]]:
        player = state.get("player") or {}
        return player.get("tileX"), player.get("tileY")

    def _adjacent_to(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        target = params.get("target")
        name = params.get("name")
        x, y = self._player_pos(state)
        if x is None or y is None:
            return False, "player position unknown", "Wait for state sync"
        loc = state.get("location") or {}
        crops = loc.get("crops") or []
        npcs = loc.get("npcs") or []
        objects = loc.get("objects") or []

        def is_adjacent(tx: int, ty: int) -> bool:
            return abs(tx - x) + abs(ty - y) == 1

        if target in ("crop", "unwatered_crop", "ready_crop"):
            for crop in crops:
                if target == "unwatered_crop" and crop.get("isWatered", False):
                    continue
                if target == "ready_crop" and not crop.get("isReadyForHarvest", False):
                    continue
                if is_adjacent(crop.get("x"), crop.get("y")):
                    return True, "", None
            return False, f"not adjacent to {target}", "Move next to target crop"

        if target == "npc":
            for npc in npcs:
                if name and npc.get("name") != name:
                    continue
                if is_adjacent(npc.get("tileX"), npc.get("tileY")):
                    return True, "", None
            return False, "not adjacent to npc", "Move next to npc"

        if target == "object":
            for obj in objects:
                if name and obj.get("name") != name:
                    continue
                if is_adjacent(obj.get("x"), obj.get("y")):
                    return True, "", None
            return False, "not adjacent to object", "Move next to object"

        if target == "water_source":
            # Check surroundings for water tiles adjacent to player
            # Surroundings data uses "directions" key and "blocker" field
            surroundings = state.get("surroundings") or {}
            directions = surroundings.get("directions") or surroundings  # Handle both formats
            for direction in ["north", "south", "east", "west"]:
                dir_data = directions.get(direction) or {}
                # Water shows as blocker="water" with tilesUntilBlocked=0
                blocker = dir_data.get("blocker", "")
                tiles_until = dir_data.get("tilesUntilBlocked", 99)
                if blocker and "water" in blocker.lower() and tiles_until == 0:
                    return True, "", None
            # Also check if NearestWater is at distance 1 or less
            nearest_water = surroundings.get("nearestWater") or loc.get("nearestWater") or {}
            if nearest_water.get("distance", 99) <= 1:
                return True, "", None
            return False, "not adjacent to water", "Move next to water source"

        return False, f"unknown adjacent target: {target}", None

    def _equipped(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        item = params.get("item")
        current = (state.get("player") or {}).get("currentTool")
        if not item:
            return False, "equipped item not specified", None
        if current and current.lower() == str(item).lower():
            return True, "", None
        return False, f"not equipped: {item}", f"Select {item}"

    def _has_item(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        item = params.get("item")
        if not item:
            return False, "item not specified", None
        inventory = state.get("inventory") or []
        for entry in inventory:
            if entry.get("name") == item and entry.get("stack", 0) > 0:
                return True, "", None
        return False, f"missing item: {item}", f"Find {item}"

    def _resource_above(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        resource = params.get("resource")
        minimum = params.get("minimum", 1)
        player = state.get("player") or {}
        resource_map = {
            "watering_can_water": player.get("wateringCanWater"),
            "energy": player.get("energy"),
            "health": player.get("health"),
        }
        value = resource_map.get(resource)
        if value is None:
            return False, f"resource unknown: {resource}", None
        if value >= minimum:
            return True, "", None
        return False, f"{resource} below {minimum}", f"Restore {resource}"

    def _location_is(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        location = params.get("location")
        current = (state.get("location") or {}).get("name")
        if not location:
            return False, "location not specified", None
        if current == location:
            return True, "", None
        return False, f"not in {location}", f"Go to {location}"

    def _time_between(self, params: Dict, state: Dict) -> Tuple[bool, str, Optional[str]]:
        start = params.get("start")
        end = params.get("end")
        time_state = state.get("time") or {}
        hour = time_state.get("hour")
        minute = time_state.get("minute", 0)
        if hour is None:
            return False, "time unknown", None
        current = hour * 60 + minute
        start_min = self._parse_time(start)
        end_min = self._parse_time(end)
        if start_min is None or end_min is None:
            return False, "invalid time range", None
        if start_min <= current <= end_min:
            return True, "", None
        return False, "time outside range", "Wait for correct time"

    def _parse_time(self, value) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value) * 60
        if isinstance(value, str):
            parts = value.split(":")
            if not parts:
                return None
            try:
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                return None
            return hour * 60 + minute
        return None
