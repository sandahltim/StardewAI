# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** ✅ READY - Tile state detection implemented

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B loaded |
| SMAPI mod | **UPDATED** | Port 8790, now with tile state detection! |
| UI Server | Running | Port 9001, team chat + VLM dashboard |
| VLM Perception | Working | Location, time, energy, tool detection |
| **Tile State API** | **NEW** | Returns tilled/planted/watered/clear state |
| Game Knowledge DB | Working | SQLite: 35 NPCs, 46 crops, 647 items |
| Episodic Memory | Working | ChromaDB: semantic search |

## Session Accomplishments (2026-01-08)

**Session 8 (Tile State Detection):**
1. **Tile state detection in SMAPI** - `currentTile` now returns:
   - `state`: "clear" | "tilled" | "planted" | "watered" | "debris"
   - `object`: null | "Weeds" | "Stone" | "Tree" | etc.
   - `canTill`: true/false
   - `canPlant`: true/false

2. **Agent uses game data** - VLM now receives explicit instructions:
   - `>>> TILE IN FRONT: CLEAR DIRT - use HOE to TILL! <<<`
   - `>>> TILE IN FRONT: TILLED SOIL - select SEEDS and PLANT! <<<`
   - `>>> TILE IN FRONT: PLANTED - select WATERING CAN and WATER! <<<`

3. **Farming state machine** - System prompt updated with clear transitions

4. **Multiple perception improvements**:
   - Ground type detection (lawn vs farmable)
   - Farm layout knowledge (decorative area near house)
   - Explicit facing-direction context

**Test Results:**
- Tile state detection confirmed working
- Agent successfully detected "WATERED" state (crops planted!)
- Rainy weather detection working

## Files Changed (Session 8)

### SMAPI Mod
- `Models/GameState.cs` - Added `CurrentTileInfo` class
- `GameStateReader.cs` - Added `GetTileState()` method for tile state detection

### Python Agent
- `unified_agent.py` - `format_surroundings()` now uses tile state for explicit guidance

### Config
- `config/settings.yaml` - Updated with:
  - Ground type perception
  - Farm layout knowledge
  - Farming state machine

## Next Steps (Priority Order)

### High Priority - NEXT SESSION
1. **Extended Planting Test** 🌱
   - Fresh Day 1 start
   - Watch Rusty plant all 15 parsnip seeds
   - Verify: till → plant → water sequence works
   - Monitor energy consumption

2. **Test Edge Cases**:
   - What happens when facing non-tillable ground?
   - Obstacle navigation (rocks, trees in the way)
   - Tool switching reliability

### Medium Priority
3. **Add crop growth tracking** - Show crop growth stage in state
4. **Inject Calendar Context** - Use `get_upcoming_events()` in VLM prompt
5. **Add remaining NPC schedules** - 17/35 still missing

### Codex Tasks (See CODEX_TASKS.md)
- UI: Display tile state in dashboard
- UI: Show current farming step (clear/till/plant/water)

---

## Quick Start: Planting Test

```bash
# 1. Verify services
curl -s http://localhost:8790/health | jq .  # SMAPI mod
curl -s http://localhost:8790/surroundings | jq .currentTile  # Tile state

# 2. Start Stardew Valley and load Day 1 save

# 3. Run agent
cd /home/tim/StardewAI
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Plant parsnips! Follow tile state instructions."
```

**Expected behavior:**
- Agent sees `>>> TILE IN FRONT: CLEAR DIRT - use HOE to TILL! <<<`
- Agent selects hoe (slot 1) and uses tool
- Agent sees `>>> TILE IN FRONT: TILLED SOIL - select SEEDS and PLANT! <<<`
- Agent selects seeds (slot 5) and uses tool
- Agent sees `>>> TILE IN FRONT: PLANTED - select WATERING CAN and WATER! <<<`
- Agent selects watering can (slot 2) and uses tool
- Agent sees `>>> TILE IN FRONT: WATERED - DONE! Move to next tile. <<<`

---

*Tile state detection implemented. Next session: full planting test.*

— Claude (PM)
