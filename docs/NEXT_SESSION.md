# Session 123: Mining Testing & Integration

**Last Updated:** 2026-01-15 Session 122 by Claude
**Status:** Mining infrastructure ready - needs end-to-end testing

---

## Session 121 Summary (Completed)

### Fixes Applied

| Fix | Description |
|-----|-------------|
| **Refill warp fallback** | When `move_to` fails (A* blocked), use direct warp to water source |
| **Water verification** | Double-check water level before each watering attempt |
| **Verification delays** | Tiles: 1.2s, water: 1.0s, others: 0.5s |
| **Auto-craft essentials** | Daily planner generates scarecrow/chest tasks when materials available |

### Commits
```
a166b15 Session 121: Fix refill - verify arrival and use warp fallback
d9c4a90 Session 121: Fix watering/refill loops, add auto-craft essentials
```

---

## Session 122 Summary (Completed)

### Problem: "Go mine" chose "clear debris" instead

**Root Causes Found:**
1. `TASK_TO_SKILL` missing mining mapping - TaskExecutor didn't know what skill to use
2. Duplicate skills: `go_to_mines` (mining.yaml) vs `warp_to_mine` (navigation.yaml)
3. 8-skill limit per category hid mining skills in crowded navigation category
4. No goal-awareness - VLM didn't prioritize mining skills when user said "mine"

### Fixes Applied

| Fix | File | Description |
|-----|------|-------------|
| Added mining mapping | `task_executor.py:121` | `"mining": "warp_to_mine"` |
| Goal-aware skill context | `unified_agent.py:3041-3120` | Keywords like "mine" highlight mining/combat/navigation categories |
| Priority categories | `unified_agent.py:3096-3116` | Goal-relevant categories show first with more skills (12 vs 6) |

### Code Changes

**task_executor.py:**
```python
TASK_TO_SKILL = {
    ...
    # Mining - Session 122
    "mining": "warp_to_mine",  # First step: get to mine
}
```

**unified_agent.py - Goal keywords:**
```python
GOAL_KEYWORDS = {
    "mine": ["mining", "combat", "navigation"],
    "mining": ["mining", "combat", "navigation"],
    "ore": ["mining"],
    "copper": ["mining"],
    ...
}
```

**VLM now sees:**
```
AVAILABLE SKILLS (use skill name as action type):
  [MINING] ⭐ RELEVANT TO YOUR GOAL
    - break_rock - Break a rock with the pickaxe
    - mine_copper_ore - Mine a copper ore node
    ...
  [NAVIGATION] ⭐ RELEVANT TO YOUR GOAL
    - warp_to_mine - Teleport to the Mine entrance
    ...
```

---

## Session 123 Priorities

### 1. Test Mining End-to-End

```bash
# Run with mining goal
python src/python-agent/unified_agent.py --goal "Go mining for copper ore"

# Expected behavior:
# 1. VLM sees mining skills highlighted
# 2. Calls warp_to_mine to get to mines
# 3. Once in mine, calls break_rock, use_ladder, etc.
```

### 2. Verify Skill Context Shows Mining

Look in logs for:
```
📚 Skill context: X available
[MINING] ⭐ RELEVANT TO YOUR GOAL
```

### 3. Add Batch Mining Support (if needed)

If VLM struggles in mines, consider adding `_batch_mine_floor()` similar to `_batch_farm_chores()`:
- Get rocks from `/mining` endpoint
- Mine in row-by-row order (closest first)
- Watch for monsters (combat or retreat)
- Find ladder when floor cleared

### 4. Combat Handling

- Monitor `/mining` for monsters near player
- Auto-attack if monster within 2 tiles
- Retreat if health < 25% or no food

---

## Quick Reference

### Mining SMAPI Endpoint

```bash
curl localhost:8790/mining | jq
```

Returns:
```json
{
  "location": "UndergroundMine",
  "floor": 5,
  "floorType": "normal",
  "ladderFound": false,
  "rocks": [{"tileX": 10, "tileY": 8, "type": "Copper", "health": 2}],
  "monsters": [{"name": "Green Slime", "tileX": 5, "tileY": 12, "health": 20}]
}
```

### Available Mining Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `warp_to_mine` | navigation | Teleport to Mine entrance |
| `enter_mine_level_X` | mining | Use elevator (1, 5, 10, 40, 80, 120) |
| `use_ladder` | mining | Descend via ladder/shaft |
| `break_rock` | mining | Pickaxe on rock (needs target_direction) |
| `mine_copper_ore` | mining | Multi-hit mining for copper |
| `attack` | combat | Swing weapon in direction |
| `eat_for_health` | combat | Eat food to restore health |

### Mining Floor Reference

| Levels | Type | Ore |
|--------|------|-----|
| 1-39 | Normal | Copper |
| 40-79 | Frozen | Iron |
| 80-119 | Lava | Gold |
| 120+ | Skull Cavern | Iridium |

---

## Key Files Changed (Session 122)

| File | Changes |
|------|---------|
| `src/python-agent/execution/task_executor.py` | Added `"mining": "warp_to_mine"` |
| `src/python-agent/unified_agent.py` | Goal-aware skill context |

---

## Pathfinding Note

Pathfinding correctly avoids placed objects (chests, scarecrows, fences) via `TilePathfinder.IsTilePassable()`:
- Checks `location.objects` + `!obj.isPassable()`
- Checks ResourceClumps (stumps, logs, boulders)
- NPCs are passable (player can push through)

---

-- Claude
