# Session 49: Shipping Hint Debug & Multi-Day Autonomy

**Last Updated:** 2026-01-10 Session 48 by Claude
**Status:** Shipping hint in progress, needs debugging

---

## Session 48 Summary

### What Was Completed

1. **Growing Crop Tile Hint Fix** ✅
   - Fixed bug where standing ON a growing crop showed "CLEAR DIRT - TILL!" hint
   - Now correctly shows crop status with days remaining and next action
   - File: `unified_agent.py:939-966`

2. **Multi-Day Autonomy Verified** ✅
   - Agent successfully went from Day 11 → Day 12
   - Bedtime behavior working
   - Crop was ready to harvest on Day 12

3. **Harvest Action Fixed** ✅
   - Changed `harvest_crop` skill from `interact` → `harvest` action
   - File: `skills/definitions/farming.yaml:95-97`

4. **Tilling Logic Improved** (Partial)
   - Clear dirt hint now checks for seeds before suggesting till
   - Tilled soil hint calls `_get_done_farming_hint` when no seeds
   - File: `unified_agent.py:1103-1130, 985-991`

### What Needs Investigation

**Shipping Hint Not Triggering**
- Added sellable items check in `_get_done_farming_hint` (lines 1362-1388)
- Parsnips are in inventory (slots 5, 10 - 15 total)
- The shipping hint (`📦 SHIP X CROPS!`) should appear but doesn't
- Possible issues:
  1. `state.get("inventory")` might return wrong data
  2. Function might not be called when expected
  3. Sellables list might not match item names exactly

Debug logging added at line 1367:
```python
logging.info(f"   📊 _get_done_farming_hint: inventory={len(inventory)}, sellables={len(sellables)}")
```

To investigate:
```bash
grep "📊.*_get_done" /tmp/agent.log
```

---

## Code Changes This Session

| Commit | Files | Description |
|--------|-------|-------------|
| `dd82dfb` | unified_agent.py, farming.yaml, NEXT_SESSION.md | Growing crop hint fix, harvest action fix |
| `01e5e78` | unified_agent.py | Shipping hint WIP, seed check, debug logging |

### Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| crop_here handling | unified_agent.py | 939-966 |
| Shipping hint check | unified_agent.py | 1362-1388 |
| Seed check before till | unified_agent.py | 1119-1129 |
| Tilled soil no seeds | unified_agent.py | 985-991 |
| Daily planner ship task | memory/daily_planner.py | 279-293 |

---

## Game State (End of Session 48)

| Item | Value |
|------|-------|
| Day | 12 |
| Location | Farm |
| Crops | None (harvested by Tim) |
| Inventory | Parsnips (slot 5: 1, slot 10: 14), tools, materials |
| Agent | Running, needs to ship parsnips |

---

## Next Session Priorities

### Priority 1: Debug Shipping Hint
1. Check if `_get_done_farming_hint` is being called
2. Verify inventory data is accessible via `state.get("inventory")`
3. Ensure sellables list matches actual item names

### Priority 2: Test Harvest Action
With the new `harvest` action in farming.yaml, test when next crop is ready.

### Priority 3: Multi-Day Run
Once shipping works, run Day 12 → Day 15+ with minimal intervention.

---

## Design Philosophy

**VLM = Planner/Brain, Code = Executor**

The VLM provides high-level decisions. The code handles execution through:
- **Action overrides**: Catch and fix common VLM mistakes
- **Skills**: Multi-step action sequences
- **Hint system**: Guide VLM to correct actions based on state
- **Daily planner**: Task prioritization and planning

---

## Quick Reference

```bash
# Check inventory for sellables
curl -s localhost:8790/state | jq '[.data.inventory[] | select(.name | test("Parsnip|Potato|etc"))]'

# Watch for debug output
tail -f /tmp/agent.log | grep -E "📊|SHIP|sellable"

# Check game state
curl -s localhost:8790/state | jq '{day: .data.time.day, hour: .data.time.hour}'

# Run agent
python src/python-agent/unified_agent.py --ui --goal "Ship parsnips"
```

---

## Known Issues

1. **Shipping hint not triggering** - Parsnips in inventory but hint shows "All crops watered!" instead of shipping direction
2. **VLM confusion** - Without proper hints, VLM wanders and tries to till (wastes energy)
3. **Harvest untested with new action** - Changed from `interact` to `harvest`, needs verification

---

*Session 48: Growing crop fix done, shipping hint needs debug*

*— Claude (PM), Session 48*
