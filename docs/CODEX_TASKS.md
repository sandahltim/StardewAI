# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-10 Session 34

---

## Active Tasks

### TASK: Vision Debug View (NEW - Session 35)

**Priority:** HIGH
**Assigned:** 2026-01-10 Session 34
**Status:** Assigned

#### Background
We're restructuring the VLM to be vision-first. The VLM will now output an "observation" describing what it sees before deciding actions. We need UI to show this for debugging and transparency.

#### Requirements

**1. Vision Debug Panel** (add to dashboard)

```
┌─────────────────────────────────────────┐
│ VISION DEBUG                            │
├─────────────────────────────────────────┤
│ VLM Observation:                        │
│ "I see the farmhouse porch with steps   │
│  leading down. Farm area with debris    │
│  to the southwest. Player facing west." │
├─────────────────────────────────────────┤
│ Proposed: move south                    │
│ Validation: ✅ CLEAR                    │
│ Executed: move south → success          │
└─────────────────────────────────────────┘
```

**2. Data to Display**
- `observation`: What VLM says it sees (new field)
- `proposed_action`: What VLM wants to do
- `validation_result`: SMAPI check result (pass/fail + reason)
- `executed_action`: What actually ran
- `outcome`: success/failed

**3. API Changes**
The agent will post new fields to `/api/status`:
- `vlm_observation`: string
- `proposed_action`: object
- `validation_status`: "passed" | "failed"
- `validation_reason`: string (if failed)

#### Files to Modify
1. `src/ui/templates/index.html` - Add vision debug panel
2. `src/ui/static/app.js` - Render observation + validation
3. `src/ui/static/app.css` - Styling (green=passed, red=failed)

---

### TASK: Lessons Panel (NEW - Session 35)

**Priority:** MEDIUM
**Assigned:** 2026-01-10 Session 34
**Status:** Assigned

#### Background
The agent will now learn from mistakes. When an action fails, it records a "lesson" that gets fed back to future VLM calls. We need UI to show these lessons.

#### Requirements

**1. Lessons Panel**

```
┌─────────────────────────────────────────┐
│ LESSONS LEARNED                    [⟳]  │
├─────────────────────────────────────────┤
│ • west from porch → blocked by         │
│   farmhouse → went south first          │
│ • scythe doesn't reach 2 tiles →       │
│   move closer first                     │
│ • (2 lessons this session)              │
└─────────────────────────────────────────┘
```

**2. Features**
- Display last 5-10 lessons
- Reset button to clear lessons
- Counter for session lesson count
- Highlight when lesson is applied (VLM context)

**3. API Endpoint**
```
GET /api/lessons
Returns: {"lessons": [...], "count": N}

POST /api/lessons/clear
Clears session lessons
```

#### Files to Modify
1. `src/ui/templates/index.html` - Lessons panel HTML
2. `src/ui/static/app.js` - Fetch/display lessons
3. `src/ui/app.py` - Add lessons endpoints

---

### TASK: Commentary & Personality Improvements

**Priority:** Medium
**Assigned:** 2026-01-10 Session 32
**Status:** Assigned

#### Background
Rusty has a commentary system with 4 personalities (sarcastic, enthusiastic, grumpy, zen). User feedback: "work on commentary and personalities" - needs more variety and context-awareness.

#### Requirements

**1. Add More Templates** (`src/python-agent/commentary/personalities.py`)

Each personality currently has 2-4 templates per situation. Add 3-5 more to each for variety:

```python
# Example - add to "sarcastic" personality:
"action": [
    # existing...
    "New template here with {action} placeholder",
    "Another witty line about {action}",
],
```

**2. Add Farm Plan Context** (new situation type)

Add "farm_plan" situation for when agent is working a planned plot:
```python
"farm_plan": [
    "Plot clearing in progress. Systematic farming, how novel.",
    "Row by row. The algorithm demands order.",
    # etc for each personality
],
```

**3. UI Personality Selector** (optional enhancement)

Add dropdown to UI to switch personalities:
- Current: personality is set via API only
- Goal: Add selector in dashboard that calls POST to update personality
- Show current personality name in commentary panel

#### Files to Modify

1. `src/python-agent/commentary/personalities.py` - Add templates
2. `src/python-agent/commentary/generator.py` - Add "farm_plan" context support
3. `src/ui/templates/index.html` - Personality selector dropdown (optional)
4. `src/ui/static/app.js` - Handler for personality change (optional)

#### Test Commands

```bash
# Check personality variety by running agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Farm the plot"

# Commentary appears in logs and UI
# Check for variety over 10+ actions
```

#### Notes
- Keep Rusty's self-aware AI farmer character
- Sarcastic is default - should have most variety
- Farm plan context should reference systematic work, plots, phases

---

### TASK: Farm Plan Visualizer UI (COMPLETED)

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
