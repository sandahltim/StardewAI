# StardewAI Module Refactoring Plan

**Created:** 2026-01-16 Session 135
**Status:** Planning
**Goal:** Split unified_agent.py (10,345 lines) into focused modules

---

## Executive Summary

**Problem:** `unified_agent.py` has grown to 10,345 lines with 115 methods. Similar patterns are duplicated 150+ times, making fixes error-prone.

**Solution:** Extract 8 focused modules, reducing main file to ~1,200 lines while improving testability and maintainability.

**Impact:**
- 88% reduction in main file size
- Testable independent units
- Centralized patterns eliminate duplication
- Faster IDE performance and LLM regeneration

---

## Current State

### unified_agent.py Breakdown

| Category | Methods | Lines | Status |
|----------|---------|-------|--------|
| Batch Skills | 17 | ~2,500 | **Highly repetitive** |
| State Retrieval (get_*) | 21 | ~600 | Independent getters |
| Hints/Context | 11 | ~1,200 | Duplicated patterns |
| Action Filtering (_fix_*) | 6 | ~800 | Similar logic |
| State Verification | 5 | ~200 | Duplicated logic |
| Task Lifecycle | 6 | ~600 | 3-phase pattern |
| VLM/Parsing | 6 | ~480 | UnifiedVLM class |
| UI/Telemetry | 12 | ~400 | Logging/events |
| Core Orchestration | 8 | ~1,200 | Essential logic |
| **Total** | **115** | **10,345** | |

### Critical Duplications Found

| Pattern | Occurrences | Impact |
|---------|-------------|--------|
| Chest finding & interaction | 4+ | Same code in 3+ methods |
| Item/object name search | 8+ | Manual loops vs InventoryManager |
| Material counting | 6+ | Same iteration pattern |
| State refresh + extraction | **150+** | `_refresh_state_snapshot()` everywhere |
| Direction calculations | 4+ | Could reuse existing method |
| Seed finding | 7+ | Should use InventoryManager |

---

## Proposed Module Structure

```
src/python-agent/
├── unified_agent.py          # 1,200 lines - Core orchestration only
├── modules/
│   ├── __init__.py
│   ├── vlm_interface.py      # 480 lines - VLM inference & parsing
│   ├── game_state.py         # 600 lines - State retrieval (get_* methods)
│   ├── state_verifier.py     # 200 lines - State verification
│   ├── context_builder.py    # 1,200 lines - VLM prompt generation
│   ├── batch_skills.py       # 2,500 lines - Autonomous skill execution
│   ├── action_fixers.py      # 800 lines - Problem detection/correction
│   ├── task_lifecycle.py     # 600 lines - Multi-step task orchestration
│   └── telemetry.py          # 400 lines - UI updates, logging
├── helpers/
│   ├── __init__.py
│   ├── inventory.py          # Centralized inventory operations
│   ├── navigation.py         # Direction calculation, movement
│   └── objects.py            # Object/chest finding
```

---

## Module Specifications

### 1. modules/vlm_interface.py (~480 lines)

**Extracts:** `UnifiedVLM` class

**Methods:**
- `infer(screenshot, prompt, state_context)`
- `_parse_response(raw_response)`
- `_repair_json(text)`
- `_extract_json_from_text(text)`

**Dependencies:** None (standalone)
**Test Ready:** YES

### 2. modules/game_state.py (~600 lines)

**Extracts:** All `get_*` methods from StardewAgent

**Methods:**
- `get_state()`, `get_farm()`, `get_skills()`
- `get_npcs()`, `get_animals()`, `get_machines()`
- `get_calendar()`, `get_fishing()`, `get_mining()`
- `get_storage()`, `get_world_state()`

**Dependencies:** `smapi_client`
**Test Ready:** YES

### 3. modules/state_verifier.py (~200 lines)

**Extracts:** Verification methods

