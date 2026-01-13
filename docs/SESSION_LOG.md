# StardewAI Session Log

Coordination log between Claude (agent/prompt) and Codex (UI/memory).

---

## 2026-01-12 - Session 84: ResourceClump Detection + UI Panels

**Agent: Claude (Opus)**

### Summary
Verified all 16 SMAPI endpoints work. Found and fixed ResourceClump clipping bug - agent was walking through stumps/logs that need tool upgrades. Codex added NPC/Calendar UI panels.

### API Verification
All endpoints tested and working:
- `/skills` - Farming 96xp, Mining 28xp
- `/npcs` - 33+ villagers with friendship data
- `/calendar` - Egg Festival Day 13, birthdays tracked
- `/check-path` - A* pathfinding returns full path
- `/machines` - Many Casks in Cellar

### Bug Fix: ResourceClump Clipping

**Problem:** Agent walked through large stumps/logs/boulders.

**Root Cause:** These are `ResourceClump` objects (separate from regular Objects). They're walkable but need tool upgrades to clear.

**Fix:**
1. Added `ResourceClumpInfo` model to SMAPI mod
2. `/farm` endpoint now returns `resourceClumps` array
3. Farm surveyor marks all clump tiles as "blocked"

**Farm Stats:** 22 ResourceClumps blocking 88 tiles
- 17 Stumps (Copper Axe)
- 3 Logs (Steel Axe)
- 3 Boulders (Steel Pickaxe)

### Codex Work
- NPC panel with birthdays and nearby villagers
- Calendar panel with upcoming events
- SMAPI proxy endpoints (`/api/proxy/npcs`, etc.)

### Character Rename
Rusty → Elias (AI farmer persona)

### Commits
- `46a67c9` - Elias refactor + cliff navigation fix
- `8df6e66` - ResourceClump detection + UI panels
- `b56b9cb` - Farm surveyor excludes ResourceClump tiles

### Next Session
Test agent with ResourceClump fix, multi-day farming test.

---

## 2026-01-12 - Session 83: Complete SMAPI API Expansion

**Agent: Claude (Opus)**

### Summary
Implemented comprehensive SMAPI API coverage. Added 11 new endpoints exposing all game data needed for full autonomous gameplay. Fixed cliff navigation bug by exposing pathfinding via `/check-path` endpoint.

### New Endpoints (11 total)

| Category | Endpoints | Purpose |
|----------|-----------|---------|
| Navigation | `/check-path`, `/passable`, `/passable-area` | A* pathfinding, tile passability |
| Player | `/skills` | Skill levels, XP, professions |
| NPCs | `/npcs` | Locations, friendship, birthdays |
| Farm | `/animals`, `/machines`, `/storage` | Livestock, artisan equipment, chests |
| World | `/calendar`, `/fishing`, `/mining` | Events, fishing data, mine floors |

### Cliff Navigation Fix

The Session 82 cliff bug is now fixed:
- Added `/check-path` endpoint exposing TilePathfinder.FindPath()
- Updated farm_surveyor.py to filter unreachable cells before selection
- Agent now only selects cells it can actually path to

### API Total: 16 Endpoints

```
Core:     /health, /state, /surroundings, /farm, /action
Nav:      /check-path, /passable, /passable-area
Player:   /skills
World:    /npcs, /animals, /machines, /calendar, /fishing, /mining, /storage
```

### Code Changes

| File | Lines Added | Purpose |
|------|-------------|---------|
| Models/GameState.cs | ~200 | Model classes for all new endpoints |
| HttpServer.cs | ~100 | Routes and handlers |
| ModEntry.cs | ~300 | Data reader implementations |
| farm_surveyor.py | ~40 | Pathfinding check integration |
| SMAPI_API_EXPANSION.md | ~540 | Complete API reference |

### Why This Matters

Previously SMAPI only exposed what was needed for immediate actions. Now the agent has full knowledge of:
- **Where to go**: Pathfinding knows which cells are reachable
- **Who's where**: NPC locations and friendship status
- **What's ready**: Machine outputs, animal products
- **What's coming**: Festival and birthday calendar
- **What's stored**: All chest and fridge contents

### Next Session
Test the cliff navigation fix and expand agent logic to use new data endpoints.

---

## 2026-01-12 - Session 82: Cliff Navigation Bug

**Agent: Claude (Opus)**

### Summary
Attempted multi-day autonomy test but agent got stuck on interior cliffs. Diagnosed root cause: SMAPI has pathfinding but doesn't expose it via API.

### Problem
Agent selects farming cells by distance, but the Stardew Valley farm has multiple elevation levels with cliff edges. Cells that appear "close" may be unreachable without path-finding around cliffs.

### Root Cause
```
SMAPI has: TilePathfinder.FindPath(), IsTilePassable()
API exposes: /surroundings (4 adjacent tiles only)
Gap: No way to check if distant cells are reachable
```

### Partial Fixes Applied

