#!/usr/bin/env python3
"""
StardewAI Unified Agent - Single VLM for Vision + Planning

Architecture:
- Single multimodal model (Qwen3-VL) handles both perception AND planning
- One inference call per tick = lower latency
- Supports co-op (Player 2) and helper (advisory) modes

Run with: python unified_agent.py --mode coop --goal "Help with farming"
"""

import asyncio
import base64
import io
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set

import httpx
import yaml
from mss import mss
from PIL import Image

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

try:
    from ui.client import UIClient
    HAS_UI = True
except ImportError:
    UIClient = None
    HAS_UI = False

try:
    from memory import get_memory, get_context_for_vlm, should_remember, get_lesson_memory
    from memory.game_knowledge import get_npc_info
    from memory.spatial_map import SpatialMap
    from memory.rusty_memory import get_rusty_memory
    from memory.daily_planner import get_daily_planner
    HAS_MEMORY = True
except ImportError:
    get_memory = None
    get_context_for_vlm = None
    should_remember = None
    get_lesson_memory = None
    get_npc_info = None
    SpatialMap = None
    get_rusty_memory = None
    get_daily_planner = None
    HAS_MEMORY = False

try:
    from skills import SkillLoader, SkillContext, SkillExecutor
    HAS_SKILLS = True
except ImportError:
    SkillLoader = None
    SkillContext = None
    SkillExecutor = None
    HAS_SKILLS = False

try:
    from execution import TaskExecutor, SortStrategy
    HAS_TASK_EXECUTOR = True
except ImportError:
    TaskExecutor = None
    SortStrategy = None
    HAS_TASK_EXECUTOR = False

try:
    from commentary import CommentaryGenerator, PiperTTS
    HAS_COMMENTARY = True
except ImportError:
    CommentaryGenerator = None
    PiperTTS = None
    HAS_COMMENTARY = False

try:
    from planning import PlotManager
    HAS_PLANNING = True
except ImportError:
    PlotManager = None
    HAS_PLANNING = False

# =============================================================================
# Optional Input Methods
# =============================================================================

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import vgamepad as vg
    HAS_GAMEPAD = True
except ImportError:
    HAS_GAMEPAD = False
    vg = None

HAS_INPUT = HAS_GAMEPAD or HAS_PYAUTOGUI


# =============================================================================
# Configuration
# =============================================================================

CARDINAL_DIRECTIONS = ["north", "east", "south", "west"]
_DIRECTION_ALIASES = {
    "up": "north",
    "down": "south",
    "left": "west",
    "right": "east",
    "north": "north",
    "south": "south",
    "east": "east",
    "west": "west",
}

# Diagonal directions split into two cardinal moves
# Order: vertical first, then horizontal (so we move away from obstacles first)
DIAGONAL_TO_CARDINAL = {
    "northeast": ("north", "east"),
    "northwest": ("north", "west"),
    "southeast": ("south", "east"),
    "southwest": ("south", "west"),
    "ne": ("north", "east"),
    "nw": ("north", "west"),
    "se": ("south", "east"),
    "sw": ("south", "west"),
}


def normalize_direction(direction: str) -> str:
    if not direction:
        return ""
    return _DIRECTION_ALIASES.get(direction.strip().lower(), direction.strip().lower())


def normalize_directions_map(directions: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in directions.items():
        normalized_key = normalize_direction(key)
        if normalized_key and normalized_key not in normalized:
            normalized[normalized_key] = value
    return normalized

@dataclass
class Config:
    """Configuration loaded from settings.yaml."""

    # Server
    server_url: str = "http://localhost:8765"
    model: str = "Qwen3VL-30B-A3B-Instruct-Q4_K_M"

    # Mode: single (full screen), splitscreen (Player 2 right half), helper (advisory)
    mode: str = "single"
    splitscreen_region: Dict[str, float] = field(default_factory=lambda: {
        "x_start": 0.5, "x_end": 1.0, "y_start": 0.0, "y_end": 1.0
    })

    # Timing
    think_interval: float = 2.0
    action_delay: float = 0.3
    request_timeout: float = 60.0

    # Capture
    monitor: int = 1
    max_image_size: int = 1280
    game_resolution: tuple = (1920, 1080)

    # Input
    input_type: str = "gamepad"

    # Logging
    log_level: str = "INFO"
    save_screenshots: bool = True
    screenshot_dir: Path = Path("./logs/screenshots")
    history_dir: Path = Path("./logs/history")

    # UI
    ui_enabled: bool = False
    ui_url: str = "http://localhost:9001"
    ui_timeout: float = 3.0

    # Model
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt: str = ""

    # Vision-First Mode (Session 35)
    vision_first_enabled: bool = False
    vision_first_system_prompt: str = ""
    vision_first_context_template: str = ""

    @classmethod
    def from_yaml(cls, path: str = "./config/settings.yaml") -> "Config":
        """Load config from YAML file."""
        config = cls()

        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)

            # Server
            if 'server' in data:
                config.server_url = data['server'].get('url', config.server_url)
                config.model = data['server'].get('model', config.model)

            # Mode
            if 'mode' in data:
                config.mode = data['mode'].get('type', config.mode)
                if 'splitscreen_region' in data['mode']:
                    config.splitscreen_region = data['mode']['splitscreen_region']

            # Timing
            if 'timing' in data:
                config.think_interval = data['timing'].get('think_interval', config.think_interval)
                config.action_delay = data['timing'].get('action_delay', config.action_delay)
                config.request_timeout = data['timing'].get('request_timeout', config.request_timeout)

            # Capture
            if 'capture' in data:
                config.monitor = data['capture'].get('monitor', config.monitor)
                config.max_image_size = data['capture'].get('max_size', config.max_image_size)
                res = data['capture'].get('game_resolution', list(config.game_resolution))
                config.game_resolution = tuple(res)

            # Input
            if 'input' in data:
                config.input_type = data['input'].get('type', config.input_type)

            # Logging
            if 'logging' in data:
                config.log_level = data['logging'].get('level', config.log_level)
                config.save_screenshots = data['logging'].get('save_screenshots', config.save_screenshots)
                config.screenshot_dir = Path(data['logging'].get('screenshot_dir', str(config.screenshot_dir)))
                config.history_dir = Path(data['logging'].get('history_dir', str(config.history_dir)))

            # UI
            if 'ui' in data:
                config.ui_enabled = data['ui'].get('enabled', config.ui_enabled)
                config.ui_url = data['ui'].get('url', config.ui_url)
                config.ui_timeout = data['ui'].get('timeout', config.ui_timeout)

            # Model
            if 'model' in data:
                config.temperature = data['model'].get('temperature', config.temperature)
                config.max_tokens = data['model'].get('max_tokens', config.max_tokens)
                config.system_prompt = data['model'].get('system_prompt', config.system_prompt)

            # Vision-First Mode
            if 'vision_first' in data:
                vf = data['vision_first']
                config.vision_first_enabled = vf.get('enabled', False)
                config.vision_first_system_prompt = vf.get('system_prompt', '')
                config.vision_first_context_template = vf.get('light_context_template', '')

        except FileNotFoundError:
            logging.warning(f"Config file not found: {path}, using defaults")
        except Exception as e:
            logging.error(f"Error loading config: {e}, using defaults")

        return config


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Action:
    """An action to execute."""
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class ThinkResult:
    """Result of a unified think() call - perception + plan combined."""
    # Perception
    location: str = ""
    time_of_day: str = ""
    energy: str = ""          # full/good/half/low/exhausted
    holding: str = ""         # current tool/item
    weather: str = ""         # sunny/rainy/stormy/snowy
    nearby_objects: List[str] = field(default_factory=list)
    menu_open: bool = False

    # Personality & Planning
    mood: str = ""            # agent's current vibe
    reasoning: str = ""
    actions: List[Action] = field(default_factory=list)

    # Vision-First Mode (Session 35)
    observation: str = ""      # VLM's description of what it sees

    # Metadata
    timestamp: float = 0.0
    raw_response: str = ""
    latency_ms: float = 0.0
    parse_success: bool = True
    parse_error: str = ""


# =============================================================================
# Unified VLM - Single model for vision + planning
# =============================================================================

class UnifiedVLM:
    """Single multimodal model that handles both perception AND planning."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=config.request_timeout)
        self.url = config.server_url
        self.model = config.model

    def capture_screen(self, crop_region: Optional[Dict[str, float]] = None) -> Image.Image:
        """Capture screen, optionally cropping to a region (for split-screen)."""
        with mss() as sct:
            shot = sct.grab(sct.monitors[self.config.monitor])
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # Crop for split-screen co-op (e.g., right half for Player 2)
        if crop_region and crop_region.get('enabled', True):
            w, h = img.size
            x1 = int(w * crop_region.get('x_start', 0))
            x2 = int(w * crop_region.get('x_end', 1))
            y1 = int(h * crop_region.get('y_start', 0))
            y2 = int(h * crop_region.get('y_end', 1))
            img = img.crop((x1, y1, x2, y2))

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

    def think(self, img: Image.Image, goal: str = "", spatial_context: str = "", memory_context: str = "", action_context: str = "") -> ThinkResult:
        """
        Unified perception + planning in a single inference call.

        The VLM sees the screenshot, understands the game state,
        and decides what actions to take - all in one pass.

        Args:
            spatial_context: Optional directional info (e.g., "north: clear | south: BLOCKED")
            memory_context: Optional memory context (NPC info, past experiences)
        """
        start_time = time.time()
        img_b64 = self.image_to_base64(img)

        # Build user prompt with all context
        user_prompt = f"CURRENT GOAL: {goal or 'Explore and help with farming'}"
        if action_context:
            user_prompt += f"\n\n{action_context}"  # Action warnings appear first!
        if memory_context:
            user_prompt += f"\n\n{memory_context}"
        if spatial_context:
            user_prompt += f"\n\n{spatial_context}"
        user_prompt += "\n\nAnalyze this Stardew Valley screenshot and plan your next actions."

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.config.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        {"type": "text", "text": user_prompt}
                    ]
                }
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        try:
            response = self.client.post(
                f"{self.url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            latency = (time.time() - start_time) * 1000

            return self._parse_response(content, latency)

        except httpx.ConnectError:
            logging.error(f"Cannot connect to {self.url} - is llama-server running?")
            return ThinkResult(
                reasoning="ERROR: Cannot connect to model server",
                actions=[Action("wait", {"seconds": 2}, "Waiting for server")],
                timestamp=time.time()
            )
        except Exception as e:
            logging.error(f"Think failed: {e}")
            return ThinkResult(
                reasoning=f"ERROR: {e}",
                actions=[Action("wait", {"seconds": 2}, "Error recovery")],
                timestamp=time.time()
            )

    def reason(self, prompt: str) -> str:
        """
        Text-only reasoning (no image) for planning and analysis.

        Used for daily planning, decision making, and reflection.
        """
        start_time = time.time()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are Rusty, an AI farmer in Stardew Valley. Think carefully and respond concisely."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,  # Shorter for reasoning
            "temperature": 0.7,
        }

        try:
            response = self.client.post(
                f"{self.url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            latency = (time.time() - start_time) * 1000
            logging.info(f"🧠 VLM reason completed in {latency:.0f}ms")
            return content
        except Exception as e:
            logging.error(f"VLM reasoning failed: {e}")
            return ""

    def think_vision_first(
        self,
        img: Image.Image,
        goal: str = "",
        light_context: str = "",
        lessons: str = "",
    ) -> ThinkResult:
        """
        Vision-first inference: Image drives decisions, text provides grounding.

        Key differences from regular think():
        - Uses minimal system prompt (vision-focused)
        - Image is primary input, light_context is secondary
        - VLM outputs observation before action
        - Lessons from past failures are included

        Args:
            img: Screenshot of game
            goal: Current agent goal
            light_context: Minimal SMAPI data (position, time, 3x3 tiles)
            lessons: Previous failures/corrections from LessonMemory
        """
        start_time = time.time()
        img_b64 = self.image_to_base64(img)

        # Build minimal user prompt
        user_parts = []
        if goal:
            user_parts.append(f"🎯 Goal: {goal}")
        if light_context:
            user_parts.append(light_context)
        if lessons:
            user_parts.append(f"\n📚 Lessons from past mistakes:\n{lessons}")
        user_parts.append("\nLOOK at the screenshot. Describe what you see, then act.")

        user_prompt = "\n".join(user_parts)

        # Use vision-first system prompt
        system_prompt = self.config.vision_first_system_prompt or self.config.system_prompt

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        # Image FIRST - primary input
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        # Then minimal text context
                        {"type": "text", "text": user_prompt}
                    ]
                }
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        try:
            response = self.client.post(
                f"{self.url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            latency = (time.time() - start_time) * 1000

            return self._parse_vision_first_response(content, latency)

        except httpx.ConnectError:
            logging.error(f"Cannot connect to {self.url} - is llama-server running?")
            return ThinkResult(
                reasoning="ERROR: Cannot connect to model server",
                actions=[Action("wait", {"seconds": 2}, "Waiting for server")],
                timestamp=time.time()
            )
        except Exception as e:
            logging.error(f"Vision-first think failed: {e}")
            return ThinkResult(
                reasoning=f"ERROR: {e}",
                actions=[Action("wait", {"seconds": 2}, "Error recovery")],
                timestamp=time.time()
            )

    def _parse_vision_first_response(self, content: str, latency_ms: float) -> ThinkResult:
        """
        Parse vision-first VLM response.

        Expected format:
        {
          "observation": "I see the farmhouse porch...",
          "reasoning": "To reach my goal, I should...",
          "actions": [{"type": "move", "direction": "south"}]
        }
        """
        result = ThinkResult(
            raw_response=content,
            latency_ms=latency_ms,
            timestamp=time.time()
        )

        data = None

        # Try to extract JSON (reuse existing strategies)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    data = json.loads(self._repair_json(json_str))
                except json.JSONDecodeError as e:
                    logging.warning(f"Vision-first JSON parse failed: {e}")

        if data:
            result.parse_success = True

            # Vision-first specific fields
            result.observation = data.get("observation", "")
            result.reasoning = data.get("reasoning", "")

            # Parse actions (same as regular think)
            actions_data = data.get("actions", [])
            if not isinstance(actions_data, list):
                actions_data = [actions_data]

            for act in actions_data:
                if isinstance(act, dict):
                    action_type = act.get("type", "wait")
                    params = {k: v for k, v in act.items() if k != "type"}
                    result.actions.append(Action(action_type, params))

            if not result.actions:
                result.actions.append(Action("wait", {"seconds": 1}, "No actions parsed"))
        else:
            result.parse_success = False
            result.reasoning = "Failed to parse vision-first response"
            result.actions = [Action("wait", {"seconds": 1}, "Parse error")]

        return result

    def _repair_json(self, text: str) -> str:
        """Attempt to repair common JSON issues from VLM output."""
        # Remove trailing commas before } or ]
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Add missing commas between "value" "key" patterns (newline)
        text = re.sub(r'(")\s*\n\s*(")', r'\1,\n\2', text)

        # Add missing commas between } "key" patterns
        text = re.sub(r'(})\s*\n\s*(")', r'\1,\n\2', text)

        # Add missing commas between ] "key" patterns
        text = re.sub(r'(])\s*\n\s*(")', r'\1,\n\2', text)

        # Add missing commas between value and "key" on same line
        text = re.sub(r'(["\d])\s+("(?:inner_monologue|perception|mood|reasoning|actions|farming_eval)")', r'\1, \2', text)

        # Fix missing comma after true/false/null followed by "key"
        text = re.sub(r'(true|false|null)\s*\n\s*(")', r'\1,\n\2', text)

        # Fix missing comma after number followed by "key"
        text = re.sub(r'(\d)\s*\n\s*(")', r'\1,\n\2', text)

        # Fix missing comma between closing bracket/brace and opening on next line
        text = re.sub(r'([}\]])\s*\n\s*(\{)', r'\1,\n\2', text)

        # Fix unquoted keys (common VLM mistake)
        text = re.sub(r'{\s*(\w+):', r'{"\1":', text)
        text = re.sub(r',\s*(\w+):', r', "\1":', text)

        return text

    def _parse_response(self, content: str, latency_ms: float) -> ThinkResult:
        """Parse the VLM's JSON response with robust extraction."""
        result = ThinkResult(
            raw_response=content,
            latency_ms=latency_ms,
            timestamp=time.time()
        )

        data = None
        parse_error = ""

        # Strategy 1: Try to extract JSON from markdown code block
        json_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_block:
            try:
                data = json.loads(json_block.group(1))
            except json.JSONDecodeError:
                # Try with repair
                try:
                    data = json.loads(self._repair_json(json_block.group(1)))
                except json.JSONDecodeError as e:
                    parse_error = f"JSON parse failed (code block): {e}"

        # Strategy 2: Find balanced braces for first complete JSON object
        if data is None:
            start = content.find("{")
            if start >= 0:
                depth = 0
                end = start
                for i, c in enumerate(content[start:], start):
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > start:
                    json_str = content[start:end]
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Try with repair
                        try:
                            data = json.loads(self._repair_json(json_str))
                        except json.JSONDecodeError as e:
                            parse_error = f"JSON parse failed (balanced braces): {e}"

        # Strategy 3: Fallback - try first { to last }
        if data is None:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try with repair
                    try:
                        data = json.loads(self._repair_json(json_str))
                        logging.info("JSON repaired successfully")
                    except json.JSONDecodeError as e:
                        logging.warning(f"JSON parse failed: {e}")
                        logging.warning(f"Raw VLM response (first 800 chars): {content[:800]}")
                        # Save failed JSON to file for debugging
                        try:
                            with open("/tmp/vlm_failed_json.txt", "w") as f:
                                f.write(content)
                        except:
                            pass
                        parse_error = f"JSON parse failed (fallback): {e}"

        # Extract data if we got valid JSON
        if data:
            result.parse_success = True
            try:
                # Perception
                perception = data.get("perception", {})
                result.location = perception.get("location", "Unknown")
                result.time_of_day = perception.get("time", "")
                result.energy = perception.get("energy", "unknown")
                result.holding = perception.get("holding", "")
                result.weather = perception.get("weather", "")
                result.nearby_objects = perception.get("nearby", [])
                result.menu_open = perception.get("menu_open", False)

                # Inner monologue (generated first in JSON for creativity) or legacy mood
                inner = data.get("inner_monologue", "")
                result.mood = inner or data.get("mood", "")
                if inner:
                    logging.info(f"🧠 Inner monologue: {inner[:60]}...")
                result.reasoning = data.get("reasoning", "")

                # Actions
                for action_data in data.get("actions", []):
                    action_type = action_data.get("type", "wait")
                    params = {}

                    if action_type == "move":
                        params["direction"] = normalize_direction(action_data.get("direction", "south"))
                        params["duration"] = action_data.get("duration", 0.5)
                    elif action_type == "button":
                        params["button"] = action_data.get("button", "a")
                    elif action_type == "wait":
                        params["seconds"] = action_data.get("seconds", 1)
                    elif action_type == "interact":
                        pass  # No extra params needed
                    elif action_type == "harvest":
                        params["direction"] = normalize_direction(action_data.get("direction", ""))  # Optional facing direction
                    elif action_type == "use_tool":
                        pass  # No extra params needed
                    elif action_type == "cancel":
                        pass  # No extra params needed
                    elif action_type == "menu":
                        pass  # No extra params needed
                    elif action_type == "warp":
                        params["location"] = action_data.get("location", "farm")
                    elif action_type == "face":
                        params["direction"] = normalize_direction(action_data.get("direction", "south"))
                    elif action_type == "select_slot":
                        params["slot"] = action_data.get("slot", 0)
                    else:
                        # Skills and unknown actions: capture common params
                        # target_direction is used by clearing/farming skills
                        if "direction" in action_data:
                            params["target_direction"] = normalize_direction(action_data.get("direction", ""))
                        if "target_direction" in action_data:
                            params["target_direction"] = normalize_direction(action_data.get("target_direction", ""))
                        if "slot" in action_data:
                            params["slot"] = action_data.get("slot", 0)
                        if "seed_slot" in action_data:
                            params["seed_slot"] = action_data.get("seed_slot", 5)

                    result.actions.append(Action(
                        action_type=action_type,
                        params=params,
                        description=action_data.get("description", "")
                    ))
            except Exception as e:
                logging.warning(f"Error extracting data from JSON: {e}")
                result.reasoning = f"Data extraction error: {e}"
        else:
            result.reasoning = "Could not parse JSON from response"
            result.parse_success = False
            result.parse_error = parse_error or "Could not parse JSON from response"

        # Ensure at least one action
        if not result.actions:
            result.actions = [Action("wait", {"seconds": 1}, "No actions planned")]

        return result


