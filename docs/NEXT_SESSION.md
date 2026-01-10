# Next Session - StardewAI

**Last Updated:** 2026-01-10 Session 31 by Claude
**Status:** Crop protection fix + Planned farming system implemented!

---

## Session 31 Results

### Completed This Session

| Task | Status | Notes |
|------|--------|-------|
| Crop protection for watered tiles | ✅ Fixed | Agent was hoeing planted crops - now warns on watered tiles |
| Farm planning module | ✅ Done | New `src/python-agent/planning/` module |
| Plot-based systematic farming | ✅ Done | Define plots, work row-by-row through phases |
| CLI arguments for plots | ✅ Done | `--plot x,y,w,h` and `--clear-plan` |
| Codex UI task assigned | ✅ Assigned | Farm Plan Visualizer in CODEX_TASKS.md |

### Key Implementations

**1. Crop Protection Fix (unified_agent.py:825-827)**
```python
# In tile_state == "watered" branch, now checks:
dangerous_tools = ["Scythe", "Hoe", "Pickaxe", "Axe"]
if tile_obj == "crop" and any(tool.lower() in current_tool.lower() for tool in dangerous_tools):
    front_info = f">>> ⚠️ WATERED CROP HERE! DO NOT use {current_tool}! ..."
```
- Bug: Agent was hoeing watered crops (state="watered" not "planted")
- Fix: Now checks `tile_obj == "crop"` regardless of state

**2. Farm Planning Module (`src/python-agent/planning/`)**
```
planning/
├── __init__.py      # Exports PlotManager, PlotDefinition, etc.
├── models.py        # Dataclasses: PlotDefinition, PlotState, FarmPlan, TileState, PlotPhase
└── plot_manager.py  # PlotManager class with serpentine traversal, phase tracking
```

**3. Systematic Farming Features**
- Define rectangular plots: `--plot 30,20,5,3` (5x3 plot at tile 30,20)
- Serpentine row traversal for efficient pathing
- Phase machine: CLEARING → TILLING → PLANTING → WATERING → DONE
- JSON persistence: `logs/farm_plans/current.json`
- VLM prompt context injection with target tile and action

**4. CLI Arguments**
```bash
--plot x,y,w,h     # Define farm plot at x,y with width w, height h
--clear-plan       # Clear existing farm plan
```

---

## Current State

- **Day 3, Spring Year 1** - rainy day
- **Farm plan active** with 2 test plots
- **Crop protection** working
- **Codex assigned** Farm Plan Visualizer UI task

---

## Codex Task: Farm Plan Visualizer UI

See `docs/CODEX_TASKS.md` for full requirements:
- API endpoint: `GET /api/farm-plan`
- Grid visualizer showing plot progress
- Phase progress bar
- WebSocket real-time updates

---

## Next Session Priorities

### 1. Test Planned Farming End-to-End
- Clear the test plans: `--clear-plan`
- Define a fresh plot near player
- Watch agent work systematically through phases

### 2. Polish Farm Planning
- Verify tile state sync from game data
- Test phase advancement (clearing → tilling → planting → watering)
- Ensure VLM follows plot targets vs random wandering

### 3. Codex Follow-up
- Review UI implementation when complete
- Integrate with agent if needed

### Potential Improvements
- Auto-detect good plot locations from game terrain
- Multiple concurrent plots with priority
- Seed type selection for plots

---

## Test Commands

```bash
# 1. Clear any existing plan
python src/python-agent/unified_agent.py --clear-plan --observe

# 2. Define a 5x3 plot and run
python src/python-agent/unified_agent.py --plot "62,18,5,3" --ui --goal "Work the farm plot systematically"

# 3. Check persisted plan
cat logs/farm_plans/current.json | python3 -m json.tool
```

---

## Files Changed (Session 31)

### New Files
- `src/python-agent/planning/__init__.py`
- `src/python-agent/planning/models.py`
- `src/python-agent/planning/plot_manager.py`

### Modified Files
- `src/python-agent/unified_agent.py`
  - Line 75-80: Import planning module
  - Lines 1555-1566: Initialize PlotManager in StardewAgent.__init__
  - Lines 2410-2424: Add farm plan context to VLM prompt
  - Lines 825-827: Fix crop protection for watered tiles
  - Lines 2596-2613: Add --plot and --clear-plan CLI arguments
- `docs/CODEX_TASKS.md` - Assigned Farm Plan Visualizer UI task

### Persistence
- `logs/farm_plans/current.json` - Active farm plan state

---

## Services

| Service | Port | Status |
|---------|------|--------|
| llama-server | 8780 | Running |
| SMAPI mod | 8790 | Running |
| UI Server | 9001 | Running |

---

## Quick Start Next Session

```bash
# 1. Verify services
curl http://localhost:8780/health
curl http://localhost:8790/health

# 2. Clear old plans and create fresh plot
source venv/bin/activate
python src/python-agent/unified_agent.py --clear-plan --observe

# 3. Run with new plot
python src/python-agent/unified_agent.py --plot "62,18,5,3" --ui --goal "Farm the plot systematically"

# 4. Watch UI at http://localhost:9001
```

---

*Session 31: Fixed crop protection bug, implemented planned farming system with systematic plot-based work. Codex assigned UI visualizer. Ready for end-to-end testing!*

*— Claude (PM)*
