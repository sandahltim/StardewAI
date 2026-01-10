# Codebase Structure

## Root Directory

```
/home/tim/StardewAI/
├── CLAUDE.md              # Project instructions for Claude Code
├── AGENTS.md              # Repository guidelines and team info
├── README.md              # Project readme
├── config/                # Configuration files
├── docs/                  # Documentation
├── scripts/               # Operational scripts
├── src/                   # Source code
│   ├── python-agent/      # Python AI agent
│   ├── smapi-mod/         # C# Stardew Valley mod
│   ├── ui/                # Dashboard web UI
│   └── data/              # Data files and databases
├── models/                # GGUF model files (large, not in git)
├── logs/                  # Runtime logs (gitignored)
├── venv/                  # Python virtual environment
└── data/                  # Additional data files
```

## Source Code Detail

### Python Agent (`src/python-agent/`)

| File | Purpose |
|------|---------|
| `unified_agent.py` | **Main agent** - unified VLM for perception + planning |
| `agent.py` | Legacy dual-model agent (deprecated, reference only) |
| `test_vision.py` | Vision system test |
| `test_gamepad.py` | Virtual controller test |
| `controller_gui.py` | Manual controller GUI |
| `manual_controller.py` | Manual control helpers |

**Subdirectories:**
- `memory/` - Episodic memory, spatial maps, game knowledge retrieval
- `skills/` - Skill system (YAML definitions, loader, executor)
- `knowledge/` - Game knowledge database queries
- `commentary/` - TTS commentary generation (Rusty personality)

### SMAPI Mod (`src/smapi-mod/StardewAI.GameBridge/`)

| File | Purpose |
|------|---------|
| `ModEntry.cs` | SMAPI mod entry point |
| `HttpServer.cs` | HTTP API server (port 8790) |
| `GameStateReader.cs` | Read game state |
| `ActionExecutor.cs` | Execute game commands |
| `Models/GameState.cs` | Game state data model |
| `Models/ActionCommand.cs` | Action command model |
| `Pathfinding/TilePathfinder.cs` | A* pathfinding |

### UI (`src/ui/`)

| File | Purpose |
|------|---------|
| `app.py` | FastAPI application |
| `storage.py` | State storage |
| `client.py` | API client helpers |
| `templates/index.html` | Dashboard template |
| `static/app.js` | Frontend JavaScript |
| `static/app.css` | Styles |

## Configuration (`config/`)

- `settings.yaml` - All agent configuration (server URL, model, mode, timing, prompts)

## Documentation (`docs/`)

| File | Purpose |
|------|---------|
| `SETUP.md` | Installation and quick start |
| `ARCHITECTURE.md` | System design |
| `NEXT_SESSION.md` | **Handoff notes** - what was done, next steps |
| `SESSION_LOG.md` | Progress log |
| `TEAM_PLAN.md` | Sprint goals |
| `CODEX_TASKS.md` | Tasks for Codex agent |
| `UI.md` | UI technical reference |
| `SMAPI_MOD.md` | SMAPI mod documentation |
| `SKILL_ARCHITECTURE.md` | Skill system design |
| `MEMORY_ARCHITECTURE.md` | Memory system design |

## Scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `start-llama-server.sh` | Start llama.cpp server |
| `download_models.py` | Download GGUF models |
| `team_chat.py` | Team communication CLI |
| `test_perception.py` | Test perception pipeline |
| `build_game_knowledge_db.py` | Build knowledge database |
| `vcontroller_daemon.py` | Virtual controller daemon |
| `keyboard_daemon.py` | Keyboard input daemon |

## Key Entry Points

1. **Run agent**: `python src/python-agent/unified_agent.py`
2. **Start model server**: `./scripts/start-llama-server.sh`
3. **Start UI**: `uvicorn src.ui.app:app --port 9001`
4. **Build SMAPI mod**: `cd src/smapi-mod/StardewAI.GameBridge && dotnet build`
