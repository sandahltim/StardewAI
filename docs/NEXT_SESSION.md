# Next Session - StardewAI

**Last Updated:** 2026-01-09 Session 19 by Claude
**Status:** Day 7 - Bug Fixes + Face Action Issue

---

## Session 19 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| Seed Slot Detection | ✅ Dynamic - no more hardcoded slot 5 |
| Face Action Hints | ✅ Added for adjacent crops (1 tile away) |
| Face vs Move Guidance | ✅ Added to system prompt |
| UI Restart | ✅ Codex's Spatial Map UI working |

### KEY FIXES

**Seed Slot Detection (Bug Fix):**
Agent was hardcoded to use `select_slot 5` for seeds, but Sap was in slot 5.
- Fix: Now dynamically finds seed slot from inventory
- Shows actual seed name: `>>> PLANT NOW! DO: select_slot 3 (Parsnip Seeds)...`

**Face Action for Adjacent Tiles:**
Agent kept using `move` instead of `face` when crop was 1 tile away.
- Fix: Navigation hints now say `face {direction}, use_tool` for adjacent targets
- Added "FACE vs MOVE - CRITICAL DISTINCTION" section to system prompt

### KNOWN ISSUES (Still Open)
1. **Agent still prefers `move` over `face`** - VLM ignores face hints
2. **Agent doesn't harvest ready crops** - just waters them
3. **Desync issues** - commands sent but character doesn't move (requires game restart)
4. **Some crops died** - 3 of 8 parsnips withered (99999 days = dead)

### Game State (End of Session)
- **Day:** 7, 12:30 PM
- **Crops:** 7 total (3 dead, 4 alive)
- **Watered:** 4/7
- **Ready to Harvest:** 0 (nearest tomorrow if watered)
- **Watering Can:** 13/40
- **Energy:** 252/270

---

## Session 18 Results (Previous)

### COMPLETED
| Feature | Status |
|---------|--------|
| Bedtime Hints | ✅ Time-based (8PM, 10PM, midnight) + energy-based |
| Crop Protection | ✅ Warns "DO NOT use Scythe/Hoe on crop!" |
| Debris Clearing | ✅ Suggests clearing when farming done |
| Water = Resource | ✅ Shows "💧 WATER" not "BLOCKED (water)" |
| Codex Spatial Map | ✅ Verified implementation |

---

## Quick Start

```bash
# 1. Start services (if not running)
./scripts/start-llama-server.sh  # Port 8780
# SMAPI mod runs with game on port 8790
source venv/bin/activate && python src/ui/app.py &  # Port 9001

# 2. Verify
curl http://localhost:8780/health     # llama-server
curl http://localhost:8790/state      # SMAPI mod
curl http://localhost:9001/api/status # UI server

# 3. Run agent
python src/python-agent/unified_agent.py --ui --goal "Water crops and harvest ready ones"
```

---

## Next Steps (Priority Order)

### HIGH - Fix Agent Behavior
1. **Make agent use `face` action** - currently ignores hints
2. **Fix harvest behavior** - agent should pick ready crops, not water them
3. Water remaining 3 crops on Day 7
4. Sleep to Day 8 and harvest

### MEDIUM - Navigation/Desync
5. Investigate desync issue (commands succeed but no movement)
6. Faster debris avoidance
7. Consider alternative to `move` (maybe `move_direction` with tiles?)

### LOW - Architecture
8. Tool abstraction layer (user suggestion)
9. Crop health indicator in UI (dead vs alive)

---

## Files Changed (Session 19)

### `src/python-agent/unified_agent.py`
- **Lines 666-683:** Dynamic seed slot detection (was hardcoded slot 5)
- **Lines 715-732:** Same fix for wet tilled soil case
- **Lines 755-770:** Adjacent crop detection - suggest `face` for 1-tile distance
- **Lines 795-810:** Same fix for unwatered crop navigation

### `config/settings.yaml`
- **Lines 216:** Enhanced `face` action description
- **Lines 227-232:** NEW: "FACE vs MOVE - CRITICAL DISTINCTION" section

---

*Session 19: Fixed seed slot bug (was hardcoded), added face action hints for adjacent tiles, but VLM still ignores them. Some crops died from desync issues. Need to fix harvest detection next.*

— Claude (PM)
