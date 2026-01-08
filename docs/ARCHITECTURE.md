# StardewAI Architecture

## System Overview

StardewAI enables a local LLM to play Stardew Valley cooperatively with a human player. The system consists of three main layers:

1. **Game Layer** - SMAPI mod providing game state and action execution
2. **Agent Layer** - Python service orchestrating decisions and tasks
3. **LLM Layer** - Ollama instances for reasoning (Nemotron) and vision (Qwen3 VL)

## Data Flow

```
Game Loop (every ~1 second):
┌──────────────────────────────────────────────────────────────────┐
│ 1. SMAPI Mod collects game state                                 │
│    - AI player position, energy, health                          │
│    - Inventory contents                                          │
│    - Nearby objects, NPCs, interactables                         │
│    - Current time, weather, season                               │
│    - Active tasks/objectives                                     │
│                                                                  │
│ 2. Python Agent receives state via HTTP GET /state               │
│                                                                  │
│ 3. Agent formats state into prompt for Nemotron                  │
│    - Current situation summary                                   │
│    - Available actions                                           │
│    - Active task queue                                           │
│                                                                  │
│ 4. Nemotron returns decision (JSON)                              │
│    - Action type: move, use_tool, interact, wait                 │
│    - Parameters: direction, target, item                         │
│                                                                  │
│ 5. Agent sends action via HTTP POST /action                      │
│                                                                  │
│ 6. SMAPI Mod executes action in game                             │
└──────────────────────────────────────────────────────────────────┘
```

## Network Topology

```
┌─────────────────────────────────────────────┐
│           MAIN SERVER                       │
│  IP: localhost / 192.168.x.x                │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Stardew Valley + SMAPI              │   │
│  │   └── StardewAI.GameBridge.dll      │   │
│  │       HTTP Server :8765             │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Python Agent                         │   │
│  │   - Connects to SMAPI :8765         │   │
│  │   - Connects to local Ollama :11434 │   │
│  │   - Connects to vision server       │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Ollama (Nemotron 3 Nano)            │   │
│  │   HTTP :11434                        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
              │
              │ HTTP (vision requests)
              ▼
┌─────────────────────────────────────────────┐
│         VISION SERVER                       │
│  IP: 192.168.x.y                            │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Ollama (Qwen3 VL)                    │   │
│  │   HTTP :11434                        │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Component Responsibilities

### SMAPI Mod (GameBridge)

**Reads from game:**
- `Game1.player` - Position, energy, health, money
- `Game1.player.Items` - Inventory
- `Game1.currentLocation` - Map, objects, NPCs
- `Game1.timeOfDay` - In-game time
- `Game1.weatherIcon` - Weather conditions
- `Game1.currentSeason` - Season

**Writes to game:**
- Movement commands (pathfinding to tile)
- Tool usage (hoe, axe, pickaxe, watering can, etc.)
- Item interactions (plant, harvest, pick up)
- NPC interactions (talk, gift)
- Menu navigation (buy, sell, craft)

### Python Agent

**Core loop:**
```python
while game_running:
    state = get_game_state()           # HTTP GET to SMAPI mod

    if needs_vision_analysis(state):
        screen = capture_screen()
        context = query_qwen_vl(screen)
        state['vision_context'] = context

    decision = query_nemotron(state)   # Local Ollama

    execute_action(decision)           # HTTP POST to SMAPI mod

    sleep(tick_rate)
```

**Task Management:**
- Maintains task queue (user commands like "plant parsnips")
- Breaks high-level tasks into action sequences
- Tracks task progress and completion
- Handles interruptions (low energy, night time, etc.)

### LLM Usage Patterns

**Nemotron 3 Nano (fast, local):**
- Tick-by-tick decisions
- Simple navigation
- Tool selection
- Task step execution
- Response to immediate game events

**Qwen3 VL (vision, network):**
- Reading shop inventories
- Identifying unknown items
- Complex menu navigation
- Analyzing farm layout for planning
- Understanding quest text

## Message Formats

### Game State (SMAPI → Agent)

```json
{
  "tick": 12345,
  "player": {
    "name": "AIFarmer",
    "position": {"x": 64, "y": 15},
    "tile": {"x": 4, "y": 1},
    "energy": 200,
    "maxEnergy": 270,
    "health": 100,
    "money": 5000
  },
  "time": {
    "hour": 9,
    "minute": 30,
    "season": "spring",
    "day": 5,
    "year": 1
  },
  "weather": "sunny",
  "location": {
    "name": "Farm",
    "objects": [
      {"type": "parsnip", "tile": {"x": 5, "y": 2}, "state": "ready"},
      {"type": "stone", "tile": {"x": 6, "y": 3}}
    ],
    "npcs": [],
    "buildings": ["cabin", "greenhouse"]
  },
  "inventory": [
    {"slot": 0, "item": "hoe", "quantity": 1},
    {"slot": 1, "item": "parsnip_seeds", "quantity": 15}
  ],
  "currentTool": "hoe",
  "nearbyInteractables": [
    {"type": "crop", "tile": {"x": 5, "y": 2}, "action": "harvest"}
  ]
}
```

### Action Command (Agent → SMAPI)

```json
{
  "action": "move",
  "target": {"x": 5, "y": 2}
}
```

```json
{
  "action": "use_tool",
  "tool": "hoe",
  "direction": "down"
}
```

```json
{
  "action": "interact",
  "target": {"x": 5, "y": 2}
}
```

## Error Handling

| Error | Recovery |
|-------|----------|
| Path blocked | Recalculate route, try alternate path |
| Low energy | Return to bed, sleep |
| Inventory full | Store items in chest, drop low-value |
| Night time | Pathfind home before 2am |
| Tool missing | Check chests, buy from shop |
| Action failed | Retry with adjusted parameters |

## Performance Targets

- Game state poll: 1-2 Hz (not every frame)
- Nemotron response: <500ms
- Qwen3 VL response: <3s (used sparingly)
- Action execution: Immediate upon receipt
