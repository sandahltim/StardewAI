#!/usr/bin/env python3
"""
Create Stardew Valley game knowledge database.
Populates NPCs (marriage candidates with gift preferences) and crops.

Data sourced from Stardew Valley Wiki - manually curated for accuracy.
Run once to create the database, re-run to reset/update.
"""

import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "game_knowledge.db"

# === SCHEMA ===

SCHEMA = """
-- NPCs and their preferences
CREATE TABLE IF NOT EXISTS npcs (
    name TEXT PRIMARY KEY,
    birthday TEXT,           -- "Spring 4"
    location TEXT,           -- Default location
    loved_gifts TEXT,        -- JSON array
    liked_gifts TEXT,
    neutral_gifts TEXT,
    disliked_gifts TEXT,
    hated_gifts TEXT,
    schedule_notes TEXT
);

-- Crop information
CREATE TABLE IF NOT EXISTS crops (
    name TEXT PRIMARY KEY,
    season TEXT,             -- "Spring", "Summer", etc.
    growth_days INTEGER,
    regrows BOOLEAN,
    regrow_days INTEGER,
    sell_price INTEGER,
    seed_name TEXT,
    seed_price INTEGER
);
"""

# === NPC DATA (Marriage Candidates) ===
# Gift preferences from Stardew Valley Wiki

