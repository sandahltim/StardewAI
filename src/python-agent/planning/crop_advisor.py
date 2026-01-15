"""
Crop Advisor - Smart crop selection based on profit and time remaining.

Answers: "What should I plant right now?"
- Considers current season and days remaining
- Ranks by profit per day
- Filters by what can still be harvested this season
- Checks affordability
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Season lengths (28 days each)
SEASON_DAYS = 28

# Crops NOT available at Pierre's (festival or special shop only)
# These should not be recommended for normal seed purchases
FESTIVAL_ONLY_CROPS = {
    "Strawberry",  # Egg Festival (Spring 13) only
    "Starfruit",   # Oasis shop only (desert, requires bus repair)
}

# Crop data - mirrors database but in-memory for speed
# Format: name -> (season, growth_days, seed_cost, sell_price, regrows, regrow_days)
CROP_DATA = {
    # Spring crops (sorted by profit_per_day)
    "Cauliflower": ("spring", 12, 80, 175, False, 0),
    "Kale": ("spring", 6, 70, 110, False, 0),
    "Potato": ("spring", 6, 50, 80, False, 0),
    "Garlic": ("spring", 4, 40, 60, False, 0),
    "Parsnip": ("spring", 4, 20, 35, False, 0),
    "Green Bean": ("spring", 10, 60, 40, True, 3),
    "Strawberry": ("spring", 8, 100, 120, True, 4),

    # Summer crops
    "Starfruit": ("summer", 13, 400, 750, False, 0),
    "Red Cabbage": ("summer", 9, 100, 260, False, 0),
    "Melon": ("summer", 12, 80, 250, False, 0),
    "Blueberry": ("summer", 13, 80, 50, True, 4),  # 3 berries per harvest
    "Hops": ("summer", 11, 60, 25, True, 1),
    "Tomato": ("summer", 11, 50, 60, True, 4),
    "Hot Pepper": ("summer", 5, 40, 40, True, 3),
    "Radish": ("summer", 6, 40, 90, False, 0),

    # Fall crops
    "Pumpkin": ("fall", 13, 100, 320, False, 0),
    "Artichoke": ("fall", 8, 30, 160, False, 0),
    "Amaranth": ("fall", 7, 70, 150, False, 0),
    "Yam": ("fall", 10, 60, 160, False, 0),
    "Beet": ("fall", 6, 20, 100, False, 0),
    "Bok Choy": ("fall", 4, 50, 80, False, 0),
    "Cranberries": ("fall", 7, 240, 75, True, 5),  # 2 berries per harvest
    "Grape": ("fall", 10, 60, 80, True, 3),
    "Eggplant": ("fall", 5, 20, 60, True, 5),
}

# Map crop names to their seed names at Pierre's
CROP_TO_SEED = {
    "Cauliflower": "cauliflower seeds",
    "Kale": "kale seeds",
    "Potato": "potato seeds",
    "Garlic": "garlic seeds",
    "Parsnip": "parsnip seeds",
    "Green Bean": "bean starter",
    "Strawberry": "strawberry seeds",  # Only at Egg Festival!
    "Starfruit": "starfruit seeds",
    "Red Cabbage": "red cabbage seeds",
    "Melon": "melon seeds",
    "Blueberry": "blueberry seeds",
    "Hops": "hops starter",
    "Tomato": "tomato seeds",
    "Hot Pepper": "pepper seeds",
    "Radish": "radish seeds",
    "Pumpkin": "pumpkin seeds",
    "Artichoke": "artichoke seeds",
    "Amaranth": "amaranth seeds",
    "Yam": "yam seeds",
    "Beet": "beet seeds",
    "Bok Choy": "bok choy seeds",
    "Cranberries": "cranberry seeds",
    "Grape": "grape starter",
    "Eggplant": "eggplant seeds",
}


@dataclass
class CropRecommendation:
    """A recommended crop to plant."""
    name: str
    seed_name: str
    seed_cost: int
    growth_days: int
    sell_price: int
    profit_per_day: float
    can_harvest_in_time: bool
    regrows: bool
    reason: str


def get_days_remaining(day: int) -> int:
    """Days remaining in current season (season is 28 days)."""
    return SEASON_DAYS - day


def calculate_profit_per_day(seed_cost: int, sell_price: int, growth_days: int,
                              regrows: bool, regrow_days: int, days_remaining: int) -> float:
    """
    Calculate profit per day for a crop.

    For non-regrow crops: (sell - cost) / growth_days
    For regrow crops: accounts for multiple harvests in remaining time
    """
    if growth_days <= 0:
        return 0.0

    if not regrows:
        return (sell_price - seed_cost) / growth_days

    # Regrow crop - calculate total harvests possible
    if days_remaining < growth_days:
        return 0.0  # Can't even get first harvest

    # First harvest after growth_days, then every regrow_days
    days_after_first = days_remaining - growth_days
    additional_harvests = days_after_first // regrow_days if regrow_days > 0 else 0
    total_harvests = 1 + additional_harvests
    total_revenue = sell_price * total_harvests

    return (total_revenue - seed_cost) / days_remaining


def get_best_crops(season: str, day: int, gold: int, count: int = 5) -> List[CropRecommendation]:
    """
    Get the best crops to plant right now.

    Args:
        season: Current season (spring, summer, fall)
        day: Current day (1-28)
        gold: Available gold
        count: Number of recommendations to return

    Returns:
        List of CropRecommendation sorted by profit_per_day
    """
    days_remaining = get_days_remaining(day)
    season_lower = season.lower()

    recommendations = []

    for crop_name, data in CROP_DATA.items():
        crop_season, growth_days, seed_cost, sell_price, regrows, regrow_days = data

        # Skip festival-only crops (not available at Pierre's)
        if crop_name in FESTIVAL_ONLY_CROPS:
            continue

        # Check if crop grows in this season
        if season_lower not in crop_season:
            continue

        # Check if we can harvest in time
        can_harvest = growth_days <= days_remaining

        # Calculate profit
        profit = calculate_profit_per_day(
            seed_cost, sell_price, growth_days,
            regrows, regrow_days, days_remaining
        )

        # Skip if negative profit or can't afford
        if profit <= 0 and can_harvest:
            continue

        seed_name = CROP_TO_SEED.get(crop_name, f"{crop_name.lower()} seeds")

        # Determine reason
        if not can_harvest:
            reason = f"Won't mature in time ({growth_days} days, only {days_remaining} left)"
        elif seed_cost > gold:
            reason = f"Can't afford ({seed_cost}g, have {gold}g)"
        elif regrows:
            reason = f"Regrows every {regrow_days} days - good long-term value"
        else:
            reason = f"{profit:.1f}g/day profit"

        recommendations.append(CropRecommendation(
            name=crop_name,
            seed_name=seed_name,
            seed_cost=seed_cost,
            growth_days=growth_days,
            sell_price=sell_price,
            profit_per_day=profit if can_harvest else 0,
            can_harvest_in_time=can_harvest,
            regrows=regrows,
            reason=reason,
        ))

    # Sort by profit per day (highest first), but only harvestable crops
    harvestable = [r for r in recommendations if r.can_harvest_in_time and r.seed_cost <= gold]
    harvestable.sort(key=lambda r: r.profit_per_day, reverse=True)

    return harvestable[:count]


def get_recommended_crop(season: str, day: int, gold: int) -> Optional[CropRecommendation]:
    """Get the single best crop to plant right now."""
    crops = get_best_crops(season, day, gold, count=1)
    return crops[0] if crops else None


def format_crop_advice(season: str, day: int, gold: int) -> str:
    """Format crop advice for logging/display."""
    crops = get_best_crops(season, day, gold, count=3)
    days_left = get_days_remaining(day)

    if not crops:
        return f"No suitable crops for {season} day {day} with {gold}g ({days_left} days left)"

    lines = [f"🌱 Crop Advice - {season.title()} Day {day} ({days_left} days left, {gold}g):"]
    for i, crop in enumerate(crops, 1):
        lines.append(f"  {i}. {crop.name}: {crop.seed_cost}g seed, {crop.growth_days}d grow, {crop.profit_per_day:.1f}g/day")

    return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    print(format_crop_advice("spring", 5, 500))
    print()
    print(format_crop_advice("spring", 20, 500))
    print()
    print(format_crop_advice("summer", 1, 1000))
