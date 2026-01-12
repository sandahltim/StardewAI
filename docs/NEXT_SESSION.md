# Session 72: Fix TaskExecutor Stuck Bug

**Last Updated:** 2026-01-11 Session 71 by Claude
**Status:** TTS/commentary blocking fixed. TaskExecutor stuck bug identified.

---

## Session 71 Summary

### Completed This Session

| Feature | Status | Notes |
|---------|--------|-------|
| **TTS Blocking Fix** | ✅ Fixed | `subprocess.Popen` instead of `run` for audio |
| **Commentary Cache** | ✅ Fixed | Settings cached 30s, not fetched every tick |
| **Warp Loop Fix** | ✅ Fixed | Was caused by blocking HTTP calls |

### Bugs Found (Not Fixed)

| Bug | Severity | Notes |
|-----|----------|-------|
| **TaskExecutor Stuck** | HIGH | When commentary-only mode + no pending action = empty queue |
| **Agent Not Autonomous** | MEDIUM | Requires explicit goals, should self-plan |

### Code Changes (Session 71)

| File | Change |
|------|--------|
| `unified_agent.py:1949-1952` | Add commentary settings cache variables |
| `unified_agent.py:3996-4017` | Use cached settings (30s TTL) instead of HTTP every tick |
| `src/ui/app.py:643-651` | Non-blocking TTS with `Popen` (cached playback) |
| `src/ui/app.py:664-669` | Non-blocking TTS with `Popen` (new audio) |

**Commit:** `ccc13fd` - Fix TTS/commentary blocking issues

---

## Session 71 Test Results

- **Cell farming**: 5/5 cells completed successfully
- **Agent reached**: Day 1 7:40 PM, 154/270 energy
- **Then stuck**: TaskExecutor commentary-only mode with empty action queue

---

## Priority for Session 72

### 1. TaskExecutor Stuck Bug - HIGH

**Location:** `unified_agent.py:5103-5113`

**Problem:** When `_task_executor_commentary_only=True` but `_pending_executor_action=None`:
```python
elif self._task_executor_commentary_only:
    if self._pending_executor_action:
        self.action_queue = [self._pending_executor_action]
    else:
        self.action_queue = []  # BUG: Empty queue = stuck!
    self._task_executor_commentary_only = False
```

VLM generates actions but they're ignored. Executor has nothing. Agent freezes.

**Fix Options:**
1. Fall back to VLM actions when executor has none
2. Clear commentary-only flag when no pending action
3. Never set commentary-only without a pending action

**Likely Root Cause:** Cell farming finishes, sets commentary-only, but executor has no next task.

### 2. Agent Autonomy

**Goal:** Agent should plan its own day without explicit `--goal` parameter.

**Current:** `--goal "Full Day 1: Plant seeds..."` required

**Should be:** Agent wakes up, looks at farm state, plans day automatically

---

## Debug Commands

```bash
# Run agent without explicit goal (test autonomy)
python src/python-agent/unified_agent.py

# Check if stuck in commentary-only mode
grep "_task_executor_commentary_only" /tmp/agent_run.log | tail -5

# Monitor action queue
grep "action_queue" /tmp/agent_run.log | tail -10
```

---

## What's Working

- TTS no longer blocks agent (async + cached settings)
- Cell farming completes successfully
- Obstacle clearing during navigation
- Stats persistence to file
- Daily summary saves

---

## Commentary System Architecture

```
Agent Loop → _send_commentary() → cached settings check (30s TTL)
                                        ↓
                              commentary_worker.push() (non-blocking)
                                        ↓
                              Worker Thread → PiperTTS.speak() (Popen)
```

Settings HTTP call: **Every 30 seconds** (not every tick)
TTS playback: **Non-blocking** (subprocess.Popen)

---

*Session 71: Fixed TTS/commentary blocking. Found TaskExecutor stuck bug. — Claude (PM)*
