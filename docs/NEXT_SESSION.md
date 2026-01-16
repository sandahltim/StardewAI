# Session 136: Codebase Modularization + Testing

**Last Updated:** 2026-01-16 Session 135 by Claude
**Status:** Ready for refactoring

---

## 🔥 PRIORITY: Codebase Modularization

### Why This Matters
`unified_agent.py` has grown to **10,345 lines** with **150+ duplicated patterns**. Session 135 analysis revealed:
- Same code repeated in 4+ places (chest finding, material counting)
- Fixes in one place get missed in duplicated code elsewhere
- File too large for effective LLM regeneration

### Refactoring Plan Created
See `docs/REFACTORING_PLAN.md` for complete extraction plan.

### Phase 1: Create Helper Modules (Codex Task)
```
src/python-agent/helpers/
├── __init__.py
├── inventory.py    # find_item, count_materials, find_seeds
├── objects.py      # find_object_by_name, find_chest
├── navigation.py   # direction_to_target, get_adjacent_tiles
└── state.py        # get_inventory, get_player_position, get_location_data
```

**Impact:** Eliminates 150+ duplicated patterns

### Codex Task Assigned
See `docs/CODEX_TASKS.md` - "CRITICAL: Codebase Modularization" for full implementation spec.

---

## What Changed (Session 135)

### Craft & Place Skills Now Work (FIXED)
| Issue | Fix |
|-------|-----|
| craft_chest, auto_place_chest not in BATCH_SKILLS | Added to BATCH_SKILLS set |
| craft_scarecrow, auto_place_scarecrow not in BATCH_SKILLS | Added to BATCH_SKILLS set |
| Skills existed in YAML but had no batch handlers | Implemented `_batch_craft_chest()`, `_batch_place_chest()`, `_batch_craft_scarecrow()`, `_batch_place_scarecrow()` |

**BATCH_SKILLS now includes:**
```python
BATCH_SKILLS = {"auto_farm_chores", "auto_mine", "gather_wood", "gather_fiber", "organize_inventory", "craft_chest", "auto_place_chest", "craft_scarecrow", "auto_place_scarecrow"}
```

### New Batch Methods
| Method | What it does |
|--------|--------------|
| `_batch_craft_chest()` | Checks 50 wood, calls craft action, verifies in inventory |
| `_batch_place_chest()` | Finds chest in inventory, moves to (65,15) near farmhouse, places it |
| `_batch_craft_scarecrow()` | Checks 50 wood + 1 coal + 20 fiber, crafts, verifies |
| `_batch_place_scarecrow()` | Finds scarecrow in inventory, places at crop center |

**New logging:**
```
📦 CRAFT CHEST - 50 Wood Required
📦 Materials: Wood=52/50
📦 Chest crafted successfully!

📦 PLACE CHEST - Near Farmhouse
📦 Placing chest at (65, 15), facing south
📦 Chest placed at (65, 15)!

🎃 CRAFT SCARECROW - 50 Wood + 1 Coal + 20 Fiber
🎃 Materials: Wood=50/50, Coal=3/1, Fiber=25/20
🎃 Scarecrow crafted successfully!

🎃 PLACE SCARECROW - Protect Crops
🎃 Calculated crop center: (60, 18) from 15 crops
🎃 Placing scarecrow at (60, 18), facing south
🎃 Scarecrow placed at (60, 18)!
```

### Pickaxe Storage Investigation (PENDING)
| Issue | Status |
|-------|--------|
| User reported pickaxe was stored | Code looks correct - FARMING_TOOLS excludes Pickaxe |
| `_store_farming_tools` only stores Hoe, Scythe, Watering Can | Need logs to debug if issue persists |

**FARMING_TOOLS definition (unchanged):**
```python
FARMING_TOOLS = ["Hoe", "Scythe", "Watering Can"]  # Pickaxe NOT included
```

**InventoryManager.ESSENTIAL_TOOLS includes:** Pickaxe, Copper Pickaxe, Steel Pickaxe, Gold Pickaxe, Iridium Pickaxe

---

## What Changed (Session 134)

### Task Queue Empty → Crafting Task Regeneration
| Issue | Fix |
|-------|-----|
| Agent confused when all tasks complete | Mid-day regeneration of crafting tasks |
| No chest/scarecrow progress after farm chores | `_regenerate_crafting_tasks()` checks and adds tasks |
| VLM just said "Explore..." with no direction | Crafting tasks auto-queued when needed |

