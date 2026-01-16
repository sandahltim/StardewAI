# Codex Task Queue

**Owner:** Codex (UI/Memory)
**Updated by:** Claude (PM)
**Last Updated:** 2026-01-16 Session 135

---

## 🔥 CRITICAL: Codebase Modularization (Session 135)

### TASK: Extract Helper Modules from unified_agent.py

**Priority:** CRITICAL - Blocking all future development
**Assigned:** 2026-01-16 Session 135
**Status:** 🔲 Not Started

#### Background

`unified_agent.py` has grown to **10,345 lines** with **115 methods** and **150+ duplicated patterns**. Session 135 analysis revealed the code is unmaintainable - fixes in one place get missed in duplicated code elsewhere.

See full analysis: `docs/REFACTORING_PLAN.md`

#### Phase 1: Helper Modules (Start Here)

Create `src/python-agent/helpers/` directory with utility modules that eliminate duplicated patterns.

**1. Create `helpers/inventory.py`**

```python
"""Centralized inventory operations - eliminates 8+ duplicate patterns."""

def find_item_in_inventory(inventory: list, name: str) -> dict | None:
    """Find item by name (case-insensitive)."""
    for item in inventory:
        if item and item.get("name", "").lower() == name.lower():
            return item
    return None

def count_materials(inventory: list, names: list[str]) -> dict[str, int]:
    """Count multiple materials in one pass."""
    counts = {name: 0 for name in names}
    for item in inventory:
        if item:
            item_name = item.get("name", "").lower()
            for name in names:
                if item_name == name.lower():
                    counts[name] = item.get("stack", 0)
    return counts

def find_item_slot(inventory: list, name: str) -> int | None:
    """Get slot index for item by name."""
    for i, item in enumerate(inventory):
        if item and item.get("name", "").lower() == name.lower():
            return i
    return None

def find_seeds(inventory: list) -> list[dict]:
    """Find all seed items."""
    return [item for item in inventory if item and "seed" in item.get("name", "").lower()]
```

**2. Create `helpers/objects.py`**

```python
"""Object finding in locations - eliminates 4+ duplicate patterns."""

def find_object_by_name(objects: list, name: str) -> tuple[int, int] | None:
    """Find object position by name (case-insensitive)."""
    for obj in objects:
        if obj.get("name", "").lower() == name.lower():
            x = obj.get("x", obj.get("tileX"))
            y = obj.get("y", obj.get("tileY"))
            return (x, y)
    return None

def find_chest(location_data: dict) -> tuple[int, int] | None:
    """Find chest position in location."""
    objects = location_data.get("objects", [])
    return find_object_by_name(objects, "chest")
```

**3. Create `helpers/navigation.py`**

```python
"""Direction and navigation utilities - eliminates 4+ duplicate patterns."""

def direction_to_target(px: int, py: int, tx: int, ty: int) -> str:
    """Calculate cardinal direction from source to target."""
    dx = tx - px
    dy = ty - py
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    else:
        return "south" if dy > 0 else "north"

def get_adjacent_tiles(x: int, y: int) -> list[tuple[int, int, str]]:
    """Get (x, y, facing_direction) for tiles adjacent to target."""
    return [
        (x, y + 1, "north"),  # Stand south, face north
        (x, y - 1, "south"),  # Stand north, face south
        (x + 1, y, "west"),   # Stand east, face west
        (x - 1, y, "east"),   # Stand west, face east
    ]
```

**4. Create `helpers/state.py`**

```python
"""Safe state extraction - eliminates 150+ defensive patterns."""

def get_inventory(state: dict | None) -> list:
    """Safely extract inventory from state."""
    if not state:
        return []
    return state.get("inventory", [])

def get_player_position(state: dict | None) -> tuple[int, int]:
    """Safely extract player position."""
    if not state:
        return (0, 0)
    player = state.get("player", {})
    return (player.get("tileX", 0), player.get("tileY", 0))

def get_location_data(state: dict | None) -> dict:
    """Safely extract location data."""
    if not state:
        return {}
    return state.get("location", {})

def get_location_name(state: dict | None) -> str:
    """Safely extract location name."""
    return get_location_data(state).get("name", "")
```

**5. Create `helpers/__init__.py`**

```python
"""Helper utilities for unified_agent.py modularization."""

from .inventory import (
    find_item_in_inventory,
    count_materials,
    find_item_slot,
    find_seeds,
)
from .objects import find_object_by_name, find_chest
from .navigation import direction_to_target, get_adjacent_tiles
from .state import (
    get_inventory,
    get_player_position,
    get_location_data,
    get_location_name,
)

__all__ = [
    "find_item_in_inventory",
    "count_materials",
    "find_item_slot",
    "find_seeds",
    "find_object_by_name",
    "find_chest",
    "direction_to_target",
    "get_adjacent_tiles",
    "get_inventory",
    "get_player_position",
    "get_location_data",
    "get_location_name",
]
```

#### Phase 2: Add Unit Tests

**Create `tests/test_helpers/test_inventory.py`**

```python
import pytest
from helpers.inventory import find_item_in_inventory, count_materials, find_item_slot

def test_find_item_by_name():
    inv = [{"name": "Wood", "stack": 50}, {"name": "Stone", "stack": 25}]
    item = find_item_in_inventory(inv, "wood")
    assert item["stack"] == 50

def test_find_item_case_insensitive():
    inv = [{"name": "Parsnip Seeds", "stack": 5}]
    item = find_item_in_inventory(inv, "PARSNIP SEEDS")
    assert item is not None

def test_count_materials():
    inv = [
        {"name": "Wood", "stack": 50},
        {"name": "Coal", "stack": 3},
        {"name": "Fiber", "stack": 20},
    ]
    counts = count_materials(inv, ["wood", "coal", "fiber"])
    assert counts == {"wood": 50, "coal": 3, "fiber": 20}

def test_find_item_slot():
    inv = [{"name": "Hoe", "stack": 1}, {"name": "Watering Can", "stack": 1}]
    slot = find_item_slot(inv, "watering can")
    assert slot == 1
```

#### Files to Create

```
src/python-agent/
├── helpers/
│   ├── __init__.py
│   ├── inventory.py
│   ├── objects.py
│   ├── navigation.py
│   └── state.py
└── tests/
    └── test_helpers/
        ├── __init__.py
        ├── test_inventory.py
        ├── test_objects.py
        ├── test_navigation.py
        └── test_state.py
```

#### Test Command

```bash
cd /home/tim/StardewAI
source venv/bin/activate
python -m pytest src/python-agent/tests/test_helpers/ -v
```

