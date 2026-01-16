# StardewAI Session Highlights Archive

Historical session highlights from TEAM_PLAN.md, archived 2026-01-16 Session 132.

---

## Session 111 Highlights

**Mining System**

Complete mining infrastructure added:

| Action | Purpose |
|--------|---------| 
| `enter_mine_level` | Enter specific floor (elevator validation) |
| `use_ladder` | Descend via ladder/shaft |
| `swing_weapon` | Combat with MeleeWeapon |

**Key Files Changed:**
```
ActionExecutor.cs        → EnterMineLevel(), UseLadder(), SwingWeapon()
ActionCommand.cs         → Level property
mining.yaml              → 20+ mining/combat skills
unified_agent.py         → Mining action dispatches
```

**Mining Floor Reference:**
| Levels | Type | Ore |
|--------|------|-----|
| 1-39 | Normal | Copper |
| 40-79 | Frozen | Iron |
| 80-119 | Lava | Gold |
| 120+ | Skull Cavern | Iridium |

**Batch Farm Chores (Architecture Change)**

Replaced individual VLM-per-action with goal-based batch execution:

| Old Flow | New Flow |
|----------|----------|
| VLM → action → VLM → action... | VLM → `auto_farm_chores` → batch runs all |

**Batch Phases:**
1. Buy seeds (if needed, Pierre open)
2. Harvest ready crops
3. Water (auto-refill)
4. Till grid (contiguous 5-wide rows)
5. Plant (row-by-row)

---

## Session 110 Highlights

**Tool Upgrade System**

Added complete tool upgrade workflow for Blacksmith:

| Action | Purpose |
|--------|---------|
| `upgrade_tool` | Start upgrade (removes tool, deducts gold+bars) |
| `collect_upgraded_tool` | Pick up finished tool (TODO) |

**Upgrade Skills Added:**
- `go_to_blacksmith` - Warp to Clint's shop
- `upgrade_pickaxe` - Copper→Steel→Gold→Iridium
- `upgrade_axe` - For chopping large stumps/logs
- `upgrade_hoe` - Larger tilling area
- `upgrade_watering_can` - More water capacity

**Upgrade Cost Table:**
| Level | Gold | Bars | Days |
|-------|------|------|------|
| Copper | 2,000g | 5 Copper Bars | 2 |
| Steel | 5,000g | 5 Iron Bars | 2 |
| Gold | 10,000g | 5 Gold Bars | 2 |
| Iridium | 25,000g | 5 Iridium Bars | 2 |

---

## Session 109 Highlights

**Smart Placement Integration**

Skills with `requires_planning: true` now call farm planner automatically:

| Skill | Planner Function | Result |
|-------|-----------------|--------|
| `auto_place_scarecrow` | `get_placement_sequence("scarecrow")` | Navigate to optimal pos, place |
| `auto_place_chest` | `get_placement_sequence("chest")` | Strategic location |
| `auto_plant_seeds` | `get_planting_sequence()` | Row-by-row planting |

**Key Files Changed:**
```
skills/models.py      → Added SkillPlanning dataclass
skills/loader.py      → Parse planning config
skills/executor.py    → _call_planner(), _apply_planned_values()
unified_agent.py      → Batch plant handler, farm data fetch
planning/farm_planner.py → get_planting_sequence(), fixed coverage
skills/definitions/farming.yaml → auto_plant_seeds skill
```

---

## Session 108 Highlights: Smart Farm Layout Planner

### New Module: `planning/farm_planner.py`
| Function | Purpose |
|----------|---------|
| `calculate_scarecrow_positions()` | Greedy set cover, 8-tile radius |
| `get_chest_locations()` | Strategic spots (shipping, farmhouse) |
| `get_placement_sequence()` | Navigate-to + place-direction |
| `get_planting_layout()` | Contiguous seed positions |
| `get_farm_layout_plan()` | Main API for UI/agent |

### API Endpoint
- `GET /api/farm-layout` - Returns planned placements + coverage stats

### Tested End-to-End
- Crafted scarecrow → Planner calculated (60, 19) → Navigated → Placed
- Scarecrow now protecting 14 crops at optimal position
- Planner recalculates after placement (4 more needed for 100%)

