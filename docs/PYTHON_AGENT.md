# Python Agent Design: Dual-Model Architecture

## Philosophy: Brain + Eyes/Body

Instead of a single model doing everything, we split cognitive functions:

```
┌─────────────────────────────────────────────────────────────────┐
│                        NEMOTRON (Brain)                         │
│  - Planning & coordination                                      │
│  - Task decomposition                                           │
│  - Decision making                                              │
│  - Memory & context management                                  │
│  - Goal tracking                                                │
│  Location: Main server (localhost:11434)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                    Instructions & Goals
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     QWEN3 VL (Eyes/Body)                        │
│  - Screen perception                                            │
│  - Visual understanding                                         │
│  - Action execution via screen coords                           │
│  - Real-time reaction                                           │
│  Location: Vision server (192.168.x.x:11434)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Split?

| Aspect | Nemotron (Brain) | Qwen3 VL (Eyes/Body) |
|--------|------------------|----------------------|
| **Strength** | Fast reasoning, planning | Visual understanding |
| **Weakness** | Can't see | Slower, higher latency |
| **Frequency** | Every few seconds | Every action |
| **Context** | Long-term goals, state | Current screen |
| **Output** | High-level instructions | Low-level actions |

## Cognitive Loop

```
┌──────────────────────────────────────────────────────────────────┐
│                       PLANNING CYCLE                             │
│                    (runs every 2-5 seconds)                      │
│                                                                  │
│  1. Qwen3 sees screen → "I see the farm, crops need water"      │
│  2. Nemotron gets perception + goal → "Water the 6 parsnips"    │
│  3. Nemotron outputs plan:                                       │
│     - Step 1: Equip watering can                                │
│     - Step 2: Move to crop area                                 │
│     - Step 3: Water each crop                                   │
│  4. Plan sent to Qwen3 for execution                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      EXECUTION CYCLE                             │
│                  (runs continuously per step)                    │
│                                                                  │
│  1. Qwen3 receives step: "Equip watering can"                   │
│  2. Qwen3 sees screen: identifies toolbar, watering can slot    │
│  3. Qwen3 outputs action: {"click": {"x": 150, "y": 50}}        │
│  4. Action executed via input simulation                        │
│  5. Qwen3 verifies: "Watering can is now equipped"              │
│  6. Reports success, moves to next step                         │
└──────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/python-agent/
├── stardew_ai/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Settings & server addresses
│   │
│   ├── brain/                  # Nemotron integration
│   │   ├── __init__.py
│   │   ├── planner.py          # High-level planning
│   │   ├── task_manager.py     # Task queue & progress
│   │   ├── memory.py           # Context & history
│   │   └── prompts.py          # System prompts for Nemotron
│   │
│   ├── body/                   # Qwen3 VL integration
│   │   ├── __init__.py
│   │   ├── perceiver.py        # Screen capture & understanding
│   │   ├── executor.py         # Action execution
│   │   ├── verifier.py         # Action verification
│   │   └── prompts.py          # System prompts for Qwen3
│   │
│   ├── interface/              # Game interaction
│   │   ├── __init__.py
│   │   ├── screen_capture.py   # Screenshot utilities
│   │   ├── input_sim.py        # Mouse/keyboard simulation
│   │   └── smapi_client.py     # SMAPI mod HTTP client
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging.py
│
├── config/
│   ├── settings.yaml           # Server addresses, timing
│   ├── brain_prompts.yaml      # Nemotron system prompts
│   └── body_prompts.yaml       # Qwen3 VL prompts
│
├── requirements.txt
└── README.md
```

## Core Classes

### Brain (Nemotron)

```python
# brain/planner.py

