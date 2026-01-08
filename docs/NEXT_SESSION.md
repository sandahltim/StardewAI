# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** ✅ Game Knowledge DB EXPANDED

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B loaded |
| SMAPI mod | Running | Port 8790, all actions + /surroundings |
| UI Server | Running | Port 9001, team chat + VLM dashboard |
| VLM Perception | Working | Location, time, energy, tool detection |
| VLM Reasoning | Working | Contextual plans with personality |
| Spatial Awareness | Working | /surroundings + VLM uses directional info |
| Blocker Names | Working | Returns "Stone", "Tree", NPC names |
| **Game Knowledge DB** | **EXPANDED** | SQLite: 35 NPCs, 46 crops, 647 items, 23 locations, 210 recipes |
| **Episodic Memory** | Working | ChromaDB: semantic search over experiences |
| **Memory Integration** | Working | Context injected into VLM prompt per tick |

## Session Accomplishments (2026-01-08)

**Session 4 (DB Expansion):**
1. Expanded game_knowledge.db:
   - 35 NPCs (all villagers, not just marriage candidates)
   - 46 crops (all seasons)
   - 647 items (fish with locations, forage, tools)
   - 23 locations (with types: Farm, Town, Nature, Mine, Building)
   - 210 recipes (cooking + crafting)
2. Added query helpers:
   - `get_location_info(name)`
   - `get_locations_by_type(type)`
3. Enhanced build script with forage/fish location parsing
4. Tested full agent with memory - working correctly

**Session 3 (Memory System):**
1. Installed ChromaDB for episodic memory
2. Created `src/python-agent/memory/` module
3. Created game_knowledge.db (initial version)
4. Integrated memory into unified_agent.py
5. Tested full system - NPC knowledge + episodic memories working

## Files Changed (Session 3)

- `src/python-agent/memory/episodic.py` - NEW
- `src/python-agent/memory/retrieval.py` - NEW
- `src/python-agent/memory/__init__.py` - Updated exports
- `src/python-agent/memory/game_knowledge.py` - Added helper functions
- `src/python-agent/unified_agent.py` - Memory integration
- `src/data/game_knowledge.db` - NEW (SQLite database)
- `src/data/create_game_knowledge_db.py` - NEW (DB creation script)

## Next Steps (Priority Order)

### High Priority
1. **Memory Storage Triggers** ✨
   - Auto-store on NPC interaction
   - Auto-store on new location visited
   - Auto-store when VLM says "remember this"
   - Currently: manual storage only

2. **Long-Running Agent Test**
   - Run agent for extended period with social goal
   - Verify memory accumulation works
   - Check for stability issues

### Medium Priority
3. **UI Memory Viewer**
   - Show recent episodic memories
   - Show game knowledge lookups
   - Search interface

4. **Item Recognition Enhancement**
   - Use items DB to identify objects in screenshots
   - VLM can now query "what is this item?" from DB

### Low Priority
5. **Memory Pruning**
   - Consolidate similar memories
   - Forget old irrelevant memories
   - Keep memory count manageable

### Completed ✅
- ~~Expand Game Knowledge DB~~ (35 NPCs, 647 items, 23 locations, 210 recipes)
- ~~Test Memory in Action~~ (birthday detection, NPC gifts working)

---

## Game Knowledge DB (Current State)

```
Tables: npcs (35), crops (46), items (647), locations (23), recipes (210)
```

Query helpers in `src/python-agent/memory/game_knowledge.py`:
- `get_npc_info(name)` - NPC with gift preferences
- `get_npc_gift_reaction(npc, item)` - "loved", "liked", etc.
- `get_crop_info(name)` - Crop details
- `get_item_locations(name)` - Where to find items
- `get_location_info(name)` - Location details
- `get_locations_by_type(type)` - All locations of a type
- `get_crops_for_season(season)` - Plantable crops
- `get_birthday_npcs(season, day)` - Who has birthday
- `format_npc_for_prompt(name)` - Formatted for VLM
- `format_crop_for_prompt(name)` - Formatted for VLM

---

## Session Startup Checklist

1. Check GPU memory: `nvidia-smi`
2. Start llama-server if needed: `./scripts/start-llama-server.sh`
3. Start Stardew Valley via Steam (with SMAPI)
4. Verify mod: `curl http://localhost:8790/health`
5. Start UI server: `cd /home/tim/StardewAI && source venv/bin/activate && uvicorn src.ui.app:app --host 0.0.0.0 --port 9001 &`
6. Run agent: `python src/python-agent/unified_agent.py --goal "..."`

## Architecture Reference

```
Screenshot → Qwen3VL (8780) → Actions → ModBridgeController → SMAPI mod (8790) → Game
                ↑                              │
                │                              └── /surroundings (spatial context)
                │
        ┌───────┴───────┐
        │ Memory Context │
        ├───────────────┤
        │ Game Knowledge │ ← SQLite (NPCs, crops)
        │ Past Experience│ ← ChromaDB (episodic)
        └───────────────┘
```

## Team Status

| Team Member | Status | Current Focus |
|-------------|--------|---------------|
| Claude | PM | DB expanded, next: memory triggers |
| Codex | Active | Expanded DB with items/locations/recipes |
| Tim | Lead | Testing, direction |

---

*Game knowledge DB expanded. 35 NPCs, 647 items, 23 locations, 210 recipes. Memory integration working.*

— Claude (PM)
