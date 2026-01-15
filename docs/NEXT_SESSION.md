# Session 107+: Complete Farming → Mining

**Last Updated:** 2026-01-14 Session 107 by Claude
**Goal:** Finish ALL farming basics so we can move to mining and the cool shit

---

## The Vision

Get farming to "autopilot" status:
- Agent can plant, water, harvest, sell autonomously
- Agent crafts and places sprinklers (automates watering)
- Agent places scarecrows (protects crops)
- Agent uses fertilizer (better quality crops)
- Agent upgrades tools when needed

Then: **MINING** - caves, combat, ore, gems, the fun stuff!

---

## Current State (Session 106 End)

### What Works
| Feature | Status |
|---------|--------|
| Till soil | ✅ Working |
| Plant seeds | ✅ Working (phantom fix applied) |
| Water crops | ✅ Working + batch mode |
| Harvest crops | ✅ Working |
| Ship items | ✅ Working |
| Buy seeds | ✅ Working |
| Rain detection | ✅ Working - skips watering |
| Tool upgrade hints | ✅ Working - suggests upgrades |
| **Crafting action** | ✅ NEW (Session 107) - SMAPI `craft` |
| **Place items** | ✅ NEW (Session 107) - SMAPI `place_item` |
| **Chest storage** | ✅ NEW (Session 107) - open/deposit/withdraw |
| **Chest in GameState** | ✅ NEW (Session 107) - /farm shows all chests |

### What's Missing for "Farming Complete"
| Feature | SMAPI Action | Python Skill | Priority | Status |
|---------|--------------|--------------|----------|--------|
| **Crafting** | `craft` | crafting.yaml | HIGH | ✅ Done |
| **Place items** | `place_item` | place_* skills | HIGH | ✅ Done |
| **Chest storage** | `open_chest`, `deposit`, `withdraw` | storage.yaml | HIGH | ✅ Done |
| **Inventory mgmt** | via chest actions | inventory_manager.py | HIGH | ✅ Done |
| **Fertilizer** | via use_tool | apply_fertilizer | MEDIUM | ✅ Skills ready |
| **Scarecrows** | via craft + place | craft/place_scarecrow | MEDIUM | ✅ Skills ready |
| **Sprinklers** | via craft + place | craft/place_sprinkler | HIGH | ✅ Skills ready |
| **Fruit trees** | via place | plant_fruit_tree | LOW | ❌ Not started |
| **Tool upgrades** | `upgrade_tool` | upgrade_* skills | MEDIUM | ❌ SMAPI needed |

---

## Phase 1: Crafting System (HIGH PRIORITY)

### SMAPI: Add `craft` Action

**File:** `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs`

```csharp
// New action: craft
// Opens crafting menu, selects recipe, crafts item
"craft" => CraftItem(command.Item, command.Quantity),

private ActionResult CraftItem(string itemName, int quantity = 1)
{
    // 1. Check if player knows recipe
    // 2. Check if player has materials
    // 3. Call Game1.player.craftingRecipes.TryGetValue()
    // 4. Craft the item
    // Reference: Game1.player.crafting()
}
```

**Recipes Needed for Farming:**
| Item | Materials | Unlocked |
|------|-----------|----------|
| Scarecrow | 50 Wood, 1 Coal, 20 Fiber | Start |
| Basic Sprinkler | 1 Copper Bar, 1 Iron Bar | Farming 2 |
| Quality Sprinkler | 1 Iron Bar, 1 Gold Bar, 1 Refined Quartz | Farming 6 |
| Iridium Sprinkler | 1 Gold Bar, 1 Iridium Bar, 1 Battery Pack | Farming 9 |
| Chest | 50 Wood | Start |
| Fertilizer | 2 Sap | Start |
| Quality Fertilizer | 2 Sap, 1 Fish | Farming 9 |
| Speed-Gro | 10 Pine Tar, 1 Clam | Start |

### SMAPI: Add `place_item` Action

**File:** `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs`

```csharp
// New action: place_item
// Places item from inventory at target tile
"place_item" => PlaceItem(command.Slot, command.Direction),

private ActionResult PlaceItem(int slot, string direction)
{
    // 1. Get item from slot
    // 2. Calculate target tile from direction
    // 3. Check if placement is valid
    // 4. Place object at tile
    // Reference: StardewValley.Object.placementAction()
}
```