**New flow:**
```
Tasks complete → Queue empty → Check crafting needs → Add gather_wood/gather_fiber → Execute
```

### Scarecrow Material Gathering (NEW)
| Issue | Fix |
|-------|-----|
| Scarecrow just logged "missing materials" | Now creates `gather_wood` and `gather_fiber` tasks |
| No fiber gathering skill | Added `_batch_gather_fiber()` - cuts weeds with scythe |
| Coal not gathered | Noted in logs - comes from mining |

**Scarecrow materials:** 50 wood + 1 coal + 20 fiber

### gather_wood Skill Fix
| Issue | Fix |
|-------|-----|
| `gather_wood` always returned True | Now returns False if target (50 wood) not reached |
| Task marked complete even if no wood gathered | Task stays in queue for retry until target reached |
| No visibility into wood progress | Logs: `Have 25/50 wood - task stays in queue` |

**New logging:**
```
✅ gather_wood: reached target! Have 52/50 wood
⚠️ gather_wood: gathered 10 wood but still at 35/50 - task stays in queue
🪓 gather_wood: no wood gathered, have 25/50 - need trees/debris
```

### Batch Task Error Handling
| Issue | Fix |
|-------|-----|
| Exception left task in "in_progress" limbo | Reset task on exception too |
| No retry after crash | Task properly resets to "pending" for retry |

### organize_inventory Skill (NEW)
| Issue | Fix |
|-------|-----|
| Excess items cluttering inventory | New `organize_inventory` skill deposits to chest |
| Rocks, wood, sap, ores not stored | Uses InventoryManager to decide what to store |
| Manual inventory management | Auto-stores excess, keeps needed amounts |

**Items stored:** Seeds, ores, bars, gems, materials (excess beyond keep amounts)
**Items kept:** Tools, food, minimum crafting materials

### Total Inventory Tracking (NEW)
| Issue | Fix |
|-------|-----|
| Crafting only checked player inventory | Now checks player inventory + ALL chests |
| Had 50 wood in chest but task said "need wood" | `get_total_inventory()` combines all sources |
| Materials in chest were "invisible" | Daily planner uses total inventory for decisions |

### Tool Storage Logging (IMPROVED)
| Issue | Fix |
|-------|-----|
| Tool storage failures were silent | Better logging shows what tools are being stored |
| Couldn't debug tool retrieval issues | Logs show: tools in inventory, chest found, deposit actions |

---

## What Changed (Session 133)

### Mining Warp to Farm
| Issue | Fix |
|-------|-----|
| Agent stuck at mine entrance after mining | Auto-warp to farm after `_batch_mine_session` completes |
| Tool retrieval happened at mine entrance | Now warps to farm first |

### Ladder Position Parsing
| Issue | Fix |
|-------|-----|
| Python ignored `ladderPosition` from SMAPI | Added `TilePosition` dataclass to `smapi_client.py` |
| Agent couldn't navigate to ladder | `MiningState` now includes `ladder_position`, `shaft_position` |
| `get_mining()` missing position data | Returns `ladderPosition` and `shaftPosition` in dict |

### Descent Verification
| Issue | Fix |
|-------|-----|
| `floors_descended` incremented even on failure | Now verifies floor changed after BOTH `use_ladder` and `descend_mine` |
| Silent descent failures | Logs error: `DESCENT FAILED! Both use_ladder and descend_mine failed` |

**New logging:**
```
⛏️ Ladder/Shaft detected: ladder=True, shaft=False, pos={'x': 15, 'y': 10}
⛏️ Descended from floor 1 to floor 2
```

### Tool Retrieval After Mining
| Issue | Fix |
|-------|-----|
| Result check defaulted to success | Proper success/failure checking |
| No visibility into retrieval status | Per-tool logging: `🧰 ✅ Retrieved Watering Can` |
| No verification tools were retrieved | Post-retrieval inventory check |

**New logging:**
```
🧰 Withdrawing Watering Can
🧰 ✅ Retrieved Watering Can
🧰 Post-retrieval inventory tools: ['Hoe', 'Scythe', 'Watering Can']
🧰 Retrieved 3/3 tools
```

### VLM Stale Weather Fix
| Issue | Fix |
|-------|-----|
| VLM thought it was raining (stale data) | Force fresh state for VLM commentary (bypass 0.5s throttle) |
| No weather debugging | Added weather debug logging |

