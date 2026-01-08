# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. UI: Watering Can Level Display (Priority: HIGH)

**Status:** Pending
**Assigned:** 2026-01-08

Display watering can water level in the dashboard:
- Show current water / max capacity (e.g., "15/40")
- Visual bar or indicator
- Warning color when low or empty
- Data available from `/state` endpoint: `player.wateringCanWater` and `player.wateringCanMax`

### 2. UI: Current Instruction Display (Priority: MEDIUM)

**Status:** Pending
**Assigned:** 2026-01-08

Show the current tile state instruction prominently in dashboard:
- The instruction from spatial context (e.g., ">>> TILE: TILLED - select_slot 5 for SEEDS <<<")
- Make it visually prominent so user can see what agent should do
- Update in real-time from agent status

---

## Completed Tasks

- [x] UI: Tile State Display (2026-01-08)
- [x] UI: Farming Progress Bar (2026-01-08)
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

*Session 9: Tool awareness and watering can capacity added. VLM now uses game state for tool info.*

— Claude (PM)