---

## Session 107 Highlights: Crafting + Storage System

### SMAPI Actions Added
| Action | Purpose |
|--------|---------|
| `craft` | Craft items from known recipes |
| `place_item` | Place craftable items at tile |
| `open_chest` / `close_chest` | Chest interaction |
| `deposit_item` / `withdraw_item` | Storage operations |

### GameState Enhancements
- `FarmState.Chests` - All chests on farm with contents summary
- `ChestInfo` model with position, name, slots_free, contents
- `ChestItemSummary` with item categorization

### Python Skills Created
| File | Count | Examples |
|------|-------|----------|
| `crafting.yaml` | 15 | craft_scarecrow, craft_sprinkler, craft_fertilizer |
| `placement.yaml` | 12 | place_scarecrow, place_sprinkler, apply_fertilizer |
| `storage.yaml` | 15 | open_chest, deposit_item, organize_inventory |

### New Module
- `planning/inventory_manager.py` - Categorizes items (keep/store/sell), finds best chest

---

## Session 106 Highlights: Farming Completion Roadmap

### Session 106 Fixes
| Fix | Details |
|-----|---------|
| Rain detection | Daily planner skips watering on rainy days |
| Tool upgrade tracking | UpgradeTracker suggests upgrades after 5 blocks |
| Decorative tiles | Path, Sprinkler, Scarecrow, etc. added to skip list |
| plant_seed verification | Fixed phantom failures using adjacentTile.hasCrop |

### Farming Completion Roadmap

**Goal:** Finish ALL farming basics → Move to MINING

| Phase | Focus | Priority |
|-------|-------|----------|
| Phase 1 | Crafting system (craft + place_item SMAPI actions) | HIGH |
| Phase 2 | Sprinklers + Scarecrows automation | HIGH |
| Phase 3 | Tool upgrades at Blacksmith | MEDIUM |
| Phase 4 | Mining preparation | NEXT |

---

## Session 104 Highlights: Dynamic Systems & Batch Operations

### Dynamic Crop Selection
- Removed ALL hardcoded `buy_parsnip_seeds` references
- New `get_recommended_seed_skill(state)` helper in unified_agent.py
- Uses crop advisor to calculate optimal seed by profit/day
- Shop hints, no-seeds hints, and overrides all use dynamic recommendation

### Festival Crop Filter
- Added `FESTIVAL_ONLY_CROPS = {"Strawberry", "Starfruit"}` 
- These aren't sold at Pierre's - caused silent skill failures
- Now excluded from recommendations, Cauliflower/Kale prioritized

### Batch Watering (Major Performance Fix)
- New `_batch_water_remaining()` method loops without VLM inference
- **Old:** ~2s per crop (VLM decides each one)
- **New:** ~0.3s per crop (direct execution loop)
- Auto-refills when can empties, returns to farm after refill
- Skips unreachable crops (behind buildings, hard obstacles)

### Obstacle Handling
- Hard obstacles (Stump, Boulder, Log) skipped immediately
- Building/terrain detection - no blocker = skip crop
- Stuck counter prevents infinite retry loops
- Skip list tracks failed crops to avoid re-attempting

### Dynamic Seed Quantity
- Buy skills now use `quantity: max` instead of hardcoded numbers
- Controller calculates: `min(money / seed_price, 20)`
- Buys as many as affordable, capped at 20

---

## Session 103 Highlights: Bug Fixes & Reliability

### Phantom Failure Fix
- Increased delay for tile-modifying skills from 0.3s to 0.8s
- `till_soil`, `clear_weeds`, `clear_stone` now wait for SMAPI tile state update
- Failure rate dropped from **46.9% to 17.9%**

### TTS Queue Fix
- Commentary worker now drains queue to latest event
- Skips stale commentary, always speaks most current
- No more 45-second lag behind agent actions

### UI Auto-Refresh
- `get_daily_planner()` and `get_rusty_memory()` now check file mtime
- Reload automatically when agent writes new data
- Fixed Day 16 showing when game was on Day 8

