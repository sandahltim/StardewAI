# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** Major SMAPI improvements, seed planting fix pending test

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B loaded |
| SMAPI mod | **UPDATED** | Port 8790, major improvements |
| UI Server | Running | Port 9001, all indicators added |
| VLM Perception | Working | Location, time, energy detection |
| Tool Awareness | Working | Uses game state, not VLM |
| **Water Detection** | **NEW** | Nearest water with direction/distance |
| **Shipping Bin** | **NEW** | Location available on Farm |
| **Crop Growth** | **FIXED** | Actual days until harvest |
| **Tillability** | **FIXED** | Porch/paths correctly blocked |
| **Seed Planting** | **NEW** | use_tool now works for seeds |
| Game Knowledge DB | Working | SQLite: 35 NPCs, 46 crops, 647 items |
| Episodic Memory | Working | ChromaDB: semantic search |

## Session 10 Accomplishments

**SMAPI Improvements (6 features):**
1. **Water source detection** - `nearestWater` in `/surroundings`
   - Returns x, y, distance, direction (e.g., "24 tiles south")
   - Agent can now navigate to refill watering can

2. **Shipping bin location** - `shippingBin` in `/state`
   - Fixed location (71, 14) on standard farm
   - For selling harvested crops

3. **Crop growth fix** - `daysUntilHarvest` now accurate
   - Was showing `dayOfCurrentPhase` (wrong)
   - Now calculates actual remaining days across all phases

4. **Tillability fix** - Non-farmable tiles now `blocked`
   - Removed blanket `location is Farm` check
   - Porch, paths, decorative areas correctly identified

5. **Forageable detection** - `isForageable` flag on objects
   - Spring onions, flowers, etc. marked for pickup

6. **Interactable objects** - `canInteract` + `interactionType`
   - Chests, machines, craftables identified

7. **Seed planting fix** - `use_tool` action handles objects
   - Was checking `CurrentTool` (null for seeds)
   - Now uses `ActiveObject` + `Utility.tryToPlaceItem()`

**Codex UI Updates (3 features):**
- Water source indicator
- Shipping bin indicator
- Crop growth progress display

**Bug Fixes:**
- CurrentTool now returns selected item name (seeds, not "None")
- Tile state correctly identifies non-tillable areas

## Files Changed (Session 10)

### SMAPI Mod
- `Models/GameState.cs` - Added WaterSourceInfo, ShippingBin, forageable/interactable fields
- `GameStateReader.cs` - Water detection, shipping bin, crop growth fix, tillability fix
- `ActionExecutor.cs` - Seed planting with Utility.tryToPlaceItem()

### Python Agent
- `unified_agent.py` - Water direction in empty can message, blocked tile handling

### Docs
- `SMAPI_IMPROVEMENTS_PLAN.md` - Created
- `CODEX_TASKS.md` - Updated by Codex

## Next Steps (Priority Order)

### HIGH - Next Session
1. **Test seed planting fix** - Restart game, verify seeds plant correctly
2. **Full farming cycle test** - Till → Plant → Water → Refill → Repeat
3. **Water refill navigation** - Agent finds and uses water source

### MEDIUM
4. **Crop harvesting** - When ready, agent harvests
5. **Shipping bin usage** - Agent sells crops
6. **Multi-day autonomy** - Run through multiple game days

### Testing Required (Before Complete)
- See TEAM_PLAN.md for comprehensive test matrix

---

## Quick Start: Testing

```bash
# 1. RESTART GAME FIRST (new SMAPI build)

# 2. Verify services
curl -s http://localhost:8790/health | jq .
curl -s http://localhost:8790/surroundings | jq '{tile: .data.currentTile, water: .data.nearestWater}'

# 3. Test planting manually
curl -X POST http://localhost:8790/action -H "Content-Type: application/json" \
  -d '{"action": "select_slot", "slot": 5}'  # Select seeds
curl -X POST http://localhost:8790/action -H "Content-Type: application/json" \
  -d '{"action": "use_tool"}'  # Should plant!

# 4. Run agent
cd /home/tim/StardewAI
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water all crops, refill can at water when empty"
```

---

*Session 10: Major SMAPI improvements. Seed planting fix ready for test.*

— Claude (PM)
