# Session 115: Fix Batch Farm Chores

**Last Updated:** 2026-01-15 Session 114 by Claude
**Priority:** CRITICAL - Batch farming actions not executing in game

---

## Session 114 Summary

### Issues Identified

#### 1. SMAPI Cache Staleness (FIXED)
- `/farm` endpoint returns cached data that only refreshes every 15 ticks (~250ms)
- Batch water loop saw crops as unwatered even after watering them
- **Fix Applied:** Track watered crops locally in `watered_this_batch` set

#### 2. Menu Blocking Warps (FIXED)
- Open GameMenu blocked warp actions, causing infinite warp loop
- **Fix Applied:** Dismiss menus before warping + retry limit (5 attempts)

#### 3. Action Parameter Key Mismatch (FIXED)
- `select_item_type` expected `type` or `item_type` param key
- Code sent `value` as key
- **Fix Applied:** Now accepts all three: `value`, `type`, `item_type`

#### 4. Actions Not Executing In-Game (UNRESOLVED)
- Logs show "12 tilled, 12 planted" but only 2 crops exist
- Seeds still at 13 (unchanged from before)
- Actions are being sent to SMAPI but not affecting game state
- **Root Cause:** Unknown - needs investigation

---

## Immediate Next Steps

### 1. Debug Action Execution
```bash
# Run agent with verbose action logging
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Plant seeds" 2>&1 | tee /tmp/debug.log

# In another terminal, watch SMAPI log
tail -f ~/.local/share/StardewValley/ErrorLogs/SMAPI-latest.txt | grep -E "Action|Select|Tool"
```

**Questions to answer:**
- Is SMAPI receiving the actions?
- Is SMAPI returning success but not executing?
- Is player in wrong position when tool used?

### 2. Test Individual Actions
```bash
# Test select_item_type (fixed)
curl -s -X POST http://localhost:8790/action -H "Content-Type: application/json" \
  -d '{"action":"select_item_type","itemType":"Hoe"}'

# Test face direction
curl -s -X POST http://localhost:8790/action -H "Content-Type: application/json" \
  -d '{"action":"face","direction":"north"}'

# Test use_tool
curl -s -X POST http://localhost:8790/action -H "Content-Type: application/json" \
  -d '{"action":"use_tool","direction":"north"}'
```

### 3. Check SMAPI Action Executor
Look at `src/smapi-mod/StardewAI.GameBridge/ActionExecutor.cs`:
- Does `UseTool()` verify player position?
- Does it check if tool can be used on target tile?
- Does it return success even when action fails?

---

## Code Changes Made in Session 114

### unified_agent.py

1. **Menu dismissal before batch chores** (line ~3402)
   - Dismisses any open menu at start of `_batch_farm_chores`

2. **Warp retry with limit** (line ~3480)
   - While loop with max 5 attempts
   - Checks for blocking menu each iteration
   - Returns early if warp fails

3. **Batch water tracking** (line ~3049)
   - Added `watered_this_batch` set
   - Filters out already-watered crops
   - Prevents re-watering due to stale cache

4. **select_item_type param fix** (line ~1849)
   - Now accepts `value`, `type`, or `item_type` as param key
   - Logs error if no valid key found

5. **Improved till+plant logging** (line ~3728)
   - Logs each till/plant action with coordinates
   - Added move verification after move_to
   - Increased delays for tool animations

---

## Known Working

- ✓ SMAPI mod loads and responds on port 8790
- ✓ `/farm` endpoint returns crop data
- ✓ `/state` endpoint returns player state
- ✓ Watering loop exits correctly (tracked locally)
- ✓ ResourceClumps (stumps/boulders) are avoided

## Known Broken

- ✗ Till/plant actions not affecting game state
- ✗ Logs show success but seeds unchanged
- ✗ Player may not be in correct position for tool use
- ✗ **NO VERIFICATION** - counters increment without checking if action worked

## Critical Architecture Flaw

We have FULL SMAPI data access but ZERO verification:

```python
# Current (broken):
self.controller.execute(Action("use_tool", ...))  # Till
await asyncio.sleep(0.5)
tilled += 1  # ASSUMES SUCCESS WITHOUT CHECKING!

# Should be:
self.controller.execute(Action("use_tool", ...))  # Till
await asyncio.sleep(0.5)
# VERIFY: Check if tilled tile exists at target
farm_data = self.controller.get_farm()
tilled_tiles = {(t['x'], t['y']) for t in farm_data.get('tilledTiles', [])}
if (x, y) in tilled_tiles:
    tilled += 1
else:
    logging.error(f"Till failed at ({x},{y}) - tile not tilled!")
```

Same pattern needed for:
- Plant verification: Check `crops` array for new crop at position
- Water verification: Check `isWatered` status
- Move verification: Check player `tileX/tileY` (partially done)

---

## Quick Start Commands

```bash
# Activate environment
cd /home/tim/StardewAI
source venv/bin/activate

# Start UI server (port 9001)
python src/ui/app.py

# Start llama server (port 8780)
./scripts/start-llama-server.sh

# Rebuild SMAPI mod
cd src/smapi-mod/StardewAI.GameBridge && dotnet build && cd ../../..

# Run agent
python src/python-agent/unified_agent.py --goal "Plant seeds"
```

---

## Architecture Context

```
Player Action Flow:
Python -> HTTP POST -> SMAPI Mod -> ActionExecutor -> Game API
          ↓               ↓             ↓
       /action      HttpServer    UseTool(), etc.
```

The disconnect appears to be between ActionExecutor returning "success" and the game actually performing the action.

---

## Session 114 Summary

**3 bugs fixed, 1 critical bug unresolved.**

The batch farm chores are sending commands but they're not affecting game state. Need to trace the action execution through SMAPI logs to understand where the disconnect happens.

-- Claude