NPCS = [
    # === BACHELORETTES ===
    {
        "name": "Abigail",
        "birthday": "Fall 13",
        "location": "Pierre's General Store",
        "loved_gifts": ["Amethyst", "Banana Pudding", "Blackberry Cobbler", "Chocolate Cake", "Pufferfish", "Pumpkin", "Spicy Eel"],
        "liked_gifts": ["Quartz", "Ancient Fruit", "Apple", "Apricot", "Artichoke", "Banana", "Beer", "Blueberry", "Cactus Fruit", "Cherry", "Coconut", "Cranberries", "Fairy Rose", "Fig", "Fruit Salad", "Grape", "Hot Pepper", "Mango", "Mead", "Melon", "Orange", "Pale Ale", "Peach", "Pineapple", "Plum", "Pomegranate", "Powdermelon", "Qi Fruit", "Red Plate", "Rhubarb", "Salmonberry", "Spice Berry", "Starfruit", "Strawberry", "Summer Spangle", "Tropical Curry", "Wild Plum", "Wine"],
        "neutral_gifts": ["All Eggs", "All Milk"],
        "disliked_gifts": ["Clay", "Copper Ore", "Gold Ore", "Iron Ore", "Iridium Ore", "Stone", "Wood"],
        "hated_gifts": ["Holly", "Sugar", "Wheat Flour", "Wild Horseradish"],
        "schedule_notes": "Usually at Pierre's shop. Goes to graveyard on rainy days. Plays pool at Saloon Fridays."
    },
    {
        "name": "Emily",
        "birthday": "Spring 27",
        "location": "2 Willow Lane (with Haley)",
        "loved_gifts": ["Amethyst", "Aquamarine", "Cloth", "Emerald", "Jade", "Ruby", "Survival Burger", "Topaz", "Wool"],
        "liked_gifts": ["Daffodil", "Quartz", "All Gems"],
        "neutral_gifts": ["All Eggs", "All Milk", "All Fruit"],
        "disliked_gifts": ["Fried Eel", "Ice Cream", "Rice Pudding", "Spicy Eel"],
        "hated_gifts": ["Fish Taco", "Holly", "Salmon Dinner", "Salmonberry"],
        "schedule_notes": "Works at Saloon Tues-Sun evenings. Home mornings. Does aerobics at Caroline's Tuesdays."
    },
    {
        "name": "Haley",
        "birthday": "Spring 14",
        "location": "2 Willow Lane (with Emily)",
        "loved_gifts": ["Coconut", "Fruit Salad", "Pink Cake", "Sunflower"],
        "liked_gifts": ["Daffodil", "All Universal Likes"],
        "neutral_gifts": ["All Eggs", "All Milk"],
        "disliked_gifts": ["Clay", "All Fish", "Wild Horseradish"],
        "hated_gifts": ["Holly", "Prismatic Shard"],
        "schedule_notes": "Takes photos around town. Beach on sunny days. Dark Shrine when 6+ hearts."
    },
    {
        "name": "Leah",
        "birthday": "Winter 23",
        "location": "Leah's Cottage (Cindersap Forest)",
        "loved_gifts": ["Goat Cheese", "Poppyseed Muffin", "Salad", "Stir Fry", "Truffle", "Vegetable Medley", "Wine"],
        "liked_gifts": ["Chanterelle", "Common Mushroom", "Daffodil", "Dandelion", "Driftwood", "Hazelnut", "Holly", "Leek", "Morel", "Purple Mushroom", "Snow Yam", "Winter Root", "All Eggs", "All Fruit"],
        "neutral_gifts": ["All Milk"],
        "disliked_gifts": ["Bread", "Fried Egg", "Hashbrowns", "Omelet", "Pancakes", "Pizza", "Tortilla"],
        "hated_gifts": ["Void Egg"],
        "schedule_notes": "Works on art in cottage. Goes to beach or bridge. Visits Saloon evenings."
    },
    {
        "name": "Maru",
        "birthday": "Summer 10",
        "location": "Carpenter's Shop (Mountain)",
        "loved_gifts": ["Battery Pack", "Cauliflower", "Cheese Cauliflower", "Diamond", "Gold Bar", "Iridium Bar", "Miner's Treat", "Pepper Poppers", "Radioactive Bar", "Rhubarb Pie", "Strawberry"],
        "liked_gifts": ["Copper Bar", "Iron Bar", "Oak Resin", "Pine Tar", "All Fruit"],
        "neutral_gifts": ["All Eggs", "All Milk", "All Vegetables"],
        "disliked_gifts": ["Honey", "Maple Syrup", "Pickles"],
        "hated_gifts": ["Holly", "Truffle"],
        "schedule_notes": "Works at Harvey's clinic Tues/Thurs. At home other days. Stargazes at night."
    },
    {
        "name": "Penny",
        "birthday": "Fall 2",
        "location": "Trailer (east of town)",
        "loved_gifts": ["Diamond", "Emerald", "Melon", "Poppy", "Poppyseed Muffin", "Red Plate", "Roots Platter", "Sandfish", "Tom Kha Soup"],
        "liked_gifts": ["Artichoke Dip", "Book", "Dandelion", "Leek", "All Milk"],
        "neutral_gifts": ["All Eggs", "All Fruit"],
        "disliked_gifts": ["Algae Soup", "Grape", "Hops", "Pale Ale", "Rabbit's Foot"],
        "hated_gifts": ["Beer", "Holly", "Mead", "Pale Ale", "Piña Colada", "Wine"],
        "schedule_notes": "Teaches Jas and Vincent at museum. Reads at library. Walks by river."
    },
    # === BACHELORS ===
    {
        "name": "Alex",
        "birthday": "Summer 13",
        "location": "1 River Road (with grandparents)",
        "loved_gifts": ["Complete Breakfast", "Jack Be Nimble, Jack Be Thick", "Salmon Dinner"],
        "liked_gifts": ["All Eggs"],
        "neutral_gifts": ["All Fruit", "All Milk"],
        "disliked_gifts": ["All Vegetables"],
        "hated_gifts": ["Holly", "Salmonberry"],
        "schedule_notes": "Exercises on beach summer. At home other seasons. Plays gridball."
    },
    {
        "name": "Elliott",
        "birthday": "Fall 5",
        "location": "Elliott's Cabin (Beach)",
        "loved_gifts": ["Crab Cakes", "Duck Feather", "Lobster", "Pomegranate", "Squid Ink", "Tom Kha Soup"],
        "liked_gifts": ["All Fruit", "Octopus", "Squid"],
        "neutral_gifts": ["All Eggs", "All Milk"],
        "disliked_gifts": ["Amaranth", "Chanterelle", "Common Mushroom", "Morel", "Purple Mushroom", "Quartz"],
        "hated_gifts": ["Holly", "Pizza", "Sea Urchin"],
        "schedule_notes": "Writes in cabin. Visits beach and bridge. Goes to library on rainy days."
    },
    {
        "name": "Harvey",
        "birthday": "Winter 14",
        "location": "Harvey's Clinic (Town)",
        "loved_gifts": ["Coffee", "Pickles", "Super Meal", "Truffle Oil", "Wine"],
        "liked_gifts": ["Chanterelle", "Common Mushroom", "Daffodil", "Dandelion", "Duck Egg", "Duck Feather", "Goat Milk", "Hazelnut", "Holly", "Large Goat Milk", "Leek", "Morel", "Purple Mushroom", "Quartz", "Snow Yam", "Spring Onion", "Wild Horseradish", "Winter Root", "All Fruit"],
        "neutral_gifts": ["All Eggs", "All Milk"],
        "disliked_gifts": ["Coral", "Nautilus Shell", "Rainbow Shell", "Spice Berry"],
        "hated_gifts": ["Fried Eel", "Spicy Eel"],
        "schedule_notes": "Works at clinic daily. Exercises in room. Studies planes. Has coffee at saloon."
    },
    {
        "name": "Sam",
        "birthday": "Summer 17",
        "location": "1 Willow Lane",
        "loved_gifts": ["Cactus Fruit", "Maple Bar", "Pizza", "Tigerseye"],
        "liked_gifts": ["Egg", "Joja Cola", "All Eggs except Void Egg"],
        "neutral_gifts": ["All Fruit", "All Milk"],
        "disliked_gifts": ["Duck Mayonnaise", "Mayonnaise"],
        "hated_gifts": ["Holly", "Sea Cucumber"],
        "schedule_notes": "Skateboards near museum. Band practice with Sebastian/Abigail. Works at JojaMart."
    },
    {
        "name": "Sebastian",
        "birthday": "Winter 10",
        "location": "Carpenter's Shop (basement room)",
        "loved_gifts": ["Frog Egg", "Frozen Tear", "Obsidian", "Pumpkin Soup", "Sashimi", "Void Egg"],
        "liked_gifts": ["Quartz", "All Eggs except Void Egg", "All Milk"],
        "neutral_gifts": ["All Fruit"],
        "disliked_gifts": ["Clay", "Complete Breakfast", "Farmer's Lunch", "Fried Egg", "Omelet"],
        "hated_gifts": ["Holly"],
        "schedule_notes": "Stays in basement room often. Smokes by lake at night. Band practice Fridays."
    },
    {
        "name": "Shane",
        "birthday": "Spring 20",
        "location": "Marnie's Ranch",
        "loved_gifts": ["Beer", "Hot Pepper", "Pepper Poppers", "Pizza"],
        "liked_gifts": ["All Eggs", "All Fruit"],
        "neutral_gifts": ["All Milk"],
        "disliked_gifts": ["Pickles", "Quartz", "Seaweed", "Wild Horseradish"],
        "hated_gifts": ["Holly"],
        "schedule_notes": "Works at JojaMart. Drinks at Saloon evenings. Visits chicken coop at ranch."
    },
]

