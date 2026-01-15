#!/usr/bin/env python3
"""Integration test for action verification (Session 115).

Tests that till/plant/water actions actually modify game state.
Run with game open and SMAPI mod loaded.

Usage:
    source venv/bin/activate
    python scripts/test_action_verification.py
"""

import httpx
import time
import sys
import json

BASE_URL = "http://localhost:8790"


def get_farm_state():
    """Get farm state from SMAPI."""
    try:
        resp = httpx.get(f"{BASE_URL}/farm", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except Exception as e:
        print(f"ERROR: Failed to get farm state: {e}")
    return None


def get_player_state():
    """Get player state from SMAPI."""
    try:
        resp = httpx.get(f"{BASE_URL}/state", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except Exception as e:
        print(f"ERROR: Failed to get player state: {e}")
    return None


def send_action(action: str, **params):
    """Send action to SMAPI."""
    payload = {"action": action, **params}
    try:
        resp = httpx.post(f"{BASE_URL}/action", json=payload, timeout=5)
        result = resp.json()
        success = result.get("success", False)
        msg = result.get("data", {}).get("message", result.get("error", ""))
        return success, msg
    except Exception as e:
        return False, str(e)


def test_till_verification():
    """Test tilling a tile and verifying it appears in tilledTiles."""
    print("\n" + "=" * 60)
    print("TEST: Till Verification")
    print("=" * 60)

    # Get initial state
    farm = get_farm_state()
    if not farm:
        print("FAIL: Cannot get farm state")
        return False

    tilled_before = {(t.get("x"), t.get("y")) for t in farm.get("tilledTiles", [])}
    print(f"Tilled tiles before: {len(tilled_before)}")

    # Get player position
    state = get_player_state()
    if not state:
        print("FAIL: Cannot get player state")
        return False

    player = state.get("player", {})
    px, py = player.get("tileX", 0), player.get("tileY", 0)
    print(f"Player at: ({px}, {py})")

    # Target tile to north
    target_x, target_y = px, py - 1
    print(f"Target tile: ({target_x}, {target_y})")

    if (target_x, target_y) in tilled_before:
        print(f"NOTE: Target already tilled, picking different spot")
        target_x, target_y = px + 1, py - 1
        print(f"New target: ({target_x}, {target_y})")

    # Move to position south of target
    stand_x, stand_y = target_x, target_y + 1
    if (px, py) != (stand_x, stand_y):
        print(f"Moving to ({stand_x}, {stand_y})...")
        success, msg = send_action("move_to", target={"x": stand_x, "y": stand_y})
        print(f"  Move result: {success} - {msg}")
        time.sleep(1.0)

    # Equip hoe
    print("Selecting Hoe...")
    success, msg = send_action("select_item_type", itemType="Hoe")
    print(f"  Select result: {success} - {msg}")
    time.sleep(0.2)

    # Face north
    print("Facing north...")
    success, msg = send_action("face", direction="north")
    print(f"  Face result: {success} - {msg}")
    time.sleep(0.1)

    # Use tool
    print("Using tool (till)...")
    success, msg = send_action("use_tool", direction="north")
    print(f"  Tool result: {success} - {msg}")
    time.sleep(0.5)  # Wait for animation

    # VERIFY: Check if tile is now tilled
    print("\nVerifying...")
    time.sleep(0.3)  # Wait for SMAPI cache refresh
    farm_after = get_farm_state()
    if not farm_after:
        print("FAIL: Cannot get farm state after action")
        return False

    tilled_after = {(t.get("x"), t.get("y")) for t in farm_after.get("tilledTiles", [])}
    print(f"Tilled tiles after: {len(tilled_after)}")

    if (target_x, target_y) in tilled_after:
        print(f"✓ PASS: Tile ({target_x}, {target_y}) is now tilled!")
        return True
    else:
        print(f"✗ FAIL: Tile ({target_x}, {target_y}) NOT in tilledTiles!")
        new_tiles = tilled_after - tilled_before
        if new_tiles:
            print(f"  New tilled tiles: {new_tiles}")
        return False


def test_plant_verification():
    """Test planting a seed and verifying it appears in crops."""
    print("\n" + "=" * 60)
    print("TEST: Plant Verification")
    print("=" * 60)

    # Get initial state
    farm = get_farm_state()
    state = get_player_state()
    if not farm or not state:
        print("FAIL: Cannot get state")
        return False

    # Find a tilled tile without crop
    tilled = farm.get("tilledTiles", [])
    crops = {(c.get("x"), c.get("y")) for c in farm.get("crops", [])}

    empty_tilled = [(t.get("x"), t.get("y")) for t in tilled if (t.get("x"), t.get("y")) not in crops]

    if not empty_tilled:
        print("SKIP: No empty tilled tiles to plant on")
        return None

    target_x, target_y = empty_tilled[0]
    print(f"Target empty tilled tile: ({target_x}, {target_y})")

    # Check for seeds
    inventory = state.get("inventory", [])
    seed_slot = None
    for i, item in enumerate(inventory):
        if item and "seed" in item.get("name", "").lower():
            seed_slot = i
            print(f"Found seeds: {item.get('name')} at slot {i}")
            break

    if seed_slot is None:
        print("SKIP: No seeds in inventory")
        return None

    crops_before = len(crops)
    print(f"Crops before: {crops_before}")

    # Move to position south of target
    stand_x, stand_y = target_x, target_y + 1
    print(f"Moving to ({stand_x}, {stand_y})...")
    success, msg = send_action("move_to", target={"x": stand_x, "y": stand_y})
    time.sleep(1.0)

    # Select seeds
    print(f"Selecting slot {seed_slot}...")
    success, msg = send_action("select_slot", slot=seed_slot)
    time.sleep(0.2)

    # Face north
    print("Facing north...")
    success, msg = send_action("face", direction="north")
    time.sleep(0.1)

    # Use tool (plant)
    print("Using tool (plant)...")
    success, msg = send_action("use_tool", direction="north")
    print(f"  Plant result: {success} - {msg}")
    time.sleep(0.5)

    # VERIFY
    print("\nVerifying...")
    time.sleep(0.3)
    farm_after = get_farm_state()
    if not farm_after:
        print("FAIL: Cannot get farm state after action")
        return False

    crops_after = {(c.get("x"), c.get("y")) for c in farm_after.get("crops", [])}
    print(f"Crops after: {len(crops_after)}")

    if (target_x, target_y) in crops_after:
        print(f"✓ PASS: Crop planted at ({target_x}, {target_y})!")
        return True
    else:
        print(f"✗ FAIL: No crop at ({target_x}, {target_y})!")
        new_crops = crops_after - crops
        if new_crops:
            print(f"  New crops: {new_crops}")
        return False


def test_water_verification():
    """Test watering a crop and verifying isWatered changes."""
    print("\n" + "=" * 60)
    print("TEST: Water Verification")
    print("=" * 60)

    # Get initial state
    farm = get_farm_state()
    state = get_player_state()
    if not farm or not state:
        print("FAIL: Cannot get state")
        return False

    # Find an unwatered crop
    unwatered = [c for c in farm.get("crops", []) if not c.get("isWatered", False)]

    if not unwatered:
        print("SKIP: No unwatered crops")
        return None

    target = unwatered[0]
    target_x, target_y = target.get("x"), target.get("y")
    print(f"Target unwatered crop: ({target_x}, {target_y}) - {target.get('cropName', 'unknown')}")

    # Check watering can
    player = state.get("player", {})
    water_left = player.get("wateringCanWater", 0)
    print(f"Watering can: {water_left} water")

    if water_left <= 0:
        print("SKIP: Watering can empty")
        return None

    # Move to position south of target
    stand_x, stand_y = target_x, target_y + 1
    print(f"Moving to ({stand_x}, {stand_y})...")
    success, msg = send_action("move_to", target={"x": stand_x, "y": stand_y})
    time.sleep(1.0)

    # Select watering can
    print("Selecting Watering Can...")
    success, msg = send_action("select_item_type", itemType="Watering Can")
    time.sleep(0.2)

    # Face north
    print("Facing north...")
    success, msg = send_action("face", direction="north")
    time.sleep(0.1)

    # Use tool (water)
    print("Using tool (water)...")
    success, msg = send_action("use_tool", direction="north")
    print(f"  Water result: {success} - {msg}")
    time.sleep(0.5)

    # VERIFY
    print("\nVerifying...")
    time.sleep(0.3)
    farm_after = get_farm_state()
    if not farm_after:
        print("FAIL: Cannot get farm state after action")
        return False

    # Find the crop at target position
    crop_after = None
    for c in farm_after.get("crops", []):
        if c.get("x") == target_x and c.get("y") == target_y:
            crop_after = c
            break

    if crop_after and crop_after.get("isWatered", False):
        print(f"✓ PASS: Crop at ({target_x}, {target_y}) is now watered!")
        return True
    else:
        print(f"✗ FAIL: Crop at ({target_x}, {target_y}) NOT watered!")
        if crop_after:
            print(f"  Crop state: {json.dumps(crop_after, indent=2)}")
        return False


def main():
    print("=" * 60)
    print("ACTION VERIFICATION TEST (Session 115)")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  - Stardew Valley running with SMAPI mod")
    print("  - Player on Farm")
    print("  - Some clear ground for tilling")
    print("  - Seeds in inventory (optional)")
    print("  - Water in watering can (optional)")

    # Test connection
    print("\nTesting SMAPI connection...")
    farm = get_farm_state()
    if not farm:
        print("ERROR: Cannot connect to SMAPI at http://localhost:8790")
        print("Make sure Stardew Valley is running with the GameBridge mod.")
        sys.exit(1)
    print(f"✓ Connected! Farm has {len(farm.get('crops', []))} crops")

    results = {}

    # Run tests
    results["till"] = test_till_verification()
    results["plant"] = test_plant_verification()
    results["water"] = test_water_verification()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    for test, result in results.items():
        if result is True:
            print(f"  ✓ {test}: PASSED")
            passed += 1
        elif result is False:
            print(f"  ✗ {test}: FAILED")
            failed += 1
        else:
            print(f"  - {test}: SKIPPED")
            skipped += 1

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n⚠ VERIFICATION FAILURES DETECTED!")
        print("Actions are not affecting game state as expected.")
        sys.exit(1)
    else:
        print("\n✓ All tests passed or skipped!")
        sys.exit(0)


if __name__ == "__main__":
    main()
