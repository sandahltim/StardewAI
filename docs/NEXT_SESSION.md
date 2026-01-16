# Session 124: Test Mining After Fix

**Last Updated:** 2026-01-15 Session 123 by Claude
**Status:** Fixed clearing loop blocking mining - ready for testing

---

## Session 123 Fix

### Problem: Agent Stuck in Clearing Loop

The agent was stuck on "clear debris" and never transitioned to mining.

**Root Cause:** The `_generate_maintenance_tasks()` function created a standalone "clear debris" task with **no `skill_override`**. This caused it to run through VLM-based execution which got stuck in an infinite loop.

**Fix:** Removed the standalone `clear_debris` task. Crops grow fine around debris. If debris clearing is needed later, it should be added to `_batch_farm_chores`.

```
Commit: ada2ef6 Session 123: Remove standalone clear_debris task blocking mining
```

---

## Session 122 Summary

### Major Feature: Batch Mining (`auto_mine`)

Similar to `auto_farm_chores`, added `auto_mine` for automated mining:

**`_batch_mine_session(target_floors=5)`**
```
Loop per floor:
1. Check health/energy → retreat if low (<25% health, <15% energy)
2. Check monsters → attack nearby (dist <= 3) OR hunt on infested floors
3. Check ladder → use it to descend
4. Find rocks → move adjacent, equip pickaxe, break
5. Repeat until target floors reached
```

**Key Features:**
| Feature | Implementation |
|---------|---------------|
| **Safety** | Retreats to surface if health < 25% or energy < 15% |
| **Food** | Auto-eats food when low health |
| **Combat** | 3x weapon swings, moves toward monsters when hunting |
| **Infested floors** | Detects and hunts ALL monsters (wiki: must kill all for ladder) |
| **Ore priority** | Sorts rocks by distance, prioritizes ore over stone |

**Helper Functions:**
- `_try_eat_food()` - Find and eat food from inventory
- `_move_adjacent_and_face()` - Navigate to rock/monster and face it
- `_direction_to_target()` - Get cardinal direction

### Fixes Applied

| Fix | File | Description |
|-----|------|-------------|
| Goal-aware skills | `unified_agent.py` | "mine" keyword highlights mining skills |
| Mining task execution | `daily_planner.py` | `skill_override="auto_mine"` |
| Missing npcs table | `game_knowledge.py` | Graceful handling if table doesn't exist |

### Mining Mechanics (from Stardew Wiki)

| Mechanic | Details |
|----------|---------|
| **Ladder spawn** | 95% on load, 15% per monster, 2% per rock |
| **Infested floors** | Must kill ALL monsters for ladder |
| **Floor sections** | 1-39 (copper), 41-79 (iron), 81-119 (gold) |
| **Elevator** | Unlocks every 5 floors |

---

## Session 122 Commits

```
9fd1165 Session 122: Improve mining monster handling for infested floors
1dba777 Fix: Handle missing npcs table gracefully
5e80396 Session 122: Add batch mining system (auto_mine)
bef4f82 Session 122: Fix mining task - add skill_override to warp to mines
fafb669 Session 122: Fix mining - goal-aware skill context
```

---

## Session 124 Priorities

### 1. Test Mining After Fix

```bash
# Test mining goal
python src/python-agent/unified_agent.py --goal "Do farm chores and go mining"

# Watch for:
# - ⛏️ BATCH MINING - Target: X floors
# - ⛏️ Floor N: X rocks, Y monsters
# - ⛏️ Mined Copper ore at (x,y)
# - ⛏️ MINING COMPLETE: ores=X, rocks=Y, floors=Z
```

### 2. Verify Combat Works

- Monsters should be attacked when nearby
- On infested floors: actively hunt all monsters
- Health check should trigger food eating or retreat

### 3. Tune Parameters (if needed)

Current settings:
- `MIN_HEALTH_PCT = 25` - retreat threshold
- `MIN_ENERGY_PCT = 15` - retreat threshold
- `MAX_ROCKS_PER_FLOOR = 30` - prevent infinite loops
- `target_floors = 3-10` - based on combat level

---

## Quick Reference

### Mining SMAPI Endpoint

```bash
curl localhost:8790/mining | jq
```

### Batch Mining Flow

```
Daily Planner creates task:
  category="mining"
  skill_override="auto_mine"

_try_start_daily_task() detects skill_override
  → Sets _pending_batch

tick() executes batch:
  → execute_skill("auto_mine", {})
  → _batch_mine_session(5)
    → Warp to Mine if needed
    → Enter level 1
    → Loop: monsters → ladder → rocks
    → Return results
```

### Key Files

| File | Session 122 Changes |
|------|---------------------|
| `unified_agent.py` | `_batch_mine_session()`, `auto_mine` handler, goal-aware skills |
| `daily_planner.py` | Mining task with `skill_override="auto_mine"` |
| `game_knowledge.py` | Graceful NPCs table handling |

---

## Known Issues

1. **Combat untested** - Weapon equipping and swing_weapon action need verification
2. **Monster movement** - Monsters move between state refreshes
3. **Pathfinding in mines** - May need warp fallback like farm refill fix

## Resolved Issues

1. ~~**Clearing loop blocks mining**~~ - Fixed Session 123: Removed standalone clear_debris task

---

## Sources

- [Mining - Stardew Valley Wiki](https://stardewvalleywiki.com/Mining)
- [The Mines - Stardew Valley Wiki](https://stardewvalleywiki.com/The_Mines)

---

-- Claude
