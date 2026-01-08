#!/usr/bin/env python3
"""
StardewAI Agent - Co-op Partner for Stardew Valley

Architecture:
- Qwen3 VL (vision server): Eyes - sees the game screen
- Nemotron (local): Brain - plans actions based on what eyes see
- pyautogui: Body - executes mouse/keyboard actions

Run with: python agent.py
"""

import asyncio
import base64
import io
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from mss import mss
from PIL import Image

# Optional: input simulation
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

# Virtual gamepad for controller simulation (preferred for co-op)
try:
    import vgamepad as vg
    HAS_GAMEPAD = True
except ImportError:
    HAS_GAMEPAD = False

HAS_INPUT = HAS_GAMEPAD or HAS_PYAUTOGUI
if not HAS_INPUT:
    print("No input method available - running in observe-only mode")


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    # Servers - both use llama.cpp with OpenAI-compatible API
    brain_url: str = "http://localhost:8034"        # Nemotron (local)
    brain_model: str = "gary-nemotron-v9-Q5_K_M"

    eyes_url: str = "http://100.104.77.44:8061"     # Qwen3 VL (vision server)
    eyes_model: str = "Qwen3VL-8B-Instruct-Q4_K_M"

    # Timing
    perception_interval: float = 2.0  # seconds between screen captures
    planning_interval: float = 5.0    # seconds between replanning
    action_delay: float = 0.3         # seconds between actions

    # Screen capture
    monitor: int = 1
    max_image_size: int = 1280

    # Logging
    log_dir: Path = Path("./logs")
    save_screenshots: bool = True


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Perception:
    """What the AI sees."""
    raw_description: str
    timestamp: float
    location: str = ""
    time_of_day: str = ""
    player_state: str = ""
    nearby_objects: list = field(default_factory=list)
    menu_open: bool = False


@dataclass
class Action:
    """An action to execute."""
    action_type: str  # move, click, key, wait
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class Plan:
    """A plan with steps to execute."""
    goal: str
    steps: list[Action] = field(default_factory=list)
    current_step: int = 0

    @property
    def is_complete(self) -> bool:
        return self.current_step >= len(self.steps)

    @property
    def current_action(self) -> Optional[Action]:
        if self.is_complete:
            return None
        return self.steps[self.current_step]


# =============================================================================
# Eyes (Qwen3 VL) - Vision/Perception
# =============================================================================

class Eyes:
    """Handles screen capture and visual perception via Qwen3 VL (llama.cpp)."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=120.0)
        self.last_perception: Optional[Perception] = None
        self.url = config.eyes_url
        self.model = config.eyes_model

    def capture_screen(self) -> Image.Image:
        """Capture the game screen."""
        with mss() as sct:
            shot = sct.grab(sct.monitors[self.config.monitor])
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # Resize for faster processing
        if max(img.size) > self.config.max_image_size:
            ratio = self.config.max_image_size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        return img

    def image_to_base64(self, img: Image.Image) -> str:
        """Convert image to base64."""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def perceive(self, img: Image.Image) -> Perception:
        """Send image to Qwen3 VL and get perception."""
        img_b64 = self.image_to_base64(img)

        prompt = """You are the eyes of a Stardew Valley AI player. Analyze this game screenshot.

Output a JSON object with these fields:
{
  "location": "name of current location (Farm, Town, Beach, Mine, etc.)",
  "time": "in-game time shown (e.g. '9:30 AM')",
  "player": "what player is doing/holding",
  "nearby": ["list", "of", "nearby", "interactive", "objects"],
  "menu_open": true/false,
  "summary": "one sentence describing the scene"
}