# =============================================================================
# ModBridgeController - SMAPI mod HTTP API
# =============================================================================

class ModBridgeController:
    """Controller that uses SMAPI mod HTTP API for precise game control."""

    def __init__(self, base_url: str = "http://localhost:8790"):
        self.base_url = base_url
        self.enabled = True
        self._check_connection()

    def _check_connection(self) -> bool:
        """Check if mod is responding."""
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=2)
            if resp.status_code == 200:
                logging.info(f"ModBridge connected at {self.base_url}")
                return True
        except Exception as e:
            logging.warning(f"ModBridge not available: {e}")
            self.enabled = False
        return False

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current game state from mod."""
        try:
            resp = httpx.get(f"{self.base_url}/state", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            logging.error(f"Failed to get state: {e}")
        return None

    def get_surroundings(self) -> Optional[Dict[str, Any]]:
        """Get directional surroundings from mod - what's blocked in each direction."""
        try:
            resp = httpx.get(f"{self.base_url}/surroundings", timeout=2)
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            logging.debug(f"Failed to get surroundings: {e}")
        return None

    def format_surroundings(self) -> str:
        """Format surroundings as text for VLM prompt with facing direction emphasis."""
        data = self.get_surroundings()
        state = self.get_state()
        if not data:
            return ""

        dirs = normalize_directions_map(data.get("directions", {}))

        # Get facing direction from game state
        facing_dir = None
        if state:
            facing_map = {0: "north", 1: "east", 2: "south", 3: "west"}
            facing_dir = facing_map.get(state.get("player", {}).get("facingDirection"))

        # Format all directions
        parts = []
        front_info = ""
        for direction in CARDINAL_DIRECTIONS:
            info = dirs.get(direction, {})
            if info.get("clear"):
                tiles = info.get("tilesUntilBlocked", "?")
                desc = f"{direction}: clear ({tiles} tiles)"
                if direction == facing_dir:
                    front_info = "IN FRONT OF YOU: CLEAR GROUND - you can till here with hoe!"
            else:
                blocker = info.get("blocker", "obstacle")
                tiles = info.get("tilesUntilBlocked", 0)
                # Special case: water is not a blocker, it's a resource!
                if "water" in blocker.lower():
                    desc = f"{direction}: 💧 WATER ({tiles} tile{'s' if tiles != 1 else ''}) - refill here!"
                elif tiles > 1:
                    # Can walk some tiles before hitting blocker
                    desc = f"{direction}: clear {tiles-1} tile{'s' if tiles > 2 else ''}, then {blocker}"
                else:
                    # Immediately blocked
                    desc = f"{direction}: BLOCKED ({blocker})"
                if direction == facing_dir:
                    if "water" in blocker.lower():
                        front_info = f">>> 💧 WATER SOURCE! DO: refill_watering_can direction={facing_dir} <<<"
                    elif blocker in ["Weeds", "Grass"]:
                        front_info = f"IN FRONT OF YOU: {blocker} - use SCYTHE to clear!"
                    elif blocker == "Stone":
                        front_info = f"IN FRONT OF YOU: {blocker} - use PICKAXE to break!"
                    elif blocker in ["Tree", "Stump"]:
                        front_info = f"IN FRONT OF YOU: {blocker} - use AXE to chop!"
                    else:
                        front_info = f"IN FRONT OF YOU: {blocker}"
            parts.append(desc)

        result = "DIRECTIONS: " + " | ".join(parts)

        # Add hint if surrounded by clearable debris
        clearable_debris = []
        for direction in CARDINAL_DIRECTIONS:
            info = dirs.get(direction, {})
            if not info.get("clear"):
                blocker = info.get("blocker", "")
                dist = info.get("tilesUntilBlocked", 0)
                if dist == 0 and blocker in ["Weeds", "Grass", "Stone", "Twig", "Wood"]:
                    tool = "SCYTHE" if blocker in ["Weeds", "Grass"] else "PICKAXE" if blocker == "Stone" else "AXE"
                    clearable_debris.append((direction, blocker, tool))

        if clearable_debris and not front_info:
            # Pick closest clearable debris
            d, b, t = clearable_debris[0]
            front_info = f">>> BLOCKED! Face {d.upper()}, select {t}, use_tool to clear {b}! <<<"

        # Add current tile state from game data (more reliable than vision)
        current_tile = data.get("currentTile", {})
        current_tool = state.get("player", {}).get("currentTool", "Unknown") if state else "Unknown"
        current_slot = state.get("player", {}).get("currentToolIndex", -1) if state else -1

        # EXPLICIT TOOL CONTEXT - VLM must know what's equipped!
        tool_info = f"🔧 EQUIPPED: {current_tool} (slot {current_slot})"

        # Tool slot mapping for switch instructions
        tool_slots = {"Axe": 0, "Hoe": 1, "Watering Can": 2, "Pickaxe": 3, "Scythe": 4}

        if current_tile:
            tile_state = current_tile.get("state", "unknown")
            tile_obj = current_tile.get("object")
            can_till = current_tile.get("canTill", False)
            can_plant = current_tile.get("canPlant", False)

            # Check if standing on a harvestable crop
            player_x = state.get("player", {}).get("tileX", 0) if state else 0
            player_y = state.get("player", {}).get("tileY", 0) if state else 0
            crops = state.get("location", {}).get("crops", []) if state else []
            crop_here = next((c for c in crops if c.get("x") == player_x and c.get("y") == player_y), None)

            # PRIORITY CHECK: Empty watering can + unwatered crops = REFILL FIRST
            # This prevents conflicting guidance (crop directions vs refill message)
            water_left = state.get("player", {}).get("wateringCanWater", 0) if state else 0
            unwatered_crops = [c for c in crops if not c.get("isWatered", False)]

            if water_left <= 0 and unwatered_crops:
                # CAN IS EMPTY AND CROPS NEED WATER - REFILL IS THE ONLY PRIORITY
                # Check if we're already AT the water (water is immediate blocker, 0-1 tiles)
                directions = normalize_directions_map(data.get("directions", {}))
                water_adjacent = None
                for dir_name, dir_info in directions.items():
                    blocker = dir_info.get("blocker", "")
                    tiles_until = dir_info.get("tilesUntilBlocked", 99)
                    if blocker and "water" in blocker.lower() and tiles_until <= 1:
                        water_adjacent = dir_name
                        break

                if water_adjacent:
                    # AT THE WATER - use refill_watering_can skill
                    if "Watering" in current_tool:
                        front_info = f">>> ⚠️ AT WATER! DO: refill_watering_can direction={water_adjacent} <<<"
                    else:
                        front_info = f">>> ⚠️ AT WATER! select_slot 2, then refill_watering_can direction={water_adjacent} <<<"
                else:
                    nearest_water = data.get("nearestWater")
                    if nearest_water:
                        water_dir = normalize_direction(nearest_water.get("direction", "nearby"))
                        water_dist = nearest_water.get("distance", "?")
                        front_info = f">>> ⚠️ WATERING CAN EMPTY! Move {water_dist} tiles {water_dir} to water, then refill_watering_can <<<"
                    else:
                        front_info = ">>> ⚠️ WATERING CAN EMPTY! Find water (pond/river), then refill_watering_can <<<"
            elif crop_here:
                # Standing ON a crop tile - handle all crop states
                crop_name = crop_here.get("cropName", "crop")
                if crop_here.get("isReadyForHarvest"):
                    front_info = f">>> 🌾 HARVEST TIME! {crop_name} is READY! DO: harvest (facing crop) <<<"
                elif crop_here.get("isWatered"):
                    # Crop is growing and watered - find something else to do
                    days_left = crop_here.get("daysUntilHarvest", "?")
                    # Check for other unwatered crops
                    other_unwatered = [c for c in crops if not c.get("isWatered", False)
                                      and (c.get("x") != player_x or c.get("y") != player_y)]
                    # Check for harvestable crops elsewhere
                    other_harvestable = [c for c in crops if c.get("isReadyForHarvest", False)
                                        and (c.get("x") != player_x or c.get("y") != player_y)]
                    if other_unwatered:
                        nearest = min(other_unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        adj_hint = self._calc_adjacent_hint(nearest["x"] - player_x, nearest["y"] - player_y, action="water")
                        front_info = f">>> 🌱 {crop_name} growing ({days_left} days). Move to water other crops! {adj_hint} <<<"
                    elif other_harvestable:
                        nearest = min(other_harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        adj_hint = self._calc_adjacent_hint(nearest["x"] - player_x, nearest["y"] - player_y, action="harvest")
                        front_info = f">>> 🌱 {crop_name} growing ({days_left} days). {adj_hint} <<<"
                    else:
                        # All crops watered, none ready - suggest useful activities
                        front_info = f">>> 🌱 {crop_name} growing ({days_left} days). Crops watered! Ship items or explore. <<<"
                else:
                    # Crop needs watering - but we're ON it, need to step off and face it
                    front_info = f">>> 🌱 {crop_name} needs water! Step off crop, face it, then water_crop. <<<"
            elif tile_state == "tilled":
                # Check if player has seeds before showing plant message
                inventory = state.get("inventory", []) if state else []
                # Find first seed slot (not just check existence)
                seed_slot = None
                seed_name = None
                for item in inventory:
                    item_name = item.get("name", "")
                    if "Seed" in item_name or item_name == "Mixed Seeds":
                        seed_slot = item.get("slot")
                        seed_name = item_name
                        break

                if seed_slot is not None:
                    if "Seed" in current_tool or current_tool == "Mixed Seeds":
                        front_info = f">>> 🌱🌱🌱 PLANT NOW! TILE IS TILLED! You have {current_tool}! DO: use_tool 🌱🌱🌱 <<<"
                    else:
                        front_info = f">>> 🌱🌱🌱 PLANT NOW! TILE IS TILLED! DO: select_slot {seed_slot} ({seed_name}), THEN use_tool! 🌱🌱🌱 <<<"
                else:
                    # No seeds - check for other priorities (shipping, clearing)
                    if unwatered_crops:
                        front_info = ">>> TILE: TILLED (empty, no seeds) - Move to find PLANTED crops to water! <<<"
                    else:
                        # All watered, no seeds - use done farming hint (suggests shipping if items)
                        front_info = self._get_done_farming_hint(state, data)
            elif tile_state == "planted":
                # CROP PROTECTION: Warn if holding wrong tool
                dangerous_tools = ["Scythe", "Hoe", "Pickaxe", "Axe"]
                if any(tool.lower() in current_tool.lower() for tool in dangerous_tools):
                    front_info = f">>> ⚠️ CROP HERE! DO NOT use {current_tool}! Select WATERING CAN (slot 2) first! <<<"
                else:
                    # Check watering can water level
                    water_left = state.get("player", {}).get("wateringCanWater", 0) if state else 0
                    water_max = state.get("player", {}).get("wateringCanMax", 40) if state else 40

                    if water_left <= 0:
                        # Get nearest water location
                        nearest_water = data.get("nearestWater")
                        if nearest_water:
                            water_dir = normalize_direction(nearest_water.get("direction", "nearby"))
                            water_dist = nearest_water.get("distance", "?")
                            front_info = f">>> WATERING CAN EMPTY! Move {water_dist} tiles {water_dir} to water, then refill_watering_can <<<"
                        else:
                            front_info = ">>> WATERING CAN EMPTY! Find water (pond/river), then refill_watering_can <<<"
                    elif "Watering" in current_tool:
                        front_info = f">>> TILE: PLANTED - You have {current_tool} ({water_left}/{water_max}), use_tool to WATER! <<<"
                    else:
                        front_info = f">>> TILE: PLANTED - select_slot 2 for WATERING CAN ({water_left}/{water_max}), then use_tool! <<<"
            elif tile_state == "watered":
                # Check if this is wet EMPTY soil (canPlant=true) vs planted+watered (canPlant=false)
                if can_plant:
                    # Wet empty soil from rain - check if player has seeds
                    inventory = state.get("inventory", []) if state else []
                    # Find first seed slot
                    seed_slot = None
                    seed_name = None
                    for item in inventory:
                        item_name = item.get("name", "")
                        if "Seed" in item_name or item_name == "Mixed Seeds":
                            seed_slot = item.get("slot")
                            seed_name = item_name
                            break

                    if seed_slot is not None:
                        if "Seed" in current_tool or current_tool == "Mixed Seeds":
                            front_info = f">>> 🌱🌱🌱 WET TILLED SOIL - NEEDS PLANTING! You have {current_tool}! DO: use_tool NOW! 🌱🌱🌱 <<<"
                        else:
                            front_info = f">>> 🌱🌱🌱 WET TILLED SOIL - NEEDS PLANTING! DO: select_slot {seed_slot} ({seed_name}), THEN use_tool! 🌱🌱🌱 <<<"
                    else:
                        # No seeds - just wet empty soil
                        if unwatered_crops:
                            front_info = ">>> TILE: WET SOIL (no seeds) - Move to find PLANTED crops to water! <<<"
                        else:
                            # Check for harvestable crops before saying "all done"
                            crops = state.get("location", {}).get("crops", []) if state else []
                            harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
                            if harvestable:
                                player_x = state.get("player", {}).get("tileX", 0) if state else 0
                                player_y = state.get("player", {}).get("tileY", 0) if state else 0
                                nearest = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                                dx = nearest["x"] - player_x
                                dy = nearest["y"] - player_y
                                dist = abs(dx) + abs(dy)
                                if dist == 1:
                                    face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
                                    front_info = f">>> 🌾 HARVEST 1 tile {face_dir.upper()}! DO: face {face_dir}, harvest ({len(harvestable)} ready) <<<"
                                else:
                                    dirs = []
                                    if dy < 0:
                                        dirs.append(f"{abs(dy)} NORTH")
                                    elif dy > 0:
                                        dirs.append(f"{abs(dy)} SOUTH")
                                    if dx < 0:
                                        dirs.append(f"{abs(dx)} WEST")
                                    elif dx > 0:
                                        dirs.append(f"{abs(dx)} EAST")
                                    direction_str = " and ".join(dirs) if dirs else "here"
                                    front_info = f">>> 🌾 {len(harvestable)} READY! Move {direction_str}, then harvest <<<"
                            else:
                                front_info = ">>> TILE: WET SOIL (no seeds) - All crops watered! <<<"
                else:
                    # Actually planted and watered crop tile
                    # CROP PROTECTION: Check for dangerous tools FIRST before any other logic
                    dangerous_tools = ["Scythe", "Hoe", "Pickaxe", "Axe"]
                    if tile_obj == "crop" and any(tool.lower() in current_tool.lower() for tool in dangerous_tools):
                        front_info = f">>> ⚠️ WATERED CROP HERE! DO NOT use {current_tool}! This will DESTROY the crop! Move away or select safe tool. <<<"
                    else:
                        # Give specific direction to next unwatered crop
                        crops = state.get("location", {}).get("crops", []) if state else []
                        # Check both isWatered and watered fields (SMAPI inconsistency)
                        unwatered_nearby = [c for c in crops if not c.get("isWatered") and not c.get("watered")]
                        if unwatered_nearby:
                            player_x = state.get("player", {}).get("tileX", 0) if state else 0
                            player_y = state.get("player", {}).get("tileY", 0) if state else 0
                            # Exclude current tile
                            unwatered_others = [c for c in unwatered_nearby if c["x"] != player_x or c["y"] != player_y]
                            if unwatered_others:
                                nearest = min(unwatered_others, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                                dx = nearest["x"] - player_x
                                dy = nearest["y"] - player_y
                                dist = abs(dx) + abs(dy)

                                # If crop is exactly 1 tile away, use FACE + use_tool (don't move onto the crop!)
                                # Use adjacent movement hint (stop 1 tile away from crop)
                                adj_hint = self._calc_adjacent_hint(dx, dy, action="use_tool")
                                front_info = f">>> TILE: WATERED ✓ - NEXT CROP: {adj_hint} ({len(unwatered_others)} more) <<<"
                            else:
                                front_info = self._get_done_farming_hint(state, data)
                        else:
                            front_info = self._get_done_farming_hint(state, data)
            elif tile_state == "debris":
                needed_tool = "Scythe" if tile_obj in ["Weeds", "Grass"] else "Pickaxe" if tile_obj == "Stone" else "Axe"
                needed_slot = tool_slots.get(needed_tool, 4)
                if needed_tool.lower() in current_tool.lower():
                    front_info = f">>> TILE: {tile_obj} - You have {current_tool}, use_tool to clear! <<<"
                else:
                    front_info = f">>> TILE: {tile_obj} - select_slot {needed_slot} for {needed_tool.upper()}, then use_tool! <<<"
            elif tile_state == "clear" and can_till:
                # Check for unwatered crops first - prioritize watering over tilling
                crops = state.get("location", {}).get("crops", []) if state else []
                unwatered = [c for c in crops if not c.get("isWatered", False)]
                if unwatered:
                    # Guide to nearest unwatered crop
                    player_x = state.get("player", {}).get("tileX", 0) if state else 0
                    player_y = state.get("player", {}).get("tileY", 0) if state else 0
                    nearest = min(unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                    dx = nearest["x"] - player_x
                    dy = nearest["y"] - player_y

                    # Use adjacent movement hint (stop 1 tile away from crop)
                    adj_hint = self._calc_adjacent_hint(dx, dy, action="water")
                    front_info = f">>> {len(unwatered)} CROPS NEED WATERING! {adj_hint} <<<"
                else:
                    # Check if we have seeds before suggesting tilling
                    inventory = state.get("inventory", []) if state else []
                    has_seeds = any(item and "seed" in item.get("name", "").lower() for item in inventory)
                    if has_seeds:
                        if "Hoe" in current_tool:
                            front_info = f">>> TILE: CLEAR DIRT - You have {current_tool}, use_tool to TILL! <<<"
                        else:
                            front_info = ">>> TILE: CLEAR DIRT - select_slot 1 for HOE, then use_tool to TILL! <<<"
                    else:
                        # No seeds - use done farming hint (will suggest shipping/clearing)
                        front_info = self._get_done_farming_hint(state, data)
            elif tile_state == "clear" or tile_state == "blocked":
                # Check if there are crops nearby that need watering
                crops = state.get("location", {}).get("crops", []) if state else []
                player_x = state.get("player", {}).get("tileX", 0) if state else 0
                player_y = state.get("player", {}).get("tileY", 0) if state else 0

                # Find nearest unwatered crop
                unwatered = [c for c in crops if not c.get("isWatered", False)]
                if unwatered:
                    # Calculate distance and direction to nearest unwatered crop
                    nearest = min(unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                    dx = nearest["x"] - player_x
                    dy = nearest["y"] - player_y

                    # Use adjacent movement hint (stop 1 tile away from crop)
                    adj_hint = self._calc_adjacent_hint(dx, dy, action="water")
                    front_info = f">>> TILE: NOT FARMABLE - {len(unwatered)} CROPS! {adj_hint} <<<"
                else:
                    # Check for harvestable crops first
                    harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
                    if harvestable:
                        nearest_h = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        dx = nearest_h["x"] - player_x
                        dy = nearest_h["y"] - player_y
                        dist = abs(dx) + abs(dy)

                        # Use adjacent movement hint (stop 1 tile away from crop)
                        adj_hint = self._calc_adjacent_hint(dx, dy, action="harvest")
                        front_info = f">>> 🌾 {len(harvestable)} READY! {adj_hint} <<<"
                    else:
                        # All crops watered, none harvestable - check for sellables, debris, bed
                        front_info = self._get_done_farming_hint(state, data)

        # Add explicit location verification at the very top to prevent hallucination
        location_name = state.get("location", {}).get("name", "Unknown") if state else "Unknown"
        player_x = state.get("player", {}).get("tileX", 0) if state else 0
        player_y = state.get("player", {}).get("tileY", 0) if state else 0
        location_header = f"📍 LOCATION: {location_name} at tile ({player_x}, {player_y})"

        # Add shipping bin info when on Farm
        shipping_info = ""
        if location_name == "Farm" and state:
            shipping_bin = state.get("location", {}).get("shippingBin")
            if shipping_bin:
                bin_x = shipping_bin.get("x", 71)
                bin_y = shipping_bin.get("y", 14)
                dx = bin_x - player_x
                dy = bin_y - player_y
                distance = abs(dx) + abs(dy)
                bin_dirs = []
                if dy < 0:
                    bin_dirs.append(f"{abs(dy)} NORTH")
                elif dy > 0:
                    bin_dirs.append(f"{abs(dy)} SOUTH")
                if dx < 0:
                    bin_dirs.append(f"{abs(dx)} WEST")
                elif dx > 0:
                    bin_dirs.append(f"{abs(dx)} EAST")
                bin_dir_str = " and ".join(bin_dirs) if bin_dirs else "here"
                shipping_info = f"📦 SHIPPING BIN: {distance} tiles away ({bin_dir_str})"

        landmark_hint = ""
        if state:
            landmarks = state.get("landmarks") or {}
            if isinstance(landmarks, dict) and landmarks:
                nearest_name = None
                nearest_info = None
                nearest_distance = None
                for name, info in landmarks.items():
                    if not isinstance(info, dict):
                        continue
                    distance = info.get("distance")
                    if distance is None:
                        continue
                    if nearest_distance is None or distance < nearest_distance:
                        nearest_distance = distance
                        nearest_name = name
                        nearest_info = info
                if nearest_name and nearest_info:
                    direction = (nearest_info.get("direction") or "").lower()
                    label = nearest_name.replace("_", " ")
                    if direction == "here" or nearest_distance == 0:
                        landmark_hint = f"📌 LANDMARK: at {label}"
                    else:
                        landmark_hint = f"📌 LANDMARK: {nearest_distance} tiles {direction} of {label}"

        # Location-specific navigation hints
        location_hint = ""
        if location_name == "FarmHouse":
            # Bed is at tile (10, 9) - for sleeping
            bed_x, bed_y = 10, 9
            dy_to_bed = bed_y - player_y
            dx_to_bed = bed_x - player_x
            bed_distance = abs(dx_to_bed) + abs(dy_to_bed)

            bed_dirs = []
            if dy_to_bed < 0:
                bed_dirs.append(f"{abs(dy_to_bed)} NORTH")
            elif dy_to_bed > 0:
                bed_dirs.append(f"{dy_to_bed} SOUTH")
            if dx_to_bed > 0:
                bed_dirs.append(f"{dx_to_bed} EAST")
            elif dx_to_bed < 0:
                bed_dirs.append(f"{abs(dx_to_bed)} WEST")

            if bed_distance <= 1:
                # Tell agent exactly which direction to face
                if dy_to_bed < 0:
                    face_dir = "NORTH"
                elif dy_to_bed > 0:
                    face_dir = "SOUTH"
                elif dx_to_bed > 0:
                    face_dir = "EAST"
                else:
                    face_dir = "WEST"
                bed_hint = f"🛏️ BED: Adjacent! Face {face_dir} and interact to sleep."
            else:
                bed_hint = f"🛏️ BED: {bed_distance} tiles away ({' and '.join(bed_dirs)}). Walk there, face it, interact to sleep."

            # FarmHouse exit is at south edge - walk SOUTH to exit through door
            # Door mat is around (3, 12) - walk south to trigger exit
            exit_y = 12  # Exit triggers when walking south past y=11
            exit_x = 3
            dy_to_exit = exit_y - player_y
            dx_to_exit = exit_x - player_x
            if abs(dx_to_exit) > 1 or dy_to_exit < 0:
                # Need to get to exit area first
                dirs = []
                if dy_to_exit > 0:
                    dirs.append(f"{dy_to_exit} SOUTH")
                if dx_to_exit > 0:
                    dirs.append(f"{dx_to_exit} EAST")
                elif dx_to_exit < 0:
                    dirs.append(f"{abs(dx_to_exit)} WEST")
                exit_hint = f"🚪 EXIT: Go {' then '.join(dirs)} to reach door, then keep going SOUTH to exit!"
            else:
            # At or near exit - just go south
                exit_hint = "🚪 EXIT: Walk SOUTH to exit the farmhouse!"

            # Combine both hints - bed first since sleeping is common goal
            location_hint = f"{bed_hint}\n{exit_hint}"
        elif location_name == "Farm":
            # Farmhouse entrance is around (64, 15)
            farmhouse_x, farmhouse_y = 64, 15
            dx = farmhouse_x - player_x
            dy = farmhouse_y - player_y
            distance = abs(dx) + abs(dy)
            if distance > 0:
                dirs = []
                if dy < 0:
                    dirs.append(f"{abs(dy)} NORTH")
                elif dy > 0:
                    dirs.append(f"{abs(dy)} SOUTH")
                if dx < 0:
                    dirs.append(f"{abs(dx)} WEST")
                elif dx > 0:
                    dirs.append(f"{abs(dx)} EAST")
                location_hint = f"🏠 FARMHOUSE DOOR: {distance} tiles away ({' and '.join(dirs)})"

        # Assemble result with explicit tool context always visible
        header_parts = [location_header, tool_info]
        if location_hint:
            header_parts.append(location_hint)
        if shipping_info:
            header_parts.append(shipping_info)

        # Add PRIORITY shipping action when sellables in inventory (more prominent than tile hints)
        priority_action = ""
        if location_name == "Farm" and state:
            inventory = state.get("inventory", [])
            sellable_items = ["Parsnip", "Potato", "Cauliflower", "Green Bean", "Kale", "Melon",
                             "Blueberry", "Corn", "Tomato", "Pumpkin", "Cranberry", "Eggplant", "Grape", "Radish"]
            sellables = [item for item in inventory if item and item.get("name") in sellable_items and item.get("stack", 0) > 0]
            if sellables:
                total_to_ship = sum(item.get("stack", 0) for item in sellables)
                # Calculate distance to shipping bin
                shipping_bin = state.get("location", {}).get("shippingBin") or {}
                bin_x = shipping_bin.get("x", 71)
                bin_y = shipping_bin.get("y", 14)
                dx = bin_x - player_x
                dy = bin_y - player_y
                dist = abs(dx) + abs(dy)
                if dist <= 1:
                    priority_action = f"⭐ PRIORITY ACTION: SHIP {total_to_ship} CROPS! At bin! DO: ship_item"
                else:
                    dirs = []
                    if dy < 0:
                        dirs.append(f"{abs(dy)} north")
                    elif dy > 0:
                        dirs.append(f"{abs(dy)} south")
                    if dx < 0:
                        dirs.append(f"{abs(dx)} west")
                    elif dx > 0:
                        dirs.append(f"{abs(dx)} east")
                    priority_action = f"⭐ PRIORITY ACTION: SHIP {total_to_ship} CROPS! Move {', '.join(dirs)} to bin, then ship_item"
        if priority_action:
            header_parts.append(priority_action)

        if landmark_hint:
            header_parts.append(landmark_hint)

        # Bedtime hint based on time and energy
        bedtime_hint = ""
        if state:
            hour = state.get("time", {}).get("hour", 6)
            energy = state.get("player", {}).get("energy", 270)
            max_energy = state.get("player", {}).get("maxEnergy", 270)
            energy_pct = (energy / max_energy * 100) if max_energy > 0 else 100

            if hour >= 24 or hour < 2:  # Midnight to 2 AM - critical
                bedtime_hint = "⚠️ VERY LATE! You'll pass out soon! Consider: go_to_bed"
            elif hour >= 22:  # 10 PM+
                bedtime_hint = "🌙 It's late (10PM+). Consider going to bed soon."
            elif hour >= 20:  # 8 PM+
                bedtime_hint = "🌆 Evening time. Finish up tasks, bed is an option."
            elif energy_pct <= 20:
                bedtime_hint = "😓 Energy very low! Consider resting or going to bed."
            elif energy_pct <= 35:
                bedtime_hint = "😐 Energy getting low. Pace yourself."

        if bedtime_hint:
            header_parts.append(bedtime_hint)

        if front_info:
            header_parts.append(front_info)
        header_parts.append(result)
        return "\n".join(header_parts)

    def _get_done_farming_hint(self, state: dict, surroundings: dict) -> str:
        """Get hint when all crops are watered - check for harvest, then suggest clearing debris or bed."""
        if not state:
            return ">>> ALL CROPS WATERED! ✓ Go to bed or explore. <<<"

        hour = state.get("time", {}).get("hour", 12)
        energy = state.get("player", {}).get("energy", 100)
        energy_pct = (energy / state.get("player", {}).get("maxEnergy", 270) * 100) if state.get("player", {}).get("maxEnergy", 270) > 0 else 100
        player_x = state.get("player", {}).get("tileX", 0)
        player_y = state.get("player", {}).get("tileY", 0)

        # PRIORITY: Check for harvestable crops first!
        crops = state.get("location", {}).get("crops", [])
        harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
        if harvestable:
            nearest = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
            dx = nearest["x"] - player_x
            dy = nearest["y"] - player_y
            dist = abs(dx) + abs(dy)
            if dist == 1:
                face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
                return f">>> 🌾 HARVEST 1 tile {face_dir.upper()}! DO: face {face_dir}, harvest ({len(harvestable)} ready) <<<"
            else:
                dirs = []
                if dy < 0:
                    dirs.append(f"{abs(dy)} NORTH")
                elif dy > 0:
                    dirs.append(f"{abs(dy)} SOUTH")
                if dx < 0:
                    dirs.append(f"{abs(dx)} WEST")
                elif dx > 0:
                    dirs.append(f"{abs(dx)} EAST")
                direction_str = " and ".join(dirs) if dirs else "here"
                return f">>> 🌾 {len(harvestable)} READY TO HARVEST! Move {direction_str}, then harvest <<<"

        # Check for sellable items in inventory (harvested crops)
        inventory = state.get("inventory", [])
        sellable_items = ["Parsnip", "Potato", "Cauliflower", "Green Bean", "Kale", "Melon", "Blueberry",
                         "Corn", "Tomato", "Pumpkin", "Cranberry", "Eggplant", "Grape", "Radish"]
        sellables = [item for item in inventory if item and item.get("name") in sellable_items and item.get("stack", 0) > 0]
        logging.info(f"   📊 _get_done_farming_hint: inventory={len(inventory)}, sellables={len(sellables)}")
        if sellables:
            total_count = sum(item.get("stack", 0) for item in sellables)
            shipping_bin = state.get("location", {}).get("shippingBin") or {}
            bin_x = shipping_bin.get("x", 71)
            bin_y = shipping_bin.get("y", 14)
            dx = bin_x - player_x
            dy = bin_y - player_y
            dist = abs(dx) + abs(dy)
            dirs = []
            if dy < 0:
                dirs.append(f"{abs(dy)} NORTH")
            elif dy > 0:
                dirs.append(f"{abs(dy)} SOUTH")
            if dx < 0:
                dirs.append(f"{abs(dx)} WEST")
            elif dx > 0:
                dirs.append(f"{abs(dx)} EAST")
            bin_dir_str = " and ".join(dirs) if dirs else "here"
            if dist <= 1:
                return f">>> 📦 SHIP {total_count} ITEMS! At shipping bin! DO: ship_item <<<"
            else:
                return f">>> 📦 SHIP {total_count} CROPS! Move {bin_dir_str} to shipping bin, then ship_item <<<"

        # Check if we need seeds and can afford them
        has_seeds = any(item and ("Seed" in item.get("name", "") or item.get("name") == "Mixed Seeds") for item in inventory)
        money = state.get("player", {}).get("money", 0)
        day_of_week = state.get("time", {}).get("dayOfWeek", "")

        # Suggest buying seeds if: no seeds, has money, Pierre's open (9-17, not Wed), not too late
        if not has_seeds and money >= 20 and hour >= 9 and hour < 17 and day_of_week != "Wed":
            return f">>> 🌱 NO SEEDS! Go to Pierre's to buy more! DO: go_to_pierre, then buy_parsnip_seeds (you have {money}g) <<<"

        # Check for nearby debris in surroundings
        nearby_debris = []
        if surroundings:
            for direction, info in normalize_directions_map(surroundings.get("directions", {})).items():
                blocker = info.get("blockerName", "")
                if blocker in ["Stone", "Weeds", "Twig", "Wood", "Log", "Stump", "Boulder"]:
                    dist = info.get("tilesUntilBlocked", 5)
                    nearby_debris.append((direction, blocker, dist))

        # If it's late or low energy, suggest bed
        if hour >= 20 or energy_pct <= 30:
            return ">>> ALL CROPS WATERED! ✓ Use action 'go_to_bed' (auto-warps home + sleeps). <<<"

        # If there's nearby debris and we have energy, suggest clearing
        if nearby_debris and energy_pct > 40:
            closest = min(nearby_debris, key=lambda x: x[2])
            direction, debris_type, dist = closest
            tool = "SCYTHE" if debris_type in ["Weeds", "Grass"] else "PICKAXE" if debris_type in ["Stone", "Boulder"] else "AXE"
            tool_slot = {"SCYTHE": 4, "PICKAXE": 3, "AXE": 0}.get(tool, 4)
            if dist == 1:
                return f">>> ✅ WATERING DONE! NOW CLEAR DEBRIS: {debris_type} 1 tile {direction.upper()}. DO: select_slot {tool_slot}, face {direction}, use_tool <<<"
            else:
                return f">>> ✅ WATERING DONE! NOW CLEAR DEBRIS: {debris_type} {dist} tiles {direction.upper()}. DO: move {direction}, select_slot {tool_slot}, use_tool <<<"

        # Default - find debris on farm
        objects = state.get("location", {}).get("objects", []) if state else []
        debris_types = ["Weeds", "Stone", "Twig", "Wood"]
        debris_nearby = [o for o in objects if o.get("name") in debris_types]
        if debris_nearby:
            # Find closest debris
            closest = min(debris_nearby, key=lambda o: abs(o["x"] - player_x) + abs(o["y"] - player_y))
            dx = closest["x"] - player_x
            dy = closest["y"] - player_y
            dist = abs(dx) + abs(dy)
            debris_name = closest["name"]
            tool = "SCYTHE" if debris_name == "Weeds" else "PICKAXE" if debris_name == "Stone" else "AXE"
            tool_slot = {"SCYTHE": 4, "PICKAXE": 3, "AXE": 0}.get(tool, 4)
            dirs = []
            if dy < 0:
                dirs.append(f"{abs(dy)} NORTH")
            elif dy > 0:
                dirs.append(f"{abs(dy)} SOUTH")
            if dx < 0:
                dirs.append(f"{abs(dx)} WEST")
            elif dx > 0:
                dirs.append(f"{abs(dx)} EAST")
            direction_str = " then ".join(dirs) if dirs else "nearby"
            return f">>> ✅ WATERING DONE! NOW CLEAR DEBRIS: {debris_name} {direction_str}. DO: move there, select_slot {tool_slot}, use_tool <<<"

        return ">>> ✅ ALL FARMING DONE! Use action 'go_to_bed' to end day. <<<"

    def _calc_adjacent_hint(self, dx: int, dy: int, action: str = "water") -> str:
        """
        Calculate movement instructions to stop ADJACENT to a crop (not on it).
        
        In Stardew Valley, you must be 1 tile away from a crop to water/harvest it.
        This method calculates the movement to get adjacent, then which direction to face.
        
        Args:
            dx: Horizontal distance to crop (positive = east, negative = west)
            dy: Vertical distance to crop (positive = south, negative = north)
            action: What to do after reaching position ("water", "harvest", etc.)
            
        Returns:
            Hint string like "Move 2N+1E (stop adjacent), face EAST, then water"
        """
        dist = abs(dx) + abs(dy)
        
        # Standing ON the crop - need to step back first
        if dist == 0:
            return f"STEP BACK! move 1 tile any direction, then face crop, {action}"
        
        # Already adjacent - just face and act (NO MOVEMENT NEEDED!)
        if dist == 1:
            face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
            return f"ADJACENT! DO: face {face_dir}, {action} (NO move needed!)"
        
        # Calculate movement to stop 1 tile away
        # Strategy: reduce the LARGER axis by 1, keep other axis full
        # This ensures we end up adjacent to the crop
        abs_dx, abs_dy = abs(dx), abs(dy)
        
        if abs_dy == 0:
            # Pure horizontal movement
            move_x = abs_dx - 1
            face_dir = "east" if dx > 0 else "west"
            x_dir = "E" if dx > 0 else "W"
            return f"move {move_x}{x_dir}, face {face_dir.upper()}, {action}"
        elif abs_dx == 0:
            # Pure vertical movement  
            move_y = abs_dy - 1
            face_dir = "south" if dy > 0 else "north"
            y_dir = "S" if dy > 0 else "N"
            return f"move {move_y}{y_dir}, face {face_dir.upper()}, {action}"
        else:
            # Diagonal movement - reduce larger axis by 1
            if abs_dy >= abs_dx:
                # Reduce Y, keep X full
                move_y = abs_dy - 1
                move_x = abs_dx
                face_dir = "south" if dy > 0 else "north"
            else:
                # Reduce X, keep Y full
                move_y = abs_dy
                move_x = abs_dx - 1
                face_dir = "east" if dx > 0 else "west"
            
            y_dir = "S" if dy > 0 else "N"
            x_dir = "E" if dx > 0 else "W"
            
            parts = []
            if move_y > 0:
                parts.append(f"{move_y}{y_dir}")
            if move_x > 0:
                parts.append(f"{move_x}{x_dir}")
            
            move_str = "+".join(parts) if parts else "0"
            return f"move {move_str} (stop adjacent), face {face_dir.upper()}, {action}"

    def execute(self, action: Action) -> bool:
        """Execute an action via SMAPI mod API."""
        if not self.enabled:
            logging.info(f"[DRY RUN] {action.action_type}: {action.params}")
            return True

        try:
            action_type = action.action_type.lower()

            if action_type == "wait":
                time.sleep(action.params.get("seconds", 1))
                return True

            elif action_type == "move":
                direction = normalize_direction(action.params.get("direction", ""))
                tiles = action.params.get("tiles", 1)
                # Convert duration-based moves to tile-based
                if "duration" in action.params:
                    tiles = max(1, int(action.params["duration"] * 3))  # ~3 tiles per second

                return self._send_action({
                    "action": "move_direction",
                    "direction": direction,
                    "tiles": tiles
                })

            elif action_type == "interact":
                return self._send_action({"action": "interact_facing"})

            elif action_type == "harvest":
                direction = normalize_direction(action.params.get("direction", ""))
                return self._send_action({
                    "action": "harvest",
                    "direction": direction
                })

            elif action_type == "use_tool":
                direction = normalize_direction(action.params.get("direction", ""))
                return self._send_action({
                    "action": "use_tool",
                    "direction": direction
                })

            elif action_type == "face":
                direction = normalize_direction(action.params.get("direction", "south"))
                return self._send_action({
                    "action": "face",
                    "direction": direction
                })

            elif action_type == "warp":
                location = action.params.get("location", "").lower()
                if location == "farm" or location == "outside":
                    return self._send_action({"action": "warp_to_farm"})
                elif location == "house" or location == "farmhouse":
                    return self._send_action({"action": "warp_to_house"})
                elif location:
                    return self._send_action({
                        "action": "warp_location",
                        "location": location
                    })
                else:
                    # Default: warp to farm if no location specified
                    return self._send_action({"action": "warp_to_farm"})

            elif action_type == "equip":
                tool = action.params.get("tool", "")
                return self._send_action({
                    "action": "equip_tool",
                    "tool": tool
                })

            elif action_type == "select_slot":
                slot = action.params.get("slot", 0)
                return self._send_action({
                    "action": "select_slot",
                    "slot": slot
                })

            elif action_type == "menu":
                return self._send_action({"action": "toggle_menu"})

            elif action_type == "cancel":
                return self._send_action({"action": "cancel"})

            elif action_type == "dismiss_menu":
                return self._send_action({"action": "dismiss_menu"})

            elif action_type == "sleep" or action_type == "go_to_bed":
                return self._send_action({"action": "go_to_bed"})

            elif action_type in ("toolbar_next", "toolbar_right"):
                return self._send_action({"action": "toolbar_next"})

            elif action_type in ("toolbar_prev", "toolbar_left"):
                return self._send_action({"action": "toolbar_prev"})

            elif action_type == "ship":
                slot = action.params.get("slot", -1)
                return self._send_action({
                    "action": "ship",
                    "slot": slot
                })

            elif action_type == "buy":
                item = action.params.get("item", "")
                quantity = action.params.get("quantity", 1)
                return self._send_action({
                    "action": "buy",
                    "item": item,
                    "quantity": quantity
                })

            # Fallback for unknown actions
            logging.warning(f"Unknown action for ModBridge: {action_type}")
            return False

        except Exception as e:
            logging.error(f"ModBridge action failed: {e}")
            return False

    def _send_action(self, payload: Dict[str, Any]) -> bool:
        """Send action to mod API."""
        try:
            resp = httpx.post(
                f"{self.base_url}/action",
                json=payload,
                timeout=5
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("success"):
                    logging.debug(f"Action OK: {result.get('data', {}).get('message', '')}")
                    return True
                else:
                    logging.warning(f"Action failed: {result.get('error', 'Unknown error')}")
            return False
        except Exception as e:
            logging.error(f"Failed to send action: {e}")
            return False

    def reset(self):
        """No-op for mod bridge."""
        pass


# =============================================================================
# GamepadController - Xbox controller input (legacy)
# =============================================================================

class GamepadController:
    """Virtual Xbox 360 controller for co-op play."""

    BUTTONS = {}
    if HAS_GAMEPAD:
        BUTTONS = {
            'a': vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            'b': vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            'x': vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            'y': vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            'rb': vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            'lb': vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            'start': vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            'back': vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        }

    DIRECTIONS = {
        "north": (0, 1),
        "south": (0, -1),
        "west": (-1, 0),
        "east": (1, 0),
        "north_west": (-0.7, 0.7),
        "north_east": (0.7, 0.7),
        "south_west": (-0.7, -0.7),
        "south_east": (0.7, -0.7),
        "up": (0, 1),
        "down": (0, -1),
        "left": (-1, 0),
        "right": (1, 0),
    }

    def __init__(self):
        self.enabled = HAS_GAMEPAD
        self.gamepad = None
        if self.enabled:
            try:
                self.gamepad = vg.VX360Gamepad()
                self.gamepad.reset()
                logging.info("Virtual Xbox 360 controller initialized")
            except Exception as e:
                logging.error(f"Failed to init gamepad: {e}")
                self.enabled = False

    def execute(self, action: Action) -> bool:
        """Execute an action via gamepad."""
        if not self.enabled:
            logging.info(f"[DRY RUN] {action.action_type}: {action.params}")
            return True

        try:
            action_type = action.action_type.lower()

            if action_type == "wait":
                time.sleep(action.params.get("seconds", 1))
                return True

            elif action_type == "move":
                direction = normalize_direction(action.params.get("direction", ""))
                duration = action.params.get("duration", 0.5)

                if direction in self.DIRECTIONS:
                    x, y = self.DIRECTIONS[direction]
                    # Use float version for reliable input
                    self.gamepad.left_joystick_float(
                        x_value_float=x,
                        y_value_float=y
                    )
                    self.gamepad.update()
                    time.sleep(duration)
                    self.gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
                    self.gamepad.update()
                    return True

            elif action_type == "interact":
                # A = Check / Do Action / Interact
                return self._press_button('a')

            elif action_type == "use_tool":
                # X = Use Tool / Swing (hold longer for charged tools)
                return self._press_button('x', duration=0.3)

            elif action_type == "cancel":
                # B = Exit menu / Cancel
                return self._press_button('b')

            elif action_type == "menu":
                # B = Open main menu (inventory, map, etc.)
                return self._press_button('b')

            elif action_type == "crafting":
                # Y = Open crafting menu
                return self._press_button('y')

            elif action_type == "journal":
                # Back = Open journal/quest log
                return self._press_button('back')

            elif action_type == "toolbar_left":
                # LB = Shift toolbar left
                return self._press_button('lb')

            elif action_type == "toolbar_right":
                # RB = Shift toolbar right
                return self._press_button('rb')

            elif action_type == "button":
                button = action.params.get("button", "a").lower()
                return self._press_button(button)

            logging.warning(f"Unknown action: {action_type}")
            return False

        except Exception as e:
            logging.error(f"Action failed: {e}")
            return False

    def _press_button(self, button: str, duration: float = 0.1) -> bool:
        """Press and release a button."""
        if button in self.BUTTONS:
            self.gamepad.press_button(button=self.BUTTONS[button])
            self.gamepad.update()
            time.sleep(duration)
            self.gamepad.release_button(button=self.BUTTONS[button])
            self.gamepad.update()
            return True
        return False

    def reset(self):
        """Reset all inputs."""
        if self.gamepad:
            self.gamepad.reset()
            self.gamepad.update()


# =============================================================================
# Main Agent
# =============================================================================

class StardewAgent:
    """Main agent using unified VLM architecture."""

    def __init__(self, config: Config):
        self.config = config
        self.vlm = UnifiedVLM(config)

        # Try ModBridge first (SMAPI mod), fallback to gamepad
        if config.input_type == "mod" or config.input_type == "modbridge":
            self.controller = ModBridgeController()
        elif config.input_type == "gamepad":
            # Try mod first, fallback to gamepad
            mod_controller = ModBridgeController()
            if mod_controller.enabled:
                self.controller = mod_controller
                logging.info("Using ModBridge controller (SMAPI mod)")
            else:
                self.controller = GamepadController()
                logging.info("Using Gamepad controller (vgamepad)")
        else:
            self.controller = GamepadController()

        self.running = False
        self.goal = ""
        self.last_think_time = 0
        self.action_queue: List[Action] = []
        self.recent_actions: List[str] = []  # Track last 10 actions for VLM context
        self.vlm_status = "Idle"
        self.last_state_poll = 0.0
        self.last_state: Optional[Dict[str, Any]] = None
        self.last_position: Optional[Tuple[int, int]] = None
        self.last_position_logged: Optional[Tuple[int, int]] = None
        self.last_tool: Optional[str] = None
        self.current_instruction: Optional[str] = None
        self.navigation_target: Optional[str] = None
        self.last_blocked_direction: Optional[str] = None
        self.movement_attempts = 0
        self.vlm_parse_success = 0
        self.vlm_parse_fail = 0
        self.vlm_errors: List[Dict[str, Any]] = []
        self.session_started_at: Optional[str] = None
        self.think_count = 0
        self.action_count = 0
        self.action_fail_count = 0
        self.action_type_counts: Dict[str, int] = {}
        self.distance_traveled = 0
        self.last_distance_position: Optional[Tuple[int, int]] = None
        self.crops_watered_count = 0
        self.crops_harvested_count = 0
        self.latency_history: List[float] = []
        self.last_user_message_id = 0
        self.awaiting_user_reply = False
        self.spatial_map = None
        self.spatial_location = None
        self.last_surroundings: Optional[Dict[str, Any]] = None
        self.ui = None
        self.ui_enabled = False
        self.commentary_generator = CommentaryGenerator() if HAS_COMMENTARY and CommentaryGenerator else None
        self.commentary_tts = PiperTTS() if HAS_COMMENTARY and PiperTTS else None
        self.last_mood: str = ""

        # Obstacle failure tolerance - give up on unclearable blockers
        # Key: (location, tile_x, tile_y, blocker_type) -> attempt count
        self._clear_attempts: Dict[Tuple[str, int, int, str], int] = {}
        # Blockers we've given up on this session
        self._skip_blockers: Set[Tuple[str, int, int, str]] = set()
        self._max_clear_attempts = 3  # Give up after 3 failed clears

        # State-change detection (phantom failure tracking)
        # Tracks consecutive failures where action reports success but state doesn't change
        self._phantom_failures: Dict[str, int] = {}  # skill_name -> consecutive count
        self._phantom_threshold = 2  # Hard-fail after this many consecutive phantom failures

        # VLM Debug state (for UI panel)
        self.vlm_observation: Optional[str] = None
        self.proposed_action: Optional[Dict[str, Any]] = None
        self.validation_status: Optional[str] = None
        self.validation_reason: Optional[str] = None
        self.executed_action: Optional[Dict[str, Any]] = None
        self.executed_outcome: Optional[str] = None

        # Skill system (contextual guidance + execution)
        self.skill_context = None
        self.skills_dict: Dict[str, Any] = {}
        self.skill_executor = None
        if HAS_SKILLS and SkillLoader and SkillContext and SkillExecutor:
            try:
                skill_dir = Path(__file__).parent / "skills" / "definitions"
                loader = SkillLoader()
                self.skills_dict = loader.load_skills(str(skill_dir))
                self.skill_context = SkillContext(self.skills_dict.values())
                # Create adapter for skill executor (wraps controller.execute)
                self.skill_executor = SkillExecutor(self._create_action_adapter())
                logging.info(f"📚 Loaded {len(self.skills_dict)} skills from {skill_dir} (executor ready)")
            except Exception as e:
                logging.warning(f"Skill system failed to load: {e}")
                self.skill_context = None

        # Farm planning system (systematic plot-based farming)
        self.plot_manager = None
        if HAS_PLANNING and PlotManager:
            try:
                self.plot_manager = PlotManager(persistence_dir="logs/farm_plans")
                if self.plot_manager.is_active():
                    logging.info(f"📋 Farm plan active with {len(self.plot_manager.farm_plan.plots)} plots")
                else:
                    logging.info("📋 Farm planning system ready (no active plan)")
            except Exception as e:
                logging.warning(f"Farm planning failed to load: {e}")
                self.plot_manager = None

        # Lesson memory (vision-first learning from failures)
        self.lesson_memory = None
        if HAS_MEMORY and get_lesson_memory:
            try:
                self.lesson_memory = get_lesson_memory()
                stats = self.lesson_memory.get_stats()
                logging.info(f"📚 Lessons loaded: {stats['total']} total, {stats['completed']} with recovery")
            except Exception as e:
                logging.warning(f"Lesson memory failed to load: {e}")

        # Rusty memory (character persistence across sessions)
        self.rusty_memory = None
        if HAS_MEMORY and get_rusty_memory:
            try:
                self.rusty_memory = get_rusty_memory()
                state = self.rusty_memory.character_state
                logging.info(
                    f"🤖 Rusty memory loaded: {state['mood']} mood, "
                    f"{self.rusty_memory.get_confidence_level()} confidence, "
                    f"{len(self.rusty_memory.relationships)} NPCs known"
                )
            except Exception as e:
                logging.warning(f"Rusty memory failed to load: {e}")

        # Daily planner (Rusty's task planning system)
        self.daily_planner = None
        self._last_planned_day = 0  # Track when we last ran planning
        if HAS_MEMORY and get_daily_planner:
            try:
                self.daily_planner = get_daily_planner()
                logging.info(f"📋 Daily planner loaded: Day {self.daily_planner.current_day}, {len(self.daily_planner.tasks)} tasks")
            except Exception as e:
                logging.warning(f"Daily planner failed to load: {e}")

        # Task Executor (deterministic task execution)
        self.task_executor = None
        self._vlm_commentary_interval = 5  # VLM commentary every N ticks during task execution
        if HAS_TASK_EXECUTOR and TaskExecutor:
            try:
                self.task_executor = TaskExecutor()
                logging.info("🎯 Task Executor initialized (deterministic execution enabled)")
            except Exception as e:
                logging.warning(f"Task Executor failed to load: {e}")

        # Memory trigger tracking
        self.last_location: str = ""
        self.last_nearby_npcs: List[str] = []
        self.visited_locations: set = set()
        self.met_npcs: set = set()
        self._load_memory_state()

        # Setup logging
        config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        config.history_dir.mkdir(parents=True, exist_ok=True)

        # Force reconfigure logging (libraries may have already configured it)
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(config.history_dir.parent / "agent.log")
            ],
            force=True  # Override any existing configuration
        )
        self._init_ui()

    def _load_memory_state(self) -> None:
        """Load visited locations and met NPCs from existing memories."""
        if not HAS_MEMORY or not get_memory:
            return
        try:
            memory = get_memory()
            # Get all memories and extract locations/NPCs
            all_mems = memory.collection.get(include=["metadatas"])
            for meta in (all_mems.get("metadatas") or []):
                if not meta:
                    continue
                mem_type = meta.get("type", "")
                location = meta.get("location", "")
                npc = meta.get("npc", "")

                if mem_type == "location_first" and location:
                    self.visited_locations.add(location)
                if mem_type == "npc_interaction" and npc:
                    self.met_npcs.add(npc)

            if self.visited_locations or self.met_npcs:
                logging.info(f"Loaded memory state: {len(self.visited_locations)} locations, {len(self.met_npcs)} NPCs")
        except Exception as e:
            logging.debug(f"Could not load memory state: {e}")

    def _get_adjacent_debris_hint(self, state: dict) -> str:
        """Check for debris in adjacent tiles and suggest tool to clear it."""
        if not state:
            return ""

        player = state.get("player", {})
        px = player.get("tileX", 0)
        py = player.get("tileY", 0)

        # Get all objects from location
        objects = state.get("location", {}).get("objects", [])

        # Tool mapping: debris type -> (tool name, slot number)
        TOOL_MAP = {
            "Weeds": ("SCYTHE", 4),
            "Grass": ("SCYTHE", 4),
            "Twig": ("AXE", 0),
            "Wood": ("AXE", 0),
            "Stone": ("PICKAXE", 3),
            "Boulder": ("PICKAXE", 3),
        }

        # Check 4 adjacent tiles
        adjacent_debris = []
        for obj in objects:
            ox, oy = obj.get("x", -99), obj.get("y", -99)
            name = obj.get("name", "")

            if name not in TOOL_MAP:
                continue

            # Check if adjacent (Manhattan distance = 1)
            dx, dy = ox - px, oy - py
            if abs(dx) + abs(dy) == 1:
                # Determine direction
                if dy < 0:
                    direction = "north"
                elif dy > 0:
                    direction = "south"
                elif dx < 0:
                    direction = "west"
                else:
                    direction = "east"

                tool_name, tool_slot = TOOL_MAP[name]
                adjacent_debris.append((direction, name, tool_name, tool_slot))

        if not adjacent_debris:
            return ""
        # Build hint for adjacent debris
        hint_lines = ["🧹 DEBRIS BLOCKING YOUR PATH! Clear it:\n"]
        for direction, debris, tool, slot in adjacent_debris:
            hint_lines.append(f"  • {debris} to {direction.upper()}: select_slot {slot} ({tool}), face {direction}, use_tool")
        hint_lines.append("\nClear the debris blocking you, then continue moving!")
        return "\n".join(hint_lines)

    def _get_time_urgency_hint(self, state: dict) -> str:
        """Check time and return urgent bedtime warning if late (hour >= 22).

        Returns empty string if not urgent, otherwise returns a warning that
        should be added to action_context to override other goals.
        """
        if not state:
            return ""

        time_data = state.get("time", {})
        hour = time_data.get("hour", 6)

        # Game time: 6-2 (6am to 2am next day, wraps at 24)
        # hour >= 24 means past midnight (e.g., 25 = 1am)

        if hour >= 26:  # 2am - will pass out imminently
            return (
                "🚨🚨🚨 EMERGENCY! IT'S 2AM - YOU'RE ABOUT TO PASS OUT! 🚨🚨🚨\n"
                "DO THIS NOW: go_to_bed (auto-warps home and sleeps)\n"
                "IGNORE ALL OTHER GOALS - SLEEP IMMEDIATELY!"
            )
        elif hour >= 25:  # 1am - very urgent
            return (
                "⚠️⚠️ CRITICAL: 1AM - Only 1 hour until you PASS OUT! ⚠️⚠️\n"
                "STOP what you're doing and use: go_to_bed\n"
                "You will LOSE MONEY if you pass out!"
            )
        elif hour >= 24:  # Midnight
            return (
                "🌙 MIDNIGHT! 2 hours until you pass out and lose money!\n"
                "STRONGLY RECOMMEND: go_to_bed to end the day safely.\n"
                "Unless you're seconds from finishing a critical task, GO TO BED."
            )
        elif hour >= 22:  # 10pm
            return (
                "🌙 It's past 10PM. Consider wrapping up and using go_to_bed.\n"
                "Tip: Don't start long tasks this late - you may pass out before finishing!"
            )

        return ""

    def _init_ui(self) -> None:
        if not self.config.ui_enabled:
            return
        if not HAS_UI or UIClient is None:
            logging.warning("UI client not available; skipping UI integration")
            return
        try:
            self.ui = UIClient(self.config.ui_url, timeout=self.config.ui_timeout)
            self.ui_enabled = True
            logging.info(f"UI connected: {self.config.ui_url}")
        except Exception as exc:
            logging.warning(f"UI disabled: {exc}")
            self.ui = None
            self.ui_enabled = False

    def _ui_safe(self, func, *args, **kwargs) -> Optional[Dict[str, Any]]:
        if not self.ui_enabled or not self.ui:
            return None
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logging.warning(f"UI request failed, disabling UI: {exc}")
            self.ui_enabled = False
            self.ui = None
            return None

    def _track_vlm_parse(self, result: ThinkResult) -> None:
        if result.parse_success:
            self.vlm_parse_success += 1
            return
        self.vlm_parse_fail += 1
        raw = (result.raw_response or "").strip()
        if len(raw) > 400:
            raw = raw[:400].rstrip() + "..."
        self.vlm_errors.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "error": result.parse_error or "JSON parse failed",
            "raw_response": raw,
        })
        self.vlm_errors = self.vlm_errors[-10:]

    def _extract_navigation_target(self, instruction: Optional[str]) -> Optional[str]:
        if not instruction:
            return None
        cleaned = instruction.replace(">>>", "").replace("<<<", "").strip()
        return cleaned or None

    def _get_recent_user_messages(self) -> str:
        if not self.ui_enabled or not self.ui:
            return ""
        try:
            messages = self.ui.list_messages(limit=50, since_id=self.last_user_message_id or None)
        except Exception as exc:
            logging.debug(f"Failed to read UI messages: {exc}")
            return ""
        if not messages:
            return ""
        ids = [msg.get("id") for msg in messages if msg.get("id")]
        if ids:
            self.last_user_message_id = max(ids)
        user_messages = [msg for msg in messages if msg.get("role") == "user" and msg.get("content")]
        if not user_messages:
            return ""
        self.awaiting_user_reply = True
        recent = user_messages[-3:]
        lines = [f"- {msg['content'].strip()}" for msg in recent if msg.get("content")]
        return "\n".join(lines)

    def _record_session_event(self, event_type: str, data: Dict[str, Any]) -> None:
        if not self.ui_enabled or not self.ui:
            return
        self._ui_safe(self.ui.add_session_event, event_type, data)

    def _ensure_spatial_map(self, location: Optional[str]) -> None:
        if SpatialMap is None or not location:
            return
        if self.spatial_location != location or self.spatial_map is None:
            self.spatial_location = location
            self.spatial_map = SpatialMap(location)

    def _update_spatial_map_from_state(self) -> None:
        if not self.last_state or SpatialMap is None:
            return
        location = (self.last_state.get("location") or {}).get("name")
        self._ensure_spatial_map(location)
        if not self.spatial_map:
            return
        loc = self.last_state.get("location") or {}
        crops = loc.get("crops") or []
        objects = loc.get("objects") or []
        updates: List[Dict[str, Any]] = []

        for crop in crops:
            x = crop.get("x")
            y = crop.get("y")
            if x is None or y is None:
                continue
            state = "planted"
            if crop.get("isReadyForHarvest"):
                state = "ready"
            elif crop.get("isWatered"):
                state = "watered"
            updates.append({
                "x": x,
                "y": y,
                "state": state,
                "crop": crop.get("cropName"),
                "watered": bool(crop.get("isWatered")),
            })

        for obj in objects:
            if obj.get("isPassable", True):
                continue
            updates.append({
                "x": obj.get("x"),
                "y": obj.get("y"),
                "state": "obstacle",
                "obstacle": obj.get("name"),
            })

        if self.last_surroundings:
            tile = (self.last_surroundings.get("currentTile") or {})
            player = self.last_state.get("player") or {}
            x = player.get("tileX")
            y = player.get("tileY")
            if x is not None and y is not None and tile:
                state = tile.get("state")
                if state:
                    updates.append({
                        "x": x,
                        "y": y,
                        "state": state,
                        "obstacle": tile.get("object"),
                    })

        if updates:
            self.spatial_map.update_tiles(updates)

    def _mark_current_tile_worked(self) -> None:
        if not self.spatial_map or not self.last_state:
            return
        player = self.last_state.get("player") or {}
        x = player.get("tileX")
        y = player.get("tileY")
        if x is None or y is None:
            return
        existing = self.spatial_map.get_tile(x, y) or {}
        existing["x"] = x
        existing["y"] = y
        existing["worked_at"] = datetime.now().isoformat(timespec="seconds")
        self.spatial_map.set_tile(x, y, existing)

    def _get_spatial_hint(self) -> str:
        if not self.spatial_map or not self.last_state:
            return ""
        player = self.last_state.get("player") or {}
        px = player.get("tileX")
        py = player.get("tileY")
        if px is None or py is None:
            return ""
        candidates = self.spatial_map.find_tiles(state="tilled", not_planted=True)
        if not candidates:
            return ""
        nearest = min(candidates, key=lambda t: abs(t.x - px) + abs(t.y - py))
        dx = nearest.x - px
        dy = nearest.y - py
        dirs = []
        if dy < 0:
            dirs.append(f"{abs(dy)} NORTH")
        elif dy > 0:
            dirs.append(f"{abs(dy)} SOUTH")
        if dx < 0:
            dirs.append(f"{abs(dx)} WEST")
        elif dx > 0:
            dirs.append(f"{abs(dx)} EAST")
        direction_str = " and ".join(dirs) if dirs else "here"
        return f"SPATIAL MAP: TILLED but UNPLANTED tile at {nearest.x},{nearest.y} ({direction_str})."

    def _get_skill_context(self) -> str:
        """Get available skills for current game state to guide VLM."""
        if not self.skill_context or not self.last_state:
            return ""
        try:
            available = self.skill_context.get_available_skills(self.last_state)
            if not available:
                return ""
            # Group by category for readability
            by_category: Dict[str, List[str]] = {}
            for skill in available:
                cat = skill.category or "other"
                if cat not in by_category:
                    by_category[cat] = []
                # Format: skill_name - description (for VLM to output skill names)
                by_category[cat].append(f"{skill.name} - {skill.description}")
            # Format as compact list - emphasize skill names for VLM selection
            lines = ["AVAILABLE SKILLS (use skill name as action type):"]
            for cat, skills in sorted(by_category.items()):
                lines.append(f"  [{cat.upper()}]")
                for desc in skills[:8]:  # Allow more skills to show
                    lines.append(f"    - {desc}")
                if len(skills) > 8:
                    lines.append(f"    ... and {len(skills) - 8} more")
            return "\n".join(lines)
        except Exception as e:
            logging.debug(f"Skill context failed: {e}")
            return ""

    def _create_action_adapter(self):
        """Create adapter for SkillExecutor that wraps controller.execute()."""
        controller = self.controller

        class ActionAdapter:
            def execute_action(self, action_type: str, params: dict) -> bool:
                """Execute a single action via the controller."""
                action = Action(action_type=action_type, params=params or {})
                return controller.execute(action)

        return ActionAdapter()

    def _capture_state_snapshot(self, skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Capture relevant state before skill execution for verification.

        Returns a snapshot dict containing skill-specific state to compare after execution.
        """
        snapshot = {"skill": skill_name, "timestamp": time.time()}

        if not self.last_state:
            return snapshot

        player = self.last_state.get("player", {})
        player_x = player.get("tileX", 0)
        player_y = player.get("tileY", 0)

        # Get target tile based on direction
        target_dir = params.get("target_direction", "south")
        directions = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
        dx, dy = directions.get(target_dir, (0, 1))
        target_x, target_y = player_x + dx, player_y + dy
        snapshot["target"] = (target_x, target_y)

        location_data = self.last_state.get("location", {})
        crops = location_data.get("crops", [])

        # Skill-specific captures
        if skill_name == "plant_seed":
            snapshot["crop_count"] = len(crops)
            # Check if target tile is tilled
            if self.last_surroundings:
                tiles = self.last_surroundings.get("adjacentTiles", {})
                tile = tiles.get(target_dir, {})
                snapshot["target_tilled"] = tile.get("isTilled", False)
                snapshot["target_has_crop"] = tile.get("hasCrop", False)

        elif skill_name == "water_crop":
            # Find crop at target
            target_crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
            snapshot["target_crop_watered"] = target_crop.get("isWatered", False) if target_crop else None

        elif skill_name == "till_soil":
            if self.last_surroundings:
                tiles = self.last_surroundings.get("adjacentTiles", {})
                tile = tiles.get(target_dir, {})
                snapshot["target_tilled"] = tile.get("isTilled", False)

        elif skill_name == "harvest_crop":
            snapshot["crop_count"] = len(crops)
            # Track inventory count for harvested items
            inventory = player.get("inventory", [])
            snapshot["inventory_count"] = sum(1 for item in inventory if item)

        elif skill_name in ["clear_weeds", "clear_stone", "clear_wood"]:
            if self.last_surroundings:
                tiles = self.last_surroundings.get("adjacentTiles", {})
                tile = tiles.get(target_dir, {})
                snapshot["target_blocker"] = tile.get("blockerType")

        return snapshot

    def _verify_state_change(self, skill_name: str, before: Dict[str, Any], params: Dict[str, Any]) -> bool:
        """Verify that skill execution actually changed the game state.

        Refreshes state and compares with before snapshot.
        Returns True if state changed as expected, False if phantom failure detected.
        """
        # Force state refresh
        self.last_state_poll = 0  # Reset to force immediate refresh
        self._refresh_state_snapshot()

        if not self.last_state:
            return True  # Can't verify without state, assume success

        player = self.last_state.get("player", {})
        location_data = self.last_state.get("location", {})
        crops = location_data.get("crops", [])
        target = before.get("target", (0, 0))
        target_x, target_y = target

        # Skill-specific verification
        if skill_name == "plant_seed":
            new_crop_count = len(crops)
            old_count = before.get("crop_count", 0)
            if new_crop_count <= old_count:
                # Check if target tile wasn't tilled (common failure reason)
                reason = "tile not tilled?" if not before.get("target_tilled") else "unknown"
                logging.warning(f"👻 PHANTOM: plant_seed reported success but crop count unchanged ({old_count} → {new_crop_count}). Reason: {reason}")
                return False
            return True

        elif skill_name == "water_crop":
            target_crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
            if target_crop:
                if not target_crop.get("isWatered", False) and before.get("target_crop_watered") == False:
                    logging.warning(f"👻 PHANTOM: water_crop reported success but crop at ({target_x}, {target_y}) still not watered")
                    return False
            return True

        elif skill_name == "till_soil":
            # Refresh surroundings for tile state
            if hasattr(self.controller, "get_surroundings"):
                self.last_surroundings = self.controller.get_surroundings()
            if self.last_surroundings:
                target_dir = params.get("target_direction", "south")
                tiles = self.last_surroundings.get("adjacentTiles", {})
                tile = tiles.get(target_dir, {})
                if not tile.get("isTilled", False) and not before.get("target_tilled", False):
                    logging.warning(f"👻 PHANTOM: till_soil reported success but tile {target_dir} still not tilled")
                    return False
            return True

        elif skill_name == "harvest_crop":
            new_crop_count = len(crops)
            old_count = before.get("crop_count", 0)
            if new_crop_count >= old_count:
                logging.warning(f"👻 PHANTOM: harvest_crop reported success but crop count unchanged ({old_count} → {new_crop_count})")
                return False
            return True

        elif skill_name in ["clear_weeds", "clear_stone", "clear_wood"]:
            # Refresh surroundings for tile state (critical - must get fresh data!)
            if hasattr(self.controller, "get_surroundings"):
                self.last_surroundings = self.controller.get_surroundings()
            if self.last_surroundings:
                target_dir = params.get("target_direction", "south")
                tiles = self.last_surroundings.get("adjacentTiles", {})
                tile = tiles.get(target_dir, {})
                old_blocker = before.get("target_blocker")
                new_blocker = tile.get("blockerType")
                if old_blocker and new_blocker == old_blocker:
                    logging.warning(f"👻 PHANTOM: {skill_name} reported success but {old_blocker} still at {target_dir}")
                    return False
            return True

        # For skills we don't specifically verify, assume success
        return True

    async def execute_skill(self, skill_name: str, params: Dict[str, Any]) -> bool:
        """Execute a multi-step skill by name.

        Args:
            skill_name: Name of the skill to execute (e.g., 'clear_weeds')
            params: Parameters for the skill (e.g., {'target_direction': 'south'})

        Returns:
            True if skill executed successfully, False otherwise
        """
        # Normalize parameter names: VLM may output 'direction' but skills expect 'target_direction'
        if 'direction' in params and 'target_direction' not in params:
            params['target_direction'] = params.pop('direction')
        
        # If no direction provided but skill needs one, use last blocked direction or facing
        if 'target_direction' not in params:
            # Check if this skill needs a direction (has face action)
            if skill_name in ['clear_weeds', 'clear_stone', 'clear_wood', 'water_crop', 
                              'harvest_crop', 'chop_tree', 'ship_item', 'refill_watering_can']:
                # Use last blocked direction if available, else try to infer from surroundings
                if self.last_blocked_direction:
                    # Extract just the direction from "south (Weeds)" format
                    blocked_dir = self.last_blocked_direction.split()[0]
                    params['target_direction'] = blocked_dir
                    logging.info(f"   ↳ Using last blocked direction: {blocked_dir}")
                elif self.last_state:
                    # Use facing direction from game state
                    facing_map = {0: "north", 1: "east", 2: "south", 3: "west"}
                    facing = self.last_state.get("player", {}).get("facingDirection", 2)
                    params['target_direction'] = facing_map.get(facing, "south")
                    logging.info(f"   ↳ Using facing direction: {params['target_direction']}")
        
        if not self.skill_executor or skill_name not in self.skills_dict:
            logging.warning(f"Skill not found or executor not ready: {skill_name}")
            return False

        # CROP PROTECTION: Block till_soil when standing on a planted crop
        if skill_name == "till_soil" and self.last_surroundings:
            tile_state = self.last_surroundings.get("standingOnTile", {})
            has_crop = tile_state.get("hasCrop", False)
            if has_crop:
                logging.warning(f"🛡️ BLOCKED: till_soil would destroy crop! Skipping.")
                self.recent_actions.append("BLOCKED: till_soil (crop protection)")
                self.recent_actions = self.recent_actions[-10:]
                return False

        # WATER VALIDATION: Auto-target nearest unwatered crop in adjacent tiles
        if skill_name == "water_crop" and self.last_state:
            player = self.last_state.get("player", {})
            player_x = player.get("tileX", 0)
            player_y = player.get("tileY", 0)
            facing = player.get("facing", "south")

            crops = self.last_state.get("location", {}).get("crops", [])

            # Check all 4 adjacent tiles for unwatered crops
            directions = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
            found_dir = None
            found_crop = None

            # First check if VLM specified a direction
            target_dir = params.get("target_direction")
            if target_dir and target_dir in directions:
                dx, dy = directions[target_dir]
                target_x, target_y = player_x + dx, player_y + dy
                crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
                if crop and not crop.get("isWatered", False):
                    found_dir = target_dir
                    found_crop = crop

            # If no valid direction specified, auto-find nearest unwatered crop
            if not found_crop:
                for dir_name, (dx, dy) in directions.items():
                    target_x, target_y = player_x + dx, player_y + dy
                    crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
                    if crop and not crop.get("isWatered", False):
                        found_dir = dir_name
                        found_crop = crop
                        break

            if not found_crop:
                logging.warning(f"🛡️ BLOCKED: water_crop but no unwatered crop adjacent to ({player_x}, {player_y})! Skipping.")
                self.recent_actions.append("BLOCKED: water_crop (no adjacent crop)")
                self.recent_actions = self.recent_actions[-10:]
                return False

            # Set the correct direction for the skill to use
            params['target_direction'] = found_dir
            logging.info(f"🎯 Auto-targeting unwatered crop {found_dir} at ({found_crop['x']}, {found_crop['y']})")

        skill = self.skills_dict[skill_name]
        logging.info(f"🎯 Executing skill: {skill_name} ({skill.description})")

        # STATE-CHANGE DETECTION: Capture before state
        state_before = self._capture_state_snapshot(skill_name, params)

        try:
            result = await self.skill_executor.execute(skill, params, self.last_state or {})
            if result.success:
                # STATE-CHANGE DETECTION: Verify actual state change
                actual_success = self._verify_state_change(skill_name, state_before, params)

                if actual_success:
                    # Reset phantom failure counter on real success
                    self._phantom_failures[skill_name] = 0
                    logging.info(f"✅ Skill {skill_name} completed: {result.actions_taken}")
                    return True
                else:
                    # Phantom failure detected - action reported success but state didn't change
                    self._phantom_failures[skill_name] = self._phantom_failures.get(skill_name, 0) + 1
                    consecutive = self._phantom_failures[skill_name]

                    if consecutive >= self._phantom_threshold:
                        # Hard-fail after threshold consecutive phantom failures
                        logging.error(f"💀 HARD FAIL: {skill_name} phantom-failed {consecutive}x consecutively. Treating as real failure.")
                        self.recent_actions.append(f"PHANTOM_FAIL: {skill_name} ({consecutive}x)")
                        self.recent_actions = self.recent_actions[-10:]
                        # Record lesson for learning
                        if self.lesson_memory:
                            self.lesson_memory.record_failure(
                                attempted=f"{skill_name} (phantom failure)",
                                blocked_by="state unchanged",
                                position=state_before.get("target"),
                                location=self.last_state.get("location", {}).get("name") if self.last_state else None
                            )
                        return False
                    else:
                        # Soft warning, still return success (might be timing issue)
                        logging.warning(f"⚠️ Phantom failure #{consecutive} for {skill_name} (threshold: {self._phantom_threshold})")
                        return True
            else:
                logging.warning(f"❌ Skill {skill_name} failed: {result.error}")
                if result.recovery_skill:
                    logging.info(f"💡 Recovery suggested: {result.recovery_skill}")
                return False
        except Exception as e:
            logging.error(f"Skill execution error: {e}")
            return False

    def is_skill(self, action_type: str) -> bool:
        """Check if an action type is a skill name."""
        return action_type in self.skills_dict

    def _filter_adjacent_crop_moves(self, actions: List[Action]) -> List[Action]:
        """
        Post-processing filter: Remove invalid move actions when already adjacent to a crop.

        The VLM sometimes ignores "NO move!" hints and outputs move actions anyway.
        This filter checks game state and removes moves that would land ON a crop.

        Returns:
            Filtered action list with invalid moves removed.
        """
        if not actions or not hasattr(self.controller, "get_state"):
            return actions

        # Only filter if first action is a move
        if actions[0].action_type != "move":
            return actions

        # Check if followed by a crop skill
        crop_skills = {"water_crop", "harvest_crop", "harvest"}
        has_crop_skill = any(a.action_type in crop_skills for a in actions)
        if not has_crop_skill:
            return actions

        # Get game state
        state = self.controller.get_state()
        if not state:
            return actions

        player_x = state.get("player", {}).get("tileX", 0)
        player_y = state.get("player", {}).get("tileY", 0)
        crops = state.get("location", {}).get("crops", [])

        if not crops:
            return actions

        # Find nearest crop that needs attention
        for crop in crops:
            cx, cy = crop.get("x", 0), crop.get("y", 0)
            dx, dy = cx - player_x, cy - player_y
            dist = abs(dx) + abs(dy)

            if dist <= 1:
                # We're adjacent or ON a crop - filter out the move!
                logging.info(f"🚫 FILTER: Removing move action - already adjacent to crop at ({cx},{cy}), dist={dist}")
                # Remove the first move action, replace with face if needed
                filtered = []
                skipped_move = False
                for a in actions:
                    if a.action_type == "move" and not skipped_move:
                        skipped_move = True
                        # Add a face action instead if we have direction
                        if dy < 0:
                            face_dir = "north"
                        elif dy > 0:
                            face_dir = "south"
                        elif dx < 0:
                            face_dir = "west"
                        else:
                            face_dir = "east"
                        filtered.append(Action("face", {"direction": face_dir}, f"Face crop (filtered move)"))
                        logging.info(f"   → Replaced with: face {face_dir}")
                    else:
                        filtered.append(a)
                return filtered

        return actions

    def _fix_empty_watering_can(self, actions: List[Action]) -> List[Action]:
        """
        Override: If watering can is empty AND at water, FORCE refill_watering_can.

        The VLM often outputs wrong actions (water_crop, interact, wait) when the can is empty.
        This override forces refill when conditions are right.
        """
        if not actions:
            return actions

        # Skip if already refilling
        if any(a.action_type == "refill_watering_can" for a in actions):
            return actions

        # Get state to check watering can level
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        water_left = state.get("player", {}).get("wateringCanWater", 40)
        if water_left > 0:
            return actions  # Can has water, no fix needed

        # Watering can is empty - check if at water
        surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None
        if not surroundings:
            return actions

        # Check directions for water
        directions = surroundings.get("directions", {})
        water_direction = None
        for dir_name in ["south", "north", "east", "west"]:
            dir_data = directions.get(dir_name, {})
            blocker = dir_data.get("blocker", "")
            tiles_until = dir_data.get("tilesUntilBlocked", 99)
            if blocker and "water" in blocker.lower() and tiles_until == 0:
                water_direction = dir_name
                break

        if not water_direction:
            return actions  # Not at water

        # OVERRIDE: Force refill regardless of what VLM output
        logging.info(f"🔄 OVERRIDE: Empty can + at water → FORCING refill_watering_can direction={water_direction}")
        return [Action("refill_watering_can", {"target_direction": water_direction}, "Auto-refill (can empty)")]

    # ═══════════════════════════════════════════════════════════════════════
    # TASK EXECUTOR HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _try_start_daily_task(self) -> bool:
        """
        Try to start the next pending task from daily planner.
        
        Maps daily planner task categories to TaskExecutor task types.
        Returns True if a task was started, False otherwise.
        """
        if not self.task_executor or not self.daily_planner:
            return False
        
        # Don't start if executor is already active
        if self.task_executor.is_active():
            return False
        
        # Get current game state for target generation
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return False
        
        player_pos = self.last_position or (0, 0)
        
        # Map daily planner categories to executor task types
        CATEGORY_TO_TASK = {
            "water": "water_crops",
            "harvest": "harvest_crops", 
            "plant": "plant_seeds",
            "clear": "clear_debris",
            "till": "till_soil",
        }
        
        # Find next pending task that maps to an executor task type
        for task in self.daily_planner.tasks:
            if task.status != "pending":
                continue
            
            # Check task description for keywords
            task_lower = task.description.lower()
            task_type = None
            
            for keyword, executor_task in CATEGORY_TO_TASK.items():
                if keyword in task_lower:
                    task_type = executor_task
                    break
            
            if not task_type:
                continue
            
            # Try to start this task
            has_targets = self.task_executor.set_task(
                task_id=task.id,
                task_type=task_type,
                game_state=state,
                player_pos=player_pos,
            )
            
            if has_targets:
                # Mark task as in progress in daily planner
                try:
                    self.daily_planner.start_task(task.id)
                except Exception:
                    pass  # start_task might not exist
                
                logging.info(f"🎯 Started task: {task_type} ({self.task_executor.progress.total_targets} targets)")
                return True
            else:
                # No targets for this task - mark complete
                logging.info(f"✅ No targets for {task_type} - marking complete")
                try:
                    self.daily_planner.complete_task(task.id)
                except Exception as e:
                    logging.warning(f"Failed to mark task complete: {e}")
        
        return False

    def _get_task_executor_context(self) -> str:
        """Get context string for VLM about current task execution."""
        if not self.task_executor:
            return ""
        
        if self.task_executor.is_active():
            return self.task_executor.get_context_for_vlm()
        
        return ""

    def _fix_active_popup(self, actions: List[Action]) -> List[Action]:
        """
        Override: If menu/event is active, dismiss it before continuing.
        This handles level-up screens, shipping summaries, dialogue boxes, etc.
        """
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        # Check for active menu or event
        menu = state.get("menu")
        event = state.get("event")
        dialogue_up = state.get("dialogueUp", False)
        paused = state.get("paused", False)

        if menu or event or dialogue_up or paused:
            what = menu or event or ("dialogue" if dialogue_up else "pause")
            logging.info(f"🚫 POPUP OVERRIDE: {what} active → dismiss_menu first")
            # Return dismiss_menu as the only action - we'll resume normal actions next tick
            return [Action("dismiss_menu", {}, f"Dismiss {what}")]

        return actions

    def _fix_late_night_bed(self, actions: List[Action]) -> List[Action]:
        """
        Override: If very late (hour >= 23) and not going to bed, force go_to_bed.
        Game time: 2AM = hour 26, midnight = 24, 11PM = 23
        """
        if not actions:
            return actions

        # Check if already going to bed
        if any(a.action_type == "go_to_bed" for a in actions):
            return actions

        # Get state to check time
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        hour = state.get("time", {}).get("hour", 6)
        if hour < 23:
            return actions  # Not critical yet (before 11 PM)

        # It's 11 PM or later - force go_to_bed
        logging.info(f"🛏️ OVERRIDE: Hour {hour} >= 23, forcing go_to_bed")
        return [Action("go_to_bed", {}, "Auto-bed (very late)")]

    def _fix_priority_shipping(self, actions: List[Action]) -> List[Action]:
        """
        Override: If we have sellable crops in inventory, prioritize shipping over other tasks.
        AGGRESSIVE: Override ALL actions except critical ones until crops are shipped.
        """
        if not actions:
            return actions

        # Only allow these through - everything else gets overridden
        critical_actions = {"ship_item", "go_to_bed", "harvest", "water_crop", "refill_watering_can", "warp"}
        if any(a.action_type in critical_actions for a in actions):
            return actions

        # Get state to check inventory and location
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        location = state.get("location", {}).get("name", "")
        if location not in ["Farm", "FarmHouse"]:
            return actions  # Only apply on farm areas

        # Check for sellable items
        inventory = state.get("inventory", [])
        sellable_items = ["Parsnip", "Potato", "Cauliflower", "Green Bean", "Kale", "Melon",
                         "Blueberry", "Corn", "Tomato", "Pumpkin", "Cranberry", "Eggplant", "Grape", "Radish"]
        sellables = [item for item in inventory if item and item.get("name") in sellable_items and item.get("stack", 0) > 0]

        if not sellables:
            return actions  # No sellables, proceed normally

        total_to_ship = sum(item.get("stack", 0) for item in sellables)

        # Get player and bin positions
        player_x = state.get("player", {}).get("tileX", 0)
        player_y = state.get("player", {}).get("tileY", 0)
        shipping_bin = state.get("location", {}).get("shippingBin") or {}
        bin_x = shipping_bin.get("x", 71)
        bin_y = shipping_bin.get("y", 14)
        dx = bin_x - player_x
        dy = bin_y - player_y
        dist = abs(dx) + abs(dy)

        # If in FarmHouse, override to warp to Farm first
        if location == "FarmHouse":
            logging.info(f"📦 OVERRIDE: Have {total_to_ship} sellables in FarmHouse → warp to Farm")
            return [Action("warp", {"location": "Farm"}, f"Auto-warp to ship {total_to_ship} crops")]

        # If adjacent to shipping bin (dist <= 2 to be safe), ship immediately
        if dist <= 2:
            face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
            logging.info(f"📦 OVERRIDE: At shipping bin (dist={dist}) → ship_item")
            return [Action("face", {"direction": face_dir}, "Face bin"),
                    Action("ship_item", {}, f"Ship {total_to_ship} crops")]

        # AGGRESSIVE: Override ANY action to move toward bin when we have sellables
        original_action = actions[0].action_type if actions else "unknown"
        
        # Calculate direction to shipping bin
        if abs(dy) > abs(dx):
            direction = "north" if dy < 0 else "south"
            tiles = min(abs(dy), 5)  # Move up to 5 tiles at a time
        else:
            direction = "west" if dx < 0 else "east"
            tiles = min(abs(dx), 5)
        
        logging.info(f"📦 OVERRIDE: VLM wanted '{original_action}' but have {total_to_ship} sellables → move {direction} toward bin (dist={dist})")
        return [Action("move", {"direction": direction, "tiles": tiles}, f"Move to ship {total_to_ship} crops")]

    def _fix_no_seeds(self, actions: List[Action]) -> List[Action]:
        """
        Override: If we have no seeds and Pierre's is open, force go_to_pierre.
        If already at Pierre's, force buy_parsnip_seeds.
        This prevents the agent from endlessly farming or clearing when it should buy seeds.
        """
        if not actions:
            return actions

        # Get state to check inventory and location
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        location = state.get("location", {}).get("name", "")

        # Check for seeds in inventory (used in both branches)
        inventory = state.get("inventory", [])
        has_seeds = any(item and ("Seed" in item.get("name", "") or item.get("name") == "Mixed Seeds")
                       for item in inventory if item)

        # If at Pierre's (SeedShop), force buy seeds regardless of VLM action
        if location == "SeedShop":
            if not has_seeds:
                money = state.get("player", {}).get("money", 0)
                if money >= 20:
                    logging.info(f"🛒 OVERRIDE: In SeedShop with no seeds → buy_parsnip_seeds (have {money}g)")
                    return [Action("buy_parsnip_seeds", {}, f"Buy seeds at Pierre's ({money}g available)")]
            return actions  # Has seeds or can't afford, proceed normally

        # Not at Pierre's - check if we should force navigation there
        # Override farming AND debris actions when no seeds
        override_actions = {"clear_stone", "clear_wood", "clear_weeds", "clear_debris",
                           "chop_tree", "mine_boulder", "break_stone",
                           "till_soil", "plant_seed", "water_crop", "harvest"}

        # Check if first action should be overridden
        first_action = actions[0].action_type if actions else ""
        if first_action not in override_actions:
            return actions  # Not a farming/debris action, let it through

        # Check for seeds in inventory
        inventory = state.get("inventory", [])
        has_seeds = any(item and ("Seed" in item.get("name", "") or item.get("name") == "Mixed Seeds") 
                       for item in inventory if item)
        
        if has_seeds:
            return actions  # Has seeds, proceed normally

        # Check if Pierre's is open
        time_data = state.get("time", {})
        hour = time_data.get("hour", 12)
        day_of_week = time_data.get("dayOfWeek", "")
        money = state.get("player", {}).get("money", 0)

        # Pierre's is open 9-17, closed Wednesday
        if day_of_week == "Wed" or hour < 9 or hour >= 17:
            return actions  # Pierre's closed

        if money < 20:
            return actions  # Can't afford seeds

        # OVERRIDE: Force go_to_pierre
        logging.info(f"🌱 OVERRIDE: VLM wanted '{first_action}' but NO SEEDS! → go_to_pierre (have {money}g, Pierre's open)")
        return [Action("go_to_pierre", {}, f"Buy seeds (have {money}g, no seeds in inventory)")]

    def _fix_edge_stuck(self, actions: List[Action]) -> List[Action]:
        """
        Override: If stuck at map edge (cliffs/water), force movement toward farm center.
        Detects repetitive actions at edges and forces retreat.
        """
        if not actions:
            return actions

        # Get state to check position
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return actions

        location = state.get("location", {}).get("name", "")
        if location != "Farm":
            return actions  # Only apply on farm

        player_x = state.get("player", {}).get("tileX", 0)
        player_y = state.get("player", {}).get("tileY", 0)
        
        # Farm center is roughly (60, 20) - farmhouse area
        # Edges are: east > 72, south > 45, north < 10, west < 8
        at_edge = player_x > 72 or player_x < 8 or player_y > 45 or player_y < 10
        
        if not at_edge:
            return actions  # Not at edge

        # Check if we're repeating debris OR move actions
        stuck_actions = {"clear_stone", "clear_wood", "clear_weeds", "clear_debris", 
                         "chop_tree", "mine_boulder", "break_stone", "move"}
        first_action = actions[0].action_type if actions else ""
        
        if first_action not in stuck_actions:
            return actions  # Not a stuck-prone action

        # Check repetition in recent history (any stuck action)
        repeat_count = sum(1 for a in self.recent_actions[-5:] if any(d in a for d in stuck_actions))
        
        if repeat_count < 3:
            return actions  # Not stuck yet

        # Calculate direction toward farm center (60, 20)
        dx = 60 - player_x
        dy = 20 - player_y
        
        # Pick direction that moves toward center, preferring the axis farther from center
        if abs(dx) > abs(dy):
            direction = "west" if dx < 0 else "east"
            tiles = min(abs(dx), 5)
        else:
            direction = "north" if dy < 0 else "south"
            tiles = min(abs(dy), 5)
        
        # Force move toward center (or go_to_bed if late)
        hour = state.get("time", {}).get("hour", 12)
        if hour >= 20:
            logging.info(f"🏃 EDGE-STUCK OVERRIDE: At edge ({player_x}, {player_y}), late night → go_to_bed")
            return [Action("go_to_bed", {}, "Late night at edge, time for bed")]
        
        logging.info(f"🏃 EDGE-STUCK OVERRIDE: At edge ({player_x}, {player_y}), repeating x{repeat_count} → retreat {direction} toward center")
        return [Action("move", {"direction": direction, "tiles": tiles}, f"Retreat from edge toward farm center")]

    def _vlm_reason(self, prompt: str) -> Optional[str]:
        """Use VLM for reasoning/planning (synchronous wrapper).

        This allows the daily planner to use compute cycles for intelligent planning.
        """
        if not self.vlm:
            return None

        try:
            # Use VLM without image for pure reasoning
            # The VLM class should have a method for text-only reasoning
            if hasattr(self.vlm, 'reason'):
                return self.vlm.reason(prompt)
            elif hasattr(self.vlm, 'think_text'):
                return self.vlm.think_text(prompt)
            else:
                # Fallback: use think with no image (if supported)
                logging.warning("VLM doesn't have text-only reasoning method")
                return None
        except Exception as e:
            logging.warning(f"VLM reasoning failed: {e}")
            return None

    def _refresh_state_snapshot(self) -> None:
        if not hasattr(self.controller, "get_state"):
            return
        if not getattr(self.controller, "enabled", True):
            return
        now = time.time()
        if now - self.last_state_poll < 0.5:
            return
        state = self.controller.get_state()
        if not state:
            return
        self.last_state_poll = now
        self.last_state = state

        # Update Rusty memory with current day/season (if available)
        if self.rusty_memory:
            time_data = state.get("time", {})
            day = time_data.get("day", 0)
            season = time_data.get("season", "spring")
            if day > 0 and (day != self.rusty_memory.current_day or season != self.rusty_memory.current_season):
                self.rusty_memory.start_session(day, season)

        # Daily planning - trigger new day plan when day changes
        if self.daily_planner:
            time_data = state.get("time", {})
            day = time_data.get("day", 0)
            season = time_data.get("season", "spring")
            if day > 0 and day != self._last_planned_day:
                logging.info(f"🌅 New day detected: Day {day} - generating plan...")
                # Pass VLM reasoning function if available
                reason_fn = self._vlm_reason if hasattr(self, '_vlm_reason') else None
                plan_summary = self.daily_planner.start_new_day(day, season, state, reason_fn)
                logging.info(f"📋 Daily plan:\n{plan_summary}")
                self._last_planned_day = day

        if hasattr(self.controller, "get_surroundings"):
            try:
                self.last_surroundings = self.controller.get_surroundings()
            except Exception:
                self.last_surroundings = None

        player = state.get("player") or {}
        tile_x = player.get("tileX")
        tile_y = player.get("tileY")
        if tile_x is not None and tile_y is not None:
            position = (tile_x, tile_y)
            self.last_position = position
            if self.last_distance_position:
                dx = abs(position[0] - self.last_distance_position[0])
                dy = abs(position[1] - self.last_distance_position[1])
                self.distance_traveled += dx + dy
            self.last_distance_position = position
            if self.last_position_logged != position:
                location = (state.get("location") or {}).get("name")
                self.last_position_logged = position
                self._record_session_event("position", {
                    "x": tile_x,
                    "y": tile_y,
                    "location": location,
                })

        current_tool = player.get("currentTool")
        if current_tool:
            self.last_tool = current_tool

        self._update_spatial_map_from_state()

    def _record_action_event(self, action: Action, success: bool) -> None:
        self.action_count += 1
        if not success:
            self.action_fail_count += 1
        action_key = action.action_type.lower()
        self.action_type_counts[action_key] = self.action_type_counts.get(action_key, 0) + 1
        if success and action_key == "use_tool" and self.last_state:
            player = self.last_state.get("player", {})
            location = self.last_state.get("location", {})
            crops = location.get("crops", [])
            px = player.get("tileX")
            py = player.get("tileY")
            tool = player.get("currentTool", "")
            if px is not None and py is not None:
                crop_here = next((c for c in crops if c.get("x") == px and c.get("y") == py), None)
                if crop_here and crop_here.get("isReadyForHarvest"):
                    self.crops_harvested_count += 1
                elif crop_here and not crop_here.get("isWatered", True) and "Watering" in tool:
                    self.crops_watered_count += 1
                self._mark_current_tile_worked()
        self._record_session_event("action", {
            "action_type": action.action_type,
            "params": action.params,
            "description": action.description,
            "success": success,
        })
        if action.action_type in ("use_tool", "equip"):
            tool_name = action.params.get("tool") or self.last_tool
            self._record_session_event("tool_use", {
                "tool": tool_name,
                "action_type": action.action_type,
                "params": action.params,
            })

        # Record to Rusty memory for character persistence
        if self.rusty_memory:
            description = action.description or f"{action.action_type}"
            outcome = "success" if success else "failure"
            location = None
            if self.last_state:
                loc_data = self.last_state.get("location", {})
                location = loc_data.get("name")

            # Determine event type and importance
            event_type = "action"
            importance = 1  # Routine
            if action.action_type in ("harvest", "plant_seeds"):
                event_type = "farming"
                importance = 2
            elif action.action_type == "use_tool":
                tool = action.params.get("tool", "").lower()
                if "hoe" in tool:
                    event_type = "farming"
                elif "watering" in tool:
                    event_type = "farming"
            elif not success:
                importance = 2  # Failures are more memorable

            self.rusty_memory.record_event(
                event_type=event_type,
                description=description,
                outcome=outcome,
                importance=importance,
                location=location,
            )

        self._send_commentary(action, success)

    def _send_commentary(self, action: Action, success: bool) -> None:
        if not self.ui_enabled or not self.ui or not self.commentary_generator:
            return

        # Track commentary count for TTS throttling
        if not hasattr(self, '_commentary_count'):
            self._commentary_count = 0
        self._commentary_count += 1

        state = self.last_state or {}
        stats = {
            "crops_harvested_count": self.crops_harvested_count,
            "crops_watered_count": self.crops_watered_count,
            "distance_traveled": self.distance_traveled,
            "action_count": self.action_count,
        }
        state_data = dict(state)
        state_data["stats"] = stats

        # Ensure location is top-level for generator
        loc_data = state.get("location") or {}
        if loc_data.get("name") and "location" not in state_data:
            state_data["location"] = loc_data.get("name")
        state_data["crops"] = loc_data.get("crops") or []
        if self.plot_manager and self.plot_manager.is_active():
            active_state = self.plot_manager.farm_plan.get_active_state() if self.plot_manager.farm_plan else None
            state_data["farm_plan"] = {
                "active": True,
                "phase": active_state.phase.value if active_state else None,
            }
        personality = None
        tts_enabled = None
        volume = None
        voice_override = None
        try:
            settings = self.ui.get_commentary()
            personality = settings.get("personality")
            tts_enabled = settings.get("tts_enabled")
            volume = settings.get("volume")
            voice_override = settings.get("voice")  # Manual voice override from UI
        except Exception:
            settings = {}

        if personality:
            self.commentary_generator.set_personality(personality)

        # Use VLM's creative mood for UI (full text)
        # TTS will only read first sentence (handled separately below)
        if self.last_mood and len(self.last_mood) > 10:
            ui_text = self.last_mood  # Full commentary for display
            logging.info(f"💭 VLM: {ui_text[:80]}...")
        else:
            ui_text = self.commentary_generator.generate(action.action_type, state_data, "")
            logging.info(f"📝 Template: {ui_text[:80]}...")

        self._ui_safe(
            self.ui.update_commentary,
            text=ui_text,
            personality=self.commentary_generator.personality,
            tts_enabled=tts_enabled,
            volume=volume,
        )

        # TTS: Read commentary every 4 actions with time throttle (prevents doubling)
        if not hasattr(self, '_last_tts_time'):
            self._last_tts_time = 0
        import time
        current_time = time.time()
        tts_cooldown = 8.0  # Minimum seconds between TTS
        time_ok = (current_time - self._last_tts_time) >= tts_cooldown

        if tts_enabled and self.commentary_tts and self._commentary_count % 4 == 0 and time_ok:
            try:
                # Clean text for TTS - remove special chars that get read aloud
                import re
                tts_text = ui_text
                tts_text = re.sub(r'["\'\*\_\#\`\[\]\(\)\{\}]', '', tts_text)  # Remove quotes, markdown
                tts_text = re.sub(r'\s+', ' ', tts_text).strip()  # Normalize whitespace

                # Get voice: UI override > personality mapping > default
                voice = voice_override
                if not voice and self.commentary_generator:
                    voice = self.commentary_generator.get_voice()

                self.commentary_tts.speak(tts_text, voice=voice)
                self._last_tts_time = current_time
            except Exception:
                pass

    def _check_memory_triggers(self, result: ThinkResult, game_day: str = "") -> None:
        """Check for events that should trigger memory storage."""
        if not HAS_MEMORY or not get_memory:
            return

        memory = get_memory()
        current_location = result.location

        # Trigger 1: New location visited (first time)
        if current_location and current_location not in self.visited_locations:
            self.visited_locations.add(current_location)
            memory.store(
                text=f"First visit to {current_location}. {result.reasoning[:100] if result.reasoning else ''}",
                memory_type="location_first",
                location=current_location,
                game_day=game_day,
                outcome="positive"
            )
            logging.info(f"   💾 Memory stored: First visit to {current_location}")

        # Trigger 2: Location changed (general transition)
        if current_location and current_location != self.last_location and self.last_location:
            # Only store if visiting after first time and it's been a while
            pass  # First visit handled above, transitions are less important

        # Trigger 3: New NPC encountered
        current_npcs = []
        if self.last_state:
            loc_data = self.last_state.get("location", {})
            current_npcs = [npc.get("name", "") for npc in loc_data.get("npcs", []) if npc.get("name")]

        for npc_name in current_npcs:
            if npc_name and npc_name not in self.met_npcs:
                self.met_npcs.add(npc_name)
                # Get NPC info from game knowledge
                npc_info = ""
                if get_npc_info:
                    info = get_npc_info(npc_name)
                    if info:
                        loved = info.get("loved_gifts", [])[:3]
                        npc_info = f"They love: {', '.join(loved)}." if loved else ""

                memory.store(
                    text=f"Met {npc_name} at {current_location}. {npc_info}",
                    memory_type="npc_interaction",
                    location=current_location,
                    npc=npc_name,
                    game_day=game_day,
                    outcome="positive"
                )
                logging.info(f"   💾 Memory stored: Met {npc_name}")

                # Also record in Rusty memory for character persistence
                if self.rusty_memory:
                    self.rusty_memory.record_event(
                        event_type="meeting",
                        description=f"First time meeting {npc_name}",
                        outcome="success",
                        importance=3,  # Meeting NPCs is moderately important
                        location=current_location,
                        npc=npc_name,
                    )

        # Trigger 4: VLM reasoning suggests importance
        if result.reasoning and should_remember:
            if should_remember("notable", reasoning=result.reasoning):
                # Avoid duplicate storage for location/NPC triggers
                if "first visit" not in result.reasoning.lower() and "met " not in result.reasoning.lower():
                    memory.store(
                        text=f"{result.reasoning[:200]}",
                        memory_type="notable",
                        location=current_location,
                        game_day=game_day,
                    )
                    logging.info(f"   💾 Memory stored: Notable event")

        # Update tracking state
        self.last_location = current_location
        self.last_nearby_npcs = current_npcs

    def _format_action(self, action: Action) -> str:
        if action.description:
            return action.description
        if action.action_type == "move":
            direction = normalize_direction(action.params.get("direction", "south"))
            duration = action.params.get("duration", 0.0)
            return f"move {direction} ({duration:.1f}s)"
        if action.action_type == "wait":
            seconds = action.params.get("seconds", 1)
            return f"wait {seconds:.1f}s"
        if action.action_type == "button":
            button = action.params.get("button", "a")
            return f"press {button}"
        return action.action_type.replace("_", " ")

    def _send_ui_status(self, result: Optional[ThinkResult] = None) -> None:
        if not self.ui_enabled:
            return
        self._refresh_state_snapshot()
        payload: Dict[str, Any] = {
            "mode": self.config.mode,
            "running": self.running,
            "vlm_status": self.vlm_status,
            "last_actions": list(self.recent_actions),
            "player_tile_x": self.last_position[0] if self.last_position else None,
            "player_tile_y": self.last_position[1] if self.last_position else None,
            "current_instruction": self.current_instruction,
            "navigation_target": self.navigation_target,
            "navigation_blocked": self.last_blocked_direction,
            "navigation_attempts": self.movement_attempts,
            "vlm_parse_success": self.vlm_parse_success,
            "vlm_parse_fail": self.vlm_parse_fail,
            "vlm_errors": list(self.vlm_errors),
            "session_started_at": self.session_started_at,
            "think_count": self.think_count,
            "action_count": self.action_count,
            "action_fail_count": self.action_fail_count,
            "action_type_counts": dict(self.action_type_counts),
            "distance_traveled": self.distance_traveled,
            "crops_watered_count": self.crops_watered_count,
            "crops_harvested_count": self.crops_harvested_count,
            "latency_history": list(self.latency_history),
            "available_skills_count": len(self.skill_context.get_available_skills(self.last_state)) if self.skill_context and self.last_state else 0,
            # VLM Debug panel fields
            "vlm_observation": self.vlm_observation,
            "proposed_action": self.proposed_action,
            "validation_status": self.validation_status,
            "validation_reason": self.validation_reason,
            "executed_action": self.executed_action,
            "executed_outcome": self.executed_outcome,
        }
        if result:
            # Only use VLM mood if it's new and substantial, don't persist old moods
            self.last_mood = result.mood if result.mood and len(result.mood) > 20 else ""
            payload.update({
                "last_tick": datetime.now().isoformat(timespec="seconds"),
                "location": result.location,
                "time_of_day": result.time_of_day,
                "weather": result.weather,
                "energy": result.energy,
                "holding": result.holding,
                "mood": result.mood,
                "menu_open": result.menu_open,
                "nearby": result.nearby_objects,
                "action_plan": [self._format_action(a) for a in result.actions],
                "last_reasoning": result.reasoning,
            })
            if result.reasoning.startswith("ERROR"):
                payload["last_error"] = result.reasoning
        # Guard against UI being disabled mid-operation
        if self.ui_enabled and self.ui:
            self._ui_safe(self.ui.update_status, **payload)

    def _send_ui_message(self, result: ThinkResult) -> None:
        if not self.ui_enabled:
            return
        plan = [self._format_action(a) for a in result.actions]
        summary_lines = [
            f"Location: {result.location or '-'} | Time: {result.time_of_day or '-'} | Weather: {result.weather or '-'}",
            f"Energy: {result.energy or '-'} | Holding: {result.holding or 'nothing'} | Mood: {result.mood or '-'}",
        ]
        if result.nearby_objects:
            summary_lines.append(f"Nearby: {', '.join(result.nearby_objects)}")
        if plan:
            summary_lines.append(f"Plan: {'; '.join(plan)}")
        summary = "\n".join(summary_lines)
        if self.ui_enabled and self.ui:
            self._ui_safe(self.ui.send_message, "agent", summary, reasoning=result.reasoning or None)

    async def run(self, goal: str = ""):
        """Main agent loop."""
        self.running = True
        self.goal = goal
        self.vlm_status = "Idle"
        self.session_started_at = datetime.now().isoformat(timespec="seconds")

        logging.info("=" * 60)
        logging.info("StardewAI Unified Agent Starting")
        logging.info(f"Mode: {self.config.mode.upper()}")
        logging.info(f"Model: {self.config.model}")
        logging.info(f"Goal: {goal or 'General assistance'}")
        logging.info(f"Controller: {'ENABLED' if self.controller.enabled else 'DRY RUN'}")
        logging.info("=" * 60)
        self._send_ui_status()

        try:
            while self.running:
                await self._tick()
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            logging.info("Stopped by user")
        finally:
            self.running = False
            self.controller.reset()
            self.vlm_status = "Idle"
            self._send_ui_status()


    def _build_dynamic_hints(self) -> str:
        """
        Extract critical hints from SMAPI state - condensed for vision-first.
        
        Returns 3-5 priority hints based on current game state.
        Priority order:
        1. Empty watering can (blocks all watering progress)
        2. Current tile action (what to do HERE)
        3. Crop status (unwatered/harvestable nearby)
        4. Time/energy warnings
        """
        if not self.last_state or not self.last_surroundings:
            return ""
        
        hints = []
        state = self.last_state
        data = self.last_surroundings
        
        # Extract common data
        player = state.get("player", {})
        location = state.get("location", {})
        crops = location.get("crops", [])
        current_tool = player.get("currentTool", "none")
        current_slot = player.get("currentToolIndex", -1)
        player_x = player.get("tileX", 0)
        player_y = player.get("tileY", 0)
        water_left = player.get("wateringCanWater", 0)
        water_max = player.get("wateringCanMax", 40)
        hour = state.get("time", {}).get("hour", 6)
        energy = player.get("energy", 270)
        max_energy = player.get("maxEnergy", 270)
        energy_pct = int(100 * energy / max_energy) if max_energy > 0 else 100
        
        # Crop counts
        unwatered = [c for c in crops if not c.get("isWatered", False)]
        harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
        
        # Tool slots for reference
        tool_slots = {"Axe": 0, "Hoe": 1, "Watering Can": 2, "Pickaxe": 3, "Scythe": 4}
        
        # --- PRIORITY 1: Empty Watering Can ---
        if water_left <= 0 and unwatered:
            nearest_water = data.get("nearestWater")
            if nearest_water:
                water_dir = nearest_water.get("direction", "nearby")
                water_dist = nearest_water.get("distance", "?")
                hints.append(f"⚠️ WATERING CAN EMPTY! Water {water_dist} tiles {water_dir} - refill first!")
            else:
                hints.append("⚠️ WATERING CAN EMPTY! Find water to refill!")
        
        # --- PRIORITY 2: Current Tile Action ---
        current_tile = data.get("currentTile", {})
        tile_state = current_tile.get("state", "unknown")
        tile_obj = current_tile.get("object")
        can_till = current_tile.get("canTill", False)
        can_plant = current_tile.get("canPlant", False)
        
        # Check for crop at current position
        crop_here = next((c for c in crops if c.get("x") == player_x and c.get("y") == player_y), None)
        
        # Check for seeds in inventory
        inventory = state.get("inventory", [])
        seed_slot = None
        seed_name = None
        for item in inventory:
            item_name = item.get("name", "")
            if "Seed" in item_name or item_name == "Mixed Seeds":
                seed_slot = item.get("slot")
                seed_name = item_name
                break
        
        if crop_here and crop_here.get("isReadyForHarvest"):
            crop_name = crop_here.get("cropName", "crop")
            hints.append(f"🌾 HARVEST! {crop_name} ready - use harvest action")
        elif tile_state == "tilled":
            if seed_slot is not None:
                if "Seed" in current_tool:
                    hints.append(f"🌱 TILLED + seeds ready - use_tool to plant!")
                else:
                    hints.append(f"🌱 TILLED - select_slot {seed_slot} ({seed_name}), use_tool to plant")
            else:
                hints.append("🌱 TILLED (no seeds) - move to find crops")
        elif tile_state == "planted":
            # Crop protection warning
            dangerous = ["Scythe", "Hoe", "Pickaxe", "Axe"]
            if any(t.lower() in current_tool.lower() for t in dangerous):
                hints.append(f"⚠️ CROP HERE! Don't use {current_tool}! Select Watering Can (slot 2)")
            elif water_left > 0:
                if "Watering" in current_tool:
                    hints.append(f"💧 PLANTED - use_tool to water! ({water_left}/{water_max})")
                else:
                    hints.append(f"💧 PLANTED - select_slot 2 (Watering Can), use_tool")
        elif tile_state == "watered":
            if can_plant and seed_slot is not None:
                hints.append(f"🌱 WET SOIL - select_slot {seed_slot}, use_tool to plant")
            else:
                hints.append("✅ WATERED - move to next crop")
        elif tile_state == "debris":
            needed = "Scythe" if tile_obj in ["Weeds", "Grass"] else "Pickaxe" if tile_obj == "Stone" else "Axe"
            needed_slot = tool_slots.get(needed, 4)
            if needed.lower() in current_tool.lower():
                hints.append(f"🪓 {tile_obj} - use_tool to clear")
            else:
                hints.append(f"🪓 {tile_obj} - select_slot {needed_slot} ({needed}), use_tool")
        elif tile_state == "clear" and can_till:
            if unwatered:
                hints.append(f"📍 CLEAR - {len(unwatered)} crops need water, move there first!")
            elif "Hoe" in current_tool:
                hints.append("📍 CLEAR + Hoe ready - use_tool to till")
            else:
                hints.append("📍 CLEAR - select_slot 1 (Hoe), use_tool to till")
        
        # --- PRIORITY 3: Crop Status (if not already handled) ---
        if unwatered and water_left > 0 and tile_state not in ["planted"]:
            nearest = min(unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
            dx = nearest["x"] - player_x
            dy = nearest["y"] - player_y
            dist = abs(dx) + abs(dy)
            
            if dist == 0:
                # Standing ON crop - step back first
                hints.append(f"💧 ON CROP! DO: move 1 tile back, face crop, water")
            elif dist == 1:
                face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
                hints.append(f"💧 ADJACENT! DO: face {face_dir}, water_crop (NO move!)")
            elif dist > 1:
                # Calculate movement to stop ADJACENT (1 tile away), then face crop
                abs_dx, abs_dy = abs(dx), abs(dy)
                if abs_dy == 0:
                    move_hint = f"{abs_dx-1}{'E' if dx > 0 else 'W'}"
                    face_dir = "EAST" if dx > 0 else "WEST"
                elif abs_dx == 0:
                    move_hint = f"{abs_dy-1}{'S' if dy > 0 else 'N'}"
                    face_dir = "SOUTH" if dy > 0 else "NORTH"
                else:
                    # Diagonal: reduce larger axis by 1
                    if abs_dy >= abs_dx:
                        my, mx = abs_dy - 1, abs_dx
                        face_dir = "SOUTH" if dy > 0 else "NORTH"
                    else:
                        my, mx = abs_dy, abs_dx - 1
                        face_dir = "EAST" if dx > 0 else "WEST"
                    parts = []
                    if my > 0: parts.append(f"{my}{'S' if dy > 0 else 'N'}")
                    if mx > 0: parts.append(f"{mx}{'E' if dx > 0 else 'W'}")
                    move_hint = "+".join(parts) if parts else "0"
                hints.append(f"💧 {len(unwatered)} unwatered - move {move_hint}, face {face_dir}")
        
        if harvestable and tile_state != "planted":
            nearest_h = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
            dx = nearest_h["x"] - player_x
            dy = nearest_h["y"] - player_y
            dist = abs(dx) + abs(dy)
            
            if dist == 0:
                # Standing ON crop - step back first
                hints.append(f"🌾 ON CROP! DO: move 1 tile back, face crop, harvest")
            elif dist == 1:
                face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
                hints.append(f"🌾 ADJACENT! DO: face {face_dir}, harvest_crop (NO move!)")
            elif dist > 1:
                # Calculate movement to stop ADJACENT (1 tile away), then face crop
                abs_dx, abs_dy = abs(dx), abs(dy)
                if abs_dy == 0:
                    move_hint = f"{abs_dx-1}{'E' if dx > 0 else 'W'}"
                    face_dir = "EAST" if dx > 0 else "WEST"
                elif abs_dx == 0:
                    move_hint = f"{abs_dy-1}{'S' if dy > 0 else 'N'}"
                    face_dir = "SOUTH" if dy > 0 else "NORTH"
                else:
                    # Diagonal: reduce larger axis by 1
                    if abs_dy >= abs_dx:
                        my, mx = abs_dy - 1, abs_dx
                        face_dir = "SOUTH" if dy > 0 else "NORTH"
                    else:
                        my, mx = abs_dy, abs_dx - 1
                        face_dir = "EAST" if dx > 0 else "WEST"
                    parts = []
                    if my > 0: parts.append(f"{my}{'S' if dy > 0 else 'N'}")
                    if mx > 0: parts.append(f"{mx}{'E' if dx > 0 else 'W'}")
                    move_hint = "+".join(parts) if parts else "0"
                hints.append(f"🌾 {len(harvestable)} harvestable - move {move_hint}, face {face_dir}")
        
        # --- PRIORITY 4: Time/Energy Warnings ---
        if hour >= 24 or hour < 2:
            hints.append("⚠️ VERY LATE! Pass out soon - go_to_bed!")
        elif hour >= 22:
            hints.append("🌙 LATE (10PM+) - consider bed")
        
        if energy_pct <= 20:
            hints.append("😓 ENERGY CRITICAL (<20%) - rest or sleep!")
        elif energy_pct <= 35:
            hints.append("😐 Energy low - pace yourself")
        
        # Return top 5 hints max
        return "\n".join(hints[:5])

    def _build_light_context(self) -> str:
        """
        Build minimal SMAPI context for vision-first mode.

        Light context includes: position, time, energy, tool, and 3x3 immediate tiles.
        This is the grounding info - vision is still primary.
        """
        if not self.last_state:
            return ""

        # Basic state
        location_data = self.last_state.get("location", {})
        time_data = self.last_state.get("time", {})
        player_data = self.last_state.get("player", {})

        location = location_data.get("name", "Unknown")
        pos = location_data.get("position", {})
        x, y = pos.get("x", 0), pos.get("y", 0)

        hour = time_data.get("hour", 6)
        minute = time_data.get("minute", 0)
        am_pm = "am" if hour < 12 else "pm"
        display_hour = hour if hour <= 12 else hour - 12
        time_str = f"{display_hour}:{minute:02d} {am_pm}"

        energy = player_data.get("energy", 270)
        max_energy = player_data.get("maxEnergy", 270)
        energy_pct = int(100 * energy / max_energy) if max_energy > 0 else 100

        tool = player_data.get("currentTool", "none")

        # Build 3x3 tile grid from surroundings
        tiles_3x3 = "  (no SMAPI data)"
        if self.last_surroundings:
            adj = self.last_surroundings.get("adjacentTiles", {})
            # Format as simple grid
            # NW N NE
            # W  C  E
            # SW S SE
            def tile_char(key: str) -> str:
                tile = adj.get(key, {})
                if tile.get("isWater"):
                    return "💧"
                if tile.get("isPassable") == False:
                    return "🚫"
                if tile.get("crop"):
                    return "🌱"
                if tile.get("debris"):
                    return "🪨"
                if tile.get("tilled"):
                    return "▒"
                return "·"

            tiles_3x3 = f"""  {tile_char('NW')} {tile_char('N')} {tile_char('NE')}
  {tile_char('W')} 👤 {tile_char('E')}
  {tile_char('SW')} {tile_char('S')} {tile_char('SE')}"""

        # Recent actions (last 3)
        recent = ", ".join(self.recent_actions[-3:]) if self.recent_actions else "none"

        # Critical navigation hints (vision can't reliably determine these)
        nav_hints = []
        if location == "FarmHouse":
            nav_hints.append("🚪 EXIT: Walk SOUTH to leave, OR use warp: {\"type\": \"warp\", \"location\": \"Farm\"}")
        elif location in ["SeedShop", "Saloon", "JojaMart", "Blacksmith", "AnimalShop"]:
            nav_hints.append("🚪 EXIT: Walk SOUTH to leave, OR use warp: {\"type\": \"warp\", \"location\": \"Farm\"}")

        # Add landmark hints if available
        if self.last_surroundings:
            landmarks = self.last_surroundings.get("landmarks", {})
            if "farmhouse" in landmarks:
                fh = landmarks["farmhouse"]
                dist = fh.get("distance", 0)
                direction = fh.get("direction", "")
                if dist > 0 and direction:
                    nav_hints.append(f"🏠 Farmhouse: {dist} tiles {direction}")

        nav_section = "\n".join(nav_hints) if nav_hints else ""

        result = f"""📍 {location} @ ({x}, {y}) | ⏰ {time_str} | 💪 {energy_pct}% | 🔧 {tool}

3x3 around you:
{tiles_3x3}

Recent: {recent}"""

        if nav_section:
            result += f"\n\n{nav_section}"

        # Add dynamic farming hints (condensed from format_surroundings)
        dynamic_hints = self._build_dynamic_hints()
        if dynamic_hints:
            result += f"\n\n--- HINTS ---\n{dynamic_hints}"

        # Add Rusty's character context (for personality continuity)
        if self.rusty_memory:
            rusty_context = self.rusty_memory.get_context_for_prompt()
            if rusty_context:
                result += f"\n\n--- RUSTY ---\n{rusty_context}"

        # Add daily plan context (task awareness)
        if self.daily_planner and self.daily_planner.tasks:
            plan_context = self.daily_planner.get_plan_summary()
            if plan_context:
                result += f"\n\n--- TODAY'S PLAN ---\n{plan_context}"

        return result

    async def _tick(self):
        """Single tick of the agent loop."""
        now = time.time()

        # Execute queued actions first
        if self.action_queue:
            action = self.action_queue.pop(0)

            # Handle diagonal movement: split into two cardinal moves
            diagonal_second_dir = None  # Track if we're doing a diagonal split
            if action.action_type == "move":
                raw_dir = action.params.get("direction", "").strip().lower()
                if raw_dir in DIAGONAL_TO_CARDINAL:
                    first_dir, second_dir = DIAGONAL_TO_CARDINAL[raw_dir]
                    diagonal_second_dir = second_dir  # Remember for blocking check
                    logging.info(f"↗️ Splitting diagonal '{raw_dir}' into {first_dir} + {second_dir}")

                    # Modify current action to first cardinal direction
                    action.params["direction"] = first_dir

                    # Create second action and insert at front of queue
                    second_action = Action(
                        action_type="move",
                        params={"direction": second_dir, "duration": action.params.get("duration", 0.3)},
                        description=f"move {second_dir} (diagonal split)"
                    )
                    self.action_queue.insert(0, second_action)

            # Collision check for move actions - skip if direction is blocked
            if action.action_type == "move" and isinstance(self.controller, ModBridgeController):
                direction = normalize_direction(action.params.get("direction", ""))
                surroundings = self.controller.get_surroundings()
                if surroundings:
                    dirs = normalize_directions_map(surroundings.get("directions", {}))
                    dir_info = dirs.get(direction, {})
                    if not dir_info.get("clear", True) and dir_info.get("tilesUntilBlocked", 1) == 0:
                        blocker = dir_info.get('blocker', 'obstacle')

                        # Check if blocker is clearable debris
                        CLEARABLE_DEBRIS = {
                            "Weeds": ("AXE", 0),  # Scythe or axe works
                            "Grass": ("SCYTHE", 4),
                            "Twig": ("AXE", 0),
                            "Wood": ("AXE", 0),
                            "Stump": ("AXE", 0),  # May require upgraded axe
                            "Tree Stump": ("AXE", 0),  # Large stump variant
                            "Stone": ("PICKAXE", 3),
                            "Boulder": ("PICKAXE", 3),
                            "Large Rock": ("PICKAXE", 3),  # May require upgraded pick
                        }

                        if blocker in CLEARABLE_DEBRIS:
                            # Get blocker position for failure tracking
                            player = surroundings.get("player", {})
                            px, py = player.get("tileX", 0), player.get("tileY", 0)
                            loc_name = self.last_state.get("location", {}).get("name", "Farm") if self.last_state else "Farm"
                            # Calculate target tile based on direction
                            dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
                            target_x, target_y = px + dx, py + dy
                            blocker_key = (loc_name, target_x, target_y, blocker)

                            # Check if we've given up on this blocker
                            if blocker_key in self._skip_blockers:
                                logging.warning(f"⏭️ Skipping {blocker} at ({target_x},{target_y}) - gave up after {self._max_clear_attempts} attempts")
                                # Treat as non-clearable, fall through to skip logic below
                            else:
                                # Track attempt
                                attempts = self._clear_attempts.get(blocker_key, 0) + 1
                                self._clear_attempts[blocker_key] = attempts

                                if attempts > self._max_clear_attempts:
                                    # Too many failures - give up on this blocker
                                    self._skip_blockers.add(blocker_key)
                                    logging.warning(f"🚫 Giving up on {blocker} at ({target_x},{target_y}) after {attempts} failed attempts")
                                    self.recent_actions.append(f"GAVE_UP: {blocker} at ({target_x},{target_y}) - unclearable")
                                    self.recent_actions = self.recent_actions[-10:]
                                    # Record lesson about this obstacle
                                    if self.lesson_memory:
                                        self.lesson_memory.record_failure(
                                            attempted=f"clear {blocker}",
                                            blocked_by=f"{blocker} (requires upgraded tool)",
                                            position=(target_x, target_y),
                                            location=loc_name
                                        )
                                    # Fall through to non-clearable logic
                                else:
                                    tool_name, tool_slot = CLEARABLE_DEBRIS[blocker]
                                    logging.info(f"🧹 Proactive clear: {blocker} blocking {direction}, using {tool_name} (attempt {attempts}/{self._max_clear_attempts})")

                                    # Queue: select_slot → face → use_tool → retry original move
                                    clear_actions = [
                                        Action("select_slot", {"slot": tool_slot}, f"select {tool_name}"),
                                        Action("face", {"direction": direction}, f"face {direction}"),
                                        Action("use_tool", {}, f"clear {blocker}"),
                                        action,  # Retry the original move after clearing
                                    ]

                                    # If diagonal, also re-queue the second move
                                    if diagonal_second_dir:
                                        clear_actions.append(Action(
                                            "move",
                                            {"direction": diagonal_second_dir, "duration": 0.3},
                                            f"move {diagonal_second_dir} (diagonal)"
                                        ))
                                        # Remove the queued second move (we'll add it back after clearing)
                                        if self.action_queue and self.action_queue[0].params.get("direction") == diagonal_second_dir:
                                            self.action_queue.pop(0)

                                    # Insert clearing actions at front of queue
                                    self.action_queue = clear_actions + self.action_queue
                                    self.recent_actions.append(f"CLEARING: {blocker} to {direction} (attempt {attempts})")
                                    self.recent_actions = self.recent_actions[-10:]
                                    # Update validation status - blocked but auto-clearing
                                    self.validation_status = "blocked"
                                    self.validation_reason = f"{blocker} (auto-clearing, attempt {attempts})"
                                    self.executed_action = {"type": action.action_type, "params": action.params}
                                    self.executed_outcome = "blocked"
                                    self._send_ui_status()
                                    return  # Will execute select_slot next tick

                        # Non-clearable obstacle (or gave up) - just skip
                        logging.warning(f"⚠️ Skipping move {direction} - blocked by {blocker}")

                        # Record lesson for future VLM context
                        if self.lesson_memory:
                            pos = self.last_position or (0, 0)
                            loc = self.last_state.get("location", {}).get("name", "") if self.last_state else ""
                            self.lesson_memory.record_failure(
                                attempted=f"move {direction}",
                                blocked_by=blocker,
                                position=pos,
                                location=loc
                            )
                            logging.info(f"   📚 Lesson recorded: move {direction} blocked by {blocker}")

                        # If this was part of a diagonal, cancel the second move too
                        if diagonal_second_dir and self.action_queue:
                            next_action = self.action_queue[0]
                            if (next_action.action_type == "move" and
                                next_action.params.get("direction") == diagonal_second_dir):
                                self.action_queue.pop(0)
                                logging.warning(f"   ↳ Cancelling diagonal second move ({diagonal_second_dir})")

                        # Still record the ATTEMPTED action so VLM learns from failed attempts
                        self.recent_actions.append(f"BLOCKED: move {direction} (hit {blocker})")
                        self.recent_actions = self.recent_actions[-10:]
                        self.movement_attempts += 1
                        self.last_blocked_direction = f"{direction} ({blocker})"
                        # Update validation status - blocked, cannot clear
                        self.validation_status = "blocked"
                        self.validation_reason = blocker
                        self.executed_action = {"type": action.action_type, "params": action.params}
                        self.executed_outcome = "blocked"
                        self._send_ui_status()
                        return

            # Validation passed - action will be executed
            self.validation_status = "passed"
            self.validation_reason = None
            self.vlm_status = "Executing"
            if action.action_type == "move":
                self.movement_attempts += 1
            self.recent_actions.append(self._format_action(action))
            self.recent_actions = self.recent_actions[-10:]  # Keep last 10 for pattern detection

            # Check if this is a skill (multi-step action sequence)
            if self.is_skill(action.action_type):
                logging.info(f"🎯 Executing skill: {action.action_type} {action.params}")
                success = await self.execute_skill(action.action_type, action.params)
            else:
                logging.info(f"🎮 Executing: {action.action_type} {action.params}")
                success = self.controller.execute(action)

            self._record_action_event(action, success)
            # Update execution outcome for UI debug panel
            self.executed_action = {"type": action.action_type, "params": action.params}
            self.executed_outcome = "success" if success else "failed"
            
            # Report result to Task Executor if active
            if self.task_executor and self.task_executor.is_active():
                self.task_executor.report_result(success, error=None if success else "execution failed")
            
            await asyncio.sleep(self.config.action_delay)
            self._send_ui_status()
            return

        # ═══════════════════════════════════════════════════════════════════════
        # TASK EXECUTOR: Deterministic execution (skip VLM when task is active)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Try to start a task from daily planner if executor is idle
        if self.task_executor and not self.task_executor.is_active():
            if self._try_start_daily_task():
                # Task started - executor will handle it next iteration
                pass
        
        if self.task_executor and self.task_executor.is_active():
            # Get player position for navigation
            player_pos = self.last_position or (0, 0)
            
            # Get next deterministic action from executor
            executor_action = self.task_executor.get_next_action(player_pos)
            
            if executor_action:
                # Check if VLM should provide commentary this tick (hybrid mode)
                if self.task_executor.should_vlm_comment(self._vlm_commentary_interval):
                    logging.info(f"🎭 Hybrid mode: VLM commentary tick {self.task_executor.tick_count}")
                    # Don't skip VLM - let it provide commentary, but still queue executor action
                else:
                    # Queue the executor's action and skip VLM
                    action = Action(
                        action_type=executor_action.action_type,
                        params=executor_action.params,
                        description=executor_action.reason
                    )
                    self.action_queue.append(action)
                    logging.info(f"🎯 TaskExecutor: {executor_action.action_type} → {executor_action.reason}")
                    
                    # Update UI status
                    self.vlm_status = f"Executing task: {self.task_executor.progress.task_type if self.task_executor.progress else 'unknown'}"
                    self._send_ui_status()
                    return  # Skip VLM thinking this tick
            else:
                # Task complete - let VLM pick next task
                if self.task_executor.is_complete() and self.task_executor.progress:
                    task_id = self.task_executor.progress.task_id
                    task_type = self.task_executor.progress.task_type
                    completed = self.task_executor.progress.completed_targets
                    total = self.task_executor.progress.total_targets
                    logging.info(f"✅ Task complete: {task_type} ({completed}/{total} targets)")
                    
                    # Mark task complete in daily planner
                    if self.daily_planner:
                        try:
                            self.daily_planner.complete_task(task_id)
                            logging.info(f"📋 Daily planner: marked {task_id} complete")
                        except Exception as e:
                            logging.warning(f"Failed to mark task complete: {e}")

        # Time to think?
        if now - self.last_think_time >= self.config.think_interval:
            self.last_think_time = now

            self.vlm_status = "Thinking"
            self._send_ui_status()
            self._refresh_state_snapshot()

            # Capture screen (crop for splitscreen mode - Player 2 right half)
            crop = self.config.splitscreen_region if self.config.mode == "splitscreen" else None
            img = self.vlm.capture_screen(crop)

            # Save screenshot (with rotation - keep last 100)
            if self.config.save_screenshots:
                timestamp = datetime.now().strftime("%H%M%S")
                img.save(self.config.screenshot_dir / f"screen_{timestamp}.png")
                # Cleanup old screenshots every 50 saves
                if not hasattr(self, '_screenshot_count'):
                    self._screenshot_count = 0
                self._screenshot_count += 1
                if self._screenshot_count >= 50:
                    self._screenshot_count = 0
                    screenshots = sorted(self.config.screenshot_dir.glob("screen_*.png"))
                    if len(screenshots) > 100:
                        for old in screenshots[:-100]:
                            old.unlink()

            # Get spatial context from mod if available
            spatial_context = ""
            if hasattr(self.controller, 'format_surroundings'):
                spatial_context = self.controller.format_surroundings()
                if spatial_context:
                    lines = spatial_context.splitlines()
                    self.current_instruction = next(
                        (line.strip() for line in lines if line.strip().startswith(">>>")),
                        None
                    )
                    self.navigation_target = self._extract_navigation_target(self.current_instruction)
                    logging.info(f"   🧭 {spatial_context}")
                else:
                    self.current_instruction = None
                    self.navigation_target = None

            # Build action context with history and repetition warnings
            action_context_parts = []

            # Check for late-night urgency FIRST (overrides other goals)
            time_hint = self._get_time_urgency_hint(self.last_state)
            if time_hint:
                action_context_parts.append(time_hint)
                logging.info(f"   ⏰ Time urgency: hour >= 22, warning added")

            # Add task executor context (current task, progress, next target)
            task_context = self._get_task_executor_context()
            if task_context:
                action_context_parts.append(task_context)
                logging.info(f"   🎯 Task context added: {self.task_executor.progress.task_type if self.task_executor and self.task_executor.progress else 'none'}")

            # Add farm plan context if active
            if self.plot_manager and self.plot_manager.is_active() and self.last_position:
                farm_plan_context = self.plot_manager.get_prompt_context(
                    self.last_position[0], self.last_position[1]
                )
                if farm_plan_context:
                    action_context_parts.append(farm_plan_context)
                    logging.info("   📋 Farm plan context added")
                    # Also sync state from game
                    if self.last_surroundings and self.last_state:
                        self.plot_manager.update_from_game_state(
                            self.last_surroundings, self.last_state
                        )

            user_context = self._get_recent_user_messages()
            if user_context:
                action_context_parts.append(
                    f"USER MESSAGES (respond in reasoning):\n{user_context}"
                )
            spatial_hint = self._get_spatial_hint()
            if spatial_hint:
                action_context_parts.append(spatial_hint)
            skill_context = self._get_skill_context()
            if skill_context:
                action_context_parts.append(skill_context)
                logging.info(f"   📚 Skill context: {len(self.skill_context.get_available_skills(self.last_state) if self.skill_context and self.last_state else [])} available")
            if self.recent_actions:
                action_history = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(self.recent_actions))
                # Detect repetition - warn if same action 3+ times in last 5
                recent_5 = self.recent_actions[-5:]
                repeat_count = 0
                last_action = ""
                if recent_5:
                    last_action = recent_5[-1]
                    repeat_count = sum(1 for a in recent_5 if a == last_action)

                if repeat_count >= 3:
                    # VERY PROMINENT warning - tell VLM to USE VISION
                    warning = f"🚨 STOP! You're STUCK! 🚨\nYou've done '{last_action}' {repeat_count} TIMES and it's not working!\n\n"

                    # Check if stuck indoors - suggest warp
                    current_location = ""
                    if self.last_state:
                        location_data = self.last_state.get("location", {})
                        current_location = location_data.get("name", "") or ""

                    if current_location in ["FarmHouse", "SeedShop", "Saloon", "JojaMart", "Blacksmith"]:
                        warning += "🚪 STUCK INSIDE? Just use WARP to teleport outside!\n"
                        warning += '→ {"type": "warp", "location": "Farm"}\n\n'
                        warning += "Don't waste time finding the door - WARP is instant!\n\n"
                    else:
                        # Check for debris blocking adjacent tiles
                        debris_hint = self._get_adjacent_debris_hint(self.last_state)
                        if debris_hint:
                            warning += debris_hint + "\n\n"
                        else:
                            warning += "👁️ LOOK AT THE SCREENSHOT! There's probably an obstacle blocking you.\n"
                            warning += "USE YOUR EYES to find a path around it:\n"
                            warning += "- See a TREE or ROCK blocking? Move sideways first to go AROUND it\n"
                            warning += "- Can't go south? Try going WEST or EAST first, THEN south\n"
                            warning += "- Still stuck? Try a completely different route\n\n"
                    action_context_parts.append(warning)

                action_context_parts.append(f"YOUR RECENT ACTIONS (oldest→newest):\n{action_history}")
                logging.info(f"   📜 Action history: {len(self.recent_actions)} actions tracked")
                if repeat_count >= 3:
                    logging.warning(f"   ⚠️  REPETITION DETECTED: '{last_action}' done {repeat_count}x in last 5")

            action_context = "\n\n".join(action_context_parts)

            # Get memory context (NPC knowledge + past experiences)
            memory_context = ""
            if HAS_MEMORY and get_context_for_vlm:
                try:
                    # Extract nearby NPCs from game state if available
                    nearby_npcs = []
                    game_day = ""
                    if self.last_state:
                        loc_data = self.last_state.get("location", {})
                        nearby_npcs = [npc.get("name", "") for npc in loc_data.get("npcs", [])]
                        time_data = self.last_state.get("time", {})
                        game_day = f"{time_data.get('season', '')} {time_data.get('day', '')} Y{time_data.get('year', 1)}"

                    memory_context = get_context_for_vlm(
                        location=self.last_state.get("location", {}).get("name", "") if self.last_state else "",
                        nearby_npcs=nearby_npcs,
                        current_goal=self.goal,
                        game_day=game_day
                    )
                    if memory_context:
                        logging.info(f"   🧠 Memory: {len(memory_context)} chars context loaded")
                except Exception as e:
                    logging.debug(f"Memory context failed: {e}")

            # Think! (unified perception + planning)
            # Branch: vision-first mode uses minimal prompt, image drives decisions
            if self.config.vision_first_enabled:
                logging.info("👁️ Vision-First Thinking...")
                light_context = self._build_light_context()
                if "--- HINTS ---" in light_context:
                    logging.debug(f"   📝 Light context hints: {light_context.split('--- HINTS ---')[1][:100]}...")
                lessons = self.lesson_memory.get_context() if self.lesson_memory else ""
                result = self.vlm.think_vision_first(
                    img, self.goal, light_context=light_context, lessons=lessons
                )
                # Log vision-first specific output
                if result.observation:
                    logging.info(f"   👁️ Sees: {result.observation[:100]}{'...' if len(result.observation) > 100 else ''}")
            else:
                logging.info("🧠 Thinking...")
                result = self.vlm.think(img, self.goal, spatial_context=spatial_context, memory_context=memory_context, action_context=action_context)

            self.think_count += 1
            if result.latency_ms:
                self.latency_history.append(result.latency_ms)
                self.latency_history = self.latency_history[-60:]
            self._track_vlm_parse(result)

            # Update VLM debug state for UI panel
            self.vlm_observation = result.observation if result.observation else (result.reasoning[:200] if result.reasoning else None)
            if result.actions:
                first_action = result.actions[0]
                self.proposed_action = {"type": first_action.action_type, "params": first_action.params}
            else:
                self.proposed_action = None
            # Reset validation/execution for new thinking cycle
            self.validation_status = None
            self.validation_reason = None
            self.executed_action = None
            self.executed_outcome = None

            # Override VLM's tool perception with actual game state (VLM often hallucinates tools)
            if self.last_state:
                actual_tool = self.last_state.get("player", {}).get("currentTool")
                if actual_tool:
                    result.holding = actual_tool

            # Log perception with personality
            energy_emoji = {"full": "💪", "good": "👍", "half": "😐", "low": "😓", "exhausted": "💀"}.get(result.energy, "❓")
            weather_emoji = {"sunny": "☀️", "rainy": "🌧️", "stormy": "⛈️", "snowy": "❄️"}.get(result.weather, "")

            logging.info(f"   📍 {result.location} @ {result.time_of_day} {weather_emoji}")
            logging.info(f"   {energy_emoji} Energy: {result.energy} | Holding: {result.holding or 'nothing'}")
            if result.mood:
                logging.info(f"   🎭 {result.mood}")
            logging.info(f"   💭 {result.reasoning[:100]}{'...' if len(result.reasoning) > 100 else ''}")
            logging.info(f"   ⏱️  {result.latency_ms:.0f}ms")

            # Check memory triggers (new location, NPC met, notable event)
            self._check_memory_triggers(result, game_day=game_day)

            if self.config.mode in ("single", "splitscreen") and result.actions:
                self.vlm_status = "Executing"
            else:
                self.vlm_status = "Idle"

            self._send_ui_status(result)
            self._send_ui_message(result)

            if self.awaiting_user_reply and result.parse_success:
                reply_text = (result.reasoning or "").strip()
                if reply_text and not reply_text.lower().startswith("could not parse json"):
                    self._ui_safe(self.ui.send_message, "agent", reply_text)
                self.awaiting_user_reply = False

            # Queue actions (with post-processing filters)
            if self.config.mode in ("single", "splitscreen"):
                # Apply action overrides in sequence
                filtered_actions = result.actions
                filtered_actions = self._fix_active_popup(filtered_actions)  # Popup/menu dismiss first
                filtered_actions = self._fix_late_night_bed(filtered_actions)  # Midnight override
                filtered_actions = self._fix_priority_shipping(filtered_actions)  # Shipping priority
                filtered_actions = self._fix_no_seeds(filtered_actions)  # No seeds → go to Pierre's
                filtered_actions = self._fix_edge_stuck(filtered_actions)  # Edge-stuck → retreat
                filtered_actions = self._fix_empty_watering_can(filtered_actions)  # Empty can override
                filtered_actions = self._filter_adjacent_crop_moves(filtered_actions)  # Adjacent move filter
                self.action_queue = filtered_actions
                for i, a in enumerate(self.action_queue):
                    logging.info(f"   [{i+1}] {a.action_type}: {a.params}")
            else:
                # Helper mode: just log advice, don't execute
                logging.info("   💡 ADVICE (not executing):")
                for a in result.actions:
                    logging.info(f"      - {a.action_type}: {a.description or a.params}")
        elif self.vlm_status != "Idle":
            self.vlm_status = "Idle"
            self._send_ui_status()

    def stop(self):
        """Stop the agent."""
        self.running = False


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="StardewAI Unified Agent")
    parser.add_argument("--config", "-c", default="./config/settings.yaml",
                        help="Path to config file")
    parser.add_argument("--goal", "-g", default="",
                        help="Goal for the agent")
    parser.add_argument("--mode", "-m", choices=["single", "splitscreen", "helper"],
                        help="Override mode: single (full screen), splitscreen (Player 2), helper (advisory)")
    parser.add_argument("--observe", "-o", action="store_true",
                        help="Observe only (disable controller)")
    parser.add_argument("--ui", action="store_true",
                        help="Enable UI updates")
    parser.add_argument("--ui-url", default=None,
                        help="UI base URL (default http://localhost:9001)")
    parser.add_argument("--plot", type=str, default=None,
                        help="Define farm plot: 'x,y,width,height' e.g., '30,20,5,3'")
    parser.add_argument("--clear-plan", action="store_true",
                        help="Clear existing farm plan")
    args = parser.parse_args()

    # Load config
    config = Config.from_yaml(args.config)

    # Override mode if specified
    if args.mode:
        config.mode = args.mode

    # Observe mode
    if args.observe:
        global HAS_GAMEPAD
        HAS_GAMEPAD = False

    if args.ui:
        config.ui_enabled = True
    if args.ui_url:
        config.ui_url = args.ui_url

    agent = StardewAgent(config)

    # Handle farm planning arguments
    if args.clear_plan and agent.plot_manager:
        agent.plot_manager.clear_plan()
        print("🗑️  Farm plan cleared")

    if args.plot and agent.plot_manager:
        try:
            parts = [int(p.strip()) for p in args.plot.split(",")]
            if len(parts) == 4:
                x, y, w, h = parts
                if not agent.plot_manager.farm_plan:
                    agent.plot_manager.create_plan("Farm")
                plot = agent.plot_manager.define_plot(x, y, w, h)
                print(f"📋 Created farm plot: {plot.id} ({w}x{h}) at ({x},{y})")
            else:
                print("⚠️  Invalid --plot format. Use: x,y,width,height")
        except ValueError as e:
            print(f"⚠️  Invalid --plot values: {e}")

    print("\n" + "=" * 60)
    print("   🎮 StardewAI - Unified VLM Agent")
    print("=" * 60)
    print(f"   Mode: {config.mode.upper()}")
    print(f"   Model: {config.model}")
    print(f"   Server: {config.server_url}")
    print(f"   Goal: {args.goal or 'Explore and help'}")
    if config.mode == "splitscreen":
        print(f"   Screen: Right half (Player 2)")
        print(f"   Input: SMAPI Mod API")
    elif config.mode == "single":
        print(f"   Screen: Full screen")
        print(f"   Input: SMAPI Mod API")
    else:
        print(f"   Screen: Full screen")
        print(f"   Input: Advisory only (no control)")
    print("   Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    asyncio.run(agent.run(goal=args.goal))


if __name__ == "__main__":
    main()
