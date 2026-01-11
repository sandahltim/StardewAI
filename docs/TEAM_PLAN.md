# StardewAI Team Plan

**Created:** 2026-01-08
**Last Updated:** 2026-01-11 Session 56
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

## Current Status (Session 54)

### 🚨 NEW: Task Execution Layer (Session 54)

**Problem Identified:** Rusty is tick-reactive, not task-driven. Each VLM call picks random targets instead of working systematically. Result: chaotic "ADHD crackhead" farming.

**Solution:** Add Task Execution Layer between Daily Planner and Skill Executor.

```
┌─────────────────────────────────────────────────────────┐
│                    DAILY PLANNER                        │
│  "Water crops" | "Harvest ready" | "Clear debris"       │
└─────────────────────────┬───────────────────────────────┘
                          │ picks next task
                          ▼
┌─────────────────────────────────────────────────────────┐
│              TASK EXECUTOR (NEW)                        │
│  Current Task: "Water crops"                            │
│  Targets: [(12,15), (13,15), (14,15)] ← row-by-row     │
│  Progress: 2/3 complete                                 │
│                                                         │
│  VLM consulted: every 5th tick (hybrid commentary)     │
│  Priority interrupts: enabled (flexible)                │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              SKILL EXECUTOR (existing)                  │
│  water_crop → [select_slot, face, use_tool]            │
└─────────────────────────────────────────────────────────┘
```

**Key Design Decisions (Tim approved):**
- **Sorting:** Row-by-row (like reading a book) - systematic farmer
- **VLM Role:** Hybrid - commentary every ~5 ticks during execution
- **Flexibility:** Can interrupt for higher priority tasks

**Assignments:**
- Claude: `execution/task_executor.py` - state machine, daily planner integration
- Codex: `execution/target_generator.py` - spatial target sorting

---

### What's Working
| Component | Status | Session |
|-----------|--------|---------|
| VLM Perception (Qwen3VL-30B) | ✅ Working | - |
| SMAPI GameBridge API (24 actions) | ✅ Working | - |
| Farm Planning System | ✅ Working | 31-32 |
| Farm Plan Visualizer UI | ✅ Working | 32 |
| Commentary System (context-aware) | ✅ Improved | 41-42 |
| TTS with Piper | ✅ Working | 27-28 |
| Skill System (55 definitions) | ✅ Working | 20-21 |
| Knowledge Base (NPCs/items/locations) | ✅ Working | 23 |
| Debris Clearing (multi-tool) | ✅ Working | 29-32 |
| Time Management (bedtime warnings) | ✅ Working | 30 |
| Diagonal Movement | ✅ Working | 30 |
| Landmark-Relative Hints | ✅ Working | 25 |
| go_to_bed skill | ✅ Fixed | 41 |
| Obstacle Failure Tolerance | ✅ New | 42 |
| Crop Protection (till blocker) | ✅ New | 42 |
| State-Change Detection | ✅ Working | 44 |
| Daily Planning System | ✅ Working | 44 |
| VLM Text Reasoning | ✅ Working | 44 |
| Daily Plan UI Panel | ✅ Codex | 44 |
| Action Failure UI Panel | ✅ Codex | 44 |
| Growing Crop Hint Fix | ✅ Fixed | 48 |
| Harvest Action (proper SMAPI) | ✅ Fixed | 48 |
| Shipping Hint System | ✅ Working | 49 |
| Shipping Override (aggressive) | ✅ Fixed | 50 |
| ship_item Skill | ✅ Fixed | 50 |
| Synchronous Movement | ✅ Fixed | 50 |
| No-Seeds Override | ✅ New | 51 |
| Edge-Stuck Override | ✅ New | 51 |
| Collision Detection Fix | ✅ Fixed | 51 |
| **Popup/Menu Handling** | ✅ New | 52 |
| **Harvest Direction Fix** | ✅ Fixed | 52 |
| **Warp Case-Sensitivity Fix** | ✅ Fixed | 53 |
| **SeedShop Buy Override** | ✅ New | 53 |
| **Pierre Navigation (direct warp)** | ✅ Fixed | 53 |

