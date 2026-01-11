# Session 65: Fix Cell Farming Bugs

**Last Updated:** 2026-01-11 Session 64 by Claude
**Status:** Cell farming activating but has multiple bugs. Ready for debugging.

---

## Session 64 Summary

### Testing Results

**What Works:**
- Surveyor correctly finds cells near farmhouse (distance 16-26, not y=0)
- Debris types correctly detected (Weeds→slot 4/scythe, Stone→slot 3/pickaxe, Twig→slot 0/axe)
- Cell farming activates when plant_seeds detected in queue
- Prereqs (clear_debris, till_soil) removed from queue when cell farming starts
- FarmHouse → Farm warp works
- Navigation to first cell works (diagonal movement)
- Cell actions execute: face → clear → till → plant → water
- Cell marked complete: "🌱 Cell (52,28): Complete!"

**Bugs Found:**

### Bug 1: Daily Plan Race Condition (FIXED)
- **Problem:** TaskExecutor ran BEFORE daily plan was created on first tick
- **Root Cause:** `_try_start_daily_task()` called before `_refresh_state_snapshot()` which creates daily plan
- **Fix Applied:** Added guard in `_try_start_daily_task()` to check if current day matches `_last_planned_day`

### Bug 2: Cell Infinite Restart (FIXED)
- **Problem:** Same cell restarted instead of completing
- **Root Cause:** When `_cell_action_index >= len(_current_cell_actions)`, the condition at line 2939 was TRUE, causing actions to regenerate
- **Fix Applied:** Separated completion check from start check - completion runs first

### Bug 3: Re-Survey After Cell Completion (NOT FIXED)
- **Problem:** After completing a cell, agent re-surveys farm and creates new plan
- **Symptom:** "🌱 Cell (52,28): Complete!" immediately followed by "🌱 Cell farming: Surveying farm for 15 seeds"
- **Root Cause:** Unknown - need to trace why `_start_cell_farming()` is called again
- **Location:** Check who calls `_start_cell_farming()` after cell coordinator already exists

### Bug 4: Navigation Stuck (NOT FIXED)
- **Problem:** Player stuck at (54,29) trying to move east to (59,29)
- **Symptom:** Infinite "Moving east to (59,29)" but position doesn't change
- **Root Cause:** Debris blocking path - simple directional move can't path around obstacles
- **Fix Needed:** Either clear blocking debris, or use smarter pathfinding

### Bug 5: Not Planting Before Watering (REPORTED)
- **User Report:** Seeds not being planted before watering
- **Expected:** select_item(seeds) → use_tool → select_slot(watering can) → use_tool
- **Need to verify:** Check actual action execution order in logs

---

## Fixes Applied (Session 64)

### 1. FarmHouse → Farm Warp (unified_agent.py:2901-2909)
```python
# Check if we need to warp to Farm first (can't farm from inside FarmHouse)
location = data.get("location", {}).get("name", "")
if location == "FarmHouse":
    logging.info("🌱 Cell farming: Player in FarmHouse → warping to Farm")
    return Action(action_type="warp", params={"location": "Farm"}, ...)
```

### 2. Daily Plan Race Guard (unified_agent.py:3064-3073)
```python
# Don't start tasks if daily plan hasn't been created yet for today
state = self.controller.get_state() ...
if current_day > 0 and current_day != self._last_planned_day:
    logging.debug("🎯 _try_start_daily_task: waiting for daily plan")
    return False
```

### 3. Cell Completion Logic (unified_agent.py:2939-2946)
```python
# Check if we just finished all actions for this cell
if self._current_cell_actions and self._cell_action_index >= len(self._current_cell_actions):
    # All actions for this cell complete
    logging.info(f"🌱 Cell ({cell.x},{cell.y}): Complete!")
    self.cell_coordinator.mark_cell_complete(cell)
    self._current_cell_actions = []
    self._cell_action_index = 0
    return None  # Will process next cell on next tick
```

---

## Debug Strategy for Session 65

### Bug 3: Re-Survey After Completion
1. Search for calls to `_start_cell_farming()`
2. Add logging before the call to see who triggers it
3. Likely in `_try_start_daily_task()` - shouldn't call if `cell_coordinator` already exists
4. Check condition: `if HAS_CELL_FARMING and not self.cell_coordinator:` - is coordinator being reset?

### Bug 4: Navigation Stuck
Options:
1. **Quick fix:** Clear debris in path during navigation (detect blocked, use tool)
2. **Better fix:** Use A* pathfinding to navigate around obstacles
3. **Simple fix:** Skip to next cell if blocked too long

### Bug 5: Planting Order
1. Run with DEBUG logging to see action sequence
2. Check `get_cell_actions()` in cell_coordinator.py returns actions in right order
3. Verify the `select_item` action is selecting the right seed

---

## Test Commands

```bash
# Quick test with debug logging
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "🌱|Complete|Cell \("

# Watch for re-survey bug
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "Surveying|Complete|Cell farming"

# Check if coordinator persists
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "cell_coordinator|_start_cell"
```

---

## Files Modified (Session 64)

| File | Lines | Change |
|------|-------|--------|
| `unified_agent.py` | 2901-2909 | FarmHouse → Farm warp in `_process_cell_farming()` |
| `unified_agent.py` | 2921 | Debug logging for navigation |
| `unified_agent.py` | 2939-2946 | Cell completion check (separated from start) |
| `unified_agent.py` | 3064-3073 | Daily plan race guard |

---

## Remaining Work

1. **Fix Bug 3 (Re-Survey)** - Most critical, causes restart loop
2. **Fix Bug 4 (Navigation)** - Causes stuck state
3. **Verify Bug 5 (Planting)** - May not be a real bug
4. **End-to-end test** - Complete 15 cells successfully

---

*Session 64: Found and fixed 2 bugs. 3 more bugs identified but not fixed. Cell farming activates correctly but has restart loop issue. — Claude (PM)*
