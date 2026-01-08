# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. Calendar/Festival Table (Priority: HIGH)

**Status:** NEW
**Assigned:** 2026-01-08

Add calendar table to `src/data/game_knowledge.db`:

```sql
CREATE TABLE calendar (
    season TEXT,
    day INTEGER,
    event_name TEXT,
    event_type TEXT,    -- "festival", "birthday", "shop"
    description TEXT,
    PRIMARY KEY (season, day, event_name)
);
```

**Events to populate:**
- Festivals: Egg Festival (Spring 13), Flower Dance (Spring 24), Luau (Summer 11), Dance of Moonlight Jellies (Summer 28), Stardew Valley Fair (Fall 16), Spirit's Eve (Fall 27), Festival of Ice (Winter 8), Night Market (Winter 15-17), Feast of Winter Star (Winter 25)
- Shop events: Traveling Cart (Fri/Sun)
- Birthday notes are already in NPCs table

**Add query helper** to `game_knowledge.py`:
```python
def get_events_for_day(season: str, day: int) -> List[Dict[str, Any]]
def get_upcoming_events(season: str, day: int, days_ahead: int = 7) -> List[Dict[str, Any]]
```

**Update** `src/data/create_game_knowledge_db.py` OR `scripts/build_game_knowledge_db.py` (whichever is canonical)

---

### 2. NPC Schedule Data (Priority: MEDIUM)

**Status:** NEW
**Assigned:** 2026-01-08

The `schedule_notes` column in NPCs table is empty for 35/35 NPCs. Add general schedule notes:

**Examples:**
- Shane: "Works at JojaMart 9am-5pm. Drinks at Saloon 6pm-11pm. Visits chicken coop at ranch mornings."
- Pierre: "Runs Pierre's General Store 9am-5pm. Closed Wednesdays."
- Penny: "Teaches Jas and Vincent at museum 10am-2pm Tue/Wed/Fri."

**Focus on:** Marriage candidates + key shop NPCs first.

---

### 3. UI: Memory Viewer Panel (Priority: LOW)

**Status:** Blocked until memory system tested
**Assigned:** 2026-01-08

Add memory viewer to the dashboard:
- Show recent episodic memories (last 10)
- Show game knowledge lookups made this session
- Simple search interface

**Memory system now working** - can unblock this task.

---

## Completed Tasks

- [x] Game Knowledge DB - Items table (2026-01-08)
- [x] Game Knowledge DB - Locations table + helpers (2026-01-08)
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