#### Acceptance Criteria

- [ ] All 4 helper modules created with functions as specified
- [ ] `helpers/__init__.py` exports all functions
- [ ] Unit tests created for each module
- [ ] All tests pass
- [ ] No external dependencies (pure Python)

#### Impact

| Pattern | Current Duplications | After Helpers |
|---------|---------------------|---------------|
| Inventory item search | 8+ | 0 |
| Material counting | 6+ | 0 |
| Object finding | 4+ | 0 |
| State extraction | 150+ | 0 |

#### Next Steps (After Phase 1)

Phase 2: Extract `modules/vlm_interface.py` (UnifiedVLM class)
Phase 3: Extract `modules/game_state.py` (get_* methods)
Phase 4: Extract `modules/batch_skills.py` (all _batch_* methods)

See `docs/REFACTORING_PLAN.md` for complete extraction sequence.

---

## 🆕 NEW: Action Verification Status Panel (Session 115)

### TASK: Action Verification UI Indicators

**Priority:** HIGH - Critical for debugging batch chores
**Assigned:** 2026-01-15 Session 115
**Status:** 🔲 Not Started

#### Background

Session 115 identified that batch farm chores (till, plant, water) log success without verifying game state. Claude is adding verification helpers that will track verified vs unverified action counts.

Codex: Add UI indicators showing verification status for recent actions.

#### Requirements

**1. Add Verification Status Panel**

```
┌──────────────────────────────────────────┐
│ ✓ ACTION VERIFICATION                    │
├──────────────────────────────────────────┤
│ RECENT BATCH (last 60s):                 │
│ Tilled:   ✓ 8/12 verified (67%)          │
│ Planted:  ✓ 8/8 verified (100%)          │
│ Watered:  ✓ 6/8 verified (75%)           │
├──────────────────────────────────────────┤
│ FAILED VERIFICATIONS:                    │
│ • Till (54,19) - tile not in tilledTiles │
│ • Till (55,19) - tile not in tilledTiles │
└──────────────────────────────────────────┘
```

**2. API Endpoint**

Add endpoint in `src/ui/app.py`:
```python
@app.get("/api/verification-status")
def get_verification_status():
    """Get action verification stats from agent."""
    # Pull from agent's verification tracking
    return {
        "tilled": {"attempted": 12, "verified": 8},
        "planted": {"attempted": 8, "verified": 8},
        "watered": {"attempted": 8, "verified": 6},
        "failures": [
            {"action": "till", "x": 54, "y": 19, "reason": "tile not tilled"}
        ]
    }
```

**3. Visual Elements**

- ✓ Green check for verified actions
- ✗ Red X for failed verifications
- Percentage bar showing verification rate
- List of specific failures with coordinates

#### Files to Modify
- `src/ui/app.py` - Add `/api/verification-status` endpoint
- `src/ui/static/app.js` - Add `pollVerificationStatus()`, `renderVerificationStatus()`
- `src/ui/templates/index.html` - Add panel section
- `src/ui/static/app.css` - Style for verification indicators

#### Implementation Note
Build UI with **placeholder/mock data** for now. Backend tracking will be added in Session 116. Use this mock response to test rendering:
```json
{
    "tilled": {"attempted": 12, "verified": 8},
    "planted": {"attempted": 8, "verified": 8},
    "watered": {"attempted": 8, "verified": 6},
    "failures": [
        {"action": "till", "x": 54, "y": 19, "reason": "tile not tilled"},
        {"action": "till", "x": 55, "y": 19, "reason": "tile not tilled"}
    ]
}
```

#### Blocked By
~~Claude implementing verification tracking in `unified_agent.py`.~~
**COMPLETED Session 116** - Backend now writes to `logs/verification_status.json`. Endpoint `/api/verification-status` serves real data.

---

## 🆕 NEW: Farm Layout Visualizer Panel (Session 108)

### TASK: Farm Layout Preview UI

**Priority:** HIGH - Part of smart placement feature
**Assigned:** 2026-01-14 Session 108
**Status:** ✅ Complete - Codex finished 2026-01-15

#### Background

Session 107 revealed a critical gap: the agent places items randomly with no layout planning. Session 108 is building `planning/farm_planner.py` to calculate optimal positions for scarecrows, sprinklers, and chests.

Codex: Build a UI panel to visualize these planned placements so Tim can see where things SHOULD go before the agent places them.

#### Requirements

**1. Add Farm Layout Panel**

```
┌──────────────────────────────────────────┐
│ 🗺️ FARM LAYOUT PLAN                      │
├──────────────────────────────────────────┤
│ PLANNED PLACEMENTS:                      │
│ 🌿 Scarecrow (54, 18) - covers 15 crops  │
│ 🌿 Scarecrow (70, 18) - covers 12 crops  │
│ 📦 Chest (64, 15) - near shipping bin    │
├──────────────────────────────────────────┤
│ COVERAGE STATS:                          │
│ Crop protection: 95% (2 tiles exposed)   │
│ Scarecrows needed: 2                     │
└──────────────────────────────────────────┘
```

**2. API Endpoint**

Add endpoint in `src/ui/app.py`:
```python
@app.get("/api/farm-layout")
def get_farm_layout():
    """Get planned placements from farm planner."""
    try:
        from planning.farm_planner import get_farm_layout_plan
        return get_farm_layout_plan()
    except Exception as e:
        return {"status": "no_plan", "error": str(e)}
```

**3. Data Fields**

From `farm_planner.get_farm_layout_plan()` (Claude building this):
```python
{
    "scarecrows": [
        {"x": 54, "y": 18, "covers_crops": 15, "radius": 8},
        {"x": 70, "y": 18, "covers_crops": 12, "radius": 8}
    ],
    "chests": [
        {"x": 64, "y": 15, "purpose": "near_shipping_bin"}
    ],
    "sprinklers": [],  # Empty until we have mining
    "coverage": {
        "protected_crops": 27,
        "total_crops": 29,
        "percentage": 93.1
    }
}
```

**4. Visual Elements**

- 🌿 for scarecrows (green - protection)
- 💧 for sprinklers (blue - watering)
- 📦 for chests (brown - storage)
- Coverage percentage bar
- List of each planned placement with coordinates

#### Files to Modify
- `src/ui/app.py` - Add `/api/farm-layout` endpoint
- `src/ui/static/app.js` - Add `pollFarmLayout()`, `renderFarmLayout()`
- `src/ui/templates/index.html` - Add panel section
- `src/ui/static/app.css` - Style for placement icons

