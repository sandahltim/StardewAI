# StardewAI Project Overview

## Purpose
StardewAI is an LLM-powered AI agent that plays Stardew Valley as a co-op partner. The system uses vision-language models (VLM) to perceive the game screen and execute actions via virtual gamepad or SMAPI mod API.

## Tech Stack

### Python Agent (Primary)
- **Python 3.12+** with virtual environment
- **Qwen3-VL** vision-language models via llama.cpp (localhost:8780)
- **httpx** for HTTP client
- **mss** for screen capture
- **vgamepad** for virtual Xbox 360 controller input
- **PIL/Pillow** for image processing
- **pyyaml** for configuration
- **chromadb** for vector storage (game knowledge)
- **sqlite3** for structured game data

### SMAPI Mod (C#)
- **.NET 6.0** targeting Stardew Valley's modding API
- HTTP server on port 8790 for game state + action execution
- Pathfinding, game state reading, action commands

### UI Server
- **FastAPI + Uvicorn** on port 9001
- **WebSocket** for real-time updates
- **Jinja2** templates for dashboard

## Architecture

```
Screenshot → Unified VLM → Actions → Execution
                │                      │
                │                      └── SMAPI Mod API (primary)
                │                          or vgamepad (fallback)
                │
                └── Qwen3 VL (llama.cpp @ localhost:8780)
                    - Perceives game screen
                    - Plans next actions
                    - Single inference call per tick
```

## Operating Modes

1. **Co-op Mode** (`--mode coop`): Controls Player 2 in split-screen, captures right half
2. **Helper Mode** (`--mode helper`): Advisory only, no input execution
3. **Single Mode** (`--mode single`): Controls main character

## Key Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| llama-server | 8780 | VLM inference (Qwen3VL) |
| SMAPI mod | 8790 | Game control API |
| UI Server | 9001 | Dashboard + Team Chat |

## Team Structure

- **Claude (Opus)**: Project Manager - architecture, task assignment
- **Codex**: UI/Memory - user interface, state persistence
- **Tim (Human)**: Lead - direction, testing, hardware
