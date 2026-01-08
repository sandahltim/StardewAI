# StardewAI - Meet Rusty, Your AI Co-op Partner

An AI farmhand that plays Stardew Valley co-op with you. Rusty sees the screen, makes decisions, and controls Player 2 - all while being delightfully sarcastic about virtual farm life.

## Project Status: Ready for Trials

**Last session:** 2026-01-07 - Unified VLM working, Rusty personality complete, ready for live testing.

### Quick Start
```bash
# Terminal 1: Start the model server
cd /home/tim/StardewAI
bash scripts/start-llama-server.sh

# Terminal 2: Start Rusty
source venv/bin/activate
python src/python-agent/unified_agent.py --observe --goal "Help with farming"
```

## Meet Rusty

Rusty is your AI co-op partner. He's helpful, occasionally sarcastic, and fully aware he's an AI playing a farming simulator.

**Sample Rusty quotes:**
- "Ah yes, watering virtual plants. Living the dream."
- "Player 1 is fishing again. Guess I'll do ALL the farming."
- "It's 11:30 PM and I'm exhausted. Player 1's still in the mines? Honestly, not surprised."

## Architecture (Unified VLM)

```
┌─────────────────────────────────────────────────────────────────┐
│                     YOUR GAMING PC                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Stardew Valley (Split-Screen Co-op)           │   │
│  │   [You - Player 1]              [Rusty - Player 2]      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│              Screen Capture (right half)                        │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Rusty (unified_agent.py)                    │   │
│  │   - Captures Player 2's screen                          │   │
│  │   - Sends to VLM for perception + planning              │   │
│  │   - Executes actions via virtual Xbox controller        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           llama-server (port 8780)                       │   │
│  │   Model: Qwen3-VL-30B-A3B (MoE)                         │   │
│  │   - Vision + Planning in ONE inference                  │   │
│  │   - ~1.1 second per decision cycle                      │   │
│  │   - Runs on RTX 3090 Ti                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Purpose |
|-----------|---------|
| `src/python-agent/unified_agent.py` | Rusty's brain - perception, planning, execution |
| `config/settings.yaml` | Rusty's personality, game knowledge, settings |
| `scripts/start-llama-server.sh` | Model server startup |
| `models/` | Downloaded GGUF models (~70GB) |

## Available Models

| Model | Speed | Best For |
|-------|-------|----------|
| **Qwen3VL-30B-A3B** | 139 tok/s | Default - fast + smart |
| Qwen3VL-8B-Thinking | 42 tok/s | Debugging (shows reasoning) |
| Qwen3VL-32B | 30 tok/s | Complex planning |
| Mistral-Small-3.2-24B | 39 tok/s | Backup |

## Modes

### Co-op Mode (default)
- Rusty controls Player 2 via virtual Xbox controller
- Captures right half of split-screen
- Full autonomous gameplay

### Helper Mode
- Rusty watches but doesn't control
- Provides advice in logs
- Good for testing/debugging

```bash
# Co-op mode (with controller)
python src/python-agent/unified_agent.py --mode coop --goal "Water the crops"

# Helper mode (observe only)
python src/python-agent/unified_agent.py --mode helper --goal "Help with farming"

# Observe mode (like helper, explicit flag)
python src/python-agent/unified_agent.py --observe --goal "Help with farming"
```

## What Rusty Knows

- **Time**: Day runs 6AM-2AM, pass out = bad
- **Energy**: Track and manage, eat food to restore
- **Farming**: Hoe → Plant → Water → Harvest
- **Weather**: Rainy = no watering needed
- **Mining**: Elevator every 5 floors, bring food
- **Social**: Gifts, birthdays, friendship

## Quick Links

- [Session Notes](docs/SESSION_2026-01-07.md) - Latest progress
- [Architecture Details](docs/ARCHITECTURE.md)
- [Setup Guide](docs/SETUP.md)
- [Model Tiers](docs/MODEL_TIERS.md)
- [Roadmap](docs/ROADMAP.md)

---
*Rusty: "I'm an AI playing a farming game. This is fine."*
