# Session 69: Stats Persistence + Morning Planning

**Last Updated:** 2026-01-11 Session 68 by Claude
**Status:** Grid layout and daily summary implemented. 17 crops planted on Day 1. Ready for stats persistence fix.

---

## Session 68 Summary

### Test Results

| Feature | Status | Notes |
|---------|--------|-------|
| **Grid Layout** | ✅ Working | Cells in compact rows: `(60,19), (61,19), (62,19)...` |
| **17 Crops Planted** | ✅ Success | Day 1 complete |
| **go_to_bed Skill** | ✅ Working | Auto-warped home + slept |
| **Daily Summary Save** | ⚠️ Partial | File created but stats empty (see issue below) |

### Code Changes (Session 68)

| File | Change |
|------|--------|
| `farm_surveyor.py:257-266` | Patches sorted by min distance to farmhouse |
| `farm_surveyor.py:319-324` | Global (y,x) sort on selected cells |
| `cell_coordinator.py:83` | Added `skipped_cells` dict |
| `cell_coordinator.py:249` | Track skip reasons |
| `cell_coordinator.py:258-276` | New `get_daily_summary()` method |
| `unified_agent.py:3837-3916` | New `_save_daily_summary()` method |
| `unified_agent.py:4675-4678` | Hook: save summary before go_to_bed |

---

## Issues for Session 69

### 1. Stats Persistence (Bug Found)

**Symptom:** Daily summary shows `cells_completed: 0` even though 17 crops were planted.

**Root Cause:** When user runs separate agent instances (e.g., "Plant seeds" then later "Go to bed"), the `cell_coordinator` is None in the second instance. Stats only exist in memory during active farming.

**Fix:** Persist cell farming stats to a file as cells complete, load them in `_save_daily_summary()`.

**Implementation:**
```python
# In cell_coordinator.py - save stats after each cell
def _persist_stats(self):
    stats = {
        "cells_completed": len(self.completed_cells) - len(self.skipped_cells),
        "cells_skipped": len(self.skipped_cells),
        "skip_reasons": dict(self.skipped_cells),
    }
    with open("logs/cell_farming_stats.json", "w") as f:
        json.dump(stats, f)

# In unified_agent.py - load in _save_daily_summary()
def _load_cell_stats(self) -> Dict:
    try:
        with open("logs/cell_farming_stats.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
```

### 2. Morning Planning Integration

**Goal:** Load yesterday's summary to inform today's plan.

**Implementation:**
```python
# In daily_planner.py
def load_yesterday_summary() -> Optional[Dict]:
    try:
        with open("logs/daily_summary.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# Add to VLM context
yesterday = load_yesterday_summary()
if yesterday and yesterday.get("lessons"):
    context += f"Yesterday's lessons: {yesterday['lessons']}"
```

### 3. Re-Survey Loop Bug

**Symptom:** Agent keeps re-surveying and selecting same tree-blocked cells.

**Root Cause:** After skipping cells, coordinator completes but surveyor doesn't know those cells failed. Next survey selects them again.

**Fix Options:**
1. Persist skipped cells to file, exclude from next survey
2. Mark tiles as "blocked" in FarmSurveyor
3. Add cooldown before re-survey

---

## Debug Commands

```bash
# Check cell farming stats file
cat logs/cell_farming_stats.json | jq .

# Check daily summary
cat logs/daily_summary.json | jq .

# Test grid layout
curl -s localhost:8790/farm | python -c "
import json, sys
sys.path.insert(0, 'src/python-agent')
from planning.farm_surveyor import get_farm_surveyor
data = json.load(sys.stdin)
surveyor = get_farm_surveyor()
tiles = surveyor.survey(data)
cells = surveyor.find_optimal_cells(tiles, 15)
for i, c in enumerate(cells[:10]):
    print(f'{i+1}. ({c.x},{c.y})')
"

# Run Day 2 test
python src/python-agent/unified_agent.py --goal "Water the crops"
```

---

## What's Working

- Grid layout: patches by proximity, cells row-by-row
- Cell farming: clear → till → plant → water cycle
- Obstacle clearing: Weeds, Stone, Twig during navigation
- Fast skip: Trees, Boulders skipped after 2 ticks
- go_to_bed: auto-warp + sleep
- Daily summary file creation

---

## Codex Status

**Daily Summary UI Panel** - ✅ Complete (waiting for backend stats fix)

---

*Session 68: Grid layout working, 17 crops planted Day 1, daily summary needs stats persistence. — Claude (PM)*