# === CROP DATA ===
# Base prices, growth times from wiki

CROPS = [
    # === SPRING ===
    {"name": "Parsnip", "season": "Spring", "growth_days": 4, "regrows": False, "regrow_days": None, "sell_price": 35, "seed_name": "Parsnip Seeds", "seed_price": 20},
    {"name": "Green Bean", "season": "Spring", "growth_days": 10, "regrows": True, "regrow_days": 3, "sell_price": 40, "seed_name": "Bean Starter", "seed_price": 60},
    {"name": "Cauliflower", "season": "Spring", "growth_days": 12, "regrows": False, "regrow_days": None, "sell_price": 175, "seed_name": "Cauliflower Seeds", "seed_price": 80},
    {"name": "Potato", "season": "Spring", "growth_days": 6, "regrows": False, "regrow_days": None, "sell_price": 80, "seed_name": "Potato Seeds", "seed_price": 50},
    {"name": "Garlic", "season": "Spring", "growth_days": 4, "regrows": False, "regrow_days": None, "sell_price": 60, "seed_name": "Garlic Seeds", "seed_price": 40},
    {"name": "Kale", "season": "Spring", "growth_days": 6, "regrows": False, "regrow_days": None, "sell_price": 110, "seed_name": "Kale Seeds", "seed_price": 70},
    {"name": "Rhubarb", "season": "Spring", "growth_days": 13, "regrows": False, "regrow_days": None, "sell_price": 220, "seed_name": "Rhubarb Seeds", "seed_price": 100},
    {"name": "Strawberry", "season": "Spring", "growth_days": 8, "regrows": True, "regrow_days": 4, "sell_price": 120, "seed_name": "Strawberry Seeds", "seed_price": 100},
    {"name": "Coffee Bean", "season": "Spring,Summer", "growth_days": 10, "regrows": True, "regrow_days": 2, "sell_price": 15, "seed_name": "Coffee Bean", "seed_price": 2500},
    {"name": "Blue Jazz", "season": "Spring", "growth_days": 7, "regrows": False, "regrow_days": None, "sell_price": 50, "seed_name": "Jazz Seeds", "seed_price": 30},
    {"name": "Tulip", "season": "Spring", "growth_days": 6, "regrows": False, "regrow_days": None, "sell_price": 30, "seed_name": "Tulip Bulb", "seed_price": 20},

    # === SUMMER ===
    {"name": "Melon", "season": "Summer", "growth_days": 12, "regrows": False, "regrow_days": None, "sell_price": 250, "seed_name": "Melon Seeds", "seed_price": 80},
    {"name": "Tomato", "season": "Summer", "growth_days": 11, "regrows": True, "regrow_days": 4, "sell_price": 60, "seed_name": "Tomato Seeds", "seed_price": 50},
    {"name": "Blueberry", "season": "Summer", "growth_days": 13, "regrows": True, "regrow_days": 4, "sell_price": 50, "seed_name": "Blueberry Seeds", "seed_price": 80},
    {"name": "Hot Pepper", "season": "Summer", "growth_days": 5, "regrows": True, "regrow_days": 3, "sell_price": 40, "seed_name": "Pepper Seeds", "seed_price": 40},
    {"name": "Wheat", "season": "Summer,Fall", "growth_days": 4, "regrows": False, "regrow_days": None, "sell_price": 25, "seed_name": "Wheat Seeds", "seed_price": 10},
    {"name": "Radish", "season": "Summer", "growth_days": 6, "regrows": False, "regrow_days": None, "sell_price": 90, "seed_name": "Radish Seeds", "seed_price": 40},
    {"name": "Red Cabbage", "season": "Summer", "growth_days": 9, "regrows": False, "regrow_days": None, "sell_price": 260, "seed_name": "Red Cabbage Seeds", "seed_price": 100},
    {"name": "Starfruit", "season": "Summer", "growth_days": 13, "regrows": False, "regrow_days": None, "sell_price": 750, "seed_name": "Starfruit Seeds", "seed_price": 400},
    {"name": "Corn", "season": "Summer,Fall", "growth_days": 14, "regrows": True, "regrow_days": 4, "sell_price": 50, "seed_name": "Corn Seeds", "seed_price": 150},
    {"name": "Hops", "season": "Summer", "growth_days": 11, "regrows": True, "regrow_days": 1, "sell_price": 25, "seed_name": "Hops Starter", "seed_price": 60},
    {"name": "Sunflower", "season": "Summer,Fall", "growth_days": 8, "regrows": False, "regrow_days": None, "sell_price": 80, "seed_name": "Sunflower Seeds", "seed_price": 200},
    {"name": "Poppy", "season": "Summer", "growth_days": 7, "regrows": False, "regrow_days": None, "sell_price": 140, "seed_name": "Poppy Seeds", "seed_price": 100},
    {"name": "Summer Spangle", "season": "Summer", "growth_days": 8, "regrows": False, "regrow_days": None, "sell_price": 90, "seed_name": "Spangle Seeds", "seed_price": 50},

    # === FALL ===
    {"name": "Eggplant", "season": "Fall", "growth_days": 5, "regrows": True, "regrow_days": 5, "sell_price": 60, "seed_name": "Eggplant Seeds", "seed_price": 20},
    {"name": "Pumpkin", "season": "Fall", "growth_days": 13, "regrows": False, "regrow_days": None, "sell_price": 320, "seed_name": "Pumpkin Seeds", "seed_price": 100},
    {"name": "Bok Choy", "season": "Fall", "growth_days": 4, "regrows": False, "regrow_days": None, "sell_price": 80, "seed_name": "Bok Choy Seeds", "seed_price": 50},
    {"name": "Yam", "season": "Fall", "growth_days": 10, "regrows": False, "regrow_days": None, "sell_price": 160, "seed_name": "Yam Seeds", "seed_price": 60},
    {"name": "Cranberries", "season": "Fall", "growth_days": 7, "regrows": True, "regrow_days": 5, "sell_price": 75, "seed_name": "Cranberry Seeds", "seed_price": 240},
    {"name": "Beet", "season": "Fall", "growth_days": 6, "regrows": False, "regrow_days": None, "sell_price": 100, "seed_name": "Beet Seeds", "seed_price": 20},
    {"name": "Artichoke", "season": "Fall", "growth_days": 8, "regrows": False, "regrow_days": None, "sell_price": 160, "seed_name": "Artichoke Seeds", "seed_price": 30},
    {"name": "Amaranth", "season": "Fall", "growth_days": 7, "regrows": False, "regrow_days": None, "sell_price": 150, "seed_name": "Amaranth Seeds", "seed_price": 70},
    {"name": "Grape", "season": "Fall", "growth_days": 10, "regrows": True, "regrow_days": 3, "sell_price": 80, "seed_name": "Grape Starter", "seed_price": 60},
    {"name": "Fairy Rose", "season": "Fall", "growth_days": 12, "regrows": False, "regrow_days": None, "sell_price": 290, "seed_name": "Fairy Seeds", "seed_price": 200},

    # === SPECIAL/MULTI-SEASON ===
    {"name": "Ancient Fruit", "season": "Spring,Summer,Fall", "growth_days": 28, "regrows": True, "regrow_days": 7, "sell_price": 550, "seed_name": "Ancient Seeds", "seed_price": 0},
    {"name": "Sweet Gem Berry", "season": "Fall", "growth_days": 24, "regrows": False, "regrow_days": None, "sell_price": 3000, "seed_name": "Rare Seed", "seed_price": 1000},
]


