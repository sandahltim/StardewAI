# StardewAI Team Plan

**Created:** 2026-01-08
**Last Updated:** 2026-01-08 Session 10
**Project Lead:** Claude (Opus) - Agent logic, architecture, coordination
**UI/Memory:** Codex - User interface, memory systems, state persistence
**Human Lead:** Tim - Direction, testing, hardware, final decisions

---

## Project Vision

**Rusty** is an AI farmer who plays Stardew Valley autonomously as a co-op partner. The goal is a fully autonomous agent that can:

- Start from Day 1 and progress through the game
- Make intelligent decisions about farming, foraging, socializing
- Adapt to seasons, weather, and events
- Run for extended periods without human intervention
- Be entertaining and competent - a true AI companion

**End State:** Rusty runs start-to-finish without Claude's help. Amazing.

---

## Current Status (Session 10)

### What's Working
| Component | Status |
|-----------|--------|
| VLM Perception (Qwen3VL-30B) | Working |
| SMAPI GameBridge API | Working |
| Tool Detection | Working |
| Tile State Detection | Working |
| Water Source Detection | Working |
| Farming Progress UI | Working |
| Memory Systems | Working |

### What's Being Fixed
| Issue | Status |
|-------|--------|
| Seed planting action | Fix ready, needs test |
| Agent decision making | Needs improvement |

---

## Completion Checklist

### Actions - Must All Work
| Action | Tested | Notes |
|--------|--------|-------|
| move (all 4 directions) | Yes | Working |
| use_tool (hoe) | Yes | Working |
| use_tool (watering can) | Yes | Working |
| use_tool (axe) | Partial | Needs test |
| use_tool (pickaxe) | Partial | Needs test |
| use_tool (scythe) | Partial | Needs test |
| use_tool (seeds/planting) | No | **Fix ready, test next** |
| use_tool (fishing rod) | No | Future |
| select_slot (0-11) | Yes | Working |
| interact (NPCs) | No | Future |
| interact (chests) | No | Future |
| interact (shipping bin) | No | Future |
| warp (locations) | Partial | Debug command |

### Locations - Must Navigate All
| Location | Can Enter | Can Navigate | Can Exit |
|----------|-----------|--------------|----------|
| FarmHouse | Yes | Yes | Yes |
| Farm | Yes | Yes | Yes |
| Town | Partial | Needs test | Needs test |
| Pierre's Shop | No | No | No |
| Beach | No | No | No |
| Forest | No | No | No |
| Mountain | No | No | No |
| Mine | No | No | No |
| Bus Stop | No | No | No |

### Game Cycles - Must Complete
| Cycle | Status | Notes |
|-------|--------|-------|
| Till → Plant → Water | Partial | Planting fix pending |
| Water daily | Partial | Needs multi-day test |
| Refill watering can | Ready | Water detection added |
| Harvest crops | No | Not implemented |
| Sell at shipping bin | No | Shipping bin location ready |
| Forage items | No | Forageable detection added |
| Talk to NPCs | No | Future |
| Give gifts | No | Future |
| Fishing | No | Future |
| Mining | No | Future |
| Full day cycle | No | 6am → 2am routine |
| Full season | No | 28 days autonomous |

---

## Phase Plan

### Phase 1: Farming Loop (Current)
- [x] Till ground
- [x] Tool detection
- [x] Tile state awareness
- [ ] Plant seeds
- [ ] Water crops
- [ ] Refill watering can
- [ ] Harvest when ready
- [ ] Sell at shipping bin

### Phase 2: Multi-Day Autonomy
- [ ] Wake up routine
- [ ] Daily task planning
- [ ] Energy management
- [ ] Sleep when tired
- [ ] 3+ day continuous run

### Phase 3: Exploration
- [ ] Navigate to Town
- [ ] Enter/exit buildings
- [ ] Map awareness
- [ ] Pathfinding improvements

### Phase 4: Social
- [ ] NPC interaction
- [ ] Gift giving
- [ ] Calendar awareness
- [ ] Event handling

### Phase 5: Advanced
- [ ] Fishing
- [ ] Mining
- [ ] Combat
- [ ] Season transitions
- [ ] Year planning

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Agent (unified_agent.py)          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐│
│  │  Screen    │─▶│  Qwen3 VL  │─▶│  Action Planning       ││
│  │  Capture   │  │  (8780)    │  │  + Game State Override ││
│  └────────────┘  └────────────┘  └───────────┬────────────┘│
└──────────────────────────────────────────────│─────────────┘
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 SMAPI GameBridge (8790)                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐│
│  │  State     │  │  Action    │  │  Spatial Awareness     ││
│  │  Reader    │  │  Executor  │  │  (surroundings, water) ││
│  └────────────┘  └────────────┘  └────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    UI Server (9001)                         │
│  Dashboard │ Team Chat │ Memory Viewer │ Status Indicators  │
└─────────────────────────────────────────────────────────────┘
```

---

## Team Assignments

### Claude (PM/Agent)
- Agent logic and decision making
- SMAPI mod features
- Bug fixes
- Architecture decisions
- Task assignment

### Codex (UI/Memory)
- Dashboard components
- Memory systems
- Status indicators
- Data visualization

### Tim (Lead)
- Direction and priorities
- Testing and feedback
- Hardware management
- Final approvals

---

## Codex Task Queue

See `docs/CODEX_TASKS.md` for current assignments.

**Potential Future Tasks:**
- Location minimap showing player position
- NPC relationship tracker
- Seasonal calendar with events
- Inventory management panel
- Action history replay

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| VLM hallucinates | Medium | Override with game state |
| Agent gets stuck | High | Stuck detection, recovery |
| Energy runs out | Medium | Energy monitoring, rest |
| Wrong tool used | Medium | Tool-aware instructions |
| Can't find crops | Medium | Crop location from state |
| Night falls | Medium | Time awareness, bed finding |
| GPU OOM | High | Monitor, restart if needed |

---

## Success Metrics

**Phase 1 Complete When:**
- Agent plants 15 seeds without help
- Agent waters all crops daily
- Agent refills can when empty
- Agent harvests mature crops
- Agent sells crops at bin

**Project Complete When:**
- Rusty runs Day 1 → Day 28 autonomously
- Completes farming, foraging, basic social
- No Claude intervention needed
- Entertaining to watch

---

## Quick Reference

### Ports
| Service | Port |
|---------|------|
| llama-server | 8780 |
| SMAPI mod | 8790 |
| UI server | 9001 |

### Key Commands
```bash
# Start agent
python src/python-agent/unified_agent.py --ui --goal "Your goal"

# Check state
curl -s localhost:8790/state | jq .

# Check surroundings
curl -s localhost:8790/surroundings | jq .

# Team chat
./scripts/team_chat.py post claude "message"
```

---

*Make Rusty amazing. — Tim*

*Updated Session 10 — Claude (PM)*
