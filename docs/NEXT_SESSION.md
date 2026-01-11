# Session 59: Complete PrereqResolver Integration

**Last Updated:** 2026-01-11 Session 58 by Claude
**Status:** PrereqResolver working, needs TaskExecutor navigation support

---

## Session 58 Accomplishments

### 1. PrereqResolver Architecture (NEW)

Created `planning/prereq_resolver.py` - resolves prerequisites UPFRONT during morning planning instead of at runtime.

**Core Flow:**
```
Morning Planning
    ↓
DailyPlanner generates raw tasks [water_crops, harvest_crops...]
    ↓
PrereqResolver.resolve(tasks, game_state)
    - Checks resources (water level, seeds, money)
    - Inserts prereq actions where needed
    - Skips unresolvable tasks (notes for memory)
    ↓
Resolved Queue: [navigate_to_water, refill, water_crops, ...]
    ↓
TaskExecutor executes queue IN ORDER (locked, no VLM switching)
```

**Example Resolution (tested and working):**
```python
Input:  [water_crops]  (watering can = 0/40)
Output: [navigate_to_water, refill_watering_can, water_crops]
```

### 2. DailyPlanner Integration

- Added `_resolve_prerequisites()` after task generation
- New attributes: `resolved_queue`, `resolution_notes`, `skipped_tasks`
- New methods: `get_resolved_queue()`, `get_next_resolved_task()`

### 3. unified_agent.py Updates

- `_try_start_daily_task()` now uses resolved queue (not keyword matching)
- Falls back to legacy method if PrereqResolver unavailable
- Keeps runtime precondition check as safety net

### 4. Smart Selling Logic

- PrereqResolver won't sell reserved crops (bundles, gifts)
- If no money for seeds: checks sellable items first
- Unresolvable prereqs: notes in memory, skips task chain

---

## Session 59 Priorities

### 1. Add Navigation Task Support to TaskExecutor

**Problem Discovered:** TaskExecutor/TargetGenerator don't understand `navigate` task type.

```
PrereqResolver adds: navigate_to_water
TaskExecutor.set_task(navigate) → TargetGenerator returns []
→ "No targets" → task skipped without moving
```

**Fix Needed in `execution/target_generator.py`:**
```python
# In dispatch dict, add:
"navigate": self._generate_navigate_target,
"refill_watering_can": self._generate_refill_target,

# New method:
def _generate_navigate_target(self, game_state, player_pos, strategy):
    # Return single target at destination coords
    # Coords come from task params (e.g., 58,16 for farm pond)
```

### 2. Handle Single-Action Tasks

Tasks like `refill_watering_can` don't have multiple targets like `water_crops`. They're single actions at a location.

**Options:**
- A) Return single target, execute skill when adjacent
- B) Handle in TaskExecutor without TargetGenerator
- C) Execute skill directly from _try_start_daily_task for prereqs

### 3. Test Full Flow

Once navigation works:
```bash
cd /home/tim/StardewAI && source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water all crops"

# Expected flow:
# 1. PrereqResolver: [navigate_to_water, refill, water_crops]
# 2. TaskExecutor: Move to pond (58,16)
# 3. TaskExecutor: Execute refill skill
# 4. TaskExecutor: Move to crops, water row-by-row
```

---

## Architecture Update

```
┌─────────────────────────────────────────────────────────────┐
│                    MORNING PLANNING                          │
│  DailyPlanner → raw tasks → PrereqResolver → resolved queue │
└─────────────────────────┬───────────────────────────────────┘
                          │ resolved queue
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              TASK EXECUTOR (locked queue)                    │
│  - Executes tasks IN ORDER from resolved queue               │
│  - No VLM task switching mid-execution                       │
│  - Runtime obstacle clearing still active                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ actions
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR                                  │
│  navigate → [move, move, move...]                           │
│  refill   → [select_slot, face, use_tool]                   │
│  water    → [select_slot, face, use_tool]                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Modified (Session 58)

| File | Change |
|------|--------|
| `planning/prereq_resolver.py` | NEW - upfront prereq resolution |
| `planning/__init__.py` | Export PrereqResolver classes |
| `memory/daily_planner.py` | Call PrereqResolver, store resolved_queue |
| `unified_agent.py` | Use resolved queue in _try_start_daily_task |

---

## Tim's Design Decisions (Session 58)

1. **Prereqs resolved upfront, not runtime** - prevents VLM task switching
2. **2-hour re-plan cycles** - finish current task first, then re-plan
3. **New PrereqResolver module** - separate from DailyPlanner and TaskExecutor
4. **Smart selling** - don't sell crops needed for bundles/gifts
5. **Note + inform user** for unresolvable prereqs
6. **Clearing is low priority** - only for blocked movement or nothing else to do
7. **Future: Farm layout planning** - planting needs layout/seed type logic

---

## Commits (Session 58)

```
890db1a Add navigate_to_water prereq before refill_watering_can
bc21480 Add PrereqResolver for upfront task prerequisite resolution
```

---

## Quick Reference

```bash
# Test PrereqResolver
cd /home/tim/StardewAI/src/python-agent
python -c "
from planning.prereq_resolver import get_prereq_resolver
from dataclasses import dataclass

@dataclass
class MockTask:
    id: str
    description: str
    estimated_time: int = 10

resolver = get_prereq_resolver()
tasks = [MockTask('w1', 'Water 9 crops')]
result = resolver.resolve(tasks, {'data': {'player': {'wateringCanWater': 0, 'wateringCanMax': 40}}})
for t in result.resolved_queue:
    print(f'{t.task_type}: {t.description}')
"
```

---

*Session 58: PrereqResolver implemented and integrated. Needs TaskExecutor navigation support to complete the flow.*

*— Claude (PM), Session 58*