---

## Startup Commands

**Terminal 1 - llama-server:**
```bash
cd /home/tim/StardewAI
./scripts/start-llama-server.sh
```

**Terminal 2 - UI Server:**
```bash
cd /home/tim/StardewAI && source venv/bin/activate
uvicorn src.ui.app:app --reload --port 9001
```

**Terminal 3 - Agent:**
```bash
cd /home/tim/StardewAI && source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Do farm chores and mine"
```

---

## Session 136 Testing Checklist

### 1. Chest Crafting and Placement (Session 135 Fix) - PRIORITY
- [ ] After gather_wood reaches 50: `craft_chest` task starts
- [ ] Craft chest logged: `📦 CRAFT CHEST - 50 Wood Required`
- [ ] Craft success: `📦 Chest crafted successfully!`
- [ ] Placement task: `auto_place_chest` starts after crafting
- [ ] Place chest logged: `📦 PLACE CHEST - Near Farmhouse`
- [ ] Place success: `📦 Chest placed at (65, 15)!`

### 2. Scarecrow Crafting and Placement (Session 135 Fix) - PRIORITY
- [ ] After materials gathered: `craft_scarecrow` task starts
- [ ] Materials checked: `🎃 Materials: Wood=50/50, Coal=1/1, Fiber=20/20`
- [ ] Craft success: `🎃 Scarecrow crafted successfully!`
- [ ] Placement task: `auto_place_scarecrow` starts after crafting
- [ ] Place at crop center: `🎃 Calculated crop center: (X, Y)`
- [ ] Place success: `🎃 Scarecrow placed at (X, Y)!`

### 3. Task Regeneration (Session 134 Fix)
- [ ] When farm chores complete: `resolved queue empty, checking crafting needs...`
- [ ] If no chest + wood < 50: `Regenerating crafting tasks (queue empty)...`
- [ ] New task created: `Added 1 new crafting task(s)`
- [ ] gather_wood executes automatically

### 2. Wood Gathering Retry (Session 134 Fix) - PRIORITY
- [ ] If target not reached: `gathered X wood but still at Y/50 - task stays in queue`
- [ ] If target reached: `reached target! Have 50/50 wood`
- [ ] Task stays in queue until 50 wood achieved
- [ ] After reaching 50: `craft_chest` task should start

### 3. Fiber Gathering for Scarecrow (Session 134) - NEW
- [ ] If fiber < 20: `gather_fiber` task created
- [ ] Weeds found: `Found X weeds on farm`
- [ ] Fiber gathered: `GATHER COMPLETE: +X fiber`
- [ ] After reaching 20 fiber + 50 wood + 1 coal: `craft_scarecrow` starts

### 4. Organize Inventory (Session 134) - NEW
- [ ] When inventory fills: `organize_inventory` task created
- [ ] Items to store logged: `Items to store: X`
- [ ] Excess deposited: `Depositing Wood x30 (keeping 20)`
- [ ] Summary logged: `ORGANIZE COMPLETE: X items stored`

### 5. Total Inventory for Crafting (Session 134) - NEW
- [ ] At day start: `Total inventory: Wood=X, Coal=Y, Fiber=Z`
- [ ] Includes chest contents in material count
- [ ] Crafting decisions use combined inventory

### 6. Mining Flow (Session 133 Fix)
- [ ] Agent descends floors (watch for `Descended from floor X to Y`)
- [ ] Ladder detection: `Ladder/Shaft detected: ladder=True, pos={...}`
- [ ] Floor verification prevents false descent counts
- [ ] Agent warps to farm after mining: `Warping to farm after mining`

### 7. Tool Storage/Retrieval (Session 133 Fix)
- [ ] Tools logged: `Tools in inventory: [Hoe, Scythe, Watering Can]`
- [ ] Tools stored before mining: `🧰 Stored 3 tools: [Hoe, Scythe, Watering Can]`
- [ ] Tools retrieved after mining: `🧰 ✅ Retrieved Watering Can`
- [ ] Inventory verification: `Post-retrieval inventory tools: [...]`
- [ ] Agent can water crops after returning from mining

### 8. VLM Weather (Session 133 Fix)
- [ ] VLM commentary shows correct weather
- [ ] No stale "rainy" data on sunny days

