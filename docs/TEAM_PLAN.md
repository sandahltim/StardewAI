# StardewAI Team Plan

**Created:** 2026-01-08
**Project Lead:** Claude (Opus) - Agent logic, architecture, coordination
**UI/Memory:** Codex - User interface, memory systems, state persistence
**Human Lead:** Tim - Direction, testing, hardware, final decisions

---

## Current Sprint: Movement Integration

### Goal
Get Rusty walking around the farm autonomously using VLM perception + SMAPI mod control.

### Success Criteria
- [ ] Rusty can walk out of farmhouse on command
- [ ] VLM perceives game state and decides next action
- [ ] Mod executes movement without clipping/collision issues
- [ ] Full loop runs for 5+ minutes without crashes

---

## Phase 1: Infrastructure Verification (Today)

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| Start llama-server | Claude | Pending | Port 8780, Qwen3VL-30B-A3B |
| Start Stardew + SMAPI | Tim | Pending | Verify mod loads |
| Test mod health endpoint | Claude | Pending | `curl :8790/health` |
| Test movement fix | Claude | Pending | Pixel offset was just patched |
| Test door transitions | Claude | Pending | Walk through farmhouse door |

### Startup Sequence
```bash
# 1. Start llama-server (Terminal 1)
cd /home/tim/StardewAI
./scripts/start-llama-server.sh

# 2. Start Stardew Valley via Steam (Tim)
# - Must have SMAPI installed
# - Load save with Rusty

# 3. Verify mod is running
curl http://localhost:8790/health
```

---

## Phase 2: Python Agent Integration

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| Create ModBridgeController class | Claude | Pending | HTTP client for mod API |
| Update unified_agent.py | Claude | Pending | Use mod instead of vgamepad |
| Add action translation | Claude | Pending | VLM output → mod commands |
| Test observe mode | Claude | Pending | VLM perception only |
| Test control mode | Claude | Pending | Full loop |

### Architecture After Integration
```
┌─────────────────────────────────────────────────────────────┐
│                      Python Agent                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Screen     │───▶│   Qwen3 VL   │───▶│  Action      │  │
│  │   Capture    │    │  (8780)      │    │  Translator  │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘  │
└──────────────────────────────────────────────────│──────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    SMAPI GameBridge (8790)                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   State      │    │   Action     │    │   Movement   │  │
│  │   Reader     │    │   Executor   │    │   Queue      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                        Game1.player.Position
```

---

## Phase 3: Full Loop Testing

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| 5-minute autonomous run | Claude | Pending | Watch for failures |
| Log analysis | Claude | Pending | Identify patterns |
| Prompt tuning | Claude | Pending | Fix perception errors |
| Edge case handling | Claude | Pending | Energy=0, nighttime, etc |

---

## For Codex: UI/Memory Integration Points

### Data Available from Mod API

```json
// GET /state response
{
  "data": {
    "player": {
      "name": "Rusty",
      "tileX": 10,
      "tileY": 15,
      "facingDirection": 2,
      "currentTool": "Hoe",
      "energy": 270,
      "maxEnergy": 270,
      "money": 500
    },
    "time": {
      "timeOfDay": 630,
      "dayOfMonth": 1,
      "season": "spring",
      "year": 1
    },
    "location": {
      "name": "FarmHouse",
      "objects": [...],
      "npcs": [...]
    }
  }
}
```

### Memory System Hooks Needed

1. **Session Memory** - Track what Rusty did this session
   - Actions taken
   - Locations visited
   - Items gathered/used

2. **Farm Knowledge** - Persistent across sessions
   - Crop locations and stages
   - Chest contents
   - Upgrade status

3. **Social Memory** - NPC relationships
   - Gift preferences learned
   - Friendship levels
   - Conversation history

### UI Ideas (Codex's Domain)

- **Live Dashboard**: Show Rusty's current state (energy, location, goal)
- **Action Log**: Stream of VLM perceptions and actions
- **Chat Interface**: Human ↔ Rusty communication
- **Memory Viewer**: What Rusty "remembers"

---

## Team Communication

### Current: Async via Docs
- SESSION_LOG.md - Progress notes
- TEAM_PLAN.md - This document
- NEXT_SESSION.md - Handoff notes

### Proposed: Local Real-time Chat

Options to evaluate:
1. **Simple HTTP polling** - Agent writes to file, UI polls
2. **WebSocket server** - Real-time bidirectional
3. **SQLite queue** - Persistent message storage

**Recommendation:** Start with file-based (simple), upgrade to WebSocket when UI is ready.

```
/home/tim/StardewAI/
├── comms/
│   ├── claude_outbox.jsonl    # Claude → Team
│   ├── codex_outbox.jsonl     # Codex → Team
│   ├── tim_outbox.jsonl       # Tim → Team
│   └── broadcast.jsonl        # All messages merged
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| VLM hallucinates actions | Medium | Validate actions against game state |
| Movement causes collision | High | Already added collision detection |
| Mod API race conditions | Medium | Add retry logic, state verification |
| GPU OOM with long sessions | High | Monitor VRAM, restart if needed |
| Game crash loses progress | Medium | Frequent autosaves |

---

## Quick Reference

### Ports
| Service | Port | Purpose |
|---------|------|---------|
| llama-server | 8780 | VLM inference |
| SMAPI mod | 8790 | Game control |
| (Future) UI | 8791 | Web dashboard |

### Key Files
| File | Owner | Purpose |
|------|-------|---------|
| `unified_agent.py` | Claude | Main agent loop |
| `ActionExecutor.cs` | Claude | SMAPI movement |
| `src/ui/app.py` | Codex | Web UI |
| `src/ui/storage.py` | Codex | Memory persistence |

---

*Updated by Claude - 2026-01-08*
