#!/usr/bin/env python3
import csv
import io
import json
import sqlite3
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/aftonsteps/stardewdata/master/"
DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "data"
DB_PATH = DATA_DIR / "game_knowledge.db"

CSV_FILES = {
    "npc_dispositions": "NPC%20Dispositions.csv",
    "npc_gift_tastes": "NPC%20Gift%20Tastes.csv",
    "universal_gifts": "Universal%20Gift%20Tastes.csv",
    "objects": "Objects.csv",
    "crops": "Crops.csv",
    "crop_objects": "Crops%20Object%20Information.csv",
    "seeds": "Seeds%20Object%20Information.csv",
    "locations": "Locations.csv",
    "cooking": "Cooking%20Recipes.csv",
    "crafting": "Crafting%20Recipes.csv",
}

CATEGORY_LABELS = {
    -2: "Gem",
    -4: "Fish",
    -5: "Egg",
    -6: "Milk",
    -7: "Cooking",
    -8: "Crafting",
    -12: "Mineral",
    -14: "Meat",
    -15: "Metal",
    -16: "Building Resource",
    -17: "Animal Product",
    -18: "Artisan Goods",
    -19: "Syrup",
    -20: "Trash",
    -21: "Bait",
    -22: "Tackle",
    -23: "Fertilizer",
    -24: "Seeds",
    -25: "Vegetable",
    -26: "Fruit",
    -27: "Flower",
    -28: "Forage",
    -74: "Seed",
    -75: "Vegetable",
    -79: "Fish",
    -80: "Egg",
    -81: "Milk",
}

TOOL_ITEMS = [
    {"name": "Hoe", "category": "Tool", "description": "Used to till soil.", "price": 0},
    {"name": "Watering Can", "category": "Tool", "description": "Used to water crops.", "price": 0},
    {"name": "Pickaxe", "category": "Tool", "description": "Breaks rocks and stones.", "price": 0},
    {"name": "Axe", "category": "Tool", "description": "Chops trees and stumps.", "price": 0},
    {"name": "Fishing Rod", "category": "Tool", "description": "Used to catch fish.", "price": 0},
    {"name": "Scythe", "category": "Tool", "description": "Cuts grass and weeds.", "price": 0},
]

FORAGE_FALLBACK = {
    "spring": ["Leek", "Daffodil", "Dandelion", "Spring Onion"],
    "summer": ["Grape", "Spice Berry", "Sweet Pea"],
    "fall": ["Hazelnut", "Wild Plum", "Blackberry"],
    "winter": ["Crystal Fruit", "Crocus", "Holly"],
}

LOCATION_TYPE_OVERRIDES = {
    "Farm": "Farm",
    "FarmHouse": "Farm",
    "Greenhouse": "Farm",
    "Barn": "Farm",
    "Coop": "Farm",
    "Town": "Town",
    "SeedShop": "Building",
    "Blacksmith": "Building",
    "Saloon": "Building",
    "Hospital": "Building",
    "JojaMart": "Building",
    "Beach": "Nature",
    "Forest": "Nature",
    "Mountain": "Nature",
    "Desert": "Nature",
    "Railroad": "Nature",
    "Mine": "Mine",
}

SCHEDULE_NOTES = {
    "Abigail": "Hangs around Pierre's or the cemetery. Plays flute on rainy afternoons.",
    "Alex": "Works out at the beach on sunny days. Often at the ice cream stand in summer.",
    "Elliott": "Lives in the beach cabin. Often on the beach or at the saloon evenings.",
    "Emily": "Works at the Saloon evenings. Spends afternoons at home or town square.",
    "Haley": "Often at home or by the fountain. Shops in town afternoons.",
    "Harvey": "Runs the clinic 9am-3pm. Spends evenings at the saloon.",
    "Leah": "Lives in the forest cottage. Often in Cindersap Forest afternoons.",
    "Maru": "Works at the clinic Tue/Thu. Spends time in the lab or at home.",
    "Penny": "Teaches Jas and Vincent at museum 10am-2pm Tue/Wed/Fri.",
    "Sam": "Hangs at home or the beach. Plays pool at the saloon evenings.",
    "Sebastian": "Often in his room; visits the mountain or saloon evenings.",
    "Shane": "Works at JojaMart 9am-5pm. Drinks at Saloon evenings.",
    "Pierre": "Runs Pierre's General Store 9am-5pm. Closed Wednesdays.",
    "Marnie": "Runs the ranch most days. Visits the saloon some evenings.",
    "Gus": "Runs the Saloon daily 12pm-12am.",
    "Clint": "Runs the Blacksmith most days (9am-4pm).",
    "Robin": "Runs the Carpenter's Shop. Closed Tuesdays.",
    "Willy": "At the Fish Shop/Beach mornings and afternoons.",
}