#### Test Command
```bash
# Test API (once Claude finishes farm_planner.py)
curl http://localhost:9001/api/farm-layout | jq

# View in UI
open http://localhost:9001
```

#### Acceptance Criteria
- [x] Panel shows planned scarecrow positions with crop coverage
- [x] Panel shows planned chest positions with purpose
- [x] Coverage stats displayed (protected/total crops)
- [x] Graceful fallback when no plan exists
- [x] Updates when farm state changes

#### Blocked By
Claude finishing `planning/farm_planner.py` with `get_farm_layout_plan()` function.

---

## ✅ DONE: Backpack Upgrade Support (Session 102)

### TASK: Add Backpack Purchase Action to SMAPI

**Priority:** MEDIUM
**Assigned:** 2026-01-14 Session 102
**Status:** ✅ Complete - Codex finished 2026-01-14

#### Background

Players can upgrade their backpack at Pierre's by clicking on the backpack display on the wall (NOT through the shop menu). This costs 2,000g for first upgrade (12→24 slots) and 10,000g for second (24→36 slots).

Currently the agent cannot purchase backpack upgrades. Need SMAPI action to handle this.

#### Research Needed

1. How does the game handle backpack purchase? Is it a tile interaction or special menu?
2. Check if there's an existing API or if we need custom action

#### Requirements

**Option A: If it's a tile/object interaction**
- Add new action type: `buy_backpack` in ActionExecutor.cs
- Locate the backpack display tile in SeedShop
- Trigger interaction programmatically

**Option B: If it requires menu manipulation**
- May need to open shop menu and navigate to backpack tab
- More complex - discuss with Claude first

#### Files to Modify

- `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs` - Add buy_backpack action
- `src/python-agent/skills/definitions/shopping.yaml` (create if needed) - Add skill

#### Test Command

```bash
# Agent should be able to buy backpack when at Pierre's with 2000g+
python src/python-agent/unified_agent.py --goal "Buy a backpack upgrade"
```

#### Acceptance Criteria

- [x] Agent can purchase backpack upgrade when at Pierre's with enough gold
- [x] Works for both first (2000g) and second (10000g) upgrades
- [x] Graceful failure if can't afford or already maxed

---

## ✅ DONE: Dynamic Tool Selection in Skills (Session 101)

### TASK: Replace Hardcoded Slot Numbers with Tool Names

**Priority:** HIGH
**Assigned:** 2026-01-14 Session 101
**Status:** ✅ COMPLETE - Codex finished 2026-01-14

#### Background

Skills currently use hardcoded slot numbers like `select_slot: 2` for Watering Can. If player reorganizes inventory, skills break. We need dynamic tool selection by name.

**Dependency:** Claude is updating SMAPI mod to support `select_item_type: Watering Can` (matching by tool name, not just category).

#### Requirements

Once Claude confirms SMAPI change is done, update `farming.yaml`:

**File:** `src/python-agent/skills/definitions/farming.yaml`

| Line | Current | Replace With |
|------|---------|--------------|
| 19 | `- select_slot: 2  # Watering Can` | `- select_item_type: Watering Can` |
| 47 | `- select_slot: 2` | `- select_item_type: Watering Can` |
| 72 | `- select_slot: 2  # Watering Can is typically slot 2` | `- select_item_type: Watering Can` |
| 180 | `- select_slot: 1  # Hoe` | `- select_item_type: Hoe` |
| 205 | `- select_slot: 1  # Hoe is typically slot 1` | `- select_item_type: Hoe` |
| 225 | `- select_slot: 4  # Scythe` | `- select_item_type: Scythe` |
| 248 | `- select_slot: 4  # Scythe is typically slot 4` | `- select_item_type: Scythe` |
| 264 | `- select_slot: 3  # Pickaxe` | `- select_item_type: Pickaxe` |
| 287 | `- select_slot: 3  # Pickaxe is typically slot 3` | `- select_item_type: Pickaxe` |
| 303 | `- select_slot: 0  # Axe` | `- select_item_type: Axe` |
| 326 | `- select_slot: 0  # Axe is typically slot 0` | `- select_item_type: Axe` |

#### Test Command

```bash
# After changes, run agent and verify tool selection works
cd /home/tim/StardewAI
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Water the crops"

# Watch for logs like:
# SelectItemType: Found Watering Can at slot X
```

#### Acceptance Criteria

- [ ] All `select_slot: N` in farming.yaml replaced with `select_item_type: ToolName`
- [ ] No hardcoded slot numbers remain in farming.yaml (except `select_slot: "{seed_slot}"` which is already dynamic)
- [ ] Agent can water crops regardless of inventory arrangement

#### Blocked By

Claude updating SMAPI `SelectItemType` to match by tool name. Will post to team chat when ready.

---

## 🆕 NEW: World Data UI Panels (Session 84)

### TASK: Display New SMAPI API Data

**Priority:** MEDIUM
**Assigned:** 2026-01-12 Session 84
**Status:** ✅ Complete

#### Background

Session 83 added 11 new SMAPI endpoints. The UI should display this rich game data:
- `/npcs` - NPC locations and friendship
- `/calendar` - Upcoming events and birthdays
- `/machines` - Artisan equipment status
- `/storage` - Chest contents
- `/skills` - Player skill levels

#### Requirements

**1. NPC Panel**
```
┌──────────────────────────────────────┐
│ 👥 VILLAGERS                         │
├──────────────────────────────────────┤
│ 🎂 BIRTHDAYS THIS WEEK:              │
│   Vincent (Day 10) - 2 days away     │
│   Haley (Day 14) - 6 days away       │
├──────────────────────────────────────┤
│ NEARBY:                              │
│   Robin @ Carpenter Shop ❤️ 1        │
│   Demetrius @ Carpenter Shop ❤️ 0    │
└──────────────────────────────────────┘
```

**2. Calendar Panel**
```
┌──────────────────────────────────────┐
│ 📅 CALENDAR - Spring 8, Year 1       │
├──────────────────────────────────────┤
│ TODAY: Monday (Sunny)                │
│ Season ends in: 20 days              │
├──────────────────────────────────────┤
│ UPCOMING:                            │
│ 🎉 Egg Festival (Day 13)             │
│ 🎂 Vincent's Birthday (Day 10)       │
│ 🎂 Haley's Birthday (Day 14)         │
└──────────────────────────────────────┘
```

**3. API Endpoints to Call**
```javascript
// Add to app.js polling
fetch('/api/proxy/npcs')      // → http://localhost:8790/npcs
fetch('/api/proxy/calendar')  // → http://localhost:8790/calendar
fetch('/api/proxy/skills')    // → http://localhost:8790/skills
```