def create_database():
    """Create the database and populate with data."""

    # Remove existing database to start fresh
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create schema
    cursor.executescript(SCHEMA)
    print("Created database schema")

    # Insert NPCs
    npc_count = 0
    for npc in NPCS:
        cursor.execute("""
            INSERT INTO npcs (name, birthday, location, loved_gifts, liked_gifts,
                            neutral_gifts, disliked_gifts, hated_gifts, schedule_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            npc["name"],
            npc["birthday"],
            npc["location"],
            json.dumps(npc["loved_gifts"]),
            json.dumps(npc["liked_gifts"]),
            json.dumps(npc["neutral_gifts"]),
            json.dumps(npc["disliked_gifts"]),
            json.dumps(npc["hated_gifts"]),
            npc["schedule_notes"]
        ))
        npc_count += 1
    print(f"Inserted {npc_count} NPCs (marriage candidates)")

    # Insert crops
    crop_count = 0
    for crop in CROPS:
        cursor.execute("""
            INSERT INTO crops (name, season, growth_days, regrows, regrow_days,
                             sell_price, seed_name, seed_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            crop["name"],
            crop["season"],
            crop["growth_days"],
            crop["regrows"],
            crop["regrow_days"],
            crop["sell_price"],
            crop["seed_name"],
            crop["seed_price"]
        ))
        crop_count += 1
    print(f"Inserted {crop_count} crops")

    conn.commit()
    conn.close()

    print(f"\nDatabase created: {DB_PATH}")
    print(f"Total size: {DB_PATH.stat().st_size / 1024:.1f} KB")

    return DB_PATH