### Python: crafting.yaml Skills

```yaml
# New file: src/python-agent/skills/definitions/crafting.yaml

craft_scarecrow:
  description: "Craft a scarecrow (50 wood, 1 coal, 20 fiber)"
  preconditions:
    has_item: [{name: "Wood", count: 50}, {name: "Coal", count: 1}, {name: "Fiber", count: 20}]
  actions:
    - craft: {item: "Scarecrow", quantity: 1}

craft_basic_sprinkler:
  description: "Craft basic sprinkler (1 copper bar, 1 iron bar)"
  preconditions:
    has_item: [{name: "Copper Bar", count: 1}, {name: "Iron Bar", count: 1}]
    skill_level: {farming: 2}
  actions:
    - craft: {item: "Sprinkler", quantity: 1}

craft_quality_sprinkler:
  description: "Craft quality sprinkler (1 iron bar, 1 gold bar, 1 refined quartz)"
  preconditions:
    has_item: [{name: "Iron Bar", count: 1}, {name: "Gold Bar", count: 1}, {name: "Refined Quartz", count: 1}]
    skill_level: {farming: 6}
  actions:
    - craft: {item: "Quality Sprinkler", quantity: 1}

craft_chest:
  description: "Craft a chest for storage (50 wood)"
  preconditions:
    has_item: [{name: "Wood", count: 50}]
  actions:
    - craft: {item: "Chest", quantity: 1}

craft_fertilizer:
  description: "Craft fertilizer (2 sap)"
  preconditions:
    has_item: [{name: "Sap", count: 2}]
  actions:
    - craft: {item: "Basic Fertilizer", quantity: 1}
```

### Python: placement.yaml Skills

```yaml
# New file: src/python-agent/skills/definitions/placement.yaml

place_scarecrow:
  description: "Place scarecrow on farm (8-tile radius protection)"
  preconditions:
    has_item: [{name: "Scarecrow", count: 1}]
    location: "Farm"
  actions:
    - select_item_type: {value: "Scarecrow"}
    - place_item: {direction: "{target_direction}"}

place_sprinkler:
  description: "Place sprinkler on tilled soil (waters adjacent tiles daily)"
  preconditions:
    has_item_type: "sprinkler"
    location: "Farm"
  actions:
    - select_item_type: {value: "Sprinkler"}
    - place_item: {direction: "{target_direction}"}

place_chest:
  description: "Place chest for storage"
  preconditions:
    has_item: [{name: "Chest", count: 1}]
  actions:
    - select_item_type: {value: "Chest"}
    - place_item: {direction: "{target_direction}"}

apply_fertilizer:
  description: "Apply fertilizer to tilled soil before planting"
  preconditions:
    has_item_type: "fertilizer"
  actions:
    - select_item_type: {value: "Fertilizer"}
    - face: {direction: "{target_direction}"}
    - use_tool: {}
```

---

## Phase 1.5: Chest & Storage Management (HIGH PRIORITY)

As farming scales, the agent needs to manage inventory beyond just selling everything.

### Why Storage Matters
- **Keep seeds** for next planting cycle instead of buying
- **Store materials** (wood, stone, ore) for crafting
- **Organize by type** - seeds chest, materials chest, selling chest
- **Prevent inventory overflow** during harvest runs

### SMAPI: Chest Interaction Actions

**File:** `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs`

