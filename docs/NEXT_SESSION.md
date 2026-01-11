# Session 47: VLM Following Positioning Hints

**Last Updated:** 2026-01-10 Session 46b by Claude
**Status:** Positioning hints improved, VLM still sometimes ignores "NO move" instructions

---

## Session 46 Summary

### What Was Completed

1. **Positioning Bug Fixed** ✅ (CRITICAL)
   - Added `_calc_adjacent_hint()` helper method
   - Fixed 6 locations where hints said "move TO crop" instead of "move ADJACENT"
   - Strategy: reduce larger axis by 1 to stop 1 tile away, then face crop
   - Commits: `4f14327`, `7902730`

2. **Edge Cases Added** ✅
   - `dist == 0`: "STEP BACK! move 1 tile any direction, then face crop"
   - `dist == 1`: "ADJACENT! DO: face X, water_crop (NO move!)"

3. **Crops Watered** ✅
   - Day 9: Both parsnips were watered
   - One harvested (parsnips in inventory at slots 5, 10)

### Remaining Issue

**VLM sometimes ignores "NO move" hint and moves anyway.** When adjacent (dist==1), the hint says:
```
💧 ADJACENT! DO: face west, water_crop (NO move!)
```

But VLM still outputs:
```
[1] move: {'direction': 'west', 'tiles': 1}  ← WRONG! Should not move!
[2] water_crop: {}
```

This causes the player to move ONTO the crop, then water_crop fails.

---

## Next Session Priorities

### Priority 1: Fix VLM Hint Interpretation

Options to try:
1. **Stronger hint wording**: "⚠️ ALREADY ADJACENT - DO NOT ISSUE move ACTION!"
2. **Prompt tuning**: Add explicit instruction about when NOT to move
3. **Post-processing**: Filter out move actions when adjacent

### Priority 2: Test Ship Flow

Parsnips in inventory (slots 5, 10). Test:
1. Navigate to shipping bin
2. Execute ship_item skill
3. Verify items shipped

### Priority 3: Continue Multi-Day Test

- Crop at (64, 22) needs 2 more days → ready Day 11
- Test harvest + ship cycle when ready

---

## Game State

**Day 9, ~6PM**
- 1 crop at (64, 22) - watered, 2 days until harvest
- Parsnips in inventory: slots 5, 10 (ready to ship)
- Shipping bin at (71, 14)

---

## Quick Reference

### Current Hint Format

| Scenario | Hint |
|----------|------|
| dist == 0 (ON crop) | "STEP BACK! move 1 tile any direction, then face crop, water" |
| dist == 1 (adjacent) | "ADJACENT! DO: face west, water_crop (NO move!)" |
| dist > 1 | "move 2N+1E (stop adjacent), face NORTH, water" |

### Test Commands

```bash
# Check positions
curl -s localhost:8790/state | jq '{player: {x: .data.player.tileX, y: .data.player.tileY}, crops: .data.location.crops}'

# Run agent
python src/python-agent/unified_agent.py --goal "Ship the parsnips"
```

---

## Commits This Session

| Hash | Description |
|------|-------------|
| `4f14327` | Session 45-46: Positioning fix + Phantom detection + Skill timing |
| `7902730` | Session 46b: Improved adjacent positioning hints |

---

*Session 46: Positioning hints work but VLM still needs tuning to not move when adjacent*

*— Claude (PM), Session 46*
