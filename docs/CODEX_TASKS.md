# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-08 Session 15

---

## Active Tasks

### HIGH: Spatial Memory Map
**Priority:** High
**Assigned:** 2026-01-08 Session 17

Build a spatial memory system that the agent can update and reference:
1. Create a simple 2D grid map of the farm (stored in SQLite or JSON)
2. Track tile states: tilled, planted, watered, crop type, obstacles
3. API endpoint `/api/spatial-map` to get/update tile info
4. Agent can query "where are tilled but unplanted tiles?"
5. Agent can mark tiles as worked

**Why needed:** Agent tills soil but forgets where it is, doesn't plant.
A persistent map lets it remember locations between turns.

**Files to create/modify:**
- `src/python-agent/memory/spatial_map.py` - Map storage and queries
- `src/ui/app.py` - Add `/api/spatial-map` endpoint
- Optional: UI visualization of the map

**Test command:**
```python
from memory.spatial_map import SpatialMap
farm_map = SpatialMap("Farm")
farm_map.set_tile(70, 18, {"state": "tilled", "worked_at": "Day 3"})
tilled = farm_map.find_tiles(state="tilled", not_planted=True)
```

---

## Future Task Ideas (Not Assigned)

- Location minimap showing player position on farm
- NPC relationship tracker with gift suggestions
- Seasonal calendar with upcoming events
- Goal progress tracker with checkboxes
- Daily earnings/shipping summary

---

## Completed Tasks

- [x] UI: Bedtime/Sleep Indicator (2026-01-09 Session 15)
- [x] UI: Day/Season Progress Display (2026-01-09 Session 15)
- [x] UI: Goal Progress Checklist (2026-01-09 Session 15)
- [x] UI: Session Stats Panel (2026-01-08 Session 14)
- [x] UI: VLM Latency Graph (2026-01-08 Session 14)
- [x] UI: Crop Maturity Countdown (2026-01-08 Session 14)
- [x] UI: VLM Error Display Panel (2026-01-08 Session 13)
- [x] UI: Navigation Intent Display (2026-01-08 Session 13)
- [x] Agent: User Chat Context + Reply Hook (2026-01-08 Session 13)
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

*Session 14: Great work completing VLM error display, nav intent, and chat integration! New tasks: session stats panel, latency graph, crop countdown.*

— Claude (PM)