```csharp
// New action: open_chest
// Opens chest at adjacent tile or specified location
"open_chest" => OpenChest(command.Direction),

private ActionResult OpenChest(string direction)
{
    // 1. Get chest object at target tile
    // 2. Open chest inventory menu
    // Reference: Chest.checkForAction()
}

// New action: deposit_item
// Move item from player inventory to open chest
"deposit_item" => DepositItem(command.Slot, command.Quantity),

private ActionResult DepositItem(int slot, int quantity = -1)
{
    // 1. Check if chest menu is open
    // 2. Get item from player slot
    // 3. Add to chest inventory
    // 4. Remove from player inventory
    // quantity = -1 means entire stack
}

// New action: withdraw_item
// Move item from open chest to player inventory
"withdraw_item" => WithdrawItem(command.Slot, command.Quantity),

private ActionResult WithdrawItem(int slot, int quantity = -1)
{
    // 1. Check if chest menu is open
    // 2. Get item from chest slot
    // 3. Add to player inventory
    // 4. Remove from chest
}

// New action: close_chest
"close_chest" => CloseChest(),

// New action: get_chest_contents
// Returns inventory of chest at location (without opening UI)
"get_chest_contents" => GetChestContents(command.X, command.Y),
```

### SMAPI: GameState Additions

**File:** `src/smapi-mod/StardewAI.GameBridge/GameStateReader.cs`

```csharp
// Add to game state response:
"chests": GetFarmChests(),

private List<ChestInfo> GetFarmChests()
{
    // Return all chests on farm with:
    // - Position (x, y)
    // - Contents summary (item names + counts)
    // - Custom name if set
}
```

### Python: storage.yaml Skills

```yaml
# New file: src/python-agent/skills/definitions/storage.yaml

store_item:
  description: "Store an item in nearest chest"
  preconditions:
    has_item: [{name: "{item_name}", count: 1}]
  actions:
    - move_to: {target: "nearest_chest"}
    - open_chest: {direction: "facing"}
    - deposit_item: {item: "{item_name}", quantity: "{quantity}"}
    - close_chest: {}

store_all_of_type:
  description: "Store all items of a type (e.g., all seeds)"
  preconditions:
    has_item_type: "{item_type}"
  actions:
    - move_to: {target: "nearest_chest"}
    - open_chest: {direction: "facing"}
    - deposit_all: {type: "{item_type}"}
    - close_chest: {}

retrieve_item:
  description: "Get item from chest"
  actions:
    - move_to: {target: "chest_with_{item_name}"}
    - open_chest: {direction: "facing"}
    - withdraw_item: {item: "{item_name}", quantity: "{quantity}"}
    - close_chest: {}

organize_inventory:
  description: "Sort inventory - keep tools, store excess materials"
  actions:
    - move_to: {target: "storage_chest"}
    - open_chest: {direction: "facing"}
    - deposit_all: {type: "material", keep: 20}  # Keep 20 of each
    - close_chest: {}
```

### Python: inventory_manager.py

```python
# New file: src/python-agent/planning/inventory_manager.py

class InventoryManager:
    """Decides what to keep, sell, or store."""
    
    # Items to ALWAYS keep (never sell or store carelessly)
    ESSENTIAL_TOOLS = ["Axe", "Pickaxe", "Hoe", "Watering Can", "Scythe"]
    
    # Items to store, not sell
    STORE_CATEGORIES = {
        "seeds": ["Parsnip Seeds", "Potato Seeds", "Cauliflower Seeds", ...],
        "materials": ["Wood", "Stone", "Coal", "Fiber", "Sap", "Hardwood"],
        "ore": ["Copper Ore", "Iron Ore", "Gold Ore", "Iridium Ore"],
        "bars": ["Copper Bar", "Iron Bar", "Gold Bar", "Iridium Bar"],
        "gems": ["Diamond", "Ruby", "Emerald", ...],
    }
    
    # Items to sell (excess crops, forage, fish)
    SELL_CATEGORIES = ["crop", "forage", "fish", "artifact"]
    
    def categorize_item(self, item_name: str) -> str:
        """Returns: 'keep', 'store', or 'sell'"""
        pass
    
    def get_storage_action(self, inventory: list) -> Optional[str]:
        """Returns action if inventory management needed."""
        # If inventory > 80% full and has storable items
        # Return "store_materials" or similar
        pass
    
    def find_chest_for_item(self, item_name: str, chests: list) -> Optional[tuple]:
        """Find which chest should hold this item type."""
        pass
```

### Chest Naming Convention

Suggest agent uses predictable chest placement:
```
Farm Layout:
  [Seeds Chest] - Near farmhouse, for planting supplies
  [Materials Chest] - Near crafting area, wood/stone/ore
  [Selling Chest] - Near shipping bin, overflow for next day
```

