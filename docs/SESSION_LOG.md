# StardewAI Session Log

Coordination log between Claude (agent/prompt) and Codex (UI/memory).

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
