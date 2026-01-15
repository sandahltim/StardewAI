# Session 107+: Complete Farming → Mining

**Last Updated:** 2026-01-14 Session 113 by Claude
**Goal:** Finish ALL farming basics so we can move to mining and the cool shit

---

## Session 113 Accomplishments

### Fix 1: Batch Chores Using Wrong Crop Data

**Problem:** Batch said "nothing to do (farm is tidy)" but VLM saw unwatered crops!

**Root Cause:** `location.get("crops", [])` only returns crops within 15 tiles of player.

**Solution:** Use `get_farm()` which returns ALL crops on farm regardless of distance.

### Fix 2: Batch Till+Plant Timing Too Fast

**Problem:** Actions fired at 0.05s intervals - tool animations need ~0.4s to complete.

**Solution:**
- Added explicit `direction: "north"` to all `use_tool` calls
- Increased delays: 0.4s for hoe, 0.2s for plant, 0.3s for water

### Fix 3: ResourceClumps Not Avoided

**Problem:** Batch tried to till tiles occupied by large stumps/boulders (need upgraded tools).

**Solution:** Read `resourceClumps` from farm data, block all tiles they occupy (width x height).

| Obstacle | Handling |
|----------|----------|
| Grass/weeds/stones/twigs | Clear with scythe/pickaxe/axe |
| Large stumps | Skip (need copper axe) |
| Large logs | Skip (need steel axe) |
| Boulders | Skip (need steel pickaxe) |

### New Log Output
```
🏠 Farm has 15 total crops
🌱 Avoiding 12 tiles blocked by stumps/boulders
💧 Phase 1: Watering 3 crops
🔨 Phase 3: Till & Plant 15 tiles
🌱 Progress: 5/15 tilled, 5 planted
🏠 BATCH CHORES COMPLETE: harvested=0, watered=3, tilled=15, planted=15
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

### 3. If Batch Works → Mining
- Test `go_to_mines` skill
- Test `enter_mine_level_1`
- Test combat with `swing_weapon`

---

## Commits This Session

```
08e0c39 Session 113: Skip ResourceClumps in batch till+plant
4011bea Session 113: Fix batch till+plant timing and direction params
f731648 Session 113: Fix batch chores using wrong crop data source
```

---

## Known Issues

### Inventory Full
Screenshot showed "Inventory Full" message. May need inventory management before planting.

---

## Session 113 Summary

**3 Critical Fixes:**
1. Use `get_farm().crops` instead of `location.crops` (15-tile limit)
2. Add `direction` param + proper delays (0.4s) to tool actions
3. Skip ResourceClumps (stumps/boulders) that need upgraded tools

**Handoff:** Batch till+plant should now work correctly — Claude

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
tail -f logs/agent.log | grep -E "BATCH|Farm has|Phase|Avoiding|COMPLETE"
```