def verify_database():
    """Print summary of database contents."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n=== DATABASE SUMMARY ===\n")

    # NPCs
    print("MARRIAGE CANDIDATES:")
    cursor.execute("SELECT name, birthday FROM npcs ORDER BY name")
    for row in cursor.fetchall():
        print(f"  - {row[0]} (Birthday: {row[1]})")

    # Sample NPC query
    print("\n--- Sample: Shane's gift preferences ---")
    cursor.execute("SELECT loved_gifts, hated_gifts FROM npcs WHERE name = 'Shane'")
    row = cursor.fetchone()
    if row:
        loved = json.loads(row[0])
        hated = json.loads(row[1])
        print(f"  Loved: {', '.join(loved)}")
        print(f"  Hated: {', '.join(hated)}")

    # Crops by season
    print("\n--- Crops by Season ---")
    for season in ["Spring", "Summer", "Fall"]:
        cursor.execute("""
            SELECT COUNT(*) FROM crops
            WHERE season LIKE ?
        """, (f"%{season}%",))
        count = cursor.fetchone()[0]
        print(f"  {season}: {count} crops")

    # Top profitable crops
    print("\n--- Top 5 Most Profitable Crops (by sell price) ---")
    cursor.execute("""
        SELECT name, season, sell_price, growth_days
        FROM crops
        ORDER BY sell_price DESC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[2]}g ({row[1]}, {row[3]} days)")

    # Regrowable crops
    print("\n--- Regrowable Crops ---")
    cursor.execute("""
        SELECT name, season, regrow_days
        FROM crops
        WHERE regrows = 1
        ORDER BY regrow_days
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: every {row[2]} days ({row[1]})")

    conn.close()


if __name__ == "__main__":
    create_database()
    verify_database()
