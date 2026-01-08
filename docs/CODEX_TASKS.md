# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08 Session 12

---

## Active Tasks

### 1. UI: Harvest Ready Indicator (Priority: HIGH)

**Status:** Pending
**Assigned:** 2026-01-08 Session 12

Show crops ready for harvest:
- Display: "HARVEST READY: 3" or "HARVEST: 0 (1-4 days)"
- Color: green when crops ready, gray when not
- Data from `/state` → `.data.location.crops[]`
- Count crops where `.isReadyForHarvest == true`
- If none ready, show days until soonest: `min(daysUntilHarvest)`

Purpose: Know when to test harvesting - parsnips maturing Day 8-9.

---

### 2. UI: Energy/Stamina Bar (Priority: MEDIUM)

**Status:** Pending
**Assigned:** 2026-01-08 Session 12

Visual stamina display:
- Bar showing current vs max stamina
- Color gradient: green → yellow → red as depleted
- Data from `/state` → `.data.player.stamina` and `.data.player.maxStamina`
- Show numeric value: "156/270"

Purpose: Agent needs to know when to rest.

---

### 3. UI: Action History Panel (Priority: MEDIUM)

**Status:** Pending
**Assigned:** 2026-01-08 Session 12

Show the last 10 actions the VLM sees:
- Display recent action list from session memory
- Highlight repeated actions in red
- Show "BLOCKED" prefix for failed moves
- Data from `/api/session-memory?event_type=action&limit=10`

Purpose: Debug what VLM sees about its past actions.

---

## Future Task Ideas (Not Assigned)

- Location minimap showing player position on farm
- NPC relationship tracker with gift suggestions
- Seasonal calendar with upcoming events
- Goal progress tracker with checkboxes
- Daily earnings/shipping summary

---

## Completed Tasks

- [x] UI: Crop Status Summary (2026-01-08 Session 11)
- [x] UI: Location + Position Display (2026-01-08 Session 11)
- [x] UI: Action Repeat Detection (2026-01-08 Session 11)
- [x] UI: Inventory Panel (2026-01-08 Session 11)
- [x] UI: Action Result Log (2026-01-08 Session 11)
- [x] UI: Agent Stuck Indicator (2026-01-08)
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
- [x] SMAPI Mod: Better blocker names (2026-01-08)
- [x] Memory System: /api/session-memory endpoint (2026-01-08)
- [x] UI: Movement History Panel (2026-01-08)
- [x] SMAPI Mod: /surroundings endpoint (2026-01-08)
- [x] SMAPI Mod: toggle_menu, cancel, toolbar actions (2026-01-08)
- [x] UI: VLM Dashboard Panel (2026-01-08)
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

*Session 12: Assigned harvest-phase UI tasks - indicator for harvest-ready crops, stamina bar, action history panel.*

— Claude (PM)