**4. Proxy Endpoints (if not already in app.py)**
```python
@app.get("/api/proxy/npcs")
def proxy_npcs():
    r = requests.get("http://localhost:8790/npcs", timeout=2)
    return r.json()
```

#### Files to Modify
- `src/ui/app.py` - Add proxy endpoints for new SMAPI routes
- `src/ui/static/app.js` - Add polling and render functions
- `src/ui/templates/index.html` - Add panel sections
- `src/ui/static/app.css` - Style for new panels

#### Test Command
```bash
# Test API directly
curl http://localhost:8790/npcs | jq '.data.npcs[:2]'
curl http://localhost:8790/calendar | jq '.data'

# Test UI
open http://localhost:9001
```

#### Acceptance Criteria
- [ ] NPC panel shows nearby villagers with hearts
- [ ] Calendar panel shows upcoming events/birthdays
- [ ] Panels update every 5 seconds
- [ ] Graceful fallback when SMAPI unavailable

---

## 🆕 NEW: Inventory Manager Module (Session 69)

### TASK: Inventory Manager

**Priority:** MEDIUM
**Assigned:** 2026-01-11 Session 69
**Status:** ✅ Complete

#### Background

During Day 1 testing, we discovered that seeds can end up in different inventory slots depending on how they're acquired (starting seeds, picked up, bought from Pierre). The current cell farming code finds seeds wherever they are, but we need better inventory management for:

1. **Multiple seed types** - If player has parsnips in slot 5 and potatoes in slot 7, which to use?
2. **Tool organization** - Hoe=1, Can=2, Axe=0, Pickaxe=3, Scythe=4 is hardcoded but items shift
3. **Stack consolidation** - Avoid fragmented stacks across multiple slots
4. **Dynamic slot lookup** - Find items by name, not hardcoded slot numbers

#### Requirements

**1. Create `src/python-agent/execution/inventory_manager.py`**

```python
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

@dataclass
class InventoryItem:
    slot: int
    name: str
    stack: int
    category: str  # "tool", "seed", "crop", "resource", etc.

class InventoryManager:
    """
    Manages inventory slot lookups and tool/item organization.
    Pure state reader - no side effects.
    """

    # Expected tool slots (default positions)
    TOOL_SLOTS = {
        "Axe": 0,
        "Hoe": 1,
        "Watering Can": 2,
        "Pickaxe": 3,
        "Scythe": 4,
    }

    def __init__(self, inventory: List[Dict[str, Any]]):
        """Parse inventory from SMAPI /state response."""
        self.items: List[Optional[InventoryItem]] = []
        self._parse(inventory)

    def find_item(self, name: str) -> Optional[int]:
        """Find slot containing item by name (case-insensitive partial match)."""
        pass

    def find_seeds(self) -> List[Tuple[int, str, int]]:
        """Find all seed items. Returns [(slot, name, stack), ...]"""
        pass

    def find_tool(self, tool_name: str) -> Optional[int]:
        """Find slot for a specific tool."""
        pass

    def get_seed_priority(self) -> Optional[Tuple[int, str]]:
        """Get (slot, name) of highest-priority seed to plant.

        Priority: Parsnip > Potato > Cauliflower (by growth time)
        """
        pass

    def total_seeds(self) -> int:
        """Count total seeds across all slots."""
        pass

    def get_tool_mapping(self) -> Dict[str, int]:
        """Build actual tool→slot mapping from current inventory."""
        pass
```

**2. Integration Points**

In `unified_agent.py:_start_cell_farming()`:
```python
# Current (hardcoded):
seed_slot = 5  # Assumes seeds always in slot 5

# New (dynamic):
from execution.inventory_manager import InventoryManager
inv_mgr = InventoryManager(inventory)
seed_slot, seed_type = inv_mgr.get_seed_priority()
```

In `cell_coordinator.py`:
```python
# Current (hardcoded tool slots):
HOE_SLOT = 1
WATERING_CAN_SLOT = 2

# New (dynamic from inventory_manager):
tool_map = inv_mgr.get_tool_mapping()
HOE_SLOT = tool_map.get("Hoe", 1)
```

**3. Test Cases**

```python
def test_find_seeds_multiple_types():
    """Seeds in different slots should all be found."""
    inv = [
        {"name": "Parsnip Seeds", "stack": 5},
        None,
        {"name": "Potato Seeds", "stack": 3},
    ]
    mgr = InventoryManager(inv)
    seeds = mgr.find_seeds()
    assert len(seeds) == 2
    assert mgr.total_seeds() == 8

def test_tool_in_unexpected_slot():
    """Tools can shift from default positions."""
    inv = [
        {"name": "Parsnip Seeds", "stack": 5},  # Tool displaced
        {"name": "Hoe", "stack": 1},  # Hoe in slot 1 (correct)
        {"name": "Axe", "stack": 1},  # Axe moved from slot 0
    ]
    mgr = InventoryManager(inv)
    assert mgr.find_tool("Axe") == 2
    assert mgr.find_tool("Hoe") == 1
```

#### Files to Create
- `src/python-agent/execution/inventory_manager.py` - Main module
- `src/python-agent/execution/test_inventory_manager.py` - Tests

#### Test Command
```bash
cd /home/tim/StardewAI
source venv/bin/activate
python -m pytest src/python-agent/execution/test_inventory_manager.py -v
```

#### Acceptance Criteria
- [ ] `find_seeds()` returns all seed items with slot, name, stack
- [ ] `find_tool()` finds tools regardless of slot position
- [ ] `get_seed_priority()` returns best seed type to plant
- [ ] `total_seeds()` counts across all slots
- [ ] All tests pass
- [ ] No external dependencies (pure Python)

---

## 🆕 NEW: Daily Summary UI Panel (Session 68)

### TASK: Daily Summary Panel

**Priority:** MEDIUM
**Assigned:** 2026-01-11 Session 68
**Status:** ✅ Complete (UI panel + endpoint ready; backend file still needed)

#### Background

Session 68 is adding **end-of-day summary persistence**. Before Rusty goes to bed, the agent saves what was accomplished. Next morning, this summary informs the daily planning.

Codex: Create a UI panel to display yesterday's summary and today's derived goals.

#### Requirements

**1. Add Daily Summary Panel**

