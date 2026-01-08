# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** ✅ READY FOR EXTENDED AGENT TEST

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
| **Memory Triggers** | **NEW** | Auto-store on new location, NPC met, notable events |

## Session Accomplishments (2026-01-08)

**Session 5 (Memory Triggers):**
1. Added automatic memory storage triggers:
   - First visit to new location
   - Meeting NPC for first time (includes gift preferences)
   - VLM reasoning with importance markers
2. Memory state persistence - loads on startup to prevent duplicates
3. Assigned Codex: Calendar/Festival table, NPC schedules
4. All systems tested and working

**Session 4 (DB Expansion):**
1. Expanded game_knowledge.db: 35 NPCs, 46 crops, 647 items, 23 locations, 210 recipes
2. Added location query helpers
3. Enhanced build script with forage/fish location parsing

**Session 3 (Memory System):**
1. ChromaDB for episodic memory
2. SQLite for game knowledge
3. Memory integration into VLM prompt

## Files Changed (Session 3)

- `src/python-agent/memory/episodic.py` - NEW
- `src/python-agent/memory/retrieval.py` - NEW
- `src/python-agent/memory/__init__.py` - Updated exports
- `src/python-agent/memory/game_knowledge.py` - Added helper functions
- `src/python-agent/unified_agent.py` - Memory integration
- `src/data/game_knowledge.db` - NEW (SQLite database)
- `src/data/create_game_knowledge_db.py` - NEW (DB creation script)

## Next Steps (Priority Order)

### High Priority - NEXT SESSION
1. **Extended Agent Test: Farming & Exploring** 🌾
   - Run agent for 10-15 minutes
   - Goals: "Water crops and explore the farm" or "Go meet villagers"
   - Watch for: memory accumulation, navigation, decision quality
   - Monitor: UI dashboard for real-time status

### What to Watch For
- Does Rusty remember locations visited?
- Does Rusty remember NPCs met?
- Does spatial awareness prevent getting stuck?
- Does memory context help with decisions?
- Any stability issues or crashes?

### Medium Priority
2. **Calendar/Festival Data** (Codex assigned)
   - Egg Festival, Flower Dance, etc.
   - Upcoming events in VLM prompt

3. **NPC Schedule Notes** (Codex assigned)
   - Where to find NPCs at what times
   - Currently 0/35 populated

4. **UI Memory Viewer** (Codex - LOW)
   - Show episodic memories in dashboard

### Completed ✅
- ~~Memory Storage Triggers~~ (auto-store on location, NPC, notable events)
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
| Claude | PM | Memory triggers complete, ready for test |
| Codex | Active | Calendar table, NPC schedules, UI work |
| Tim | Lead | Next: watch Rusty farm & explore |

---

## Quick Start: Extended Agent Test

```bash
# 1. Verify services
curl -s http://localhost:8790/health | jq .  # SMAPI mod
curl -s http://localhost:8780/health | jq .  # llama-server

# 2. Open UI dashboard in browser
# http://localhost:9001

# 3. Start Stardew Valley (if not running)
# Load a save with some crops to water

# 4. Run agent with farming goal
cd /home/tim/StardewAI
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water the crops, then explore and meet villagers"

# OR for observe-only (no control)
python src/python-agent/unified_agent.py --observe --ui --goal "Water crops and explore"
```

**Monitor:**
- Terminal: Watch for 💾 memory storage, 🧭 spatial awareness, 💭 reasoning
- UI Dashboard: Real-time status, movement history, VLM decisions
- Game: Watch Rusty's behavior

---

*All systems ready. Memory triggers active. Next session: extended farming & exploration test.*

— Claude (PM)