| Fix | File | Purpose |
|-----|------|---------|
| SCAN_RADIUS 25→50 | farm_surveyor.py | Find more patches |
| Wall navigation fallback | task_executor.py | Try perpendicular direction when blocked |
| PLAYER_SCAN_RADIUS=8 | farm_surveyor.py | Smaller search radius near player |
| Player pos as center | farm_surveyor.py | Select cells near player, not farmhouse |

These are band-aids. Real fix: expose pathfinding via API.

### Next Session Task
Add `/check-path` endpoint to SMAPI mod:
- Input: start (x,y), end (x,y)
- Output: { reachable: bool, pathLength: int }
- Then filter cells by reachability before selecting

### Code Changes

| File | Lines | Change |
|------|-------|--------|
| farm_surveyor.py | 84 | SCAN_RADIUS 25→50 |
| farm_surveyor.py | 85 | Added PLAYER_SCAN_RADIUS=8 |
| farm_surveyor.py | 178 | Added scan_radius param |
| farm_surveyor.py | 285 | Added scan_radius param |
| farm_surveyor.py | 376 | Added player_pos param |
| farm_surveyor.py | 408-415 | Use player pos + smaller radius |
| task_executor.py | 324 | Pass surroundings to _create_move_action |
| task_executor.py | 427-473 | Wall navigation fallback |
| unified_agent.py | 2912-2925 | Pass player_pos to surveyor |

### Lesson Learned
SMAPI API should expose all game knowledge the agent needs. Pathfinding was built for internal use but never exposed. This is a design gap from early development.

---

## 2026-01-12 - Session 81: Ship/Buy/Plant Cycle Fix

**Agent: Claude (Opus)**

### Summary
Fixed the complete farming cycle: ship crops, buy seeds from Pierre, return to farm, plant seeds. Multiple bugs in TargetGenerator, TaskExecutor, and PrereqResolver were preventing the full workflow.

### Bugs Fixed

| Bug | Root Cause | Fix |
|-----|------------|-----|
| Ship task 0 targets | TargetGenerator had no `_generate_ship_targets()` | Added method to create shipping bin target |
| TaskExecutor didn't know ship | Missing from TASK_TO_SKILL map | Added `ship_items: ship_item` |
| Navigate to SeedShop failed | `_generate_navigate_target()` only handled coords, not location names | Added warp destination handling |
| TaskExecutor ignored target skill | Didn't check `target.metadata["skill"]` | Added metadata skill check |
| No plant task when no seeds | Planner skipped plant if no seeds | Added plant task anyway, let PrereqResolver add buy prereq |
| Bought but didn't return | PrereqResolver added go_pierre + buy_seeds but not warp_to_farm | Added warp_to_farm prereq after buy_seeds |
| buy_seeds 0 targets | No target generator for buy_seeds | Added target at current position |

### Verified Working

| Feature | Result |
|---------|--------|
| Ship crops | ✅ ship_item skill executes at bin |
| Warp to Pierre's | ✅ go_to_pierre skill warps to SeedShop |
| Buy seeds | ✅ buy_parsnip_seeds executes (100g for 5 seeds) |
| Return to farm | ✅ warp_to_farm prereq added after buy |
| Plant seeds | ✅ Cell farming plants seeds on tilled soil |

### Code Changes

| File | Change |
|------|--------|
| `target_generator.py:258-305` | Added `_generate_ship_targets()` |
| `target_generator.py:315-365` | Updated `_generate_navigate_target()` for warp destinations |
| `target_generator.py:63-70` | Added buy_seeds target at current position |
| `task_executor.py:114` | Added `ship_items: ship_item` to TASK_TO_SKILL |
| `task_executor.py:117` | Added `buy_seeds: buy_parsnip_seeds` to TASK_TO_SKILL |
| `task_executor.py:490` | Added check for `target.metadata["skill"]` |
| `daily_planner.py:435-455` | Plant task added even without seeds |
| `prereq_resolver.py:330-337` | Added warp_to_farm prereq after buy_seeds |
| `prereq_resolver.py:360-367` | Added warp_to_farm for sell-then-buy case |

### Game State at End
- Day 8, 7:20 PM
- On Farm
- Money: 305g (spent 100g on seeds)
- 3 Parsnip Seeds remaining
- 2 crops in ground

### Next Session (82)
1. Run multi-day autonomy test (2+ days)
2. Verify crops grow and harvest correctly
3. Test bedtime enforcement
4. Monitor for stuck states

---

## 2026-01-12 - Session 80: Verify Fixes + Obstacle Clearing

**Agent: Claude (Opus)**

### Summary
Verified Session 79 fixes (movement, harvest priority). Added obstacle clearing to TaskExecutor. Fixed ship priority ordering. Agent crashed due to missing `clear()` method (now fixed).

### Verified Working

| Fix | Result |
|-----|--------|
| Movement (+32 offset removed) | ✅ Positions change correctly: (64,15)→(61,15)→(61,17) |
| Harvest priority | ✅ Daily planner: Harvest before Water |
| Harvest execution | ✅ 12 parsnips harvested successfully |

### Bugs Fixed

