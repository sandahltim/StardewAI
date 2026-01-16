# Session 128: Test Complete Task Flow

**Last Updated:** 2026-01-16 Session 127 by Claude
**Status:** Multiple dispatch bugs fixed - ready for full flow test

---

## Session 127 Summary

Fixed 4 action dispatch bugs that were breaking the farm→ship→mine workflow:

| Bug | Symptom | Root Cause | Fix |
|-----|---------|------------|-----|
| `descend_mine` unknown | Loop at mine entrance | Missing Python dispatch | `unified_agent.py:2183` |
| Ship task skipped | Mining before selling | Only created if crops in inventory | `daily_planner.py:450` |
| No ship targets | 0 sellable items found | Missing "fruit" type | `target_generator.py:287` |
| Watering rocks in mine | Wrong tool used | `equip_tool` not dispatched | `unified_agent.py:2082` |

### Key Insight

The "watering rocks" bug: batch mining called `Action("equip_tool", ...)` but dispatcher only recognized `action_type == "equip"`. Pickaxe never equipped, so watering can got used on rocks.

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

## Session 128 Testing Checklist

### Task Flow Verification
- [ ] Farm chores runs first (CRITICAL priority)
- [ ] Ship task runs after harvest (HIGH priority)
- [ ] Mining runs last (MEDIUM priority)
- [ ] Log shows: `📦 Ship task created: Ship X crops after harvest`

### Ship Task Verification
- [ ] Log shows: `📦 Ship target check: N sellable, inventory=[...]`
- [ ] Sellable items include type "crop" and "fruit"
- [ ] Agent navigates to shipping bin
- [ ] Items actually shipped

### Mining Verification
- [ ] `descend_mine` works (no "Unknown action" warning)
- [ ] Agent descends from floor 0 to floor 1
- [ ] Pickaxe gets equipped (not watering can)
- [ ] Rocks get mined (not watered)

---

## Files Modified Session 127

| File | Line | Change |
|------|------|--------|
| `unified_agent.py` | 2082 | `equip_tool` alias for `equip` |
| `unified_agent.py` | 2183 | `descend_mine` dispatch |
| `daily_planner.py` | 450 | Ship task if harvestable crops exist |
| `target_generator.py` | 287 | Added "fruit" to sellable types |
| `target_generator.py` | 293 | Diagnostic logging for ship targets |

---

## Session 126 Fixes (Still Relevant)

These fixes from Session 126 are still in effect:

| Fix | File | Line |
|-----|------|------|
| Warp rate limit reset | `unified_agent.py` | 4246 |
| Failed tasks retry | `unified_agent.py` | 8016 |
| Farm chores verification | `unified_agent.py` | 3497 |
| Ladder/shaft coordinates | `ModEntry.cs` | 757 |

---

## Known Issues

1. **SMAPI mod rebuild required** if C# changes made - game must restart
2. **Python changes** only need agent restart (no game restart)
3. **VLM fallback** - if batch skills fail, VLM takes over with potentially wrong actions

---

## Architecture Notes

### Task Priority Order
```
CRITICAL (1) → HIGH (2) → MEDIUM (3) → LOW (4)
farm_chores  → ship     → mining     → social
```

### Batch Skills (bypass TaskExecutor)
- `auto_farm_chores` - harvest, water, till, plant
- `auto_mine` - descend floors, break rocks, combat

### Action Dispatch Chain
```
Action("equip_tool", {tool: "Pickaxe"})
  → unified_agent._execute_modbridge_action()
  → action_type in ("equip", "equip_tool")  ← Session 127 fix
  → _send_action({action: "equip_tool", tool: "Pickaxe"})
  → SMAPI mod ActionExecutor.cs
```

---

-- Claude (Session 127)
