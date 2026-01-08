# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StardewAI is an LLM-powered AI agent that plays Stardew Valley as a co-op partner. The system uses vision models to perceive the game screen and execute actions via virtual gamepad input.

## Quick Start Commands

```bash
# Activate environment
cd /home/tim/StardewAI
source venv/bin/activate

# Run agent (observe only - no input)
python src/python-agent/unified_agent.py --observe --goal "Help with farming"

# Run agent with gamepad control (Player 2 in co-op)
python src/python-agent/unified_agent.py --mode coop --goal "Water the crops"

# Run in helper mode (advisory only, no control)
python src/python-agent/unified_agent.py --mode helper --goal "Help with farming"

# Test vision only
python src/python-agent/test_vision.py
```

## Architecture

```
Screenshot → Unified VLM → Actions → Execution
                │                      │
                │                      └── vgamepad (virtual Xbox controller)
                │
                └── Qwen3 VL (llama.cpp @ localhost:8780)
                    - Perceives game screen
                    - Plans next actions
                    - Single inference call per tick
```

**Approach:** Single unified VLM (Qwen3 VL) handles both perception AND planning in one inference call. This is simpler and lower latency than the earlier dual-model design.

**Input Methods:**
- `gamepad` (default): Virtual Xbox 360 controller via vgamepad - used for co-op Player 2
- `keyboard`: WASD + pyautogui - fallback for single-player

## Key Files

| File | Purpose |
|------|---------|
| `src/python-agent/unified_agent.py` | Main agent - single VLM for perception + planning |
| `src/python-agent/agent.py` | Legacy dual-model agent (deprecated) |
| `config/settings.yaml` | Server URLs, timing, model selection |

## Server Configuration

The agent connects to a local llama-server instance:

```yaml
server_url: "http://localhost:8780"
model: "Qwen3VL-30B-A3B-Instruct-Q4_K_M"
```

**Important:** StardewAI uses port 8780 to avoid conflicts with other local services (Gary uses 8034, API uses 8765).

## GPU Configuration (CRITICAL)

**StardewAI and Gary CANNOT run simultaneously** - both use tensor-split across the same GPUs.

```
RTX 3090 Ti (24GB) + RTX 4070 (12GB) - tensor-split 20,4 (83%/17%)

StardewAI VRAM estimate (30B model):
- Model weights: ~18GB
- Vision encoder: ~1GB
- KV cache (4K): ~1GB
- Flash attention: ~1GB
- Overhead: ~500MB
Total: ~21.5GB (split across both GPUs)
```

**GPU UUIDs** (used in CUDA_VISIBLE_DEVICES):
```
3090 Ti: GPU-10495487-d4ed-4e22-9d9a-14f16b8ea0b3
4070:    GPU-fb1bf618-f91b-d2a8-f1e0-0161e11ece56
```

**Before running StardewAI:**
```bash
# Stop Gary's services
sudo systemctl stop llama-server gary

# Verify GPUs are free
nvidia-smi

# Start StardewAI llama-server
./scripts/start-llama-server.sh
```

**Crash Prevention (lessons from Gary):**
- Tensor-split required - single GPU = OOM with 30B model
- 4K context (not 8K) - saves ~1GB VRAM
- CUDA_VISIBLE_DEVICES with UUIDs for consistent GPU ordering
- Watch for XID 158 errors = frame buffer timeout = reboot needed

## Model Selection

Available models in `config/settings.yaml`:

```yaml
model: "Qwen3VL-30B-A3B-Instruct-Q4_K_M"  # Default: MoE, balanced
# model: "Qwen3VL-8B-Thinking-F16"        # Smooth gameplay, fast
# model: "Qwen3VL-32B-Instruct-Q4_K_M"    # Complex planning, slower
```

The earlier multi-tier escalation design (`docs/MODEL_TIERS.md`) is preserved for reference but not currently used.

## Co-op Mode Details

When running in co-op mode, the agent:
1. Captures only the right half of the screen (Player 2's view)
2. Uses virtual Xbox controller as Player 2 input
3. Stardew Valley must be in split-screen co-op mode

Controller mapping:
- A: Use tool / Confirm
- B: Cancel / Back
- X: Check / Interact
- Y: Inventory / Menu
- Left stick: Movement

## Development Team

**This project is developed by two AI agents with a human lead:**

| Role | Agent | Responsibilities |
|------|-------|------------------|
| **Project Manager** | Claude (Opus) | Agent logic, architecture, task assignment, coordination |
| **UI/Memory** | Codex | User interface, memory systems, state persistence |
| **Human Lead** | Tim | Direction, testing, hardware, final decisions |

## Team Communication Protocol

### Channels

| Channel | Purpose | How |
|---------|---------|-----|
| **Team Chat** | Real-time updates, quick questions, status | `http://localhost:9001/api/team` or `scripts/team_chat.py` |
| **Task Docs** | Formal task assignments, requirements | `docs/CODEX_TASKS.md`, `docs/CLAUDE_TASKS.md` |
| **Session Log** | Progress notes, decisions, blockers | `docs/SESSION_LOG.md` |
| **Plan Doc** | Sprint goals, architecture decisions | `docs/TEAM_PLAN.md` |

### For Claude (PM Responsibilities)

1. **Start of Session:**
   - Post to team chat: "Session started. Working on: [focus]"
   - Check `docs/CODEX_TASKS.md` for any completed items or blockers
   - Update `docs/TEAM_PLAN.md` if priorities changed

2. **Task Assignment to Codex:**
   - Update `docs/CODEX_TASKS.md` with clear requirements
   - Post to team chat: "New task assigned: [summary]"
   - Include: what's done, what's needed, test commands

3. **Status Updates:**
   - Post significant progress to team chat
   - Update `docs/SESSION_LOG.md` at end of session

4. **Document Format:**
   - Use markdown tables for structured data
   - Include code blocks with test commands
   - Mark priorities: High/Medium/Low
   - Include "Blocked by" if dependencies exist

### For Codex

1. **Check-in:**
   - Read `docs/CODEX_TASKS.md` for current assignments
   - Post to team chat when starting work

2. **Completion:**
   - Post to team chat: "Completed: [task]"
   - Note any issues or follow-up items

3. **Questions/Blockers:**
   - Post to team chat for quick questions
   - Update task doc with blocker details if significant

### Doc Locations

```
docs/
├── TEAM_PLAN.md       # Sprint goals, architecture (Claude maintains)
├── CODEX_TASKS.md     # Codex task queue (Claude assigns, Codex updates)
├── SESSION_LOG.md     # Progress log (both update)
├── NEXT_SESSION.md    # Handoff notes for next session
└── UI.md              # UI technical reference (Codex maintains)
```

### Team Chat CLI

```bash
# Post message
./scripts/team_chat.py post claude "message"
./scripts/team_chat.py post codex "message"
./scripts/team_chat.py post tim "message"

# Read recent
./scripts/team_chat.py read

# Watch live
./scripts/team_chat.py watch
```

## Development Notes

- **SMAPI GameBridge mod** (`src/smapi-mod/StardewAI.GameBridge/`) is implemented and provides HTTP API on port 8790
- **UI Server** runs on port 9001 with WebSocket support for real-time updates
- Screenshots are saved to `./logs/screenshots/` when `save_screenshots: true`
- Action execution has built-in delays (`action_delay`) to match game animation timing
- The agent runs in a tick-based loop with configurable `think_interval` (default 2s)

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| llama-server | 8780 | VLM inference (Qwen3VL) |
| SMAPI mod | 8790 | Game control API |
| UI Server | 9001 | Dashboard + Team Chat |
