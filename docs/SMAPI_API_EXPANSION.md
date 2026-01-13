# SMAPI API Reference

**Last Updated:** 2026-01-12 Session 83
**Status:** ✅ All endpoints implemented
**Base URL:** `http://localhost:8790`

---

## Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/state` | GET | Full game state |
| `/surroundings` | GET | 4 adjacent tiles |
| `/farm` | GET | Farm-wide data |
| `/action` | POST | Execute actions |
| `/check-path` | GET | A* pathfinding |
| `/passable` | GET | Tile passability |
| `/passable-area` | GET | Area passability scan |
| `/skills` | GET | Player skill levels |
| `/npcs` | GET | NPC locations/friendship |
| `/animals` | GET | Farm animals |
| `/machines` | GET | Artisan equipment |
| `/calendar` | GET | Events/festivals |
| `/fishing` | GET | Fishing data |
| `/mining` | GET | Mine floor data |
| `/storage` | GET | Chest contents |

---

## Endpoint Details

### `/health` - Health Check

```bash
curl http://localhost:8790/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "gameRunning": true,
    "playerInGame": true,
    "modVersion": "0.1.0"
  }
}
```

---

### `/state` - Full Game State

Complete snapshot of player, time, location, and inventory.

```bash
curl http://localhost:8790/state
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tick": 12345,
    "player": {
      "name": "Rusty",
      "tileX": 64, "tileY": 15,
      "facing": "south",
      "energy": 270, "maxEnergy": 270,
      "health": 100, "maxHealth": 100,
      "money": 500,
      "currentTool": "Hoe",
      "wateringCanWater": 40, "wateringCanMax": 40
    },
    "time": {
      "hour": 6, "minute": 0,
      "timeString": "6:00 AM",
      "season": "spring", "day": 1, "year": 1,
      "weather": "sunny"
    },
    "location": {
      "name": "Farm",
      "isOutdoors": true,
      "isFarm": true
    },
    "inventory": [
      {"slot": 0, "name": "Hoe", "type": "tool", "stack": 1}
    ]
  }
}
```

---

### `/check-path` - A* Pathfinding

Check if a path exists between two points.

```bash
curl "http://localhost:8790/check-path?startX=64&startY=15&endX=32&endY=17"
```

**Parameters:**
- `startX`, `startY`: Starting tile coordinates
- `endX`, `endY`: Destination tile coordinates

**Response:**
```json
{
  "success": true,
  "data": {
    "reachable": true,
    "pathLength": 35,
    "path": [
      {"x": 64, "y": 15},
      {"x": 63, "y": 15},
      ...
    ]
  }
}
```

---

### `/passable` - Single Tile Check

Check if a single tile is passable.

```bash
curl "http://localhost:8790/passable?x=32&y=17"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "x": 32, "y": 17,
    "passable": true,
    "blocker": null
  }
}
```

**Blocker values:** `null`, `"wall"`, `"water"`, `"map_edge"`, `"Tree"`, `"Stone"`, object names

---

### `/passable-area` - Area Scan

Check passability for an area around a center point.

```bash
curl "http://localhost:8790/passable-area?centerX=42&centerY=19&radius=10"
```

**Parameters:**
- `centerX`, `centerY`: Center tile coordinates
- `radius`: Scan radius (max 25)

**Response:**
```json
{
  "success": true,
  "data": {
    "centerX": 42, "centerY": 19, "radius": 10,
    "tiles": [
      {"x": 32, "y": 9, "passable": true, "blocker": null},
      {"x": 33, "y": 9, "passable": false, "blocker": "Stone"},
      ...
    ]
  }
}
```

---

### `/skills` - Player Skills

Get all skill levels, XP, and professions.

```bash
curl http://localhost:8790/skills
```

**Response:**
```json
{
  "success": true,
  "data": {
    "farming": {
      "level": 4,
      "xp": 1350,
      "xpToNextLevel": 800,
      "profession5": "Tiller",
      "profession10": null
    },
    "fishing": {"level": 2, "xp": 200, ...},
    "foraging": {"level": 3, "xp": 450, ...},
    "mining": {"level": 1, "xp": 80, ...},
    "combat": {"level": 0, "xp": 0, ...},
    "luck": {"level": 0, "xp": 0, ...}
  }
}
```

**Professions:**
- Farming 5: Rancher / Tiller
- Farming 10: Coopmaster / Shepherd / Artisan / Agriculturist
- (Similar for other skills)

---

### `/npcs` - NPC Data

Get all NPCs with locations and friendship.

```bash
curl http://localhost:8790/npcs
```

**Response:**
```json
{
  "success": true,
  "data": {
    "npcs": [
      {
        "name": "Pierre",
        "displayName": "Pierre",
        "location": "SeedShop",
        "tileX": 4, "tileY": 17,
        "isVillager": true,
        "canSocialize": true,
        "friendshipPoints": 250,
        "friendshipHearts": 1,
        "canDate": false,
        "isDating": false,
        "isMarried": false,
        "birthdaySeason": "spring",
        "birthdayDay": 26,
        "isBirthdayToday": false,
        "giftedToday": false,
        "giftsThisWeek": 0
      }
    ]
  }
}
```

---

### `/animals` - Farm Animals

Get all farm animals and buildings.

```bash
curl http://localhost:8790/animals
```

**Response:**
```json
{
  "success": true,
  "data": {
    "animals": [
      {
        "id": 12345,
        "name": "Bessie",
        "type": "Cow",
        "buildingName": "Barn",
        "tileX": 45, "tileY": 20,
        "isOutside": true,
        "happiness": 200,
        "friendship": 800,
        "wasPetToday": true,
        "producedToday": true,
        "currentProduct": "Milk",
        "age": 14
      }
    ],
    "buildings": [
      {
        "type": "Barn",
        "name": "Barn",
        "tileX": 40, "tileY": 18,
        "animalCount": 2,
        "maxAnimals": 4,
        "doorOpen": true
      }
    ]
  }
}
```

