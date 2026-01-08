# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. UI: Tile State Display (Priority: HIGH)

**Status:** Not Started
**Assigned:** 2026-01-08

**Description:**
The SMAPI mod now returns `currentTile` data from `/surroundings`. Display this in the dashboard so we can see what farming state Rusty is working with.

**API Response:**
```json
GET /surroundings
{
  "currentTile": {
    "state": "clear|tilled|planted|watered|debris",
    "object": null|"Weeds"|"Stone"|"Tree"|etc,
    "canTill": true|false,
    "canPlant": true|false
  }
}
```

**Requirements:**
1. Add "Tile State" indicator to dashboard
2. Color-coded display:
   - `clear` (canTill): 🟢 "Ready to Till"
   - `tilled`: 🟤 "Ready to Plant"
   - `planted`: 🟡 "Ready to Water"
   - `watered`: 🔵 "Done!"
   - `debris`: 🔴 with object name
3. Poll `/surroundings` endpoint to update

**Test:** `curl -s http://localhost:8790/surroundings | jq .data.currentTile`

---

### 2. UI: Farming Progress Bar (Priority: MEDIUM)

**Status:** Not Started

**Description:**
Visual workflow indicator:
```
[CLEAR] → [TILL] → [PLANT] → [WATER] → ✓
```
Highlight current step based on tile state.

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

## Communication Protocol

### For Status Updates
Post to team chat: `./scripts/team_chat.py post codex "your message"`

### For Task Completion
1. Post to team chat: "Completed: [task name]"
2. Update this doc or Claude will

---

*New: Tile state detection working! UI tasks to visualize it.*

— Claude (PM)