Be accurate and concise. Output ONLY the JSON, no other text."""

        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            "max_tokens": 500,
            "temperature": 0.2,
        }

        try:
            response = self.client.post(
                f"{self.url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            # Try to parse JSON from response
            perception = self._parse_perception(content)
            self.last_perception = perception
            return perception

        except Exception as e:
            logging.error(f"Perception failed: {e}")
            return Perception(
                raw_description=f"ERROR: {e}",
                timestamp=time.time()
            )

    def _parse_perception(self, content: str) -> Perception:
        """Parse Qwen's response into a Perception object."""
        try:
            # Try to extract JSON from response
            # Handle case where model adds text before/after JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)

                return Perception(
                    raw_description=data.get("summary", content),
                    timestamp=time.time(),
                    location=data.get("location", "Unknown"),
                    time_of_day=data.get("time", ""),
                    player_state=data.get("player", ""),
                    nearby_objects=data.get("nearby", []),
                    menu_open=data.get("menu_open", False)
                )
        except json.JSONDecodeError:
            pass

        # Fallback: use raw content
        return Perception(
            raw_description=content,
            timestamp=time.time()
        )


# =============================================================================
# Brain (Nemotron) - Planning/Decision Making
# =============================================================================

class Brain:
    """Handles planning and decision making via Nemotron (llama.cpp)."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=120.0)
        self.current_goal: str = ""
        self.current_plan: Optional[Plan] = None

    def think(self, perception: Perception, user_goal: str = "", input_mode: str = "gamepad") -> Plan:
        """Given perception and goal, create a plan."""

        if user_goal:
            self.current_goal = user_goal

        system_prompt = """You are the brain of a Stardew Valley AI co-op partner.
You control Player 2 using an Xbox controller.
Output ONLY valid JSON, no other text."""

        # Controller-specific action types
        action_help = """
ACTION TYPES (Xbox controller):
- move: Move with left stick. direction: up/down/left/right/up_left/up_right/down_left/down_right, duration: seconds
- interact: Press X button to check/interact with objects in front of you
- use_tool: Press A button to use currently held tool
- cancel: Press B button to cancel/back out of menus
- menu: Press Y button to open inventory/menu
- button: Press specific button. button: a/b/x/y/rb/lb/start
- wait: Wait for seconds. seconds: number
"""

        user_prompt = f"""CURRENT PERCEPTION:
- Location: {perception.location}
- Time: {perception.time_of_day}
- Player state: {perception.player_state}
- Nearby: {', '.join(perception.nearby_objects) if perception.nearby_objects else 'nothing notable'}
- Menu open: {perception.menu_open}
- Scene: {perception.raw_description}

CURRENT GOAL: {self.current_goal or "Explore and help with farming"}

{action_help}

Create a short action plan. Output JSON:
{{
  "goal": "what we're trying to accomplish",
  "reasoning": "brief explanation",
  "steps": [
    {{"action": "description", "type": "move|interact|use_tool|cancel|menu|button|wait", "direction": "if move", "duration": 0.5, "button": "if button type"}}
  ]
}}

RULES:
- Keep plans SHORT (1-3 steps)
- If menu is open, use cancel first (B button)
- To interact with something, move toward it then use interact
- Movement is relative to current position (use left stick directions)
- You cannot click specific screen locations - use movement + interact"""

        # Use OpenAI-compatible API (llama.cpp)
        payload = {
            "model": self.config.brain_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7,
        }

        try:
            response = self.client.post(
                f"{self.config.brain_url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            return self._parse_plan(content)

        except Exception as e:
            logging.error(f"Planning failed: {e}")
            return Plan(goal="Wait and observe", steps=[
                Action(action_type="wait", params={"seconds": 2}, description="Waiting due to error")
            ])

    def _parse_plan(self, content: str) -> Plan:
        """Parse Nemotron's response into a Plan."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])

                steps = []
                for step in data.get("steps", []):
                    action_type = step.get("type", "wait")
                    params = {}

                    # Extract controller-specific params
                    if action_type == "move":
                        params["direction"] = step.get("direction", "down")
                        params["duration"] = step.get("duration", 0.5)
                    elif action_type == "button":
                        params["button"] = step.get("button", "a")
                        params["duration"] = step.get("duration", 0.1)
                    elif action_type == "wait":
                        params["seconds"] = step.get("duration", step.get("seconds", 1))
                    # interact, use_tool, cancel, menu need no extra params

                    steps.append(Action(
                        action_type=action_type,
                        params=params,
                        description=step.get("action", "")
                    ))

                return Plan(
                    goal=data.get("goal", "Unknown"),
                    steps=steps if steps else [Action("wait", {"seconds": 1}, "No actions planned")]
                )
        except json.JSONDecodeError:
            pass

        return Plan(goal="Observe", steps=[
            Action("wait", {"seconds": 2}, "Could not parse plan")
        ])


