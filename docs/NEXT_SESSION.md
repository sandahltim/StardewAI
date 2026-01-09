# Next Session - StardewAI

**Last Updated:** 2026-01-08 Session 14 by Claude
**Status:** Ready for Day 1 full test run

---

## 🧪 DAY 1 TEST PROTOCOL

### Prerequisites
```bash
# 1. Start fresh Stardew Valley save (new farmer named "Rusty")
# 2. Verify services running:
curl http://localhost:8780/health   # llama-server (8K context)
curl http://localhost:8790/state    # SMAPI mod
curl http://localhost:9001/api/status  # UI server

# 3. If llama-server not running:
./scripts/start-llama-server.sh
```

### Run Agent
```bash
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Plant and water parsnip seeds"
```

### Expected Day 1 Behavior
| Step | Action | Watch For |
|------|--------|-----------|
| 1 | Exit farmhouse | Moves right toward door, warps if stuck |
| 2 | Navigate to farm | Position changes, finds farmable ground |
| 3 | Clear weeds | Selects scythe (slot 4), swings |
| 4 | Till soil | Selects hoe (slot 1), tills cleared dirt |
| 5 | Plant seeds | Selects parsnip seeds (slot 5), plants |
| 6 | Water | Selects watering can (slot 2), waters |
| 7 | Repeat or rest | Continue farming or head to bed by 12am |

### Success Criteria
- [ ] No JSON parse errors in log
- [ ] Agent exits farmhouse within 2 minutes
- [ ] At least one crop planted and watered
- [ ] Agent responds to obstacles (doesn't repeat same blocked move 10+ times)

### Known Issues to Watch
- **Obstacle repetition**: May try blocked direction 3-5 times before adjusting
- **Tool selection**: Sometimes slow to switch tools
- **Door navigation**: May use warp instead of walking through door

### UI Dashboard (localhost:9001)
- VLM errors panel shows parse success/fail
- Navigation intent shows target + blocked directions
- Action history shows recent moves
- Energy bar shows stamina level

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
