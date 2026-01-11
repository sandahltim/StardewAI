# Session 57: TaskExecutor Debugging

**Last Updated:** 2026-01-11 Session 56 by Claude
**Status:** Daily planner fixed, TaskExecutor not activating - needs debugging

---

## Session 56 Accomplishments

### Bug Fixes

1. **Buy seeds skills fixed** - Replaced template `{quantity}` with hardcoded defaults:
   - `buy_parsnip_seeds`: 5 seeds (100g)
   - `buy_cauliflower_seeds`: 1 seed (80g)
   - `buy_potato_seeds`: 2 seeds (100g)

2. **Daily planner SMAPI state path fixed** - Same bug as TargetGenerator in Session 55:
   - Was looking at `state.location.crops`
   - Fixed to look at `state.data.location.crops`
   - Now correctly detects unwatered crops and generates "Water N crops" task

### Remaining Issue: TaskExecutor Not Activating

**Symptom:** Daily planner correctly generates "Water 12 crops" task (priority 1), but TaskExecutor never starts. VLM continues to drive actions directly.

**Debug logging added** in `_try_start_daily_task()`:
- Function entry
- Executor/planner availability
- Farm location check
- Task iteration and keyword matching
- set_task() calls

**Expected logs that SHOULD appear:**
```
🎯 _try_start_daily_task called
🎯 _try_start_daily_task: checking N tasks on Farm
🎯 Checking task: 'Water 12 crops' status=pending
🎯 Matched keyword 'water' → water_crops
🎯 Calling set_task(water_crops) with 12 crops in state
🎯 Started task: water_crops (12 targets)
```

**Actual logs:** None of the above appear - suggesting `_try_start_daily_task()` is never reached or returning early.

---

## Session 57 Priority 1: Debug TaskExecutor Activation

### Hypothesis 1: tick() flow never reaches TaskExecutor check

The tick flow is:
1. Line 4060-4064: Check TaskExecutor, try to start task
2. Line 4066+: If executor active, get next action
3. Line 4107+: VLM thinking

Test: Add logging BEFORE line 4060 to confirm tick reaches that point.

### Hypothesis 2: daily_planner.tasks is empty in tick()

The daily planner might be a different instance or the tasks might not be persisted.

Test: Add `logging.info(f"Planner tasks: {len(self.daily_planner.tasks)}")` before the check.

### Hypothesis 3: task_executor is None

The TaskExecutor might fail to initialize.

Test: Check logs for `🎯 Task Executor initialized` at startup.

### Quick Debug Commands

```bash
cd /home/tim/StardewAI && source venv/bin/activate

# Clear state and run with verbose logging
rm -f logs/daily_planner_state.json
python src/python-agent/unified_agent.py --ui --goal "Water crops" 2>&1 | grep -E "(Task Executor|_try_start|Started task|daily_planner)"
```

---

## Session 57 Priority 2: Fix Once Debugged

Once we find why TaskExecutor isn't starting, the fix should enable:

1. **Deterministic execution** - Row-by-row watering instead of VLM-driven chaos
2. **Event-driven commentary** - VLM triggers on milestones, not every tick
3. **Task completion tracking** - Daily planner marks tasks complete

---

## Architecture Reference

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY PLANNER ✅ FIXED                   │
│  Correctly generates "Water N crops" with SMAPI state       │
└─────────────────────────┬───────────────────────────────────┘
                          │ ❓ ISSUE: Not reaching TaskExecutor
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              TASK EXECUTOR (needs debugging)                │
│  _try_start_daily_task() not being called?                 │
│  Or set_task() returning False?                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR (working)                       │
│  water_crop → [select_slot, face, use_tool]                │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Modified (Session 56)

| File | Change |
|------|--------|
| `skills/definitions/farming.yaml` | Fixed buy seeds - hardcoded quantities |
| `memory/daily_planner.py` | Fixed SMAPI state paths (data.location.crops) |
| `unified_agent.py` | Added debug logging in _try_start_daily_task() |

---

## Commits This Session

```
12c4e06 Fix buy seeds skills - replace template {quantity} with hardcoded defaults
593e5b7 Fix daily_planner SMAPI state path - crops not detected
1ecccdf Add debug logging to _try_start_daily_task for TaskExecutor investigation
```

---

## Quick Reference

```bash
# Activate environment
cd /home/tim/StardewAI && source venv/bin/activate

# Start services
python src/ui/app.py &
./scripts/start-llama-server.sh &

# Test daily planner directly
PYTHONPATH=src/python-agent python -c "
import sys
sys.path.insert(0, 'src/python-agent')
from memory.daily_planner import get_daily_planner
import requests
state = requests.get('http://localhost:8790/state').json()
planner = get_daily_planner()
plan = planner.start_new_day(state['data']['time']['day'], state['data']['time']['season'], state)
print(f'Plan: {plan}')
print(f'Tasks: {[(t.description, t.status) for t in planner.tasks]}')
"

# Run agent
python src/python-agent/unified_agent.py --ui --goal "Water all crops"
```

---

*Session 56: Daily planner fixed. TaskExecutor activation still needs debugging. Debug logs added for next session.*

*— Claude (PM), Session 56*
