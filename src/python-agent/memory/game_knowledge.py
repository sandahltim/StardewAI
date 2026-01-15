import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "game_knowledge.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for key in [
        "loved_gifts",
        "liked_gifts",
        "neutral_gifts",
        "disliked_gifts",
        "hated_gifts",
        "locations",
        "notable_features",
        "ingredients",
    ]:
        if key in data and data[key]:
            data[key] = json.loads(data[key])
    return data


def get_npc_info(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM npcs WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_npc_gift_reaction(npc: str, item: str) -> str:
    info = get_npc_info(npc)
    if not info or not item:
        return "unknown"
    item_lower = item.strip().lower()
    if item_lower in (gift.lower() for gift in info.get("loved_gifts", [])):
        return "loved"
    if item_lower in (gift.lower() for gift in info.get("liked_gifts", [])):
        return "liked"
    if item_lower in (gift.lower() for gift in info.get("disliked_gifts", [])):
        return "disliked"
    if item_lower in (gift.lower() for gift in info.get("hated_gifts", [])):
        return "hated"
    if item_lower in (gift.lower() for gift in info.get("neutral_gifts", [])):
        return "neutral"
    return "unknown"


def get_crop_info(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM crops WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
    return dict(row) if row else None


def get_item_locations(name: str) -> List[str]:
    if not name:
        return []
    with _connect() as conn:
        row = conn.execute(
            "SELECT locations FROM items WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
    if not row or not row["locations"]:
        return []
    return json.loads(row["locations"])


def get_location_info(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM locations WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_locations_by_type(location_type: str) -> List[Dict[str, Any]]:
    if not location_type:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM locations WHERE lower(type) = lower(?) ORDER BY name",
            (location_type,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_events_for_day(season: str, day: int) -> List[Dict[str, Any]]:
    if not season or not day:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT season, day, event_name, event_type, description
            FROM calendar
            WHERE lower(season) = lower(?) AND day = ?
            ORDER BY event_type, event_name
            """,
            (season, day),
        ).fetchall()
    return [dict(row) for row in rows]


def get_upcoming_events(season: str, day: int, days_ahead: int = 7) -> List[Dict[str, Any]]:
    if not season or not day:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT season, day, event_name, event_type, description
            FROM calendar
            WHERE lower(season) = lower(?)
              AND day BETWEEN ? AND ?
            ORDER BY day, event_type, event_name
            """,
            (season, day, day + days_ahead),
        ).fetchall()
    return [dict(row) for row in rows]


def get_crops_for_season(season: str) -> List[Dict[str, Any]]:
    """Get all crops that can be grown in a given season."""
    if not season:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM crops WHERE season LIKE ? ORDER BY sell_price DESC",
            (f"%{season}%",),
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_npcs() -> List[Dict[str, Any]]:
    """Get all NPCs with their info."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM npcs ORDER BY name").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_birthday_npcs(season: str, day: int) -> List[str]:
    """Get NPCs whose birthday is on a given day."""
    birthday = f"{season} {day}"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name FROM npcs WHERE birthday = ?",
            (birthday,),
        ).fetchall()
    return [row["name"] for row in rows]


def format_npc_for_prompt(npc_name: str) -> str:
    """Format NPC info for inclusion in VLM prompt."""
    info = get_npc_info(npc_name)
    if not info:
        return f"{npc_name}: No data available"

    lines = [f"{npc_name}:"]
    if info.get("birthday"):
        lines.append(f"  Birthday: {info['birthday']}")
    if info.get("loved_gifts"):
        lines.append(f"  Loves: {', '.join(info['loved_gifts'][:5])}")
    if info.get("hated_gifts"):
        lines.append(f"  Hates: {', '.join(info['hated_gifts'][:3])}")
    if info.get("schedule_notes"):
        lines.append(f"  Usually: {info['schedule_notes']}")

    return "\n".join(lines)


def format_crop_for_prompt(crop_name: str) -> str:
    """Format crop info for inclusion in VLM prompt."""
    info = get_crop_info(crop_name)
    if not info:
        return f"{crop_name}: No data available"

    regrow_text = ""
    if info.get("regrows"):
        regrow_text = f", regrows every {info['regrow_days']} days"

    return (
        f"{crop_name}: {info['season']}, {info['growth_days']} days to grow, "
        f"sells for {info['sell_price']}g{regrow_text}"
    )
