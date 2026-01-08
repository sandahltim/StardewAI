# StardewAI Setup Guide

> **AI-Maintained Project** - This codebase is developed and maintained by AI agents.
> All changes should be documented in markdown for future AI sessions.

## Overview

StardewAI is an LLM-powered agent that plays Stardew Valley as a co-op partner or advisory helper.

### Architecture (v2 - Unified VLM)

```
┌─────────────────────────────────────────────────────────────┐
│                    Unified VLM Agent                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Screen    │ →  │  Qwen3-VL   │ →  │   Gamepad   │     │
│  │   Capture   │    │  (See+Plan) │    │  Controller │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         ↓                  ↓                  ↓              │
│    Split-screen       Single model       Virtual Xbox       │
│    crop (co-op)       inference          for Player 2       │
└─────────────────────────────────────────────────────────────┘
```

**Key Change from v1**: Single multimodal model handles both vision AND planning in one inference call, reducing latency from ~8s to ~2s.

## Prerequisites

- Python 3.12+
- NVIDIA GPU with 20+ GB VRAM (RTX 3090 Ti recommended)
- llama.cpp (using Gary's build at `/Gary/llama.cpp/`)
- Virtual environment with dependencies

## Installation

```bash
cd /home/tim/StardewAI
source venv/bin/activate

# Dependencies should already be installed:
# pip install httpx pillow mss pyautogui vgamepad pyyaml

# UI dependencies (if missing):
# pip install fastapi uvicorn jinja2
# TTS dependencies (optional):
# piper + aplay (ALSA)
```

## Models

Models are stored in `/home/tim/StardewAI/models/` (isolated from Gary):

| Model | File | Size | Use Case |
|-------|------|------|----------|
| Qwen3-VL-30B-A3B | `Qwen3VL-30B-A3B-Instruct-Q4_K_M.gguf` | 17.3 GB | Balanced (MoE, recommended) |
| Qwen3-VL-8B-Thinking | `Qwen3VL-8B-Thinking-F16.gguf` | 15.3 GB | Fast, smooth gameplay |
| Qwen3-VL-32B | `Qwen3VL-32B-Instruct-Q4_K_M.gguf` | 18.4 GB | Complex planning |
| Mistral-3.2-24B | `mistralai_Mistral-Small-3.2-24B-Instruct-2506-Q5_K_M.gguf` | 15.6 GB | General accuracy |

Each model has a corresponding `mmproj-*.gguf` vision encoder.

## Quick Start

### 1. Verify Gary is NOT Running

```bash
sudo systemctl status gary-llama.service
# Must show: inactive (dead)

# Or check directly:
pgrep -fa llama-server
# Should return nothing
```

### 2. Start LLaMA Server

```bash
cd /home/tim/StardewAI
./scripts/start-llama-server.sh Qwen3VL-30B-A3B
```

Wait for: `Server starting on http://127.0.0.1:8780`

Test with: `curl http://127.0.0.1:8780/health`

### 3. Run Agent

In a new terminal:

```bash
cd /home/tim/StardewAI
source venv/bin/activate

# Co-op mode (controls Player 2)
python src/python-agent/unified_agent.py --mode coop --goal "Help water the crops"

# Helper mode (advisory only)
python src/python-agent/unified_agent.py --mode helper --goal "Give farming advice"
```

### 4. Run UI (Agent Console)

```bash
source venv/bin/activate
uvicorn src.ui.app:app --reload --port 9001
```

Open `http://localhost:9001` for chat, goals, and tasks. See `docs/UI.md` for streaming and integration details.
When `ui.enabled` is true in `config/settings.yaml`, the unified agent streams Rusty snapshots and action plans into the UI.

## Configuration

Edit `config/settings.yaml`:

```yaml
server:
  url: "http://localhost:8780"
  model: "Qwen3VL-30B-A3B-Instruct-Q4_K_M"

mode:
  type: "coop"  # or "helper"
  coop_region:
    x_start: 0.5  # Right half of screen for Player 2

ui:
  enabled: true
  url: "http://localhost:9001"
```

## Modes

### Co-op Mode (`--mode coop`)
- Captures right half of screen (Player 2's view in split-screen)
- Executes actions via virtual Xbox controller
- Full autonomous gameplay

### Helper Mode (`--mode helper`)
- Captures full screen
- Analyzes and provides advice in logs
- No input execution (advisory only)

## Troubleshooting

### "Cannot connect to model server"
- Ensure llama-server is running on port 8780
- Check: `curl http://127.0.0.1:8780/health`

### GPU OOM
- Try smaller model (Qwen3VL-8B-Thinking)
- Reduce context: Edit startup script, change `-c 8192` to `-c 4096`
- Offload MoE experts to CPU: Uncomment `-ot '.ffn_.*_exps.=CPU'` in startup script

### "Gary's llama-server appears to be running"
- Stop Gary: `sudo systemctl stop gary-llama.service`
- Never run both simultaneously

## File Structure

```
/home/tim/StardewAI/
├── config/
│   └── settings.yaml          # Agent configuration
├── docs/
│   ├── SETUP.md              # This file
│   ├── ARCHITECTURE.md       # System design
│   └── SESSION_*.md          # Session notes
├── logs/
│   ├── agent.log             # Runtime logs
│   ├── screenshots/          # Captured screens
│   └── history/              # Action history
├── models/                    # Downloaded GGUF models
├── scripts/
│   ├── start-llama-server.sh # Server startup
│   └── download_models.py    # Model downloader
├── src/python-agent/
│   ├── agent.py              # Original dual-model (reference)
│   └── unified_agent.py      # Current unified VLM agent
└── venv/                      # Python virtual environment
```

## Isolation from Gary

**CRITICAL**: StardewAI is completely isolated from Gary:

| Aspect | Gary | StardewAI |
|--------|------|-----------|
| Port | 8034 | 8780 |
| Models | `/Gary/models/` | `/home/tim/StardewAI/models/` |
| Config | `/Gary/config/` | `/home/tim/StardewAI/config/` |
| Service | systemd managed | Manual scripts |

**Never modify files in `/Gary/`** - read-only access to llama.cpp binary only.

## Version History

- **v2.0** (2026-01-07): Unified VLM architecture, single model for vision+planning
- **v1.0** (2026-01-06): Dual model (Nemotron brain + Qwen3 VL eyes)

---
*Last updated: 2026-01-07 by AI Agent*
