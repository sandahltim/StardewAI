# Session 118: Fix Farmable Tile Validation

**Last Updated:** 2026-01-15 Session 117 by Claude
**Priority:** CRITICAL BUG FIX

---

## Session 117 Summary

### Completed: Verification Improvements
1. **Diagnostic logging** - `verify_watered()` and `verify_planted()` now log exactly what they see when failing
2. **Increased wait times** - Water: 0.5s → 1.0s, Plant: 0.3s → 0.5s
3. **Retry mechanisms** - All verification failures now retry once before recording failure

### CRITICAL BUG DISCOVERED: Invalid Tile Selection

**Problem:** Agent tried to till/plant on farmhouse lawn - tiles that CANNOT be farmed.

**Root Cause:** `_batch_till_and_plant()` selects grid positions based on:
- Not in `existing_tilled` or `existing_crops`
- Not blocked by `resourceClumps` (stumps/boulders)
- Not in `objects`, `grass`, `debris`

**MISSING:** Validation that tiles are actually **tillable ground** (not building footprints, paths, water, etc.)

---

## Bug Location

**File:** `src/python-agent/unified_agent.py`
**Method:** `_batch_till_and_plant()` (lines ~3785-4006)
**Issue:** Grid generation at lines ~3860-3880

```python
# Current (BROKEN) - only checks for blockers, not tillability
unclearable = permanent_blocked | clump_blocked
grid_positions = []
for row in range(count // GRID_WIDTH + 2):
    for col in range(GRID_WIDTH):
        x = start_x + col
        y = start_y + row
        if (x, y) not in unclearable:  # ← NOT ENOUGH!
            grid_positions.append((x, y))
```

---

## Fix Required

### Option A: Use SMAPI `/passable-area` endpoint
Check if tile is passable AND not a building:
```python
# Before adding to grid:
passable = self.controller.check_passable(x, y)
if passable and (x, y) not in unclearable:
    grid_positions.append((x, y))
```

### Option B: Use `/farm` tilledTiles + known good areas
The farm has specific tillable regions. Could define bounds:
```python
FARMHOUSE_BOUNDS = {"x_min": 56, "x_max": 69, "y_min": 8, "y_max": 16}  # Approximate
# Skip tiles inside farmhouse area
```

### Option C: Pre-check with hoe (most accurate)
Before committing to a tile, verify `canTill` from surroundings:
```python
# Get tile info from surroundings
tile_info = surroundings.get("adjacentTiles", {}).get("north", {})
if tile_info.get("canTill", False):
    # Safe to till
```

**Recommendation:** Option A is cleanest if `/passable-area` works. Option C is most game-accurate.

---

## Code Changes Made (Session 117)

### 1. Diagnostic Logging
```python
# verify_watered() - line 2023-2025
if not is_watered:
    logging.warning(f"verify_watered({x},{y}): Crop exists but isWatered=False (crop={crop.get('cropName', '?')})")

# verify_planted() - line 2007-2008
if not result:
    logging.warning(f"verify_planted({x},{y}): NOT in crops (total_crops={len(crops)})")
```

### 2. Water Verification Retry (lines 3967-3987)
```python
await asyncio.sleep(1.0)  # Increased from 0.5s
water_verified = self.controller.verify_watered(x, y)
if not water_verified:
    logging.info(f"💧 Water verification failed at ({x},{y}), retrying...")
    self.controller.execute(Action("use_tool", {"direction": "north"}, "water"))
    await asyncio.sleep(1.0)
    water_verified = self.controller.verify_watered(x, y)
```

### 3. Plant Verification Retry (lines 3959-3980)
```python
await asyncio.sleep(0.5)  # Increased from 0.3s
plant_verified = self.controller.verify_planted(x, y)
if not plant_verified:
    logging.info(f"🌱 Plant verification failed at ({x},{y}), retrying...")
    # Re-select seeds and retry
    await asyncio.sleep(0.5)
    plant_verified = self.controller.verify_planted(x, y)
```

### 4. Similar fix in `_batch_water_remaining()` (lines 3321-3352)

---

## Testing Checklist for Session 118

### Test 1: Validate Grid Positions
After implementing fix, run agent and verify:
```bash
python src/python-agent/unified_agent.py --goal "Plant seeds"
```
- Grid positions should NOT include farmhouse area
- All tilled positions should be valid farmland

### Test 2: Verification Rates
Check verification after fix:
```bash
curl -s localhost:9001/api/verification-status | jq
```
Target: >90% for till, plant, AND water

### Test 3: Full Cycle
If verification passes, test complete farm chores cycle.

---

## Quick Reference

**SMAPI Endpoints for Tile Validation:**
- `GET /passable?x=N&y=N` - Is tile passable?
- `GET /surroundings` - Returns `adjacentTiles` with `canTill`, `canPlant` flags
- `GET /farm` - Returns `tilledTiles` array (known good positions)

**Farmhouse approximate bounds (Standard Farm):**
- Building: x=57-68, y=9-15 (rough - verify in game)
- Porch/entrance: extends south a few tiles

---

## Commits This Session

None yet - changes not committed due to critical bug discovery.

**Changed files (uncommitted):**
- `src/python-agent/unified_agent.py` - Verification improvements + retry logic

---

## Session 118 Priority

1. **FIX:** Add tillable validation to `_batch_till_and_plant()` grid selection
2. **TEST:** Verify grid excludes farmhouse/buildings
3. **TEST:** Run verification tests, target >90%
4. **COMMIT:** All fixes once verified working

-- Claude