---

### `/machines` - Artisan Equipment

Get all processing machines and their status.

```bash
curl http://localhost:8790/machines
```

**Response:**
```json
{
  "success": true,
  "data": {
    "machines": [
      {
        "name": "Keg",
        "location": "Farm",
        "tileX": 45, "tileY": 20,
        "isProcessing": true,
        "inputItem": "Ancient Fruit",
        "outputItem": "Wine",
        "minutesUntilReady": 4320,
        "readyForHarvest": false,
        "needsInput": false
      },
      {
        "name": "Preserves Jar",
        "location": "Farm",
        "tileX": 46, "tileY": 20,
        "isProcessing": false,
        "readyForHarvest": true,
        "needsInput": false
      }
    ]
  }
}
```

**Tracked machines:** Keg, Preserves Jar, Cheese Press, Mayonnaise Machine, Loom, Oil Maker, Seed Maker, Crystalarium, Recycling Machine, Furnace, Charcoal Kiln, Cask, Dehydrator, Fish Smoker, Bait Maker, and more.

---

### `/calendar` - Events & Festivals

Get calendar information and upcoming events.

```bash
curl http://localhost:8790/calendar
```

**Response:**
```json
{
  "success": true,
  "data": {
    "season": "spring",
    "day": 9,
    "year": 1,
    "dayOfWeek": "Tue",
    "daysUntilSeasonEnd": 19,
    "todayEvent": null,
    "upcomingEvents": [
      {"day": 13, "season": "spring", "name": "Egg Festival", "type": "festival"},
      {"day": 24, "season": "spring", "name": "Flower Dance", "type": "festival"}
    ],
    "upcomingBirthdays": [
      {"day": 14, "season": "spring", "name": "Haley", "type": "birthday"},
      {"day": 26, "season": "spring", "name": "Pierre", "type": "birthday"}
    ]
  }
}
```

---

### `/fishing` - Fishing Data

Get fishing information for current location.

```bash
curl http://localhost:8790/fishing
```

**Response:**
```json
{
  "success": true,
  "data": {
    "location": "Beach",
    "weather": "Sunny",
    "season": "spring",
    "timeOfDay": 1100,
    "availableFish": []
  }
}
```

*Note: Full fish availability requires Content API integration.*

---

### `/mining` - Mine Data

Get current mine floor information.

```bash
curl http://localhost:8790/mining
```

**Response:**
```json
{
  "success": true,
  "data": {
    "location": "UndergroundMine",
    "floor": 45,
    "floorType": "frozen",
    "ladderFound": false,
    "shaftFound": false,
    "rocks": [
      {"tileX": 15, "tileY": 8, "type": "Iron", "health": 4},
      {"tileX": 22, "tileY": 12, "type": "Copper", "health": 2}
    ],
    "monsters": [
      {"name": "Dust Sprite", "tileX": 10, "tileY": 15, "health": 15, "maxHealth": 20, "damage": 4}
    ]
  }
}
```

**Floor types:** `normal`, `frozen`, `lava`, `skull_cavern`
**Ore types:** `Stone`, `Copper`, `Iron`, `Gold`, `Iridium`

---

### `/storage` - Chest Contents

Get all chests, fridge, and silo contents.

```bash
curl http://localhost:8790/storage
```

**Response:**
```json
{
  "success": true,
  "data": {
    "chests": [
      {
        "location": "Farm",
        "tileX": 48, "tileY": 6,
        "color": "{R:255 G:0 B:0}",
        "items": [
          {"slot": 0, "name": "Parsnip", "type": "crop", "stack": 50, "quality": 1}
        ]
      }
    ],
    "fridge": [
      {"slot": 0, "name": "Egg", "type": "object", "stack": 12, "quality": 0}
    ],
    "siloHay": 120,
    "siloCapacity": 240
  }
}
```

---

### `/action` - Execute Actions

Execute game actions (POST request).

```bash
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "move_direction", "direction": "north", "tiles": 5}'
```

**Available Actions:**
| Action | Parameters | Description |
|--------|------------|-------------|
| `move_direction` | `direction`, `tiles` | Move in direction |
| `use_tool` | `direction` (optional) | Use current tool |
| `equip_tool` | `tool` | Equip tool by name |
| `select_slot` | `slot` | Select inventory slot (0-11) |
| `face` | `direction` | Face direction |
| `interact_facing` | - | Interact with facing tile |
| `harvest` | `direction` | Harvest crop |
| `ship` | `slot` | Ship item from slot |
| `eat` | `slot` | Eat item from slot |
| `buy` | `item`, `quantity` | Buy from shop |
| `go_to_bed` | - | End day |
| `warp_to_farm` | - | Warp to farm |
| `warp_to_house` | - | Warp to farmhouse |
| `warp_location` | `location`, `target` | Warp to location |
| `dismiss_menu` | - | Close active menu |
| `confirm_dialog` | - | Confirm dialog (Yes) |

**Directions:** `north`, `south`, `east`, `west`

---

## Error Handling

All endpoints return consistent error format:

```json
{
  "success": false,
  "error": "Error message here"
}
```

---

## Testing

```bash
# Quick health check
curl http://localhost:8790/health

# Check pathfinding
curl "http://localhost:8790/check-path?startX=64&startY=15&endX=32&endY=17"

# Get all NPCs
curl http://localhost:8790/npcs

# Get player skills
curl http://localhost:8790/skills

# Check storage
curl http://localhost:8790/storage
```

---

*Session 83: Complete API implementation — Claude*
