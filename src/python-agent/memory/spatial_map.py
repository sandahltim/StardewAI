"""Simple spatial memory map stored as JSON per location."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_BASE_DIR = Path("/home/tim/StardewAI/logs/spatial_map")


@dataclass
class TileEntry:
    x: int
    y: int
    data: Dict[str, Any]


class SpatialMap:
    """Lightweight spatial map with JSON persistence."""

    def __init__(self, location: str, base_dir: Path = DEFAULT_BASE_DIR) -> None:
        self.location = location or "Unknown"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / f"{self.location}.json"
        self._tiles: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._tiles = {}
            return
        try:
            data = json.loads(self.path.read_text())
            self._tiles = data.get("tiles", {})
        except json.JSONDecodeError:
            self._tiles = {}

    def _save(self) -> None:
        payload = {
            "location": self.location,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "tiles": self._tiles,
        }
        self.path.write_text(json.dumps(payload, indent=2))

    def _key(self, x: int, y: int) -> str:
        return f"{x},{y}"

    def get_tile(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        return self._tiles.get(self._key(x, y))

    def set_tile(self, x: int, y: int, data: Dict[str, Any]) -> Dict[str, Any]:
        key = self._key(x, y)
        entry = dict(data)
        entry["x"] = x
        entry["y"] = y
        entry["updated_at"] = entry.get("updated_at") or datetime.now().isoformat(timespec="seconds")
        self._tiles[key] = entry
        self._save()
        return entry

    def update_tiles(self, tiles: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        updated: List[Dict[str, Any]] = []
        for tile in tiles:
            x = tile.get("x")
            y = tile.get("y")
            if x is None or y is None:
                continue
            updated.append(self.set_tile(int(x), int(y), tile))
        return updated

    def find_tiles(
        self,
        state: Optional[str] = None,
        crop: Optional[str] = None,
        watered: Optional[bool] = None,
        not_planted: bool = False,
        not_worked: bool = False,
    ) -> List[TileEntry]:
        results: List[TileEntry] = []
        for key, data in self._tiles.items():
            try:
                x_str, y_str = key.split(",", 1)
                x = int(x_str)
                y = int(y_str)
            except ValueError:
                continue
            if state and data.get("state") != state:
                continue
            if crop and data.get("crop") != crop:
                continue
            if watered is not None and bool(data.get("watered")) != watered:
                continue
            if not_planted and data.get("crop"):
                continue
            if not_worked and data.get("worked_at"):
                continue
            results.append(TileEntry(x=x, y=y, data=data))
        return results

    def as_list(self) -> List[Dict[str, Any]]:
        tiles = []
        for entry in self.find_tiles():
            tiles.append(entry.data)
        return tiles
