# Session 62: Fix Prereq Task Removal Loop

**Last Updated:** 2026-01-11 Session 61 by Claude
**Status:** XOR mode working! VLM commentary-only. Refill skill works but prereq tasks loop.

---

## Session 61 Summary

### What's Fixed ✅

1. **XOR Mode Implemented** - VLM brain vs TaskExecutor hands separation
   - When TaskExecutor active → VLM observes only, no actions
   - VLM actions completely ignored in commentary mode
   - VLM can say "PAUSE" to interrupt if problem detected

2. **Dynamic Water Location** - Fixed hardcoded (58,16) pond coordinates
   - Now uses `nearestWater` from SMAPI surroundings data
   - Falls back to (72,31) if not available

3. **Navigate → Refill Flow Working**
   - Player navigates to water at (72,31) ✓
   - Refill skill executes ✓
   - Water level: 0 → 32/40 ✓

### What's Still Broken 🔴

1. **Prereq Task Removal Loop**
   - Refill task completes but immediately restarts
   - Task not being removed from `resolved_queue`
   - Possible cause: task ID mismatch or multiple prereqs with same ID

---

## Architecture After Session 61

```
VLM (Brain) ──────────────────────────────────────────────┐
│ Decides tasks │ Observes during execution │ Can PAUSE   │
└─────────────────────────┬───────────────────────────────┘
                          │ "Do this task"
                          ▼
TaskExecutor (Hands) ─────────────────────────────────────┐
│ Owns action queue │ Executes deterministically          │
│ VLM runs in commentary-only mode during execution       │
└─────────────────────────────────────────────────────────┘
```

When TaskExecutor active:
- VLM prompt includes: "YOU ARE IN OBSERVER MODE"
- VLM actions ignored at line 4515-4525
- Only executor action queued
- VLM can say "PAUSE" to take control back

---

## Files Modified (Session 61)

| File | Line(s) | Change |
|------|---------|--------|
| `unified_agent.py` | 2010 | Add `_task_executor_commentary_only` flag |
| `unified_agent.py` | 2217 | Set commentary flag when storing executor action |
| `unified_agent.py` | 2951-2980 | Add observer mode context to VLM prompt |
| `unified_agent.py` | 4249 | Clear flag when no executor action |
| `unified_agent.py` | 4501-4538 | Handle commentary-only mode, skip VLM actions |
| `planning/prereq_resolver.py` | 115-146 | Accept surroundings, extract water location |
| `planning/prereq_resolver.py` | 254-282 | Use dynamic water coords instead of hardcoded |
| `memory/daily_planner.py` | 118, 160, 163-195 | Pass surroundings through chain |
| `unified_agent.py` | 3272-3297 | Fetch surroundings before daily planning |

---

## Session 62 Priority: Fix Task Removal

The prereq task completion loop happens because:
1. Refill task completes → `report_result(success=True)` called
2. TaskExecutor state → TASK_COMPLETE
3. Next tick: task removal code runs (line 4262-4285)
4. Task ID lookup fails OR queue already has new task started
5. Same task restarts from queue

**Debug added:** Line 4269 now logs queue contents before removal

**Investigation needed:**
1. What is the actual task ID when refill starts vs completes?
2. Is the removal finding a match?
3. Are there multiple refill prereqs in queue?

---

## Hardcoded Values Review

Found ~100 hardcoded values. Most critical:

| Location | Value | Status |
|----------|-------|--------|
| prereq_resolver.py:259 | Water (58,16) | ✅ FIXED - now dynamic |
| daily_planner.py:421 | Shipping bin (71,14) | Needs fix |
| unified_agent.py:915 | Tool slots 0-4 | Should scan inventory |
| 5 files | Crop lists | Should centralize |

---

## Test Commands

```bash
# Check state
curl -s localhost:8790/state | jq '{pos: "\(.data.player.tileX),\(.data.player.tileY)", water: .data.player.wateringCanWater}'

# Check nearest water
curl -s localhost:8790/surroundings | jq '.data.nearestWater'

# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Water all crops"
```

---

*Session 61: XOR mode working. VLM is brain, TaskExecutor is hands. Refill executes but loops. — Claude (PM)*
