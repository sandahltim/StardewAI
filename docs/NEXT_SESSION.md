# Session 107+: Complete Farming → Mining

**Last Updated:** 2026-01-14 Session 113 by Claude
**Goal:** Finish ALL farming basics so we can move to mining and the cool shit

---

## Session 113 Accomplishments

### Critical Fix: Batch Chores Using Wrong Crop Data

**Problem:** Batch said "nothing to do (farm is tidy)" but VLM saw unwatered crops!

**Root Cause:**
- `location.get("crops", [])` only returns crops within **15 tiles** of player
- When player warps to farm spawn point, actual crops may be 50+ tiles away
- Result: Empty crop list → "nothing to do"

**Solution:** Use `get_farm()` which returns **ALL crops** on farm regardless of distance.

| Function | Before | After |
|----------|--------|-------|
| `_batch_farm_chores()` | `location.get("crops", [])` | `get_farm().get("crops", [])` |
| `_batch_water_remaining()` | `location.get("crops", [])` | `get_farm().get("crops", [])` |

### New Log Output
```
🏠 Farm has 15 total crops        # NEW - confirms crop detection
💧 Phase 1: Watering 3 crops      # Actually finds unwatered crops
```

---

## Session 114 Priorities

### 1. REBUILD SMAPI MOD (Required!)
```bash
cd /home/tim/StardewAI/src/smapi-mod/StardewAI.GameBridge && dotnet build
```
`GrassPositions` field from Session 112 still needs rebuild.

### 2. Test Batch Chores End-to-End
```bash
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Farm the crops"
```

**Watch for:**
```
🚀 BATCH MODE: Task farm_chores_X uses skill_override=auto_farm_chores
🏠 Farm has N total crops        # Should show actual crop count
💧 Phase 1: Watering X crops     # Should water all unwatered
🔨 Phase 3: Till & Plant Y tiles # Should till and plant
🏠 BATCH CHORES COMPLETE: harvested=0, watered=3, tilled=10, planted=10
```

### 3. If Batch Works → Mining
- Test `go_to_mines` skill
- Test `enter_mine_level_1`
- Test combat with `swing_weapon`

---

## Known Issues

### Inventory Full
Screenshot showed "Inventory Full" message. May need inventory management before planting.

### VLM Fallback
When batch returns 0 actions, VLM takes over with scattered operations. Batch should now work properly.

---

## Session 112 Summary (Previous)

**Fixed:** Proximity-based grid search (15 tiles), combined till+plant+water, grass clearing

**Issues Found:** Batch said "nothing to do" when crops existed far from player

---

## Session 113 Summary

**Fix 1:** Batch chores now use `get_farm()` for full crop visibility instead of distance-limited `location.crops`

**Fix 2:** Batch till+plant timing was too fast (0.05s) - tool animations need ~0.4s. Added explicit `direction` param to all `use_tool` calls.

**Key Issues Found:**
- `get_state().location.crops` → 15 tile radius only (use `get_farm()` instead)
- `use_tool` calls need explicit `direction` param, not relying on prior `face` action
- Tool animations need 0.3-0.4s to complete, not 0.05s

**Handoff:** Batch till+plant should now actually till before planting — Claude

---

## Quick Start Commands

```bash
# Activate environment
cd /home/tim/StardewAI
source venv/bin/activate

# IMPORTANT: Rebuild SMAPI mod first!
cd src/smapi-mod/StardewAI.GameBridge && dotnet build && cd ../../..

# Run agent
python src/python-agent/unified_agent.py --goal "Farm the crops"

# Check batch logs
tail -f logs/agent.log | grep -E "BATCH|Farm has|Phase|COMPLETE"
```
