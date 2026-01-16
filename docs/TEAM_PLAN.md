# StardewAI Team Plan

**Last Updated:** 2026-01-16 Session 132
**Project Lead:** Claude (Opus) - Agent logic, architecture, coordination
**UI/Memory:** Codex - User interface, memory systems, state persistence
**Human Lead:** Tim - Direction, testing, hardware, final decisions

---

## Current Focus: Inventory Management & Item Placement

### Immediate Priorities (Session 133+)

| Priority | Task | Status |
|----------|------|--------|
| HIGH | Test chest crafting | Ready to test |
| HIGH | Test organize_inventory skill | Ready to test |
| HIGH | Test mining gates | Ready to test |
| MEDIUM | Scarecrow crafting/placement | Blocked by chest |
| MEDIUM | Sprinkler crafting | Blocked by mining |

### Recent Fixes (Sessions 131-132)

| Fix | Impact |
|-----|--------|
| `craft` action Python handler | Chest crafting now works |
| Mining gates | No more mining loop (chest required, odd day/rain) |
| Tool storage | Stores hoe/scythe/can before mining, retrieves after |
| Wood gathering filter | Only targets twigs/branches/trees, not rocks/bushes |
| Quantity tracking | Logs harvest breakdown, inventory, chest contents |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Agent (unified_agent.py)          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐│
│  │  Screen    │─▶│  Qwen3 VL  │─▶│  Skill/Action Planner  ││
│  │  Capture   │  │  (8780)    │  │  outputs skill names   ││
│  └────────────┘  └────────────┘  └───────────┬────────────┘│
│                                              │              │
│  ┌───────────────────────────────────────────▼────────────┐│
│  │              Batch Skills (autonomous)                 ││
│  │  auto_farm_chores, auto_mine, gather_wood              ││
│  └───────────────────────────────────────────┬────────────┘│
└──────────────────────────────────────────────│─────────────┘
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 SMAPI GameBridge (8790)                     │
│  16 API endpoints: /state, /farm, /mining, /storage, etc.  │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    UI Server (9001)                         │
│  Dashboard │ Farm Plan │ Team Chat │ Status Indicators      │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Systems

### Batch Skills (Autonomous Execution)
| Skill | What It Does |
|-------|--------------|
| `auto_farm_chores` | Buy seeds → Harvest → Water → Till → Plant |
| `auto_mine` | Store tools → Mine floors → Retrieve tools |
| `gather_wood` | Clear debris + chop trees until target wood |
| `organize_inventory` | Deposit excess to chest |

### Mining Gates (Prevents Loop)
| Gate | Condition |
|------|-----------|
| Chest exists | `has_chest_placed == True` |
| 4+ free slots | Mining stackables don't count as blocking |
| Odd day OR rain | Even sunny days = farm focus |

### Action Handler Pattern
```
New actions need BOTH:
1. C# ActionExecutor.cs - switch case + method
2. Python unified_agent.py - elif handler in ModBridgeController

Missing either = "Unknown action" error
```

---

## Roadmap

### Phase 1: Farming Foundation ✅ COMPLETE
- Till, plant, water, harvest, ship, buy seeds

### Phase 2: Inventory & Storage (CURRENT)
- [x] Chest crafting action
- [x] Wood gathering skill
- [ ] Test chest placement
- [ ] organize_inventory skill
- [ ] Backpack upgrade (2000g → 24 slots)

### Phase 3: Mining & Resources
- [x] Mining batch skill
- [x] Mining gates (chest, slots, day)
- [x] Tool storage during mining
- [ ] Multi-floor mining runs
- [ ] Ore processing (furnace)

### Phase 4: Farm Optimization
- [ ] Scarecrow placement (crop protection)
- [ ] Sprinkler crafting (auto-water)
- [ ] Multi-chest routing by item type

### Phase 5: Advanced (Future)
- [ ] NPC relationships
- [ ] Fishing
- [ ] Season transitions
- [ ] Full year autonomy

---

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| llama-server | 8780 | VLM inference (Qwen3VL) |
| SMAPI mod | 8790 | Game control API |
| UI Server | 9001 | Dashboard + Team Chat |

---

## Team Communication

| Channel | Purpose |
|---------|---------|
| Team Chat | `http://localhost:9001/api/team` |
| Task Docs | `docs/CODEX_TASKS.md`, `docs/CLAUDE_TASKS.md` |
| Session Log | `docs/SESSION_LOG.md` |
| Handoff | `docs/NEXT_SESSION.md` |

---

## Project Vision

**Rusty** is an AI farmer who plays Stardew Valley autonomously. The goal:
- Start from Day 1 and progress through the game
- Make intelligent decisions about farming, mining, socializing
- Run for extended periods without human intervention
- Be entertaining and competent - a true AI companion

**End State:** Rusty runs start-to-finish without Claude's help.

*Make Rusty amazing. — Tim*

---

-- Claude (PM)