**Methods:**
- `verify_tilled()`, `verify_planted()`
- `verify_watered()`, `verify_cleared()`
- `verify_player_at()`
- `get_verification_snapshot()`

**Dependencies:** `game_state.py`
**Test Ready:** YES

### 4. modules/context_builder.py (~1,200 lines)

**Extracts:** Hint generation methods

**Methods:**
- `_get_done_farming_hint()`, `_calc_adjacent_hint()`
- `_get_adjacent_debris_hint()`, `_get_time_urgency_hint()`
- `_get_spatial_hint()`, `_get_skill_context()`
- `_get_task_executor_context()`, `_build_dynamic_hints()`
- `_build_light_context()`, `_get_monster_tactics()`

**Dependencies:** `game_state.py`, `state_verifier.py`
**Test Ready:** YES

### 5. modules/batch_skills.py (~2,500 lines) - LARGEST

**Extracts:** All `_batch_*` methods

**Methods:**
- `_batch_water_remaining()`, `_batch_plant_seeds()`
- `_batch_mine_session()`, `_batch_gather_wood()`
- `_batch_gather_fiber()`, `_batch_till_and_plant()`
- `_batch_organize_inventory()`, `_batch_craft_chest()`
- `_batch_place_chest()`, `_batch_craft_scarecrow()`
- `_batch_place_scarecrow()`, `_batch_farm_chores()`

**Dependencies:** All modules
**Test Ready:** PARTIAL (needs async mocking)

### 6. modules/action_fixers.py (~800 lines)

**Extracts:** Action correction methods

**Methods:**
- `_fix_empty_watering_can()`, `_fix_active_popup()`
- `_fix_late_night_bed()`, `_fix_priority_shipping()`
- `_fix_no_seeds()`, `_fix_edge_stuck()`

**Dependencies:** Minimal
**Test Ready:** YES (pure functions)

### 7. modules/task_lifecycle.py (~600 lines)

**Extracts:** Multi-step task orchestration

**Methods:**
- `_start_cell_farming()`, `_process_cell_farming()`
- `_finish_cell_farming()`, `_start_day1_clearing()`
- `_process_day1_clearing()`, `_finish_day1_clearing()`

**Dependencies:** `batch_skills.py`
**Test Ready:** PARTIAL

### 8. modules/telemetry.py (~400 lines)

**Extracts:** UI and logging methods

**Methods:**
- `_send_ui_status()`, `_send_ui_message()`
- `_send_commentary()`, `_record_action_event()`
- `_record_session_event()`, `_track_vlm_parse()`

**Dependencies:** None (HTTP calls)
**Test Ready:** YES (mock HTTP)

---

## Helper Modules (Eliminate Duplication)

### helpers/inventory.py

**Consolidates:**
- Inventory item search (8+ duplications)
- Material counting (6+ duplications)
- Seed finding (7+ duplications)

**Key Functions:**
```python
def find_item_in_inventory(inventory: List, name: str) -> Optional[Dict]:
    """Find item by name (case-insensitive)."""

def count_materials(inventory: List, names: List[str]) -> Dict[str, int]:
    """Count multiple materials in one pass."""

def find_seeds(inventory: List) -> List[Dict]:
    """Find all seed items."""

def get_item_slot(inventory: List, name: str) -> Optional[int]:
    """Get slot index for item."""
```

### helpers/navigation.py

**Consolidates:**
- Direction calculations (4+ duplications)
- Facing direction from position

**Key Functions:**
```python
def direction_to_target(px: int, py: int, tx: int, ty: int) -> str:
    """Calculate cardinal direction from source to target."""

def get_adjacent_tiles(x: int, y: int) -> List[Tuple[int, int, str]]:
    """Get (x, y, facing_direction) for adjacent tiles."""
```

### helpers/objects.py

**Consolidates:**
- Object finding by name (4+ duplications)
- Chest finding and interaction

