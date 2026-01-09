"""Dataclasses for knowledge base entries."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class NPC:
    name: str
    location: Optional[str] = None
    schedule: Dict[str, str] = field(default_factory=dict)
    birthday: Optional[str] = None
    loved_gifts: List[str] = field(default_factory=list)
    liked_gifts: List[str] = field(default_factory=list)
    neutral_gifts: List[str] = field(default_factory=list)
    disliked_gifts: List[str] = field(default_factory=list)
    hated_gifts: List[str] = field(default_factory=list)


@dataclass
class Shop:
    name: str
    open_hours: Optional[str] = None


@dataclass
class Location:
    name: str
    connections: List[str] = field(default_factory=list)
    shops: List[Shop] = field(default_factory=list)


@dataclass
class Item:
    name: str
    category: Optional[str] = None
    sell_price: Optional[int] = None
    gift_quality: Optional[str] = None


@dataclass
class Event:
    name: str
    season: Optional[str] = None
    day: Optional[int] = None
    location: Optional[str] = None
