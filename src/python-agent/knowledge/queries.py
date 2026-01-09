"""Query helpers for the knowledge base."""

from functools import lru_cache
import re
from typing import Dict, List, Optional

from . import loader
from .models import Item, Location, NPC, Shop


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _parse_time_string(value: str) -> Optional[int]:
    if not value:
        return None
    text = value.strip().lower()
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def _parse_time_range(value: str) -> Optional[tuple]:
    if not value or "-" not in value:
        return None
    start_text, end_text = [part.strip() for part in value.split("-", 1)]
    start = _parse_time_string(start_text)
    end = _parse_time_string(end_text)
    if start is None or end is None:
        return None
    return start, end


def _time_in_range(time_minutes: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= time_minutes <= end
    return time_minutes >= start or time_minutes <= end


@lru_cache(maxsize=1)
def _npcs_by_name() -> Dict[str, NPC]:
    return { _normalize_name(npc.name): npc for npc in loader.load_npcs() if npc.name }


@lru_cache(maxsize=1)
def _locations_by_name() -> Dict[str, Location]:
    return { _normalize_name(loc.name): loc for loc in loader.load_locations() if loc.name }


@lru_cache(maxsize=1)
def _items_by_name() -> Dict[str, Item]:
    return { _normalize_name(item.name): item for item in loader.load_items() if item.name }


def _name_variants(value: str) -> List[str]:
    base = _normalize_name(value)
    variants = {base}
    if base.endswith(" shop"):
        variants.add(base[:-5].strip())
    variants.add(re.sub(r"'s$", "", base))
    return [variant for variant in variants if variant]


def _find_shop(shop_name: str) -> Optional[Shop]:
    targets = set(_name_variants(shop_name))
    for location in _locations_by_name().values():
        location_names = _name_variants(location.name)
        for shop in location.shops:
            shop_names = _name_variants(shop.name)
            if targets.intersection(location_names + shop_names):
                return shop
    return None


def is_shop_open(shop_name: str, time: str) -> bool:
    """Return True if the named shop is open at the given time (HH:MM or H:MM am/pm)."""
    shop = _find_shop(shop_name)
    if not shop or not shop.open_hours:
        return False
    time_minutes = _parse_time_string(time)
    if time_minutes is None:
        return False
    time_range = _parse_time_range(shop.open_hours)
    if not time_range:
        return False
    start, end = time_range
    return _time_in_range(time_minutes, start, end)


def get_npc_location(npc_name: str, time: str, day: Optional[str] = None) -> str:
    npc = _npcs_by_name().get(_normalize_name(npc_name))
    if not npc:
        return "Unknown"
    time_minutes = _parse_time_string(time)
    if time_minutes is not None and npc.schedule:
        schedule_key = None
        if day and day in npc.schedule:
            schedule_key = day
        elif "default" in npc.schedule:
            schedule_key = "default"
        if schedule_key:
            entry = npc.schedule.get(schedule_key)
            if isinstance(entry, str):
                location = _location_from_schedule(entry, time_minutes)
                if location:
                    return location
            if isinstance(entry, list):
                for schedule_line in entry:
                    location = _location_from_schedule(str(schedule_line), time_minutes)
                    if location:
                        return location
    if npc.location:
        return npc.location
    return "Unknown"


def _location_from_schedule(entry: str, time_minutes: int) -> Optional[str]:
    match = re.match(r"^([^\s]+\s*-[^\s]+)\s+(.+)$", entry.strip())
    if not match:
        return None
    time_range = _parse_time_range(match.group(1))
    if not time_range:
        return None
    start, end = time_range
    if _time_in_range(time_minutes, start, end):
        return match.group(2).strip()
    return None


def get_gift_quality(npc_name: str, item_name: str) -> str:
    npc = _npcs_by_name().get(_normalize_name(npc_name))
    item = _items_by_name().get(_normalize_name(item_name))
    if npc:
        normalized_item = _normalize_name(item_name)
        if normalized_item in { _normalize_name(name) for name in npc.loved_gifts }:
            return "loved"
        if normalized_item in { _normalize_name(name) for name in npc.liked_gifts }:
            return "liked"
        if normalized_item in { _normalize_name(name) for name in npc.disliked_gifts }:
            return "disliked"
        if normalized_item in { _normalize_name(name) for name in npc.hated_gifts }:
            return "hated"
        if normalized_item in { _normalize_name(name) for name in npc.neutral_gifts }:
            return "neutral"
    if item and item.gift_quality:
        return item.gift_quality.lower()
    return "neutral"


def get_location_connections(location_name: str) -> List[str]:
    location = _locations_by_name().get(_normalize_name(location_name))
    if not location:
        return []
    return list(location.connections)
