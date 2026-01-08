# Next Session - StardewAI

**Last Updated:** 2026-01-08 by Claude
**Status:** ✅ Memory System COMPLETE

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
| **Game Knowledge DB** | **NEW** | SQLite: 12 NPCs, 36 crops |
| **Episodic Memory** | **NEW** | ChromaDB: semantic search over experiences |
| **Memory Integration** | **NEW** | Context injected into VLM prompt per tick |

## Session Accomplishments (2026-01-08)

**Session 3 (Memory System):**
1. Installed ChromaDB for episodic memory
2. Created `src/python-agent/memory/` module:
   - `episodic.py` - ChromaDB storage/retrieval
   - `retrieval.py` - Combined memory context for VLM
   - `game_knowledge.py` - SQLite queries (extended with new helpers)
3. Created `src/data/game_knowledge.db` with:
   - 12 NPCs (all marriage candidates with gift preferences)
   - 36 crops (all seasons with growth/price data)
4. Integrated memory into `unified_agent.py`:
   - Memory context retrieved per tick
   - Injected into VLM prompt before spatial context
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
1. **Expand Game Knowledge DB**
   - Add `items` table (tools, forage, artifacts, fish)
   - Add `locations` table (buildings, areas, unlock conditions)
   - Add `recipes` table (cooking, crafting)
   - Consider: fish locations, tool upgrades, calendar events

2. **Test Memory in Action**
   - Run agent with goal "Make friends with Shane"
   - Verify NPC info appears in VLM prompt
   - Verify episodic memories are stored after interactions
   - Test birthday detection

### Medium Priority
3. **Memory Storage Triggers**
   - Auto-store on NPC interaction
   - Auto-store on new location visited
   - Auto-store when VLM says "remember this"
   - Currently: manual storage only

4. **UI Memory Viewer**
   - Show recent episodic memories
   - Show game knowledge lookups
   - Search interface

### Low Priority
5. **Memory Pruning**
   - Consolidate similar memories
   - Forget old irrelevant memories
   - Keep memory count manageable

---

## Data to Add (Game Knowledge DB)

### Items Table (High Priority)
```sql
CREATE TABLE items (
    name TEXT PRIMARY KEY,
    category TEXT,       -- "Fish", "Forage", "Artifact", "Tool", etc.
    description TEXT,
    sell_price INTEGER,
    locations TEXT       -- JSON array of where to find
);
```

**Categories to populate:**
- Tools (Hoe, Watering Can, Pickaxe, Axe, Fishing Rod)
- Forage items by season
- Common fish with locations/times
- Artifacts for museum

### Locations Table (Medium Priority)
```sql
CREATE TABLE locations (
    name TEXT PRIMARY KEY,
    type TEXT,           -- "Town", "Farm", "Mine", "Beach", etc.
    unlocked_by TEXT,    -- How to access
    notable_features TEXT -- JSON array
);
```

**Locations to add:**
- Farm, FarmHouse, Greenhouse
- Town buildings (Pierre's, Blacksmith, Saloon, etc.)
- Beach, Forest, Mountain, Desert
- Mines (with floor info)

### Recipes Table (Low Priority)
```sql
CREATE TABLE recipes (
    name TEXT PRIMARY KEY,
    type TEXT,           -- "Cooking", "Crafting"
    ingredients TEXT,    -- JSON: {"Wood": 50, "Stone": 20}
    unlock_condition TEXT
);
```

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
| Claude | PM | Memory system complete, expand DB next |
| Codex | Idle | Available for items/locations/recipes |
| Tim | Lead | Testing, direction |

---

*Memory system complete. Next: expand game knowledge with items, locations, recipes.*

— Claude (PM)
