# Session 73: TTS Overlapping Fix + Agent Autonomy

**Last Updated:** 2026-01-11 Session 72 by Claude
**Status:** TaskExecutor stuck bug fixed. TTS overlapping still needs work.

---

## Session 72 Summary

### Completed This Session

| Feature | Status | Notes |
|---------|--------|-------|
| **TaskExecutor Stuck Bug** | ✅ Fixed | VLM fallback when no executor action |
| **Settings Cache Optimization** | ✅ Fixed | Only push to worker when refreshed |

### Bugs Found / Partially Fixed

| Bug | Severity | Notes |
|-----|----------|-------|
| **TTS Overlapping** | MEDIUM | Attempted fix broke TTS, rolled back |
| **UI Pulsing** | LOW | Voice/volume settings resetting in UI |
| **Navigation Twig Bug** | LOW | Blocker coords show (0,0) incorrectly |

### Code Changes (Session 72)

| File | Change |
|------|--------|
| `unified_agent.py:5103-5120` | VLM fallback when commentary-only but no executor action |
| `unified_agent.py:1952` | Added `_commentary_settings_applied` flag |
| `unified_agent.py:4003-4020` | Only apply settings to worker when refreshed |

---

## Session 72 Test Results

- **Agent autonomy**: Ran without `--goal`, generated own daily plan
- **Cell farming**: Working, cleared debris and navigated
- **TaskExecutor stuck bug**: FIXED - VLM fallback prevents freezing
- **TTS**: Working but still overlaps (rolled back fix attempt)

---

## Priority for Session 73

### 1. TTS Overlapping Fix - MEDIUM

**Problem:** When new TTS starts, previous audio should stop. Current Popen calls don't track/kill previous process.

**Location:** `src/python-agent/commentary/tts.py:PiperTTS.speak()`

**Attempted Fix (rolled back):**
- Added `_current_process` tracking
- Kill previous process before starting new
- Issue: Broke TTS entirely (unclear why)

**Investigation Needed:**
- Test the fix in isolation vs in full agent context
- Check if process tracking works with shell=True Popen
- Consider using process groups for reliable kill

### 2. UI Pulsing / Settings Reset - LOW

**Problem:** Voice and volume controls in UI keep resetting/pulsing.

**Hypothesis:** Too many commentary updates pushing to UI.

**Partial Fix Applied:**
- `_commentary_settings_applied` flag prevents repeated `set_settings()` calls
- Settings only fetched every 30s (cached)

### 3. Agent Autonomy - MEDIUM

**Current:** Agent can run without `--goal` (uses "General assistance")
**Desired:** Agent should look at farm state and plan its own day intelligently

---

## Debug Commands

```bash
# Test TTS in isolation
cd /home/tim/StardewAI/src/python-agent
python3 -c "
from commentary.tts import PiperTTS
tts = PiperTTS(voice='TARS')
print('Available:', tts.available)
result = tts.speak('Testing one two three')
print('Result:', result)
"

# Run agent without goal
python src/python-agent/unified_agent.py --ui

# Check TTS calls in log
grep "🔊 TTS" /tmp/agent_test.log | tail -10
```

---

## What's Working

- TTS commentary (no overlapping fix, but functional)
- Cell farming with obstacle clearing
- TaskExecutor with VLM fallback
- Commentary settings caching (30s TTL)
- Agent running without explicit goal

---

## TTS Architecture

```
Agent Loop → _send_commentary() → CommentaryWorker.push()
                                        ↓
                                  Worker Thread → PiperTTS.speak()
                                        ↓
                                  subprocess.Popen(piper | aplay)
```

**The Fix Needed:**
Track Popen process, kill before starting new. But shell=True Popen with pipes complicates this.

---

*Session 72: Fixed TaskExecutor stuck bug. TTS overlapping fix attempted but rolled back. — Claude (PM)*
