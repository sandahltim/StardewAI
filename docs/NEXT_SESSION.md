# Session 50: Shipping Override Needs Strengthening

**Last Updated:** 2026-01-10 Session 49 by Claude
**Status:** Shipping hints and override added, VLM still ignores them

---

## Session 49 Summary

### What Was Completed

1. **Fixed NOT FARMABLE Hint Logic** ✅
   - Line 1160-1162: Now calls `_get_done_farming_hint()` instead of static message
   - This ensures shipping hint appears when on non-farmable ground with sellables

2. **Added Priority Shipping Action** ✅
   - Lines 1297-1327: New `priority_action` variable added to nav header
   - Shows `⭐ PRIORITY ACTION: SHIP X CROPS! Move Y north, Z east...`
   - Appears above tile-specific hints

3. **Added Shipping Action Override** ✅
   - Lines 2740-2808: New `_fix_priority_shipping()` method
   - Added to override chain at line 3963
   - Override logic:
     - If in FarmHouse with sellables → warp to Farm
     - If adjacent to bin → face + ship_item
     - If doing till/clear → override to move toward bin

4. **Fixed Bugs** ✅
   - `logger.debug` → `logging.debug` (lines 2912, 2915)
   - `shipping_bin` None handling with `or {}` (lines 1307, 1402, 2776)

### What's NOT Working

**VLM Ignores Shipping Hints**
- The hints are showing clearly:
  ```
  ⭐ PRIORITY ACTION: SHIP 15 CROPS! Move 1 north, 3 east to bin, then ship_item
  >>> 📦 SHIP 15 CROPS! Move 1 NORTH and 3 EAST to shipping bin, then ship_item <<<
  ```
- But VLM says: "There are no visible tilled plots... I need to find farmable ground"
- VLM outputs `move right` instead of following directions

**Override Not Catching All Cases**
- Override only triggers for `till_soil`, `clear_*`, `use_tool`
- VLM is outputting `move` which isn't blocked
- Need to expand override or change VLM prompt

---

## Code Changes This Session

| Commit | Files | Description |
|--------|-------|-------------|
| (unstaged) | unified_agent.py | Priority action, shipping override, bug fixes |

### Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| Priority action in nav | unified_agent.py | 1297-1327 |
| `_fix_priority_shipping()` | unified_agent.py | 2740-2808 |
| Override chain | unified_agent.py | 3960-3965 |
| Fixed NOT FARMABLE branch | unified_agent.py | 1160-1162 |

---

## Game State (End of Session 49)

| Item | Value |
|------|-------|
| Day | 14 |
| Location | Farm |
| Position | Near shipping bin (68, 15) |
| Inventory | 15 Parsnips (slots 5, 10) |
| Agent | Running but not shipping |

---

## Next Session Priorities

### Priority 1: Force VLM to Follow Shipping Directions

Options:
1. **Expand override**: Catch ALL actions when sellables exist, not just till/clear
2. **Stronger prompt**: Add "MUST FOLLOW ⭐ PRIORITY ACTION" in system prompt
3. **Direct action injection**: Bypass VLM entirely when adjacent to bin

### Priority 2: Test Complete Shipping Flow

Once agent reaches bin:
1. Verify `ship_item` action works
2. Confirm inventory is cleared
3. Check gold increases

### Priority 3: Multi-Day Test

After shipping works:
1. Day 14-15+ autonomous run
2. Monitor for regressions
3. Test harvest → ship → clear flow

---

## Design Philosophy

**VLM = Planner/Brain, Code = Executor**

The VLM provides high-level decisions. The code handles execution through:
- **Action overrides**: Catch and fix VLM mistakes
- **Skills**: Multi-step action sequences
- **Hint system**: Guide VLM to correct actions
- **Daily planner**: Task prioritization

**Current Problem**: VLM ignores hints even when shown prominently. Need stronger override or prompt modification.

---

## Quick Reference

```bash
# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Ship parsnips"

# Check game state
curl -s localhost:8790/state | jq '{day: .data.time.day, hour: .data.time.hour}'

# Check inventory
curl -s localhost:8790/state | jq '[.data.inventory[] | select(.name == "Parsnip")]'

# Watch agent log
tail -f /tmp/agent.log | grep -E "OVERRIDE|SHIP|📦|⭐"
```

---

## Files Modified (Unstaged)

```
M src/python-agent/unified_agent.py  # Priority action, shipping override
M docs/NEXT_SESSION.md               # This file
```

---

*Session 49: Shipping hints working but VLM ignores them. Override added but needs strengthening.*

*— Claude (PM), Session 49*
