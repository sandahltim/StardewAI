# SMAPI Mod Specification: GameBridge

## Overview

The GameBridge mod provides an HTTP API for external programs to read game state and execute actions. It runs an embedded HTTP server within the Stardew Valley process.

## Technical Requirements

- .NET 6.0 (Stardew Valley 1.6+)
- SMAPI 4.0+
- Embedded HTTP server (System.Net.HttpListener or similar)

## Project Structure

```
src/smapi-mod/
├── StardewAI.GameBridge/
│   ├── StardewAI.GameBridge.csproj
│   ├── manifest.json
│   ├── ModEntry.cs              # SMAPI entry point
│   ├── HttpServer.cs            # HTTP server implementation
│   ├── GameStateReader.cs       # Reads game state
│   ├── ActionExecutor.cs        # Executes game actions
│   ├── Models/
│   │   ├── GameState.cs
│   │   ├── PlayerState.cs
│   │   ├── ActionCommand.cs
│   │   └── ActionResult.cs
│   └── Pathfinding/
│       └── TilePathfinder.cs    # A* pathfinding for movement
└── README.md
```

## manifest.json

```json
{
  "Name": "StardewAI GameBridge",
  "Author": "tim",
  "Version": "0.1.0",
  "Description": "HTTP API for AI agent control",
  "UniqueID": "tim.StardewAI.GameBridge",
  "EntryDll": "StardewAI.GameBridge.dll",
  "MinimumApiVersion": "4.0.0",
  "Dependencies": []
}
```

## HTTP API Endpoints

### GET /state

Returns current game state.

**Response:**
```json
{
  "success": true,
  "data": {
    "tick": 12345,
    "player": { ... },
    "time": { ... },
    "location": { ... },
    "inventory": [ ... ]
  }
}
```

### POST /action

Execute an action in the game.

**Request:**
```json
{
  "action": "move",
  "target": {"x": 10, "y": 15}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Moving to tile (10, 15)"
}
```

### GET /health

Server health check.

**Response:**
```json
{
  "status": "ok",
  "gameRunning": true,
  "playerInGame": true
}
```

## Supported Actions

### Movement

```json
{"action": "move", "target": {"x": 10, "y": 15}}
```
- Uses A* pathfinding to navigate to target tile
- Handles obstacles automatically
- Returns error if path not found

```json
{"action": "move_direction", "direction": "up", "tiles": 1}
```
- Move in cardinal direction (up/down/left/right)
- Simple movement without pathfinding

### Tools

```json
{"action": "use_tool", "direction": "down"}
```
- Uses currently equipped tool
- Direction: up, down, left, right

```json
{"action": "equip_tool", "tool": "hoe"}
```
- Switches to specified tool
- Tool names: hoe, pickaxe, axe, wateringCan, fishingRod, scythe

### Inventory

```json
{"action": "select_slot", "slot": 0}
```
- Select inventory slot (0-11 for toolbar)

```json
{"action": "use_item", "direction": "down"}
```
- Use held item (plant seed, place object)

### Interaction

```json
{"action": "interact", "target": {"x": 5, "y": 3}}
```
- Interact with object/NPC at tile
- Harvests crops, talks to NPCs, opens doors

```json
{"action": "interact_facing"}
```
- Interact with whatever player is facing

### Farming

```json
{"action": "plant", "seed": "parsnip_seeds", "tile": {"x": 5, "y": 3}}
```
- High-level: move to tile, equip seeds, plant

```json
{"action": "water", "tile": {"x": 5, "y": 3}}
```
- High-level: move to tile, equip can, water

```json
{"action": "harvest", "tile": {"x": 5, "y": 3}}
```
- High-level: move to tile, interact

### System

```json
{"action": "wait", "ticks": 60}
```
- Do nothing for N game ticks

```json
{"action": "sleep"}
```
- Go to bed (will pathfind to bed)

## Game State Details

### Player State

```csharp
public class PlayerState
{
    public string Name { get; set; }
    public Point Position { get; set; }      // Pixel position
    public Point Tile { get; set; }          // Tile position
    public int FacingDirection { get; set; } // 0=up, 1=right, 2=down, 3=left
    public int Energy { get; set; }
    public int MaxEnergy { get; set; }
    public int Health { get; set; }
    public int MaxHealth { get; set; }
    public int Money { get; set; }
    public string CurrentTool { get; set; }
    public bool IsMoving { get; set; }
    public bool CanMove { get; set; }
}
```

### Location State

```csharp
public class LocationState
{
    public string Name { get; set; }
    public List<GameObject> Objects { get; set; }
    public List<NpcInfo> Npcs { get; set; }
    public List<TerrainFeature> TerrainFeatures { get; set; }
    public int[,] Passability { get; set; }  // Pathfinding grid
}
```

### Time State

```csharp
public class TimeState
{
    public int Hour { get; set; }        // 6-26 (2am)
    public int Minute { get; set; }      // 0, 10, 20, 30, 40, 50
    public string Season { get; set; }   // spring, summer, fall, winter
    public int Day { get; set; }         // 1-28
    public int Year { get; set; }
    public string Weather { get; set; }  // sunny, rainy, stormy, snowy
}
```

## Implementation Notes

### Thread Safety

The HTTP server runs on a separate thread. Game state must be read on the main game thread via SMAPI's `UpdateTicked` event. Use a thread-safe queue for actions.

```csharp
// Collect state on game thread
private void OnUpdateTicked(object sender, UpdateTickedEventArgs e)
{
    if (e.IsMultipleOf(15)) // Every 250ms at 60fps
    {
        _cachedState = GameStateReader.ReadState();
    }

    // Process queued actions
    while (_actionQueue.TryDequeue(out var action))
    {
        ActionExecutor.Execute(action);
    }
}
```

### Pathfinding

Use A* algorithm with game's passability data:

```csharp
public List<Point> FindPath(Point start, Point end, GameLocation location)
{
    // Check location.isTilePassable() for each tile
    // Account for NPCs, objects, buildings
    // Return list of tiles to traverse
}
```

### Action Execution

Actions may span multiple frames (pathfinding, animations). Track action state:

```csharp
public enum ActionState
{
    Idle,
    MovingToTarget,
    PerformingAction,
    WaitingForAnimation,
    Complete,
    Failed
}
```

## Configuration

`config.json`:
```json
{
  "HttpPort": 8790,
  "StateUpdateIntervalMs": 250,
  "EnableLogging": true,
  "AllowRemoteConnections": false
}
```

## References

- [SMAPI Modder Guide](https://stardewvalleywiki.com/Modding:Modder_Guide/APIs)
- [SMAPI Events](https://stardewvalleywiki.com/Modding:Modder_Guide/APIs/Events)
- [SMAPIDedicatedServerMod](https://github.com/ObjectManagerManager/SMAPIDedicatedServerMod) - Bot automation patterns
