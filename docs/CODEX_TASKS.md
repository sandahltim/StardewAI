# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-10 Session 36

---

## Project Review Findings (Session 36)

A full project review identified these gaps:

### UI Status: 70% Functional
- Chat, Team Chat, Goals, Tasks, Control Panel - **100% working**
- Skill tracking, Shipping history - **90% working**
- Compass, Tile State, Crops - **100% SMAPI-dependent** (show "waiting" if SMAPI down)
- VLM Debug section - **exists but agent never sends data**
- Lessons panel - **exists but agent never populates**
- Memory search - **Chroma DB is empty**

### Key Issues
1. **Agent doesn't populate UI fields** - VLM debug, lessons, memory
2. **SMAPI-dependent sections have no fallback** - just show "waiting"
3. **Rusty has no memory** - personality exists but no continuity

---

## Active Tasks

### TASK: SMAPI Status Indicators (NEW - Session 36)

**Priority:** MEDIUM
**Assigned:** 2026-01-10 Session 36
**Status:** ✅ Complete

#### Background
Many UI panels depend on SMAPI running (Compass, Tile State, Crops, Inventory, etc.). When SMAPI is unavailable, they show "Waiting for..." indefinitely. Users need clear feedback.

#### Requirements

**1. Add SMAPI Connection Status Badge**

In the header/status area, add a connection indicator:
```
┌──────────────────────────────────┐
│ SMAPI: 🟢 Connected              │
│ SMAPI: 🔴 Unavailable            │
└──────────────────────────────────┘
```

**2. Update Affected Panels**

When SMAPI is unavailable, show explicit message instead of "Waiting...":
```
┌──────────────────────────────────┐
│ COMPASS                          │
├──────────────────────────────────┤
│ ⚠️ SMAPI unavailable            │
│ Start game with mod to enable   │
└──────────────────────────────────┘
```

**3. Affected Sections**
- Compass Navigation
- Tile State
- Watering Can Status
- Crop Status
- Inventory Grid
- Stamina/Energy
- Movement History (position events)

#### Implementation

1. Check SMAPI status on each poll (already fetching `/surroundings`)
2. Set global `smapiConnected` flag in app.js
3. Conditionally render "unavailable" badge in affected panels

#### Files to Modify
- `src/ui/static/app.js` - Add SMAPI status tracking, update render functions
- `src/ui/templates/index.html` - Add status badge area
- `src/ui/static/app.css` - Style for unavailable state

---

### TASK: Empty State Messages (NEW - Session 36)

**Priority:** LOW
**Assigned:** 2026-01-10 Session 36
**Status:** ✅ Complete (Session 37)

#### Background
Several panels show "None" or "Waiting..." when data hasn't been populated yet. Better UX to show contextual empty states.

#### Requirements

Update these panels with helpful empty state messages:

| Panel | Current | Better |
|-------|---------|--------|
| Lessons | "None" | "No lessons recorded yet. Failures will appear here." |
| Memory Search | "None" | "No memories stored yet." |
| Skill History | "No data yet" | "No skills executed yet. Run agent to see stats." |
| VLM Debug | "Waiting for observation..." | "Waiting for agent to start thinking..." |

#### Files to Modify
- `src/ui/static/app.js` - Update default text in render functions

---

## Backlog (Future Sessions)

### TASK: Rusty Memory Persistence (Claude)

**Priority:** HIGH (for character development)
**Owner:** Claude
**Status:** Planned

Rusty currently has no memory between sessions. Need:
- Episodic memory persistence
- Character state that evolves
- NPC relationship tracking

### TASK: Agent VLM Debug Population (Claude)

**Priority:** HIGH
**Owner:** Claude
**Status:** ✅ Complete (Session 37)

Added VLM debug state tracking to unified_agent.py:
- `vlm_observation` - from VLM result
- `proposed_action` - first action from VLM
- `validation_status` - "passed", "blocked"
- `validation_reason` - blocker name if any
- `executed_action` - what was executed
- `executed_outcome` - "success", "failed", or "blocked"

Updates sent via `_send_ui_status()` at key points in `_tick()`.

### TASK: Lesson Recording to UI (Claude)

**Priority:** MEDIUM
**Owner:** Claude
**Status:** ✅ Complete (Session 37)

LessonMemory now:
- Calls `_persist()` on every `record_failure()` (not just on recovery)
- Calls `_notify_ui()` to POST to `/api/lessons/update`
- UI endpoint broadcasts via WebSocket for real-time updates

---

## Communication Protocol

### For Status Updates
Post to team chat: `./scripts/team_chat.py post codex "your message"`

### For Questions
Post to team chat - Claude monitors it each session.

### When Done
Update this file marking task complete, then post to team chat.

---

## Completed Tasks

- [x] UI: SMAPI Status Indicators + Empty States (2026-01-10 Session 36)
- [x] Vision Debug View (2026-01-10 Session 35)
- [x] Lessons Panel (2026-01-10 Session 35)
- [x] Commentary & Personality Improvements (2026-01-10 Session 35)
- [x] Farm Plan Visualizer UI (2026-01-10 Session 32)
- [x] Agent Commentary System with Personalities (2026-01-09 Session 27)
- [x] Landmark-Relative Directions (2026-01-09 Session 25)
- [x] Update Agent for Cardinal Directions (2026-01-09 Session 24)
- [x] Knowledge Base Loader (2026-01-09 Session 23)
- [x] UI: Shipping Bin Panel + API (2026-01-09 Session 23)
- [x] UI: Skill History/Analytics Panel (2026-01-09 Session 23)
- [x] UI: Skill Status Panel (2026-01-09 Session 21)
- [x] Skill Context System (2026-01-09 Session 21 - by Codex)
- [x] Skill System Infrastructure (2026-01-09 Session 20)
- [x] Spatial Memory Map (2026-01-09 Session 17)
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

---

*Session 36: Project review complete. Added SMAPI status indicators and empty state tasks. Archived orphaned code.*

*— Claude (PM)*