New panel showing yesterday's accomplishments and today's plan:
```
┌──────────────────────────────────────────┐
│ 📊 DAILY SUMMARY - Day 4                 │
├──────────────────────────────────────────┤
│ YESTERDAY (Day 3):                       │
│ • Planted: 9 parsnip seeds               │
│ • Watered: 12 crops                      │
│ • Cleared: 5 debris tiles                │
│ • Energy used: 45/270                    │
├──────────────────────────────────────────┤
│ LESSONS LEARNED:                         │
│ • 6 cells skipped (tree blocked)         │
│ • Watering can ran dry once              │
├──────────────────────────────────────────┤
│ TODAY'S GOALS (from summary):            │
│ • Continue planting (6 seeds remaining)  │
│ • Water all 12 crops                     │
│ • Avoid tree-blocked area                │
└──────────────────────────────────────────┘
```

**2. API Endpoint**

Add endpoint in `src/ui/app.py`:
```python
@app.get("/api/daily-summary")
def get_daily_summary():
    """Load yesterday's summary and today's derived goals."""
    try:
        with open("logs/daily_summary.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"status": "no_summary", "message": "No summary yet. Complete a day first."}
```

**3. Data Fields**

From `logs/daily_summary.json` (Claude will create this):
- `day`, `season`, `year` - When summary was saved
- `planted_count`, `watered_count`, `cleared_count` - Accomplishments
- `cells_skipped` - With reasons (tree blocked, etc.)
- `energy_used`, `energy_remaining` - Resource tracking
- `lessons` - What went wrong, to avoid next time
- `next_day_goals` - Derived from summary

#### Files to Modify
- `src/ui/app.py` - Add `/api/daily-summary` endpoint
- `src/ui/static/app.js` - Add `pollDailySummary()`, `renderDailySummary()`
- `src/ui/templates/index.html` - Add panel section
- `src/ui/static/app.css` - Style for summary sections

#### Blocked By
Claude implementing `save_daily_summary()` in unified_agent.py (Session 68).

---

## ✅ COMPLETED: Target Generator Module (Session 54)

### TASK: Target Generator (NEW - Session 54)

**Priority:** HIGH - Foundation for Task Execution Layer
**Assigned:** 2026-01-11 Session 54
**Status:** ✅ Complete

#### Background

Session 54 research revealed Rusty's chaotic behavior stems from tick-reactive execution - each VLM call picks random targets instead of working systematically. We're building a **Task Execution Layer** that needs a **Target Generator** to convert high-level tasks into ordered spatial target lists.

This is CORE LOGIC, not UI - a pure function module that Claude's Task Executor will consume.

#### Requirements

**1. Create `src/python-agent/execution/target_generator.py`**

```python
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class SortStrategy(Enum):
    ROW_BY_ROW = "row_by_row"      # y asc, x asc - like reading a book
    NEAREST_FIRST = "nearest"      # Manhattan distance from player
    SPIRAL_OUT = "spiral"          # Center outward (future)

@dataclass
class Target:
    x: int
    y: int
    target_type: str              # "crop", "debris", "tile", "object"
    metadata: Dict[str, Any]      # crop_name, is_watered, etc.

class TargetGenerator:
    """
    Generates sorted target lists for task execution.
    Pure function - no side effects, no state.
    """
    
    def generate(
        self,
        task_type: str,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        strategy: SortStrategy = SortStrategy.ROW_BY_ROW
    ) -> List[Target]:
        """
        Main entry point. Dispatches to task-specific generators.
        
        Args:
            task_type: "water_crops", "harvest_crops", "clear_debris", 
                      "till_soil", "plant_seeds"
            game_state: From SMAPI /state endpoint
            player_pos: (x, y) current player position
            strategy: How to sort targets
            
        Returns:
            Ordered list of Target objects
        """
        pass
    
    def _generate_water_targets(self, state, pos, strategy) -> List[Target]:
        """Get unwatered crops from state.crops, sort by strategy."""
        pass
    
    def _generate_harvest_targets(self, state, pos, strategy) -> List[Target]:
        """Get ready crops from state.crops where isReadyForHarvest=True."""
        pass
    
    def _generate_debris_targets(self, state, pos, strategy) -> List[Target]:
        """Get debris objects (Stone, Weeds, Twig) from state.objects."""
        pass
    
    def _generate_till_targets(self, state, pos, strategy) -> List[Target]:
        """Get tillable tiles - clear ground that canTill=True."""
        # May need spatial_map data or surroundings scan
        pass
    
    def _generate_plant_targets(self, state, pos, strategy) -> List[Target]:
        """Get plantable tiles - tilled but empty."""
        pass
    
    def _sort_targets(
        self, 
        targets: List[Target], 
        player_pos: Tuple[int, int],
        strategy: SortStrategy
    ) -> List[Target]:
        """Apply sorting strategy to target list."""
        if strategy == SortStrategy.ROW_BY_ROW:
            return sorted(targets, key=lambda t: (t.y, t.x))
        elif strategy == SortStrategy.NEAREST_FIRST:
            return sorted(targets, key=lambda t: abs(t.x - player_pos[0]) + abs(t.y - player_pos[1]))
        return targets
```

**2. Data Sources**

Use data from SMAPI `/state` endpoint:

```python
# Crops (for water/harvest)
state["data"]["crops"] = [
    {"x": 12, "y": 15, "cropName": "Parsnip", "isWatered": False, "isReadyForHarvest": False},
    {"x": 13, "y": 15, "cropName": "Parsnip", "isWatered": True, "isReadyForHarvest": False},
    ...
]

# Objects (for debris)
state["data"]["objects"] = [
    {"x": 10, "y": 20, "name": "Stone", "type": "debris"},
    {"x": 11, "y": 20, "name": "Weeds", "type": "debris"},
    ...
]

# Player position
state["data"]["player"]["tileX"], state["data"]["player"]["tileY"]
```

**3. Test File: `src/python-agent/execution/test_target_generator.py`**

```python
def test_water_targets_row_by_row():
    """Crops sorted by y then x."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 14, "y": 15, "isWatered": False, "cropName": "Parsnip"},
                {"x": 12, "y": 15, "isWatered": False, "cropName": "Parsnip"},
                {"x": 13, "y": 16, "isWatered": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("water_crops", state, (10, 10), SortStrategy.ROW_BY_ROW)
    
    # Should be sorted: (12,15), (14,15), (13,16)
    assert targets[0].x == 12 and targets[0].y == 15
    assert targets[1].x == 14 and targets[1].y == 15
    assert targets[2].x == 13 and targets[2].y == 16

def test_water_excludes_watered():
    """Already watered crops not included."""
    gen = TargetGenerator()
    state = {
        "data": {
            "crops": [
                {"x": 12, "y": 15, "isWatered": True, "cropName": "Parsnip"},
                {"x": 13, "y": 15, "isWatered": False, "cropName": "Parsnip"},
            ]
        }
    }
    targets = gen.generate("water_crops", state, (10, 10))
    
    assert len(targets) == 1
    assert targets[0].x == 13

def test_harvest_targets():
    """Only ready crops included."""
    pass

def test_nearest_first_sorting():
    """Nearest to player comes first."""
    pass
```