# =============================================================================
# Body (pyautogui) - Action Execution
# =============================================================================

class Body:
    """Handles action execution via mouse/keyboard simulation."""

    def __init__(self, config: Config):
        self.config = config
        self.enabled = HAS_INPUT

    def execute(self, action: Action) -> bool:
        """Execute an action. Returns True if successful."""
        if not self.enabled:
            logging.info(f"[DRY RUN] Would execute: {action.action_type} - {action.description}")
            return True

        try:
            if action.action_type == "wait":
                seconds = action.params.get("seconds", 1)
                time.sleep(seconds)
                return True

            elif action.action_type == "key":
                key = action.params.get("key", "")
                if key:
                    pyautogui.press(key)
                    return True

            elif action.action_type == "click":
                x = action.params.get("x")
                y = action.params.get("y")
                if x is not None and y is not None:
                    pyautogui.click(x, y)
                    return True

            elif action.action_type == "move":
                # Movement via WASD - this will need game-specific logic
                direction = action.params.get("direction", "")
                duration = action.params.get("duration", 0.5)
                key_map = {"up": "w", "down": "s", "left": "a", "right": "d"}
                if direction in key_map:
                    pyautogui.keyDown(key_map[direction])
                    time.sleep(duration)
                    pyautogui.keyUp(key_map[direction])
                    return True

            logging.warning(f"Unknown action type: {action.action_type}")
            return False

        except Exception as e:
            logging.error(f"Action execution failed: {e}")
            return False


# =============================================================================
# GamepadBody - Controller-based input (preferred for co-op)
# =============================================================================

