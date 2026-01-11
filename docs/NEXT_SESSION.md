# Session 55: Task Execution Layer Testing + Morning Routine

**Last Updated:** 2026-01-11 Session 54 by Claude
**Status:** Task Execution Layer COMPLETE - Ready for testing

---

## Session 54 Accomplishments

### Task Execution Layer ✅ COMPLETE

**Problem Solved:** Rusty was chaotic ("ADHD crackhead tilling with a shotgun") - each VLM tick picked random targets instead of working systematically.

**Solution Built:**

```
Daily Planner → Task Executor → Skill Executor
                     ↓
              Target Generator (Codex)
```

### Files Created/Modified

| File | Change |
|------|--------|
| `execution/target_generator.py` | **NEW** - Codex built, generates sorted target lists |
| `execution/task_executor.py` | **NEW** - Claude built, deterministic state machine |
| `execution/__init__.py` | Updated exports |
| `unified_agent.py` | Integrated TaskExecutor into tick loop |

### Key Features

1. **Row-by-row execution** - Targets sorted by (y, x) like reading a book
2. **Hybrid VLM mode** - Commentary every 5 ticks during execution
3. **Automatic task pickup** - Reads from daily planner, auto-starts tasks
4. **Completion tracking** - Calls `daily_planner.complete_task()` when done
5. **Failure tolerance** - Skips target after 3 consecutive failures

---

## Session 55 Priority 1: TESTING

### Test Plan

```bash
# 1. Start fresh game (Day 1) or load save with crops

# 2. Start UI server
cd /home/tim/StardewAI
source venv/bin/activate
python src/ui/app.py &

# 3. Run agent with task executor
python src/python-agent/unified_agent.py --ui --goal "Farm systematically"

# 4. Watch for these log markers:
#    🎯 TaskExecutor: Started water_crops with N targets
#    🎯 TaskExecutor: water_crop → Moving east toward target
#    ✅ Task complete: water_crops (N/N targets)
#    📋 Daily planner: marked task_id complete
```

### What to Verify

| Behavior | Expected | Check |
|----------|----------|-------|
| Task auto-start | Agent picks task from daily planner | ☐ |
| Row-by-row execution | Crops watered in spatial order | ☐ |
| Skip VLM during execution | No VLM calls except every 5th tick | ☐ |
| Task completion | `complete_task()` called when done | ☐ |
| Next task pickup | After completion, picks next task | ☐ |
| Failure handling | Skips stuck targets after 3 tries | ☐ |

### Known Limitations (Expected)

1. **No wake-up trigger** - Task executor doesn't know when day starts
2. **No periodic re-plan** - Won't adjust mid-day if priorities change
3. **Daily planner tasks generic** - May not map perfectly to executor task types

---

## Session 55 Priority 2: Wake-Up Routine

If testing passes, implement morning routine:

### Wake-Up Detection

```python
# In tick loop, detect:
# - Time changed from 2am to 6am (new day)
# - Location is FarmHouse
# - Trigger: _morning_routine()
```

### Morning Routine Flow

```python
def _morning_routine(self):
    """Execute morning planning when Rusty wakes up."""
    
    # 1. Read yesterday's unfinished
    carryover = self.daily_planner.get_incomplete_tasks()
    
    # 2. Read memories
    lessons = self.lesson_memory.get_recent(limit=5)
    memories = self.rusty_memory.get_notable_events()
    
    # 3. Check game state
    state = self.controller.get_state()
    crops_to_water = len([c for c in state.crops if not c.isWatered])
    ready_to_harvest = len([c for c in state.crops if c.isReadyForHarvest])
    
    # 4. Generate today's plan (VLM reasoning)
    plan_prompt = f"""
    Yesterday's unfinished: {carryover}
    Recent lessons: {lessons}
    Today's state: {crops_to_water} crops need water, {ready_to_harvest} ready to harvest
    
    Create today's priority list.
    """
    plan = self.vlm.reason(plan_prompt)
    
    # 5. Feed to daily planner
    self.daily_planner.start_new_day(...)
```

---

## Session 55 Priority 3: Periodic Re-Planning

Add re-evaluation every 2 game hours:

```python
# Track last re-plan time
self._last_replan_hour = 6

# In tick loop
current_hour = state.time.hour
if current_hour >= self._last_replan_hour + 2:
    self._last_replan_hour = current_hour
    self._replan_priorities()
```

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────┐
│                    MORNING ROUTINE (6am)                    │
│  Read yesterday → Check state → VLM reasoning → Plan day    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    DAILY PLANNER                            │
│  Task queue with priorities (CRITICAL > HIGH > MEDIUM)      │
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │   PERIODIC RE-PLAN        │ ← Every 2 game hours
            │   (adjust priorities)     │
            └─────────────┬─────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              TASK EXECUTOR ✅ BUILT                         │
│  Picks task → generates targets → executes row-by-row      │
│  VLM commentary: every 5 ticks (hybrid mode)               │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR (existing)                      │
│  water_crop → [select_slot, face, use_tool]                │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Reference

```bash
# Activate environment
cd /home/tim/StardewAI && source venv/bin/activate

# Start UI server
python src/ui/app.py &

# Run agent
python src/python-agent/unified_agent.py --ui --goal "Farm systematically"

# Check team chat
python scripts/team_chat.py read

# Watch for task executor logs
tail -f logs/agent.log | grep -E "(TaskExecutor|🎯|✅ Task)"
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `execution/target_generator.py` | Sorted target lists (Codex) |
| `execution/task_executor.py` | Deterministic execution (Claude) |
| `unified_agent.py` | Main agent with integration |
| `memory/daily_planner.py` | Task queue and planning |

---

*Session 54: Task Execution Layer complete. Ready for testing.*

*— Claude (PM), Session 54*
