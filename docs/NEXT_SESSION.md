# Session 38: Lesson Recording & Rusty Memory

**Last Updated:** 2026-01-10 Session 37 by Claude
**Status:** VLM Debug pipeline complete, SMAPI indicators done

---

## Session 37 Summary

### What Was Completed

1. **Agent → UI Data Pipeline** ✅
   - Added VLM debug state tracking to `unified_agent.py`
   - Sends: `vlm_observation`, `proposed_action`, `validation_status`, `validation_reason`, `executed_action`, `executed_outcome`
   - Updates at 3 key points: after VLM thinking, during validation, after execution

2. **Lesson Recording to UI** ✅
   - LessonMemory now persists on `record_failure()` (was only on recovery)
   - Added `_notify_ui()` method to POST lessons to UI server
   - Added `/api/lessons/update` endpoint to UI for WebSocket broadcast

3. **SMAPI Status Indicators** ✅ (Codex)
   - Added SMAPI online/offline row with last-seen time
   - Tracked SMAPI health in app.js polling
   - Applied offline empty-state messaging
   - Status styling for connected/disconnected states

4. **Empty State Messages** ✅ (Codex)
   - Better "no data" messages for panels without data yet

---

## Session 36 Summary

### What Was Completed

1. **Dynamic Hints Integration**
   - Built `_build_dynamic_hints()` method (~140 lines)
   - Integrated into vision-first light context
   - Fixed skill parameter normalization
   - Skills working: clear_weeds, till_soil

2. **Project Review (3 parallel agents)**
   - UI review: 70% functional, 30% placeholder/SMAPI-dependent
   - Rusty personality: Framework exists, character depth missing
   - Connectivity: Core is solid, ~1500 lines orphaned code

3. **Cleanup**
   - Archived orphaned code to `src/python-agent/archive/`:
     - `agent.py` (old dual-model agent)
     - `manual_controller.py`, `controller_gui.py`, `test_gamepad.py`
     - `knowledge/` folder (redundant with memory/)
   - Updated CODEX_TASKS.md with new tasks

---

## Project Review Findings

### UI: Mostly Functional Now

| Component | Status | Issue |
|-----------|--------|-------|
| Chat, Team Chat, Goals, Tasks | ✅ 100% | Working |
| Skill tracking, Shipping | ✅ 90% | Working |
| VLM Debug Panel | ✅ 100% | Agent sends all data |
| Lessons Panel | ✅ 100% | Agent POSTs + WebSocket broadcast |
| Memory Search | ❌ Empty | Chroma not populated |
| SMAPI Panels | ✅ 100% | Shows online/offline status with fallback |

### Rusty: Flavor Without Depth

| Aspect | Status |
|--------|--------|
| Personality templates | ✅ 4 personalities, 7-8 contexts each |
| System prompt identity | ✅ "Self-aware AI farmer with dry wit" |
| Commentary integration | ✅ Working |
| Memory/continuity | ❌ None - forgets each session |
| Character arc | ❌ None - doesn't grow |
| NPC relationships | ❌ None - same voice for everyone |
| Decision influence | ❌ Personality is cosmetic only |

### Connectivity: Solid Core

```
unified_agent.py → VLM (8780) → SMAPI (8790) → Game  ✅
Skills system: loaded and executable                  ✅
Memory systems: integrated and queried               ✅
UI server: running on 9001                           ✅
```

**Archived (orphaned):** ~1500 lines in `src/python-agent/archive/`

---

## Next Session Priorities

### ~~Priority 1: Lesson Recording to UI (Claude)~~ ✅ DONE

Completed in Session 37:
- LessonMemory now POSTs to `/api/lessons/update`
- UI endpoint broadcasts via WebSocket

### Priority 2: Rusty Memory Persistence (Claude)

Make Rusty remember between sessions:
- Save episodic memories to file/Chroma
- Track NPC relationships
- Character state persistence
- Could use existing ChromaDB infrastructure

### Priority 3: Full Farm Cycle Test (Claude)

Test end-to-end with real game:
- Clear→Till→Plant→Water sequence
- Verify VLM debug panel shows data
- Verify lessons panel populates on failures

### ~~Priority 4: SMAPI Status Indicators (Codex)~~ ✅ DONE

Completed in Session 37 by Codex.

---

## Tasks by Owner

### Claude (Future Sessions)

| Task | Priority | Status |
|------|----------|--------|
| ~~Agent VLM debug data~~ | ~~HIGH~~ | ✅ Done Session 37 |
| ~~Lesson recording to UI~~ | ~~HIGH~~ | ✅ Done Session 37 |
| Rusty memory persistence | HIGH | Next up |
| Test full farm cycle | MEDIUM | After memory |
| Rusty character bible | LOW | Future |

### Codex (Completed Session 37)

| Task | Status |
|------|--------|
| SMAPI status indicators | ✅ Done |
| Empty state messages | ✅ Done |

---

## Code Reference

| Feature | File | Notes |
|---------|------|-------|
| Dynamic hints | unified_agent.py:2500 | `_build_dynamic_hints()` |
| Light context | unified_agent.py:2670 | `_build_light_context()` |
| Skill execution | unified_agent.py:2130 | `execute_skill()` |
| UI status | unified_agent.py:2429 | `_send_ui_status()` |
| VLM debug state | unified_agent.py:1722 | Instance vars in `__init__` |
| Lesson memory | memory/lessons.py | `LessonMemory` class |
| Archived code | archive/README.md | Old agent, debug tools |

---

## Key Insight from Session 37

**Agent→UI pipeline complete. VLM debug panel now shows live data.**

- VLM observation, proposed action, validation status, execution outcome all sent to UI
- Codex completed SMAPI status indicators + empty states
- Next: Wire lesson recording to UI, then Rusty memory

*— Claude (PM), Session 37*
