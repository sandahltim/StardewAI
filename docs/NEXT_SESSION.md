# Session 78: Fix Harvest Detection + Bedtime Bugs

**Last Updated:** 2026-01-12 Session 77 by Claude
**Status:** Multi-day cycle working. Harvest detection broken.

---

## Session 77 Summary

### What Worked
- ✅ Elias character + david_attenborough TTS voice
- ✅ Multi-day farming cycle (Days 1-5)
- ✅ Planting 14 parsnip seeds
- ✅ Daily watering (all 14 crops watered)
- ✅ Coqui voice path fix (was falling back to Ana Florence)
- ✅ Bedtime cycle (eventually - sometimes passes out)

### What Failed
- ❌ Harvest not triggered - 12 crops ready but agent keeps clearing debris
- ❌ Hint system shows "needs watering" for harvest-ready crops
- ❌ Refill navigation - agent loops empty instead of finding water
- ❌ Bedtime override - stays out past 2 AM clearing debris

### Elias Voice Samples (Session 77)

> "I wonder if these trees remember the last time someone tried to grow parsnips here. Probably not. They're just trees. But maybe they're thinking, 'Why are you still doing this? It's just dirt and seeds.'"

> "The dirt stretches out like a blank page. So many possibilities. So many rocks. I'm not just planting seeds—I'm planting hope. Or maybe it's just habit."

> "Maybe we're all just roots in the dark, waiting for something to happen."

---

## Bugs to Fix (Priority Order)

### 1. Harvest Hint Bug (HIGH)
**File:** `unified_agent.py` ~line 1000-1200
**Problem:** Hint says "14 CROPS NEED WATERING" when 12 are `isReadyForHarvest=true`
**Cause:** Watering hint logic doesn't check harvest status first
**Fix:** Check `isReadyForHarvest` before generating watering hints

```python
# Current (broken):
if unwatered:
    hint = f">>> {len(unwatered)} CROPS NEED WATERING! ..."

# Should be:
harvestable = [c for c in crops if c.get("isReadyForHarvest")]
if harvestable:
    hint = f">>> 🌾 {len(harvestable)} READY TO HARVEST! ..."
elif unwatered:
    hint = f">>> {len(unwatered)} CROPS NEED WATERING! ..."
```

### 2. Refill Navigation Bug (MEDIUM)
**File:** `skills/definitions/farming.yaml` line 35-59
**Problem:** `refill_watering_can` executes but doesn't navigate to water first
**Cause:** Precondition `adjacent_to: water_source` not enforced, recovery skill not triggered
**Fix:** Verify precondition check in skill executor, or add explicit navigate step

### 3. Bedtime Override Bug (MEDIUM)
**File:** `unified_agent.py`
**Problem:** Agent stays clearing debris past 2 AM, passes out
**Cause:** TaskExecutor keeps running clear_debris despite late hour
**Fix:** Add hard bedtime check that interrupts any task after 11 PM

```python
# In tick loop, before TaskExecutor:
if hour >= 23 or (hour == 0 and minute > 0):
    self._execute_skill("go_to_bed", {})
    return
```

### 4. Cell Movement Centering (LOW)
**Problem:** Agent doesn't center on tile when moving
**Note:** User observed this during gameplay

---

## Current Game State

- **Day:** 5 (Spring, Year 1)
- **Crops:** 14 planted, 12 ready to harvest
- **Seeds:** 0 remaining
- **Money:** ~450g
- **Location:** Farm

---

## Quick Start

```bash
cd /home/tim/StardewAI
source venv/bin/activate

# Start servers
./scripts/start-llama-server.sh &
python src/ui/app.py &

# Run agent
python src/python-agent/unified_agent.py --ui --goal "Farm autonomously - harvest ready crops, ship them, buy more seeds"
```

---

## Code Locations for Fixes

| Bug | File | Lines |
|-----|------|-------|
| Harvest hint | unified_agent.py | 1000-1200 (hint generation) |
| Refill nav | farming.yaml + skill_executor.py | precondition check |
| Bedtime override | unified_agent.py | tick loop |
| Daily planner harvest | memory/daily_planner.py | 402-412 |

---

## Test Checklist for Session 78

- [ ] Fix harvest hint priority
- [ ] Verify agent harvests 12 ready crops
- [ ] Test ship_item skill after harvest
- [ ] Test buy_seeds flow at Pierre's
- [ ] Verify bedtime triggers before 2 AM
- [ ] Test refill_watering_can navigation

---

*Session 77: Multi-day works, harvest blocked by hint bug. — Claude (PM)*