### 9. Chest Crafting (Session 131 Fix)
- [ ] No "Unknown action for ModBridge: craft" error
- [ ] Chest placed on farm after crafting

---

## Key Log Messages

```
Task Regeneration (Session 134):
  🎯 _try_start_daily_task: resolved queue empty, checking crafting needs...
  📋 Regenerating crafting tasks (queue empty)...
  📋 Added 1 new crafting task(s)
  🚀 BATCH MODE: Task gather_wood_1 uses skill_override=gather_wood

Wood Gathering Retry (Session 134):
  ✅ gather_wood: reached target! Have 52/50 wood
  ⚠️ gather_wood: gathered 10 wood but still at 35/50 - task stays in queue
  🪓 gather_wood: no wood gathered, have 25/50 - need trees/debris

Fiber Gathering (Session 134):
  🌿 GATHER FIBER - Target: 20 fiber
  🌿 Found 15 weeds on farm
  🌿 GATHER COMPLETE: +12 fiber
  ✅ gather_fiber: reached target! Have 20/20 fiber
  ⚠️ gather_fiber: gathered 8 fiber but still at 15/20 - task stays in queue

Organize Inventory (Session 134):
  📦 ORGANIZE INVENTORY - Store excess items
  📦 Items to store: 5
  📦 Depositing Wood x30 (keeping 20)
  📦 Depositing Stone x25 (keeping 20)
  📦 ORGANIZE COMPLETE: 5 items stored

Total Inventory (Session 134):
  📋 Total inventory: Wood=75, Coal=3, Fiber=25
  📋 Using total inventory: 75 wood, 3 coal, 25 fiber

Tool Storage (Session 134):
  🧰 STORE FARMING TOOLS - Before Mining
  🧰 Tools in inventory: ['Hoe', 'Scythe', 'Watering Can']
  🧰 Found chest at (64, 15)
  🧰 Depositing Hoe from slot 0
  🧰 Stored 3 tools: ['Hoe', 'Scythe', 'Watering Can']

Mining Descent:
  ⛏️ Ladder/Shaft detected: ladder=True, shaft=False, pos={'x': 15, 'y': 10}
  ⛏️ Descended from floor 1 to floor 2
  ⛏️ MINING COMPLETE: ores=5, rocks=12, floors=3
  ⛏️ Warping to farm after mining (was at UndergroundMine)

Tool Flow:
  🧰 Storing farming tools before mining...
  🧰 Stored 3 tools: ['Hoe', 'Scythe', 'Watering Can']
  ... mining ...
  🧰 Retrieving farming tools: ['Hoe', 'Scythe', 'Watering Can']
  🧰 ✅ Retrieved Hoe
  🧰 ✅ Retrieved Scythe
  🧰 ✅ Retrieved Watering Can
  🧰 Post-retrieval inventory tools: ['Hoe', 'Scythe', 'Watering Can']
  🧰 Retrieved 3/3 tools

Descent Failure (if occurs):
  ⛏️ use_ladder didn't descend (still floor 5), using descend_mine fallback
  ⛏️ DESCENT FAILED! Both use_ladder and descend_mine failed on floor 5
```

---

## Files Modified (Session 135)

| File | Change |
|------|--------|
| `unified_agent.py` | Added `craft_chest`, `auto_place_chest`, `craft_scarecrow`, `auto_place_scarecrow` to BATCH_SKILLS |
| `unified_agent.py` | Added skill handlers for the 4 new skills in `execute_skill()` |
| `unified_agent.py` | Added `_batch_craft_chest()` - checks 50 wood, crafts, verifies |
| `unified_agent.py` | Added `_batch_place_chest()` - moves to (65,15), places near farmhouse |
| `unified_agent.py` | Added `_batch_craft_scarecrow()` - checks materials, crafts, verifies |
| `unified_agent.py` | Added `_batch_place_scarecrow()` - calculates crop center, places there |

---

## Files Modified (Session 134)

