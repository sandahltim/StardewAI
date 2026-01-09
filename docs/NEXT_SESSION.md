# Next Session - StardewAI

**Last Updated:** 2026-01-08 Session 17 by Claude
**Status:** Day 4 - ALL 9 CROPS PLANTED! 🌱

---

## Session 17 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| Rain Bug Fix | ✅ Wet tilled soil was showing "WATERED-DONE" |
| Aggressive Plant Prompts | ✅ "🌱🌱🌱 PLANT NOW!" with emojis |
| No Seeds Check | ✅ Don't show plant prompt if no seeds |
| go_to_bed Fix | ✅ Now uses `Game1.NewDay(0.0f)` |
| Game Knowledge DB | ✅ 12 NPCs + 36 crops scraped from wiki |
| Spatial Map Task | ✅ Assigned to Codex |

### KEY FIX: Rain Bug
When it rained, empty tilled soil showed `state="watered"` with `canPlant=true`.
Agent saw "TILE: WATERED - DONE!" and moved on without planting.

**Fix:** Check `canPlant` - if true, soil is wet but EMPTY, show "NEEDS PLANTING!"

### KEY FIX: No Seeds Check
Agent was trying to plant with empty inventory (all seeds used).
**Fix:** Check inventory for seeds before showing "PLANT NOW" prompt.

### Game State (End of Session)
- **Day:** 4, 11:40 AM
- **Crops:** 9 parsnips (3 harvest Day 6, 3 Day 7, 3 Day 8)
- **Seeds:** 0 remaining (all planted!)
- **Next:** Water crops, sleep to Day 6, harvest

### Spatial Map Task (Assigned to Codex)
Agent tills but forgets where → can't find planted crops to water.
Need persistent spatial memory:
- SQLite/JSON map of tile states
- `/api/spatial-map` endpoint
- Query: "where are unwatered planted tiles?"

---

## Session 16 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| Day 1→2 Transition | ✅ Manual sleep (agent struggled) |
| Day 2 Watering | ✅ All 3 crops watered |
| Location Nav Hints | ✅ Added farmhouse door/farm directions |
| `go_to_bed` Action | ✅ Added to SMAPI mod |
| `sleep` Agent Action | ✅ Added to unified_agent.py |

### KEY FIX: go_to_bed Action
Agent was getting stuck finding farmhouse door and bed.
- Added `go_to_bed` SMAPI action that:
  - Warps to FarmHouse if not there
  - Positions player at bed
  - Triggers sleep dialog
- Agent can now call `{"action": "sleep"}` or `{"action": "go_to_bed"}`
- **Note:** Requires game restart for SMAPI mod changes!

### KEY FIX: Location Navigation Hints
Agent didn't know where doors/exits were located.
- FarmHouse: `🚪 EXIT: Door is X tiles DOWN, Y tiles LEFT`
- Farm: `🏠 FARMHOUSE DOOR: X tiles away (direction)`
- Helps VLM navigate more efficiently

### MEMORY SYSTEMS (Exist but Empty)
- ChromaDB episodic memory: 0 items stored
- SQLite game_knowledge.db: 0 bytes
- Infrastructure ready but needs population

### Day 2 Progress
- ✅ 3 parsnips watered
- Time: 2:10 PM
- Crops: 3 days until harvest (Day 5)

---

## Session 15 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| Tool Hallucination Fix | ✅ Explicit "🔧 EQUIPPED: X" in prompt |
| Tile Centering Fix | ✅ Snap to tile coords on move complete |
| Day 1 Test | ✅ 3 parsnips planted & watered |
| Codex UI Features | ✅ Stats panel, latency graph, crop countdown |

### KEY FIX: Tool Hallucination
VLM was guessing equipped tool from screenshot (unreliable).
- VLM thought it had scythe when actually holding parsnip seeds
- Now every prompt includes: `🔧 EQUIPPED: ToolName (slot X)`
- Agent correctly selects tools based on explicit context

### KEY FIX: Tile Centering
Player was landing on tile edges after movement, causing tool misalignment.
- Added `player.Position = (tileX * 64, tileY * 64)` snap when reaching destination
- Both path-following and directional movement now snap to tile coords
- **Note:** Requires game restart for SMAPI mod changes

### DAY 1 TEST RESULTS
- ✅ Exit farmhouse (navigated out successfully)
- ✅ Navigate to farm (position 70,18)
- ✅ Select seeds (slot 5 correctly)
- ✅ Plant 3 parsnips
- ✅ Select watering can (slot 2 correctly)
- ✅ Water all 3 crops
- Energy: 232/270 | Watering can: 34/40

---

## 🧪 FULL FARMING CYCLE TEST

### Prerequisites
```bash
# 1. Fresh Stardew Valley save with farmer "Rusty" (or continue existing)
# 2. RESTART GAME if SMAPI mod was updated (centering fix needs restart)
# 3. Verify services:
curl http://localhost:8780/health     # llama-server
curl http://localhost:8790/state      # SMAPI mod
curl http://localhost:9001/api/status # UI server
```

### Test Phases

#### Phase 1: Clear → Till → Plant → Water
```bash
python src/python-agent/unified_agent.py --ui --goal "Clear weeds, till soil, plant parsnip seeds, water crops"
```

