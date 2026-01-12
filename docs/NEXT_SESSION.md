# Session 67: Improve Cell Navigation

**Last Updated:** 2026-01-11 Session 66 by Claude
**Status:** Seed selection fixed. Navigation blocking most cells.

---

## Session 66 Summary

### Bug Fixed

| Bug | Fix Applied | Verified |
|-----|-------------|----------|
| **select_item not supported** | Changed to select_slot with inventory index | YES - seed slot 5 used |

### Test Results
- **Cells Completed:** 1/15 (Cell 60,27 - full cycle worked)
- **Cells Skipped:** 14/15 (stuck on debris navigation)
- **Seeds Planted:** 1 (confirmed: 15→14 in inventory)

### Code Changes (Session 66)

| File | Change |
|------|--------|
| `planning/farm_surveyor.py:56` | Added `seed_slot: int = 5` to CellPlan |
| `planning/farm_surveyor.py:354` | `create_farming_plan` accepts `seed_slot` param |
| `execution/cell_coordinator.py:197-204` | Changed `select_item` → `select_slot` |
| `unified_agent.py:2837-2864` | Find seed slot index from inventory |

---

## Problem for Session 67

### Navigation Blocked by Debris

**Symptom:** Agent tries to move to cell but gets stuck on debris in path

**Log evidence:**
```
🌱 Cell (57,27): player=(61, 24), nav_target=(57, 28)
🌱 Cell (57,27): Moving south to (57, 28)
[repeats 10 times at same position]
🌱 Cell (57,27): STUCK after 10 attempts, skipping cell
```

**Impact:** 14/15 cells skipped, only 1 seed planted

**Root Cause Options:**
1. Surveyor picks cells that are far from farmhouse door (64,15)
2. Debris blocks direct path, no pathfinding around obstacles
3. Navigation uses simple directional moves, not A* pathfinding

### Fix Options

**Option 1: Smarter Cell Selection**
- Prioritize cells closer to farmhouse door
- Check if path is clear before adding cell to plan
- Start with cells adjacent to already-clear areas

**Option 2: Clear Path First**
- Before farming a cell, clear debris along the route
- Navigate to debris → clear → continue to cell

**Option 3: Better Pathfinding**
- Use A* or BFS to find walkable path
- Navigate around obstacles instead of through them

**Recommended:** Option 1 (simplest) - pick accessible cells first

---

## Debug Commands

```bash
# Test cell farming
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "🌱|slot|Complete"

# Check cell selection
curl -s localhost:8790/farm | python -c "
import json, sys
sys.path.insert(0, 'src/python-agent')
from planning.farm_surveyor import get_farm_surveyor
data = json.load(sys.stdin)
surveyor = get_farm_surveyor()
tiles = surveyor.survey(data)
cells = surveyor.find_optimal_cells(tiles, 15)
for c in cells[:5]:
    print(f'Cell ({c.x},{c.y}) needs_clear={c.needs_clear}')
"

# Check player position
curl -s localhost:8790/state | jq '.data.player'
```

---

## Files to Investigate

- `planning/farm_surveyor.py` - `find_optimal_cells()` cell selection logic
- `unified_agent.py` - `_process_cell_farming()` navigation logic

---

## What's Working

- Seed slot detection from inventory
- select_slot action for seeds
- Full cell cycle: face → clear → till → plant → water
- Stuck detection (skip after 10 attempts)
- Re-survey guard (don't restart coordinator)

---

*Session 66: Fixed seed selection bug. 1/15 cells planted successfully. Navigation is now the bottleneck - most cells skipped due to debris blocking path. — Claude (PM)*
