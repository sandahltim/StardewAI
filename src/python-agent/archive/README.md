# Archived Code

**Archived:** 2026-01-10 (Session 36 cleanup)
**Reason:** Orphaned/unused code identified in project review

## Files

| File | Lines | Description | Why Archived |
|------|-------|-------------|--------------|
| `agent.py` | 735 | Old dual-model agent (Eyes/Brain/Body pattern) | Replaced by unified_agent.py |
| `manual_controller.py` | 145 | Keyboard/mouse control interface | Debug tool, not integrated |
| `controller_gui.py` | 140 | GUI for manual control | Debug tool, not integrated |
| `test_gamepad.py` | 296 | Gamepad testing utility | Test tool, not part of agent |

## Restoration

If needed, these files can be restored:
```bash
mv src/python-agent/archive/*.py src/python-agent/
```

## Folders

| Folder | Description | Why Archived |
|--------|-------------|--------------|
| `knowledge/` | Game knowledge loader/queries | Redundant with `memory/game_knowledge.py` |

## Note

The current active agent is `unified_agent.py` which uses:
- Single VLM (Qwen3VL) for perception + planning
- ModBridgeController for SMAPI communication
- Skills system for action execution
