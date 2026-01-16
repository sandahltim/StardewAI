# Session 125: Debug Batch Execution

**Last Updated:** 2026-01-15 Session 124 by Claude
**Status:** Extensive diagnostics added - MUST RESTART AGENT to test

---

## CRITICAL: Agent Must Be Restarted

All code changes require restarting the agent. If you don't see these logs, the agent is running old code:

```
⏱️ TICK: queue=X, day1=Y, pending_batch=Z    ← Every tick
🔍 STEP 2b: day1_clearing=X, has_executor=Y  ← Task executor check
```

**Restart command:**
```bash
python src/python-agent/unified_agent.py --goal "Do farm chores and go mining"
```

---

## Session 124 Summary

### All Commits (8 total)

```
a24257c Session 124: Add tick-level diagnostic that MUST appear
d2d93c1 Session 124: Mining hint takes priority over debris clearing
9336b7d Session 124: Final handoff documentation
2eb7890 Session 124: Implement tactical combat system for mining
ac0d1f7 Session 124: Fix hint to not suggest bed at 9:50 AM
7540b28 Session 124: Update handoff doc with fixes and diagnostics
4e7241a Session 124: Add comprehensive task flow diagnostics
332f441 Session 124: Fix hint system for Mine location + add diagnostics
```

### What Was Fixed

| Issue | Fix | File:Line |
|-------|-----|-----------|
| No visibility into tick | Added `⏱️ TICK:` log every tick | `unified_agent.py:7534` |
| "Go to bed" in Mine | Location check at function start | `unified_agent.py:1765` |
| "Go to bed" at 9:50 AM | Time check before bed suggestion | `unified_agent.py:1865` |
| Debris blocks mining hint | Mining check moved BEFORE debris | `unified_agent.py:1865` |
| Task flow invisible | INFO-level logs at all decision points | `unified_agent.py:7880+` |
| Fixed 3 swings all monsters | Monster-type-aware swing counts | `unified_agent.py:4334` |
| No kiting | Hit-and-run for dangerous monsters | `unified_agent.py:4414` |
| Basic flee got cornered | Smart multi-direction retreat | `unified_agent.py:4458` |
| No weapon pickup | Auto-pickup from containers | `unified_agent.py:4500` |

---

## Diagnostic Logs to Look For

### 1. Tick Running (MUST appear)
```
⏱️ TICK: queue=0, day1=False, pending_batch=False
```
If missing: Agent not restarted

### 2. Task Executor Check
```
🔍 STEP 2b: day1_clearing=False, has_executor=True, has_planner=True
```
If missing: Code returning before STEP 2b (check action_queue)

### 3. Task Queue Status
```
📋 Task queue: 3 resolved, 2 pending tasks
   📋 Pending: farm_chores_5 (farming) skill_override=auto_farm_chores
```
If missing: Executor is active OR daily_planner is None

### 4. Batch Detection
```
🔍 Task check: id=farm_chores_5, skill_override=auto_farm_chores
🚀 BATCH MODE: Task farm_chores_5 uses skill_override=auto_farm_chores
🚀 Executing batch: auto_farm_chores
```
If missing: Task not in queue OR already completed

---

## Known Issue: VLM Running Instead of Batch

The agent is using VLM hints ("CLEAR DEBRIS") instead of executing batch farm chores.

### Possible Causes

1. **Farm chores task not created** - Check for:
   ```
   Farm chores: harvest X, water Y, plant Z
   ```
   at day start. If missing, no crops/seeds/money.

2. **Task already completed** - Task might be marked done before batch runs

3. **Resolved queue empty** - PrereqResolver not populating queue

4. **Day mismatch** - `_last_planned_day` doesn't match current day

### Debugging Steps for Next Session

1. Look for `⏱️ TICK:` - confirms code is current
2. Look for `🔍 STEP 2b:` - confirms reaching task executor
3. Look for `📋 Task queue:` - shows what's pending
4. Look for `🚀 BATCH MODE:` - confirms batch detected

If step 2 is reached but step 4 never happens, add more logging in `_try_start_daily_task()`.

---

## Combat System (Ready for Testing)

### Monster Knowledge
```python
MONSTER_DATA = {
    "Green Slime": {"danger": 1, "swings": 2, "kite": False},
    "Serpent": {"danger": 5, "swings": 6, "kite": True},
    # 20+ monster types
}
```

### Combat Methods
| Method | Purpose |
|--------|---------|
| `_combat_engage()` | Main dispatcher |
| `_combat_kite()` | Hit-and-run for danger >= 4 |
| `_combat_retreat()` | Smart escape when weaponless |
| `_try_pickup_weapon()` | Search containers for weapons |

---

## Hint System (Fixed)

### Priority Order (highest first)
1. In Mine? → "Break rocks to find ladder"
2. Not on Farm? → No hint (empty string)
3. Pending mining task + before 4pm? → "GO MINING!"
4. Nearby debris? → "CLEAR DEBRIS"
5. Late (6pm+) or low energy? → "go to bed"
6. Otherwise → "Explore, forage, fish"

---

## Key Files Reference

| File | Line | Purpose |
|------|------|---------|
| `unified_agent.py` | 7534 | `⏱️ TICK:` diagnostic |
| `unified_agent.py` | 7880 | `🔍 STEP 2b:` diagnostic |
| `unified_agent.py` | 6061 | `_try_start_daily_task()` |
| `unified_agent.py` | 4334 | MONSTER_DATA |
| `unified_agent.py` | 1765 | Location-aware hint |
| `unified_agent.py` | 1865 | Mining priority hint |
| `daily_planner.py` | 427 | Farm chores task creation |
| `daily_planner.py` | 587 | Mining task creation |

---

## Next Session Priority

1. **Restart agent and check logs**
2. **If `⏱️ TICK:` missing** - agent still running old code
3. **If `🔍 STEP 2b:` missing** - something returning early
4. **If `📋 Task queue:` shows 0** - daily planner issue
5. **If batch never triggers** - add logging in `_try_start_daily_task()`

The batch system exists and should work - we just need to find where the flow is broken.

---

-- Claude (Session 124)
