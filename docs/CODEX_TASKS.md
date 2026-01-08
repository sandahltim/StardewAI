# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08 Session 13

---

## Active Tasks

### 1. HIGH: VLM Error Display Panel
**Why:** VLM often returns malformed JSON. Currently fails silently - hard to debug.

**What:** Show VLM errors in UI:
- Display "JSON Parse Error" when VLM returns bad JSON
- Show last raw VLM response (truncated) for debugging
- Count of successful vs failed parses this session

**Data source:** Add to `/api/status` - track `vlm_errors: [{time, error, raw_response}]`

---

### 2. MEDIUM: Navigation Intent Display
**Why:** Agent now uses visual navigation. Useful to see what it's trying to do.

**What:** Show navigation info:
- Current target (e.g., "Going to: Water (21 tiles south)")
- Last blocked direction (e.g., "Blocked: down by Tree")
- Movement attempts counter

**Data source:** Extract from `/api/status` surroundings and action history

---

### 3. LOW: Rusty Chat Integration (Roadmap)
**Why:** Tim wants Rusty to respond to messages in team chat.

**What:** When user posts to team chat, include message in VLM context. VLM can respond in its `reasoning` field, which gets posted back to chat.

**Note:** This is prep work - actual VLM integration is Claude's task.

---

## Future Task Ideas (Not Assigned)

- Location minimap showing player position on farm
- NPC relationship tracker with gift suggestions
- Seasonal calendar with upcoming events
- Goal progress tracker with checkboxes
- Daily earnings/shipping summary

---

## Completed Tasks

- [x] UI: Harvest Ready Indicator (2026-01-08 Session 12)
- [x] UI: Energy/Stamina Bar (2026-01-08 Session 12)
- [x] UI: Action History Panel (2026-01-08 Session 12)
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

*Session 13: Assigned VLM error display (debug tool), navigation intent display (pathfinding debug), Rusty chat prep (roadmap).*

— Claude (PM)