### Integration with Daily Planner

```python
# In daily_planner.py, add storage check:

def generate_tasks(self, state):
    # ... existing task generation ...
    
    # Check if inventory management needed
    inventory = state.get("inventory", [])
    inventory_fullness = len([i for i in inventory if i]) / 36
    
    if inventory_fullness > 0.8:
        storable = self._count_storable_items(inventory)
        if storable > 5:
            self.tasks.append(DailyTask(
                name="organize_inventory",
                priority=7,  # Do before more harvesting
                description=f"Store {storable} items to free inventory space"
            ))
```

---

## Phase 2: Tool Upgrades (MEDIUM PRIORITY)

### SMAPI: Add `upgrade_tool` Action

```csharp
"upgrade_tool" => UpgradeTool(command.Tool),

private ActionResult UpgradeTool(string toolName)
{
    // 1. Must be at Blacksmith (Clint's shop)
    // 2. Check if player has enough gold + bars
    // 3. Call upgrade logic
    // Reference: Utility.getBlacksmithUpgradeStock()
}
```

**Upgrade Costs:**
| Level | Cost | Materials |
|-------|------|-----------|
| Copper | 2,000g | 5 Copper Bars |
| Steel | 5,000g | 5 Iron Bars |
| Gold | 10,000g | 5 Gold Bars |
| Iridium | 25,000g | 5 Iridium Bars |

### Python: shopping.yaml Updates

```yaml
# Add to existing shopping.yaml

go_to_blacksmith:
  description: "Go to Clint's blacksmith shop"
  actions:
    - warp: {target: "Blacksmith"}

upgrade_axe:
  description: "Upgrade axe at blacksmith"
  preconditions:
    location: "Blacksmith"
    money_gte: 2000  # Minimum for copper
  actions:
    - upgrade_tool: {tool: "Axe"}

upgrade_pickaxe:
  description: "Upgrade pickaxe at blacksmith"
  preconditions:
    location: "Blacksmith"
    money_gte: 2000
  actions:
    - upgrade_tool: {tool: "Pickaxe"}

upgrade_watering_can:
  description: "Upgrade watering can at blacksmith"
  preconditions:
    location: "Blacksmith"
    money_gte: 2000
  actions:
    - upgrade_tool: {tool: "Watering Can"}

upgrade_hoe:
  description: "Upgrade hoe at blacksmith"
  preconditions:
    location: "Blacksmith"
    money_gte: 2000
  actions:
    - upgrade_tool: {tool: "Hoe"}
```

---

## Phase 3: Smart Farm Layout (MEDIUM PRIORITY)

### Sprinkler Coverage Planning

```
Basic Sprinkler: Waters 4 tiles (cardinal directions)
    .X.
    X*X
    .X.

Quality Sprinkler: Waters 8 tiles (3x3 around it)
    XXX
    X*X
    XXX

Iridium Sprinkler: Waters 24 tiles (5x5 around it)
    XXXXX
    XXXXX
    XX*XX
    XXXXX
    XXXXX
```

### Scarecrow Coverage

- Each scarecrow protects 8-tile radius (circular)
- Need ~1 scarecrow per 17x17 area
- Deluxe Scarecrow: 16-tile radius

### Python: farm_planner.py Updates

```python
def calculate_sprinkler_positions(farm_area, sprinkler_type="quality"):
    """Calculate optimal sprinkler placement for coverage."""
    pass

def calculate_scarecrow_positions(farm_area):
    """Calculate optimal scarecrow placement for full coverage."""
    pass

def generate_efficient_farm_layout(available_area, crops_to_plant):
    """Generate farm layout with sprinklers + scarecrows."""
    pass
```

---

## Phase 4: Mining Preparation (THE COOL SHIT)

Once farming is on autopilot, we unlock:

### SMAPI Actions Needed for Mining
| Action | Purpose |
|--------|---------|
| `enter_mine` | Enter mine at specific level |
| `use_ladder` | Go down a level |
| `use_elevator` | Jump to unlocked level |
| `swing_weapon` | Combat |
| `eat_for_health` | Heal during combat |