CALENDAR_EVENTS = [
    {"season": "Spring", "day": 13, "name": "Egg Festival", "type": "festival", "description": "Town festival with egg hunt."},
    {"season": "Spring", "day": 24, "name": "Flower Dance", "type": "festival", "description": "Dance in the forest."},
    {"season": "Summer", "day": 11, "name": "Luau", "type": "festival", "description": "Community potluck at the beach."},
    {"season": "Summer", "day": 28, "name": "Dance of the Moonlight Jellies", "type": "festival", "description": "Night festival at the beach."},
    {"season": "Fall", "day": 16, "name": "Stardew Valley Fair", "type": "festival", "description": "Grange display and fair games."},
    {"season": "Fall", "day": 27, "name": "Spirit's Eve", "type": "festival", "description": "Spooky festival in town."},
    {"season": "Winter", "day": 8, "name": "Festival of Ice", "type": "festival", "description": "Ice fishing and snowman contest."},
    {"season": "Winter", "day": 15, "name": "Night Market", "type": "festival", "description": "Night Market on the beach."},
    {"season": "Winter", "day": 16, "name": "Night Market", "type": "festival", "description": "Night Market on the beach."},
    {"season": "Winter", "day": 17, "name": "Night Market", "type": "festival", "description": "Night Market on the beach."},
    {"season": "Winter", "day": 25, "name": "Feast of the Winter Star", "type": "festival", "description": "Gift exchange in town."},
]


