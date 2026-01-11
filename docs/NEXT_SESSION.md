# Session 48: Multi-Day Autonomy Testing

**Last Updated:** 2026-01-10 Session 47 by Claude
**Status:** Action overrides implemented, ready for extended testing

---

## Session 47 Summary

### What Was Completed

1. **Adjacent Move Filter** ✅
   - Added `_filter_adjacent_crop_moves()` method
   - When player is adjacent to crop (dist<=1), removes move actions
   - Replaces with face action toward crop
   - File: `unified_agent.py:2505-2570`

2. **Water Source Precondition** ✅
   - Fixed `adjacent_to: water_source` handler in precondition checker
   - Now correctly checks `blocker == "water"` in surroundings
   - File: `preconditions.py:78-94`

3. **Improved Refill Skill** ✅
   - Auto-equips watering can (select_slot 2) before refilling
   - Added animation delays between actions
   - File: `skills/definitions/farming.yaml:35-59`

4. **Empty Can Override** ✅ (NEW)
   - When watering can empty + at water + VLM outputs water_crop
   - Auto-replaces with `refill_watering_can`
   - File: `unified_agent.py:2572-2623`

5. **Late Night Bed Override** ✅ (NEW - FIXED)
   - When hour >= 23 (11 PM), forces `go_to_bed`
   - Triggers earlier to prevent passing out
   - File: `unified_agent.py:2618-2648`

6. **Empty Can Force Refill** ✅ (FIXED)
   - When empty can + at water, FORCES refill regardless of VLM output
   - Previously only triggered on water_crop, now triggers on ANY action
   - File: `unified_agent.py:2572-2616`

### Action Override Chain

```python
# Applied in sequence before action execution:
filtered_actions = result.actions
filtered_actions = self._fix_late_night_bed(filtered_actions)      # Midnight → bed
filtered_actions = self._fix_empty_watering_can(filtered_actions)  # Empty can → refill
filtered_actions = self._filter_adjacent_crop_moves(filtered_actions)  # Adjacent → face
```

---

## Next Session Priorities

### Priority 1: Verify Overrides Working

Check logs for these markers:
- `🛏️ OVERRIDE: Hour X >= 24, forcing go_to_bed`
- `🔄 OVERRIDE: Watering can empty + at water → replacing water_crop with refill_watering_can`
- `🚫 FILTER: Removing move action - already adjacent to crop`

### Priority 2: Test Full Day Cycle

1. Start fresh day
2. Water crops (with refill if needed)
3. Harvest when ready
4. Ship parsnips (slots 5, 10 have parsnips)
5. Go to bed

### Priority 3: Multi-Day Run

- Current: Day 10
- Crop at (64, 22): 1 day until harvest → ready Day 11
- Goal: Run Day 10 → Day 12 with minimal intervention

---

## Game State (End of Session 47)

| Item | Value |
|------|-------|
| Day | 10, hour 24+ (very late) |
| Player | (75, 30), at water |
| Tool | Watering Can (empty) |
| Crop | (64, 22) - Parsnip, 1 day to harvest |
| Inventory | Parsnips in slots 5, 10 |

---

## Code Changes This Session

| File | Change |
|------|--------|
| `unified_agent.py` | Added 3 filter/override methods, wired to action queue |
| `preconditions.py` | Fixed water_source detection (blocker field) |
| `farming.yaml` | Improved refill_watering_can with auto-equip |

---

## Design Philosophy

**VLM = Planner/Brain, Code = Executor**

The VLM provides high-level decisions and planning. The code handles low-level execution details through:
- **Action overrides**: Catch and fix common VLM mistakes (wrong action, bad timing)
- **Skills**: Multi-step action sequences (face → use_tool → wait)
- **State-based corrections**: Check game state and adjust actions accordingly

This makes objectives easier - VLM just needs to decide WHAT to do, code handles HOW.

---

## Known Issues / Watch For

1. **Slot 2 hardcoded** - Watering can assumed in slot 2. Could break if reorganized.
2. **VLM interpretation** - Still outputs wrong actions sometimes, but overrides catch most cases.
3. **Repetition loops** - Agent can get stuck doing same action. Overrides help but don't fully solve.

---

## Quick Reference

### Test Commands

```bash
# Check game state
curl -s localhost:8790/state | jq '{day: .data.time.day, hour: .data.time.hour, player: {x: .data.player.tileX, y: .data.player.tileY, waterLeft: .data.player.wateringCanWater}}'

# Check surroundings for water
curl -s localhost:8790/surroundings | jq '.data.directions'

# Watch agent logs
tail -f /tmp/agent.log | grep -E "OVERRIDE|FILTER|Executing"

# Run agent
python src/python-agent/unified_agent.py --ui --goal "Farm autonomously"
```

### Override Triggers

| Override | Condition | Result |
|----------|-----------|--------|
| Late night | hour >= 24 | Force `go_to_bed` |
| Empty can at water | waterLeft=0 + water adjacent + water_crop action | Replace with `refill_watering_can` |
| Adjacent crop | dist<=1 to crop + move action | Replace with `face` |

---

## Commits This Session

*(Pending - will commit at end of testing)*

---

*Session 47: Action overrides for robustness - VLM outputs can now be corrected when they conflict with game state*

*— Claude (PM), Session 47*
