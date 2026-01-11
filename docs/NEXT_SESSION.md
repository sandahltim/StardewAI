# Session 54: Multi-Day Autonomy Test

**Last Updated:** 2026-01-11 Session 53 by Claude
**Status:** Seeds flow complete, ready for extended testing

---

## Session 53 Summary

### Fixed: Warp Location Case-Sensitivity Bug

**Problem:** Agent was warping to (10, 10) - a walled playground area - instead of proper Town location (43, 57).

**Root Cause:**
- Python sends lowercase location names: `"town"`
- C# `LocationSpawns` dictionary had PascalCase keys: `"Town"`
- Case-sensitive lookup failed → fell back to default (10, 10)

**Fix:** Made dictionary case-insensitive:
```csharp
private static readonly Dictionary<string, (int x, int y)> LocationSpawns =
    new(StringComparer.OrdinalIgnoreCase) { ... }
```

File: `ActionExecutor.cs:1080-1081`

### Fixed: SeedShop Buy Override

**Problem:** Agent would warp to Pierre's but then leave without buying seeds.

**Root Cause:** `_fix_no_seeds` override only triggered for farming actions, but VLM was outputting `move` commands in shop.

**Fix:** Moved location check BEFORE action check - when in SeedShop with no seeds, force `buy_parsnip_seeds` regardless of VLM action.

```python
# If at Pierre's (SeedShop), force buy seeds regardless of VLM action
if location == "SeedShop":
    if not has_seeds:
        return [Action("buy_parsnip_seeds", {}, ...)]
```

File: `unified_agent.py:2881-2888`

### Simplified: Pierre Navigation

**Before:** Warp Town → walk north → interact (fragile, wrong coordinates)
**After:** Warp directly to SeedShop (5, 20)

File: `navigation.yaml:323-324`

### Working Flow

```
Farm (no seeds)
  → _fix_no_seeds override forces go_to_pierre
  → warps to SeedShop (5, 20)
  → _fix_no_seeds override forces buy_parsnip_seeds
  → agent buys seeds
  → returns to farm with seeds
```

---

## Session 53 Commits

| Commit | Description |
|--------|-------------|
| `bd21dee` | Fix warp location case-sensitivity bug |
| `09ba152` | Add SeedShop buy override + simplify Pierre navigation |

---

## Next Session Priority

### Priority 1: Multi-Day Autonomy Test

The core farming loop is now complete:
- Till → Plant → Water → Harvest → Ship → Buy Seeds

Run agent for 3+ in-game days and monitor for issues.

### Priority 2: Harvest Phantom Failures (if still occurring)

Previous session noted crops not being harvested even with correct direction. May need to investigate:
1. Player adjacency to crops
2. SMAPI Harvest action functionality
3. Crop state detection

### Priority 3: Season Transition

Day 28 → Day 1 of next season. Test if agent handles:
- Crops dying (wrong season)
- New season seeds needed
- Calendar awareness

---

## Quick Reference

```bash
# Run agent
source venv/bin/activate
python src/python-agent/unified_agent.py --ui --goal "Farm autonomously"

# Check current state
curl -s localhost:8790/state | jq '{location: .data.location.name, day: .data.time.day, hour: .data.time.hour}'

# Check inventory for seeds
curl -s localhost:8790/state | jq '.data.inventory[] | select(.name | contains("Seed"))'

# Watch for overrides
tail -f logs/agent.log | grep "OVERRIDE"
```

---

*Session 53: Warp case-sensitivity fixed, buy override added, seeds flow complete.*

*— Claude (PM), Session 53*
