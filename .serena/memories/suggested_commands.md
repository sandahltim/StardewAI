# Suggested Commands

## Environment Setup

```bash
# Activate Python environment (ALWAYS do this first!)
cd /home/tim/StardewAI
source venv/bin/activate
```

## Running the Agent

```bash
# Co-op mode (controls Player 2)
python src/python-agent/unified_agent.py --mode coop --goal "Help water the crops"

# Helper mode (advisory only, no control)
python src/python-agent/unified_agent.py --mode helper --goal "Give farming advice"

# With UI enabled
python src/python-agent/unified_agent.py --ui --goal "Farm autonomously"

# Observe only (no input execution)
python src/python-agent/unified_agent.py --observe --goal "Watch the game"
```

## Model Server

```bash
# Start llama-server (MUST stop Gary first!)
./scripts/start-llama-server.sh Qwen3VL-30B-A3B

# Check health
curl http://localhost:8780/health
```

## UI Server

```bash
# Start dashboard
uvicorn src.ui.app:app --reload --port 9001

# Access at http://localhost:9001
```

## SMAPI Mod

```bash
# Check SMAPI mod API
curl http://localhost:8790/health

# Get game state
curl http://localhost:8790/state
```

## Testing

```bash
# Test vision capture
python src/python-agent/test_vision.py

# Test gamepad
python src/python-agent/test_gamepad.py

# Test perception pipeline
python scripts/test_perception.py
```

## Git Operations

```bash
# Standard git workflow
git status
git add <files>
git commit -m "description"

# Never push without explicit approval from Tim
```

## GPU Monitoring

```bash
# Check GPU memory usage
nvidia-smi

# Watch GPU usage
watch -n 1 nvidia-smi
```

## SMAPI Mod Build (C#)

```bash
cd src/smapi-mod/StardewAI.GameBridge
dotnet build

# Deploy to Stardew Valley Mods folder
dotnet build -c Release
```

## Team Communication

```bash
# Post to team chat
./scripts/team_chat.py post claude "message"
./scripts/team_chat.py post codex "message"

# Read recent messages
./scripts/team_chat.py read

# Watch live
./scripts/team_chat.py watch
```
