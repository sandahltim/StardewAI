# Next Session - StardewAI

**Last Updated:** 2026-01-08 Session 12 by Claude
**Status:** Decision-making improvements implemented, ready for extended test

---

## Session 12 Results

### IMPROVEMENTS MADE
| Fix | Description |
|-----|-------------|
| **Action History** | VLM now sees last 10 actions with prominent STOP warning on 3+ repeats |
| **Blocked Action Tracking** | Failed moves recorded as "BLOCKED: move right (hit wall)" |
| **Location Verification** | Explicit "📍 LOCATION: Farm at (69, 18)" prevents hallucination |
| **Repetition Detection** | Loop warning triggers after 3 repeated actions in last 5 |

### VERIFIED WORKING
- Codex UI features: Crop Status Summary, Location Display, Action Repeat Detection
- All 15 crops watered (from Session 11)
- Action history tracking and logging
- Repetition detection with VLM acknowledgment ("I'm stuck in a loop")

### TESTING OBSERVATIONS
- VLM recognizes when stuck ("I need to break this pattern")
- Takes 2-3 cycles for VLM to change behavior after warning
- Blocked moves now recorded so VLM learns from failed attempts

---

## What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| llama-server | Running | Port 8780, Qwen3VL-30B |
| SMAPI mod | Working | Port 8790, all features |
| UI Server | Working | Port 9001, all Codex features |
| Action History | **NEW** | 10-action history sent to VLM |
| Location Header | **NEW** | Explicit location prevents hallucination |
| Repetition Detection | **NEW** | Warns on 3+ repeated actions |
| Crop Watering | Verified | 15/15 crops watered |

---

## Next Steps (Priority Order)

### HIGH - Extended Testing
1. **Full farming cycle** - Run agent for 10+ minutes, verify loop-breaking works
2. **Crop harvesting** - Test when parsnips mature (Day 8-9, 1-4 days left)
3. **Shipping bin** - Navigate to (71,14) and sell harvested crops

### MEDIUM - Agent Intelligence
4. **Goal-based planning** - Add multi-step goal planning (harvest → ship → sleep)
5. **Energy management** - Track stamina, know when to rest
6. **Time awareness** - React to time of day (morning = farm, evening = ship/sleep)

### LOW - Polish
7. **NPC interaction** - Use knowledge DB for gifts/schedules
8. **Weather adaptation** - Skip watering on rainy days (already in reasoning!)

---

## Files Changed (Session 12)

### Python Agent (`unified_agent.py`)
- Added `action_context` parameter to `think()` method
- Added action history building with repetition warning
- Blocked actions now recorded to history
- Added location header to `format_surroundings()`
- Increased action history from 3 to 10 actions

Key code sections:
- Lines 1307-1330: Action context building with STOP warning
- Lines 1264-1271: Blocked action recording
- Lines 666-676: Location verification header

---

## Quick Start

```bash
# Services should be running already

# Check state
curl -s http://localhost:8790/state | jq '{location: .data.location.name, pos: {x: .data.player.tileX, y: .data.player.tileY}}'

# Test format_surroundings (shows location + action context)
python -c "
import sys; sys.path.insert(0, 'src/python-agent')
from unified_agent import ModBridgeController
ctrl = ModBridgeController('http://localhost:8790')
print(ctrl.format_surroundings())
"

# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Water crops and explore"

# Monitor for repetition warnings
tail -f /tmp/*.log | grep -E "REPETITION|STOP|📜"
```

---

*Session 12: Implemented action history, blocked action tracking, and location verification. VLM now recognizes when stuck and attempts to change behavior.*

— Claude (PM)
