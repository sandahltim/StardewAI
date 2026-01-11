# StardewAI Python Agent

## Purpose
AI agent (Rusty) that plays Stardew Valley autonomously using VLM perception + SMAPI mod API for game control.

## Tech Stack
- Python 3.x
- Qwen3 VL (llama.cpp @ localhost:8780) for perception
- SMAPI GameBridge mod (localhost:8790) for game control
- Skill-based action system (55 skills)

## Architecture
```
Screenshot → VLM (Qwen3VL) → Daily Planner → Task Executor → Skill Executor → SMAPI API
```

## Key Components
- `unified_agent.py`: Main agent loop
- `execution/task_executor.py`: Task state machine
- `execution/target_generator.py`: Spatial target sorting
- `memory/daily_planner.py`: Day planning
- `skills/`: Skill definitions (YAML) and executor
- `planning/farm_surveyor.py`: Cell-by-cell farming survey
- `execution/cell_coordinator.py`: Cell farming orchestration

## Ports
- 8780: llama-server (VLM)
- 8790: SMAPI mod API
- 9001: UI server
