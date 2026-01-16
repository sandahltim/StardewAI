# Session 124: Fix Mining Execution

**Last Updated:** 2026-01-15 Session 123 by Claude
**Status:** Mining task created but not executing - needs diagnosis

---

## Session 123 Summary

### Fixes Applied

| Fix | File | Description |
|-----|------|-------------|
| Remove clear_debris task | `daily_planner.py` | Standalone clear task had no skill_override, caused infinite VLM loop |
| Skip prereqs for batch tasks | `prereq_resolver.py` | Tasks with `skill_override` now skip prereq checking entirely |
| Add skill_override to ResolvedTask | `prereq_resolver.py` | Pass through batch mode to resolved queue |
| Check resolved task skill_override | `unified_agent.py` | Task executor checks both daily_task and resolved_task for skill_override |
| Weapon-optional mining | `unified_agent.py` | Combat is skipped if no weapon - agent flees instead |
| Debug logging | `unified_agent.py` | Added `📋 Task queue:` logging (but not appearing in output) |

### Session 123 Commits

```
5582e88 Session 123: Add debug logging for task queue diagnosis
ca6780a Session 123: Make mining combat optional when no weapon
f1abcd3 Session 123: Fix prereq resolver adding clear_debris blocking mining
ada2ef6 Session 123: Remove standalone clear_debris task blocking mining
d2d767f Session 123: Update docs with clearing fix
```

---

## Current Issue: Mining Not Executing

### Symptoms

1. Agent IS in the Mine (`Mine at tile (20, 12)`)
2. But hint says "ALL FARMING DONE! Use action 'go_to_bed'" (WRONG!)
3. Debug logging `📋 Task queue:` NOT appearing in output
4. Agent has Hoe equipped in Mine (should have Pickaxe)

### Root Cause Analysis

The `_get_done_farming_hint()` function is being called even when at the Mine, and:
1. It doesn't check current location
2. It doesn't check pending daily planner tasks
3. It defaults to "go to bed" when no farm work is found

The debug logging at line 7602 should show task queue status, but it's not appearing. This suggests:
- Either `task_executor.is_active()` is returning True (blocking the code path)
- Or the code changes weren't reloaded

### Code Flow Issue

```
tick() at line 7592:
  elif self.task_executor:
    if executor_active:
      logging.debug(...)  # DEBUG level - might not show
    elif not executor_active:
      logging.info(📋 Task queue: ...)  # Should show but doesn't
      if self._try_start_daily_task():
        ...execute batch...
```

---

## Session 124 Priorities

### 1. Diagnose Why Task Queue Logging Not Showing

```python
# Add INFO level log BEFORE the executor check to confirm code is reached
logging.info("🔍 STEP 2b: Checking task executor...")
```

Or check if task_executor.is_active() is returning True unexpectedly.

### 2. Fix Hint Context Awareness

`_get_done_farming_hint()` should:
- Return early if not on Farm
- Check for pending mining/other tasks before suggesting bed
- Suggest appropriate actions based on location

```python
def _get_done_farming_hint(self, state: dict, surroundings: dict) -> str:
    location = state.get("location", {}).get("name", "") if state else ""

    # Not on Farm - don't give farming hints
    if location != "Farm":
        if "Mine" in location:
            return ">>> ⛏️ IN MINES! Break rocks to find ladder. <<<"
        return ""  # No hint for other locations

    # Check pending daily tasks before suggesting bed
    if self.daily_planner:
        pending = [t for t in self.daily_planner.tasks if t.status == "pending"]
        mining_task = next((t for t in pending if t.category == "mining"), None)
        if mining_task:
            return ">>> ⛏️ GO MINING! Use warp_to_mine skill <<<"

    # ... rest of existing logic
```

### 3. Verify Batch Mining Triggers

Once task queue is being processed, verify:
- Mining task has `skill_override="auto_mine"`
- `_try_start_daily_task()` detects and sets `_pending_batch`
- `execute_skill("auto_mine", {})` is called
- `_batch_mine_session()` runs

---

## Quick Reference

### Test Command
```bash
python src/python-agent/unified_agent.py --goal "Do farm chores and go mining"
```

### Expected Log Sequence
```
📋 Task queue: X resolved, Y pending tasks
📋 Pending: mining_N_1 (mining) skill_override=auto_mine
🔍 Task check: id=mining_N_1, skill_override=auto_mine
🚀 BATCH MODE: Task mining_N_1 uses skill_override=auto_mine
🚀 Executing batch: auto_mine
⛏️ BATCH MINING - Target: 5 floors
```

### Key Files

| File | What to Check |
|------|---------------|
| `unified_agent.py:7592` | Task executor check and queue logging |
| `unified_agent.py:1758` | `_get_done_farming_hint()` - needs location awareness |
| `unified_agent.py:5777` | `_try_start_daily_task()` - batch detection |
| `unified_agent.py:4315` | `_batch_mine_session()` - actual mining logic |

---

## Architecture Note

The agent has two parallel systems that need coordination:

1. **Vision/Hint System** - Provides context hints to VLM (`_get_done_farming_hint`)
2. **Task Executor System** - Runs daily planner tasks (`_try_start_daily_task`)

Currently these are not coordinated:
- Hint system doesn't know about pending tasks
- Task executor doesn't override hints
- VLM follows hints instead of waiting for task executor

**Solution**: Either:
- A) Make hints aware of pending tasks
- B) Make task executor suppress hints when batch is running
- C) Both

---

-- Claude (Session 123)