**4. Integration Point**

Claude will create `execution/task_executor.py` that imports your generator:

```python
from execution.target_generator import TargetGenerator, SortStrategy

class TaskExecutor:
    def __init__(self):
        self.target_gen = TargetGenerator()
    
    def set_task(self, task_type: str, game_state: dict):
        player_pos = (state["data"]["player"]["tileX"], state["data"]["player"]["tileY"])
        self.targets = self.target_gen.generate(task_type, game_state, player_pos)
        self.target_index = 0
```

#### Files to Create
- `src/python-agent/execution/__init__.py` - Package init
- `src/python-agent/execution/target_generator.py` - Main module
- `src/python-agent/execution/test_target_generator.py` - Tests

#### Test Command
```bash
cd /home/tim/StardewAI
source venv/bin/activate
python -m pytest src/python-agent/execution/test_target_generator.py -v
```

#### Acceptance Criteria
- [ ] `generate("water_crops", ...)` returns unwatered crops sorted row-by-row
- [ ] `generate("harvest_crops", ...)` returns ready-to-harvest crops
- [ ] `generate("clear_debris", ...)` returns Stone/Weeds/Twig objects
- [ ] `SortStrategy.NEAREST_FIRST` sorts by Manhattan distance
- [ ] All tests pass
- [ ] No external dependencies (pure Python + dataclasses)

---

---

## Active Tasks

### TASK: Daily Plan Panel (NEW - Session 44)

**Priority:** HIGH
**Assigned:** 2026-01-10 Session 44
**Status:** ✅ Complete

#### Background

Session 44 added a daily planning system (`memory/daily_planner.py`). Rusty now generates a prioritized task list each morning and tracks progress throughout the day. We need a UI panel to display this.

#### Requirements

**1. Add Daily Plan Panel**

New panel showing Rusty's daily tasks:
```
┌──────────────────────────────────────┐
│ 📋 RUSTY'S PLAN - Day 5              │
├──────────────────────────────────────┤
│ ▶ CURRENT:                           │
│   • Water 11 crops                   │
├──────────────────────────────────────┤
│ ☐ TODO:                              │
│   • !! Harvest 3 mature crops        │
│   • ! Plant 5 seeds                  │
│   • Clear debris from farm           │
├──────────────────────────────────────┤
│ ✓ DONE: 2 tasks                      │
├──────────────────────────────────────┤
│ Completion: ████████░░ 80%           │
└──────────────────────────────────────┘
```

**2. API Endpoint**

Add endpoint in `src/ui/app.py`:
```python
@app.get("/api/daily-plan")
def get_daily_plan():
    from memory.daily_planner import get_daily_planner
    planner = get_daily_planner()
    return planner.to_api_format()
```

**3. Data Fields**

From `DailyPlanner.to_api_format()`:
- `day`, `season` - Current game day
- `tasks` - List of tasks with id, description, status, priority
- `focus` - Current task description
- `stats` - total/completed/pending/failed counts

#### Files to Modify
- `src/ui/app.py` - Add endpoint
- `src/ui/static/app.js` - Add `pollDailyPlan()`, `renderDailyPlan()`
- `src/ui/templates/index.html` - Add panel section
- `src/ui/static/app.css` - Style for task list, priority indicators

---

### TASK: Action Failure Panel (NEW - Session 44)

**Priority:** MEDIUM
**Assigned:** 2026-01-10 Session 44
**Status:** ✅ Complete

#### Background

Session 44 added phantom failure detection - tracking when actions report success but the game state doesn't actually change. We need a UI panel to show these failures for debugging.

#### Requirements

**1. Add Action Failure Panel**

New panel showing recent failures:
```
┌──────────────────────────────────────┐
│ ⚠️ ACTION FAILURES                   │
├──────────────────────────────────────┤
│ Recent Phantom Failures:             │
│ • plant_seed: 2x (tile not tilled)   │
│ • water_crop: 1x (no crop at target) │
├──────────────────────────────────────┤
│ Success Rates (last 50 actions):     │
│ water_crop:   ████████░░ 85%         │
│ plant_seed:   ██████░░░░ 60%         │
│ harvest_crop: ██████████ 100%        │
└──────────────────────────────────────┘
```

**2. Data Source**

This data comes from:
- `unified_agent.py:_phantom_failures` - consecutive failure counts
- `LessonMemory` - recorded failures with reasons
- Could add new tracking dict to agent for success/fail counts

**3. Implementation Notes**

Option A: Add `/api/action-stats` endpoint that tracks success/fail per skill
Option B: Extend `/api/lessons` to include phantom failure context

#### Files to Modify
- `src/ui/app.py` - Add endpoint
- `src/python-agent/unified_agent.py` - Add action success tracking (if needed)
- `src/ui/static/app.js` - Add render function
- `src/ui/templates/index.html` - Add panel

---

## Project Review Findings (Session 36)

A full project review identified these gaps:

### UI Status: 70% Functional
- Chat, Team Chat, Goals, Tasks, Control Panel - **100% working**
- Skill tracking, Shipping history - **90% working**
- Compass, Tile State, Crops - **100% SMAPI-dependent** (show "waiting" if SMAPI down)
- VLM Debug section - **exists but agent never sends data**
- Lessons panel - **exists but agent never populates**
- Memory search - **Chroma DB is empty**

### Key Issues
1. **Agent doesn't populate UI fields** - VLM debug, lessons, memory
2. **SMAPI-dependent sections have no fallback** - just show "waiting"
3. **Rusty has no memory** - personality exists but no continuity

---

## Active Tasks

### TASK: Multi-Day Progress Panel (NEW - Session 40)

**Priority:** HIGH
**Assigned:** 2026-01-10 Session 40
**Status:** ✅ Complete

#### Background

Session 40 is testing multi-day farming cycles:
- Day 1: Plant parsnips
- Days 2-3: Water daily
- Day 4: Harvest

We need a UI panel to track this cycle visually. Currently there's no way to see at a glance where we are in the multi-day farming loop.

#### Requirements

**1. Add Multi-Day Tracker Panel**

