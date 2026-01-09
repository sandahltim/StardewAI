# Repository UI Guide

## Overview
The StardewAI UI is a lightweight FastAPI app that provides a chat console, goal editor, and task queue. All data is stored on disk so long-term goals and memory survive restarts.

## Run the UI
```bash
source venv/bin/activate
uvicorn src.ui.app:app --reload --port 9001
```
Open `http://localhost:9001`.

## Storage
- SQLite DB: `logs/ui/agent_ui.db`
- Status file: `logs/ui/status.json`

## Streaming Updates (WebSocket)
The UI connects to `/ws` for live updates. Whenever the backend receives new messages, task updates, goals, or status changes, it broadcasts an event to connected clients.

Event types:
- `message_created`, `message_updated`
- `task_created`, `task_updated`
- `goal_updated`
- `status_updated`
- `session_event_created`

The UI uses `status_updated` to populate the Rusty Snapshot panel with:
- `location`, `time_of_day`, `weather`, `energy`, `holding`, `mood`, `menu_open`, `nearby`
- `action_plan` (list of short action strings)
- `last_tick` (shown as the snapshot timestamp)
- `vlm_status` (Idle/Thinking/Executing), `last_reasoning`, `last_actions`
- `vlm_parse_success`, `vlm_parse_fail`, `vlm_errors` (JSON parse debug)
- `session_started_at`, `think_count`, `action_count`, `action_fail_count`, `latency_history`
- `action_type_counts`, `distance_traveled`, `crops_watered_count`, `crops_harvested_count`
- `player_tile_x`, `player_tile_y`
- `current_instruction`, `navigation_target`, `navigation_blocked`, `navigation_attempts`

## Text-to-Speech (Piper)
TTS runs on the UI machine. The UI can auto-speak agent replies when enabled, or you can click the “Speak” button on any agent message.

Requirements:
- `piper` installed and available on `PATH` (override with `PIPER_CMD`)
- `aplay` installed (override with `APLAYER_CMD`)
- Voice model in `models/tts/` (default: `en_US-amy-medium.onnx` + `en_US-amy-medium.onnx.json`)

API:
- `POST /api/tts` with `{ "message_id": 123 }` or `{ "text": "hello" }`

Caching:
- Audio is cached in `logs/ui/tts/cache` by voice + text hash to avoid re-synthesis.
- The most recent audio is also copied to `logs/ui/tts/latest.wav`.

## Agent Integration Points
If you wire the agent to the UI, these endpoints are the minimal surface:

- `POST /api/messages`: Store a user/agent message.
- `POST /api/messages/stream`: Create or append to a message while streaming reasoning.
- `GET /api/goals`: Read the active goal.
- `GET /api/tasks`: Read the task queue.
- `POST /api/status`: Update agent runtime state.
- `GET /api/messages`: Read user + agent chat history (used for prompt context).
- `GET /api/spatial-map`: Read spatial memory tiles (filters supported).
- `POST /api/spatial-map`: Update spatial memory tiles.
- `POST /api/confirm`: Grant one-time execution permission when confirm-before-execute is enabled.
- `POST /api/action/pending`: Set the next action for approval (`pending_action` fields in status).
- `POST /api/action/clear`: Clear pending action + reset confirmation.
- `POST /api/session-memory`: Store session events (positions, actions, tool use).
- `GET /api/session-memory`: Read session events (filter by `event_type`).
- `GET /api/game-knowledge?type=npc&name=Shane`: Query game knowledge.
- `GET /api/episodic-memories?limit=10`: Read recent episodic memories (optional `query`).

## Agent Helper Client
`src/ui/client.py` provides a thin HTTP client for agents:

```python
from ui.client import UIClient

ui = UIClient("http://localhost:9001")
message = ui.stream_message(None, role="agent", content="Starting...", append=True)
ui.stream_message(message["id"], content=" done.", append=True)
ui.set_pending_action("Move left for 1s", action_id="move-1")
```

## Co-op Safety Toggle
The UI offers **Free mode** (no confirmation) and **Confirm mode**. The state is stored in `status.json` under `confirm_before_execute`.

When confirmation is enabled, the agent should:
1) set `pending_action` via `POST /api/action/pending`
2) wait for `confirm_granted`
3) execute once, then reset `confirm_granted` to false via `POST /api/status`

The UI shows the pending action and provides Approve/Clear controls.

## UI Interaction Upgrades
- Quick Control Bar: change mode, goal, and safety without leaving the chat pane.
- Next Action Preview: banner with approve/deny to mirror pending action state.
- Inline Task Editing: edit title, priority, and structured fields directly in the list.

## Team Chat (New!)

Team communication channel for Claude, Codex, and Tim.

### Backend (Complete)
- Table: `team_messages` (id, sender, content, created_at)
- `GET /api/team?limit=100&since_id=5` - Read messages
- `POST /api/team` with `{"sender": "claude", "content": "..."}` - Post message
- WebSocket event: `team_message_created`

