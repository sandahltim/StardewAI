# Session 35: Vision-First Architecture

**Last Updated:** 2026-01-10 Session 34 by Claude
**Status:** Major architecture redesign planned - vision as primary, SMAPI as validation

---

## Session 34 Summary

### What Worked
- Skill system executing correctly (clear_weeds auto-equips scythe)
- Direction hints improved ("clear 3 tiles, then Weeds")
- Screenshots ARE being captured and sent to VLM

### What Didn't Work
- VLM ignoring vision, following text hints blindly
- Can't navigate around farmhouse (stuck on porch)
- Too much text overwhelming the model
- Spatial reasoning failure despite having vision capability

### Key Insight
**We built great SMAPI infrastructure but used it wrong** - as primary input instead of validation. The VLM should LOOK at the game and decide, then SMAPI validates.

---

## Architecture Redesign

### Current (Broken)
```
SMAPI text → VLM reads text → follows text → ignores vision
```

### New (Vision-First)
```
Vision → VLM decides what to do
                ↓
         SMAPI validates/confirms
                ↓
         Execute or adjust
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: PERCEPTION                          │
│                                                                 │
│  ┌──────────────┐      ┌─────────────────────────────────────┐ │
│  │  Screenshot  │ ──►  │  VLM sees image FIRST               │ │
│  │  (primary)   │      │  "What do I see? Where am I?        │ │
│  └──────────────┘      │   What's around me? What should     │ │
│                        │   I do to reach my goal?"           │ │
│  ┌──────────────┐      │                                     │ │
│  │  Light SMAPI │ ──►  │  Grounding context:                 │ │
│  │  (minimal)   │      │  - Position (X,Y), Time, Energy     │ │
│  └──────────────┘      │  - 3x3 immediate tiles              │ │
│                        │  - Goal + recent actions            │ │
│                        │  - Lessons learned                  │ │
│                        └──────────────────┬──────────────────┘ │
└─────────────────────────────────────────────│───────────────────┘
                                              │
                                              ▼ VLM proposes action
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: VALIDATION                          │
│                                                                 │
│  VLM says: "I want to move south"                              │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SMAPI Check (detailed surroundings)                    │   │
│  │                                                         │   │
│  │  South clear?                                           │   │
│  │  ├─ YES ──► Execute action                              │   │
│  │  └─ NO ───► Return to VLM: "South blocked by {X}.       │   │
│  │             What's your alternative?"                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 3: EXECUTION + LEARNING                │
│                                                                 │
│  Execute via GameBridge → Get new state → Record outcome       │
│                                                                 │
│  If failed: Record lesson                                       │
│  "Tried west from porch → blocked by farmhouse → south worked" │
└─────────────────────────────────────────────────────────────────┘
```

---

## SMAPI Data Layers

| Layer | When Used | Data Provided |
|-------|-----------|---------------|
| **Light** | Always (perception phase) | Position, time, energy, tool, 3x3 tiles |
| **Medium** | On request | Cardinal directions, blocking info |
| **Heavy** | Validation phase | Full surroundings, all objects, exact distances |

---

## New VLM Prompt Structure

### Before (text-heavy):
```
[LONG system prompt with DIRECTIONS, SKILLS, FARMING STATE MACHINE...]
[Image appended at end - ignored]
```

### After (vision-first):
```
SYSTEM:
You are Rusty, an AI farmer. LOOK at the screenshot to understand where you are.
Use your EYES to navigate - you can SEE the game!

Your goal: {goal}
Position: ({x}, {y}) | Time: {time} | Energy: {energy} | Holding: {tool}

Immediate 3x3 tiles:
  [N]     [NE]
[W] [YOU] [E]
  [S]     [SE]

Recent: {last_5_actions}
Lessons: {any_lessons}

LOOK at the image. What do you see? Then decide your action.
Output: {"observation": "I see...", "reasoning": "I should...", "action": {...}}
```

---

## Lessons System (New Feature)

```python
class LessonMemory:
    """Track mistakes and successful corrections for VLM learning."""

    def record_failure(self, attempted: str, blocked_by: str, recovery: str):
        lesson = f"{attempted} → blocked by {blocked_by} → {recovery} worked"
        self.lessons.append(lesson)

    def get_context(self) -> str:
        return "\n".join(self.lessons[-5:])

    def persist(self):
        # Save to logs/lessons.json for cross-session memory
```

---

## Implementation Tasks

### Claude (Session 35)

| Task | Priority | Description |
|------|----------|-------------|
| Vision-first prompt | HIGH | New `build_vision_first_prompt()` - minimal text, observation output |
| Validation layer | HIGH | `validate_action()` checks SMAPI before execute |
| Lesson memory | MEDIUM | Track failures, feed back to VLM |
| Test non-MoE model | MEDIUM | Try Qwen3VL-32B-Instruct for better vision |

### Codex Tasks

| Task | Priority | Description |
|------|----------|-------------|
| Vision Debug View | HIGH | Show VLM observation, proposed vs executed action, validation status |
| Lessons Panel | MEDIUM | Display lessons learned, when applied, reset button |
| Persistent Lessons | LOW | Save/load lessons across sessions |

---

## Model Options

| Model | Vision | Speed | Notes |
|-------|--------|-------|-------|
| Qwen3VL-30B-A3B (current) | Medium | Fast | MoE, may sacrifice visual reasoning |
| Qwen3VL-32B-Instruct | Better | Slower | Dense, test this first |
| Qwen3VL-8B-Thinking | Unknown | Fastest | Explicit reasoning, smaller |

**Plan:** Try 32B-Instruct to see if visual reasoning improves. If too slow, try 8B-Thinking.

---

## Success Criteria

1. Agent navigates off porch using VISION (sees steps, walks down)
2. Agent reaches target plot without text-based navigation hints
3. Lessons recorded when mistakes happen
4. Validation catches impossible actions before execution

---

## Test Commands (Session 35)

```bash
# Start with vision-first (after implementation)
python src/python-agent/unified_agent.py --vision-first --ui --goal "Farm the plot"

# Try alternate model
# Edit config/settings.yaml: model: "Qwen3VL-32B-Instruct-Q4_K_M"
python src/python-agent/unified_agent.py --ui --goal "Navigate to farm"
```

---

## Files to Modify

- `src/python-agent/unified_agent.py`
  - New prompt builder (vision-first)
  - Validation layer before execution
  - Lesson memory integration
- `config/settings.yaml`
  - Simplified system prompt
  - Model switch option
- `src/python-agent/lessons.py` (new)
  - LessonMemory class
- UI components (Codex)
  - Vision debug panel
  - Lessons display

---

*Vision drives decisions. SMAPI validates them. Mistakes become lessons.*

*— Claude (PM), Session 34*