New panel in the UI that shows:
```
┌──────────────────────────────────────┐
│ 🌱 FARMING CYCLE                     │
├──────────────────────────────────────┤
│ Day 5, Spring Year 1                 │
│ Weather: ☀️ Sunny                    │
├──────────────────────────────────────┤
│ PARSNIP PROGRESS (4 day crop)        │
│ [██████░░] Day 3/4 - Water today!    │
├──────────────────────────────────────┤
│ TODAY'S TASKS:                       │
│ ☐ Water all crops                    │
│ ☐ Check for harvestables             │
├──────────────────────────────────────┤
│ RECENT DAYS:                         │
│ Day 4: Watered 4 crops               │
│ Day 3: Watered 4 crops               │
│ Day 2: Watered 4 crops               │
│ Day 1: Planted 4 parsnips            │
└──────────────────────────────────────┘
```

**2. Data Sources**

Pull from existing endpoints:
- `/state` → `day`, `season`, `year`, `weather`
- `/surroundings` → crop data (growth stage)
- Rusty Memory → recent events for daily log

**3. Crop Growth Tracking**

Calculate days until harvest based on crop type:
- Parsnip: 4 days
- Cauliflower: 12 days
- Potato: 6 days
(Can hardcode common crops or pull from knowledge base)

**4. Visual Progress Bar**

Show growth progress as:
- Empty: ░ (not planted)
- Growing: █ (each day of growth)
- Ready: 🌾 (harvestable)

#### Files to Modify
- `src/ui/templates/index.html` - Add panel section
- `src/ui/static/app.js` - Add render function, poll data
- `src/ui/static/app.css` - Style progress bars

#### Reference

Knowledge base for crop data: `src/python-agent/knowledge/items.yaml`
SMAPI state endpoint already provides day/season/weather.

---

### TASK: Rusty Memory UI Panel (NEW - Session 39)

**Priority:** MEDIUM
**Assigned:** 2026-01-10 Session 39
**Status:** ✅ Complete

#### Background

Session 38 added `memory/rusty_memory.py` - a character persistence system that tracks Rusty's episodic memory, mood, confidence, and NPC relationships. The system has a `to_api_format()` method ready for UI consumption, but no panel displays this data yet.

The existing "Rusty Snapshot" section shows mood but isn't connected to RustyMemory.

#### Requirements

**1. Add API Endpoint**

In `src/ui/app.py`, add endpoint to serve RustyMemory data:
```python
@app.get("/api/rusty/memory")
def get_rusty_memory():
    # Import from memory/rusty_memory.py
    # Return: character_state, recent_events, known_npcs
```

**2. Update Rusty Snapshot Panel**

Enhance the existing "Rusty Snapshot" section in index.html:
```
┌──────────────────────────────────┐
│ RUSTY                            │
├──────────────────────────────────┤
│ Mood: 😊 content                 │
│ Confidence: ████████░░ 80%      │
│ Day 12 of farming                │
├──────────────────────────────────┤
│ Recent Events:                   │
│ • Planted 3 parsnips             │
│ • Harvested cauliflower          │
│ • Met Lewis                      │
├──────────────────────────────────┤
│ Known NPCs: 4                    │
│ • Robin (acquaintance)           │
│ • Lewis (friend)                 │
└──────────────────────────────────┘
```

**3. Data Fields to Display**

From `RustyMemory.to_api_format()`:
- `character_state.mood` - Icon + text (😊 content, 😤 frustrated, etc.)
- `character_state.confidence` - Progress bar (0.0-1.0)
- `character_state.days_farming` - Counter
- `recent_events` - Last 5 events (description only)
- `known_npcs` - List with friendship levels

**4. Empty State**

When memory file doesn't exist yet:
```
┌──────────────────────────────────┐
│ RUSTY                            │
├──────────────────────────────────┤
│ No memories yet.                 │
│ Run agent to start recording.   │
└──────────────────────────────────┘
```

#### Implementation

1. Add import in app.py: `from memory.rusty_memory import get_rusty_memory`
2. Add `/api/rusty/memory` GET endpoint
3. Add poll function in app.js: `pollRustyMemory()`
4. Update `renderRustyPanel()` to use new data
5. Add CSS for confidence bar and event list

#### Files to Modify
- `src/ui/app.py` - Add endpoint
- `src/ui/static/app.js` - Add polling and render function
- `src/ui/templates/index.html` - Expand Rusty Snapshot section
- `src/ui/static/app.css` - Style for confidence bar

#### Reference

Memory file location: `logs/rusty_state.json`
Memory module: `src/python-agent/memory/rusty_memory.py`

Key method:
```python
def to_api_format(self) -> Dict[str, Any]:
    return {
        "character_state": self.character_state,
        "recent_events": self.episodic[-10:],
        "known_npcs": list(self.relationships.keys()),
        "relationship_count": len(self.relationships),
        "context": self.get_context_for_prompt(),
    }
```

---

### TASK: SMAPI Status Indicators (NEW - Session 36)

**Priority:** MEDIUM
**Assigned:** 2026-01-10 Session 36
**Status:** ✅ Complete

#### Background
Many UI panels depend on SMAPI running (Compass, Tile State, Crops, Inventory, etc.). When SMAPI is unavailable, they show "Waiting for..." indefinitely. Users need clear feedback.

#### Requirements

**1. Add SMAPI Connection Status Badge**

In the header/status area, add a connection indicator:
```
┌──────────────────────────────────┐
│ SMAPI: 🟢 Connected              │
│ SMAPI: 🔴 Unavailable            │
└──────────────────────────────────┘
```

**2. Update Affected Panels**

When SMAPI is unavailable, show explicit message instead of "Waiting...":
```
┌──────────────────────────────────┐
│ COMPASS                          │
├──────────────────────────────────┤
│ ⚠️ SMAPI unavailable            │
│ Start game with mod to enable   │
└──────────────────────────────────┘
```

**3. Affected Sections**
- Compass Navigation
- Tile State
- Watering Can Status
- Crop Status
- Inventory Grid
- Stamina/Energy
- Movement History (position events)

#### Implementation

1. Check SMAPI status on each poll (already fetching `/surroundings`)
2. Set global `smapiConnected` flag in app.js
3. Conditionally render "unavailable" badge in affected panels

#### Files to Modify
- `src/ui/static/app.js` - Add SMAPI status tracking, update render functions
- `src/ui/templates/index.html` - Add status badge area
- `src/ui/static/app.css` - Style for unavailable state

---

### TASK: Empty State Messages (NEW - Session 36)

**Priority:** LOW
**Assigned:** 2026-01-10 Session 36
**Status:** ✅ Complete (Session 37)

