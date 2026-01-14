# Session 101: Multi-Day Run + Phantom Failures

**Last Updated:** 2026-01-13 Session 100 by Claude
**Status:** Agent farming with TTS, commentary throttled, varied openings

---

## Session 100 Summary

### Fix 1: Missing Skill Parameters

**Problem:** VLM calling `till_soil: {}` without `target_direction` → stuck in loop.

**Fix:** 
- Config example updated with `target_direction`
- Skill context shows `(target_direction: north/south/east/west)` for directional skills

### Fix 2: TTS Falling Behind

**Problem:** TTS takes ~40s per monologue, but commentary pushed every ~6s → queue backing up.

**Fix:** 
- `_min_commentary_interval = 45.0` seconds between TTS pushes
- `_vlm_commentary_interval = 5` ticks (was 2)

### Fix 3: Repetitive "Ah, the..." Openings

**Problem:** Every monologue started with "Ah, the farm..." - annoying.

**Fix:** Added BANNED instruction in prompts:
- `config/settings.yaml`: "BANNED: Starting with 'Ah'"
- `elias_character.py`: "BANNED OPENING: 'Ah' - this is FORBIDDEN"

### Files Modified Session 100

| File | Change |
|------|--------|
| `config/settings.yaml:411` | Added `target_direction` to action examples |
| `config/settings.yaml:182,408` | BANNED "Ah" in inner_monologue instructions |
| `unified_agent.py:2031-2034` | Added `_last_commentary_push_time`, `_min_commentary_interval` |
| `unified_agent.py:2124` | VLM interval 2 → 5 ticks |
| `unified_agent.py:2496-2503` | Skill context shows required params |
| `unified_agent.py:4393-4397` | Rate limit check before TTS push |
| `elias_character.py:87` | BANNED "Ah" opening |

---

---

## Session 99 Summary

### Major Fix: Commentary Queue Flood

**Problem:** `_send_commentary` called after every action (~0.3s), but `last_mood` only updates when VLM runs (~6-10s). This flooded the queue with 20-30 identical events per VLM tick, causing:
- TTS to speak stale/old content
- Queue filled before new monologues arrived
- New events dropped when queue full

**Fix:** Added `_last_pushed_monologue` tracking (unified_agent.py:4374-4405)

| Metric | Before | After |
|--------|--------|-------|
| Events per VLM tick | 20-30 (duplicates) | 1 (unique only) |
| Queue fill rate | ~15 seconds | Never fills |
| TTS content freshness | Stale (minutes old) | Current |

### TTS Performance: CPU → GPU

**Change:** Moved Coqui XTTS from CPU to 4070 GPU (cuda:1)

| Metric | CPU | GPU (4070) |
|--------|-----|------------|
| Generation time | 3-5 seconds | ~0.5-1 second |
| VRAM usage | 0 | ~1-2 GB |
| Available on 4070 | N/A | ~8 GB free |

---

## Files Modified Session 99

| File | Change |
|------|--------|
| `unified_agent.py:2031` | Added `_last_pushed_monologue` tracker |
| `unified_agent.py:4374-4405` | Only push NEW monologues to queue |
| `coqui_tts.py:24-44` | TTS on GPU (cuda:1 = 4070) |
| `generator.py:56-71` | Debug logging (can remove) |
| `async_worker.py:188-198` | Debug logging (can remove) |

---

## Session 101 Priorities

### 1. Monitor Multi-Day Run
Agent should now complete full farming days autonomously.
- Watch for repetition loops
- Check TTS continues working

### 2. Fix Daily Summary JSON Crash
Agent crashes on bedtime due to tuple keys in summary dict:
```
TypeError: keys must be str, int, float, bool or None, not tuple
```
File: `unified_agent.py:4342` in `_save_daily_summary()`

### 3. Phantom Failure Investigation
Some skills report success but state doesn't change:
```
[ERROR] 💀 HARD FAIL: water_crop phantom-failed 3x consecutively
```
May need to check tile targeting or verify state change logic.

### 4. Clean Up Debug Logging (Optional)
Temporary debug logging added during Session 99:
- `generator.py` line 56: `import logging` and lines 63, 66, 70
- `async_worker.py` lines 191-198

---

## Key Architecture Notes

### TTS Flow (Session 99 Fixed)
```
VLM generates inner_monologue
  → result.mood set
  → _send_ui_status(result) → self.last_mood = result.mood
  → Actions execute
  → _send_commentary() checks if last_mood != _last_pushed_monologue
  → If NEW: push to queue (1 event per VLM tick, not 20-30)
  → Worker processes event
  → Generator checks if != _last_spoken
  → Coqui generates on GPU (~1s)
  → aplay plays audio
  → "🔊 TTS:" logged
```

### GPU Usage
```
3090 Ti: VLM (tensor-split main) - ~17GB/24GB used
4070:    VLM (tensor-split 17%) + TTS (~2GB) - ~6GB/12GB used
```

---

*Session 100: Skill params, TTS rate limit, ban "Ah" — Claude*