### Watering Can Refill
- New `go_refill_watering_can` skill - pathfinds to water + refills
- Changed `stop_adjacent: false` to reach cardinal edge (not diagonal corner)
- Tries all 4 directions to find water

### Shop Context Awareness
- VLM hints now recognize task locations (SeedShop, Blacksmith, etc.)
- Skip "WATERING CAN EMPTY" override when at Pierre's
- Added shop-specific hints: "AT PIERRE'S! DO: buy_seeds"

---

## Session 102 Highlights: Farming Framework Solidified

### Crop Database & Smart Selection
- Created `data/game_knowledge.db` with 30+ crops (Spring/Summer/Fall)
- Data includes: growth_days, seed_cost, sell_price, profit_per_day
- `planning/crop_advisor.py` picks highest profit crop for season/day/budget
- Integrated into PrereqResolver - buy_seeds now specifies optimal seed type

### All Spring Crops at Pierre's
Added buy skills for: kale, garlic, green bean, tulip, jazz, rice (joins existing parsnip, cauliflower, potato)

### Dynamic Inventory Complete
- Fixed `equip_seeds` to use `select_item_type: seed` (was using param)
- All farming skills now use dynamic tool selection - no hardcoded slots

### Backpack Upgrade (Codex)
- SMAPI action `buy_backpack` - direct upgrade with money check
- Handles both tiers: 12→24 (2000g), 24→36 (10000g)
- New `shopping.yaml` skill file

---

## Session 101 Highlights: JSON Crash & Phantom Failures

### Daily Summary JSON Crash Fixed
**Problem:** Agent crashed at bedtime trying to save daily summary:
```
TypeError: keys must be str, int, float, bool or None, not tuple
```

**Root Cause:** `cell_coordinator.py:get_daily_summary()` used tuple keys `(x,y)` for skip_reasons dict.

**Fix:** Convert to string keys `"x,y"` before JSON serialization.

### Phantom Failure Timing Fixed
**Problem:** Skills reported success but state verification detected failure:
```
[ERROR] 💀 HARD FAIL: water_crop phantom-failed 3x consecutively
```

**Root Cause:** Race condition - verification ran before SMAPI could poll updated game state.

**Fix:** Added 0.3s delay before state verification + enhanced diagnostic logging.

---

## Session 100 Highlights: TTS Pipeline & VLM Prompting

### TTS Rate Limiting Fixed
**Problem:** TTS takes ~40s per monologue, but commentary pushed every ~6s → queue backed up, spoke stale content.

**Fixes:**
- `_min_commentary_interval = 45.0` seconds between TTS pushes
- VLM commentary interval: 2 → 5 ticks
- Only push NEW monologues (duplicate tracking)

### VLM Skill Parameters Fixed
**Problem:** VLM calling `till_soil: {}` without `target_direction` → stuck in loop.

**Fixes:**
- Config examples updated with `target_direction`
- Skill context shows `(target_direction: north/south/east/west)` for directional skills

### Repetitive Openings Fixed
**Problem:** Every monologue started with "Ah, the farm..." - annoying.

**Fix:** BANNED instruction in prompts - VLM respects "BANNED" stronger than "NEVER".

---

## Session 99 Highlights: TTS Pipeline Fix

| Problem | Fix |
|---------|-----|
| Commentary flooding queue | Added `_last_pushed_monologue` - only push NEW monologues |
| TTS on CPU too slow | Moved Coqui XTTS to GPU (cuda:1 = 4070) |
| Queue backed up | Events dropped when queue full |

**Before/After:**
| Metric | Before | After |
|--------|--------|-------|
| Events per VLM tick | 20-30 (duplicates) | 1 (unique only) |
| TTS generation time | 3-5 seconds (CPU) | ~0.5-1 second (GPU) |

---

## Session 90 Highlights: Stale Targets & Buy Seeds

| Bug | Fix |
|-----|-----|
| Stale water targets | Added `no_crop_at_target` validation |
| Stale harvest targets | Added `not_ready_for_harvest` check |
| Cell farming bypasses buy_seeds | Check for seeds before starting cell farming |
| Water navigation fails | Pass surroundings to skill executor |
| SeedShop warp race | TaskExecutor stays at SeedShop if no seeds |