### Current Focus
| Task | Status |
|------|--------|
| Shipping workflow | ✅ COMPLETE |
| Edge-stuck recovery | ✅ COMPLETE |
| No-seeds → Pierre's → Buy | ✅ COMPLETE |
| Full seeds flow | ✅ COMPLETE |
| **Task Execution Layer** | ✅ COMPLETE (Session 54) |
| Target Generator (Codex) | ✅ COMPLETE |
| Task Executor (Claude) | ✅ COMPLETE |
| **Event-Driven Commentary** | ✅ COMPLETE (Session 55) |
| **State Path Fixes** | ✅ COMPLETE (Session 55) |
| Multi-day autonomy test | 🔄 READY TO TEST |
| Wake-up routine | 📋 NEXT |
| Periodic re-planning | 📋 NEXT |

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
| use_tool (seeds/planting) | Yes | Working |
| use_tool (fishing rod) | No | Future |
| select_slot (0-11) | Yes | Working |
| harvest | Yes | Working (Session 25) |
| ship | Yes | Working (Session 26) |
| eat | Yes | Working (Session 26) |
| buy | Yes | Working (Session 26) |
| interact (NPCs) | No | Future |
| interact (chests) | No | Future |
| warp (locations) | Yes | Working |

### Locations - Must Navigate All
| Location | Can Enter | Can Navigate | Can Exit |
|----------|-----------|--------------|----------|
| FarmHouse | Yes | Yes | Yes |
| Farm | Yes | Yes | Yes |
| Town | Partial | Needs test | Needs test |
| Pierre's Shop (SeedShop) | Yes | Yes | Yes |
| Beach | No | No | No |
| Forest | No | No | No |
| Mountain | No | No | No |
| Mine | No | No | No |
| Bus Stop | No | No | No |

### Game Cycles - Must Complete
| Cycle | Status | Notes |
|-------|--------|-------|
| Till → Plant → Water | **Yes** | Working (Session 17+) |
| Water daily | Partial | Needs multi-day test |
| Refill watering can | Ready | Water detection added |
| Harvest crops | **Yes** | Working (Session 25) |
| Sell at shipping bin | **Yes** | ship action (Session 26) |
| Buy seeds at shop | **Yes** | buy action (Session 26) |
| Forage items | No | Forageable detection added |
| Talk to NPCs | No | Future |
| Give gifts | No | Future |
| Fishing | No | Future |
| Mining | No | Future |
| Full day cycle | No | 6am → 2am routine |
| Full season | No | 28 days autonomous |

---

## Phase Plan

### Phase 1: Farming Loop ✅ COMPLETE (Session 26)
- [x] Till ground
- [x] Tool detection
- [x] Tile state awareness
- [x] Plant seeds
- [x] Water crops
- [x] Refill watering can
- [x] Harvest when ready
- [x] Sell at shipping bin
- [x] Buy seeds from shop

### Phase 1.5: Skill-Based Actions ✅ COMPLETE (Session 33)
- [x] Skill system infrastructure (55 skills)
- [x] Skill executor with multi-step sequences
- [x] Auto-equip tools in skills (clear_weeds, clear_stone, etc.)
- [x] VLM outputs skill names → executor handles tool selection
- [x] Farm planning system (systematic plot clearing)

### Phase 2: Multi-Day Autonomy (Current)
- [x] Bedtime warnings (go_to_bed at 11pm+)
- [x] Energy monitoring
- [x] Time management
- [x] State-change detection (phantom failure tracking) - Session 44
- [x] Daily task planning (priority queue) - Session 44
- [x] VLM reasoning for planning - Session 44
- [x] Standard daily routine (water→harvest→plant→clear) - Session 44
- [x] **Task Execution Layer** - Session 54 ✅
  - [x] Target Generator (Codex) - sorted spatial targets
  - [x] Task Executor (Claude) - deterministic execution
  - [x] Daily planner integration - completion tracking
  - [x] Hybrid VLM mode - commentary every 5 ticks
  - [x] Priority interruption - flexible task switching
- [ ] Wake up routine + morning planning
- [ ] Periodic re-planning (every 2 game hours)
- [ ] Memory integration (yesterday's lessons → today's plan)
- [ ] 6+ day continuous run (Day 1 → harvest cycle)