### CLI Tool
```bash
# Post a message
./scripts/team_chat.py post claude "Starting VLM integration"
./scripts/team_chat.py post tim "Game is running"

# Read messages
./scripts/team_chat.py read

# Watch live (polls every 2s)
./scripts/team_chat.py watch
```

### Frontend (TODO - Codex)
Suggested implementation:
- Add "Team Chat" panel/tab to UI
- Show messages with sender badges (color-coded: Claude=purple, Codex=blue, Tim=green)
- Input field with sender dropdown
- Auto-scroll on new messages
- Connect to WebSocket `team_message_created` event

## Chat Feed UX

- Agent conversation feed shows the most recent 10 messages.
- Newest messages appear at the top.
- Send box sits above the feed (under the quick selectors).
- User messages are injected into the VLM prompt; agent replies are posted back to the same chat.

## Movement History

- VLM dashboard shows last 10 positions, stuck indicator, and a direction trail.
- Data is sourced from session memory events (`event_type=position`).

## Directional Compass

- Compass widget polls `http://<ui-host>:8790/surroundings` and shows clear/blocked tiles per direction.
- Green = clear (tile count), red = blocked (tiles until blocked).

## Tile State

- Tile State card reads `currentTile` from `/surroundings` and shows clear/tilled/planted/watered/debris.
- Progress bar highlights farming workflow: CLEAR → TILL → PLANT → WATER → DONE.

## Watering Can

- Watering can panel reads `player.wateringCanWater` and `player.wateringCanMax` from `/state`.
- Shows remaining water with a warning when low or empty.

## Water Source

- Water source indicator reads `nearestWater.direction` and `nearestWater.distance` from `/surroundings`.
- Highlights when watering can is low or empty.

## Shipping Bin

- Shipping bin indicator reads `location.shippingBin.x/y` from `/state`.
- Shows direction/distance when on Farm and inventory has sellable items.

## Crop Growth

- Crop progress aggregates `location.crops[].daysUntilHarvest` from `/state`.
- Shows counts by days remaining and ready crops.

## Crop Countdown

- Countdown list groups `location.crops[]` by crop name and days until harvest.
- Shows the soonest-ready crops at a glance.

## Bedtime Indicator

- Shows current time and suggests when to sleep based on late hours or low energy.

## Day/Season Progress

- Displays day-of-season progress with a simple progress bar.

## Goal Progress Checklist

- Uses `/api/tasks` to show a small checklist with done/total progress.

## Spatial Memory Map

- JSON tile map per location stored in `logs/spatial_map/`.
- `GET /api/spatial-map?location=Farm&state=tilled&not_planted=true` returns tiles that need planting.
- `POST /api/spatial-map` updates tiles with `{ location, tiles }`.

## Crop Status

- Watered summary uses `location.crops[].isWatered` from `/state`.
- Displays `WATERED: x/y` with color cues for unwatered crops.

## Harvest Ready

- Harvest indicator uses `location.crops[].isReadyForHarvest`.
- When none are ready, shows the soonest `daysUntilHarvest`.

## Inventory Panel

- Toolbar inventory grid reads `inventory[]` and `player.currentToolIndex` from `/state`.
- Highlights selected slot and shows item name + stack size.

## Action Result Log

- Action results list reads `/api/session-memory?event_type=action`.
- Displays recent action success/fail outcomes for debugging.

## Action History

- Action history panel shows the last 10 actions (from session memory).
- Highlights repeats and prefixes failed actions with `BLOCKED`.

## Action Repeat Detection

- Repeats alert uses recent action events to flag 3+ identical actions in a row.

## Current Instruction

- Instruction callout shows the latest spatial instruction from agent status.

## Navigation Intent

- Navigation intent card shows the active instruction target, last blocked direction, and movement attempts.

## VLM Error Display

- Error panel reports VLM JSON parse failures with last raw response (truncated) and success/fail counters.

## Latency Graph

- Latency graph shows recent VLM response times (`latency_history`) with avg/max stats.

## Session Stats

- Session stats show uptime, think/action counts, distance traveled, and crop water/harvest counts.
- Action type breakdown lists the most frequent action types this session.

## Location + Position

- Location card uses `/state` `location.name` and `player.tileX/tileY`.

## Energy/Stamina

- Energy bar reads `player.stamina` and `player.maxStamina` from `/state`.

## Session Timeline

- Collapsible list of the most recent session events (positions/actions/tool use).

## Memory Viewer

- Shows recent episodic memories (ChromaDB) and game knowledge lookups.
- Search uses `/api/episodic-memories?query=...`.

### Valid Senders
- `claude` - Claude (Opus) - Agent/architecture
- `codex` - Codex - UI/memory
- `tim` - Tim - Human lead

## Dependencies
Add these packages to the environment if they are missing:
- `fastapi`
- `uvicorn`
- `jinja2`