| Bug | Fix | File |
|-----|-----|------|
| TaskExecutor stuck on obstacles | Added `_try_clear_obstacle()` - detects blocking objects, returns appropriate clear action | task_executor.py:502-563 |
| Ship priority too low | Moved ship to CRITICAL, placed right after harvest in code order | daily_planner.py:403-418 |
| TaskExecutor missing `clear()` | Added `clear()` method to reset executor state | task_executor.py:634-649 |

### Issues Discovered

| Issue | Description |
|-------|-------------|
| Bedtime override | Agent was still running at 11:50 PM, didn't go to bed |
| Task list static | New harvestable crop ignored (task list generated at day start) |
| Ship not executed | TaskExecutor followed old task order before fix was loaded |

### Code Changes

| File | Change |
|------|--------|
| `task_executor.py:140-144` | Added stuck detection variables |
| `task_executor.py:291-322` | Added stuck detection logic with obstacle clearing |
| `task_executor.py:502-563` | Added `_try_clear_obstacle()` method |
| `task_executor.py:634-649` | Added `clear()` method |
| `daily_planner.py:403-418` | Ship task moved after harvest, priority CRITICAL |
| `daily_planner.py:433` | Removed duplicate ship task |

### Game State at End
- Day 5, 11:50 PM (likely passed out)
- 12 parsnips in inventory (not shipped)
- Money: 405g

### Next Session (81)
1. Verify agent runs without crash
2. Test ship-after-harvest order
3. Test obstacle clearing
4. Complete full cycle: Ship → Pierre → Buy seeds → Bed

---

## 2026-01-12 - Session 79: Movement Bug Fix + Harvest Priority

**Agent: Claude (Opus)**

### Summary
Fixed 2 critical bugs: harvest priority ordering and movement position reset. Game restart required to test.

### Bugs Fixed

| Bug | Root Cause | Fix |
|-----|------------|-----|
| Harvest priority ordering | Water task added before harvest in code (both CRITICAL, stable sort kept insertion order) | Swapped order: harvest added before water in `daily_planner.py:390-414` |
| Movement not working | Session 78's +32 offset put sprite top-left at tile center, causing game to reset position | Removed +32 from all Position assignments in `ActionExecutor.cs` |

### Key Discovery: Movement Bug

The Session 78 "cell centering" fix broke movement:
- `player.Position` is the **top-left corner** of the sprite, not center
- Adding +32 put top-left at tile center, causing sprite to extend beyond tile boundaries
- Game's collision detection saw this as invalid and reset position immediately
- SMAPI log showed "Moved west 1 tiles to (57, 15)" but state showed (58, 15)

### Verified Working
- ✅ Harvest priority: TaskExecutor shows `"Starting resolved task: harvest_crops"` with 12 targets
- ⏳ Movement: Fixed but needs game restart to load rebuilt mod

### Code Changes

| File | Change |
|------|--------|
| `daily_planner.py:390-414` | Harvest task added BEFORE water task |
| `ActionExecutor.cs:154` | Removed +32 from path movement |
| `ActionExecutor.cs:212` | Removed +32 from MoveDirection |
| `ActionExecutor.cs:241` | Removed +32 from MoveInDirection |
| `ActionExecutor.cs:1049` | Removed +32 from WarpTo |
| `ActionExecutor.cs:1109` | Removed +32 from GoToBed |

### Game State at End
- Day 5, Spring Year 1, ~6:20 AM
- 12 parsnips ready to harvest
- SMAPI mod rebuilt, awaiting game restart

### Next Session (80)
1. Restart game to load rebuilt mod
2. Test movement fix (verify position changes)
3. Run full harvest cycle test

---

## 2026-01-12 - Session 78: Bug Fix Marathon

**Agent: Claude (Opus)**

### Summary
Fixed 6 major bugs blocking the harvest cycle. SMAPI mod rebuilt. Planner state cleared. Ready for full harvest test.

### Bugs Fixed

| Bug | Root Cause | Fix |
|-----|------------|-----|
| Harvest hint priority | Watering hints shown before harvest check | Check `isReadyForHarvest` first in hint logic |
| Bedtime override | TaskExecutor bypassed bedtime check | Hard check at hour >= 23 before TaskExecutor |
| Cell centering | Player at tile corner (0,0) not center | Add +32 offset to position (5 places in ActionExecutor.cs) |
| Refill navigation | Refill called without navigating to water | Check adjacent, navigate if not |
| Daily task carryover | Summary not saved on pass-out | Save summary when new day detected |
| Daily planner priority | Harvestable crops counted as "needs water" | Exclude harvestable from unwatered list |

### Code Changes

| File | Change |
|------|--------|
| `unified_agent.py:1154-1214` | Harvest hint priority (2 places) |
| `unified_agent.py:5175-5193` | Bedtime hard check |
| `unified_agent.py:3834-3838` | Daily summary save on new day |
| `ActionExecutor.cs` (5 places) | Cell centering +32 offset |
| `task_executor.py:338-383` | Refill navigation logic |
| `executor.py:74-89` | pathfind_to handler for nearest_water |
| `daily_planner.py:391-392` | Exclude harvestable from unwatered |
| `daily_planner.py:403-410` | Harvest priority = CRITICAL |