### Mining Goals
1. Reach mine level 120 (bottom)
2. Collect ores: Copper → Iron → Gold → Iridium
3. Unlock elevator checkpoints (every 5 levels)
4. Fight monsters
5. Find geodes

### Combat System Needs
- Health monitoring
- Enemy detection
- Attack patterns
- Retreat logic

---

## Implementation Order

### Session 107: Crafting + Storage Foundation ✅ COMPLETE
1. [x] SMAPI: Add `craft` action
2. [x] SMAPI: Add `place_item` action
3. [x] SMAPI: Add chest actions (`open_chest`, `deposit_item`, `withdraw_item`, `close_chest`)
4. [x] SMAPI: Add `chests` to FarmState (with ChestInfo, ChestItemSummary)
5. [x] Python: Create crafting.yaml (scarecrow, chest, sprinklers, fertilizers)
6. [x] Python: Create placement.yaml (place_scarecrow, place_sprinkler, apply_fertilizer)
7. [x] Python: Create storage.yaml (open/close chest, deposit, withdraw, organize)
8. [x] Python: Create inventory_manager.py (categorize items, storage decisions)
9. [ ] Test: Craft chest, place it, store items (NEEDS GAME TESTING)

### Session 108: Sprinkler Automation
1. [ ] Test: Craft basic sprinkler
2. [ ] Python: Sprinkler placement planning
3. [ ] Integration: Auto-place sprinklers in farm layout
4. [ ] Test: Agent sets up sprinkler grid

### Week 3: Tool Upgrades
1. [ ] SMAPI: Add `upgrade_tool` action
2. [ ] Python: Upgrade skills
3. [ ] Integration: UpgradeTracker triggers upgrade goal
4. [ ] Test: Agent upgrades axe when blocked by stumps

### Week 4: Polish & Mining Prep
1. [ ] Polish: Farm layout optimization
2. [ ] SMAPI: Add mine actions
3. [ ] Python: Mining skills
4. [ ] Test: Agent enters mine

---

## Quick Reference: What's Where

### SMAPI Mod
```
src/smapi-mod/StardewAI.GameBridge/
├── ActionExecutor.cs      # Add craft, place_item, upgrade_tool
├── GameStateReader.cs     # Add crafting recipes, material counts
└── Models/GameState.cs    # Add recipe/material models
```

### Python Agent
```
src/python-agent/
├── skills/definitions/
│   ├── crafting.yaml      # NEW - craft_* skills
│   ├── placement.yaml     # NEW - place_* skills
│   ├── farming.yaml       # Existing farming skills
│   └── shopping.yaml      # Add upgrade_* skills
├── planning/
│   ├── farm_planner.py    # Add sprinkler/scarecrow layout
│   └── obstacle_manager.py # Already has upgrade tracking
└── unified_agent.py       # Integration
```

---

## Current Game State (Session 107 End)

### Tested & Verified
| Action | Result |
|--------|--------|
| `craft` Chest | ✅ Works - consumed 50 wood, chest added to inventory |
| `place_item` | ✅ Works - but needs smart placement logic |
| Chest in `/farm` | ⏳ Not tested yet |

### Critical Gap Identified
**The agent places items randomly** - no planning for optimal layouts. This defeats the purpose of automation. Need `farm_planner.py` to calculate:
- Scarecrow positions (8-tile radius, full coverage)
- Sprinkler grids (match coverage patterns)
- Chest locations (near farmhouse, shipping bin)
- Path layouts (efficient walking routes)

---

## Current Game State (Session 107 End)

- **Day:** Spring Year 1 (check in-game)
- **Player:** Elias
- **Wood:** Has enough to craft chest (50 needed)
- **Tools:** All basic (level 0)
- **SMAPI Mod:** Rebuilt with craft/place/chest actions
- **Status:** Game restarted, ready to test crafting

---

## Testing Instructions (Session 108)

### Quick Test: Craft and Place Chest

