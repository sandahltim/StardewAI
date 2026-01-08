# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. UI: Memory Viewer Panel (Priority: LOW)

**Status:** Complete
**Assigned:** 2026-01-08

Memory viewer added to dashboard:
- Recent episodic memories (last 10)
- Game knowledge lookups made this session
- Search interface

---

## Completed Tasks

- [x] Game Knowledge DB - Calendar table + helpers (2026-01-08)
- [x] Game Knowledge DB - NPC schedule notes (2026-01-08)
- [x] UI: Memory Viewer Panel (2026-01-08)
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
