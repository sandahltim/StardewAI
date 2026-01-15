# Session 119: Verification Testing

**Last Updated:** 2026-01-15 Session 118 by Claude
**Status:** Game restart required, then test

---

## Session 118 Summary

### Fixes Implemented

#### 1. Tillable Validation (CRITICAL)
**Problem:** Agent tried to till/plant on farmhouse lawn - non-farmable tiles.

**Solution:** Added `/tillable-area` endpoint to SMAPI mod that checks:
- Tile has "Diggable" map property (farmland only)
- Tile is passable (not blocked)

**Files:**
- `src/smapi-mod/StardewAI.GameBridge/Models/GameState.cs` - TillableResult model
- `src/smapi-mod/StardewAI.GameBridge/HttpServer.cs` - `/tillable-area` route
- `src/smapi-mod/StardewAI.GameBridge/ModEntry.cs` - Implementation
- `src/python-agent/unified_agent.py` - `get_tillable_area()` + grid filtering

#### 2. Water Positioning Fix
**Problem:** Agent stepped toward crop one tile at a time, sometimes ending ON the crop.

**Solution:** Use `move_to` to target specific adjacent position (south preferred).

#### 3. Phantom Failure Prevention
**Problem:** VLM directed till/plant to tiles already in target state, causing phantom failures.

**Solution:** Added pre-checks to block:
- `till_soil` if target already tilled
- `plant_seed` if target already has crop

#### 4. Cache Staleness Fix (CRITICAL)
**Problem:** SMAPI state cache updated every 250ms. Actions verified before cache refreshed → phantom failures.

**Solution:**
- Reduced `StateUpdateInterval` from 15 to 5 ticks (~80ms)
- Water verification now uses fresh `/farm` data

---

## Commits This Session

```
40fd545 Session 117+118: Add tillable validation to prevent farming on non-farmland
6244c77 Session 118: Fix water positioning to use move_to for adjacent position
67aa88c Session 118: Update handoff docs with fixes summary
88ab24e Session 118: Block redundant till/plant actions to prevent phantom failures
a8f45fa Session 118: Use fresh farm data for water verification
ae54fd7 Session 118: Reduce SMAPI state cache interval from 250ms to 80ms
```

---

## GAME RESTART REQUIRED

The SMAPI mod was updated with:
1. `/tillable-area` endpoint
2. Faster state cache (5 ticks instead of 15)

**Restart the game to load the updated mod.**

---

## Session 119 Priorities

1. **TEST:** Verify cache fix eliminates phantom failures
2. **TEST:** Run full farm chores cycle - should complete without falling to debris clearing
3. **VERIFY:** Tillable validation prevents farmhouse planting
4. **MONITOR:** Check CPU usage with faster state updates (should be fine)

---

## Quick Test Commands

```bash
# After game restart, verify new cache interval is active
# (State should feel more responsive)

# Test tillable area
curl -s "http://localhost:8790/tillable-area?centerX=60&centerY=14&radius=8" | jq '{tillable: ([.data.tiles[] | select(.canTill == true)] | length)}'

# Check farm state
curl -s http://localhost:8790/farm | jq '{crops: (.data.crops | length), unwatered: ([.data.crops[] | select(.isWatered == false)] | length)}'

# Run agent with farm chores
python src/python-agent/unified_agent.py --goal "Water and plant crops"
```

---

## Known Issues to Watch

1. **VLM directing wrong actions** - The VLM sometimes tells agent to till/plant tiles that are already done. Pre-checks now block these, but VLM should learn from BLOCKED messages.

2. **Batch vs VLM mode** - `auto_farm_chores` skill uses efficient batch operations. VLM mode is slower and more error-prone. Prefer batch mode for farming.

---

## Architecture Notes

**State Cache Flow:**
```
Game State → SMAPI Mod (cache every 5 ticks) → HTTP API → Python Agent
```

**Verification Flow:**
```
Action → Wait 80ms → Query /farm (fresh) → Compare with before snapshot
```

**Tillable Check Flow:**
```
Grid start position → /tillable-area query → Filter non-tillable → Process remaining
```

---

-- Claude