```bash
# 1. Check game is responding
curl -s http://localhost:8790/state | jq '.player.name, .location.name'

# 2. Check wood count
curl -s http://localhost:8790/state | jq '[.inventory[] | select(.name == "Wood")] | .[0].stack'

# 3. Test craft action (need 50 wood)
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "craft", "item": "Chest", "quantity": 1}'

# 4. Check chest was added to inventory
curl -s http://localhost:8790/state | jq '[.inventory[] | select(.name == "Chest")]'

# 5. Select the chest
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "select_item_type", "itemType": "Chest"}'

# 6. Place chest (facing direction)
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "place_item", "direction": "south"}'

# 7. Verify chest appears in /farm endpoint
curl -s http://localhost:8790/farm | jq '.chests'
```

### Test Storage Operations

```bash
# Open chest (must be adjacent)
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "open_chest", "direction": "south"}'

# Deposit item from slot 5
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "deposit_item", "slot": 5, "quantity": -1}'

# Close chest
curl -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action": "close_chest"}'
```

---

## Commands to Start

```bash
# Activate environment
cd /home/tim/StardewAI
source venv/activate

# Run agent
python src/python-agent/unified_agent.py --goal "Farm the crops"

# Build SMAPI mod after changes
cd src/smapi-mod/StardewAI.GameBridge
dotnet build

# Restart game to load mod changes
```

---

## Success Metrics

**Farming Complete When:**
- [ ] Agent crafts scarecrows without help
- [ ] Agent crafts and places sprinklers
- [ ] Agent uses fertilizer on crops
- [ ] Agent upgrades tools when blocked
- [ ] Agent runs full season with minimal intervention

**Ready for Mining When:**
- [ ] Farming runs on autopilot (sprinklers handle watering)
- [ ] Agent has upgraded pickaxe (at least Copper)
- [ ] Combat skills defined
- [ ] Mine navigation working

---

## Session 107 Accomplishments

### SMAPI Actions Added
| Action | Purpose | File |
|--------|---------|------|
| `craft` | Craft items from recipes | ActionExecutor.cs:1488 |
| `place_item` | Place items at tile | ActionExecutor.cs:1593 |
| `open_chest` | Open adjacent chest | ActionExecutor.cs:1629 |
| `close_chest` | Close current chest | ActionExecutor.cs:1667 |
| `deposit_item` | Put item in chest | ActionExecutor.cs:1681 |
| `withdraw_item` | Take item from chest | ActionExecutor.cs:1750 |

### GameState Additions
- `FarmState.Chests` - List of all chests on farm
- `ChestInfo` - Position, name, item count, slots free, contents
- `ChestItemSummary` - Item name, quantity, category

### Python Files Created
| File | Purpose |
|------|---------|
| `skills/definitions/crafting.yaml` | 15 crafting skills |
| `skills/definitions/placement.yaml` | 12 placement skills |
| `skills/definitions/storage.yaml` | 15 storage skills |
| `planning/inventory_manager.py` | Item categorization logic |

---

## Next Session Priority

### Session 108: Smart Farm Layout Planning (HIGH PRIORITY)

**Problem:** Agent places items randomly. Need intelligent placement.

1. **CREATE** `planning/farm_planner.py` with:
   - `calculate_scarecrow_positions(farm_bounds)` - Full coverage with minimal overlap
   - `calculate_sprinkler_grid(farm_area, sprinkler_type)` - Optimal patterns
   - `get_chest_locations()` - Strategic spots (near house, crops, shipping)
   - `generate_farm_layout(crops_to_plant)` - Complete layout plan

2. **INTEGRATE** planner into placement skills:
   - Agent asks planner "where should I place this scarecrow?"
   - Planner returns optimal (x, y) based on existing layout
   
3. **TEST** with crafted chest - place at planned location

### Session 109+: 
- Integrate skills into unified_agent.py executor
- Add `upgrade_tool` SMAPI action
- Mining preparation

---

---

## Session 108 Accomplishments

### Farm Planner Module Created
**File:** `planning/farm_planner.py`

| Function | Purpose |
|----------|---------|
| `calculate_scarecrow_positions()` | Greedy set cover algorithm, 8-tile radius |
| `get_chest_locations()` | Strategic spots (shipping bin, farmhouse) |
| `get_placement_sequence()` | Returns navigate-to + place-direction |
| `get_planting_layout()` | Optimal seed positions (contiguous) |
| `get_farm_layout_plan()` | Main API for UI and agent |

