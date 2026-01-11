# Session 66: Fix Seed Selection Bug

**Last Updated:** 2026-01-11 Session 65 by Claude
**Status:** Cell farming works but seeds not planted due to select_item bug.

---

## Session 65 Summary

### Bugs Fixed

| Bug | Fix Applied | Verified |
|-----|-------------|----------|
| **Re-Survey After Completion** | Guard in `_start_cell_farming()` - skip if coordinator already active | YES - only one survey |
| **Navigation Stuck** | Stuck detection after 10 ticks, skip cell | YES - cells skipped |
| **Planting Order** | Code order correct (plant before water) | YES |

### New Bug Discovered

**Bug: select_item Not Supported by ModBridge**
- **Symptom:** "Unknown action for ModBridge: select_item" in logs
- **Impact:** Seeds never get selected, planting fails silently
- **Root Cause:** `CellAction.to_dict()` returns `{"select_item": "Parsnip Seeds"}` but mod only supports `{"select_slot": N}`
- **Fix Needed:** Convert seed name to slot number before creating action

### Test Results
- **Cells Completed:** 6/15 (actions ran but planting failed)
- **Cells Skipped:** 9/15 (stuck on debris)
- **Seeds Actually Planted:** ~3 (manual VLM intervention)
- **Re-Survey Bug:** FIXED - only one survey per farming session

---

## Fixes Applied (Session 65)

### 1. Re-Survey Guard (unified_agent.py:2826-2829)
```python
# Don't restart if already actively farming cells
if self.cell_coordinator and not self.cell_coordinator.is_complete():
    logging.debug("Cell farming: Coordinator already active, skipping restart")
    return True  # Already running
```

### 2. Stuck Detection (unified_agent.py:2932-2944)
```python
# Stuck detection: if position hasn't changed since last tick, increment counter
if self._cell_nav_last_pos == player_pos:
    self._cell_nav_stuck_count += 1
    if self._cell_nav_stuck_count >= self._CELL_NAV_STUCK_THRESHOLD:
        logging.warning(f"Cell ({cell.x},{cell.y}): STUCK after {self._cell_nav_stuck_count} attempts, skipping cell")
        self.cell_coordinator.skip_cell(cell, f"Stuck at {player_pos}")
        self._cell_nav_stuck_count = 0
        self._cell_nav_last_pos = None
        return None  # Will process next cell on next tick
```

### 3. New Variables Added (unified_agent.py:2867-2869)
```python
self._cell_nav_last_pos = None  # Track position for stuck detection
self._cell_nav_stuck_count = 0  # Count consecutive stuck attempts
self._CELL_NAV_STUCK_THRESHOLD = 10  # Skip cell after this many stuck ticks
```

---

## Fix Required for Session 66

### select_item -> select_slot Conversion

**Location:** `execution/cell_coordinator.py` lines 196-205

**Current Code:**
```python
if cell.needs_plant:
    actions.append(CellAction(
        action_type="select_item",
        params={"item": cell.seed_type},
    ))
```

**Fix Options:**
1. **Simple:** Hardcode seed slot (slot 5 for Parsnip Seeds)
2. **Better:** Pass seed_slot to CellPlan from surveyor (query inventory)
3. **Best:** Add `select_item` support to ModBridge

**Recommended Fix (Option 2):**
1. In FarmSurveyor, find seed slot from inventory when creating plan
2. Add `seed_slot` field to `CellPlan` dataclass
3. Change cell coordinator to use `select_slot` with `cell.seed_slot`

### Files to Modify
- `planning/farm_surveyor.py` - Add `seed_slot` detection
- `execution/cell_coordinator.py` - Use `select_slot` instead of `select_item`

---

## Debug Commands

```bash
# Test cell farming
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "🌱|Complete|select"

# Check for select_item errors
grep "Unknown action" logs/agent.log

# Verify seed slot
curl -s localhost:8790/state | jq '.data.inventory[] | select(.name | contains("Seeds"))'
```

---

## Files Modified (Session 65)

| File | Lines | Change |
|------|-------|--------|
| `unified_agent.py` | 2826-2829 | Re-survey guard |
| `unified_agent.py` | 2867-2869 | Stuck tracking variables |
| `unified_agent.py` | 2932-2944 | Stuck detection logic |
| `unified_agent.py` | 2959-2962 | Reset stuck tracking at target |

---

## Remaining Work

1. **Fix select_item bug** - Critical, seeds not being planted
2. **Improve navigation** - 9/15 cells skipped due to debris
3. **End-to-end test** - Complete full farming cycle

---

*Session 65: Fixed re-survey and stuck detection bugs. Discovered select_item not supported by mod - seeds not actually planted. 6 cells processed but only ~3 seeds planted via VLM fallback. — Claude (PM)*