| Step | Action | Tool | Success Indicator |
|------|--------|------|-------------------|
| 1 | Clear weeds | Scythe (4) | Weeds removed, debris gone |
| 2 | Till soil | Hoe (1) | Brown tilled squares visible |
| 3 | Plant seeds | Seeds (5) | Small seedling sprites appear |
| 4 | Water crops | Can (2) | Soil darkens, can level decreases |

#### Phase 2: Refill Watering Can
```bash
python src/python-agent/unified_agent.py --ui --goal "Refill watering can at water source"
```

| Step | Action | Success Indicator |
|------|--------|-------------------|
| 1 | Navigate to water | "Water is X tiles south" decreasing |
| 2 | Face water | Player facing pond/river |
| 3 | Use watering can | Can level resets to 40/40 |

#### Phase 3: Sleep to Next Day
```bash
python src/python-agent/unified_agent.py --ui --goal "Go to bed and sleep"
```

| Step | Action | Success Indicator |
|------|--------|-------------------|
| 1 | Navigate to farmhouse | Location changes to "FarmHouse" |
| 2 | Find bed | Position near bed coordinates |
| 3 | Interact with bed | Day advances, new morning starts |

#### Phase 4: Harvest (Day 4+)
```bash
python src/python-agent/unified_agent.py --ui --goal "Harvest ready crops and ship them"
```

| Step | Action | Success Indicator |
|------|--------|-------------------|
| 1 | Navigate to crops | Position near planted area |
| 2 | Harvest | Parsnip added to inventory |
| 3 | Navigate to shipping bin | Position near (71, 14) |
| 4 | Ship | Parsnip removed, money pending |

### Success Criteria
- [ ] No JSON parse errors
- [ ] Agent selects correct tools (🔧 EQUIPPED shows in log)
- [ ] Crops planted and watered (SMAPI shows watered=true)
- [ ] Watering can refilled (40/40)
- [ ] Day advances via sleeping
- [ ] Harvest successful (Day 4+)

### Known Issues
- **Tile centering**: Requires game restart after mod update
- **Farmhouse exit**: May take several attempts to find door
- **Bed interaction**: May need to stand on correct tile

---

## Session 14 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| JSON Truncation Fix | ✅ Root cause: 4K context limit |
| 8K Context | ✅ llama-server updated |
| max_tokens 1500 | ✅ Response headroom |
| Debug Logging | ✅ Failed JSON saved to file |
| Codex UI Features | ✅ VLM errors, nav intent, chat |

### KEY FIX: 8K Context Window
The VLM was truncating JSON responses mid-field because:
- Image: ~1000 tokens
- System prompt: ~2500 tokens
- User context: ~500 tokens
- Total input: ~4000 tokens (hitting 4K limit!)
- Response room: ~100 tokens (truncated!)

**Solution:** Increased `-c 4096` → `-c 8192` in llama-server startup script.

### VERIFIED WORKING
- ✅ JSON parsing succeeds (finish_reason: stop)
- ✅ Agent exits farmhouse
- ✅ Agent follows "water is south" guidance
- ✅ Water distance decreasing (19 → 14 tiles during test)
- ✅ Priority message: "WATERING CAN EMPTY! REFILL FIRST!"

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, **8K context** |
| SMAPI mod | Working | Port 8790, all features |
| UI Server | Working | Port 9001, Codex features |
| JSON Parsing | **Fixed** | 8K context prevents truncation |
| Navigation | Improved | Following directions to water |
| Priority Logic | Working | Shows refill when can empty |

---

## Next Steps (Priority Order)

### HIGH - Complete Farming Cycle
1. **Refill test** - Does agent reach water and use_tool to refill?
2. **Watering test** - Does agent water crops after refill?
3. **Harvest test** - Day 8+ crops should be ready

### MEDIUM - Navigation Polish
4. **Obstacle avoidance** - Agent still repeats blocked moves
5. **Warp fallback** - If stuck 10+ times, use warp command

### LOW - Optimization
6. **Reduce system prompt** - 9500 chars is large, could trim
7. **Energy tracking** - Warn when low, suggest bed

---

## Files Changed (Session 14)

### `scripts/start-llama-server.sh`
- **Line 147:** `-c 4096` → `-c 8192` (8K context)

### `config/settings.yaml`
- **Line 113:** `max_tokens: 600` → `max_tokens: 1500`

### `src/python-agent/unified_agent.py`
- **Lines 424-431:** Debug logging for failed JSON (saves to /tmp/vlm_failed_json.txt)

### Codex UI Changes
- `src/ui/app.py` - VLM error tracking endpoints
- `src/ui/static/app.js` - Error display, nav intent, chat integration
- `src/ui/static/app.css` - Styling for new panels
- `src/ui/templates/index.html` - New UI sections

---

## Quick Start

```bash
# Restart llama-server with 8K context (if not already)
pkill -f "llama-server.*8780"
./scripts/start-llama-server.sh

# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Refill watering can and water crops"

# Watch for:
# - No JSON parse errors
# - "Water is X tiles south" decreasing
# - Agent reaching water and using tool
```

---

## Commits
- `d7826f8` - Session 14: Fix JSON truncation with 8K context

---

*Session 14: Fixed JSON truncation by increasing llama-server context from 4K to 8K. Agent now parses responses correctly and navigates toward water.*

— Claude (PM)
