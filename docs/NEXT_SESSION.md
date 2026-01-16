# Session 131: Test Mining + Scarecrow + Inventory Fixes

**Last Updated:** 2026-01-16 Session 130 by Claude
**Status:** Major fixes ready - RESTART GAME to test mining

---

## What Changed (Sessions 129-130)

### Mining Fixes (CRITICAL - Restart Game!)
| Issue | Fix |
|-------|-----|
| Agent stuck on floor 1 | `UseLadder()` now checks BOTH `mine.Objects` AND `mine.objects` collections |
| Ladder detection failed | Same fix applied to `GetMiningInfo()` detection |
| Not collecting ore/geodes | Walk circle around rock after mining to auto-collect |
| Mining with full inventory | Return to surface when < 2 slots free |

### Farm Chores Fixes
| Issue | Fix |
|-------|-----|
| Harvest loop with full inventory | Skip crops when 0 slots, stop after 3 skips |
| Not planting on tilled tiles | Prioritize empty tilled tiles as targets (not blocked!) |
| State not refreshing after buy | Wait 0.6s + reset `last_state_poll = 0` |
| Inventory slot count wrong | Calculate `max_items - len(used_items)` for sparse list |

### New Features (Session 130)
| Feature | How It Works |
|---------|--------------|
| **Coverage-based scarecrow planning** | Uses `farm_planner.get_farm_layout_plan()` to calculate WHICH crops are unprotected and how many scarecrows needed |
| **Inventory-aware crafting** | Checks if scarecrow/chest in inventory → place task, not craft task |
| **Multi-scarecrow support** | Creates task for EACH scarecrow needed, deducts materials |
| **Inventory management** | When >80% full + 5 storable items + chest exists → `organize_inventory` task |

---

## Startup Commands

**Terminal 1 - llama-server:**
```bash
cd /home/tim/StardewAI
./scripts/start-llama-server.sh
```

**Terminal 2 - UI Server:**
```bash
cd /home/tim/StardewAI && source venv/bin/activate
uvicorn src.ui.app:app --reload --port 9001
```

**Terminal 3 - Agent:**
```bash
cd /home/tim/StardewAI && source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Do farm chores and go mining"
```

---

## Session 131 Testing Checklist

### ⚠️ IMPORTANT: Restart Game First!
The SMAPI mod was rebuilt with mining fixes. Game must be restarted to load new DLL.

### Mining (Priority - Was Broken)
- [ ] Agent descends past floor 1 (watch floor numbers in log)
- [ ] `use_ladder` works on spawned ladders (log: "Descended to level X via ladder")
- [ ] Falls back to `descend_mine` if needed (log: "using descend_mine fallback")
- [ ] Collects items after mining (log shows walking circle)
- [ ] Returns to surface when inventory < 2 slots free

### Scarecrow (New Feature)
- [ ] Log shows coverage analysis: `📋 Crop coverage: X/Y (Z%)`
- [ ] Creates multiple scarecrow tasks if needed: `need N more scarecrow(s)`
- [ ] If scarecrow in inventory: `Added task: Place scarecrow (have in inventory)`
- [ ] If no scarecrow: `Added task: Craft scarecrow`

### Inventory Management (New Feature)
- [ ] When inventory >80% full: `Added task: Organize inventory (X to store)`
- [ ] If no chest but inventory full: warning logged
- [ ] `organize_inventory` skill runs and deposits items

### Farm Chores
- [ ] Planting uses tilled tiles: `Found X empty tilled tiles ready for planting`
- [ ] Seeds detected after buying: `inventory has seeds: [...]`
- [ ] Harvest stops when full: `Inventory FULL`

---

## Key Log Messages to Watch

```
Mining:
  ⛏️ BATCH MINING - Target: 5 floors
  ⛏️ Floor 1: X rocks, Y monsters, ladder=False
  ⛏️ Ladder found! Descending...
  ⛏️ Descended to level 2 via ladder

Scarecrow:
  📋 Crop coverage: 15/30 (50%) - need 1 more scarecrow(s)
  📋 Added task: Craft scarecrow (have X wood, X coal, X fiber)

Inventory:
  📋 Added task: Organize inventory (8 to store, 5 to sell)

Planting:
  🌱 Found 36 empty tilled tiles ready for planting
  🌱 Using 15 pre-tilled positions for planting
```

---

## Files Modified (Sessions 129-130)

| File | Change |
|------|--------|
| `ActionExecutor.cs` | UseLadder + GetMiningInfo check both Objects collections |
| `unified_agent.py` | Mining: collect items, inventory check, descent fallbacks |
| `unified_agent.py` | Planting: prioritize tilled tiles, sparse inventory fix |
| `unified_agent.py` | Batch: TTS commentary, state refresh after buy |
| `daily_planner.py` | Coverage-based scarecrow + inventory management tasks |

---

## Architecture Notes

### The Objects vs objects Bug (Critical)
```
MineShaft has TWO collections:
- mine.Objects (capital O) - property, pre-existing objects
- mine.objects (lowercase o) - field, runtime spawned objects

Ladders spawned from breaking rocks go into LOWERCASE collection.
Both GetMiningInfo() and UseLadder() now check BOTH.
```

### Inventory Management Flow
```
Daily Planner runs → calls get_inventory_manager()
  → needs_organization(inventory)? (>80% full + 5 storable)
  → get_storage_summary() for what to store/sell
  → Creates organize_inventory task (HIGH priority)
  → Skill navigates to chest, deposits excess, keeps tools
```

### Scarecrow Coverage Flow
```
Daily Planner runs → calls get_farm_layout_plan(farm_state)
  → farm_planner calculates unprotected crops
  → Returns scarecrows_needed count
  → For each: check inventory first, then materials
  → Creates place_scarecrow or craft_scarecrow task
```

---

## Roadmap (Future Sessions)

1. **Crafting/upgrades** - Use blacksmith, craft items from recipes
2. **Popup handling** - Dismiss dialogs, handle festival options
3. **Food reservation** - Keep 1-2 edible items for mining health
4. **Multi-chest support** - Route items to appropriate chests by type

---

## Session 130 Commits

```
55be5d7 Session 129: Fix UseLadder to check both Objects collections
bb8d1e6 Session 130: Coverage-based scarecrow planning + inventory check
bfeb02c Session 130: Wire up inventory management to daily planner
7d1ccab Session 130: Update docs with scarecrow + inventory features
```

---

-- Claude (Session 130)
