# Session 115: Action Verification Gap Analysis

**Date:** 2026-01-15
**Status:** IN PROGRESS
**Priority:** CRITICAL

---

## Executive Summary

Batch farm chores (till, plant, water) log success but don't actually execute in-game because:
1. **Python code** increments counters without verifying SMAPI state
2. **SMAPI ActionExecutor** returns success after calling game API, without checking result
3. **No feedback loop** - we have full game state access but don't use it to verify

---

## Architecture Problem

```
Current Flow (BROKEN):
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Python: use_tool("north")                                          │
│      │                                                              │
│      ▼                                                              │
│  HTTP POST /action → SMAPI ActionExecutor.UseTool()                 │
│      │                                                              │
│      ▼                                                              │
│  C#: player.BeginUsingTool() → returns "Success" immediately        │
│      │                                                              │
│      ▼                                                              │
│  Python: tilled += 1  ← ASSUMES SUCCESS WITHOUT CHECKING!           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Required Flow (FIXED):
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Python: use_tool("north") at target (x, y)                         │
│      │                                                              │
│      ▼                                                              │
│  HTTP POST /action → SMAPI ActionExecutor.UseTool()                 │
│      │                                                              │
│      ▼                                                              │
│  Wait for tool animation (0.5s)                                     │
│      │                                                              │
│      ▼                                                              │
│  Python: get_farm() → check tilledTiles contains (x, y)             │
│      │                                                              │
│      ├── YES → tilled += 1, proceed to plant                        │
│      └── NO  → log error, retry or skip                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Root Cause Analysis

### 1. ModBridgeController._send_action (Line 1949-1967)

```python
def _send_action(self, payload: Dict[str, Any]) -> bool:
    resp = httpx.post(f"{self.base_url}/action", json=payload, timeout=5)
    if resp.status_code == 200:
        result = resp.json()
        if result.get("success"):
            return True  # TRUSTS SMAPI blindly!
    return False
```

**Problem:** Returns True based on HTTP 200 + JSON success field. Doesn't verify game state changed.

### 2. _batch_till_and_plant (Line 3575-3758)

```python
# Line 3717-3726
self.controller.execute(Action("use_tool", {"direction": "north"}, "till"))
await asyncio.sleep(0.5)
tilled += 1  # ← INCREMENTS WITHOUT VERIFICATION!

self.controller.execute(Action("use_tool", {"direction": "north"}, "plant"))
await asyncio.sleep(0.3)
planted += 1  # ← INCREMENTS WITHOUT VERIFICATION!
```

**Problem:** Counters increment unconditionally. No call to `get_farm()` to verify.

### 3. ActionExecutor.UseTool (Line 340-430 in C#)

```csharp
if (tool != null)
{
    player.BeginUsingTool();  // Queues animation
    _waitTicksRemaining = 30;  // Wait for animation
    return new ActionResult
    {
        Success = true,  // ← RETURNS SUCCESS IMMEDIATELY!
        Message = $"Using {tool.DisplayName}",
        State = ActionState.PerformingAction
    };
}
```

**Problem:** Returns success after calling `BeginUsingTool()`, doesn't verify tile state changed.

---

## Available Verification Data

SMAPI's `/farm` endpoint already provides everything we need:

| Field | Type | Use For |
|-------|------|---------|
| `tilledTiles` | `[{x, y}]` | Verify tilling worked |
| `crops` | `[{x, y, isWatered, ...}]` | Verify planting & watering |
| `grassPositions` | `[{x, y}]` | Check if grass still present |
| `objects` | `[{x, y, name}]` | Check if debris cleared |
| `resourceClumps` | `[{x, y, width, height}]` | Large obstacles (stumps/boulders) |

---

## Fix Implementation Plan

### Phase 1: Add Verification Helpers to ModBridgeController

```python
def verify_tilled(self, x: int, y: int) -> bool:
    """Check if tile at (x,y) is now tilled."""
    farm = self.get_farm()
    if not farm:
        return False
    tilled = {(t.get("x"), t.get("y")) for t in farm.get("tilledTiles", [])}
    return (x, y) in tilled

def verify_planted(self, x: int, y: int) -> bool:
    """Check if crop exists at (x,y)."""
    farm = self.get_farm()
    if not farm:
        return False
    crops = {(c.get("x"), c.get("y")) for c in farm.get("crops", [])}
    return (x, y) in crops

def verify_watered(self, x: int, y: int) -> bool:
    """Check if crop at (x,y) is watered."""
    farm = self.get_farm()
    if not farm:
        return False
    for crop in farm.get("crops", []):
        if crop.get("x") == x and crop.get("y") == y:
            return crop.get("isWatered", False)
    return False
```

### Phase 2: Update _batch_till_and_plant with Verification

```python
# After tilling
self.controller.execute(Action("use_tool", {"direction": "north"}, "till"))
await asyncio.sleep(0.5)

# VERIFY: Check if tile actually got tilled
if self.controller.verify_tilled(x, y):
    tilled += 1
    logging.info(f"✓ Tilled ({x},{y}) verified")
else:
    logging.error(f"✗ Till FAILED at ({x},{y}) - tile not tilled!")
    continue  # Skip planting since till failed

# After planting (only if till succeeded)
self.controller.execute(Action("use_tool", {"direction": "north"}, "plant"))
await asyncio.sleep(0.3)

# VERIFY: Check if crop now exists
if self.controller.verify_planted(x, y):
    planted += 1
    logging.info(f"✓ Planted ({x},{y}) verified")
else:
    logging.error(f"✗ Plant FAILED at ({x},{y}) - no crop found!")
```

### Phase 3: Fix _batch_water_remaining Similarly

Add verification after each water action using `verify_watered()`.

---

## Testing Protocol

### 1. Manual Action Test (curl)

```bash
# Test individual actions work
curl -s -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action":"select_item_type","itemType":"Hoe"}'

curl -s -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action":"face","direction":"north"}'

curl -s -X POST http://localhost:8790/action \
  -H "Content-Type: application/json" \
  -d '{"action":"use_tool","direction":"north"}'

# Then check farm state
curl -s http://localhost:8790/farm | jq '.data.tilledTiles'
```

### 2. Integration Test Script

Create `scripts/test_till_verify.py`:
```python
# 1. Get farm state before
# 2. Execute till action
# 3. Wait for animation
# 4. Get farm state after
# 5. Compare tilledTiles before/after
# 6. Report pass/fail
```

---

## SMAPI Cache Consideration

`ModEntry.cs` line 40: `StateUpdateInterval = 15` ticks (~250ms)

**Impact:** After an action, `get_farm()` may return stale data for up to 250ms.

**Mitigation:**
- Current delay of 0.5s after tilling is sufficient (2x cache interval)
- Alternative: Add `/farm/fresh` endpoint that forces refresh

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/python-agent/unified_agent.py` | Add verification helpers, fix batch methods |
| `scripts/test_till_verify.py` | New integration test |
| `docs/NEXT_SESSION.md` | Update with fixes |

---

## Success Criteria

1. `_batch_till_and_plant` logs match actual game state
2. Failed actions are logged with clear error messages
3. Integration test passes: till → verify → plant → verify → water → verify
4. No more "12 tilled, 12 planted" when only 2 crops exist

---

## Timeline

- Phase 1 (verification helpers): 15 min
- Phase 2 (fix batch till/plant): 20 min
- Phase 3 (fix batch water): 10 min
- Testing: 15 min

**Total: ~1 hour**

---

*-- Claude, Session 115 PM*
