# Session 60: Test Full Watering Flow

**Last Updated:** 2026-01-11 Session 59 by Claude
**Status:** Navigate + refill tasks implemented, ready for live testing

---

## Session 59 Accomplishments

### 1. Navigate Task Support (NEW)

Added full support for `navigate` task type in TaskExecutor/TargetGenerator:

**Flow:**
```
PrereqResolver adds: navigate_to_water (params: {target_coords: (58,16)})
    ↓
TargetGenerator._generate_navigate_target() → [Target(58, 16)]
    ↓
TaskExecutor moves to target
    ↓
At destination (distance=0): task auto-completes (no skill needed)
```

### 2. Refill Task Support (NEW)

Added `refill_watering_can` task type with proper skill execution:

**Flow:**
```
PrereqResolver adds: refill_watering_can (params: {target_direction: "south"})
    ↓
TargetGenerator._generate_refill_target() → [Target(current_pos, metadata={direction})]
    ↓
TaskExecutor at target: executes refill_watering_can skill with correct direction
```

### 3. Task Params Threading

Connected params from PrereqResolver through the entire execution chain:

```
_try_start_daily_task()
    → extracts resolved_task.params
    → passes to set_task(task_params=...)
        → passes to generate(task_params=...)
            → _generate_navigate_target uses target_coords
            → _generate_refill_target uses target_direction
```

### 4. No-Skill Task Handling

TaskExecutor now handles tasks that don't require skill execution:

- For `navigate` (skill=None): Auto-completes when player reaches destination
- Updates `current_index`, `progress.completed_targets`, and `state`
- Queues `TASK_COMPLETE` event for commentary

---

## Bugs Found in Testing

### 1. Can't See Crops From FarmHouse (CRITICAL)

**Problem:** DailyPlanner runs at 6AM when Rusty is in FarmHouse. SMAPI only returns crops for current location → Farm crops = 0 during planning.

**Evidence:**
```
Location: FarmHouse, crops: 0  ← planning happens here
...warp to Farm...
Location: Farm, crops: 15     ← crops exist but too late
```

**Solutions:**
- A) SMAPI endpoint for global farm state (all locations)
- B) Memory: Store yesterday's farm state for planning
- C) Warp to Farm first, plan, then proceed

### 2. Need Bedtime Notes

Rusty should document at end of day:
- What crops he has planted (type, count, days to harvest)
- What he harvested today
- What he shipped
- What's in inventory
- Money earned/spent

This enables smarter morning planning.

---

## Session 60 Priorities

### 1. Fix Crop Visibility for Planning

```bash
cd /home/tim/StardewAI && source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water all crops"

# Expected flow:
# 1. Morning planning: water_crops needs water → PrereqResolver adds navigate + refill
# 2. Resolved queue: [navigate_to_water, refill_watering_can, water_crops]
# 3. TaskExecutor: Move to pond (58,16)
# 4. TaskExecutor: Execute refill skill facing south
# 5. TaskExecutor: Move to crops, water row-by-row
```

### 2. Verify State Transitions

Watch logs for:
```
🎯 Starting resolved task: navigate (prereq) params={'destination': 'water', 'target_coords': (58, 16)}
🎯 Navigate complete: reached (58, 16)
✅ TaskExecutor: Navigate task COMPLETE
🎯 Starting resolved task: refill_watering_can (prereq)
...execute refill skill...
🎯 Starting resolved task: water_crops (main)
```

### 3. Edge Cases to Test

- Rusty already at water source (navigate should complete immediately)
- Watering can already full (PrereqResolver should skip prereqs)
- Multiple tasks in resolved queue (verify sequential execution)

---

## Files Modified (Session 59)

| File | Change |
|------|--------|
| `execution/target_generator.py` | Add task_params, _generate_navigate_target, _generate_refill_target |
| `execution/task_executor.py` | Add task_params, navigate/refill in TASK_TO_SKILL, no-skill completion |
| `unified_agent.py` | Extract and pass task_params from resolved queue |

---

## Architecture (Complete)

```
┌─────────────────────────────────────────────────────────────┐
│                    MORNING PLANNING                          │
│  DailyPlanner → raw tasks → PrereqResolver → resolved queue │
│  [water_crops] → [navigate, refill, water_crops]            │
└─────────────────────────┬───────────────────────────────────┘
                          │ resolved queue with params
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              TASK EXECUTOR (with task_params)                │
│  navigate: target_coords → move → auto-complete             │
│  refill: target_direction → skill execution                  │
│  water_crops: scan state → row-by-row execution             │
└─────────────────────────┬───────────────────────────────────┘
                          │ actions
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR                                  │
│  refill_watering_can → [select_slot, face, use_tool]        │
│  water_crop → [select_slot, face, use_tool]                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Commits (Session 59)

```
6b6c53c Add navigate and refill task support to TaskExecutor
```

---

## Quick Test Commands

```bash
# Test TargetGenerator navigate
cd /home/tim/StardewAI/src/python-agent
python -c "
from execution.target_generator import TargetGenerator
gen = TargetGenerator()
targets = gen.generate('navigate', {}, (10,10), task_params={'target_coords': (58,16)})
print(targets)
"

# Test full PrereqResolver + TaskExecutor flow
python -c "
from planning.prereq_resolver import get_prereq_resolver
from execution.task_executor import TaskExecutor, TaskState
from dataclasses import dataclass

@dataclass
class MockTask:
    id: str
    description: str
    estimated_time: int = 10

resolver = get_prereq_resolver()
result = resolver.resolve([MockTask('w1', 'Water crops')], {'data': {'player': {'wateringCanWater': 0}}})
for t in result.resolved_queue:
    print(f'{t.task_type}: {t.description}')
"
```

---

*Session 59: Navigate + refill task support complete. Ready for live testing.*

*— Claude (PM), Session 59*
