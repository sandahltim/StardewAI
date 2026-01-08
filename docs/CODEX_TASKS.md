# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08 Session 11

---

## Active Tasks

### 1. UI: Crop Status Summary (Priority: HIGH)

**Status:** Pending
**Assigned:** 2026-01-08 Session 11

Prominent display of crop watering status:
- Large, clear display: "WATERED: 6/15" or similar
- Color code: green when all watered, orange when some remain
- Show count from `/state` → `.data.location.crops[]`
- Calculate: watered vs unwatered (`.isWatered == true/false`)
- Update on each poll

Purpose: Help debug agent efficiency - see at a glance if crops are getting watered.

---

### 2. UI: Location + Position Display (Priority: HIGH)

**Status:** Pending
**Assigned:** 2026-01-08 Session 11

Clear display of current location and position:
- Show location name prominently: "FARM" or "FARMHOUSE"
- Show tile coordinates: "(64, 19)"
- Data from `/state` → `.data.location.name` and `.data.player.tileX/Y`

Purpose: Debug VLM hallucination - agent sometimes thinks it's in wrong location.

---

### 3. UI: Action Repeat Detection (Priority: MEDIUM)

**Status:** Pending
**Assigned:** 2026-01-08 Session 11

Detect and highlight when agent repeats same action:
- Track last 5-10 actions from session-memory
- If same action appears 3+ times in a row, show "REPEATING" warning
- Color code: red when stuck in loop
- Data from `/api/session-memory?event_type=action&limit=10`

Purpose: Debug agent decision-making - identify when it's stuck in a loop.

---

## Future Task Ideas (Not Assigned)

- Location minimap showing player position on farm
- NPC relationship tracker with gift suggestions
- Seasonal calendar with upcoming events
- Goal progress tracker with checkboxes

---

## Completed Tasks

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

*Session 11: Assigned debugging UI tasks to help identify agent decision-making issues.*

— Claude (PM)