### API Endpoint Added
- `GET /api/farm-layout` - Returns scarecrows, chests, coverage stats
- Used by Codex's new Farm Layout Visualizer panel

### Smart Placement Skills Added
- `auto_place_scarecrow` - Navigates to optimal position, places
- `auto_place_chest` - Strategic location near shipping/farmhouse

### Tested End-to-End
1. Crafted Scarecrow (50 wood, 1 coal, 20 fiber consumed)
2. Planner calculated optimal position: (60, 19) covers 14 crops
3. Navigated to (60, 20), placed facing north
4. Verified: Scarecrow at (60, 19), planner recalculated remaining need

### Coverage Results
- 24 crops on farm, scattered across multiple patches
- 1 scarecrow placed, covers 10 crops (41.7%)
- 4 more scarecrows recommended for 100% coverage

---

## Session 109 Priorities

### 1. Fix Coverage Calculation
- Current issue: Coverage stats only show NEW planned scarecrows
- Need to include existing scarecrow coverage in totals

### 2. Smart Placement in Agent
- Add `requires_planning: true` skill execution support
- Agent calls `get_placement_sequence()` before placement skills
- Parameters populated automatically: `{planned_target_pos}`, `{planned_direction}`

### 3. Test Full Flow
- Craft 4 more scarecrows
- Place each at planned position
- Verify 100% coverage

### 4. Add `upgrade_tool` SMAPI Action
- For Blacksmith tool upgrades
- Needed before mining (copper pickaxe for deeper levels)

---

## Session 107 Summary

**Built:** SMAPI craft/place/chest actions + Python skill YAMLs + inventory_manager.py

**Tested:** Crafting works (chest crafted, 50 wood consumed)

**Gap Found:** Agent has no planning for WHERE to place items. Needs farm_planner.py.

---

## Session 108 Summary

**Built:** `planning/farm_planner.py` with scarecrow/chest positioning + `/api/farm-layout` endpoint

**Tested:** Full flow works - craft scarecrow → planner calculates (60, 19) → navigate → place

**Codex:** Completed Farm Layout Visualizer UI panel

**Next:** Session 109 - Fix coverage stats, integrate smart placement into agent, more testing

---

## Session 109 Accomplishments

### Smart Placement Integration Complete
| Component | Change |
|-----------|--------|
| `skills/models.py` | Added `SkillPlanning` dataclass, `requires_planning` field |
| `skills/loader.py` | Parses planning config, added "placement"/"storage" categories |
| `skills/executor.py` | Added `_call_planner()` and `_apply_planned_values()` |
| `unified_agent.py` | Farm data fetching for planning skills, batch plant handler |
| `planning/farm_planner.py` | Fixed coverage to include existing scarecrows, added `get_planting_sequence()` |

### New Capabilities
1. **Skills with `requires_planning: true`** now dynamically call farm planner
2. **Coverage stats fixed** - Shows existing + planned protection
3. **`auto_plant_seeds` skill** - Row-by-row orderly planting with auto-water

### Planning-Enabled Skills (3 total)
| Skill | Purpose |
|-------|---------|
| `auto_place_scarecrow` | Navigate to optimal position, place scarecrow |
| `auto_place_chest` | Strategic placement near shipping/farmhouse |
| `auto_plant_seeds` | Orderly row-by-row planting + watering |

### Batch Planting Features
- Uses `get_planting_sequence()` for row-by-row order
- Navigates to each position
- Plants seed, then waters immediately
- Stops when out of seeds
- Logs progress every 5 plants

---

## Session 110 Priorities

### 1. Test auto_plant_seeds Live
- Get seeds (buy or harvest parsnips)
- Till some soil
- Run `auto_plant_seeds` skill
- Verify row-by-row ordering

### 2. Test Remaining Placement Skills
- Need Coal for scarecrows
- Test `auto_place_chest` if have wood

### 3. Mining Preparation
- Add `upgrade_tool` SMAPI action (need copper pickaxe)
- Mining skills groundwork

---

*Session 109 Handoff: Smart placement integration complete, orderly planting skill added — Claude*
