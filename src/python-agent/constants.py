"""
Centralized constants for StardewAI.

All hardcoded game values should be defined here for easy maintenance.
These are DEFAULT values - dynamic detection should be preferred when available.
"""

# =============================================================================
# TOOL SLOTS (Default positions in new game inventory)
# =============================================================================
# These are the typical starting positions. Skills should scan inventory
# when possible, but these serve as fallbacks.
TOOL_SLOTS = {
    "Axe": 0,
    "Hoe": 1,
    "Watering Can": 2,
    "Pickaxe": 3,
    "Scythe": 4,
}

# Reverse lookup: slot -> tool name
SLOT_TO_TOOL = {v: k for k, v in TOOL_SLOTS.items()}

# =============================================================================
# SEED PRICES (Pierre's shop)
# =============================================================================
SEED_PRICES = {
    # Spring
    "parsnip": 20,
    "potato": 50,
    "cauliflower": 80,
    "green bean": 60,
    "kale": 70,
    "garlic": 40,
    "jazz seeds": 30,
    "tulip bulb": 20,
    # Summer
    "melon": 80,
    "blueberry": 80,
    "corn": 150,
    "tomato": 50,
    "hot pepper": 40,
    "wheat": 10,
    "radish": 40,
    "red cabbage": 100,
    "starfruit": 400,
    "poppy": 100,
    "summer spangle": 50,
    # Fall
    "pumpkin": 100,
    "cranberry": 240,
    "eggplant": 20,
    "grape": 60,
    "amaranth": 70,
    "artichoke": 30,
    "beet": 20,
    "bok choy": 50,
    "yam": 60,
    "fairy seeds": 200,
    "sunflower": 200,
}

# =============================================================================
# SEASONAL CROPS
# =============================================================================
SPRING_CROPS = [
    "Parsnip", "Green Bean", "Cauliflower", "Potato",
    "Kale", "Garlic", "Blue Jazz", "Tulip",
]

SUMMER_CROPS = [
    "Melon", "Blueberry", "Hot Pepper", "Tomato",
    "Corn", "Wheat", "Radish", "Red Cabbage",
    "Starfruit", "Poppy", "Summer Spangle",
]

FALL_CROPS = [
    "Corn", "Eggplant", "Pumpkin", "Grape",
    "Cranberries", "Amaranth", "Artichoke", "Beet",
    "Bok Choy", "Yam", "Fairy Rose", "Sunflower",
]

# Crops reserved for bundles/gifts (don't auto-sell)
RESERVED_CROPS = [
    # Community center bundles - Spring
    "Parsnip", "Green Bean", "Cauliflower", "Potato",
    # Community center bundles - Summer
    "Melon", "Blueberry", "Hot Pepper", "Tomato",
    # Community center bundles - Fall
    "Corn", "Eggplant", "Pumpkin",
]

# =============================================================================
# DEFAULT LOCATIONS (Fallbacks when SMAPI data unavailable)
# =============================================================================
# These should only be used when dynamic data isn't available
DEFAULT_LOCATIONS = {
    "shipping_bin": (71, 14),      # Farm shipping bin
    "water_pond": (72, 31),         # Farm pond (common)
    "farmhouse_door": (64, 15),     # Exit from farmhouse lands here
    "pierre_door": (43, 57),        # Pierre's shop entrance (Town)
}

# =============================================================================
# DEBRIS TYPES (for clearing)
# =============================================================================
DEBRIS_TOOLS = {
    "Weeds": "Scythe",
    "Stone": "Pickaxe",
    "Twig": "Axe",
    "Wood": "Axe",
    "Boulder": "Pickaxe",  # Upgraded pickaxe needed
    "Stump": "Axe",        # Upgraded axe needed
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tool_slot(tool_name: str, inventory: list = None) -> int:
    """
    Get the inventory slot for a tool.

    If inventory is provided, scans it to find the actual slot.
    Otherwise returns the default slot.
    """
    if inventory:
        for i, item in enumerate(inventory):
            if item and item.get("name") == tool_name:
                return i
    return TOOL_SLOTS.get(tool_name, 0)


def get_season_crops(season: str) -> list:
    """Get list of crops for a season."""
    season_lower = season.lower()
    if season_lower == "spring":
        return SPRING_CROPS
    elif season_lower == "summer":
        return SUMMER_CROPS
    elif season_lower == "fall":
        return FALL_CROPS
    return []


def get_seed_price(crop_name: str) -> int:
    """Get seed price for a crop (returns 0 if unknown)."""
    return SEED_PRICES.get(crop_name.lower(), 0)
