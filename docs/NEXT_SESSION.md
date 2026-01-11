# Session 61: Fix TaskExecutor + VLM Integration

**Last Updated:** 2026-01-11 Session 60 by Claude
**Status:** Multiple bugs fixed but full watering flow still broken. VLM/Executor integration needs work.

---

## Session 60 Summary

### What Works
1. **Navigate task completes correctly** - Player reaches pond (58, 16) ✓
2. **Prereq chaining** - "⚡ Chained to next prereq task immediately" ✓
3. **Queue removal** - "📋 Removed water_4_1_prereq from resolved queue" ✓
4. **/farm endpoint** - Working, shows 15 crops from FarmHouse ✓

### What's Still Broken
1. **refill_watering_can skill never executes** - water remains 0
2. **VLM/Executor conflict** - VLM still interferes with skill execution
3. **Player wanders** - After navigate completes, player moves away from pond

---

## Bugs Fixed (Session 60)

### 1. Executor Action Dropped During VLM Commentary
**Problem:** When VLM commentary triggered (every 5 ticks), TaskExecutor action was queued but VLM later **replaced entire queue** at line 4495.

**Fix:** Store executor action in `_pending_executor_action`, prepend it after VLM sets queue.

```python
# Before VLM runs (line 4209):
self._pending_executor_action = Action(...)

# After VLM sets queue (line 4497):
if self._pending_executor_action:
    self.action_queue.insert(0, self._pending_executor_action)
```

### 2. Completed Tasks Not Removed from Queue
**Problem:** After task completed, it was marked complete but stayed in `resolved_queue`, causing infinite restart loop.

**Fix:** Added removal logic at line 4233:
```python
for i, rt in enumerate(resolved_queue):
    if rt_id == task_id:
        resolved_queue.pop(i)
        break
```

### 3. Stale Player Position
**Problem:** `last_position` was used for TaskExecutor decisions, could be stale.

**Fix:** Extract fresh position from `game_state` at lines 4160-4170 and 2803-2807.

### 4. Prereq Chain Broken by VLM
**Problem:** After navigate completed, VLM ran and moved player before refill started.

**Fix:** Added immediate chaining at line 4236:
```python
if resolved_queue and self._try_start_daily_task():
    return  # Skip VLM this tick
```

---

## Current Issue: Refill Skill Not Executing

Looking at latest test log:
```
🎯 TaskExecutor (with VLM): refill_watering_can → Executing refill_watering_can on target at (58, 15)
   [0] 🎯 refill_watering_can: {'target_direction': 'south'} (executor)
🎮 Executing: warp {'location': 'Farm'}   # ← VLM's action executed instead!
```

The executor action is now prepended (`[0] 🎯 refill_watering_can`), but something is still executing VLM's action first.

**Hypothesis:** The prepend is happening but the action_queue already had VLM actions from a previous tick, so the VLM action was at position 0 before we prepended.

**Investigation needed:**
1. Check action_queue state before prepend
2. Verify prepend happens at right time
3. Check if queue is being processed from wrong end

---

## Files Modified (Session 60)

| File | Line(s) | Change |
|------|---------|--------|
| `unified_agent.py` | 2009 | Add `_pending_executor_action` init |
| `unified_agent.py` | 2803-2807 | Fresh position from state |
| `unified_agent.py` | 2898-2902 | Fresh position (legacy) |
| `unified_agent.py` | 4160-4170 | Fresh position in tick |
| `unified_agent.py` | 4209-4215 | Store pending executor action |
| `unified_agent.py` | 4235-4238 | Immediate prereq chaining |
| `unified_agent.py` | 4496-4506 | Prepend executor action after VLM |

---

## Session 61 Priorities

### 1. Debug Refill Skill Execution
Add logging to understand why skill isn't executing:
```python
# At line 4130ish, before action execution:
logging.info(f"🔍 ACTION QUEUE: {[a.action_type for a in self.action_queue]}")
```

### 2. Consider Simpler Architecture
The VLM/Executor integration is fragile. Consider:
- **Option A:** TaskExecutor completely bypasses VLM when active
- **Option B:** VLM only provides commentary, never actions, when TaskExecutor active
- **Option C:** Separate execution modes (TaskExecutor XOR VLM, never both)

### 3. Test Refill Skill Directly
```bash
# Test refill skill works in isolation:
curl -X POST localhost:8790/action -d '{"action": "select_slot", "params": {"slot": 2}}'
curl -X POST localhost:8790/action -d '{"action": "face", "params": {"direction": "south"}}'
curl -X POST localhost:8790/action -d '{"action": "use_tool"}'
```

---

## Test Commands

```bash
# Check state
curl -s localhost:8790/state | jq '{pos: "\(.data.player.tileX),\(.data.player.tileY)", water: .data.player.wateringCanWater}'

# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Refill watering can"
```

---

## Architecture Notes

The current tick() flow:
```
1. Process action_queue (if not empty)
2. Check TaskExecutor (if active)
   - Get executor action
   - If VLM commentary needed:
     - Store action in _pending_executor_action
     - Continue to VLM
   - Else: queue action, return (skip VLM)
3. VLM thinking
4. VLM sets action_queue = filtered_actions
5. Prepend pending executor action
6. Next tick: execute from queue
```

**Problem:** Step 1 might execute VLM actions from previous tick before TaskExecutor's action gets prepended.

---

*Session 60: Fixed multiple bugs but VLM/Executor integration still broken. Need simpler architecture.*

*— Claude (PM), Session 60*
