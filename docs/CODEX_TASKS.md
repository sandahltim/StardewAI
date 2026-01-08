# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. Expand Game Knowledge DB - Items Table (Priority: HIGH)

**Status:** NEW - Next Session Priority
**Assigned:** 2026-01-08

Add items table to `src/data/game_knowledge.db`:

```sql
CREATE TABLE items (
    name TEXT PRIMARY KEY,
    category TEXT,       -- "Tool", "Fish", "Forage", "Artifact", "Mineral"
    description TEXT,
    sell_price INTEGER,
    locations TEXT       -- JSON array of where to find
);
```

**Data to populate:**
1. **Tools** (5-10 items):
   - Hoe, Watering Can, Pickaxe, Axe, Fishing Rod, Scythe
   - Include upgrade levels if useful

2. **Forage by Season** (20+ items):
   - Spring: Leek, Daffodil, Dandelion, Spring Onion
   - Summer: Grape, Spice Berry, Sweet Pea
   - Fall: Hazelnut, Wild Plum, Blackberry
   - Winter: Crystal Fruit, Crocus, Holly

3. **Common Fish** (15-20 items):
   - Include location, time of day, season
   - Priority: Carp, Sunfish, Catfish, Sturgeon, etc.

**Update `src/data/create_game_knowledge_db.py`** to include items data.

**Test:** `python -c "from memory.game_knowledge import get_item_locations; print(get_item_locations('Leek'))"`

---

### 2. Expand Game Knowledge DB - Locations Table (Priority: MEDIUM)

**Status:** NEW
**Assigned:** 2026-01-08

Add locations table to the database:

```sql
CREATE TABLE locations (
    name TEXT PRIMARY KEY,
    type TEXT,           -- "Farm", "Town", "Nature", "Mine", "Building"
    unlocked_by TEXT,    -- How to access (default available, repair bus, etc.)
    notable_features TEXT -- JSON array ["fishing", "foraging", "npcs"]
);
```

**Locations to add:**
- Farm areas: Farm, FarmHouse, Greenhouse, Barn, Coop
- Town: Pierre's, Blacksmith, Saloon, Clinic, JojaMart
- Nature: Beach, Forest, Mountain, Desert, Railroad
- Mine: Mines (note floor ranges: 1-40 ice, 41-79 lava, 80-120 skull)

**Add query helper** to `game_knowledge.py`:
```python
def get_location_info(name: str) -> Optional[Dict[str, Any]]
def get_locations_by_type(type: str) -> List[Dict[str, Any]]
```

---

### 3. UI: Memory Viewer Panel (Priority: LOW)

**Status:** NEW - Blocked until memory system tested
**Assigned:** 2026-01-08

Add memory viewer to the dashboard:
- Show recent episodic memories (last 10)
- Show game knowledge lookups made this session
- Simple search interface

---

## Completed Tasks

- [x] Game Knowledge Database - NPCs and Crops (2026-01-08)
- [x] SMAPI Mod: Better blocker names - NPCs, objects, terrain, buildings (2026-01-08)
- [x] Memory System: /api/session-memory endpoint + session_events table (2026-01-08)
- [x] UI: Movement History Panel - positions, stuck indicator, trail (2026-01-08)
- [x] SMAPI Mod: /surroundings endpoint - directional awareness (2026-01-08)
- [x] SMAPI Mod: toggle_menu, cancel, toolbar_next, toolbar_prev (2026-01-08)
- [x] UI: VLM Dashboard Panel - status, reasoning, actions (2026-01-08)
- [x] FastAPI UI server (app.py)
- [x] SQLite storage layer (storage.py)
- [x] WebSocket broadcast infrastructure
- [x] TTS integration (Piper)
- [x] Status/goals/tasks API
- [x] Team Chat frontend

---

## Data Sources for Game Knowledge

**Existing JSON data (check these first):**
- https://github.com/MouseyPounds/stardew-checkup (has structured data)
- https://github.com/spacechase0/StardewEditor (game data exports)
- SMAPI itself may have data files

**Wiki scraping (fallback):**
- https://stardewvalleywiki.com/Fish
- https://stardewvalleywiki.com/Foraging
- https://stardewvalleywiki.com/Artifacts

**Note:** WebFetch may be blocked in background agents. Use training knowledge or download JSON files manually.

---

## Communication Protocol

### For Status Updates
Post to team chat: `./scripts/team_chat.py post codex "your message"`

### For Questions
Post to team chat, Claude will respond async.

### For Task Completion
1. Post to team chat: "Completed: [task name]"
2. Update this doc or Claude will

---

*Priority: Items table is most useful for identifying objects Rusty sees.*

— Claude (PM)
