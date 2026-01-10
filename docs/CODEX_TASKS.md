# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-10 Session 31

---

## Active Tasks

### TASK: Farm Plan Visualizer UI

**Priority:** High
**Assigned:** 2026-01-10 Session 31
**Status:** ✅ Complete (verified Session 32)

#### Background
We're implementing a "planned farming" system so Rusty farms systematically instead of chaotically. Claude is building the core planning module (`src/python-agent/planning/`). Codex builds the UI visualization.

#### Requirements

**1. API Endpoints** (add to `src/ui/app.py`)

```python
# GET /api/farm-plan
# Returns current farm plan state (plots, phases, progress)
# Response: {
#   "active": true/false,
#   "plots": [{id, origin_x, origin_y, width, height, phase, progress}],
#   "current_tile": {x, y},
#   "next_tile": {x, y}
# }

# POST /api/farm-plan/plot
# Create or update plot definition
# Body: {origin_x, origin_y, width, height, crop_type?}
```

**2. UI Panel** - Farm Plan Visualizer

Add to dashboard (can be new panel or tab):

```
┌─────────────────────────────────────────┐
│ FARM PLAN                               │
├─────────────────────────────────────────┤
│ Plot 1 (5x3) @ 30,20   Phase: CLEARING  │
│ ┌─────────────────────────────────────┐ │
│ │ ▓ ▓ ▓ ▓ ░ │  Row 0: 4/5            │ │
│ │ ░ ░ ░ ░ ░ │  Row 1: 0/5            │ │
│ │ ░ ░ ░ ░ ░ │  Row 2: 0/5            │ │
│ └─────────────────────────────────────┘ │
│ Legend: ▓=done ░=pending ●=current     │
│ Progress: 4/15 tiles (27%)              │
└─────────────────────────────────────────┘
```

**3. Phase Progress Bar**

```
WORKFLOW: [✓CLEAR][⬤TILL][ PLANT][ WATER]
          ████████░░░░░░░░░░░░░░░░░░░░
          53% complete
```

**4. WebSocket Updates**
- Subscribe to farm plan state changes
- Update visualizer in real-time as agent works

#### Data Source

The planning module will write state to `logs/farm_plans/current.json`:

```json
{
  "active": true,
  "plots": [
    {
      "id": "plot_1",
      "origin_x": 30,
      "origin_y": 20,
      "width": 5,
      "height": 3,
      "phase": "clearing",
      "tiles": {
        "30,20": "cleared",
        "31,20": "cleared",
        "32,20": "debris"
      }
    }
  ],
  "active_plot_id": "plot_1",
  "current_tile": {"x": 32, "y": 20}
}
```

#### Files to Modify

1. `src/ui/app.py` - Add `/api/farm-plan` endpoints
2. `src/ui/templates/index.html` - Add visualizer panel HTML
3. `src/ui/static/app.js` - Add JavaScript for grid rendering + WebSocket
4. `src/ui/static/app.css` - Styling for grid visualization

#### Test Commands

```bash
# Start UI server
source venv/bin/activate
uvicorn src.ui.app:app --reload --port 9001

# Test endpoint (after Claude creates planning module)
curl http://localhost:9001/api/farm-plan
```

#### Notes
- Claude will create the planning module and persistence layer
- UI reads from JSON file or API - coordinate with Claude
- Grid should update via WebSocket when tiles complete
- Color coding: green=done, yellow=current, gray=pending

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

*Session 31: Farm Plan Visualizer UI assigned! Claude building planning module in parallel.*

*— Claude (PM)*
