"""Load knowledge base data from YAML files."""

from pathlib import Path
from typing import Dict, List

import yaml

from .models import Event, Item, Location, NPC, Shop


KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge"


def _load_yaml_list(filename: str) -> List[Dict]:
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or []
    if isinstance(data, list):
        return data
    return []


def load_npcs() -> List[NPC]:
    npcs: List[NPC] = []
    for entry in _load_yaml_list("npcs.yaml"):
        schedule = entry.get("schedule") or {}
        if not isinstance(schedule, dict):
            schedule = {}
        npcs.append(
            NPC(
                name=entry.get("name", "").strip(),
                location=entry.get("location"),
                schedule=schedule,
                birthday=entry.get("birthday"),
                loved_gifts=list(entry.get("loved_gifts") or []),
                liked_gifts=list(entry.get("liked_gifts") or []),
                neutral_gifts=list(entry.get("neutral_gifts") or []),
                disliked_gifts=list(entry.get("disliked_gifts") or []),
                hated_gifts=list(entry.get("hated_gifts") or []),
            )
        )
    return npcs


def load_locations() -> List[Location]:
    locations: List[Location] = []
    for entry in _load_yaml_list("locations.yaml"):
        shops: List[Shop] = []
        for shop_entry in entry.get("shops") or []:
            shops.append(
                Shop(
                    name=shop_entry.get("name", "").strip(),
                    open_hours=shop_entry.get("open_hours"),
                )
            )
        locations.append(
            Location(
                name=entry.get("name", "").strip(),
                connections=list(entry.get("connections") or []),
                shops=shops,
            )
        )
    return locations


def load_items() -> List[Item]:
    items: List[Item] = []
    for entry in _load_yaml_list("items.yaml"):
        sell_price = entry.get("sell_price")
        if isinstance(sell_price, str) and sell_price.isdigit():
            sell_price = int(sell_price)
        items.append(
            Item(
                name=entry.get("name", "").strip(),
                category=entry.get("category"),
                sell_price=sell_price,
                gift_quality=entry.get("gift_quality"),
            )
        )
    return items


def load_calendar() -> List[Event]:
    events: List[Event] = []
    for entry in _load_yaml_list("calendar.yaml"):
        day = entry.get("day")
        if isinstance(day, str) and day.isdigit():
            day = int(day)
        events.append(
            Event(
                name=entry.get("name", "").strip(),
                season=entry.get("season"),
                day=day,
                location=entry.get("location"),
            )
        )
    return events