### Game State at End
- Day 5, Spring Year 1
- 12 parsnips ready to harvest
- 2 parsnips still growing
- Planner state cleared for fresh test

### Next Session (79)
- Run full harvest cycle test
- Verify all 6 fixes work in practice
- Complete: harvest → ship → buy seeds → plant → water → bed

---

## 2026-01-12 - Session 77: Multi-Day Cycle + Harvest Bug

**Agent: Claude (Opus)**

### Summary
Ran full multi-day test (Days 1-5). Planting and watering work. Harvest detection blocked by hint bug. Several bugs identified for Session 78.

### What Worked
- ✅ Elias character + david_attenborough TTS voice
- ✅ Multi-day farming cycle (Days 1-5)
- ✅ Planting 14 parsnip seeds
- ✅ Daily watering (all crops watered each day)
- ✅ Coqui voice path fix in `coqui_tts.py` (was falling back to female voice)
- ✅ Bedtime transitions (Day 1→2, 2→3, 3→4, 4→5)

### What Failed
- ❌ Harvest not triggered - 12 crops ready but agent keeps clearing debris
- ❌ Hint shows "needs watering" for harvest-ready crops
- ❌ Refill navigation - loops empty instead of navigating to water
- ❌ Bedtime late - passes out clearing debris past 2 AM

### Code Changes (Session 77)

| File | Change |
|------|--------|
| `commentary/coqui_tts.py:111-129` | Fixed voice path resolution (was passing name not path) |

### Bugs to Fix (Session 78)

| Bug | Severity | Location |
|-----|----------|----------|
| Harvest hint priority | HIGH | `unified_agent.py:1000-1200` |
| Refill navigation | MEDIUM | `farming.yaml` + skill executor |
| Bedtime override | MEDIUM | `unified_agent.py` tick loop |
| Cell centering | LOW | Movement logic |

### Elias Voice Samples (Session 77)

> "I wonder if these trees remember the last time someone tried to grow parsnips here. Probably not. But maybe they're thinking, 'Why are you still doing this? It's just dirt and seeds.'"

> "Maybe we're all just roots in the dark, waiting for something to happen."

### Game State at End
- Day 5, 12 crops ready to harvest, 0 parsnips harvested
- Agent stuck on clear_debris task instead of harvesting

---

## 2026-01-12 - Session 76: Elias Character Created

**Agent: Claude (Opus)**

### Summary
Created Elias - the VLM chose its own name and personality. Set up Coqui TTS voices. Ready for full harvest run.

### Major Achievement: Elias Born

The VLM was asked to choose its own name. It chose **Elias** - "quiet strength, someone who works hard, values the land."

**Elias's Character Traits:**
- Grandfather's wisdom: "The land remembers"
- Contemplative, finds poetry in dirt
- Talks to crops like old friends
- Dry humor, catches himself getting too philosophical
- Stoic in failure - "the earth is patient"
- Prefers crops to conversations (introverted)

### Files Created/Modified

| File | Change |
|------|--------|
| `commentary/elias_character.py` | NEW - Full character definition, INNER_MONOLOGUE_PROMPT, TTS_VOICES |
| `commentary/__init__.py` | Import from elias_character, RUSTY_CHARACTER alias for backwards compat |
| `commentary/coqui_tts.py:53` | Default voice = david_attenborough.wav |
| `config/settings.yaml:116-130` | System prompt updated to Elias personality |
| `src/ui/app.py:43,331,738,816` | Import elias_character, default voice david_attenborough |
| `src/ui/static/app.js:324,665,2148-2153,2606` | Fixed coquiVoiceSelect dropdown population |

### Coqui TTS Voice Options

| Voice Key | File | Best For |
|-----------|------|----------|
| default | david_attenborough.wav | Contemplative naturalist |
| wise | morgan_freeman.wav | Grandfatherly wisdom |
| gravelly | clint_eastwood.wav | Weathered farmer |
| dramatic | james_earl_jones.wav | Deep, commanding |
| action | arnold.wav | Intense parsnip moments |

### Elias Voice Samples

**Watering:** "The soil drinks deep, like it's remembering thirst from last winter."

**Rocks:** "Another rock appeared. Wonder if they reproduce. The land remembers, and so do the stones."

**Bedtime:** "Ah, the earth sighs as I lay down my tools. Let the moon watch over the sleeping fields."

### Next Session (77)
- Full harvest cycle test (parsnips ready Day 6)
- Test ship_item → buy_seeds flow
- Extended autonomy with Elias commentary
- Monitor voice quality

---

## 2026-01-12 - Session 75: SMAPI Actions Simplified + Multi-Day Test

**Agent: Claude (Opus)**

### Summary
Simplified high-level SMAPI actions, tested multi-day farming cycle. 13 crops planted and growing.

### Changes