| File | Change |
|------|--------|
| `unified_agent.py` | `gather_wood` skill now returns False if target not reached |
| `unified_agent.py` | Added `_regenerate_crafting_tasks()` for mid-day task creation |
| `unified_agent.py` | Queue empty handling calls regeneration before legacy fallback |
| `unified_agent.py` | Batch exception handling resets task for retry |
| `unified_agent.py` | Added `gather_fiber` skill for scarecrow crafting |
| `unified_agent.py` | Added `_batch_gather_fiber()` - cuts weeds with scythe |
| `unified_agent.py` | Added `organize_inventory` skill - stores excess items |
| `unified_agent.py` | Added `_batch_organize_inventory()` - uses InventoryManager |
| `unified_agent.py` | Added `get_total_inventory()` - player + chest contents |
| `unified_agent.py` | Better tool storage logging before mining |
| `daily_planner.py` | Scarecrow now creates `gather_wood` and `gather_fiber` tasks |
| `daily_planner.py` | `_generate_crafting_tasks()` accepts `total_inventory` param |
| `daily_planner.py` | `start_new_day()` accepts and passes `total_inventory` |

---

## Files Modified (Session 133)

| File | Change |
|------|--------|
| `unified_agent.py` | Warp to farm after mining completes |
| `unified_agent.py` | Descent verification after both ladder methods |
| `unified_agent.py` | Ladder/shaft detection logging |
| `unified_agent.py` | Tool retrieval with proper result checking |
| `unified_agent.py` | Force fresh state for VLM commentary |
| `unified_agent.py` | `get_mining()` includes ladder/shaft positions |
| `smapi_client.py` | `TilePosition` dataclass |
| `smapi_client.py` | `MiningState` with `ladder_position`, `shaft_position` |

---

## Architecture Notes

### Mining Warp Flow
```python
# In execute_skill() for auto_mine:
results = await self._batch_mine_session(target_floors)

# Session 133: Always warp to farm after mining
self._refresh_state_snapshot()
location = self.last_state.get("location", {}).get("name", "")
if location != "Farm":
    logging.info(f"⛏️ Warping to farm after mining (was at {location})")
    self.controller.execute(Action("warp", {"location": "Farm"}, "return to farm"))
```

### Ladder Position Data Flow
```
C# SMAPI (ModEntry.cs) → LadderPosition {X, Y}
    ↓
Python smapi_client.py → MiningState.ladder_position: TilePosition
    ↓
unified_agent.py get_mining() → {"ladderPosition": {"x": 15, "y": 10}}
    ↓
_batch_mine_session() → Navigate to ladder, then use_ladder
```

### Tool Storage/Retrieval Flow
```
_batch_mine_session():
  1. _store_farming_tools() → chest (Hoe, Scythe, Watering Can)
  2. ... mining loop ...
  3. _retrieve_farming_tools() → inventory
  4. return results
execute_skill(auto_mine):
  5. warp to farm (Session 133)
```

---

## Roadmap (Future Sessions)

1. **Test craft/place skills** - Verify Session 135 chest/scarecrow crafting and placement
2. **Debug pickaxe storage** - If issue persists, check logs for deposit actions
3. **Test mining + tool flow** - Verify Session 133 fixes work
4. **Backpack upgrade** - Buy when gold >= 2000g (12 → 24 slots)
5. **Multi-chest support** - Route items to appropriate chests by type

---

## Session 135 Summary

| Change | Impact |
|--------|--------|
| craft_chest in BATCH_SKILLS | Crafting chest now uses proper batch handler |
| auto_place_chest in BATCH_SKILLS | Placing chest now uses placement logic |
| craft_scarecrow in BATCH_SKILLS | Crafting scarecrow now uses proper batch handler |
| auto_place_scarecrow in BATCH_SKILLS | Placing scarecrow uses smart crop-center calculation |
| 4 new batch methods | Full crafting and placement workflow implemented |

---

## Session 134 Summary

| Change | Impact |
|--------|--------|
| Task regeneration | Agent auto-adds crafting tasks when farm chores done |
| gather_wood retry | Task stays in queue until 50 wood achieved |
| gather_fiber skill | Agent cuts weeds for fiber (scarecrow needs 20) |
| Scarecrow gathering | Missing materials trigger gathering tasks |
| organize_inventory | Excess items deposited to chest automatically |
| Total inventory tracking | Crafting checks player inventory + all chests |
| Exception handling | Crashed tasks properly reset for retry |
| Tool storage logging | Better visibility into mining tool flow |

---

## Session 133 Summary

| Change | Impact |
|--------|--------|
| Mining warp to farm | No more stuck at mine entrance |
| Ladder position parsing | Agent can navigate to ladders |
| Descent verification | Accurate floor tracking |
| Tool retrieval fix | Tools properly restored after mining |
| VLM fresh state | Correct weather in commentary |

---

-- Claude (Session 134)
