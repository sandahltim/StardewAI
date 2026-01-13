# Session 88: Fix Watering Priority & Cell Reachability

**Last Updated:** 2026-01-13 Session 87 by Claude
**Status:** Multi-day test revealed critical bugs - watering and cell reachability

---

## Session 87 Summary

### Test Results

| Metric | Result |
|--------|--------|
| Seeds planted | 13/15 (87%) |
| Day 1 crops watered | NO - saved by rain on Day 3 |
| Bedtime | Agent went to bed (worked) |
| Multi-day survival | Yes - Day 1 → Day 3 |

### Critical Bugs Found

#### BUG #1: Water Task False Completion (HIGH PRIORITY)

**Problem:** At day start, agent is in FarmHouse. Water task generates targets by pathfinding from current position (inside house) to farm cells. All paths fail → 0 targets → task auto-completes as "done".

**Evidence:**
```
12:19:40,459 [INFO] FarmSurveyor: Filtered 33 unreachable cells
12:19:40,459 [INFO] FarmSurveyor: Selected 0 reachable cells: []...
12:19:44,644 [INFO] ✅ Task completed: Water 4 crops  # FALSE! 0 watering done
```

**Impact:** Crops don't get watered. Only survived because Day 3 had rain.

**Fix Options:**
1. Don't auto-complete tasks with 0 targets (mark as "blocked" instead)
2. Run water task AFTER player exits farmhouse
3. Use farmhouse door position for pathfinding reference

---

#### BUG #2: Cell Reachability for Till/Plant (HIGH PRIORITY)

**Problem:** To till or plant a cell at (X, Y), the player must stand at (X, Y+1) and face north. But the target generator only checks if (X, Y) is reachable, not if the action position (X, Y+1) is reachable.

**Evidence:**
```
🌱 Cell (48,17): player=(48, 18), nav_target=(48, 18)
# Player at Y+1 position, but if (48, 18) was blocked, cell would fail
```

When action position is blocked (debris, tree, water), the agent:
1. Tries to reach blocked position
2. Gets stuck
3. Phantom failure accumulates
4. Eventually skips after 3+ failures

**Impact:** Many till/plant targets fail because action position isn't validated.

**Fix:** In `target_generator.py` or `farm_surveyor.py`:
- For each candidate cell (X, Y), also verify (X, Y+1) is:
  - Passable (not blocked by debris/tree/water)
  - Reachable via pathfinding

---

#### BUG #3: Till Phantom Failures (MEDIUM)

**Problem:** Till targets generated at survey time. As farming progresses, some cells get tilled by cell farming. Later, TaskExecutor tries to till already-tilled cells → phantom failure.

**Evidence:**
```
12:24:54,944 [ERROR] 💀 HARD FAIL: till_soil phantom-failed 23x consecutively
```

**Fix Options:**
1. Re-validate tile state before each till action
2. Regenerate target list periodically
3. Skip targets where tile is already tilled

---

#### BUG #4: Cell Farming Interrupted (MEDIUM)

**Problem:** Cell farming was planting seeds (13/15 done), then TaskExecutor started clear_debris with 131 targets, abandoning the remaining 2 seeds.

**Cause:** Daily planner queue had clear_debris after planting. When cell farming coordinator finished its batch, control returned to TaskExecutor which started the next queued task.

**Fix:** Either:
1. Cell farming should complete ALL seeds before returning control
2. Or, re-queue remaining seeds when cell farming is interrupted

---

### Bedtime Status

Bedtime override appears to work for single days. Agent went to bed. However, during multi-day runs with long-running tasks (like 131-target clear_debris), the bedtime check may not trigger frequently enough.

**Status:** Monitor in future sessions, not critical now.

---

## Session 88 Priority

### 1. Fix Water Task Priority (CRITICAL)

The water task MUST succeed at day start. Options:

**Option A: Exit Farmhouse First**
- Add `exit_farmhouse` prereq to water task
- Water targets generated after player is on Farm

**Option B: Don't Auto-Complete 0-Target Tasks**
- In TaskExecutor, if targets == 0, mark task as "blocked" not "complete"
- Re-try later when player position changes

**Option C: Use Farm-Side Reference for Pathfinding**
- When surveying from FarmHouse, use (64, 15) as reference (just outside door)
- Check reachability from that point, not current position

### 2. Fix Cell Reachability (HIGH)

For till/plant targets, validate BOTH:
- Target cell (X, Y) is tillable
- Action position (X, Y+1) is passable AND reachable

**Location:** `src/python-agent/farming/farm_surveyor.py` around line 354

### 3. Test Fixes

```bash
# Fresh Day 1 start
# Verify: Agent exits farmhouse THEN waters
# Verify: Till/plant targets are actually reachable
python src/python-agent/unified_agent.py --goal "Water crops and plant seeds"
```

---

## Current Game State

- **Day:** 3 (Spring, Year 1) - 6:00 AM
- **Weather:** Raining (auto-waters crops)
- **Location:** Farm
- **Crops:** 13 parsnips (all watered by rain)
- **Seeds remaining:** 2 Parsnip Seeds
- **Character:** Elias (hippie version - may revert)

---

## Files to Modify

| File | Change Needed |
|------|---------------|
| `daily_planner.py` | Water task should require player on Farm |
| `target_generator.py` | Validate action position (Y+1) reachability |
| `farm_surveyor.py` | Check action position when selecting cells |
| `task_executor.py` | Don't auto-complete 0-target tasks |

---

## Character Note

Elias character was updated to "hippie/70s burnout" style. Tim wants to test both versions. May merge or revert based on commentary quality.

---

*Session 87: Multi-day test bugs identified — Claude (PM)*
