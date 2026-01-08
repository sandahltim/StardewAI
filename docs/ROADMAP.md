# Implementation Roadmap

## Phase 0: Proof of Concept (Start Here)

**Goal:** Verify the vision-based approach works before building complex systems.

### 0.1 - Basic Vision Test
- [ ] Screenshot capture of Stardew Valley window
- [ ] Send screenshot to Qwen3 VL, get description
- [ ] Verify Qwen3 can identify: location, time, player position, toolbar

```python
# test_vision.py - Quick validation script
from mss import mss
import httpx
import base64

# Capture screen
with mss() as sct:
    screenshot = sct.grab(sct.monitors[1])

# Send to Qwen3 VL
# ... (test code)
```

### 0.2 - Basic Input Test
- [ ] pyautogui click on Stardew window
- [ ] Verify game responds to simulated input
- [ ] Test keyboard inputs (WASD movement)

### 0.3 - Simple Command Loop
- [ ] "Walk right" → Qwen3 sees screen → outputs keypress → executes
- [ ] "Use tool" → Qwen3 identifies tool slot → clicks
- [ ] Human-in-loop: you type commands, AI executes

**Deliverable:** Working script that takes text commands and executes them via vision.

---

## Phase 1: Core Agent Loop

**Goal:** Autonomous operation with brain/body split.

### 1.1 - Perception Pipeline
- [ ] Continuous screen capture (1 FPS)
- [ ] Qwen3 VL perception prompts
- [ ] Structured output parsing (JSON)
- [ ] Perception history/memory

### 1.2 - Planning Pipeline
- [ ] Nemotron integration
- [ ] Goal → Plan decomposition
- [ ] Step validation
- [ ] Plan adjustment on failure

### 1.3 - Execution Pipeline
- [ ] Step → Action translation
- [ ] Action execution (click/key)
- [ ] Success verification
- [ ] Retry logic

### 1.4 - Integration
- [ ] Full brain ↔ body loop
- [ ] Logging and debugging
- [ ] Screenshot archival

**Deliverable:** Agent that can execute multi-step tasks like "water crops" autonomously.

---

## Phase 2: Game Knowledge

**Goal:** Teach the agent about Stardew Valley mechanics.

### 2.1 - Farm Operations
- [ ] Crop lifecycle (plant → water → harvest)
- [ ] Tool usage patterns
- [ ] Energy management
- [ ] Time awareness (sleep before 2am)

### 2.2 - Navigation
- [ ] Location recognition
- [ ] Door/transition detection
- [ ] Pathfinding between areas
- [ ] Obstacle avoidance

### 2.3 - Inventory Management
- [ ] Item identification
- [ ] Toolbar organization
- [ ] Chest storage
- [ ] Shopping

**Deliverable:** Agent can run a basic farming day autonomously.

---

## Phase 3: Co-op Integration

**Goal:** Play alongside human as helpful partner.

### 3.1 - Communication
- [ ] Chat interface (in-game or external)
- [ ] Task assignment from human
- [ ] Status reporting
- [ ] Question asking when uncertain

### 3.2 - Coordination
- [ ] Avoid duplicating human's work
- [ ] Division of labor
- [ ] Shared goal tracking

### 3.3 - Multiplayer Setup
- [ ] Steam co-op connection
- [ ] Second game instance or cabin join
- [ ] Player identification

**Deliverable:** Functional co-op partner that takes commands and helps farm.

---

## Phase 4: SMAPI Integration (Optional)

**Goal:** More reliable action execution via game API.

### 4.1 - Mod Development
- [ ] Basic SMAPI mod structure
- [ ] HTTP server in mod
- [ ] Game state reading
- [ ] Action execution

### 4.2 - Hybrid Mode
- [ ] Vision for perception
- [ ] SMAPI for actions
- [ ] Fallback between methods

**Deliverable:** More reliable action execution, less visual error.

---

## Phase 5: Advanced Features

### 5.1 - Long-term Planning
- [ ] Season planning
- [ ] Crop rotation
- [ ] Income optimization

### 5.2 - Social
- [ ] NPC relationships
- [ ] Gift giving
- [ ] Festival participation

### 5.3 - Combat
- [ ] Mine exploration
- [ ] Enemy recognition
- [ ] Combat actions

---

## Quick Start Checklist

To begin Phase 0:

1. **Install dependencies:**
   ```bash
   cd /home/tim/StardewAI
   python3 -m venv venv
   source venv/bin/activate
   pip install mss pillow httpx pyautogui
   ```

2. **Verify Ollama servers:**
   ```bash
   # Local Nemotron
   curl http://localhost:11434/api/tags

   # Remote Qwen3 VL (replace IP)
   curl http://192.168.x.x:11434/api/tags
   ```

3. **Start Stardew Valley** in windowed mode

4. **Run test script** (to be created)

---

## Decision Points

### Vision-Only vs SMAPI Hybrid?

| Approach | Pros | Cons |
|----------|------|------|
| **Vision-only** | No mod needed, works with any game | Less precise, slower, can fail on visual edge cases |
| **SMAPI hybrid** | Precise actions, fast, reliable | Requires C# mod development, more complex |

**Recommendation:** Start vision-only (Phase 0-2), add SMAPI later if needed (Phase 4).

### Single Instance vs Two Instances?

| Setup | Pros | Cons |
|-------|------|------|
| **One instance, AI on same screen** | Simple, AI sees your game | Can interfere with your play |
| **Two instances, split-screen** | Independent, true co-op | More resource intensive |
| **Headless server + AI client** | Clean separation | Complex setup |

**Recommendation:** Start with one instance. Move to two instances for real co-op in Phase 3.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Qwen3 VL too slow | Cache perceptions, reduce frequency, use for complex tasks only |
| Visual recognition fails | Add fallback patterns, SMAPI for critical actions |
| Actions miss targets | Add verification loop, retry with offset |
| Game updates break vision | Version-lock game, update prompts as needed |
| Multiplayer sync issues | Use SMAPI for position sync, conservative actions |
