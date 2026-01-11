# Session 64: Cell-by-Cell Farming Testing

**Last Updated:** 2026-01-11 Session 63 by Claude
**Status:** Cell-by-cell farming architecture implemented. Needs testing.

---

## Session 63 Summary

### New Feature: Cell-by-Cell Farming

**Problem Solved:** Agent was chaotic - clearing ALL debris, then tilling ALL tiles, then planting ALL. Inefficient movement, looks like "Grok on acid."

**Solution:** Cell-by-cell approach where each tile is fully processed before moving to next:
- Survey farm → Find contiguous patch → Process each cell (clear → till → plant → water) → Next cell

### New Files Created

| File | Purpose |
|------|---------|
| `planning/farm_surveyor.py` | Surveys farm, finds contiguous tillable patches via BFS, creates CellFarmingPlan |
| `execution/cell_coordinator.py` | Orchestrates cell-by-cell execution, generates dynamic action sequences |

### Key Components

**FarmSurveyor:**
- Uses `/farm` endpoint to get complete farm state
- BFS to find contiguous patches of tillable tiles (debris or tilled)
- Selects optimal cells within 25-tile radius of farmhouse
- Detects debris type per cell (Stone/Weeds/Twig) for correct tool selection

**CellFarmingCoordinator:**
- Takes CellFarmingPlan and yields cells one at a time
- Dynamic action sequences based on cell needs:
  - `needs_clear` → select correct tool (pickaxe/scythe/axe) + use_tool
  - `needs_till` → select hoe + use_tool
  - `needs_plant` → select seed + use_tool
  - `needs_water` → select watering can + use_tool
- Handles navigation between cells

### Integration Points

| File | Change |
|------|--------|
| `unified_agent.py:100-111` | Import FarmSurveyor, CellFarmingCoordinator |
| `unified_agent.py:2039-2045` | New attributes: cell_coordinator, _cell_farming_plan |
| `unified_agent.py:2807-2876` | `_start_cell_farming()` - surveys farm, creates plan |
| `unified_agent.py:2878-2982` | `_process_cell_farming()` - executes one tick of cell farming |
| `unified_agent.py:2984-3005` | `_finish_cell_farming()` - cleanup and task completion |
| `unified_agent.py:3007-3033` | `_remove_plant_prereqs_from_queue()` - removes clear/till prereqs |
| `unified_agent.py:3054-3078` | Modified `_try_start_daily_task()` - detects plant_seeds, starts cell farming |
| `unified_agent.py:4324-4331` | Tick loop integration - process cell farming before task_executor |

---

## What Needs Testing (Session 64)

1. **Cell Farming Activation**
   - Does it detect plant_seeds in queue and start cell farming?
   - Are prereqs (clear_debris, till_soil) properly removed from queue?

2. **Survey Accuracy**
   - Are cells selected near farmhouse (not edge of map)?
   - Are debris types correctly detected (Stone → pickaxe, Weeds → scythe)?

3. **Cell Execution**
   - Does navigation work to reach each cell?
   - Do dynamic actions execute in correct order (face → clear → till → plant → water)?
   - Is cell marked complete after all actions?

4. **End-to-End**
   - Full Day 1: plant_seeds triggers cell farming → all cells processed → task complete

---

## Test Commands

```bash
# Check farm state
curl -s localhost:8790/farm | jq '.data | {crops: .crops | length, objects: .objects | length}'

# Test surveyor directly
source venv/bin/activate && python -c "
from planning.farm_surveyor import get_farm_surveyor
import requests
farm_state = requests.get('http://localhost:8790/farm').json()
surveyor = get_farm_surveyor()
plan = surveyor.create_farming_plan(farm_state, seed_count=15, seed_type='Parsnip Seeds')
print(f'Plan: {len(plan.cells)} cells')
for c in plan.cells[:5]:
    print(f'  ({c.x},{c.y}): clear={c.needs_clear} debris={c.debris_type}')
"

# Run agent with plant goal
python unified_agent.py --goal "Plant parsnip seeds"

# Watch for cell farming logs:
# 🌱 Cell farming: Surveying farm for N seeds
# 🌱 Cell farming started: N cells (X need clearing, Y need tilling)
# 🌱 Cell (x,y): Starting N actions (facing direction)
# 🌱 Cell (x,y): Complete!
```

---

## Known Issues to Watch

1. **VLM server not running** - Cell farming still works (deterministic), but no commentary
2. **First cell might fail** - If navigation doesn't reach adjacent tile exactly
3. **Tool selection** - verify Copper Stone, Geode Stone map to pickaxe

---

## Files Modified (Session 63)

| File | Lines | Change |
|------|-------|--------|
| `planning/farm_surveyor.py` | NEW | FarmSurveyor class (~300 lines) |
| `execution/cell_coordinator.py` | NEW | CellFarmingCoordinator class (~200 lines) |
| `unified_agent.py` | 100-111 | Imports for cell farming |
| `unified_agent.py` | 2039-2045 | cell_coordinator attributes |
| `unified_agent.py` | 2807-3033 | Cell farming methods |
| `unified_agent.py` | 3054-3078 | _try_start_daily_task cell farming check |
| `unified_agent.py` | 4324-4331 | Tick loop cell farming integration |

---

## Architecture (Post Session 63)

```
                          ┌─────────────────────────────────────┐
                          │         DailyPlanner                │
                          │   plant_seeds detected in queue     │
                          └─────────────────┬───────────────────┘
                                            │
                          ┌─────────────────▼───────────────────┐
                          │         FarmSurveyor                │
                          │   GET /farm → BFS patches → plan    │
                          └─────────────────┬───────────────────┘
                                            │
                          ┌─────────────────▼───────────────────┐
                          │    CellFarmingCoordinator           │
                          │   For each cell:                    │
                          │     1. Navigate to adjacent tile    │
                          │     2. face → clear → till → plant  │
                          │     3. Mark complete, next cell     │
                          └─────────────────┬───────────────────┘
                                            │
                          ┌─────────────────▼───────────────────┐
                          │      SMAPI GameBridge               │
                          │   Execute actions one by one        │
                          └─────────────────────────────────────┘
```

---

*Session 63: Implemented cell-by-cell farming architecture. Ready for testing. — Claude (PM)*
