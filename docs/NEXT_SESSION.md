# Session 125: Test Mining Execution & Combat

**Last Updated:** 2026-01-15 Session 124 by Claude
**Status:** Major fixes applied - ready for testing

---

## Session 124 Summary

### What Was Fixed

| Issue | Fix | File |
|-------|-----|------|
| "Go to bed" hint in Mine | Location check returns mining hint | `unified_agent.py:1765` |
| "Go to bed" at 9:50 AM | Time check + pending task awareness | `unified_agent.py:1893-1901` |
| Task flow invisible | Added INFO-level diagnostic logging | `unified_agent.py:7600, 5798-5842` |
| Fixed 3 swings for all monsters | Monster-type-aware swing counts | `unified_agent.py:4334-4380` |
| No dodge mechanics | Kiting for dangerous monsters | `unified_agent.py:4414-4456` |
| "Flee if no weapon" got cornered | Smart retreat with multiple escape routes | `unified_agent.py:4458-4498` |
| No weapon pickup | Auto-pickup from ground/containers | `unified_agent.py:4500-4552` |

### Session 124 Commits

```
2eb7890 Session 124: Implement tactical combat system for mining
ac0d1f7 Session 124: Fix hint to not suggest bed at 9:50 AM
7540b28 Session 124: Update handoff doc with fixes and diagnostics
4e7241a Session 124: Add comprehensive task flow diagnostics
332f441 Session 124: Fix hint system for Mine location + add diagnostics
```

---

## New Combat System

### Monster Knowledge (MONSTER_DATA)

```python
# 20+ monster types with tactics
"Green Slime": {"danger": 1, "speed": "slow", "swings": 2, "kite": False}
"Serpent":     {"danger": 5, "speed": "very_fast", "swings": 6, "kite": True}
"Shadow Shaman": {"danger": 4, "attack": "ranged", "swings": 4, "kite": True}
```

### Combat Methods

| Method | Purpose |
|--------|---------|
| `_get_monster_tactics(name)` | Get danger/swings/kite for monster type |
| `_combat_engage(monster, x, y, has_weapon)` | Main combat dispatcher |
| `_combat_kite(monster, x, y, tactics)` | Hit-and-run for danger >= 4 |
| `_combat_retreat(mx, my, px, py, name)` | Smart escape when weaponless |
| `_try_pickup_weapon()` | Search ground/containers for weapons |

### Combat Flow

```
Monster detected
    ↓
Check weapon inventory
    ↓ (no weapon)
_try_pickup_weapon() → break nearby barrels/crates
    ↓
Still no weapon? → _combat_retreat() (smart escape)
Has weapon? → _combat_engage()
    ↓
danger >= 4 and kite=True? → _combat_kite() (hit-and-run)
danger < 4? → standard attack (monster-specific swings)
```

---

## Hint System Improvements

### Location Awareness

```python
# At start of _get_done_farming_hint():
if "Mine" in location:
    return ">>> ⛏️ IN MINES! Break rocks to find ladder. <<<"
if location != "Farm":
    return ""  # No farming hints outside farm
```

### Time & Task Awareness

```python
# Before suggesting bed:
if self.daily_planner:
    mining_task = next((t for t in pending if t.category == "mining"), None)
    if mining_task and hour < 16:
        return ">>> ⛏️ FARM DONE! GO MINING! <<<"

# Only suggest bed if actually late
if hour >= 18 or energy_pct <= 40:
    return ">>> go to bed <<<"

# Otherwise suggest exploration
return ">>> Explore, forage, fish, or visit town. <<<"
```

---

## Testing

### Test Command
```bash
python src/python-agent/unified_agent.py --goal "Do farm chores and go mining"
```

### Expected Logs - Task Flow

```
🔍 STEP 2b: day1_clearing=False, has_executor=True, has_planner=True
🎯 _try_start_daily_task: 3 items in resolved queue
🔍 Task check: id=mining_5_1, skill_override=auto_mine
🚀 BATCH MODE: Task mining_5_1 uses skill_override=auto_mine
🚀 Executing batch: auto_mine
```

### Expected Logs - Combat

```
⛏️ Floor 3: 12 rocks, 2 monsters, ladder=False
⚔️ Combat: Bat (danger=2, dist=3)
⚔️ Combat: Green Slime (danger=1, dist=5)
```

### Expected Logs - Kiting (Dangerous Monster)

```
⚔️ Combat: Serpent (danger=5, dist=4)
⚔️ Kiting Serpent (danger=5)
⚔️ Serpent still alive - continue kiting
```

### Expected Logs - No Weapon

```
⛏️ No weapon! Searching for one...
📦 Breaking Barrel at (12,8) for loot
⚔️ Got a weapon from container!
⛏️ Armed and ready!
```

### Expected Logs - Smart Retreat

```
🏃 No weapon! Smart retreat from Bug
🏃 Escaped west
```

---

## If Mining Still Not Executing

### Check 1: Diagnostic Logs Appearing?

Look for `🔍 STEP 2b:` log. If missing:
- Agent wasn't restarted after code changes
- Code path returning before STEP 2b (check earlier returns in `_tick()`)

### Check 2: Day Mismatch?

If you see `waiting for daily plan (day X, last_planned=Y)`:
- `new_day()` wasn't called for current day
- Check daily planner initialization

### Check 3: Empty Resolved Queue?

If you see `no resolved queue, falling back to legacy`:
- PrereqResolver not creating queue
- Check `_resolve_prerequisites()` logs

### Check 4: Mining Task Not Created?

Look for `⛏️ Mining task ADDED:` at day start. If missing, check:
- `has_pickaxe=True` (player needs pickaxe)
- `energy_pct > 60` (over 60% energy)
- `hour < 14` (before 2pm)

---

## Key Files Quick Reference

| File | Line | What |
|------|------|------|
| `unified_agent.py` | 1763-1770 | Location-aware hint |
| `unified_agent.py` | 1893-1901 | Time-aware hint |
| `unified_agent.py` | 4334-4380 | MONSTER_DATA |
| `unified_agent.py` | 4382-4412 | `_combat_engage()` |
| `unified_agent.py` | 4414-4456 | `_combat_kite()` |
| `unified_agent.py` | 4458-4498 | `_combat_retreat()` |
| `unified_agent.py` | 4500-4552 | `_try_pickup_weapon()` |
| `unified_agent.py` | 5786-5944 | `_try_start_daily_task()` |
| `unified_agent.py` | 7600 | STEP 2b diagnostic |
| `daily_planner.py` | 572-598 | Mining task creation |

---

## Next Session Priorities

1. **Test the fixes** - Restart agent and verify:
   - Diagnostic logs appear
   - Mining task triggers after farm chores
   - Combat system works (kiting, retreat, weapon pickup)

2. **If mining still broken** - Follow troubleshooting above

3. **Combat tuning** - After testing, may need to adjust:
   - Swing counts per monster
   - Kite distance/timing
   - Retreat direction selection

---

-- Claude (Session 124)
