# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. Game Knowledge Database (Priority: HIGH)

**Status:** NEW - Next Session Priority
**Assigned:** 2026-01-08
**Depends on:** None
**Reference:** `docs/MEMORY_ARCHITECTURE.md`

Create SQLite database with Stardew Valley game knowledge so Rusty understands the game.

**Deliverables:**
1. Create `src/data/game_knowledge.db` with schema:
   - `npcs` - name, birthday, gifts (loved/liked/hated), location
   - `crops` - name, season, growth_days, sell_price, seed info
   - `items` - name, category, sell_price, where to find
   - `locations` - name, type, how to unlock
   - `recipes` - name, type, ingredients

2. Populate with data:
   - Find existing Stardew JSON/CSV data (modding community has these)
   - Or scrape from wiki if needed
   - Priority: NPCs (gifts), Crops, basic Items

3. Create query helpers in `src/python-agent/memory/game_knowledge.py`:
   ```python
   def get_npc_info(name: str) -> dict
   def get_npc_gift_reaction(npc: str, item: str) -> str  # "loved"/"liked"/etc
   def get_crop_info(name: str) -> dict
   def get_item_locations(name: str) -> list
   ```

4. Expose via `/api/game-knowledge?type=npc&name=Shane`

**Test:** `curl http://localhost:9001/api/game-knowledge?type=npc&name=Shane` returns his gift preferences.

---

### 2. UI: Directional Compass Widget (Priority: Medium)

**Status:** NEW
**Assigned:** 2026-01-08

Add visual compass to VLM dashboard:
```
     ↑ (5)
  ← (5)  ✗ (1)
     ✗ (2)
```
- Green arrow = clear, show tiles
- Red X = blocked, show tiles until blocked
- Update via WebSocket when surroundings change

---

### 3. UI: Session Events Timeline (Priority: Low)

**Status:** NEW
**Assigned:** 2026-01-08

Show recent session events from `/api/session-memory`:
- Position changes
- Actions executed
- Collapsible panel, last 20 events

---

### 4. UI: Memory Viewer (Priority: Low - Future)

**Status:** BLOCKED - Waiting for memory system
**Assigned:** 2026-01-08

Once memory system exists:
- Show recent episodic memories
- Show game knowledge lookups
- Search memories

---

## Completed Tasks

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
- https://stardewvalleywiki.com/Villagers (NPC data)
- https://stardewvalleywiki.com/Crops (crop data)

**Priority order:**
1. NPCs + gift preferences (most useful for social gameplay)
2. Crops (farming is core gameplay)
3. Items (for identification)
4. Locations (for navigation)

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

*Priority: Game Knowledge DB is critical for making Rusty smart.*

— Claude (PM)