class GamepadBody:
    """Handles action execution via virtual Xbox controller (vgamepad).

    Stardew Valley controller mapping:
    - Left stick: Movement
    - A: Use tool / Confirm
    - B: Cancel / Back
    - X: Check / Interact
    - Y: Inventory / Menu
    - RB/LB: Cycle tools
    - Start: Pause menu
    """

    # Button mapping for vgamepad
    BUTTONS = {
        'a': vg.XUSB_BUTTON.XUSB_GAMEPAD_A if HAS_GAMEPAD else None,
        'b': vg.XUSB_BUTTON.XUSB_GAMEPAD_B if HAS_GAMEPAD else None,
        'x': vg.XUSB_BUTTON.XUSB_GAMEPAD_X if HAS_GAMEPAD else None,
        'y': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y if HAS_GAMEPAD else None,
        'rb': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER if HAS_GAMEPAD else None,
        'lb': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER if HAS_GAMEPAD else None,
        'start': vg.XUSB_BUTTON.XUSB_GAMEPAD_START if HAS_GAMEPAD else None,
        'back': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK if HAS_GAMEPAD else None,
        'dpad_up': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP if HAS_GAMEPAD else None,
        'dpad_down': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN if HAS_GAMEPAD else None,
        'dpad_left': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT if HAS_GAMEPAD else None,
        'dpad_right': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT if HAS_GAMEPAD else None,
    }

    def __init__(self, config: Config):
        self.config = config
        self.enabled = HAS_GAMEPAD
        self.gamepad = None
        if self.enabled:
            try:
                self.gamepad = vg.VX360Gamepad()
                self.gamepad.reset()
                logging.info("Virtual Xbox 360 controller initialized")
            except Exception as e:
                logging.error(f"Failed to initialize gamepad: {e}")
                self.enabled = False

    def execute(self, action: Action) -> bool:
        """Execute an action via gamepad. Returns True if successful."""
        if not self.enabled:
            logging.info(f"[DRY RUN] Would execute: {action.action_type} - {action.description}")
            return True

        try:
            if action.action_type == "wait":
                seconds = action.params.get("seconds", 1)
                time.sleep(seconds)
                return True

            elif action.action_type == "button":
                # Press a button (a, b, x, y, rb, lb, start, back)
                button_name = action.params.get("button", "a").lower()
                duration = action.params.get("duration", 0.1)

                if button_name in self.BUTTONS and self.BUTTONS[button_name]:
                    self.gamepad.press_button(button=self.BUTTONS[button_name])
                    self.gamepad.update()
                    time.sleep(duration)
                    self.gamepad.release_button(button=self.BUTTONS[button_name])
                    self.gamepad.update()
                    logging.info(f"Pressed button: {button_name}")
                    return True
                else:
                    logging.warning(f"Unknown button: {button_name}")
                    return False

            elif action.action_type == "move":
                # Move using left stick
                direction = action.params.get("direction", "").lower()
                duration = action.params.get("duration", 0.5)

                # Map direction to stick values (-1.0 to 1.0)
                stick_map = {
                    "up": (0, 1),
                    "down": (0, -1),
                    "left": (-1, 0),
                    "right": (1, 0),
                    "up_left": (-0.7, 0.7),
                    "up_right": (0.7, 0.7),
                    "down_left": (-0.7, -0.7),
                    "down_right": (0.7, -0.7),
                }

                if direction in stick_map:
                    x, y = stick_map[direction]
                    # Convert to int16 range (-32768 to 32767)
                    x_val = int(x * 32767)
                    y_val = int(y * 32767)

                    self.gamepad.left_joystick(x_value=x_val, y_value=y_val)
                    self.gamepad.update()
                    time.sleep(duration)
                    self.gamepad.left_joystick(x_value=0, y_value=0)
                    self.gamepad.update()
                    logging.info(f"Moved {direction} for {duration}s")
                    return True
                else:
                    logging.warning(f"Unknown direction: {direction}")
                    return False

            elif action.action_type == "interact":
                # X button for check/interact in Stardew
                self.gamepad.press_button(button=self.BUTTONS['x'])
                self.gamepad.update()
                time.sleep(0.1)
                self.gamepad.release_button(button=self.BUTTONS['x'])
                self.gamepad.update()
                logging.info("Interacted (X button)")
                return True

            elif action.action_type == "use_tool":
                # A button for use tool
                self.gamepad.press_button(button=self.BUTTONS['a'])
                self.gamepad.update()
                time.sleep(0.1)
                self.gamepad.release_button(button=self.BUTTONS['a'])
                self.gamepad.update()
                logging.info("Used tool (A button)")
                return True

            elif action.action_type == "cancel":
                # B button for cancel/back
                self.gamepad.press_button(button=self.BUTTONS['b'])
                self.gamepad.update()
                time.sleep(0.1)
                self.gamepad.release_button(button=self.BUTTONS['b'])
                self.gamepad.update()
                logging.info("Cancelled (B button)")
                return True

            elif action.action_type == "menu":
                # Y button for inventory/menu
                self.gamepad.press_button(button=self.BUTTONS['y'])
                self.gamepad.update()
                time.sleep(0.1)
                self.gamepad.release_button(button=self.BUTTONS['y'])
                self.gamepad.update()
                logging.info("Opened menu (Y button)")
                return True

            logging.warning(f"Unknown action type: {action.action_type}")
            return False

        except Exception as e:
            logging.error(f"Gamepad action failed: {e}")
            return False

    def reset(self):
        """Reset all gamepad inputs to neutral."""
        if self.gamepad:
            self.gamepad.reset()
            self.gamepad.update()


# =============================================================================
# Main Agent Loop
# =============================================================================

