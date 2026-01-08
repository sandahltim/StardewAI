# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08

---

## Active Tasks

### 1. UI: Agent Stuck Indicator (Priority: LOW)

**Status:** Pending
**Assigned:** 2026-01-08 Session 10

Visual indicator when agent appears stuck:
- Track position over last 10 ticks
- If position unchanged for 5+ ticks while actions sent, show "STUCK" warning
- Could use movement history data already being collected
- Help identify when agent needs intervention

*Note: Low priority - only assign if Codex has bandwidth*

---

## Future Task Ideas (Not Assigned)

- Location minimap showing player position on farm
- NPC relationship tracker with gift suggestions
- Seasonal calendar with upcoming events
- Inventory management panel
- Action history replay/visualization
- Goal progress tracker with checkboxes

---

## Completed Tasks

- [x] UI: Water Source Indicator (2026-01-08)
- [x] UI: Shipping Bin Indicator (2026-01-08)
- [x] UI: Crop Growth Progress (2026-01-08)
- [x] UI: Watering Can Level Display (2026-01-08)
- [x] UI: Current Instruction Display (2026-01-08)
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