def fetch_csv(name: str):
    url = BASE_URL + name
    req = urllib.request.Request(url, headers={"User-Agent": "stardewai"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def build_object_maps(rows):
    by_id = {}
    for row in rows:
        try:
            item_id = int(row["Object Id"])
        except (KeyError, ValueError):
            continue
        name = row.get("English Name") or row.get("Name")
        raw_category = row.get("Category") or ""
        category_label = row.get("Type") or ""
        try:
            category_id = int(raw_category)
        except ValueError:
            category_id = None
        if category_id in CATEGORY_LABELS:
            category_label = CATEGORY_LABELS[category_id]
        by_id[item_id] = {
            "name": name,
            "price": int(row.get("Price") or 0),
            "category": category_label or raw_category,
            "description": row.get("Description") or "",
        }
    return by_id


def parse_item_ids(raw: str, object_map):
    if not raw:
        return []
    names = []
    for token in raw.split():
        try:
            item_id = int(token)
        except ValueError:
            continue
        if item_id in object_map:
            names.append(object_map[item_id]["name"])
        elif item_id in CATEGORY_LABELS:
            names.append(f"Category:{CATEGORY_LABELS[item_id]}")
        else:
            names.append(f"Id:{item_id}")
    return names


def parse_id_list(raw: str):
    if not raw or raw.strip() == "-1":
        return []
    ids = []
    for token in raw.split():
        try:
            value = int(token)
        except ValueError:
            continue
        if value == -1:
            continue
        ids.append(value)
    return ids


def parse_fishing_list(raw: str):
    if not raw or raw.strip() == "-1":
        return []
    values = []
    tokens = raw.split()
    for i in range(0, len(tokens), 2):
        try:
            item_id = int(tokens[i])
        except ValueError:
            continue
        if item_id == -1:
            continue
        values.append(item_id)
    return values


def find_seed_for_crop(crop_name, seed_rows):
    crop_lower = crop_name.lower()
    candidates = []
    for row in seed_rows:
        seed_name = row.get("English Name") or row.get("Name") or ""
        if crop_lower in seed_name.lower():
            candidates.append(row)
    if not candidates:
        return None
    for row in candidates:
        if "seed" in (row.get("English Name") or "").lower():
            return row
    return candidates[0]


def parse_recipe_ingredients(raw, object_map):
    if not raw:
        return {}
    parts = raw.split()
    ingredients = {}
    for i in range(0, len(parts), 2):
        try:
            item_id = int(parts[i])
            qty = int(parts[i + 1])
        except (ValueError, IndexError):
            continue
        if item_id in object_map:
            name = object_map[item_id]["name"]
        elif item_id in CATEGORY_LABELS:
            name = f"Category:{CATEGORY_LABELS[item_id]}"
        else:
            name = f"Id:{item_id}"
        ingredients[name] = qty
    return ingredients


def add_location_entry(item_locations, name, location, season, kind):
    if not name:
        return
    label = f"{location} ({season} {kind})"
    item_locations.setdefault(name, set()).add(label)


def create_schema(conn):
    conn.executescript(
        """
        DROP TABLE IF EXISTS npcs;
        DROP TABLE IF EXISTS crops;
        DROP TABLE IF EXISTS items;
        DROP TABLE IF EXISTS locations;
        DROP TABLE IF EXISTS recipes;

        CREATE TABLE npcs (
            name TEXT PRIMARY KEY,
            birthday TEXT,
            location TEXT,
            loved_gifts TEXT,
            liked_gifts TEXT,
            neutral_gifts TEXT,
            disliked_gifts TEXT,
            hated_gifts TEXT,
            schedule_notes TEXT
        );

        CREATE TABLE crops (
            name TEXT PRIMARY KEY,
            season TEXT,
            growth_days INTEGER,
            regrows INTEGER,
            regrow_days INTEGER,
            sell_price INTEGER,
            seed_name TEXT,
            seed_price INTEGER
        );

        CREATE TABLE items (
            name TEXT PRIMARY KEY,
            category TEXT,
            description TEXT,
            sell_price INTEGER,
            locations TEXT
        );

        CREATE TABLE locations (
            name TEXT PRIMARY KEY,
            type TEXT,
            unlocked_by TEXT,
            notable_features TEXT
        );

        CREATE TABLE recipes (
            name TEXT PRIMARY KEY,
            type TEXT,
            ingredients TEXT,
            unlock_condition TEXT
        );

        CREATE TABLE calendar (
            season TEXT,
            day INTEGER,
            event_name TEXT,
            event_type TEXT,
            description TEXT,
            PRIMARY KEY (season, day, event_name)
        );
        """
    )


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    objects = fetch_csv(CSV_FILES["objects"])
    object_map = build_object_maps(objects)
    seeds = fetch_csv(CSV_FILES["seeds"])

    npcs = fetch_csv(CSV_FILES["npc_dispositions"])
    npc_gifts = {row["Name"]: row for row in fetch_csv(CSV_FILES["npc_gift_tastes"])}

    crops = fetch_csv(CSV_FILES["crops"])
    crop_objects = fetch_csv(CSV_FILES["crop_objects"])
    crop_object_map = build_object_maps(crop_objects)

    locations = fetch_csv(CSV_FILES["locations"])
    cooking = fetch_csv(CSV_FILES["cooking"])
    crafting = fetch_csv(CSV_FILES["crafting"])

    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)

        for row in npcs:
            name = row.get("Name", "").strip()
            if not name:
                continue
            gifts = npc_gifts.get(name, {})
            loved = parse_item_ids(gifts.get("Loved Items", ""), object_map)
            liked = parse_item_ids(gifts.get("Liked Items", ""), object_map)
            neutral = parse_item_ids(gifts.get("Neutral Items", ""), object_map)
            disliked = parse_item_ids(gifts.get("Disliked Items", ""), object_map)
            hated = parse_item_ids(gifts.get("Hated Items", ""), object_map)
            location = row.get("Start Location") or row.get("Home Region") or ""

            conn.execute(
                """
                INSERT INTO npcs
                (name, birthday, location, loved_gifts, liked_gifts, neutral_gifts, disliked_gifts, hated_gifts, schedule_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    row.get("Birthday") or "",
                    location,
                    json.dumps(loved),
                    json.dumps(liked),
                    json.dumps(neutral),
                    json.dumps(disliked),
                    json.dumps(hated),
                    SCHEDULE_NOTES.get(name, ""),
                ),
            )

        for row in crops:
            try:
                harvest_id = int(row.get("Index Of Harvest") or 0)
            except ValueError:
                harvest_id = 0
            crop_name = ""
            sell_price = 0
            if harvest_id in crop_object_map:
                crop_name = crop_object_map[harvest_id]["name"]
                sell_price = crop_object_map[harvest_id]["price"]
            elif harvest_id in object_map:
                crop_name = object_map[harvest_id]["name"]
                sell_price = object_map[harvest_id]["price"]
            if not crop_name:
                continue

            stages = [
                int(row.get("Days in Stage 1 Growth") or 0),
                int(row.get("Days in Stage 2 Growth") or 0),
                int(row.get("Days in Stage 3 Growth") or 0),
                int(row.get("Days in Stage 4 Growth") or 0),
                int(row.get("Days in Stage 5 Growth") or 0),
            ]
            growth_days = sum(stages)
            regrow_days = int(row.get("Regrow After Harvest") or -1)
            regrows = 1 if regrow_days and regrow_days > 0 else 0

            seed_row = find_seed_for_crop(crop_name, seeds)
            seed_name = seed_row.get("English Name") if seed_row else ""
            seed_price = int(seed_row.get("Sell Price") or 0) if seed_row else 0

            conn.execute(
                """
                INSERT INTO crops
                (name, season, growth_days, regrows, regrow_days, sell_price, seed_name, seed_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    crop_name,
                    row.get("Growth Seasons") or "",
                    growth_days,
                    regrows,
                    regrow_days if regrows else 0,
                    sell_price,
                    seed_name,
                    seed_price,
                ),
            )

        item_locations = {}
        for row in locations:
            location_name = row.get("Name") or ""
            for season_key in ["Spring", "Summer", "Fall", "Winter"]:
                forage_raw = row.get(f"{season_key} Foraging") or ""
                for item_id in parse_id_list(forage_raw):
                    item = object_map.get(item_id)
                    if item:
                        add_location_entry(item_locations, item["name"], location_name, season_key, "forage")

                fish_raw = row.get(f"{season_key} Fishing") or ""
                for item_id in parse_fishing_list(fish_raw):
                    item = object_map.get(item_id)
                    if item:
                        add_location_entry(item_locations, item["name"], location_name, season_key, "fishing")

        for season, items in FORAGE_FALLBACK.items():
            season_title = season.capitalize()
            for name in items:
                item_locations.setdefault(name, set()).add(f"General ({season_title} forage)")

        for item in object_map.values():
            conn.execute(
                """
                INSERT OR IGNORE INTO items (name, category, description, sell_price, locations)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item["name"],
                    item["category"],
                    item["description"],
                    item["price"],
                    json.dumps(sorted(item_locations.get(item["name"], []))),
                ),
            )

        for tool in TOOL_ITEMS:
            conn.execute(
                """
                INSERT OR IGNORE INTO items (name, category, description, sell_price, locations)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tool["name"],
                    tool["category"],
                    tool["description"],
                    tool["price"],
                    json.dumps([]),
                ),
            )

        for row in locations:
            name = row.get("Name", "").strip()
            if not name:
                continue
            location_type = LOCATION_TYPE_OVERRIDES.get(name, "Unknown")
            features = []
            for season_key in ["Spring", "Summer", "Fall", "Winter"]:
                if (row.get(f"{season_key} Foraging") or "") not in ("", "-1") and "foraging" not in features:
                    features.append("foraging")
                if (row.get(f"{season_key} Fishing") or "") not in ("", "-1") and "fishing" not in features:
                    features.append("fishing")
            if (row.get("Artifact Data") or "") not in ("", "-1"):
                features.append("artifacts")
            conn.execute(
                """
                INSERT INTO locations (name, type, unlocked_by, notable_features)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    location_type,
                    "",
                    json.dumps(features),
                ),
            )

        for row in cooking:
            name = row.get("Name", "").strip()
            if not name:
                continue
            ingredients = parse_recipe_ingredients(row.get("Ingredients", ""), object_map)
            conn.execute(
                """
                INSERT INTO recipes (name, type, ingredients, unlock_condition)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    "Cooking",
                    json.dumps(ingredients),
                    row.get("Unlock Conditions") or "",
                ),
            )

        for row in crafting:
            name = row.get("Name", "").strip()
            if not name:
                continue
            ingredients = parse_recipe_ingredients(row.get("Ingredients", ""), object_map)
            conn.execute(
                """
                INSERT INTO recipes (name, type, ingredients, unlock_condition)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    "Crafting",
                    json.dumps(ingredients),
                    row.get("Unlock Conditions") or "",
                ),
            )

        for event in CALENDAR_EVENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO calendar (season, day, event_name, event_type, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["season"],
                    event["day"],
                    event["name"],
                    event["type"],
                    event["description"],
                ),
            )

        for season in ["Spring", "Summer", "Fall", "Winter"]:
            for day in [5, 7, 12, 14, 19, 21, 26, 28]:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO calendar (season, day, event_name, event_type, description)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        season,
                        day,
                        "Traveling Cart",
                        "shop",
                        "Traveling Cart at Cindersap Forest (Fri/Sun).",
                    ),
                )

        conn.commit()
        print(f"Game knowledge DB built at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