class StardewAgent:
    """Main agent orchestrating eyes, brain, and body."""

    def __init__(self, config: Config = None, use_gamepad: bool = True):
        self.config = config or Config()
        self.eyes = Eyes(self.config)
        self.brain = Brain(self.config)

        # Prefer gamepad for co-op (Player 2 uses controller)
        if use_gamepad and HAS_GAMEPAD:
            self.body = GamepadBody(self.config)
            self.input_mode = "gamepad"
        else:
            self.body = Body(self.config)
            self.input_mode = "keyboard"

        self.running = False
        self.current_plan: Optional[Plan] = None
        self.last_perception_time = 0
        self.last_plan_time = 0

        # Setup logging
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.config.log_dir / "agent.log")
            ]
        )

    async def run(self, goal: str = ""):
        """Main agent loop."""
        self.running = True
        self.brain.current_goal = goal

        logging.info("=" * 60)
        logging.info("StardewAI Agent Starting")
        logging.info(f"Goal: {goal or 'General assistance'}")
        logging.info(f"Input mode: {self.input_mode.upper()}")
        logging.info(f"Input enabled: {'YES' if self.body.enabled else 'NO (observe only)'}")
        logging.info("=" * 60)

        try:
            while self.running:
                await self._tick()
                await asyncio.sleep(0.1)  # Small delay between ticks

        except KeyboardInterrupt:
            logging.info("Agent stopped by user")
        finally:
            self.running = False

    async def _tick(self):
        """Single tick of the agent loop."""
        now = time.time()

        # Perception: capture and analyze screen
        if now - self.last_perception_time >= self.config.perception_interval:
            self.last_perception_time = now

            logging.info("👁️  Perceiving...")
            img = self.eyes.capture_screen()

            # Save screenshot if enabled
            if self.config.save_screenshots:
                timestamp = datetime.now().strftime("%H%M%S")
                img.save(self.config.log_dir / f"screen_{timestamp}.png")

            perception = self.eyes.perceive(img)
            logging.info(f"   Location: {perception.location}, Time: {perception.time_of_day}")
            logging.info(f"   {perception.raw_description[:100]}...")

        # Planning: decide what to do
        if now - self.last_plan_time >= self.config.planning_interval:
            self.last_plan_time = now

            if self.eyes.last_perception:
                logging.info("🧠 Planning...")
                self.current_plan = self.brain.think(self.eyes.last_perception, input_mode=self.input_mode)
                logging.info(f"   Goal: {self.current_plan.goal}")
                for i, step in enumerate(self.current_plan.steps):
                    logging.info(f"   Step {i+1}: {step.description}")

        # Execution: perform planned actions
        if self.current_plan and not self.current_plan.is_complete:
            action = self.current_plan.current_action
            if action:
                logging.info(f"🦾 Executing: {action.description}")
                success = self.body.execute(action)
                if success:
                    self.current_plan.current_step += 1
                    await asyncio.sleep(self.config.action_delay)

    def stop(self):
        """Stop the agent."""
        self.running = False


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="StardewAI Agent")
    parser.add_argument("--goal", "-g", type=str, default="",
                        help="Goal for the agent (e.g., 'water the crops')")
    parser.add_argument("--observe", "-o", action="store_true",
                        help="Observe only, don't execute actions")
    parser.add_argument("--keyboard", "-k", action="store_true",
                        help="Use keyboard/mouse input instead of gamepad")
    parser.add_argument("--interval", "-i", type=float, default=2.0,
                        help="Perception interval in seconds")
    args = parser.parse_args()

    config = Config(
        perception_interval=args.interval,
    )

    # Determine input mode
    use_gamepad = not args.keyboard

    if args.observe:
        global HAS_INPUT, HAS_GAMEPAD, HAS_PYAUTOGUI
        HAS_INPUT = False
        HAS_GAMEPAD = False
        HAS_PYAUTOGUI = False

    agent = StardewAgent(config, use_gamepad=use_gamepad)

    input_desc = "Observe only" if args.observe else f"{agent.input_mode.upper()} control"

    print("\n" + "=" * 60)
    print("   🎮 StardewAI - Your AI Co-op Partner")
    print("=" * 60)
    print(f"   Goal: {args.goal or 'Explore and help with farming'}")
    print(f"   Input: {input_desc}")
    if agent.input_mode == "gamepad":
        print("   Using: Virtual Xbox controller (Player 2)")
    print("   Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    asyncio.run(agent.run(goal=args.goal))


if __name__ == "__main__":
    main()
