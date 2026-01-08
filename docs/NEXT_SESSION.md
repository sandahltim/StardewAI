# Next Session - StardewAI

**Last Updated:** 2026-01-08 Session 12 by Claude
**Status:** Core improvements done, priority logic needs work

---

## Session 12 Results

### COMPLETED
| Feature | Status |
|---------|--------|
| Action History (10 actions) | ✅ Working |
| Blocked Action Tracking | ✅ Working |
| Repetition Warning (3+ repeats) | ✅ Working |
| Location Verification Header | ✅ Working |
| Harvest Detection | ✅ Working |
| Shipping Bin Distance/Direction | ✅ Working |
| Codex UI: Harvest Indicator | ✅ Completed |
| Codex UI: Energy Bar | ✅ Completed |
| Codex UI: Action History Panel | ✅ Completed |

### ISSUE IDENTIFIED
**Empty watering can priority** - When can is empty, agent gets conflicting messages:
- "WATERING CAN EMPTY! Water is 16 tiles south"
- "14 CROPS NEED WATERING! Nearest: 1 UP"

VLM oscillates between trying to water (can't, empty) and going to crops. Needs clear priority logic: **IF can empty → GO TO WATER FIRST, ignore crop directions.**

### NEXT SESSION PRIORITY
Fix the priority logic cleanly:
1. Empty can + crops to water → ONLY show water refill message
2. Add a simple task priority system the VLM can follow

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B |
| SMAPI mod | Working | Port 8790, all features |
| UI Server | Working | Port 9001, all Codex features |
| Action History | Working | 10-action history with STOP warning |
| Location Header | Working | "📍 LOCATION: Farm at (x, y)" |
| Shipping Bin Info | Working | Distance + direction on Farm |
| Harvest Detection | Working | "🌾 HARVEST TIME!" when on ready crop |

---

## Next Steps (Priority Order)

### HIGH - Fix Priority Logic
1. **Empty can priority** - MUST refill before any crop guidance
2. **Task priority list** - Give VLM clear priority order to follow

### HIGH - Extended Testing
3. **Full farming cycle** - Water → refill → water more
4. **Crop harvesting** - Test when parsnips mature (Day 8)
5. **Shipping bin** - Navigate and sell

### MEDIUM - Agent Intelligence
6. **Goal-based planning** - Multi-step planning (harvest → ship → sleep)
7. **Energy management** - Track stamina, know when to rest

### ROADMAP - Future Features
8. **Rusty UI responses** - Agent responds to user messages in team chat
9. **Multi-day autonomy** - Full day cycle: wake → farm → ship → sleep

---

## Files Changed (Session 12)

### Python Agent (`unified_agent.py`)
- Added `action_context` parameter to `think()` method
- Added action history building with repetition warning
- Blocked actions now recorded to history
- Added location header to `format_surroundings()`
- Added shipping bin distance/direction
- Added harvest detection for ready crops
- Increased action history from 3 to 10 actions

### Key Code Locations
- Lines 1307-1330: Action context building with STOP warning
- Lines 1264-1271: Blocked action recording
- Lines 691-723: Location header + shipping bin info
- Lines 580-582: Harvest detection

---

## Quick Start

```bash
# Services should be running
curl -s http://localhost:8790/state | jq '{water: .data.player.wateringCanWater, unwatered: [.data.location.crops[] | select(.isWatered == false)] | length}'

# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water all crops"
```

---

*Session 12: Added action history, location verification, harvest detection, shipping bin guidance. Identified priority logic issue with empty watering can.*

— Claude (PM)