**Key Functions:**
```python
def find_object_by_name(objects: List, name: str) -> Optional[Tuple[int, int]]:
    """Find object position by name (case-insensitive)."""

def find_chest(location_data: Dict) -> Optional[Tuple[int, int]]:
    """Find chest position in location."""
```

### helpers/state.py

**Consolidates:**
- State refresh patterns (150+ duplications)
- Safe extraction with defaults

**Key Functions:**
```python
def get_inventory(state: Dict) -> List:
    """Safely extract inventory from state."""

def get_player_position(state: Dict) -> Tuple[int, int]:
    """Safely extract player position."""

def get_location_data(state: Dict) -> Dict:
    """Safely extract location data."""
```

---

## Extraction Sequence

### Phase 1: Helpers (1-2 hours)
**Why first:** No dependencies, immediately reduces duplication

1. Create `helpers/inventory.py`
2. Create `helpers/navigation.py`
3. Create `helpers/objects.py`
4. Create `helpers/state.py`
5. Update imports in unified_agent.py

### Phase 2: Independent Modules (2-3 hours)
**Why second:** No internal dependencies

1. Extract `modules/vlm_interface.py`
2. Extract `modules/game_state.py`
3. Extract `modules/telemetry.py`

### Phase 3: Dependent Modules (3-4 hours)
**Why third:** Depend on Phase 2

1. Extract `modules/state_verifier.py`
2. Extract `modules/context_builder.py`
3. Extract `modules/action_fixers.py`

### Phase 4: Complex Modules (4-6 hours)
**Why last:** Depend on everything else

1. Extract `modules/batch_skills.py`
2. Extract `modules/task_lifecycle.py`
3. Clean up `unified_agent.py` to orchestration only

---

## Dependency Graph

```
helpers/*                    (standalone)
    ↓
vlm_interface.py            (standalone)
game_state.py               (uses helpers)
telemetry.py                (standalone)
    ↓
state_verifier.py           (uses game_state)
    ↓
context_builder.py          (uses game_state, state_verifier)
action_fixers.py            (minimal deps)
    ↓
batch_skills.py             (uses all above)
    ↓
task_lifecycle.py           (uses batch_skills)
    ↓
unified_agent.py            (orchestrates all)
```

---

## Testing Strategy

### Unit Tests (Per Module)

```
tests/
├── test_helpers/
│   ├── test_inventory.py
│   ├── test_navigation.py
│   └── test_objects.py
├── test_modules/
│   ├── test_vlm_interface.py
│   ├── test_game_state.py
│   ├── test_state_verifier.py
│   └── test_context_builder.py
```

### Integration Tests

- Test module interactions
- Mock SMAPI responses
- Verify action execution flow

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes | Extract one module at a time, test after each |
| Import cycles | Use dependency injection, clear layering |
| Performance regression | Profile before/after extraction |
| Lost functionality | Keep original file as backup until verified |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Main file lines | 10,345 | ~1,200 |
| Largest module | 10,345 | ~2,500 |
| Duplicated patterns | 150+ | 0 |
| Test coverage | ~0% | ~80% per module |
| IDE responsiveness | Slow | Fast |

---

## Codex Tasks

### Immediate (Can start now)

1. **Create helper modules** - Extract inventory, navigation, objects, state helpers
2. **Add unit tests** - Test helpers before extracting more

### Next Sprint

3. **Extract vlm_interface.py** - Standalone VLM class
4. **Extract game_state.py** - All get_* methods
5. **Extract telemetry.py** - UI/logging methods

### Following Sprint

6. **Extract remaining modules** - Verifiers, context, batch skills
7. **Clean up unified_agent.py** - Pure orchestration

---

## Notes

- Keep `ModBridgeController` and `GamepadController` in unified_agent.py for now
- Consider extracting to `controllers/` module later
- Maintain backward compatibility during extraction
- Use `from modules.X import Y` pattern for clean imports

---

**Next Action:** Create helpers/ directory and start with inventory.py extraction
