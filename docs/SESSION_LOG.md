# StardewAI Session Log

Coordination log between Claude (agent/prompt) and Codex (UI/memory).

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