---

## Session 88-89 Highlights

**Session 88: Water Priority Fixes**
- Fixed 5 bugs: BLOCKED state, Y+1 validation, target validation, water priority FIRST, warp_to_farm prereq
- Partial test on rainy Day 3 - fixes working

**Session 89: Day Change Task Reset**
- Fixed: Task executor not resetting on day change (old tasks continued)
- Fixed: `smapi_data` AttributeError
- Multi-day test: Days 1-5 autonomous, stopped on water refill bug

---

## Session 87 Highlights: Multi-Day Test Results

- 13/15 seeds planted (87%)
- Day 1 crops NOT watered - saved by rain Day 3
- Agent went to bed successfully
- Survived Day 1 → Day 3

**Critical Bugs Found:**
| Bug | Impact | Priority |
|-----|--------|----------|
| Water task false completion | Crops unwatered (0 targets from FarmHouse) | HIGH |
| Cell reachability | Action position (Y+1) not validated | HIGH |
| Till phantom failures | 23+ failures on already-tilled cells | MEDIUM |
| Cell farming interrupted | 2 seeds unplanted | MEDIUM |

---

## Session 83 Highlights: Complete SMAPI API

### API Expansion Complete

Added 11 new endpoints to SMAPI mod for full game data access:

| Category | Endpoints |
|----------|-----------|
| Navigation | `/check-path`, `/passable`, `/passable-area` |
| Player | `/skills` |
| NPCs | `/npcs` |
| Farm | `/animals`, `/machines`, `/storage` |
| World | `/calendar`, `/fishing`, `/mining` |

**Total: 16 API endpoints** - Full coverage for autonomous gameplay.

### Cliff Navigation Fixed

Session 82 identified that agent got stuck on interior farm cliffs. Root cause: pathfinding existed internally but wasn't exposed via API.

**Solution:**
- Added `/check-path` endpoint exposing A* pathfinding
- farm_surveyor.py now filters unreachable cells before selection
- Agent only targets cells it can actually path to

---

## Session 82 Highlights: Cliff Navigation Bug

**Root Cause: SMAPI API Gap**
```
SMAPI has internally:
  - TilePathfinder.FindPath(start, end, location)
  - IsTilePassable(tile, location)

API exposes:
  - /surroundings → only 4 adjacent tiles
  - /farm → objects, crops, no passability

Gap: No endpoint for pathfinding/reachability checks
```

**Partial Fixes Applied (band-aids):**
| Fix | Purpose |
|-----|---------|
| SCAN_RADIUS 25→50 | Find more tillable patches |
| Wall navigation fallback | Try perpendicular direction when blocked |
| PLAYER_SCAN_RADIUS=8 | Very small search radius near player |
| Player pos as center | Select cells near player, not farmhouse |

---

## Session 81 Highlights: Ship/Buy/Plant Cycle Fixed

Complete farming cycle now works: ship crops → buy seeds → return to farm → plant

**Key Fixes:**
| Component | Bug | Fix |
|-----------|-----|-----|
| TargetGenerator | No ship targets | Added `_generate_ship_targets()` |
| TargetGenerator | Navigate to SeedShop failed | Added warp destination handling |
| TargetGenerator | No buy_seeds targets | Added target at current position |
| TaskExecutor | Didn't know ship/buy skills | Added to TASK_TO_SKILL mapping |
| TaskExecutor | Ignored target metadata skill | Added `target.metadata["skill"]` check |
| DailyPlanner | Skipped plant if no seeds | Added plant task anyway |
| PrereqResolver | No warp home after buy | Added warp_to_farm prereq |

---

## Session 80 Highlights: TaskExecutor Obstacle Clearing

- Added stuck detection: tracks position, increments counter if unchanged
- After 3 stuck attempts, checks surroundings for clearable obstacles
- Clears with appropriate tool: Tree→Axe, Stone→Pickaxe, Weeds→Scythe
- Falls back to skipping target if no clearable obstacle