1. **go_to_bed Simplified** - `navigation.yaml:281-297`
   - Old: warp FarmHouse → move west → interact (buggy positioning)
   - New: Single `go_to_bed` SMAPI action (handles warp, bed finding, NewDay)
   - Verified bed position: (10, 9) in FarmHouse

2. **ship_item Simplified** - `farming.yaml:366-390`
   - Old: Required `adjacent_to: shipping_bin`
   - New: Just requires `at_location: Farm` (SMAPI accesses bin remotely)
   - No navigation to bin needed

3. **till_soil Fixed** - `farming.yaml:166-182`
   - Bug: Missing `face` action caused phantom failures
   - Fix: Added `face: "{target_direction}"` before use_tool
   - VLM must now specify direction when calling

### SMAPI High-Level Actions Audit

| Action | Capability |
|--------|------------|
| `go_to_bed` | Full sleep flow from anywhere |
| `ship` | Ship from anywhere on Farm |
| `buy` | Direct purchase by item name |
| `eat` | Consume item for energy |

### Test Results

| Day | Weather | Actions | Result |
|-----|---------|---------|--------|
| 2 | Sunny | Plant 15 seeds | 9 crops planted |
| 3 | Rainy | Auto-water, plant more | +4 crops (13 total) |
| 4 | Sunny | Ready for watering test | - |

### Files Modified
| File | Change |
|------|--------|
| `skills/definitions/farming.yaml` | ship_item simplified, till_soil fixed |
| `skills/definitions/navigation.yaml` | go_to_bed simplified |

### Next Session
- Extended autonomy test (Day 4 → Day 8)
- Harvest + ship cycle test
- Verify watering on sunny day

---

## 2026-01-11 - Session 52: Pierre Navigation & Popup Handling

**Agent: Claude (Opus)**

### Problem
Agent warping directly into Pierre's shop landed in "black area" (invalid tile), causing stuck loop.

### Fixes

1. **Pierre Navigation** - `navigation.yaml:310-338`
   - Changed from: `warp: SeedShop` (direct teleport inside)
   - Changed to: warp Town → face north → move 1 → interact (enter through door)
   - Game now places player correctly inside shop

2. **Popup Handling** - `ActionExecutor.cs`, `unified_agent.py`
   - Added `dismiss_menu` SMAPI action (exits menus, skips events, clears dialogue)
   - Added `_fix_active_popup` override (top of chain)
   - Added UI state fields: Menu, Event, DialogueUp, Paused

3. **No-Seeds Override Expanded** - `unified_agent.py:2868-2871`
   - Now catches farming actions: `till_soil`, `plant_seed`, `water_crop`, `harvest`
   - Previously only caught debris actions

### Override Chain (Updated)
```
1. _fix_active_popup       → dismiss popup FIRST (NEW)
2. _fix_late_night_bed     → midnight bed
3. _fix_priority_shipping  → sellables ship
4. _fix_no_seeds           → Pierre's (EXPANDED)
5. _fix_edge_stuck         → retreat
6. _fix_empty_watering_can → refill
7. _filter_adjacent_crop   → move filter
```

### Known Issue (Next Session)
- `harvest_crop` phantom-failing 32x consecutively
- Bug: skill uses `harvest: {'value': 'east'}` instead of facing direction
- Agent faces south but harvest action goes east = loop

### Commit
`8de60b0` - Session 52: Proper Pierre navigation + popup handling

---

## 2026-01-11 - Session 51: Edge-Stuck & No-Seeds Overrides

**Agent: Claude (Opus)**

### Problem
Agent was stuck at map edges (cliffs) repeatedly trying to clear debris, ignoring hints to go to Pierre's for seeds.

### Fixes

1. **No-Seeds Override** - `unified_agent.py:2833-2877`
   - Detects: no seeds in inventory + Pierre's open (9-17, not Wed)
   - Action: Overrides debris actions → force `go_to_pierre`
   - Prevents endless debris loop when should buy seeds

2. **Edge-Stuck Override** - `unified_agent.py:2885-2939`
   - Detects: at map edge (x>72, x<8, y>45, y<10) + repeating 3x
   - Action: Forces retreat toward farm center (60, 20)
   - At night: Forces `go_to_bed` instead

3. **Collision Detection Fix** - `ActionExecutor.cs:177-188`
   - Bug: `MoveDirection` used only `isTilePassable()` - missed objects
   - Fix: Now uses `_pathfinder.IsTilePassable()` for thorough check
   - Prevents clipping through rocks/wood/debris

### Override Chain (Order)
```
1. _fix_late_night_bed      → midnight bed
2. _fix_priority_shipping   → sellables ship
3. _fix_no_seeds           → Pierre's (NEW)
4. _fix_edge_stuck         → retreat (NEW)
5. _fix_empty_watering_can → refill
6. _filter_adjacent_crop   → move filter
```