class BrainPlanner:
    """High-level planning with Nemotron."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url, model="nemotron-nano")
        self.memory = ConversationMemory()

    def create_plan(self, perception: str, current_goal: str) -> Plan:
        """
        Given what the eyes see and the current goal,
        create a step-by-step plan.
        """
        prompt = f"""
        You are the brain of a Stardew Valley AI player.

        CURRENT GOAL: {current_goal}

        WHAT I SEE: {perception}

        Create a step-by-step plan to achieve the goal.
        Output JSON:
        {{
            "plan_name": "short description",
            "steps": [
                {{"step": 1, "action": "description", "success_condition": "how to verify"}},
                ...
            ]
        }}
        """
        response = self.client.generate(prompt)
        return Plan.from_json(response)

    def evaluate_progress(self, plan: Plan, current_step: int,
                         perception: str) -> PlanUpdate:
        """Decide if plan needs adjustment based on current state."""
        ...
```

### Body (Qwen3 VL)

```python
# body/perceiver.py

class BodyPerceiver:
    """Visual perception with Qwen3 VL."""

    def __init__(self, ollama_url: str):  # Vision server address
        self.client = OllamaClient(ollama_url, model="qwen3-vl")

    def perceive(self, screenshot: Image) -> Perception:
        """
        Look at the screen and describe what we see.
        """
        prompt = """
        You are the eyes of a Stardew Valley AI player.
        Describe what you see:
        - Current location
        - Time of day (top right)
        - Player position and what they're holding
        - Nearby objects (crops, rocks, trees, NPCs)
        - Any UI elements open (menus, dialogs)
        - Current toolbar items

        Be concise but complete.
        """
        response = self.client.generate(prompt, images=[screenshot])
        return Perception(raw=response, timestamp=time.time())
```

```python
# body/executor.py

class BodyExecutor:
    """Action execution with Qwen3 VL."""

    def __init__(self, ollama_url: str):
        self.client = OllamaClient(ollama_url, model="qwen3-vl")
        self.input = InputSimulator()

    def execute_step(self, step: PlanStep, screenshot: Image) -> StepResult:
        """
        Execute a single step by looking at the screen and
        determining the exact action needed.
        """
        prompt = f"""
        You are controlling a Stardew Valley player.

        TASK: {step.action}

        Look at the screen and output the action needed.
        Output JSON:
        {{
            "action_type": "click|keypress|drag",
            "details": {{...}}  // coords for click, key for keypress
        }}

        If the task is already done, output:
        {{"action_type": "none", "reason": "already complete"}}
        """
        response = self.client.generate(prompt, images=[screenshot])
        action = parse_action(response)

        if action.type != "none":
            self.input.execute(action)

        return StepResult(action=action, success=True)
```

## Dual-Model Communication

```python
# main.py

class StardewAI:
    """Main orchestrator."""

    def __init__(self, config: Config):
        self.brain = BrainPlanner(config.nemotron_url)
        self.body = BodyPerceiver(config.qwen_url)
        self.executor = BodyExecutor(config.qwen_url)
        self.screen = ScreenCapture()

        self.current_plan: Optional[Plan] = None
        self.current_step: int = 0

    async def run(self):
        while True:
            # Eyes: What do we see?
            screenshot = self.screen.capture()
            perception = await self.body.perceive(screenshot)

            # Brain: What should we do?
            if not self.current_plan or self.plan_complete():
                goal = await self.get_next_goal()
                self.current_plan = await self.brain.create_plan(
                    perception.raw, goal
                )
                self.current_step = 0

            # Body: Execute the current step
            step = self.current_plan.steps[self.current_step]
            result = await self.executor.execute_step(step, screenshot)

            # Verify and advance
            if await self.verify_step_complete(step):
                self.current_step += 1

            await asyncio.sleep(0.5)  # Tick rate
```

## Input Methods

### Option A: Pure Vision (Screen + Mouse/Keyboard)

```python
# No SMAPI mod needed
# Qwen3 VL sees screen, outputs click coordinates
# pyautogui executes clicks

class InputSimulator:
    def click(self, x: int, y: int):
        pyautogui.click(x, y)

    def keypress(self, key: str):
        pyautogui.press(key)

    def drag(self, start: tuple, end: tuple):
        pyautogui.drag(end[0]-start[0], end[1]-start[1])
```

### Option B: Hybrid (Vision + SMAPI)

```python
# SMAPI mod provides precise game state
# Qwen3 VL handles visual ambiguity
# SMAPI executes actions reliably

class HybridInterface:
    def __init__(self):
        self.smapi = SmapiClient("http://localhost:8765")
        self.vision = BodyPerceiver(qwen_url)

    async def get_state(self):
        # Get structured data from SMAPI
        state = await self.smapi.get_state()

        # Use vision for things SMAPI can't tell us
        if state.in_menu:
            screenshot = capture_screen()
            menu_context = await self.vision.read_menu(screenshot)
            state.menu_context = menu_context

        return state

    async def execute(self, action):
        # Use SMAPI for precise game actions
        await self.smapi.execute(action)
```

## Prompt Templates

### Brain (Nemotron) System Prompt

```yaml
# config/brain_prompts.yaml

system_prompt: |
  You are the BRAIN of a Stardew Valley AI co-op partner.

  Your role:
  - Receive visual descriptions from your EYES (another AI)
  - Make high-level plans and decisions
  - Break goals into actionable steps
  - Track progress and adapt plans

  You cannot see the game directly. You rely on descriptions.

  Current goals are given by the human player.
  Be helpful, efficient, and communicate your plans.

  Output format: JSON
```

### Body (Qwen3 VL) System Prompt

```yaml
# config/body_prompts.yaml

perceiver_prompt: |
  You are the EYES of a Stardew Valley AI player.
  Your job: describe what you see accurately and concisely.

  Include:
  - Location name
  - Time shown on screen
  - Player position (rough: left/center/right of screen)
  - Current held item
  - Nearby interactable objects
  - Any open menus or dialogs
  - Toolbar contents (left to right)

executor_prompt: |
  You are the BODY of a Stardew Valley AI player.
  Your job: execute specific actions by clicking/typing.

  Given a task, look at the screen and determine:
  1. What needs to be clicked/pressed
  2. The exact screen coordinates or key

  Output JSON actions only.
```

## Dependencies

```
# requirements.txt
httpx>=0.24.0           # HTTP client for Ollama
pillow>=10.0.0          # Image handling
pyautogui>=0.9.54       # Input simulation
mss>=9.0.0              # Fast screen capture
pyyaml>=6.0             # Config files
pydantic>=2.0           # Data models
asyncio                 # Async orchestration
```

## Configuration

```yaml
# config/settings.yaml

servers:
  nemotron:
    url: "http://localhost:11434"
    model: "nemotron-nano"

  qwen_vl:
    url: "http://192.168.x.x:11434"  # Update with actual IP
    model: "qwen3-vl"

timing:
  perception_interval_ms: 1000
  planning_interval_ms: 3000
  action_delay_ms: 200

game:
  window_title: "Stardew Valley"
  resolution: [1920, 1080]

logging:
  level: INFO
  save_screenshots: true
  screenshot_dir: "./logs/screenshots"
```