**Ship Priority Fix:**
- Moved ship task to right after harvest in daily_planner.py
- Changed priority from HIGH to CRITICAL
- Order now: Harvest → Ship → Water → Plant → Clear

---

## Session 68 Highlights: Grid Layout & Daily Summary

**Grid Layout Fix:**
- Patches sorted by proximity to farmhouse (not size)
- Global cell sort for row-by-row walking order
- Before: `(57,27), (59,27), (54,19)...` → After: `(54,19), (55,19), (56,19)...`

**End-of-Day Summary:**
- `_save_daily_summary()` called before go_to_bed action
- Saves to `logs/daily_summary.json`: cells completed, skipped, reasons, lessons
- Derives next_day_goals from summary

---

## Session 67 Highlights: Obstacle Clearing During Navigation

- Detect blockers via `/surroundings` endpoint after 2 stuck attempts
- Clear debris (Weeds, Stone, Twig, Wood, Grass) with correct tool
- Skip non-clearable obstacles (Tree, Boulder, Stump, Log) immediately
- New helper method `_execute_obstacle_clear()` for face→tool→swing sequence

**Test Results:**
- 9/15 seeds planted (60%) vs 1/15 before (7%)
- **9x improvement** from Session 66

---

## Session 66 Highlights: Seed Selection Bug Fixed

- Root cause: `select_item` action not supported by ModBridge
- Fix: Added `seed_slot` field to CellPlan, use `select_slot` instead
- Verified: Seed slot 5 correctly selected during cell farming

**Test Results:**
- 1/15 cells completed successfully (full clear→till→plant→water cycle)
- 14/15 cells skipped due to navigation blocked by debris

---

## Session 65 Highlights: Cell Farming Bug Fixes

- Fixed re-survey bug: Added guard to skip restart if coordinator already active
- Fixed navigation stuck: Added 10-tick stuck detection, skip blocked cells
- Discovered select_item bug: ModBridge doesn't support select_item action

**Test Results:**
- 6/15 cells processed (actions executed)
- 9/15 cells skipped (stuck on debris)
- ~3 seeds actually planted (VLM fallback)

---

## Session 55-56 Highlights: Task Execution Fixes

**Session 55: Event-Driven Commentary**
- VLM triggers on meaningful events, not just timer intervals
- Events: TASK_STARTED, MILESTONE_25/50/75, TARGET_FAILED, ROW_CHANGE, TASK_COMPLETE

**Session 56: Buy Seeds Skills Fixed**
- Replaced template `{quantity}` with hardcoded defaults
- Daily Planner state path fixed: `state.data.location.crops`

---

## Session 54 Highlights: Task Execution Layer

**Problem Identified:** Rusty is tick-reactive, not task-driven. Each VLM call picks random targets instead of working systematically.

**Solution:** Task Execution Layer between Daily Planner and Skill Executor.

```
┌─────────────────────────────────────────────────────────┐
│                    DAILY PLANNER                        │
│  "Water crops" | "Harvest ready" | "Clear debris"       │
└─────────────────────────┬───────────────────────────────┘
                          │ picks next task
                          ▼
┌─────────────────────────────────────────────────────────┐
│              TASK EXECUTOR (NEW)                        │
│  Current Task: "Water crops"                            │
│  Targets: [(12,15), (13,15), (14,15)] ← row-by-row     │
│  Progress: 2/3 complete                                 │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR (existing)                  │
│  water_crop → [select_slot, face, use_tool]            │
└─────────────────────────────────────────────────────────┘
```

---

## Session 44 Highlights: State-Change Detection & Daily Planning

**State-Change Detection:**
- Captures state snapshot before skill execution
- Verifies actual state change after execution
- Tracks consecutive phantom failures per skill
- Hard-fails after 2 consecutive phantom failures

**Daily Planning System:**
- New module: `memory/daily_planner.py`
- Auto-triggers on day change
- Standard routine: incomplete→water→harvest→plant→clear
- VLM reasoning for intelligent prioritization

---

*Archived 2026-01-16 Session 132 — Claude (PM)*
