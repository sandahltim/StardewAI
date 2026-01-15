# Session 120: Verify Batch-Only Farming

**Last Updated:** 2026-01-15 Session 119 by Claude
**Status:** Ready to test - major simplification

---

## Session 119 Summary

### Architecture Simplification

**Cell farming DISABLED** - Batch mode is now the ONLY path for farming.

Cell farming was legacy code (Session 62+) that processed farm cells one at a time using VLM guidance. It caused:
- Phantom failures from VLM directing invalid actions
- Inefficient cell-by-cell processing
- Getting stuck at map edges

**Now:** `auto_farm_chores` batch mode handles ALL farming reliably.

### Fixes Implemented

#### 1. Pre-checks Block Invalid VLM Commands
Added pre-validation to block actions BEFORE execution:
- `plant_seed`: Block if tile not tilled OR already has crop
- `till_soil`: Block if tile not tillable (water, cliff) OR already tilled
- `clear_*`: Block if no clearable object in target direction

#### 2. Task Type Inference Expanded
Added missing task types so queue doesn't show "unknown":
- `go_mining`, `explore`, `go_fishing`, `forage`, `go_to_bed`

#### 3. Edge-Stuck Detection Improved
- Added `plant_seed`, `till_soil` to stuck-prone actions
- BLOCKED messages count toward stuck threshold
- Lower threshold (2 vs 3) when surrounded by obstacles

---

## Commits This Session

```
12e0f24 Session 119: Fix VLM phantom failures and edge-stuck detection
19c2e51 Session 119: Disable cell farming - batch mode only
```

---

## Session 120 Priorities

1. **TEST:** Run full day cycle - batch farm chores should complete cleanly
2. **VERIFY:** No cell farming triggers (look for absence of "Cell-by-cell farming" in logs)
3. **VERIFY:** Pre-checks blocking invalid VLM commands (look for "🛡️ BLOCKED:" messages)
4. **TEST:** After farming, explore/mine tasks should execute (not "unknown")

---

## Quick Test Commands

```bash
# Run agent
python src/python-agent/unified_agent.py --goal "Do farm chores and explore" 2>&1 | tee /tmp/session120_test.log

# Check for cell farming (should NOT appear)
grep -i "cell.*farm" /tmp/session120_test.log

# Check for batch mode (should appear)
grep "BATCH" /tmp/session120_test.log

# Check for pre-check blocks
grep "BLOCKED" /tmp/session120_test.log
```

---

## Architecture Notes

**Farm Chores Flow (simplified):**
```
Daily Plan → "Farm chores" task with skill_override=auto_farm_chores
          → _batch_farm_chores()
          → harvest, water, till, plant in efficient batch
          → Task complete → Next task from queue
```

**Pre-check Flow:**
```
VLM outputs action → Pre-check validates → BLOCKED if invalid → Skip action
```

---

-- Claude