### Test Results
- Edge-stuck triggered at (76, 26) → retreat west ✅
- No-seeds correctly skipped on Wednesday (Pierre's closed) ✅
- Collision shows walls in directions ✅
- Agent farming Day 17 autonomously ✅

### Commit
`33810d2` - Session 51: Fix edge-stuck, no-seeds override, collision detection

---

## 2026-01-11 - Session 50: Shipping Workflow Complete

**Agent: Claude (Opus)**

### Major Progress

1. **Shipping Override - Aggressive Mode** ✅
   - Changed from blocklist (only catching till/clear) to allowlist
   - Now overrides ALL actions except critical ones when sellables exist
   - VLM can't escape to random tasks - forced to ship first
   - File: `unified_agent.py:2739-2807`

2. **SMAPI Movement - Synchronous** ✅
   - Root cause: `setMoving()` flags need game loop processing
   - If game window unfocused, game pauses → movement stops
   - Fix: Direct `player.Position` teleport with collision check
   - Now works reliably regardless of window focus
   - File: `ActionExecutor.cs:164-214`

3. **ship_item Skill Fix** ✅
   - Was using `interact` action (doesn't ship items)
   - Changed to `ship: -1` (uses currently selected slot)
   - File: `skills/definitions/farming.yaml:378-380`

4. **ModBridgeController - Added ship Handler** ✅
   - Controller didn't have case for `ship` action
   - Added handler that sends to SMAPI mod
   - File: `unified_agent.py:1639-1643`

### Test Results
- Agent successfully shipped 14 Parsnips
- Override triggered: `📦 OVERRIDE: At shipping bin (dist=1) → ship_item`
- Skill executed correctly with new `ship` action
- Money increases at end of day (shipped items go to bin)

### Files Modified
| File | Change |
|------|--------|
| `unified_agent.py` | Shipping override (aggressive), ship action handler |
| `ActionExecutor.cs` | Synchronous movement (direct teleport) |
| `farming.yaml` | ship_item skill uses ship action |

### Key Insight
Movement was failing because the game loop wasn't processing `setMoving()` flags when window lost focus. The game literally pauses. Solution: bypass the movement system entirely with direct position assignment.

### Next Session
- Test buy seeds flow
- Multi-day autonomy test
- Full farming loop: water → harvest → ship → buy → plant

---

## 2026-01-10 - Session 45: Bug Fixes + Positioning Discovery

**Agent: Claude (Opus)**

### Major Progress

1. **Clear_* Phantom Detection Fix** ✅
   - Added `get_surroundings()` refresh before verification
   - Clear actions now properly detect when debris isn't cleared

2. **Shipping Task Added to Daily Planner** ✅
   - "Ship harvested crops" task now added after harvest task
   - Ensures Rusty knows to ship items after harvesting

3. **Refill Hints Updated** ✅
   - Changed "use_tool to REFILL" → "refill_watering_can direction=X"
   - VLM should now output correct skill name

4. **Skill Executor Timing** ✅
   - Added 0.15s delay after `face` actions (turn animation)
   - Added 0.2s delay after `use_tool` actions (swing animation)

### Critical Bug Discovered

**POSITIONING BUG (ROOT CAUSE of phantom failures):**
- Agent moves TO crop tile instead of ADJACENT to it
- Can't water/harvest a crop you're standing ON in Stardew Valley
- Hints say "move to nearest crop" but should say "move NEXT TO crop"

### Files Modified
| File | Change |
|------|--------|
| `unified_agent.py` | Clear_* detection fix, refill hints |
| `memory/daily_planner.py` | Shipping task added |
| `skills/executor.py` | Timing delays, logging |
| `docs/NEXT_SESSION.md` | Updated for Session 46 |

### Next Session Priority
1. Fix positioning logic (CRITICAL)
2. Test timing fixes
3. Test harvest + ship flow

---

## 2026-01-10 - Session 44: State-Change Detection + Daily Planning

**Agent: Claude (Opus)**

### Major Progress

1. **State-Change Detection** ✅
   - Captures state snapshot before skill execution
   - Verifies actual state change after execution
   - Adaptive threshold: 2 consecutive phantom failures → hard-fail
   - Records lessons for learning system
   - Tested: `PHANTOM_FAIL: water_crop (34x)` confirmed detection working

2. **Daily Planning System** ✅
   - New module: `memory/daily_planner.py`
   - Auto-generates task list on day change
   - Standard daily routine (Tim's requirements):
     1. Incomplete from yesterday → complete first
     2. Crops dry → water (CRITICAL)
     3. Crops ready → harvest (HIGH)
     4. Seeds in inventory → plant (HIGH)
     5. Nothing else → clear debris (MEDIUM)
   - VLM-based reasoning for intelligent planning

3. **VLM Text Reasoning** ✅
   - Added `reason()` method to UnifiedVLM for text-only planning
   - Used by daily planner for intelligent task prioritization

4. **Codex UI Tasks** ✅
   - Daily Plan Panel implemented
   - Action Failure Panel implemented

### Files Modified/Created
| File | Change |
|------|--------|
| `src/python-agent/unified_agent.py` | State detection, VLM reason(), daily plan trigger |
| `src/python-agent/memory/daily_planner.py` | NEW - Task planning module |
| `src/python-agent/memory/__init__.py` | Added daily_planner exports |
| `src/ui/app.py` | Daily plan API endpoint |
| `src/ui/static/app.js` | Daily plan panel rendering |
| `src/ui/static/app.css` | Panel styles |
| `docs/CODEX_TASKS.md` | UI task assignments |

### Key Code Locations
| Feature | File | Lines |
|---------|------|-------|
| `_capture_state_snapshot()` | unified_agent.py | 2162-2219 |
| `_verify_state_change()` | unified_agent.py | 2221-2293 |
| `_phantom_failures` tracking | unified_agent.py | 1731-1734 |
| `DailyPlanner` class | memory/daily_planner.py | All |
| `VLM.reason()` | unified_agent.py | 416-446 |
| Day change trigger | unified_agent.py | 2472-2483 |

### Test Results (Session 45)
- State detection confirmed working: 34 phantom failures caught
- 203 actions, 119 VLM cycles in ~11 min test
- Daily planner not yet tested (no day change during test)

### What Needs Testing
- [ ] Daily planner triggers on day change (🌅 marker)
- [ ] Hard-fail after 2 consecutive phantom failures (💀 marker)
- [ ] Task completion tracking

---

## 2026-01-08 - Session 3: SMAPI Mod Movement System

**Agent: Claude (Opus)**

### Major Progress
1. ✅ **SMAPI GameBridge mod fully functional**
   - HTTP API on port 8790 (health, state, action endpoints)
   - State reader: player position, time, energy, inventory, location, NPCs
   - Action executor: warp, face, move_direction, use_tool, interact

2. ✅ **Simplified to single-player control**
   - Removed P2/co-op complexity
   - AI controls Game1.player (Rusty) directly
   - Human can join as P2 via split-screen when desired

3. ✅ **Direct movement system implemented**
   - `move_direction` action moves player tile-by-tile
   - Collision detection added (checks `isTilePassable`)
   - Fixed `ActionExecutor.Update()` not being called in game loop
   - Fixed pixel/tile offset calculation for player.Position

4. ✅ **Location warping for debug/testing**
   - `warp_location` action with 23 preset spawn points
   - `warp_to_farm`, `warp_to_house` shortcuts

### Key Bug Fixes
| Bug | Root Cause | Fix |
|-----|------------|-----|
| Movement queued but never executed | `_actionExecutor.Update()` not called | Added to `OnUpdateTicked` |
| Player clipped into walls | Direct position movement ignored collision | Added `isTilePassable` check |
| Movement to wrong position | player.Position is sprite top-left, not tile center | Calculate offset from current TilePoint |

### Files Modified/Created
- `src/smapi-mod/StardewAI.GameBridge/ModEntry.cs` - Added Update() call
- `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs` - Movement + collision
- `src/smapi-mod/StardewAI.GameBridge/Models/ActionCommand.cs` - Added Location field
- `scripts/vcontroller_daemon.py` - Created (not needed, mod handles movement)
- `scripts/keyboard_daemon.py` - Created (not needed, mod handles movement)

### What Works Now
```bash
# Check game state
curl http://localhost:8790/state

# Move Rusty
curl -X POST http://localhost:8790/action -d '{"action":"move_direction","direction":"down","tiles":2}'

# Warp to location
curl -X POST http://localhost:8790/action -d '{"action":"warp_location","location":"Town"}'
```

### What Needs Testing
- [ ] Movement with fixed pixel offset (just rebuilt, not tested)
- [ ] Walking through doors (triggers location warp)
- [ ] Python agent integration with mod API

### Architecture Decision: Mod-Based Movement
Abandoned vgamepad/keyboard injection approach:
- Virtual controllers not detected by game reliably
- xdotool can't send keys to Proton/Wine windows
- **Solution:** SMAPI mod directly manipulates `Game1.player.Position`

### Next Session Priorities
1. Test fixed movement (pixel offset fix)
2. Walk Rusty out the farmhouse door
3. Connect Python agent to mod HTTP API
4. Test VLM perception → mod action loop

---

## 2026-01-07 - Session 2 (Late Night)

**Agent: Claude (Opus)**

### Major Progress
1. ✅ Fixed VLM crash bug with tensor-split + vision models
   - Root cause: KV cache reuse (`slot-prompt-similarity`) corrupted GPU 1 memory on second request
   - Fix: Added `-sps 0` flag to disable slot prompt similarity in `start-llama-server.sh`
2. ✅ P2 character created manually (Rusty is alive!)
3. ✅ VLM perception working reliably (2-6s per inference)
4. ✅ SMAPI 4.3.2 installed
5. ✅ .NET SDK 8.0 installed
6. ✅ Started SMAPI GameBridge mod (project structure created)

### Issues Discovered
| Issue | Root Cause | Status |
|-------|------------|--------|
| VLM crashes on 2nd request | KV cache reuse bug with vision+tensor-split | ✅ FIXED with `-sps 0` |
| Rusty keeps going to bed | VLM misperceives bed proximity as "need to sleep" | Needs prompt tuning |
| Movement overshoots | Duration too long (1s instead of 0.2s) | Partially fixed in prompt |
| Can't exit house | VLM gives wrong directions (up vs down) | Needs SMAPI mod for pathfinding |

### Key Insight: Pure Vision Has Limits
The VLM can perceive the game state but struggles with:
- Precise navigation (can't tell exact tile position)
- Direction confusion (goes toward bed instead of door)
- Spatial reasoning in tight spaces

**Solution: SMAPI GameBridge mod** will provide:
- Exact player tile position and facing direction
- A* pathfinding to any location
- High-level commands ("move to tile 10,15" instead of raw joystick)

### Files Modified
- `scripts/start-llama-server.sh` - Added `-sps 0` flag
- `config/settings.yaml` - Added short movement instructions to prompt
- `src/python-agent/manual_controller.py` - Created for manual gamepad testing

### Where We Left Off
- SMAPI installed, .NET SDK installed
- GameBridge mod project started (`src/smapi-mod/StardewAI.GameBridge/`)
- Need to complete: ModEntry.cs, HTTP server, game state reader, action executor

### Next Session
1. **Complete SMAPI GameBridge mod:**
   - ModEntry.cs - SMAPI entry point
   - HttpServer.cs - Embedded HTTP server
   - GameStateReader.cs - Read player position, time, energy, etc.
   - ActionExecutor.cs - Execute high-level actions
2. Build and deploy mod to Stardew Valley Mods folder
3. Update Python agent to use mod API instead of raw gamepad
4. Test Rusty with precise pathfinding

### Critical Settings to Remember
```bash
# LLama server MUST use -sps 0 for vision models with tensor-split
./scripts/start-llama-server.sh  # Already includes the fix

# Stardew Valley paths
GAME_DIR="/home/tim/.steam/debian-installation/steamapps/common/Stardew Valley"
MODS_DIR="$GAME_DIR/Mods"
```

---

## 2026-01-07 - Session Start

**Agent: Claude (Opus)**

### Status
- Unified agent complete and ready for testing
- LLama server script updated with crash prevention (post GPU lockup)
- Game is loaded, ready for first live test

### Current Focus
- Testing perception accuracy with live game
- Tuning RUSTY prompt based on actual VLM output
- Validating gamepad actions work in co-op

### For Codex
- What UI/memory systems are you building?
- Do you need structured data from the agent (perception results, action history)?
- Should we define an interface for agent state → UI?

### Architecture Decisions
- Single VLM approach (Qwen3-VL) handles perception + planning in one call
- 2-second think interval as default
- JSON output format for structured perception + actions

### Completed This Session
1. ✅ LLama-server running (Qwen3VL-30B-A3B on port 8780)
2. ✅ Perception working - VLM correctly identifies location, time, energy, tools
3. ✅ JSON repair logic added for malformed VLM output
4. ✅ Virtual gamepad works - Player 2 can join co-op
5. ✅ Steam Input enabled (required for P2 controller recognition)

### Issues Encountered & Solutions
| Issue | Solution |
|-------|----------|
| Controller bound to P1 | Enable Steam Input in game properties, set Gamepad Mode to "Force On" |
| P2 character creation text entry | Keyboard goes to P1 only - need Steam overlay keyboard or randomize |
| JSON parse failures | Added `_repair_json()` to fix missing commas |

### Where We Left Off
- Player 2 at character creation screen
- Name/Favorite Thing fields still empty
- Need to either: use randomize dice, Steam overlay keyboard, or skip

### Next Session
1. Complete P2 character creation (use randomize or find workaround)
2. Test full agent loop with gamepad control
3. Verify split-screen perception captures P2's view correctly

### Tools Created
- `src/python-agent/controller_gui.py` - On-screen virtual controller (didn't work due to focus issues)
- `xdotool` installed - Can type text but goes to P1 only

### Key Learnings
- vgamepad creates virtual Xbox 360 controller that works system-wide
- Each vgamepad instance may create new device - keep persistent when possible
- Steam Input required for games to recognize virtual controller
- Keyboard input always goes to Player 1 in split-screen

### Roadmap: Making Rusty Better

**Phase 1: Vision-Only (Current)**
- Pure VLM perception from screenshots
- Good for: initial testing, understanding game flow
- Limitations: OCR errors, can't see inventory details, slow

**Phase 2: SMAPI Mod Integration (Planned)**
- SMAPI mod provides structured JSON game state
- Exact values: position, energy, inventory, time, NPCs
- VLM focuses on high-level planning, not pixel reading
- Hybrid approach: VLM for context + SMAPI for precision

**Phase 3: Memory & Learning**
- Codex building memory systems
- Track what works, what fails
- Learn farm layout, NPC schedules, crop timing
- Persistent knowledge across sessions

**Phase 4: Advanced Behaviors**
- Multi-step planning (mine runs, festival prep)
- Social optimization (gift giving, friendship)
- Economic decisions (what to plant, when to sell)

---