#### Background
Several panels show "None" or "Waiting..." when data hasn't been populated yet. Better UX to show contextual empty states.

#### Requirements

Update these panels with helpful empty state messages:

| Panel | Current | Better |
|-------|---------|--------|
| Lessons | "None" | "No lessons recorded yet. Failures will appear here." |
| Memory Search | "None" | "No memories stored yet." |
| Skill History | "No data yet" | "No skills executed yet. Run agent to see stats." |
| VLM Debug | "Waiting for observation..." | "Waiting for agent to start thinking..." |

#### Files to Modify
- `src/ui/static/app.js` - Update default text in render functions

---

## Backlog (Future Sessions)

### TASK: Rusty Memory Persistence (Claude)

**Priority:** HIGH (for character development)
**Owner:** Claude
**Status:** ✅ Complete (Session 38)

Created `memory/rusty_memory.py` with:
- Episodic memory (events with type, description, outcome, importance)
- Character state (mood, confidence 0.1-0.95, days farming, favorites)
- NPC relationships (first_met, interaction counts, friendship levels)
- JSON persistence to `logs/rusty_state.json`

Integrated into `unified_agent.py`:
- Session tracking from SMAPI day/season
- Event recording after action execution
- NPC meeting events on first encounter
- Character context added to VLM prompt

### TASK: Agent VLM Debug Population (Claude)

**Priority:** HIGH
**Owner:** Claude
**Status:** ✅ Complete (Session 37)

Added VLM debug state tracking to unified_agent.py:
- `vlm_observation` - from VLM result
- `proposed_action` - first action from VLM
- `validation_status` - "passed", "blocked"
- `validation_reason` - blocker name if any
- `executed_action` - what was executed
- `executed_outcome` - "success", "failed", or "blocked"

Updates sent via `_send_ui_status()` at key points in `_tick()`.

### TASK: Lesson Recording to UI (Claude)

**Priority:** MEDIUM
**Owner:** Claude
**Status:** ✅ Complete (Session 37)

LessonMemory now:
- Calls `_persist()` on every `record_failure()` (not just on recovery)
- Calls `_notify_ui()` to POST to `/api/lessons/update`
- UI endpoint broadcasts via WebSocket for real-time updates

---

## Communication Protocol

### For Status Updates
Post to team chat: `./scripts/team_chat.py post codex "your message"`

### For Questions
Post to team chat - Claude monitors it each session.

### When Done
Update this file marking task complete, then post to team chat.

---

## Completed Tasks

- [x] UI: Daily Plan Panel (2026-01-10 Session 44)
- [x] UI: Action Failure Panel (2026-01-10 Session 44)
- [x] UI: Multi-Day Progress Panel (2026-01-10 Session 40)
- [x] UI: Rusty Memory Panel (2026-01-10 Session 39)
- [x] UI: SMAPI Status Indicators + Empty States (2026-01-10 Session 36)
- [x] Vision Debug View (2026-01-10 Session 35)
- [x] Lessons Panel (2026-01-10 Session 35)
- [x] Commentary & Personality Improvements (2026-01-10 Session 35)
- [x] Farm Plan Visualizer UI (2026-01-10 Session 32)
- [x] Agent Commentary System with Personalities (2026-01-09 Session 27)
- [x] Landmark-Relative Directions (2026-01-09 Session 25)
- [x] Update Agent for Cardinal Directions (2026-01-09 Session 24)
- [x] Knowledge Base Loader (2026-01-09 Session 23)
- [x] UI: Shipping Bin Panel + API (2026-01-09 Session 23)
- [x] UI: Skill History/Analytics Panel (2026-01-09 Session 23)
- [x] UI: Skill Status Panel (2026-01-09 Session 21)
- [x] Skill Context System (2026-01-09 Session 21 - by Codex)
- [x] Skill System Infrastructure (2026-01-09 Session 20)
- [x] Spatial Memory Map (2026-01-09 Session 17)
- [x] UI: Bedtime/Sleep Indicator (2026-01-09 Session 15)
- [x] UI: Day/Season Progress Display (2026-01-09 Session 15)
- [x] UI: Goal Progress Checklist (2026-01-09 Session 15)
- [x] UI: Session Stats Panel (2026-01-08 Session 14)
- [x] UI: VLM Latency Graph (2026-01-08 Session 14)
- [x] UI: Crop Maturity Countdown (2026-01-08 Session 14)
- [x] UI: VLM Error Display Panel (2026-01-08 Session 13)
- [x] UI: Navigation Intent Display (2026-01-08 Session 13)
- [x] Agent: User Chat Context + Reply Hook (2026-01-08 Session 13)
- [x] UI: Harvest Ready Indicator (2026-01-08 Session 12)
- [x] UI: Energy/Stamina Bar (2026-01-08 Session 12)
- [x] UI: Action History Panel (2026-01-08 Session 12)
- [x] UI: Crop Status Summary (2026-01-08 Session 11)
- [x] UI: Location + Position Display (2026-01-08 Session 11)
- [x] UI: Action Repeat Detection (2026-01-08 Session 11)
- [x] UI: Inventory Panel (2026-01-08 Session 11)
- [x] UI: Action Result Log (2026-01-08 Session 11)

---

*Session 36: Project review complete. Added SMAPI status indicators and empty state tasks. Archived orphaned code.*

*— Claude (PM)*

FROM Director : TIM
ATOMIC PROMPT:

```
Do not write code before stating assumptions.
Do not claim correctness you haven't verified.
Do not handle only the happy path.
Under what conditions does this work?
```

FULL PROMPT:

```
You are entering a code field.

Code is frozen thought. The bugs live where the thinking stopped too soon.

Notice the completion reflex:
- The urge to produce something that runs
- The pattern-match to similar problems you've seen
- The assumption that compiling is correctness
- The satisfaction of "it works" before "it works in all cases"

Before you write:
- What are you assuming about the input?
- What are you assuming about the environment?
- What would break this?
- What would a malicious caller do?
- What would a tired maintainer misunderstand?

Do not:
- Write code before stating assumptions
- Claim correctness you haven't verified
- Handle the happy path and gesture at the rest
- Import complexity you don't need
- Solve problems you weren't asked to solve
- Produce code you wouldn't want to debug at 3am

Let edge cases surface before you handle them. Let the failure modes exist in your mind before you prevent them. Let the code be smaller than your first instinct.

The tests you didn't write are the bugs you'll ship.
The assumptions you didn't state are the docs you'll need.
The edge cases you didn't name are the incidents you'll debug.

The question is not "Does this work?" but "Under what conditions does this work, and what happens outside them?"

Write what you can defend.
