# Session 40: Multi-Day Farming

**Last Updated:** 2026-01-10 Session 39 by Claude
**Status:** Full farming cycle verified, ready for multi-day testing

---

## Session 39 Summary

### What Was Completed

1. **Mode Refactoring** ✅
   - Renamed `coop` → `splitscreen` (Player 2 right half screen)
   - Default mode now `single` (full screen capture)
   - Updated unified_agent.py, config/settings.yaml, CLAUDE.md

2. **Full Farming Cycle Verified** ✅
   - `clear_weeds` (scythe) - working
   - `clear_stone` (pickaxe) - working
   - `clear_wood` (axe) - working
   - `till_soil` (hoe) - working
   - `plant_seed` - working
   - `water_crop` - working

3. **Rusty Memory UI Panel** ✅ (Codex)
   - Added `/api/rusty/memory` endpoint
   - UI panel shows mood, confidence bar, recent events

### Key Discovery: Goal Phrasing

**Problem:** VLM gets stuck in one phase with vague goals like "clear weeds and plant"

**Solution:** Explicit goals with phases and constraints:
```
"Find a small clear area (avoid trees). Clear weeds/stones/branches,
till the soil, plant parsnip seeds, and water them."
```

The "avoid trees" constraint is critical - Day 1 farms have many trees that take too long to chop.

---

## Session 38 Summary

1. **Rusty Memory System** ✅
   - `memory/rusty_memory.py` with episodic memory, character state, NPC relationships
   - Persists to `logs/rusty_state.json`
   - Integrated into unified_agent.py

---

## Next Session Priorities

### Priority 1: Multi-Day Cycle (Claude)

Now that single-day farming works, test multi-day:
1. Plant crops on Day 1
2. Sleep (go_to_bed skill)
3. Wake up Day 2 and water crops
4. Repeat until harvest ready (parsnips = 4 days)

**Test command:**
```bash
cd src/python-agent
source ../../venv/bin/activate
python unified_agent.py --config ../../config/settings.yaml --ui \
  --goal "Day 1: Find a clear 2x2 area, clear debris, till, plant parsnips, water. Then go to bed when tired or after 6pm."
```

### Priority 2: Bedtime Logic

Verify the time management system:
- `go_to_bed` skill exists
- Agent should sleep before 2am (passing out = bad)
- Test that agent finds bed and sleeps

### Priority 3: Watering Routine

Day 2+ goal:
```
"Water all planted crops. If watering can is empty, refill at pond."
```

---

## Completion Checklist Update

| Action | Status | Session |
|--------|--------|---------|
| clear_weeds (scythe) | ✅ Verified | 39 |
| clear_stone (pickaxe) | ✅ Verified | 39 |
| clear_wood (axe) | ✅ Verified | 39 |
| till_soil | ✅ Verified | 39 |
| plant_seed | ✅ Verified | 39 |
| water_crop | ✅ Verified | 39 |
| go_to_bed | Needs test | 40 |
| harvest | Previously verified | 25 |

---

## Code Reference

| Feature | File | Notes |
|---------|------|-------|
| Mode config | unified_agent.py:155 | `mode: str = "single"` |
| Splitscreen region | unified_agent.py:157 | `splitscreen_region` |
| Skill definitions | skills/definitions/farming.yaml | All debris/farming skills |
| Rusty Memory API | src/ui/app.py | `/api/rusty/memory` endpoint |

---

*Session 39: Full farming cycle verified. Goal phrasing is critical for VLM behavior.*

*— Claude (PM), Session 39*