### Phase 3: Exploration
- [x] Warp to locations
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
│  │  Screen    │─▶│  Qwen3 VL  │─▶│  Skill/Action Planner  ││
│  │  Capture   │  │  (8780)    │  │  outputs skill names   ││
│  └────────────┘  └────────────┘  └───────────┬────────────┘│
│                                              │              │
│  ┌───────────────────────────────────────────▼────────────┐│
│  │              Skill Executor (skills/)                  ││
│  │  skill_name → [select_slot, face, use_tool] sequence   ││
│  │  45 skills: clear_*, till_*, water_*, harvest_*, etc.  ││
│  └───────────────────────────────────────────┬────────────┘│
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
│  Dashboard │ Farm Plan │ Team Chat │ Status Indicators      │
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
- Landmark-relative directions (e.g., "southeast of farmhouse", "near bus stop")
- **Agent Commentary System** - Real-time narration of what Rusty is doing/thinking (Tim wants to discuss)
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
Final Logic- day starts- Rusty plans his day and creates todo list from day before and final summary before sleep and any inputs from user. then using different modules for each type of task and based on priority and further palnning cycles he completes all that he can and creates daily conclusion for next day. We need to play with model context to see how much of a complete day we can keep with a single model before compact/flush of context cache. We need to add more reasoning and palnning instead of just chaos. The project boils down to an ai model(any VLM we choose) becomes the eyes and brain for the farmer Rusty. He BECOMES the farmer and we hear his running inner monologue throughout the day for comedy genius. This will be evolving so keep updated and ask clarification questions when needed.
*Make Rusty amazing. — Tim*

---

## Session 54 Highlights

**Task Execution Layer Architecture:**
- Identified root cause of chaotic behavior: tick-reactive, not task-driven
- Designed new layer: Daily Planner → Task Executor → Skill Executor
- Tim decisions: row-by-row sorting, hybrid VLM (every 5 ticks), flexible interrupts

**Codex Assignment:**
- Target Generator module (`execution/target_generator.py`)
- Converts tasks to sorted spatial target lists
- Foundation for deterministic execution

**Claude Assignment:**
- Task Executor module (`execution/task_executor.py`)
- State machine for task focus persistence
- Daily planner integration for completion tracking

**Research Findings:**
- `daily_planner.complete_task()` exists but NEVER called - orphaned code
- SMAPI provides all spatial data needed (crop positions, objects, etc.)
- VLM sees daily plan but no "FOCUS NOW" task guidance

---

## Session 44 Highlights

**State-Change Detection:**
- Captures state snapshot before skill execution
- Verifies actual state change after execution
- Tracks consecutive phantom failures per skill
- Hard-fails after 2 consecutive phantom failures
- Records lessons for learning system

**Daily Planning System:**
- New module: `memory/daily_planner.py`
- Auto-triggers on day change
- Standard routine: incomplete→water→harvest→plant→clear
- VLM reasoning for intelligent prioritization
- Plan context added to VLM prompts

**Code Locations:**
| Feature | File | Lines |
|---------|------|-------|
| State capture | unified_agent.py | 2162-2219 |
| State verify | unified_agent.py | 2221-2293 |
| Daily planner | memory/daily_planner.py | All |
| VLM reason | unified_agent.py | 416-446 |

*Updated Session 44 — Claude (PM)*

---

## Session 55 Highlights

**Event-Driven Commentary:**
- VLM triggers on meaningful events, not just timer intervals
- Events: TASK_STARTED, MILESTONE_25/50/75, TARGET_FAILED, ROW_CHANGE, TASK_COMPLETE
- Fallback: Every 5 ticks if no events pending
- Makes Rusty's commentary feel natural and reactive

**Bug Fixes:**
- TargetGenerator state path: `data.location.crops` (not `data.crops`)
- Debris detection: `type="Litter"` (SMAPI format)
- Farm location check: Only start tasks when on Farm map

**Code Locations:**
| Feature | File |
|---------|------|
| CommentaryEvent enum | execution/task_executor.py |
| _extract_crops() | execution/target_generator.py |
| _extract_objects() | execution/target_generator.py |
| Farm location check | unified_agent.py:2785-2790 |

*Updated Session 55 — Claude (PM)*

---

## Session 56 Highlights

**Buy Seeds Skills Fixed:**
- Replaced template `{quantity}` with hardcoded defaults
- `buy_parsnip_seeds`: 5 seeds (100g), `buy_cauliflower_seeds`: 1 (80g), `buy_potato_seeds`: 2 (100g)
- Updated preconditions to match actual costs

**Daily Planner State Path Fixed:**
- Same bug as TargetGenerator in Session 55
- Was looking at `state.location.crops`, fixed to `state.data.location.crops`
- Now correctly generates "Water N crops" task with proper crop count

**Remaining Issue:**
- TaskExecutor not activating despite correct daily planner tasks
- Debug logging added to `_try_start_daily_task()` for Session 57 investigation
- Hypothesis: tick() flow not reaching TaskExecutor check, or planner tasks empty at tick time

*Updated Session 56 — Claude (PM)*
