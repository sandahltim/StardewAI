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

# Session 120: Unified SMAPI client for complete game data access
from smapi_client import SMAPIClient, get_client as get_smapi_client

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
    from execution import TaskExecutor, SortStrategy, TaskState
    HAS_TASK_EXECUTOR = True
except ImportError:
    TaskExecutor = None
    SortStrategy = None
    HAS_TASK_EXECUTOR = False

try:
    from constants import TOOL_SLOTS, DEFAULT_LOCATIONS
    HAS_CONSTANTS = True
except ImportError:
    TOOL_SLOTS = {"Axe": 0, "Hoe": 1, "Watering Can": 2, "Pickaxe": 3, "Scythe": 4}
    DEFAULT_LOCATIONS = {"shipping_bin": (71, 14), "water_pond": (72, 31)}
    HAS_CONSTANTS = False

try:
    from commentary import AsyncCommentaryWorker, INNER_MONOLOGUE_PROMPT, ELIAS_CHARACTER
    HAS_COMMENTARY = True
except ImportError:
    AsyncCommentaryWorker = None
    INNER_MONOLOGUE_PROMPT = ""
    ELIAS_CHARACTER = ""
    HAS_COMMENTARY = False

try:
    from planning import PlotManager
    HAS_PLANNING = True
except ImportError:
    PlotManager = None
    HAS_PLANNING = False

try:
    from planning.crop_advisor import get_recommended_crop
    HAS_CROP_ADVISOR = True
except ImportError:
    get_recommended_crop = None
    HAS_CROP_ADVISOR = False

# Cell-by-cell farming (Session 62+)
try:
    from planning.farm_surveyor import FarmSurveyor, CellFarmingPlan, get_farm_surveyor
    from execution.cell_coordinator import CellFarmingCoordinator, CellAction
    from execution.inventory_manager import InventoryManager
    HAS_CELL_FARMING = True
except ImportError:
    FarmSurveyor = None
    CellFarmingPlan = None
    CellFarmingCoordinator = None
    CellAction = None
    get_farm_surveyor = None
    InventoryManager = None
    HAS_CELL_FARMING = False

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
# Tool-Aware Obstacle System (centralized module)
# =============================================================================
try:
    from planning.obstacle_manager import (
        can_clear_obstacle,
        get_tool_level,
        should_path_around,
        classify_blocker,
        get_blocking_info,
        get_upgrade_tracker,
        OBSTACLE_REQUIREMENTS,
        IMPASSABLE_OBSTACLES,
        BASIC_CLEARABLE,
    )
    HAS_OBSTACLE_MANAGER = True
except ImportError:
    HAS_OBSTACLE_MANAGER = False
    # Fallback stubs if module not available
    def can_clear_obstacle(inv, obs): return (False, "module not loaded", None)
    def get_tool_level(inv, tool): return -1
    def should_path_around(blocker, inv, allow_slow=False): return True
    def classify_blocker(blocker, inv): return "unknown"
    def get_blocking_info(blocker, inv): return {"blocker": blocker, "can_clear": False}
    def get_upgrade_tracker(): return None
    OBSTACLE_REQUIREMENTS = {}
    IMPASSABLE_OBSTACLES = set()
    BASIC_CLEARABLE = set()


# =============================================================================
# Helper Functions
# =============================================================================

def get_recommended_seed_skill(state: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    """Get dynamically recommended seed purchase skill based on crop advisor.
    
    Returns:
        Tuple of (skill_name, reason) e.g. ("buy_kale_seeds", "Kale (6.67g/day profit)")
        Falls back to buy_parsnip_seeds if no recommendation available.
    """
    if not HAS_CROP_ADVISOR or not get_recommended_crop:
        return ("buy_parsnip_seeds", "Parsnip (fallback - no crop advisor)")
    
    if not state:
        return ("buy_parsnip_seeds", "Parsnip (fallback - no state)")
    
    time_data = state.get("time", {})
    season = time_data.get("season", "spring")
    day = time_data.get("day", 1)
    money = state.get("player", {}).get("money", 0)
    
    try:
        rec = get_recommended_crop(season, day, money)
        if rec:
            # Convert crop name to skill: "Kale" -> "buy_kale_seeds"
            skill_name = f"buy_{rec.name.lower()}_seeds"
            reason = f"{rec.name} ({rec.profit_per_day:.2f}g/day profit)"
            return (skill_name, reason)
    except Exception as e:
        logging.warning(f"Crop advisor error: {e}")
    
    return ("buy_parsnip_seeds", "Parsnip (fallback)")


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

                # Build system prompt: Character (from Python) + Game Mechanics (from YAML)
                # This separates WHO Elias is from HOW the game works
                game_mechanics = data['model'].get('game_mechanics', '')
                if ELIAS_CHARACTER and game_mechanics:
                    config.system_prompt = f"{ELIAS_CHARACTER}\n\n{game_mechanics}"
                elif ELIAS_CHARACTER:
                    config.system_prompt = ELIAS_CHARACTER
                elif game_mechanics:
                    config.system_prompt = game_mechanics
                else:
                    # Fallback to old system_prompt if neither available
                    config.system_prompt = data['model'].get('system_prompt', config.system_prompt)

            # Vision-First Mode
            if 'vision_first' in data:
                vf = data['vision_first']
                config.vision_first_enabled = vf.get('enabled', False)
                config.vision_first_context_template = vf.get('light_context_template', '')

                # Vision-first also combines character + mechanics
                vf_mechanics = vf.get('game_mechanics', '')
                if ELIAS_CHARACTER and vf_mechanics:
                    config.vision_first_system_prompt = f"{ELIAS_CHARACTER}\n\n{vf_mechanics}"
                elif ELIAS_CHARACTER:
                    config.vision_first_system_prompt = ELIAS_CHARACTER
                elif vf_mechanics:
                    config.vision_first_system_prompt = vf_mechanics
                else:
                    # Fallback to old system_prompt if neither available
                    config.vision_first_system_prompt = vf.get('system_prompt', '')

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
                {"role": "system", "content": "You are Elias, an AI farmer in Stardew Valley. Think carefully and respond concisely."},
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
            
            # Inner monologue for streaming narration (stored in mood field)
            inner = data.get("inner_monologue", "")
            if inner:
                result.mood = inner
                logging.info(f"🧠 Inner monologue: {inner[:60]}...")

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
    """Controller that uses SMAPI mod HTTP API for precise game control.
    
    Session 120: Now uses unified SMAPIClient for complete game data access.
    All endpoints are available: /state, /farm, /npcs, /animals, /machines, etc.
    """

    def __init__(self, base_url: str = "http://localhost:8790"):
        self.base_url = base_url
        self.enabled = True
        # Session 120: Unified SMAPI client for all game data
        self.smapi = SMAPIClient(base_url)
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

    def get_farm(self) -> Optional[Dict[str, Any]]:
        """Get Farm state regardless of current location - for morning planning."""
        try:
            resp = httpx.get(f"{self.base_url}/farm", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            logging.debug(f"Failed to get farm state: {e}")
        return None

    def get_tillable_area(self, center_x: int, center_y: int, radius: int = 10) -> Optional[set]:
        """Get set of tillable positions around a center point.
        
        Uses the SMAPI /tillable-area endpoint which checks both:
        - Tile has "Diggable" map property (farmland, not lawn/paths/buildings)
        - Tile is passable (not blocked by objects/buildings)
        
        Returns:
            Set of (x, y) tuples that can be tilled, or None if endpoint unavailable.
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/tillable-area",
                params={"centerX": center_x, "centerY": center_y, "radius": radius},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                if data.get("success") == False:  # Endpoint exists but failed
                    logging.warning(f"Tillable area query failed: {data.get('error')}")
                    return None
                tillable = set()
                for tile in data.get("tiles", []):
                    if tile.get("canTill", False):
                        tillable.add((tile.get("x"), tile.get("y")))
                logging.info(f"🌱 Tillable area: {len(tillable)} tiles in radius {radius} around ({center_x},{center_y})")
                return tillable
            else:
                # Endpoint not found (older mod version)
                logging.warning(f"Tillable area endpoint returned {resp.status_code} - update SMAPI mod")
                return None
        except Exception as e:
            logging.warning(f"Failed to get tillable area: {e}")
            return None

    # =========================================================================
    # Session 120: Complete SMAPI endpoint access via unified client
    # =========================================================================

    def get_skills(self) -> Optional[Dict[str, Any]]:
        """Get player skill levels (farming, mining, fishing, etc.)."""
        skills = self.smapi.get_skills()
        if skills:
            return {
                "farming": {"level": skills.farming.level, "xp": skills.farming.xp},
                "mining": {"level": skills.mining.level, "xp": skills.mining.xp},
                "fishing": {"level": skills.fishing.level, "xp": skills.fishing.xp},
                "foraging": {"level": skills.foraging.level, "xp": skills.foraging.xp},
                "combat": {"level": skills.combat.level, "xp": skills.combat.xp},
            }
        return None

    def get_npcs(self) -> Optional[List[Dict[str, Any]]]:
        """Get all NPCs with location, friendship, birthday info."""
        npcs = self.smapi.get_npcs()
        if npcs:
            return [
                {
                    "name": n.name,
                    "location": n.location,
                    "tileX": n.tile_x,
                    "tileY": n.tile_y,
                    "friendship": n.friendship_hearts,
                    "isBirthdayToday": n.is_birthday_today,
                    "giftedToday": n.gifted_today,
                }
                for n in npcs.npcs
            ]
        return None

    def get_animals(self) -> Optional[Dict[str, Any]]:
        """Get farm animals and buildings."""
        animals = self.smapi.get_animals()
        if animals:
            return {
                "animals": [
                    {
                        "name": a.name,
                        "type": a.type,
                        "happiness": a.happiness,
                        "wasPetToday": a.was_pet_today,
                        "producedToday": a.produced_today,
                    }
                    for a in animals.animals
                ],
                "buildings": [
                    {
                        "type": b.type,
                        "animalCount": b.animal_count,
                        "maxAnimals": b.max_animals,
                        "doorOpen": b.door_open,
                    }
                    for b in animals.buildings
                ],
            }
        return None

    def get_machines(self) -> Optional[List[Dict[str, Any]]]:
        """Get all processing machines with status."""
        machines = self.smapi.get_machines()
        if machines:
            return [
                {
                    "name": m.name,
                    "location": m.location,
                    "tileX": m.tile_x,
                    "tileY": m.tile_y,
                    "isProcessing": m.is_processing,
                    "readyForHarvest": m.ready_for_harvest,
                    "needsInput": m.needs_input,
                    "minutesUntilReady": m.minutes_until_ready,
                }
                for m in machines.machines
            ]
        return None

    def get_calendar(self) -> Optional[Dict[str, Any]]:
        """Get calendar with events and birthdays."""
        cal = self.smapi.get_calendar()
        if cal:
            return {
                "season": cal.season,
                "day": cal.day,
                "year": cal.year,
                "dayOfWeek": cal.day_of_week,
                "daysUntilSeasonEnd": cal.days_until_season_end,
                "todayEvent": cal.today_event,
                "upcomingEvents": [
                    {"day": e.day, "name": e.name, "type": e.type}
                    for e in cal.upcoming_events
                ],
                "upcomingBirthdays": [
                    {"day": b.day, "name": b.name}
                    for b in cal.upcoming_birthdays
                ],
            }
        return None

    def get_fishing(self) -> Optional[Dict[str, Any]]:
        """Get fishing info for current location."""
        fishing = self.smapi.get_fishing()
        if fishing:
            return {
                "location": fishing.location,
                "weather": fishing.weather,
                "availableFish": [
                    {"name": f.name, "difficulty": f.difficulty, "basePrice": f.base_price}
                    for f in fishing.available_fish
                ],
            }
        return None

    def get_mining(self) -> Optional[Dict[str, Any]]:
        """Get mine floor info."""
        mining = self.smapi.get_mining()
        if mining:
            return {
                "location": mining.location,
                "floor": mining.floor,
                "floorType": mining.floor_type,
                "ladderFound": mining.ladder_found,
                "rocks": [
                    {"x": r.tile_x, "y": r.tile_y, "type": r.type}
                    for r in mining.rocks
                ],
                "monsters": [
                    {"name": m.name, "x": m.tile_x, "y": m.tile_y, "health": m.health}
                    for m in mining.monsters
                ],
            }
        return None

    def get_storage(self) -> Optional[Dict[str, Any]]:
        """Get all storage containers."""
        storage = self.smapi.get_storage()
        if storage:
            return {
                "chests": [
                    {"location": c.location, "x": c.tile_x, "y": c.tile_y, "items": len(c.items)}
                    for c in storage.chests
                ],
                "siloHay": storage.silo_hay,
                "siloCapacity": storage.silo_capacity,
            }
        return None

    def get_world_state(self) -> Optional[Dict[str, Any]]:
        """Get COMPLETE world state - all endpoints combined.
        
        Use this when planning needs full game context.
        """
        world = self.smapi.get_world_state()
        if not world:
            return None
        
        return {
            "player": {
                "name": world.game.player.name,
                "tileX": world.game.player.tile_x,
                "tileY": world.game.player.tile_y,
                "energy": world.game.player.energy,
                "maxEnergy": world.game.player.max_energy,
                "money": world.game.player.money,
                "wateringCanWater": world.game.player.watering_can_water,
            },
            "time": {
                "hour": world.game.time.hour,
                "season": world.game.time.season,
                "day": world.game.time.day,
                "weather": world.game.time.weather,
            },
            "location": world.game.location.name,
            "farmCrops": len(world.farm.crops) if world.farm else 0,
            "farmCropsUnwatered": len([c for c in world.farm.crops if not c.is_watered]) if world.farm else 0,
            "farmCropsReady": len([c for c in world.farm.crops if c.is_ready_for_harvest]) if world.farm else 0,
            "npcsCount": len(world.npcs.npcs) if world.npcs else 0,
            "birthdaysToday": [n.name for n in world.npcs.npcs if n.is_birthday_today] if world.npcs else [],
            "animalsCount": len(world.animals.animals) if world.animals else 0,
            "machinesReady": len([m for m in world.machines.machines if m.ready_for_harvest]) if world.machines else 0,
            "daysUntilSeasonEnd": world.calendar.days_until_season_end if world.calendar else 0,
        }

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

        # Tool slot mapping for switch instructions (from constants)
        tool_slots = TOOL_SLOTS

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
            # BUT: Skip this hint if we're at a shop/building for a task (buying seeds, etc.)
            water_left = state.get("player", {}).get("wateringCanWater", 0) if state else 0
            unwatered_crops = [c for c in crops if not c.get("isWatered", False)]
            current_location = state.get("location", {}).get("name", "") if state else ""
            task_locations = ["SeedShop", "Blacksmith", "FishShop", "Hospital", "JojaMart", "Saloon"]
            at_task_location = current_location in task_locations

            if water_left <= 0 and unwatered_crops and not at_task_location:
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
                        front_info = f">>> ⚠️ AT WATER! Use refill_watering_can with target_direction={water_adjacent} <<<"
                else:
                    nearest_water = data.get("nearestWater")
                    if nearest_water:
                        water_dir = normalize_direction(nearest_water.get("direction", "nearby"))
                        water_dist = nearest_water.get("distance", "?")
                        front_info = f">>> ⚠️ WATERING CAN EMPTY! DO: go_refill_watering_can (water is {water_dist} tiles {water_dir}) <<<"
                    else:
                        front_info = ">>> ⚠️ WATERING CAN EMPTY! DO: go_refill_watering_can <<<"
            elif at_task_location:
                # At a shop/building - give location-specific guidance
                money = state.get("player", {}).get("money", 0) if state else 0
                inventory = state.get("inventory", []) if state else []
                has_seeds = any(i and "seed" in i.get("name", "").lower() for i in inventory)
                if current_location == "SeedShop":
                    if not has_seeds and money >= 20:
                        seed_skill, seed_reason = get_recommended_seed_skill(state)
                        front_info = f">>> 🛒 AT PIERRE'S! DO: {seed_skill} - {seed_reason} (have {money}g) <<<"
                    elif has_seeds:
                        front_info = ">>> 🛒 AT PIERRE'S with seeds! DO: warp_to_farm to plant <<<"
                    else:
                        front_info = f">>> 🛒 AT PIERRE'S but only {money}g - need more money for seeds <<<"
                elif current_location == "Blacksmith":
                    front_info = ">>> 🔨 AT BLACKSMITH! Check tool upgrades or break geodes <<<"
                else:
                    front_info = f">>> 📍 At {current_location} - complete your task here <<<"
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
                    front_info = f">>> ⚠️ CROP HERE! DO NOT use {current_tool}! Use water_crop skill! <<<"
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
                            front_info = f">>> WATERING CAN EMPTY! DO: go_refill_watering_can (water is {water_dist} tiles {water_dir}) <<<"
                        else:
                            front_info = ">>> WATERING CAN EMPTY! DO: go_refill_watering_can <<<"
                    elif "Watering" in current_tool:
                        front_info = f">>> TILE: PLANTED - You have {current_tool} ({water_left}/{water_max}), use_tool to WATER! <<<"
                    else:
                        front_info = f">>> TILE: PLANTED - Use water_crop skill! (can: {water_left}/{water_max}) <<<"
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
                # Priority: 1) Harvest ready crops, 2) Water unwatered crops, 3) Till/plant
                crops = state.get("location", {}).get("crops", []) if state else []
                player_x = state.get("player", {}).get("tileX", 0) if state else 0
                player_y = state.get("player", {}).get("tileY", 0) if state else 0

                # HARVEST FIRST - check for ready-to-harvest crops
                harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
                if harvestable:
                    nearest = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                    dx = nearest["x"] - player_x
                    dy = nearest["y"] - player_y
                    adj_hint = self._calc_adjacent_hint(dx, dy, action="harvest")
                    front_info = f">>> 🌾 {len(harvestable)} CROPS READY TO HARVEST! {adj_hint} <<<"
                else:
                    # No harvestable - check for unwatered crops
                    unwatered = [c for c in crops if not c.get("isWatered", False)]
                    if unwatered:
                        nearest = min(unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        dx = nearest["x"] - player_x
                        dy = nearest["y"] - player_y
                        adj_hint = self._calc_adjacent_hint(dx, dy, action="water")
                        front_info = f">>> {len(unwatered)} CROPS NEED WATERING! {adj_hint} <<<"
                    else:
                        # No unwatered crops - check if we have seeds before suggesting tilling
                        inventory = state.get("inventory", []) if state else []
                        has_seeds = any(item and "seed" in item.get("name", "").lower() for item in inventory)
                        if has_seeds:
                            if "Hoe" in current_tool:
                                front_info = f">>> TILE: CLEAR DIRT - You have {current_tool}, use_tool to TILL! <<<"
                            else:
                                front_info = ">>> TILE: CLEAR DIRT - Use till_soil skill to prepare for planting! <<<"
                        else:
                            # No seeds - use done farming hint (will suggest shipping/clearing)
                            front_info = self._get_done_farming_hint(state, data)
            elif tile_state == "clear" or tile_state == "blocked":
                # Priority: 1) Harvest ready crops, 2) Water unwatered crops, 3) Done farming
                crops = state.get("location", {}).get("crops", []) if state else []
                player_x = state.get("player", {}).get("tileX", 0) if state else 0
                player_y = state.get("player", {}).get("tileY", 0) if state else 0

                # HARVEST FIRST - check for ready-to-harvest crops
                harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
                if harvestable:
                    nearest = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                    dx = nearest["x"] - player_x
                    dy = nearest["y"] - player_y
                    adj_hint = self._calc_adjacent_hint(dx, dy, action="harvest")
                    front_info = f">>> 🌾 {len(harvestable)} CROPS READY TO HARVEST! {adj_hint} <<<"
                else:
                    # No harvestable - check for unwatered crops
                    unwatered = [c for c in crops if not c.get("isWatered", False)]
                    if unwatered:
                        nearest = min(unwatered, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        dx = nearest["x"] - player_x
                        dy = nearest["y"] - player_y
                        adj_hint = self._calc_adjacent_hint(dx, dy, action="water")
                        front_info = f">>> TILE: NOT FARMABLE - {len(unwatered)} CROPS! {adj_hint} <<<"
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
            bed_x, bed_y = 9, 9  # Bed is 1 tile west of warp point (10,9)
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

        # Session 124: Location awareness - don't give farm hints outside Farm
        location = state.get("location", {}).get("name", "") if state else ""
        if "Mine" in location:
            # In mines - give mining hint, not farming hint
            return ">>> ⛏️ IN MINES! Break rocks to find ladder. Use Pickaxe on rocks. <<<"
        if location and location != "Farm":
            # Not on farm - no farming hints (let other systems handle)
            return ""

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
            seed_skill, seed_reason = get_recommended_seed_skill(state)
            return f">>> 🌱 NO SEEDS! Go to Pierre's! DO: go_to_pierre, then {seed_skill} - {seed_reason} (you have {money}g) <<<"

        # Check for nearby debris in surroundings
        nearby_debris = []
        if surroundings:
            for direction, info in normalize_directions_map(surroundings.get("directions", {})).items():
                blocker = info.get("blocker", "")
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
            # Map debris to clear skill
            skill = "clear_weeds" if debris_type in ["Weeds", "Grass"] else "clear_stone" if debris_type in ["Stone", "Boulder"] else "clear_wood"
            if dist == 1:
                return f">>> ✅ WATERING DONE! CLEAR DEBRIS: {debris_type} {direction.upper()}. Use {skill} with target_direction={direction} <<<"
            else:
                return f">>> ✅ WATERING DONE! CLEAR DEBRIS: {debris_type} {dist} tiles {direction.upper()}. Move closer, then use {skill} <<<"

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
            # Map debris to clear skill
            skill = "clear_weeds" if debris_name == "Weeds" else "clear_stone" if debris_name == "Stone" else "clear_wood"
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
            return f">>> ✅ WATERING DONE! CLEAR DEBRIS: {debris_name} {direction_str}. Move there, then use {skill} <<<"

        # Session 124: Time-aware hints - don't suggest bed at 9:50 AM!
        # Check for pending mining task before suggesting bed
        if self.daily_planner:
            pending = [t for t in self.daily_planner.tasks if t.status == "pending"]
            mining_task = next((t for t in pending if t.category == "mining"), None)
            if mining_task and hour < 16:
                return ">>> ⛏️ FARM DONE! GO MINING! Use skill: warp_to_mine <<<"

        # Only suggest bed if it's actually late or low energy
        if hour >= 18 or energy_pct <= 40:
            return ">>> ✅ ALL FARMING DONE! Use action 'go_to_bed' to end day. <<<"

        # Daytime with nothing to do - suggest exploring
        return ">>> ✅ FARM CHORES DONE! Explore, forage, fish, or visit town. <<<"

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

            elif action_type == "move_to":
                # Direct pathfinding to coordinates - SMAPI handles A* navigation
                # Must poll for completion since movement takes multiple game ticks
                x = action.params.get("x")
                y = action.params.get("y")
                if x is None or y is None:
                    logging.error("move_to requires x and y coordinates")
                    return False

                # Send the move command - check data.success for path failures
                try:
                    resp = httpx.post(
                        f"{self.base_url}/action",
                        json={"action": "move_to", "target": {"x": x, "y": y}},
                        timeout=5
                    )
                    if resp.status_code != 200:
                        logging.warning(f"move_to HTTP error: {resp.status_code}")
                        return False
                    result = resp.json()
                    data = result.get("data", {})
                    if not data.get("success", False):
                        error = data.get("error", "Unknown error")
                        logging.warning(f"move_to failed: {error}")
                        return False  # No path found - don't poll
                except Exception as e:
                    logging.error(f"move_to request failed: {e}")
                    return False

                # Poll for arrival (max 10 seconds, check every 200ms)
                max_polls = 50
                for i in range(max_polls):
                    time.sleep(0.2)
                    state = self.get_state()
                    if state:
                        player = state.get("player", {})
                        # Use tileX/tileY directly (not position.x/64)
                        px = player.get("tileX", 0)
                        py = player.get("tileY", 0)
                        # Check if arrived (within 1 tile)
                        if abs(px - x) <= 1 and abs(py - y) <= 1:
                            logging.debug(f"move_to arrived at ({px}, {py})")
                            return True
                    if i > 0 and i % 10 == 0:
                        logging.debug(f"move_to polling... {i}/{max_polls}")

                logging.warning(f"move_to timeout - may not have reached ({x}, {y})")
                return True  # Return true anyway - let task executor handle stuck detection

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

            elif action_type == "select_item_type":
                # Accept "value", "type", or "item_type" as param key
                item_type = action.params.get("value", action.params.get("type", action.params.get("item_type", "")))
                if not item_type:
                    logging.error(f"select_item_type: no item type specified in params: {action.params}")
                    return False
                return self._send_action({
                    "action": "select_item_type",
                    "itemType": item_type
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
                
                # Dynamic quantity: "max" or "auto" calculates based on money
                if quantity in ("max", "auto"):
                    # Seed prices (lowercase item name -> price)
                    seed_prices = {
                        "parsnip seeds": 20, "cauliflower seeds": 80,
                        "potato seeds": 50, "kale seeds": 70, "garlic seeds": 40,
                        "bean starter": 60, "melon seeds": 80, "tomato seeds": 50,
                        "blueberry seeds": 80, "pepper seeds": 40, "radish seeds": 40,
                        "pumpkin seeds": 100, "cranberry seeds": 240, "grape starter": 60,
                        "wheat seeds": 10, "corn seeds": 150,
                    }
                    price = seed_prices.get(item.lower(), 50)  # Default 50g if unknown
                    money = self.get_state().get("player", {}).get("money", 0) if self.get_state() else 0
                    # Calculate max affordable, cap at 20 to leave money for other things
                    max_qty = min(money // price, 20) if price > 0 else 1
                    quantity = max(1, max_qty)  # At least 1
                    logging.info(f"💰 Buy {item}: {money}g / {price}g = {quantity} seeds")
                
                return self._send_action({
                    "action": "buy",
                    "item": item,
                    "quantity": quantity
                })
            elif action_type == "buy_backpack":
                return self._send_action({"action": "buy_backpack"})

            elif action_type == "upgrade_tool":
                tool = action.params.get("tool", "")
                return self._send_action({
                    "action": "upgrade_tool",
                    "tool": tool
                })

            elif action_type == "collect_upgraded_tool":
                return self._send_action({"action": "collect_upgraded_tool"})

            # Mining actions
            elif action_type == "enter_mine_level":
                level = action.params.get("level", 1)
                return self._send_action({
                    "action": "enter_mine_level",
                    "level": level
                })

            elif action_type == "use_ladder":
                return self._send_action({"action": "use_ladder"})

            elif action_type == "swing_weapon":
                direction = action.params.get("direction", "")
                return self._send_action({
                    "action": "swing_weapon",
                    "direction": direction
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

    # ========== VERIFICATION HELPERS ==========
    # These methods check game state to verify actions actually worked.
    # Critical fix for Session 115: batch chores logged success without verification.
    
    def verify_tilled(self, x: int, y: int) -> bool:
        """Verify that tile at (x,y) is now tilled (HoeDirt without crop).
        
        Returns True if tile is in tilledTiles from /farm endpoint.
        Call this AFTER use_tool with Hoe and waiting for animation.
        """
        farm = self.get_farm()
        if not farm:
            logging.warning(f"verify_tilled({x},{y}): No farm data")
            return False
        tilled = {(t.get("x"), t.get("y")) for t in farm.get("tilledTiles", [])}
        result = (x, y) in tilled
        if not result:
            logging.debug(f"verify_tilled({x},{y}): NOT in tilledTiles (count: {len(tilled)})")
        return result
    
    def verify_planted(self, x: int, y: int) -> bool:
        """Verify that crop exists at (x,y).

        Returns True if position is in crops array from /farm endpoint.
        Call this AFTER planting seeds and waiting for animation.
        """
        farm = self.get_farm()
        if not farm:
            logging.warning(f"verify_planted({x},{y}): No farm data")
            return False
        crops = {(c.get("x"), c.get("y")) for c in farm.get("crops", [])}
        result = (x, y) in crops
        if not result:
            # Session 117: More diagnostic info for plant failures
            logging.warning(f"verify_planted({x},{y}): NOT in crops (total_crops={len(crops)})")
        return result
    
    def verify_watered(self, x: int, y: int) -> bool:
        """Verify that crop at (x,y) is watered.

        Returns True if crop exists and isWatered=True.
        Call this AFTER watering and waiting for animation.
        """
        farm = self.get_farm()
        if not farm:
            logging.warning(f"verify_watered({x},{y}): No farm data")
            return False
        for crop in farm.get("crops", []):
            if crop.get("x") == x and crop.get("y") == y:
                is_watered = crop.get("isWatered", False)
                if not is_watered:
                    # Diagnostic: Log why verification failed (WARNING level for debugging Session 117)
                    logging.warning(f"verify_watered({x},{y}): Crop exists but isWatered=False (crop={crop.get('cropName', '?')})")
                return is_watered
        logging.debug(f"verify_watered({x},{y}): No crop found at position")
        return False
    
    def verify_cleared(self, x: int, y: int) -> bool:
        """Verify that debris/object at (x,y) was cleared.
        
        Returns True if position is NOT in objects or debris arrays.
        Call this AFTER clearing with appropriate tool.
        """
        farm = self.get_farm()
        if not farm:
            logging.warning(f"verify_cleared({x},{y}): No farm data")
            return False
        objects = {(o.get("x"), o.get("y")) for o in farm.get("objects", [])}
        debris = {(d.get("x"), d.get("y")) for d in farm.get("debris", [])}
        grass = {(g.get("x"), g.get("y")) for g in farm.get("grassPositions", [])}
        blocked = objects | debris | grass
        result = (x, y) not in blocked
        if not result:
            logging.debug(f"verify_cleared({x},{y}): Still blocked (objects:{len(objects)}, debris:{len(debris)}, grass:{len(grass)})")
        return result
    
    def get_verification_snapshot(self) -> dict:
        """Get current farm state for batch verification.
        
        Returns dict with sets for quick membership testing.
        Use this at start of batch operation, then verify against fresh data after.
        """
        farm = self.get_farm()
        if not farm:
            return {"tilledTiles": set(), "crops": set(), "watered": set()}
        return {
            "tilledTiles": {(t.get("x"), t.get("y")) for t in farm.get("tilledTiles", [])},
            "crops": {(c.get("x"), c.get("y")) for c in farm.get("crops", [])},
            "watered": {(c.get("x"), c.get("y")) for c in farm.get("crops", []) if c.get("isWatered", False)},
        }

    def verify_player_at(self, x: int, y: int, tolerance: int = 1) -> bool:
        """Verify player is at or adjacent to expected position.
        
        Args:
            x, y: Target tile coordinates
            tolerance: How many tiles away is acceptable (default 1 = adjacent)
            
        Returns True if player is within tolerance of target.
        """
        state = self.get_state()
        if not state:
            logging.warning(f"verify_player_at({x},{y}): No state data")
            return False
        player = state.get("player", {})
        px, py = player.get("tileX", 0), player.get("tileY", 0)
        distance = abs(px - x) + abs(py - y)  # Manhattan distance
        result = distance <= tolerance
        if not result:
            logging.warning(f"verify_player_at({x},{y}): Player at ({px},{py}), distance={distance} > tolerance={tolerance}")
        return result

    # =========================================================================
    # Verification Tracking - Persists to logs/verification_status.json
    # =========================================================================
    
    def reset_verification_tracking(self):
        """Reset tracking counters for a new batch operation."""
        self._verification_tracking = {
            "status": "active",
            "window_seconds": 60,
            "tilled": {"attempted": 0, "verified": 0},
            "planted": {"attempted": 0, "verified": 0},
            "watered": {"attempted": 0, "verified": 0},
            "failures": [],
            "updated_at": None,
        }
    
    def record_verification(self, action_type: str, x: int, y: int, success: bool, reason: str = ""):
        """Record a verification result.
        
        Args:
            action_type: "tilled", "planted", or "watered"
            x, y: Tile coordinates
            success: Whether verification passed
            reason: Failure reason if not successful
        """
        if not hasattr(self, "_verification_tracking"):
            self.reset_verification_tracking()
        
        tracking = self._verification_tracking
        if action_type in tracking:
            tracking[action_type]["attempted"] += 1
            if success:
                tracking[action_type]["verified"] += 1
            else:
                tracking["failures"].append({
                    "action": action_type.rstrip("ed"),  # tilled -> till
                    "x": x,
                    "y": y,
                    "reason": reason or f"{action_type} verification failed",
                })
        
        # Update timestamp
        from datetime import datetime
        tracking["updated_at"] = datetime.now().isoformat()
    
    def persist_verification_tracking(self):
        """Save tracking to logs/verification_status.json for UI consumption."""
        if not hasattr(self, "_verification_tracking"):
            return
        
        import json
        from pathlib import Path
        
        path = Path("/home/tim/StardewAI/logs/verification_status.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            path.write_text(json.dumps(self._verification_tracking, indent=2))
            logging.debug(f"Persisted verification tracking: {self._verification_tracking}")
        except Exception as e:
            logging.error(f"Failed to persist verification tracking: {e}")


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
        self._pending_batch = None  # For skill_override batch execution
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
        # Async commentary worker - runs in background thread
        self.commentary_worker = None  # Initialized after UI is set up
        self.last_mood: str = ""
        self._last_pushed_monologue: str = ""  # Track to avoid pushing duplicates
        self._last_commentary_push_time: float = 0.0  # Rate limit TTS pushes
        self._min_commentary_interval: float = 45.0  # Minimum seconds between TTS pushes (TTS takes ~35-50s)
        # Commentary settings cache - avoid HTTP calls on every tick
        self._commentary_settings_cache: Dict[str, Any] = {}
        self._commentary_settings_last_fetch: float = 0.0
        self._commentary_settings_ttl: float = 30.0  # Refresh every 30 seconds
        self._commentary_settings_applied: bool = False  # Track if settings were pushed to worker

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

        # Character memory (Elias's persistence across sessions)
        self.rusty_memory = None  # TODO: Rename to elias_memory
        if HAS_MEMORY and get_rusty_memory:
            try:
                self.rusty_memory = get_rusty_memory()
                state = self.rusty_memory.character_state
                logging.info(
                    f"🤖 Elias memory loaded: {state['mood']} mood, "
                    f"{self.rusty_memory.get_confidence_level()} confidence, "
                    f"{len(self.rusty_memory.relationships)} NPCs known"
                )
            except Exception as e:
                logging.warning(f"Elias memory failed to load: {e}")

        # Daily planner (Elias's task planning system)
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
        self._vlm_commentary_interval = 5  # VLM commentary every N ticks (lower = more frequent narration)
        self._commentary_event = None  # Event context for VLM prompt injection
        self._pending_executor_action = None  # Executor action to prepend after VLM runs
        self._task_executor_commentary_only = False  # When True, VLM observes only, no actions
        if HAS_TASK_EXECUTOR and TaskExecutor:
            try:
                self.task_executor = TaskExecutor()
                logging.info("🎯 Task Executor initialized (deterministic execution enabled)")
            except Exception as e:
                logging.warning(f"Task Executor failed to load: {e}")

        # Cell Farming Coordinator (cell-by-cell execution for plant_seeds)
        self.cell_coordinator: Optional[CellFarmingCoordinator] = None
        self._cell_farming_plan: Optional[CellFarmingPlan] = None
        self._current_cell_actions: List[CellAction] = []
        self._cell_action_index = 0
        self._cell_farming_done_today = False  # Prevent re-survey after completion
        self._cell_farming_last_day = 0  # Track day for reset
        self._pending_warp_location: Optional[str] = None  # Track pending warp to prevent loop
        self._pending_warp_time: float = 0.0  # When warp was issued
        if HAS_CELL_FARMING:
            logging.info("🌱 Cell-by-cell farming available")

        # Day 1 Clearing Mode - systematic debris clearing without VLM
        self._day1_clearing_active = False
        self._day1_tiles_cleared = 0
        self._day1_last_clear_time = 0.0
        self._last_vlm_time = 0.0  # Track VLM timing for commentary during clearing

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
            
        # Start async commentary worker (runs in background thread)
        if HAS_COMMENTARY and AsyncCommentaryWorker and self.ui_enabled:
            try:
                ui_callback = lambda **kw: self._ui_safe(self.ui.update_commentary, **kw)
                self.commentary_worker = AsyncCommentaryWorker(ui_callback=ui_callback)
                self.commentary_worker.start()
                logging.info("Commentary worker started")
            except Exception as exc:
                logging.warning(f"Commentary disabled: {exc}")
                self.commentary_worker = None

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

    def _get_skill_context(self, goal: str = "") -> str:
        """Get available skills for current game state to guide VLM.

        Session 122: Added goal-awareness to prioritize relevant skills.
        """
        if not self.skill_context or not self.last_state:
            return ""
        try:
            available = self.skill_context.get_available_skills(self.last_state)
            if not available:
                return ""
            # Skills that require target_direction parameter
            DIRECTION_SKILLS = {
                "till_soil", "plant_seed", "water_crop", "harvest_crop",
                "clear_weeds", "clear_stone", "clear_wood"
            }

            # Session 122: Goal-keyword to category/skill mapping
            goal_lower = goal.lower() if goal else ""
            GOAL_KEYWORDS = {
                "mine": ["mining", "combat", "navigation"],
                "mining": ["mining", "combat", "navigation"],
                "ore": ["mining"],
                "copper": ["mining"],
                "iron": ["mining"],
                "farm": ["farming", "crafting"],
                "water": ["farming"],
                "harvest": ["farming"],
                "plant": ["farming"],
                "shop": ["shopping", "navigation"],
                "pierre": ["shopping", "navigation"],
            }

            # Find priority categories based on goal
            priority_categories = set()
            for keyword, cats in GOAL_KEYWORDS.items():
                if keyword in goal_lower:
                    priority_categories.update(cats)

            # Group by category for readability
            by_category: Dict[str, List[str]] = {}
            for skill in available:
                cat = skill.category or "other"
                if cat not in by_category:
                    by_category[cat] = []
                # Format: skill_name - description (for VLM to output skill names)
                # Add parameter hint for directional skills
                if skill.name in DIRECTION_SKILLS:
                    by_category[cat].append(f"{skill.name} (target_direction: north/south/east/west) - {skill.description}")
                else:
                    by_category[cat].append(f"{skill.name} - {skill.description}")

            # Format as compact list - emphasize skill names for VLM selection
            lines = ["AVAILABLE SKILLS (use skill name as action type):"]

            # Session 122: Show priority categories first (more skills allowed)
            shown_categories = set()
            for cat in sorted(by_category.keys()):
                if cat in priority_categories:
                    shown_categories.add(cat)
                    skills = by_category[cat]
                    lines.append(f"  [{cat.upper()}] ⭐ RELEVANT TO YOUR GOAL")
                    for desc in skills[:12]:  # Show more for priority categories
                        lines.append(f"    - {desc}")
                    if len(skills) > 12:
                        lines.append(f"    ... and {len(skills) - 12} more")

            # Then show other categories
            for cat, skills in sorted(by_category.items()):
                if cat in shown_categories:
                    continue
                lines.append(f"  [{cat.upper()}]")
                for desc in skills[:6]:  # Fewer for non-priority
                    lines.append(f"    - {desc}")
                if len(skills) > 6:
                    lines.append(f"    ... and {len(skills) - 6} more")
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

        # CRITICAL: Refresh surroundings BEFORE capture to get current tile state
        if skill_name in ["plant_seed", "till_soil", "clear_weeds", "clear_stone", "clear_wood"]:
            if hasattr(self.controller, "get_surroundings"):
                self.last_surroundings = self.controller.get_surroundings()

        # Skill-specific captures using NEW API structure: directions.{dir}.adjacentTile
        if skill_name == "plant_seed":
            snapshot["crop_count"] = len(crops)
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                snapshot["target_tilled"] = adj_tile.get("isTilled", False)
                snapshot["target_has_crop"] = adj_tile.get("hasCrop", False)

        elif skill_name == "water_crop":
            target_crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
            snapshot["target_crop_watered"] = target_crop.get("isWatered", False) if target_crop else None

        elif skill_name == "till_soil":
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                snapshot["target_tilled"] = adj_tile.get("isTilled", False)

        elif skill_name == "harvest_crop":
            snapshot["crop_count"] = len(crops)
            inventory = player.get("inventory", [])
            snapshot["inventory_count"] = sum(1 for item in inventory if item)

        elif skill_name in ["clear_weeds", "clear_stone", "clear_wood"]:
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                snapshot["target_blocker"] = adj_tile.get("blockerType") or dir_info.get("blocker")

        return snapshot

    def _verify_state_change(self, skill_name: str, before: Dict[str, Any], params: Dict[str, Any]) -> bool:
        """Verify that skill execution actually changed the game state.

        Refreshes state and compares with before snapshot.
        Returns True if state changed as expected, False if phantom failure detected.
        """
        # Force state refresh
        self.last_state_poll = 0
        self._refresh_state_snapshot()

        if not self.last_state:
            return True  # Can't verify without state, assume success

        player = self.last_state.get("player", {})
        location_data = self.last_state.get("location", {})
        crops = location_data.get("crops", [])
        target = before.get("target", (0, 0))
        target_x, target_y = target
        target_dir = params.get("target_direction", "south")

        # Refresh surroundings for tile-based verification
        if hasattr(self.controller, "get_surroundings"):
            self.last_surroundings = self.controller.get_surroundings()

        # Skill-specific verification using NEW API: directions.{dir}.adjacentTile
        if skill_name == "plant_seed":
            # PRIMARY CHECK: adjacentTile.hasCrop (most reliable)
            # location.crops is unreliable when player isn't near crops
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                now_has_crop = adj_tile.get("hasCrop", False)
                was_has_crop = before.get("target_has_crop", False)

                if now_has_crop:
                    # Tile has a crop now - either we planted it or it was already there
                    if not was_has_crop:
                        return True  # We planted it!
                    else:
                        # Was already planted - this is weird but not a phantom failure
                        logging.debug(f"plant_seed: tile already had crop (target_dir={target_dir})")
                        return True
                else:
                    # Tile doesn't have crop - check if planting was even valid
                    if not adj_tile.get("canPlant", False) and not adj_tile.get("isTilled", False):
                        logging.warning(f"👻 PHANTOM: plant_seed - tile not plantable (tilled={adj_tile.get('isTilled')}, canPlant={adj_tile.get('canPlant')})")
                    else:
                        logging.warning(f"👻 PHANTOM: plant_seed - crop not planted on {target_dir} tile")
                    return False
            # Fallback to crop count if surroundings not available
            new_crop_count = len(crops)
            old_count = before.get("crop_count", 0)
            if new_crop_count > old_count:
                return True
            logging.warning(f"👻 PHANTOM: plant_seed - no surroundings, crop count {old_count}→{new_crop_count}")
            return False

        elif skill_name == "water_crop":
            # Session 118: Use fresh farm data for water verification (state cache is stale)
            farm_data = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
            if farm_data:
                fresh_crops = farm_data.get("crops", [])
                target_crop = next((c for c in fresh_crops if c.get("x") == target_x and c.get("y") == target_y), None)
            else:
                target_crop = next((c for c in crops if c.get("x") == target_x and c.get("y") == target_y), None)
            
            if target_crop:
                if target_crop.get("isReadyForHarvest", False):
                    return True  # Wrong action but not a failure
                if not target_crop.get("isWatered", False) and before.get("target_crop_watered") == False:
                    logging.warning(f"👻 PHANTOM: water_crop at ({target_x},{target_y}) still not watered")
                    return False
            return True

        elif skill_name == "till_soil":
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                now_tilled = adj_tile.get("isTilled", False)
                was_tilled = before.get("target_tilled", False)
                if not now_tilled and not was_tilled:
                    logging.warning(f"👻 PHANTOM: till_soil {target_dir} - tile still not tilled")
                    return False
            return True

        elif skill_name == "harvest_crop":
            new_crop_count = len(crops)
            old_count = before.get("crop_count", 0)
            if new_crop_count >= old_count:
                logging.warning(f"👻 PHANTOM: harvest_crop - count {old_count}→{new_crop_count}")
                return False
            return True

        elif skill_name in ["clear_weeds", "clear_stone", "clear_wood"]:
            if self.last_surroundings:
                dirs = self.last_surroundings.get("directions", {})
                dir_info = dirs.get(target_dir, {})
                adj_tile = dir_info.get("adjacentTile", {})
                old_blocker = before.get("target_blocker")
                new_blocker = adj_tile.get("blockerType") or dir_info.get("blocker")
                if old_blocker and new_blocker == old_blocker:
                    logging.warning(f"👻 PHANTOM: {skill_name} - {old_blocker} still at {target_dir}")
                    return False
            return True

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

        # Session 118+119: Block till_soil if target tile is already tilled OR not tillable
        if skill_name == "till_soil" and self.last_surroundings:
            target_dir = params.get("target_direction", "south")
            dirs = self.last_surroundings.get("directions", {})
            dir_info = dirs.get(target_dir, {})
            adj_tile = dir_info.get("adjacentTile", {})
            blocker = dir_info.get("blocker", "")
            if adj_tile.get("isTilled", False):
                logging.warning(f"🛡️ BLOCKED: till_soil target {target_dir} already tilled! Skipping.")
                self.recent_actions.append(f"BLOCKED: till_soil ({target_dir} already tilled)")
                self.recent_actions = self.recent_actions[-10:]
                return False
            # Session 119: Block if tile is not tillable (water, cliff, etc.)
            if not adj_tile.get("canTill", False):
                logging.warning(f"🛡️ BLOCKED: till_soil target {target_dir} not tillable (blocker={blocker})! Skipping.")
                self.recent_actions.append(f"BLOCKED: till_soil ({target_dir} not tillable)")
                self.recent_actions = self.recent_actions[-10:]
                return False

        # Session 118+119: Block plant_seed if target tile already has crop OR is not tilled
        if skill_name == "plant_seed" and self.last_surroundings:
            target_dir = params.get("target_direction", "south")
            dirs = self.last_surroundings.get("directions", {})
            dir_info = dirs.get(target_dir, {})
            adj_tile = dir_info.get("adjacentTile", {})
            if adj_tile.get("hasCrop", False):
                logging.warning(f"🛡️ BLOCKED: plant_seed target {target_dir} already has crop! Skipping.")
                self.recent_actions.append(f"BLOCKED: plant_seed ({target_dir} has crop)")
                self.recent_actions = self.recent_actions[-10:]
                return False
            # Session 119: Block if tile is NOT tilled - can't plant on untilled ground
            if not adj_tile.get("isTilled", False) and not adj_tile.get("canPlant", False):
                logging.warning(f"🛡️ BLOCKED: plant_seed target {target_dir} not tilled! Skipping.")
                self.recent_actions.append(f"BLOCKED: plant_seed ({target_dir} not tilled)")
                self.recent_actions = self.recent_actions[-10:]
                return False

        # Session 119: Block debris clearing if no clearable object in target direction
        # Uses SMAPI surroundings data directly - blocker field contains object name
        if skill_name in ["clear_weeds", "clear_stone", "clear_wood"] and self.last_surroundings:
            target_dir = params.get("target_direction", "south")
            dirs = self.last_surroundings.get("directions", {})
            dir_info = dirs.get(target_dir, {})
            blocker = (dir_info.get("blocker") or "").lower()

            # Non-clearable blockers - terrain features that can't be removed
            NON_CLEARABLE = {"water", "wall", "building", "cliff", "fence", ""}

            if blocker in NON_CLEARABLE:
                logging.warning(f"🛡️ BLOCKED: {skill_name} target {target_dir} has no clearable object (blocker={blocker or 'none'})! Skipping.")
                self.recent_actions.append(f"BLOCKED: {skill_name} ({target_dir} nothing to clear)")
                self.recent_actions = self.recent_actions[-10:]
                return False

            # Optional: Warn if wrong tool for debris type (but still allow - game might accept it)
            tool_debris_map = {
                "clear_weeds": ["weeds", "grass", "fiber"],
                "clear_stone": ["stone", "boulder", "rock"],
                "clear_wood": ["twig", "stump", "log", "wood", "branch"],
            }
            expected = tool_debris_map.get(skill_name, [])
            if blocker and not any(e in blocker for e in expected):
                logging.info(f"⚠️ {skill_name} target has {blocker} - may need different tool")

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

        # Prepare state with surroundings for skill executor (needed for pathfind_to: nearest_water etc.)
        skill_state = dict(self.last_state) if self.last_state else {}
        if hasattr(self.controller, "get_surroundings"):
            surroundings = self.controller.get_surroundings()
            if surroundings:
                skill_state["surroundings"] = surroundings.get("data", surroundings)

        # Add farm data for skills that require planning (auto_place_* skills)
        if skill.requires_planning and hasattr(self.controller, "get_farm"):
            farm_data = self.controller.get_farm()
            if farm_data:
                skill_state["farm"] = farm_data

        # BATCH OPERATIONS: Some skills trigger special batch handlers
        if skill_name == "auto_farm_chores":
            results = await self._batch_farm_chores()
            total = results["harvested"] + results["watered"] + results["planted"]
            if total > 0:
                logging.info(f"✅ auto_farm_chores: {total} actions taken")
                return True
            else:
                logging.info("✅ auto_farm_chores: nothing to do (farm is tidy)")
                return True  # Success even if nothing to do

        # Session 122: Batch mining
        if skill_name == "auto_mine":
            target_floors = params.get("floors", 5)
            results = await self._batch_mine_session(target_floors)
            total = results["ores_mined"] + results["rocks_broken"]
            if results["floors_descended"] > 0 or total > 0:
                logging.info(f"✅ auto_mine: {results['floors_descended']} floors, {results['ores_mined']} ores, {results['rocks_broken']} rocks")
                return True
            else:
                logging.info("✅ auto_mine: nothing mined (possibly retreated)")
                return True

        if skill_name == "auto_plant_seeds":
            planted = await self._batch_plant_seeds(params.get("seed_type"))
            if planted > 0:
                logging.info(f"✅ auto_plant_seeds: planted {planted} seeds")
                return True
            else:
                logging.warning("❌ auto_plant_seeds: no seeds planted")
                return False

        try:
            result = await self.skill_executor.execute(skill, params, skill_state)
            if result.success:
                # STATE-CHANGE DETECTION: Wait for game state to settle before verification
                # Tool swing animation completes, then SMAPI needs time to poll updated state
                # Session 121: Increased delays - SMAPI state cache can be slow
                if skill_name in ("till_soil", "plant_seed", "clear_weeds", "clear_stone", "clear_wood"):
                    await asyncio.sleep(1.2)  # Tile state takes longer to propagate
                elif skill_name == "water_crop":
                    await asyncio.sleep(1.0)  # Watering needs time for isWatered to update
                else:
                    await asyncio.sleep(0.5)

                # STATE-CHANGE DETECTION: Verify actual state change
                actual_success = self._verify_state_change(skill_name, state_before, params)

                if actual_success:
                    # Reset phantom failure counter on real success
                    self._phantom_failures[skill_name] = 0
                    logging.info(f"✅ Skill {skill_name} completed: {result.actions_taken}")
                    
                    # BATCH WATERING: After successful water_crop, continue watering without VLM
                    if skill_name == "water_crop":
                        await self._batch_water_remaining()
                    
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

    async def _batch_water_remaining(self) -> None:
        """Continue watering all remaining crops without returning to VLM.
        
        Called after first successful water_crop to batch water everything.
        Auto-refills when can empties. Stops on: all watered, energy low, or errors.
        """
        batch_count = 0
        refill_count = 0
        max_batch = 200  # Safety limit
        self._refill_attempts = 0  # Session 120: Reset refill attempt counter
        max_moves_to_crop = 50  # Max moves to reach a single crop
        skipped_crops = set()  # Crops we couldn't reach (behind buildings, etc.)
        watered_this_batch = set()  # Track crops we've watered (SMAPI cache is stale for ~250ms)
        
        # Initialize verification tracking (Session 116)
        self.controller.reset_verification_tracking()
        
        while batch_count < max_batch:
            # Force state refresh (bypass 0.5s throttle for batch operations)
            self.last_state_poll = 0
            self._refresh_state_snapshot()
            if not self.last_state:
                break
            
            player = self.last_state.get("player", {})
            location = self.last_state.get("location", {})
            location_name = location.get("name", "")
            
            # Use get_farm() for ALL crops (location.crops only has 15-tile range)
            farm_data = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
            if farm_data:
                crops = farm_data.get("crops", [])
            else:
                crops = location.get("crops", [])
            
            # Check energy constraint
            energy = player.get("energy", 0)
            if energy < 5:
                logging.info(f"⚡ Batch water stopped: low energy ({energy}) after {batch_count} crops")
                break
            
            # Check water can - refill if empty
            water_left = player.get("wateringCanWater", 0)
            if water_left <= 0:
                # Session 120: Track refill attempts to prevent infinite loop
                if not hasattr(self, '_refill_attempts'):
                    self._refill_attempts = 0
                self._refill_attempts += 1
                
                if self._refill_attempts > 3:
                    logging.warning(f"🚿 Refill failed {self._refill_attempts} times, stopping batch water")
                    self._refill_attempts = 0  # Reset for next batch
                    break
                
                logging.info(f"🚿 Water can empty after {batch_count} crops, refilling (attempt {self._refill_attempts})...")

                # Session 121: Direct refill approach - move to water, then use tool
                self._refresh_state_snapshot()
                surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else {}
                nearest_water = surroundings.get("nearestWater")

                if nearest_water and nearest_water.get("x"):
                    water_x, water_y = nearest_water["x"], nearest_water["y"]
                    logging.info(f"🚿 Found water at ({water_x}, {water_y}), distance={nearest_water.get('distance', '?')}")
                else:
                    # Fallback: Use standard farm pond location
                    water_x, water_y = 71, 33
                    logging.info(f"🚿 No nearestWater found, using farm pond at ({water_x}, {water_y})")

                # Move adjacent to water (can't stand ON water)
                # Try positions around the water tile
                water_adjacent = [
                    (water_x, water_y + 1, "north"),
                    (water_x, water_y - 1, "south"),
                    (water_x + 1, water_y, "west"),
                    (water_x - 1, water_y, "east"),
                ]

                refill_success = False
                for adj_x, adj_y, face_dir in water_adjacent:
                    logging.info(f"🚿 Attempting to reach ({adj_x}, {adj_y}) to refill facing {face_dir}")

                    # Try move_to first (uses A* pathfinding)
                    move_result = self.controller.execute(Action("move_to", {"x": adj_x, "y": adj_y}, "move to water"))

                    # Check if we actually arrived
                    await asyncio.sleep(0.2)
                    self._refresh_state_snapshot()
                    arrived = False
                    if self.last_state:
                        player = self.last_state.get("player", {})
                        px, py = player.get("tileX", 0), player.get("tileY", 0)
                        dist = abs(px - adj_x) + abs(py - adj_y)
                        if dist <= 1:
                            arrived = True
                            logging.info(f"🚿 Arrived at ({px},{py}) via move_to")

                    # If move_to failed, use warp (teleport - no pathfinding needed)
                    if not arrived:
                        logging.info(f"🚿 move_to failed, trying direct warp to ({adj_x},{adj_y})")
                        # Send warp directly to API (controller.execute doesn't support coord warp)
                        try:
                            import httpx
                            resp = httpx.post(
                                f"{self.controller.base_url}/action",
                                json={"action": "warp", "target": {"x": adj_x, "y": adj_y}},
                                timeout=5
                            )
                            if resp.status_code == 200:
                                await asyncio.sleep(0.2)
                                self._refresh_state_snapshot()
                                if self.last_state:
                                    player = self.last_state.get("player", {})
                                    px, py = player.get("tileX", 0), player.get("tileY", 0)
                                    if abs(px - adj_x) + abs(py - adj_y) <= 1:
                                        arrived = True
                                        logging.info(f"🚿 Arrived at ({px},{py}) via warp")
                        except Exception as e:
                            logging.warning(f"🚿 Warp failed: {e}")

                    if not arrived:
                        logging.warning(f"🚿 Could not reach ({adj_x},{adj_y}), trying next position")
                        continue

                    # We're close enough - try to refill
                    self.controller.execute(Action("select_item_type", {"value": "Watering Can"}, "equip can"))
                    await asyncio.sleep(0.1)
                    self.controller.execute(Action("face", {"direction": face_dir}, f"face {face_dir}"))
                    await asyncio.sleep(0.1)
                    self.controller.execute(Action("use_tool", {"direction": face_dir}, "refill"))
                    await asyncio.sleep(0.5)

                    # Check if refilled
                    self._refresh_state_snapshot()
                    new_water = self.last_state.get("player", {}).get("wateringCanWater", 0) if self.last_state else 0
                    if new_water > 0:
                        refill_count += 1
                        self._refill_attempts = 0
                        logging.info(f"✅ Refilled water can to {new_water} (refill #{refill_count})")
                        refill_success = True
                        break
                    else:
                        logging.warning(f"🚿 Refill attempt failed at ({adj_x},{adj_y}) facing {face_dir} - not facing water?")

                if refill_success:
                    # Already on farm (pond is on farm), just continue watering
                    continue
                else:
                    logging.warning(f"⚠️ Could not refill at any position around ({water_x}, {water_y})")
                    continue  # Will hit attempt limit
            
            # If not on Farm, return to farm
            if location_name != "Farm":
                logging.info(f"📍 Not on farm ({location_name}), returning...")
                warp_skill = self.skills_dict.get("warp_to_farm")
                if warp_skill:
                    result = await self.skill_executor.execute(warp_skill, {}, dict(self.last_state))
                    if result.success:
                        await asyncio.sleep(0.5)
                        continue
                break
            
            # Find unwatered crops (excluding skipped AND ones we watered this batch - SMAPI cache is stale)
            unwatered = [c for c in crops if not c.get("isWatered", False)
                         and (c.get("x"), c.get("y")) not in skipped_crops
                         and (c.get("x"), c.get("y")) not in watered_this_batch]
            if not unwatered:
                skipped_count = len(skipped_crops)
                if skipped_count > 0:
                    logging.info(f"✅ Batch water complete: {batch_count} crops watered, {skipped_count} unreachable, {refill_count} refills")
                else:
                    logging.info(f"✅ Batch water complete: {batch_count} crops watered, {refill_count} refills (total crops: {len(crops)})")
                break
            
            # Log progress periodically
            if batch_count == 0:
                logging.info(f"🚿 Starting batch water: {len(unwatered)} unwatered of {len(crops)} crops")
            
            player_x = player.get("tileX", 0)
            player_y = player.get("tileY", 0)
            
            # Check adjacent tiles first
            directions = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
            adjacent_crop = None
            water_dir = None
            
            for dir_name, (dx, dy) in directions.items():
                tx, ty = player_x + dx, player_y + dy
                crop = next((c for c in unwatered if c.get("x") == tx and c.get("y") == ty), None)
                if crop:
                    adjacent_crop = crop
                    water_dir = dir_name
                    break
            
            if adjacent_crop:
                # Session 121: Double-check water BEFORE attempting to water
                # This catches cases where state was stale at top of loop
                self._refresh_state_snapshot()
                current_water = self.last_state.get("player", {}).get("wateringCanWater", 0) if self.last_state else 0
                if current_water <= 0:
                    logging.info(f"🚿 Can empty before watering - need refill first")
                    continue  # Will trigger refill at top of next iteration

                # Water adjacent crop directly
                params = {"target_direction": water_dir}
                skill = self.skills_dict.get("water_crop")
                if skill:
                    skill_state = dict(self.last_state)
                    result = await self.skill_executor.execute(skill, params, skill_state)
                    if result.success:
                        # Track locally immediately (SMAPI cache is stale for ~250ms)
                        watered_this_batch.add((adjacent_crop['x'], adjacent_crop['y']))
                        await asyncio.sleep(1.0)  # Session 117: Increased from 0.5s to 1.0s

                        # VERIFY: Check if crop is actually watered (Session 115 fix + Session 116 tracking)
                        crop_x, crop_y = adjacent_crop['x'], adjacent_crop['y']
                        water_verified = self.controller.verify_watered(crop_x, crop_y)

                        # Session 117: Retry once if verification fails
                        if not water_verified:
                            logging.info(f"💧 Water verification failed at ({crop_x},{crop_y}), retrying...")
                            await self.skill_executor.execute(skill, params, skill_state)
                            await asyncio.sleep(1.0)
                            water_verified = self.controller.verify_watered(crop_x, crop_y)

                        self.controller.record_verification("watered", crop_x, crop_y, water_verified, "crop not watered")
                        if water_verified:
                            batch_count += 1
                            if batch_count % 10 == 0:
                                logging.info(f"🚿 Batch progress: {batch_count} VERIFIED, {len(unwatered)-1} remaining")
                        else:
                            logging.warning(f"⚠ Water not verified at ({crop_x},{crop_y}) after retry - counted anyway")
                            batch_count += 1  # Count anyway since we tracked locally
                        continue
                    else:
                        logging.warning(f"🚿 Batch water failed at ({adjacent_crop['x']}, {adjacent_crop['y']})")
                        break
            else:
                # Session 118: Move to ADJACENT position (not ON crop) using move_to
                nearest = min(unwatered, key=lambda c: abs(c.get("x", 0) - player_x) + abs(c.get("y", 0) - player_y))
                target_x, target_y = nearest.get("x", 0), nearest.get("y", 0)
                
                # Choose adjacent position: prefer south (facing north to water)
                # Try: south, north, east, west of crop
                adjacent_positions = [
                    (target_x, target_y + 1, "north"),  # Stand south, face north
                    (target_x, target_y - 1, "south"),  # Stand north, face south
                    (target_x + 1, target_y, "west"),   # Stand east, face west
                    (target_x - 1, target_y, "east"),   # Stand west, face east
                ]
                
                # Find best adjacent position (closest to player)
                best_pos = None
                best_dir = None
                best_dist = float('inf')
                for adj_x, adj_y, face_dir in adjacent_positions:
                    dist = abs(adj_x - player_x) + abs(adj_y - player_y)
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (adj_x, adj_y)
                        best_dir = face_dir
                
                if best_pos:
                    adj_x, adj_y = best_pos
                    logging.debug(f"🚿 Moving to ({adj_x},{adj_y}) to water crop at ({target_x},{target_y})")
                    
                    move_result = self.controller.execute(Action("move_to", {"x": adj_x, "y": adj_y}, f"move adjacent to crop"))
                    await asyncio.sleep(0.3)  # Wait for move to complete
                    
                    # Check if move failed - might be blocked
                    if not move_result or (isinstance(move_result, dict) and not move_result.get("success", True)):
                        logging.info(f"⏭️ Can't reach crop at ({target_x},{target_y}), skipping")
                        skipped_crops.add((target_x, target_y))
                        continue
                    
                    # Verify we're adjacent (within 1 tile)
                    self._refresh_state_snapshot()
                    if self.last_state:
                        new_player = self.last_state.get("player", {})
                        new_x = new_player.get("tileX", 0)
                        new_y = new_player.get("tileY", 0)
                        dist_to_crop = abs(new_x - target_x) + abs(new_y - target_y)
                        if dist_to_crop > 1:
                            logging.info(f"⏭️ Couldn't get adjacent to crop at ({target_x},{target_y}), skipping")
                            skipped_crops.add((target_x, target_y))
                            continue
                    continue  # Loop will check for adjacent crop on next iteration
                
                # Fallback: step-by-step movement (should rarely happen)
                surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None
                dirs_info = surroundings.get("directions", {}) if surroundings else {}
                
                dx = target_x - player_x
                dy = target_y - player_y
                
                move_options = []
                if abs(dx) >= abs(dy):
                    move_options.append("east" if dx > 0 else "west")
                    move_options.append("south" if dy > 0 else "north")
                else:
                    move_options.append("south" if dy > 0 else "north")
                    move_options.append("east" if dx > 0 else "west")
                
                move_dir = None
                for opt in move_options:
                    dir_info = dirs_info.get(opt, {})
                    is_clear = dir_info.get("clear", True)
                    tiles_until = dir_info.get("tilesUntilBlocked", 99)
                    if is_clear or tiles_until > 0:
                        move_dir = opt
                        break
                
                if not move_dir:
                    # All directions blocked - try to clear debris in preferred direction
                    primary_dir = move_options[0] if move_options else "south"
                    dir_info = dirs_info.get(primary_dir, {})
                    blocker = dir_info.get("blocker") or ""  # Handle None
                    
                    # Track stuck attempts per position
                    stuck_key = (player_x, player_y, blocker)
                    if not hasattr(self, '_batch_stuck_counts'):
                        self._batch_stuck_counts = {}
                    self._batch_stuck_counts[stuck_key] = self._batch_stuck_counts.get(stuck_key, 0) + 1
                    
                    # Give up after 3 attempts at same obstacle
                    if self._batch_stuck_counts[stuck_key] > 3:
                        logging.warning(f"🚿 Giving up on crop near ({player_x}, {player_y}) - {blocker} won't clear")
                        # Add target crop to skip list
                        skipped_crops.add((target_x, target_y))
                        # Move away from obstacle if possible
                        for escape_dir in ["south", "north", "east", "west"]:
                            escape_info = dirs_info.get(escape_dir, {})
                            if escape_info.get("clear", False) or escape_info.get("tilesUntilBlocked", 0) > 0:
                                escape_action = Action("move", {"direction": escape_dir, "duration": 0.3}, f"escape {escape_dir}")
                                if hasattr(self.controller, "execute"):
                                    self.controller.execute(escape_action)
                                    await asyncio.sleep(0.3)
                                break
                        continue
                    
                    # No blocker but still stuck = building/impassable terrain
                    if not blocker:
                        logging.info(f"⏭️ Blocked by building/terrain at ({player_x}, {player_y}), skipping crop")
                        skipped_crops.add((target_x, target_y))
                        await asyncio.sleep(0.2)
                        continue

                    # TOOL-AWARE OBSTACLE CHECK: Can we clear this with current tools?
                    inventory = self.last_state.get("inventory", []) if self.last_state else []
                    can_clear, reason, clear_skill_name = can_clear_obstacle(inventory, blocker)

                    if not can_clear:
                        logging.info(f"⏭️ Skipping {blocker} ({reason})")
                        skipped_crops.add((target_x, target_y))
                        # Track for tool upgrade suggestions
                        tracker = get_upgrade_tracker()
                        if tracker:
                            upgrade_suggestion = tracker.record_blocked(blocker, inventory)
                            if upgrade_suggestion:
                                logging.warning(f"🔧 TOOL UPGRADE SUGGESTED: {upgrade_suggestion}")
                        await asyncio.sleep(0.2)
                        continue

                    if clear_skill_name and clear_skill_name in self.skills_dict:
                        logging.info(f"🧹 Clearing {blocker} blocking {primary_dir}")
                        clear_skill = self.skills_dict[clear_skill_name]
                        skill_state = dict(self.last_state)
                        skill_state["surroundings"] = surroundings
                        result = await self.skill_executor.execute(clear_skill, {"direction": primary_dir}, skill_state)
                        await asyncio.sleep(0.3)
                        continue  # Retry movement after clearing
                    else:
                        logging.warning(f"🚿 Can't clear {blocker} at ({player_x}, {player_y})")
                        await asyncio.sleep(0.3)
                        continue
                
                # Execute move via controller
                move_action = Action("move", {"direction": move_dir, "duration": 0.15}, f"move {move_dir}")
                if hasattr(self.controller, "execute"):
                    self.controller.execute(move_action)
                    await asyncio.sleep(0.05)  # Let game process the move
                else:
                    logging.warning("🚿 No controller.execute for movement")
                    break
        
        if batch_count > 0:
            logging.info(f"🚿 Batch watering done: {batch_count} crops, {refill_count} refills")
        
        # Persist verification tracking for UI (Session 116)
        self.controller.persist_verification_tracking()

    async def _batch_plant_seeds(self, seed_type: str = None, tilled_positions: list = None) -> int:
        """Batch plant seeds at positions.

        If tilled_positions provided, plant there directly (from fresh tilling).
        Otherwise, query farm state for existing tilled tiles.

        Args:
            seed_type: Specific seed to plant (None = any seeds)
            tilled_positions: List of (x, y) tuples to plant at (from _batch_till_grid)

        Returns:
            Number of seeds successfully planted
        """
        planted_count = 0
        max_attempts = 100  # Safety limit

        # Force fresh state
        self.last_state_poll = 0
        self._refresh_state_snapshot()
        if not self.last_state:
            logging.warning("🌱 Batch plant: no state available")
            return 0

        inventory = self.last_state.get("inventory", [])
        seed_items = [i for i in inventory if i and "seed" in i.get("name", "").lower()]
        if seed_type:
            seed_items = [i for i in seed_items if seed_type.lower() in i.get("name", "").lower()]

        if not seed_items:
            logging.info(f"🌱 No seeds in inventory{' matching ' + seed_type if seed_type else ''}")
            return 0

        total_seeds = sum(i.get("stack", 1) for i in seed_items)
        seed_slot = seed_items[0].get("slot", 0)
        logging.info(f"🌱 Starting batch plant: {total_seeds} seeds available")

        # Use provided positions or query farm state
        if tilled_positions:
            # Positions passed directly - use them (sorted row-by-row)
            positions = sorted(tilled_positions, key=lambda p: (p[1], p[0]))
            positions = [{"x": x, "y": y} for x, y in positions[:total_seeds]]
            logging.info(f"🌱 Using {len(positions)} provided positions")
        else:
            # Query farm state (fallback)
            from planning.farm_planner import get_planting_sequence
            farm_state = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
            if not farm_state:
                logging.warning("🌱 Batch plant: no farm state")
                return 0

            data = farm_state.get("data") or farm_state
            logging.info(f"🌱 Farm state: {len(data.get('tilledTiles', []))} tilled, {len(data.get('crops', []))} crops")

            player = self.last_state.get("player", {})
            player_pos = (player.get("tileX", 0), player.get("tileY", 0))

            sequence = get_planting_sequence(farm_state, player_pos, total_seeds)
            positions = sequence.get("positions", [])

        if not positions:
            logging.info("🌱 No positions available for planting")
            return 0

        logging.info(f"🌱 Planting at {len(positions)} positions")

        for i, pos in enumerate(positions):
            if planted_count >= max_attempts:
                break

            target_x, target_y = pos["x"], pos["y"]

            # Navigate to adjacent position
            # Stand south of target to face north and plant
            stand_x, stand_y = target_x, target_y + 1

            # Move to position
            move_result = self.controller.execute(Action(
                "move_to", {"x": stand_x, "y": stand_y}, f"move to ({stand_x},{stand_y})"
            ))
            if not move_result:
                logging.debug(f"🌱 Couldn't reach ({stand_x},{stand_y}), skipping")
                continue

            await asyncio.sleep(0.05)  # Minimal wait for move_to

            # Select seeds
            self.controller.execute(Action("select_slot", {"slot": seed_slot}, "select seeds"))

            # Face north and plant
            self.controller.execute(Action("face", {"direction": "north"}, "face north"))
            self.controller.execute(Action("use_tool", {}, "plant seed"))
            await asyncio.sleep(0.05)  # Minimal delay

            # Water immediately
            water_skill = self.skills_dict.get("water_crop")
            if water_skill:
                skill_state = dict(self.last_state) if self.last_state else {}
                await self.skill_executor.execute(water_skill, {"target_direction": "north"}, skill_state)
                await asyncio.sleep(0.03)  # Minimal delay

            planted_count += 1

            if planted_count % 5 == 0:
                logging.info(f"🌱 Planted {planted_count}/{len(positions)}")

            # Refresh state for next iteration
            self._refresh_state_snapshot()

            # Check if we ran out of seeds
            inventory = self.last_state.get("inventory", []) if self.last_state else []
            remaining = sum(i.get("stack", 1) for i in inventory
                          if i and "seed" in i.get("name", "").lower())
            if remaining <= 0:
                logging.info(f"🌱 Out of seeds after planting {planted_count}")
                break

        logging.info(f"🌱 Batch planting complete: {planted_count} seeds planted and watered")
        return planted_count

    async def _batch_farm_chores(self) -> dict:
        """Execute ALL farm chores in sequence without VLM consultation.

        Order: Buy Seeds (if needed) → Harvest → Water → Till → Plant

        Returns dict with counts of each action taken.
        """
        results = {"seeds_bought": 0, "harvested": 0, "watered": 0, "tilled": 0, "planted": 0}

        logging.info("🏠 ═══════════════════════════════════════")
        logging.info("🏠 BATCH FARM CHORES - Running autonomously")
        logging.info("🏠 ═══════════════════════════════════════")

        # Refresh state
        self._refresh_state_snapshot()
        if not self.last_state:
            logging.warning("🏠 No state available for batch chores")
            return results

        # Dismiss any open menus first (they block warps!)
        menu = self.last_state.get("menu")
        if menu:
            logging.info(f"🏠 Dismissing open menu: {menu}")
            self.controller.execute(Action("dismiss_menu", {}, "close menu"))
            await asyncio.sleep(0.2)
            self._refresh_state_snapshot()

        if not self.last_state:
            logging.warning("🏠 No state available for batch chores")
            return results

        # --- PHASE 0: BUY SEEDS IF NEEDED ---
        inventory = self.last_state.get("inventory", [])
        has_seeds = any(i and "seed" in i.get("name", "").lower() for i in inventory)

        if not has_seeds:
            player = self.last_state.get("player", {})
            money = player.get("money", 0)
            time_data = self.last_state.get("time", {})
            hour = time_data.get("hour", 6)
            day_of_week = time_data.get("dayOfWeek", "Monday")

            # Pierre's open: 9-17, not Wednesday
            pierre_open = 9 <= hour < 17 and day_of_week != "Wednesday"

            if pierre_open and money >= 20:  # Minimum for parsnip seeds
                logging.info(f"🛒 Phase 0: No seeds! Going to Pierre's ({money}g available)")

                # Get recommended seed
                seed_skill, seed_reason = get_recommended_seed_skill(self.last_state)
                logging.info(f"🛒 Crop advisor recommends: {seed_reason}")

                # Go to Pierre's
                self.controller.execute(Action("warp", {"location": "SeedShop"}, "warp to Pierre's"))
                await asyncio.sleep(0.15)  # Warp is instant, just need state sync
                self._refresh_state_snapshot()

                # Buy seeds - calculate quantity based on money
                # Get seed price from skill name (approximate)
                seed_prices = {
                    "buy_parsnip_seeds": 20,
                    "buy_potato_seeds": 50,
                    "buy_cauliflower_seeds": 80,
                    "buy_kale_seeds": 70,
                    "buy_garlic_seeds": 40,
                    "buy_jazz_seeds": 30,
                }
                price = seed_prices.get(seed_skill, 20)
                quantity = min(money // price, 15)  # Max 15 seeds at once

                if quantity > 0:
                    # Extract seed item name from skill
                    seed_item = seed_skill.replace("buy_", "").replace("_", " ").title()
                    logging.info(f"🛒 Buying {quantity} {seed_item} @ {price}g each")

                    self.controller.execute(Action("buy", {
                        "item": seed_item,
                        "quantity": quantity
                    }, f"buy {quantity} {seed_item}"))
                    await asyncio.sleep(0.1)  # Buy is instant
                    results["seeds_bought"] = quantity

                # Return to farm
                logging.info("🏠 Returning to farm...")
                self.controller.execute(Action("warp", {"location": "Farm"}, "warp to Farm"))
                await asyncio.sleep(0.15)  # Warp is instant
                self._refresh_state_snapshot()
            elif not pierre_open:
                logging.info(f"🛒 No seeds but Pierre's closed (hour={hour}, day={day_of_week})")
            elif money < 20:
                logging.info(f"🛒 No seeds and not enough money ({money}g)")

        location = self.last_state.get("location", {}) if self.last_state else {}

        # Check we're on farm (with retry limit to prevent infinite loop)
        loc_name = location.get("name", "")
        warp_attempts = 0
        while loc_name != "Farm" and warp_attempts < 5:
            warp_attempts += 1
            logging.info(f"🏠 Not on Farm (at {loc_name}), warping... (attempt {warp_attempts}/5)")

            # Check for blocking menu
            menu = self.last_state.get("menu") if self.last_state else None
            if menu:
                logging.info(f"🏠 Menu blocking warp: {menu}, dismissing...")
                self.controller.execute(Action("dismiss_menu", {}, "close menu"))
                await asyncio.sleep(0.2)

            self.controller.execute(Action("warp", {"location": "Farm"}, "warp to Farm"))
            await asyncio.sleep(0.3)  # Give warp time to complete
            self._refresh_state_snapshot()
            location = self.last_state.get("location", {}) if self.last_state else {}
            loc_name = location.get("name", "")

        if loc_name != "Farm":
            logging.error(f"🏠 Failed to warp to Farm after {warp_attempts} attempts!")
            return results

        # CRITICAL: Use get_farm() for ALL crops (no distance limit)
        # location.crops only has crops within 15 tiles of player!
        farm_data = None
        if hasattr(self.controller, 'get_farm'):
            farm_data = self.controller.get_farm()
        if farm_data:
            crops = farm_data.get("crops", [])
            logging.info(f"🏠 Farm has {len(crops)} total crops")
        else:
            # Fallback to location crops (limited range)
            crops = location.get("crops", [])
            logging.warning(f"🏠 Using location crops (fallback): {len(crops)}")

        # Helper to refresh crops from farm data
        def _refresh_farm_crops():
            if hasattr(self.controller, 'get_farm'):
                fd = self.controller.get_farm()
                if fd:
                    return fd.get("crops", [])
            return self.last_state.get("location", {}).get("crops", []) if self.last_state else []

        # --- PHASE 1: WATER (critical - crops die without water!) ---
        unwatered = [c for c in crops if not c.get("isWatered", False) and not c.get("isReadyForHarvest", False)]
        if unwatered:
            logging.info(f"💧 Phase 1: Watering {len(unwatered)} crops")
            await self._batch_water_remaining()
            results["watered"] = len(unwatered)  # Approximate
            self._refresh_state_snapshot()
            crops = _refresh_farm_crops()

        # --- PHASE 2: HARVEST ---
        harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
        if harvestable:
            logging.info(f"🌾 Phase 2: Harvesting {len(harvestable)} crops")
            skipped_harvest = 0
            for crop in harvestable:
                cx, cy = crop.get("x", 0), crop.get("y", 0)
                crop_name = crop.get("cropName", "crop")
                
                # Session 120: Try multiple adjacent positions to reach crop
                # Order: south (face north), north (face south), east (face west), west (face east)
                adjacent_positions = [
                    (cx, cy + 1, "north"),  # Stand south, face north
                    (cx, cy - 1, "south"),  # Stand north, face south
                    (cx + 1, cy, "west"),   # Stand east, face west
                    (cx - 1, cy, "east"),   # Stand west, face east
                ]
                
                reached = False
                for adj_x, adj_y, face_dir in adjacent_positions:
                    move_result = self.controller.execute(Action("move_to", {"x": adj_x, "y": adj_y}, f"move to harvest"))
                    await asyncio.sleep(0.1)  # Wait for teleport to complete
                    
                    # Check if move succeeded (we should be at target position)
                    self._refresh_state_snapshot()
                    if self.last_state:
                        player = self.last_state.get("player", {})
                        px, py = player.get("tileX", 0), player.get("tileY", 0)
                        if px == adj_x and py == adj_y:
                            # Successfully reached adjacent position
                            self.controller.execute(Action("face", {"direction": face_dir}, "face crop"))
                            self.controller.execute(Action("harvest", {"direction": face_dir}, "harvest"))
                            await asyncio.sleep(0.1)  # Wait for harvest
                            results["harvested"] += 1
                            reached = True
                            break
                
                if not reached:
                    logging.warning(f"⏭️ Couldn't reach {crop_name} at ({cx},{cy}), skipping")
                    skipped_harvest += 1
            
            if skipped_harvest > 0:
                logging.info(f"🌾 Harvested {results['harvested']} crops, skipped {skipped_harvest} unreachable")
            else:
                logging.info(f"🌾 Harvested {results['harvested']} crops")
            self._refresh_state_snapshot()
            crops = _refresh_farm_crops()

        # --- PHASE 3: TILL & PLANT (combined for efficiency) ---
        # Check for seeds - process EACH seed type separately (Session 116 fix)
        inventory = self.last_state.get("inventory", []) if self.last_state else []
        seed_items = [i for i in inventory if i and "seed" in i.get("name", "").lower()]
        
        total_tilled = 0
        total_planted = 0
        
        for seed_item in seed_items:
            seed_slot = seed_item.get("slot", 0)
            seed_count = seed_item.get("stack", 1)
            seed_name = seed_item.get("name", "seeds")
            
            if seed_count > 0:
                logging.info(f"🔨 Phase 3: Till & Plant {seed_count} {seed_name} from slot {seed_slot}")
                tilled, planted = await self._batch_till_and_plant(seed_count, seed_slot)
                total_tilled += tilled
                total_planted += planted
                
                # Refresh inventory for next seed type
                self._refresh_state_snapshot()
                inventory = self.last_state.get("inventory", []) if self.last_state else []
        
        results["tilled"] = total_tilled
        results["planted"] = total_planted

        logging.info("🏠 ═══════════════════════════════════════")
        logging.info(f"🏠 BATCH CHORES COMPLETE: harvested={results['harvested']}, watered={results['watered']}, tilled={results['tilled']}, planted={results['planted']}")
        logging.info("🏠 ═══════════════════════════════════════")

        return results

    # =========================================================================
    # BATCH MINING - Session 122
    # =========================================================================

    async def _batch_mine_session(self, target_floors: int = 5) -> dict:
        """Execute mining session: descend floors, break rocks, collect ore.

        Session 122: Batch mining similar to batch farm chores.

        Args:
            target_floors: How many floors to descend (default 5)

        Returns dict with counts:
            - rocks_broken: Regular stones broken
            - ores_mined: Copper/Iron/Gold/Iridium mined
            - monsters_killed: Monsters defeated
            - floors_descended: Floors cleared and descended
        """
        results = {"rocks_broken": 0, "ores_mined": 0, "monsters_killed": 0, "floors_descended": 0}

        logging.info("⛏️ ═══════════════════════════════════════")
        logging.info(f"⛏️ BATCH MINING - Target: {target_floors} floors")
        logging.info("⛏️ ═══════════════════════════════════════")

        # Safety limits
        MAX_ROCKS_PER_FLOOR = 30
        MIN_HEALTH_PCT = 25
        MIN_ENERGY_PCT = 15

        # Ensure we're in the mines
        self._refresh_state_snapshot()
        if not self.last_state:
            logging.warning("⛏️ No state available")
            return results

        location = self.last_state.get("location", {}).get("name", "")
        if "Mine" not in location and "UndergroundMine" not in location:
            logging.info(f"⛏️ Not in mines (at {location}), warping...")
            self.controller.execute(Action("warp", {"location": "Mine"}, "warp to mines"))
            await asyncio.sleep(0.3)
            # Enter level 1
            self.controller.execute(Action("enter_mine_level", {"level": 1}, "enter mine level 1"))
            await asyncio.sleep(0.5)
            self._refresh_state_snapshot()

        while results["floors_descended"] < target_floors:
            floor_rocks = 0

            # Get fresh state
            self._refresh_state_snapshot()
            if not self.last_state:
                break

            player = self.last_state.get("player", {})
            health = player.get("health", 100)
            max_health = player.get("maxHealth", 100)
            energy = player.get("energy", 100)
            max_energy = player.get("maxEnergy", 270)
            health_pct = (health / max_health * 100) if max_health > 0 else 0
            energy_pct = (energy / max_energy * 100) if max_energy > 0 else 0
            player_x = player.get("tileX", 0)
            player_y = player.get("tileY", 0)

            # Safety check: retreat if low health/energy
            if health_pct < MIN_HEALTH_PCT:
                logging.warning(f"⛏️ LOW HEALTH ({health_pct:.0f}%) - trying to eat")
                # Try to eat food
                ate = await self._try_eat_food()
                if not ate:
                    logging.warning("⛏️ No food! Retreating to surface")
                    self.controller.execute(Action("enter_mine_level", {"level": 0}, "retreat to surface"))
                    break

            if energy_pct < MIN_ENERGY_PCT:
                logging.warning(f"⛏️ LOW ENERGY ({energy_pct:.0f}%) - retreating")
                self.controller.execute(Action("enter_mine_level", {"level": 0}, "retreat to surface"))
                break

            # Get mining state
            mining = self.controller.get_mining() if hasattr(self.controller, 'get_mining') else None
            if not mining:
                logging.warning("⛏️ Can't get mining state")
                break

            floor = mining.get("floor", 0)
            rocks = mining.get("rocks", [])
            monsters = mining.get("monsters", [])
            ladder_found = mining.get("ladderFound", False)
            shaft_found = mining.get("shaftFound", False)

            logging.info(f"⛏️ Floor {floor}: {len(rocks)} rocks, {len(monsters)} monsters, ladder={ladder_found}")

            # Detect infested floor: monsters present but no ladder spawns from rocks
            # On infested floors, ALL monsters must die before ladder appears
            is_infested = len(monsters) > 3 and not ladder_found and len(rocks) < 10

            # Priority 1: Handle monsters
            # - Always attack nearby monsters (dist <= 3)
            # - On infested floors or low rocks: actively hunt monsters
            hunt_monsters = is_infested or (len(rocks) < 5 and len(monsters) > 0)

            if hunt_monsters and monsters:
                logging.info(f"⛏️ {'INFESTED FLOOR' if is_infested else 'Low rocks'} - hunting {len(monsters)} monsters")

            for monster in monsters:
                mx, my = monster.get("x", monster.get("tileX", 0)), monster.get("y", monster.get("tileY", 0))
                dist = abs(mx - player_x) + abs(my - player_y)

                # Attack if nearby OR actively hunting
                if dist <= 3 or (hunt_monsters and dist <= 8):
                    logging.info(f"⛏️ Engaging {monster.get('name', 'unknown')} at ({mx},{my}), dist={dist}")

                    # Move closer if needed
                    if dist > 2:
                        self.controller.execute(Action("move_to", {"x": mx, "y": my}, f"approach monster"))
                        await asyncio.sleep(0.3)
                        self._refresh_state_snapshot()
                        if self.last_state:
                            player = self.last_state.get("player", {})
                            player_x = player.get("tileX", player_x)
                            player_y = player.get("tileY", player_y)

                    # Session 123: Check if we have a weapon before attacking
                    # Player can find weapons in the mines, so don't require one upfront
                    inventory = self.last_state.get("inventory", []) if self.last_state else []
                    has_weapon = any(
                        item and item.get("type") == "Weapon"
                        for item in inventory if item
                    )

                    if has_weapon:
                        # Equip weapon and attack
                        direction = self._direction_to_target(player_x, player_y, mx, my)
                        self.controller.execute(Action("select_item_type", {"value": "Weapon"}, "equip weapon"))
                        await asyncio.sleep(0.1)
                        # Multiple swings for tougher monsters
                        for _ in range(3):
                            self.controller.execute(Action("swing_weapon", {"direction": direction}, f"attack {direction}"))
                            await asyncio.sleep(0.2)
                        results["monsters_killed"] += 1
                    else:
                        # No weapon - avoid monster and focus on rocks
                        logging.info(f"⛏️ No weapon! Avoiding monster at ({mx},{my})")
                        # Move away from monster
                        escape_dir = self._direction_to_target(mx, my, player_x, player_y)  # Opposite direction
                        self.controller.execute(Action("move", {"direction": escape_dir, "duration": 0.3}, f"flee {escape_dir}"))
                        await asyncio.sleep(0.3)

            # Priority 2: Use ladder if found
            if ladder_found or shaft_found:
                logging.info(f"⛏️ {'Ladder' if ladder_found else 'Shaft'} found! Descending...")
                self.controller.execute(Action("use_ladder", {}, "use ladder"))
                await asyncio.sleep(0.5)
                results["floors_descended"] += 1
                continue

            # Priority 3: Mine rocks
            if not rocks:
                logging.info("⛏️ No rocks on floor - waiting for ladder spawn or moving on")
                await asyncio.sleep(0.5)
                continue

            # Sort by distance - mine closest first
            rocks_sorted = sorted(rocks, key=lambda r: abs(r.get("x", r.get("tileX", 0)) - player_x) + abs(r.get("y", r.get("tileY", 0)) - player_y))

            for rock in rocks_sorted[:5]:  # Process up to 5 rocks per iteration
                rx = rock.get("x", rock.get("tileX", 0))
                ry = rock.get("y", rock.get("tileY", 0))
                rock_type = rock.get("type", "Stone")

                # Move adjacent to rock
                moved = await self._move_adjacent_and_face(rx, ry)
                if not moved:
                    logging.debug(f"⛏️ Couldn't reach rock at ({rx},{ry})")
                    continue

                # Equip pickaxe and break rock
                self.controller.execute(Action("equip_tool", {"tool": "Pickaxe"}, "equip pickaxe"))
                await asyncio.sleep(0.1)

                # Determine hits needed based on rock type
                hits = 1
                if rock_type == "Copper":
                    hits = 2
                elif rock_type == "Iron":
                    hits = 3
                elif rock_type in ("Gold", "Iridium"):
                    hits = 4

                for _ in range(hits):
                    self.controller.execute(Action("use_tool", {}, "swing pickaxe"))
                    await asyncio.sleep(0.25)

                if rock_type in ("Copper", "Iron", "Gold", "Iridium"):
                    results["ores_mined"] += 1
                    logging.info(f"⛏️ Mined {rock_type} ore at ({rx},{ry})")
                else:
                    results["rocks_broken"] += 1

                floor_rocks += 1
                if floor_rocks >= MAX_ROCKS_PER_FLOOR:
                    logging.info(f"⛏️ Hit rock limit ({MAX_ROCKS_PER_FLOOR}) for this floor")
                    break

            # Brief pause between rock batches
            await asyncio.sleep(0.2)

        logging.info("⛏️ ═══════════════════════════════════════")
        logging.info(f"⛏️ MINING COMPLETE: ores={results['ores_mined']}, rocks={results['rocks_broken']}, floors={results['floors_descended']}")
        logging.info("⛏️ ═══════════════════════════════════════")

        return results

    async def _try_eat_food(self) -> bool:
        """Try to eat food from inventory to restore health."""
        self._refresh_state_snapshot()
        if not self.last_state:
            return False

        inventory = self.last_state.get("inventory", [])
        # Look for edible items
        FOOD_ITEMS = ["Salad", "Cheese", "Egg", "Milk", "Bread", "Cookie", "Pizza",
                      "Salmon", "Sardine", "Parsnip", "Potato", "Cauliflower"]

        for i, item in enumerate(inventory):
            if not item:
                continue
            name = item.get("name", "")
            if any(food.lower() in name.lower() for food in FOOD_ITEMS):
                logging.info(f"⛏️ Eating {name} from slot {i}")
                self.controller.execute(Action("select_slot", {"slot": i}, f"select {name}"))
                await asyncio.sleep(0.1)
                self.controller.execute(Action("eat", {}, f"eat {name}"))
                await asyncio.sleep(0.3)
                return True
        return False

    async def _move_adjacent_and_face(self, target_x: int, target_y: int) -> bool:
        """Move to a tile adjacent to target and face it."""
        self._refresh_state_snapshot()
        if not self.last_state:
            return False

        player = self.last_state.get("player", {})
        px, py = player.get("tileX", 0), player.get("tileY", 0)

        # Try adjacent positions: south, north, east, west of target
        adjacent = [
            (target_x, target_y + 1, "north"),  # Stand south, face north
            (target_x, target_y - 1, "south"),  # Stand north, face south
            (target_x + 1, target_y, "west"),   # Stand east, face west
            (target_x - 1, target_y, "east"),   # Stand west, face east
        ]

        # Sort by distance from player
        adjacent.sort(key=lambda a: abs(a[0] - px) + abs(a[1] - py))

        for adj_x, adj_y, face_dir in adjacent:
            # Try to move there
            self.controller.execute(Action("move_to", {"x": adj_x, "y": adj_y}, f"move to ({adj_x},{adj_y})"))
            await asyncio.sleep(0.3)

            # Check if we arrived
            self._refresh_state_snapshot()
            if self.last_state:
                player = self.last_state.get("player", {})
                new_x, new_y = player.get("tileX", 0), player.get("tileY", 0)
                if new_x == adj_x and new_y == adj_y:
                    # Face the target
                    self.controller.execute(Action("face", {"direction": face_dir}, f"face {face_dir}"))
                    await asyncio.sleep(0.1)
                    return True

        return False

    def _direction_to_target(self, px: int, py: int, tx: int, ty: int) -> str:
        """Get cardinal direction from player to target."""
        dx = tx - px
        dy = ty - py
        if abs(dx) > abs(dy):
            return "east" if dx > 0 else "west"
        else:
            return "south" if dy > 0 else "north"

    async def _batch_till_and_plant(self, count: int, seed_slot: int) -> tuple:
        """Combined till+plant+water operation for maximum efficiency.
        
        For each position: move → clear (if needed) → till → plant → water
        All done while standing adjacent, avoiding pathfinding issues.
        
        Args:
            count: Number of tiles to process
            seed_slot: Inventory slot containing seeds
            
        Returns:
            Tuple of (tilled_count, planted_count)
        """
        GRID_WIDTH = 5
        tilled = 0
        planted = 0
        
        # Initialize verification tracking (Session 116)
        self.controller.reset_verification_tracking()
        
        logging.info(f"🌱 Combined till+plant+water: {count} tiles")
        
        # Ensure we're on the farm (with menu dismissal and retry)
        self._refresh_state_snapshot()
        location = self.last_state.get("location", {}) if self.last_state else {}
        loc_name = location.get("name", "")
        warp_attempts = 0
        while loc_name != "Farm" and warp_attempts < 5:
            warp_attempts += 1
            logging.info(f"🌱 Not on Farm (at {loc_name}), warping... (attempt {warp_attempts}/5)")

            # Check for blocking menu
            menu = self.last_state.get("menu") if self.last_state else None
            if menu:
                logging.info(f"🌱 Menu blocking warp: {menu}, dismissing...")
                self.controller.execute(Action("dismiss_menu", {}, "close menu"))
                await asyncio.sleep(0.2)

            self.controller.execute(Action("warp", {"location": "Farm"}, "warp to Farm"))
            await asyncio.sleep(0.3)
            self._refresh_state_snapshot()
            location = self.last_state.get("location", {}) if self.last_state else {}
            loc_name = location.get("name", "")

        if loc_name != "Farm":
            logging.error(f"🌱 Failed to warp to Farm after {warp_attempts} attempts!")
            return (0, 0)

        # Get farm state
        farm_state = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
        if not farm_state:
            logging.warning("🌱 No farm state")
            return (0, 0)
            
        data = farm_state.get("data") or farm_state
        
        # Get blocked positions
        existing_tilled = {(t.get("x"), t.get("y")) for t in data.get("tilledTiles", [])}
        existing_crops = {(c.get("x"), c.get("y")) for c in data.get("crops", [])}
        permanent_blocked = existing_tilled | existing_crops
        
        objects_list = data.get("objects", [])
        objects_by_pos = {(o.get("x"), o.get("y")): o for o in objects_list}
        grass_positions = {(g.get("x"), g.get("y")) for g in data.get("grassPositions", [])}
        debris = {(d.get("x"), d.get("y")) for d in data.get("debris", [])}
        
        # ResourceClumps = large stumps, logs, boulders (need upgraded tools)
        # These have width x height, so block ALL tiles they occupy
        clump_blocked = set()
        for clump in data.get("resourceClumps", []):
            cx, cy = clump.get("x", 0), clump.get("y", 0)
            cw, ch = clump.get("width", 2), clump.get("height", 2)
            for dx in range(cw):
                for dy in range(ch):
                    clump_blocked.add((cx + dx, cy + dy))
        
        all_blocked = permanent_blocked | debris | set(objects_by_pos.keys()) | grass_positions | clump_blocked
        if clump_blocked:
            logging.info(f"🌱 Avoiding {len(clump_blocked)} tiles blocked by stumps/boulders")
        
        # Get player position for proximity
        player_pos = None
        if self.last_state:
            player = self.last_state.get("player", {})
            px, py = player.get("tileX"), player.get("tileY")
            if px is not None and py is not None:
                player_pos = (px, py)
        
        # Find best grid start near player
        start_x, start_y = self._find_best_grid_start(all_blocked, count, GRID_WIDTH, data, player_pos)
        logging.info(f"🌱 Grid start: ({start_x}, {start_y}) near player at {player_pos}")
        
        # Session 118: Query tillable area to exclude farmhouse/paths/non-farmland
        # This checks the "Diggable" map property to ensure tile is actually farmable
        tillable_area = self.controller.get_tillable_area(start_x, start_y, radius=15)
        if tillable_area is None:
            logging.warning("🌱 Tillable validation unavailable - restart game to load updated mod")
            # Fall back to old behavior (skip tillable check)
        elif len(tillable_area) == 0:
            logging.warning("🌱 No tillable tiles in area - may be on non-farmland")
        else:
            logging.info(f"🌱 Tillable validation: {len(tillable_area)} valid positions in area")
        
        # Generate grid positions - skip anything we can't clear
        # (permanent_blocked = already tilled/planted, clump_blocked = need upgraded tools)
        unclearable = permanent_blocked | clump_blocked
        grid_positions = []
        for row in range(count // GRID_WIDTH + 2):
            for col in range(GRID_WIDTH):
                if len(grid_positions) >= count:
                    break
                x = start_x + col
                y = start_y + row
                # Session 118: Must be tillable (if endpoint available) AND not blocked
                is_tillable = (tillable_area is None) or ((x, y) in tillable_area)
                if is_tillable and (x, y) not in unclearable:
                    grid_positions.append((x, y))
            if len(grid_positions) >= count:
                break
        
        if not grid_positions:
            logging.warning("🌱 No grid positions available")
            return (0, 0)
        
        logging.info(f"🌱 Processing {len(grid_positions)} positions")
        
        for x, y in grid_positions:
            if tilled >= count:
                break
            
            # Stand south of target
            stand_x, stand_y = x, y + 1
            move_result = self.controller.execute(Action("move_to", {"x": stand_x, "y": stand_y}, f"move to ({x},{y})"))

            if not move_result:
                logging.warning(f"🌱 move_to ({stand_x},{stand_y}) returned None, skipping")
                continue

            # Check if move_result indicates failure
            if isinstance(move_result, dict) and not move_result.get("success", True):
                logging.warning(f"🌱 move_to failed: {move_result.get('error', 'unknown')}")
                continue

            await asyncio.sleep(0.3)  # Wait for move to complete (was 0.1 - too fast)

            # Verify we actually moved (Session 116: use verify_player_at)
            if not self.controller.verify_player_at(stand_x, stand_y, tolerance=1):
                logging.warning(f"🌱 Move failed: player not at ({stand_x},{stand_y})")
                self.controller.record_verification("tilled", x, y, False, "player not at position")
                continue
            
            # 1. Clear if needed (grass or object)
            if (x, y) in grass_positions:
                self.controller.execute(Action("select_item_type", {"value": "Scythe"}, "equip scythe"))
                self.controller.execute(Action("use_tool", {"direction": "north"}, "clear grass"))
                await asyncio.sleep(0.4)  # Tool animation
            elif (x, y) in objects_by_pos:
                obj = objects_by_pos.get((x, y), {})
                obj_name = obj.get("name", "").lower()
                if "stone" in obj_name or "rock" in obj_name:
                    self.controller.execute(Action("select_item_type", {"value": "Pickaxe"}, "equip pickaxe"))
                elif "twig" in obj_name or "wood" in obj_name:
                    self.controller.execute(Action("select_item_type", {"value": "Axe"}, "equip axe"))
                else:
                    self.controller.execute(Action("select_item_type", {"value": "Scythe"}, "equip scythe"))
                self.controller.execute(Action("use_tool", {"direction": "north"}, "clear"))
                await asyncio.sleep(0.4)  # Tool animation
            
            # 2. Till - MUST complete before planting
            logging.info(f"🔨 Tilling ({x},{y}) - equip hoe, face north, use_tool")
            self.controller.execute(Action("select_item_type", {"value": "Hoe"}, "equip hoe"))
            await asyncio.sleep(0.1)  # Wait for item selection
            self.controller.execute(Action("face", {"direction": "north"}, "face north"))
            await asyncio.sleep(0.05)
            self.controller.execute(Action("use_tool", {"direction": "north"}, "till"))
            await asyncio.sleep(0.5)  # Tool animation - hoe swing must complete
            
            # VERIFY: Check if tile actually got tilled (Session 115 fix + Session 116 tracking)
            till_verified = self.controller.verify_tilled(x, y)
            self.controller.record_verification("tilled", x, y, till_verified, "tile not in tilledTiles")
            if till_verified:
                tilled += 1
                logging.info(f"✓ Till verified at ({x},{y})")
            else:
                logging.error(f"✗ Till FAILED at ({x},{y}) - tile not tilled! Skipping plant.")
                continue  # Skip planting since till failed

            # 3. Plant - on the now-tilled tile (only if till verified) - Session 117: retry
            logging.info(f"🌱 Planting at ({x},{y}) - slot {seed_slot}")
            self.controller.execute(Action("select_slot", {"slot": seed_slot}, "select seeds"))
            await asyncio.sleep(0.1)  # Wait for item selection
            self.controller.execute(Action("use_tool", {"direction": "north"}, "plant"))
            await asyncio.sleep(0.5)  # Session 117: Increased from 0.3s to 0.5s

            # VERIFY: Check if crop now exists (Session 115 fix + Session 116 tracking)
            plant_verified = self.controller.verify_planted(x, y)

            # Session 117: Retry once if verification fails
            if not plant_verified:
                logging.info(f"🌱 Plant verification failed at ({x},{y}), retrying...")
                self.controller.execute(Action("select_slot", {"slot": seed_slot}, "select seeds"))
                await asyncio.sleep(0.1)
                self.controller.execute(Action("use_tool", {"direction": "north"}, "plant"))
                await asyncio.sleep(0.5)
                plant_verified = self.controller.verify_planted(x, y)

            self.controller.record_verification("planted", x, y, plant_verified, "no crop at position")
            if plant_verified:
                planted += 1
                logging.info(f"✓ Plant verified at ({x},{y})")
            else:
                logging.error(f"✗ Plant FAILED at ({x},{y}) - no crop found!")
                continue  # Skip watering since plant failed

            # 4. Water (only if plant verified) - Session 117: increased wait + retry
            self.controller.execute(Action("select_item_type", {"value": "Watering Can"}, "equip can"))
            await asyncio.sleep(0.1)
            self.controller.execute(Action("use_tool", {"direction": "north"}, "water"))
            await asyncio.sleep(1.0)  # Session 117: Increased from 0.5s to 1.0s for SMAPI state refresh

            # VERIFY: Check if crop is watered (Session 115 fix + Session 116 tracking)
            water_verified = self.controller.verify_watered(x, y)

            # Session 117: Retry once if verification fails (SMAPI cache may need more time)
            if not water_verified:
                logging.info(f"💧 Water verification failed at ({x},{y}), retrying...")
                self.controller.execute(Action("use_tool", {"direction": "north"}, "water"))
                await asyncio.sleep(1.0)
                water_verified = self.controller.verify_watered(x, y)

            self.controller.record_verification("watered", x, y, water_verified, "crop not watered")
            if water_verified:
                logging.debug(f"✓ Water verified at ({x},{y})")
            else:
                logging.warning(f"⚠ Water not verified at ({x},{y}) after retry")

            if tilled % 5 == 0:
                logging.info(f"🌱 Progress: {tilled}/{count} tilled, {planted} planted (VERIFIED)")
        
        logging.info(f"🌱 Complete: {tilled} tilled, {planted} planted & watered")
        
        # Persist verification tracking for UI (Session 116)
        self.controller.persist_verification_tracking()
        
        return (tilled, planted)

    async def _batch_till_grid(self, count: int) -> tuple:
        """Till a contiguous grid of soil tiles (legacy - use _batch_till_and_plant instead).

        CLEARS obstacles (grass, weeds, stones, twigs) first, then tills.
        DYNAMICALLY finds the best farming area from farm state.

        Args:
            count: Number of tiles to till

        Returns:
            Tuple of (tiles_tilled_count, list_of_positions)
        """
        GRID_WIDTH = 5  # Till in rows of 5

        tilled = 0
        tilled_positions = []  # Track what we actually tilled

        # Initialize verification tracking (Session 116)
        self.controller.reset_verification_tracking()

        logging.info(f"🔨 Batch tilling {count} tiles in grid pattern")

        # Get farm state to find tillable positions
        farm_state = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
        if not farm_state:
            logging.warning("🔨 No farm state for tilling")
            return (0, [])

        data = farm_state.get("data") or farm_state

        # Get existing tilled and crop positions (can't till these)
        existing_tilled = {(t.get("x"), t.get("y")) for t in data.get("tilledTiles", [])}
        existing_crops = {(c.get("x"), c.get("y")) for c in data.get("crops", [])}
        permanent_blocked = existing_tilled | existing_crops

        # Get clearable objects with their types
        objects_list = data.get("objects", [])
        objects_by_pos = {(o.get("x"), o.get("y")): o for o in objects_list}
        
        # Get grass positions (terrain features that need scythe)
        grass_positions = {(g.get("x"), g.get("y")) for g in data.get("grassPositions", [])}
        logging.info(f"🔨 Farm state: {len(grass_positions)} grass tiles detected")
        
        # Debris (resource clumps - big stumps, boulders) - usually can't clear early game
        debris = {(d.get("x"), d.get("y")) for d in data.get("debris", [])}

        # For grid search, consider all blocked (even clearable like grass)
        all_blocked = permanent_blocked | debris | set(objects_by_pos.keys()) | grass_positions

        # Get player position for proximity-based grid search
        player_pos = None
        if self.last_state:
            player = self.last_state.get("player", {})
            px, py = player.get("tileX"), player.get("tileY")
            if px is not None and py is not None:
                player_pos = (px, py)
        
        # DYNAMIC: Find best starting position near player
        start_x, start_y = self._find_best_grid_start(all_blocked, count, GRID_WIDTH, data, player_pos)
        logging.info(f"🔨 Dynamic grid start: ({start_x}, {start_y})")

        # Generate grid positions (may include clearable objects/grass)
        grid_positions = []
        positions_to_clear = []  # Track which need clearing first (with type)

        for row in range(count // GRID_WIDTH + 2):  # Extra rows in case some blocked
            for col in range(GRID_WIDTH):
                if len(grid_positions) >= count:
                    break
                x = start_x + col
                y = start_y + row
                
                if (x, y) in permanent_blocked or (x, y) in debris:
                    continue  # Can't use this tile
                
                # Check if needs clearing
                if (x, y) in grass_positions:
                    positions_to_clear.append(((x, y), "grass"))
                elif (x, y) in objects_by_pos:
                    positions_to_clear.append(((x, y), "object"))
                
                grid_positions.append((x, y))
            if len(grid_positions) >= count:
                break

        if not grid_positions:
            logging.warning("🔨 No available grid positions")
            return (0, [])

        logging.info(f"🔨 Grid: {len(grid_positions)} positions, {len(positions_to_clear)} need clearing")

        # --- PHASE 1: CLEAR obstacles (grass, weeds, stones, twigs) ---
        if positions_to_clear:
            logging.info(f"🧹 Clearing {len(positions_to_clear)} obstacles before tilling")
            
            for (x, y), clear_type in positions_to_clear:
                # Choose tool based on type
                if clear_type == "grass":
                    # Grass terrain feature - use scythe
                    self.controller.execute(Action("select_item_type", {"value": "Scythe"}, "equip scythe"))
                else:
                    # Object - check what kind
                    obj = objects_by_pos.get((x, y), {})
                    obj_name = obj.get("name", "").lower()
                    
                    if "stone" in obj_name or "rock" in obj_name:
                        self.controller.execute(Action("select_item_type", {"value": "Pickaxe"}, "equip pickaxe"))
                    elif "twig" in obj_name or "wood" in obj_name or "branch" in obj_name:
                        self.controller.execute(Action("select_item_type", {"value": "Axe"}, "equip axe"))
                    else:
                        # Weeds, fiber, etc - use scythe
                        self.controller.execute(Action("select_item_type", {"value": "Scythe"}, "equip scythe"))
                
                # Move adjacent (stand south, face north)
                stand_x, stand_y = x, y + 1
                self.controller.execute(Action("move_to", {"x": stand_x, "y": stand_y}, f"move to clear"))
                await asyncio.sleep(0.05)
                
                # Face and clear
                self.controller.execute(Action("face", {"direction": "north"}, "face north"))
                self.controller.execute(Action("use_tool", {}, "clear"))
                await asyncio.sleep(0.05)
            
            logging.info(f"🧹 Cleared {len(positions_to_clear)} obstacles")

        # --- PHASE 2: TILL the grid ---
        logging.info(f"🔨 Tilling {len(grid_positions)} positions")
        self.controller.execute(Action("select_item_type", {"value": "Hoe"}, "equip hoe"))

        for x, y in grid_positions:
            if tilled >= count:
                break

            # Move adjacent (stand south, face north)
            stand_x, stand_y = x, y + 1
            self.controller.execute(Action("move_to", {"x": stand_x, "y": stand_y}, f"move to till"))
            await asyncio.sleep(0.2)  # Increased for move completion

            # Face north and till
            self.controller.execute(Action("face", {"direction": "north"}, "face north"))
            self.controller.execute(Action("use_tool", {}, "till"))
            await asyncio.sleep(0.5)  # Wait for tool animation

            # VERIFY: Check if tile actually got tilled (Session 115 fix + Session 116 tracking)
            till_verified = self.controller.verify_tilled(x, y)
            self.controller.record_verification("tilled", x, y, till_verified, "tile not in tilledTiles")
            if till_verified:
                tilled += 1
                tilled_positions.append((x, y))
                if tilled % 5 == 0:
                    logging.info(f"🔨 Tilled {tilled}/{count} (VERIFIED)")
            else:
                logging.error(f"✗ Till FAILED at ({x},{y}) - tile not tilled!")

        logging.info(f"🔨 Batch tilling complete: {tilled} VERIFIED tiles at positions {tilled_positions[:3]}...")
        
        # Persist verification tracking for UI (Session 116)
        self.controller.persist_verification_tracking()
        
        return (tilled, tilled_positions)

    def _find_best_grid_start(self, blocked: set, count: int, grid_width: int, farm_data: dict = None, player_pos: tuple = None) -> tuple:
        """Find the best starting position for a farming grid.

        PRIORITIZES positions near the player for reachability.
        Scans to find the position with the most contiguous clear tiles.

        Args:
            blocked: Set of (x, y) tuples that are blocked
            count: Number of tiles needed
            grid_width: Width of the grid pattern
            farm_data: Farm state data with name, mapWidth, mapHeight
            player_pos: (x, y) tuple of player position for proximity scoring

        Returns:
            Tuple of (start_x, start_y) for best grid position
        """
        # Get farm dimensions and type from SMAPI data
        map_width = farm_data.get("mapWidth", 80) if farm_data else 80
        map_height = farm_data.get("mapHeight", 65) if farm_data else 65
        farm_name = (farm_data.get("name", "") or "").lower() if farm_data else ""

        # Farm-type-specific tillable bounds
        # These define WHERE crops can actually grow on each farm type
        if "beach" in farm_name:
            # Beach Farm: Only small tillable patches, sand can't be tilled
            MIN_X, MAX_X = 35, 55
            MIN_Y, MAX_Y = 30, 50
        elif "riverland" in farm_name:
            # Riverland Farm: Islands with water between them
            MIN_X, MAX_X = 40, 70
            MIN_Y, MAX_Y = 20, 45
        elif "forest" in farm_name:
            # Forest Farm: Large stumps on left, tillable on right
            MIN_X, MAX_X = 50, 80
            MIN_Y, MAX_Y = 15, 45
        elif "hilltop" in farm_name or "hill-top" in farm_name:
            # Hilltop Farm: Quarry on left, small tillable areas
            MIN_X, MAX_X = 55, 85
            MIN_Y, MAX_Y = 20, 45
        elif "wilderness" in farm_name:
            # Wilderness Farm: Similar to standard but monsters at night
            MIN_X, MAX_X = 55, 85
            MIN_Y, MAX_Y = 16, 40
        elif "four" in farm_name and "corner" in farm_name:
            # Four Corners Farm: Divided into quadrants
            MIN_X, MAX_X = 30, 70
            MIN_Y, MAX_Y = 20, 50
        else:
            # Standard Farm (default): Large open tillable area
            # Use map dimensions with margins for buildings
            MIN_X = max(5, int(map_width * 0.4))   # ~40% from left
            MAX_X = min(map_width - 5, int(map_width * 0.95))
            MIN_Y = 16  # Below farmhouse row
            MAX_Y = min(map_height - 5, int(map_height * 0.7))

        logging.info(f"🔨 Farm bounds: {farm_name or 'standard'} ({MIN_X}-{MAX_X} x {MIN_Y}-{MAX_Y})")

        best_pos = (MIN_X + 5, MIN_Y + 2)  # Fallback within bounds
        best_score = 0

        grid_height = (count + grid_width - 1) // grid_width

        # If player position known, search in a smaller area NEAR the player
        if player_pos:
            search_radius = 15  # Only search within 15 tiles of player
            search_min_x = max(MIN_X, player_pos[0] - search_radius)
            search_max_x = min(MAX_X, player_pos[0] + search_radius)
            search_min_y = max(MIN_Y, player_pos[1] - search_radius)
            search_max_y = min(MAX_Y, player_pos[1] + search_radius)
            logging.info(f"🔨 Search area near player: ({search_min_x}-{search_max_x} x {search_min_y}-{search_max_y})")
        else:
            search_min_x, search_max_x = MIN_X, MAX_X
            search_min_y, search_max_y = MIN_Y, MAX_Y

        # Scan potential starting positions
        for start_y in range(search_min_y, search_max_y - grid_height + 1, 2):
            for start_x in range(search_min_x, search_max_x - grid_width + 1, 2):
                # Count how many tiles in this grid are clear
                clear_count = 0
                for row in range(grid_height):
                    for col in range(grid_width):
                        x = start_x + col
                        y = start_y + row
                        if (x, y) not in blocked:
                            clear_count += 1

                # Score: clear tiles + STRONG bonus for proximity to player
                score = clear_count
                
                if player_pos:
                    # Distance from player to grid center
                    grid_center_x = start_x + grid_width // 2
                    grid_center_y = start_y + grid_height // 2
                    distance = abs(grid_center_x - player_pos[0]) + abs(grid_center_y - player_pos[1])
                    # Heavily penalize far positions (proximity is critical for pathfinding)
                    proximity_bonus = max(0, 50 - distance * 2)  # Max 50 bonus at distance 0
                    score += proximity_bonus
                else:
                    # No player pos - prefer south (away from buildings)
                    score += (start_y - MIN_Y) * 0.1

                if score > best_score:
                    best_score = score
                    best_pos = (start_x, start_y)

        logging.info(f"🔨 Grid search: best={best_pos} with score={best_score:.1f} (player at {player_pos})")
        return best_pos

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

    def _start_cell_farming(
        self,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        task_id: str,
        description: str,
    ) -> bool:
        """
        Start cell-by-cell farming for plant_seeds task.

        Surveys the farm, creates a cell farming plan, and initializes
        the CellFarmingCoordinator for execution.

        Returns:
            True if cell farming started successfully, False otherwise
        """
        if not HAS_CELL_FARMING or not get_farm_surveyor:
            return False

        # Get current day to detect day change
        data = game_state.get("data") or game_state
        time_data = data.get("time", {})
        current_day = time_data.get("day", 0)
        
        # Reset flag on new day
        if current_day != self._cell_farming_last_day:
            self._cell_farming_done_today = False
            self._cell_farming_last_day = current_day
            logging.info(f"🌱 Cell farming: New day {current_day}, reset done flag")

        # Day 1: Skip cell farming - debris blocks all paths
        # Focus on clearing debris first, plant on Day 2+
        if current_day == 1:
            logging.info("🌱 Cell farming: Day 1 - skipping (clear debris first, plant Day 2+)")
            return False

        # Don't restart if already actively farming cells
        if self.cell_coordinator and not self.cell_coordinator.is_complete():
            logging.debug("🌱 Cell farming: Coordinator already active, skipping restart")
            return True  # Already running, return True so caller knows farming is active

        # Don't re-survey if already completed today
        if self._cell_farming_done_today:
            logging.debug("🌱 Cell farming: Already completed today, skipping re-survey")
            return False  # Don't start new farming, let other tasks run

        try:
            # Get farm state from /farm endpoint
            farm_state = self.controller.get_farm() if hasattr(self.controller, "get_farm") else None
            if not farm_state:
                logging.warning("🌱 Cell farming: No farm state available")
                return False

            # Count seeds in inventory and find seed slot
            data = game_state.get("data") or game_state
            inventory = data.get("inventory", [])

            seed_slot = None
            seed_type = "Parsnip Seeds"
            total_seeds = 0
            tool_map: Dict[str, int] = {}

            if InventoryManager:
                inv_mgr = InventoryManager(inventory)
                seed_priority = inv_mgr.get_seed_priority()
                if seed_priority:
                    seed_slot, seed_type = seed_priority
                total_seeds = inv_mgr.total_seeds()
                tool_map = inv_mgr.get_tool_mapping()
            else:
                for i, item in enumerate(inventory):
                    if item and "seed" in item.get("name", "").lower():
                        if seed_slot is None:
                            seed_slot = i
                            seed_type = item.get("name", "Parsnip Seeds")
                        total_seeds += item.get("stack", 1)
            
            if seed_slot is None:
                logging.warning("🌱 Cell farming: No seeds in inventory")
                return False

            # Get player position for cell selection (avoids cliff navigation issues)
            player = data.get("player", {})
            player_pos = (player.get("tileX", 64), player.get("tileY", 15))

            logging.info(f"🌱 Cell farming: Surveying farm for {total_seeds} {seed_type} (slot {seed_slot})")

            # Survey and create plan - use player position as center
            surveyor = get_farm_surveyor()
            self._cell_farming_plan = surveyor.create_farming_plan(
                farm_state=farm_state,
                seed_count=total_seeds,
                seed_type=seed_type,
                seed_slot=seed_slot,
                player_pos=player_pos,  # Select cells near player to stay on same cliff level
            )

            if not self._cell_farming_plan or not self._cell_farming_plan.cells:
                logging.warning("🌱 Cell farming: No optimal cells found")
                return False

            # Create coordinator
            self.cell_coordinator = CellFarmingCoordinator(self._cell_farming_plan, tool_map=tool_map)
            self._current_cell_actions = []
            self._cell_action_index = 0
            self._cell_nav_last_pos = None  # Track position for stuck detection
            self._cell_nav_stuck_count = 0  # Count consecutive stuck attempts
            self._CELL_NAV_STUCK_THRESHOLD = 10  # Skip cell after this many stuck ticks
            # Obstacle clearing state
            self._cell_clearing_obstacle = False
            self._cell_clear_action_index = 0
            self._cell_clear_direction = None
            self._cell_clear_blocker = None

            # Log plan summary
            cell_count = len(self._cell_farming_plan.cells)
            needs_clear = sum(1 for c in self._cell_farming_plan.cells if c.needs_clear)
            needs_till = sum(1 for c in self._cell_farming_plan.cells if c.needs_till)
            logging.info(
                f"🌱 Cell farming started: {cell_count} cells "
                f"({needs_clear} need clearing, {needs_till} need tilling)"
            )

            return True

        except Exception as e:
            logging.error(f"🌱 Cell farming failed to start: {e}")
            return False

    def _process_cell_farming(self) -> Optional[Action]:
        """
        Process one tick of cell-by-cell farming.

        Called each tick when cell_coordinator is active.
        Returns an Action to queue, or None if waiting.
        """
        if not self.cell_coordinator:
            return None

        # Get current game state and player position
        game_state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not game_state:
            return None

        data = game_state.get("data") or game_state
        player = data.get("player") or {}
        tile_x = player.get("tileX")
        tile_y = player.get("tileY")
        if tile_x is None or tile_y is None:
            return None
        player_pos = (tile_x, tile_y)

        # Check if we need to warp to Farm first (can't farm from inside FarmHouse)
        location = data.get("location", {}).get("name", "")
        if location == "FarmHouse":
            # Check if warp is already pending (prevent warp loop)
            now = time.time()
            if self._pending_warp_location == "Farm":
                if now - self._pending_warp_time < 3.0:
                    # Warp in progress, wait for it
                    logging.debug("🌱 Cell farming: Warp to Farm pending, waiting...")
                    return None
                else:
                    # Warp timed out, clear and retry
                    logging.warning("🌱 Cell farming: Warp to Farm timed out, retrying")
                    self._pending_warp_location = None

            # Issue warp and track it
            logging.info("🌱 Cell farming: Player in FarmHouse → warping to Farm")
            self._pending_warp_location = "Farm"
            self._pending_warp_time = now
            return Action(
                action_type="warp",
                params={"location": "Farm"},
                description="Warp to Farm for cell farming"
            )
        else:
            # Clear pending warp when we've arrived
            if self._pending_warp_location:
                logging.info(f"🌱 Warp complete: now in {location}")
                self._pending_warp_location = None

        # Get nearest uncompleted cell (dynamic, based on current position)
        cell = self.cell_coordinator.get_nearest_cell(player_pos)
        logging.debug(f"🌱 _process_cell_farming: player={player_pos}, nearest_cell={cell}")
        if not cell:
            # All cells complete - finish cell farming
            self._finish_cell_farming()
            return None

        # Check if we're currently clearing an obstacle
        if self._cell_clearing_obstacle:
            action = self._execute_obstacle_clear()
            if action:
                return action
            # Clearing complete, will continue navigation next tick

        # Check if we need to navigate to this cell
        nav_target = self.cell_coordinator.get_navigation_target(cell, player_pos)

        if player_pos != nav_target:
            # Stuck detection: if position hasn't changed, we may be blocked
            if self._cell_nav_last_pos == player_pos:
                self._cell_nav_stuck_count += 1

                # Skip cell after threshold - SMAPI pathfinding failed
                if self._cell_nav_stuck_count >= self._CELL_NAV_STUCK_THRESHOLD:
                    logging.warning(f"🌱 Cell ({cell.x},{cell.y}): STUCK, pathfinding failed. Skipping.")
                    self.cell_coordinator.skip_cell(cell, f"Pathfinding failed from {player_pos}")
                    self._cell_nav_stuck_count = 0
                    self._cell_nav_last_pos = None
                    return None
            else:
                # Position changed, reset counter
                self._cell_nav_stuck_count = 0
            self._cell_nav_last_pos = player_pos

            # Use move_to for direct pathfinding - SMAPI handles A* navigation
            logging.info(f"🌱 Cell ({cell.x},{cell.y}): Pathfinding to {nav_target}")
            return Action(
                action_type="move_to",
                params={"x": nav_target[0], "y": nav_target[1]},
                description=f"Pathfinding to cell ({cell.x},{cell.y})"
            )

        # We're at the right position - reset stuck tracking
        self._cell_nav_stuck_count = 0
        self._cell_nav_last_pos = None

        # Execute cell actions
        # Check if we just finished all actions for this cell
        if self._current_cell_actions and self._cell_action_index >= len(self._current_cell_actions):
            # All actions for this cell complete
            logging.info(f"🌱 Cell ({cell.x},{cell.y}): Complete!")
            self.cell_coordinator.mark_cell_complete(cell)
            self._current_cell_actions = []
            self._cell_action_index = 0
            return None  # Will process next cell on next tick

        # Check if we need to start a new cell
        if not self._current_cell_actions:
            # Start fresh cell execution
            # Compute facing direction
            facing = self.cell_coordinator.get_facing_direction(cell, player_pos)
            cell.target_direction = facing
            self._current_cell_actions = self.cell_coordinator.get_cell_actions(cell)
            self._cell_action_index = 0

            if not self._current_cell_actions:
                # No actions needed for this cell (already complete?)
                logging.info(f"🌱 Cell ({cell.x},{cell.y}): No actions needed, skipping")
                self.cell_coordinator.mark_cell_complete(cell)
                return None

            logging.info(f"🌱 Cell ({cell.x},{cell.y}): Starting {len(self._current_cell_actions)} actions (facing {facing})")

        # Get next action
        if self._cell_action_index < len(self._current_cell_actions):
            cell_action = self._current_cell_actions[self._cell_action_index]

            # Convert CellAction to Action
            action_dict = cell_action.to_dict()
            action_type = list(action_dict.keys())[0] if action_dict else "unknown"
            action_value = action_dict.get(action_type)

            # Dynamic check: Before watering, verify crop exists at cell
            if action_type == "select_slot" and self.cell_coordinator:
                watering_slot = self.cell_coordinator.watering_can_slot
                if action_value == watering_slot:
                    # About to water - check if crop exists at this cell
                    crop_exists = self._check_crop_at_cell(cell.x, cell.y)
                    if not crop_exists:
                        logging.warning(f"🌱 Cell ({cell.x},{cell.y}): No crop found, skipping water")
                        # Skip remaining actions (water is always last)
                        self._cell_action_index = len(self._current_cell_actions)
                        return None

            self._cell_action_index += 1

            # Build params based on action type
            params = {}
            if action_type == "select_slot":
                params = {"slot": action_value}
                action_type = "select_slot"
            elif action_type == "select_item":
                params = {"item": action_value}
                action_type = "select_item"
            elif action_type == "face":
                params = {"direction": action_value}
                action_type = "face"
            elif action_type == "use_tool":
                params = {}
                action_type = "use_tool"

            progress = f"({self._cell_action_index}/{len(self._current_cell_actions)})"
            logging.debug(f"🌱 Cell ({cell.x},{cell.y}): Action {progress} - {action_type}")

            return Action(
                action_type=action_type,
                params=params,
                description=f"Cell ({cell.x},{cell.y}): {action_type}"
            )

        # No more actions (should be caught by completion check at start)
        return None

    def _check_crop_at_cell(self, x: int, y: int) -> bool:
        """
        Check if there's a crop at the given cell coordinates.

        Queries live game state to verify crop exists before watering.
        This prevents watering empty tilled soil when planting failed.

        Args:
            x: Cell X coordinate
            y: Cell Y coordinate

        Returns:
            True if crop exists at cell, False otherwise
        """
        try:
            state = self.controller.get_state()
            if not state:
                return False

            data = state.get("data") or state
            location = data.get("location") or {}
            crops = location.get("crops") or []

            # Check if any crop matches this cell
            for crop in crops:
                crop_x = crop.get("x")
                crop_y = crop.get("y")
                if crop_x == x and crop_y == y:
                    logging.debug(f"🌱 Found crop at ({x},{y}): {crop.get('cropName')}")
                    return True

            return False
        except Exception as e:
            logging.warning(f"🌱 Error checking crop at ({x},{y}): {e}")
            return False  # Fail safe - don't water if we can't verify

    def _finish_cell_farming(self) -> None:
        """
        Complete cell-by-cell farming and clean up.
        """
        if not self.cell_coordinator:
            return

        completed, total = self.cell_coordinator.get_progress()
        logging.info(f"🌱 Cell farming complete: {completed}/{total} cells processed")
        
        # Mark as done for today to prevent re-survey loop
        self._cell_farming_done_today = True

        # Mark the plant_seeds task as complete
        if self.daily_planner:
            for task in self.daily_planner.tasks:
                if "plant" in task.description.lower() and task.status == "in_progress":
                    self.daily_planner.complete_task(task.id, f"Planted {completed} cells")
                    break

        # Clean up
        self.cell_coordinator = None
        self._cell_farming_plan = None
        self._current_cell_actions = []
        self._cell_action_index = 0

    # ========== DAY 1 CLEARING MODE ==========
    # Systematic debris clearing without VLM overhead
    # VLM is for decisions, not grunt work

    def _start_day1_clearing(self) -> bool:
        """Start Day 1 clearing mode - systematic debris clearing."""
        self._day1_clearing_active = True
        self._day1_tiles_cleared = 0
        self._day1_last_clear_time = time.time()
        logging.info("🧹 Day 1 clearing: Started - clearing debris near farmhouse")
        return True

    def _process_day1_clearing(self) -> Optional[Action]:
        """
        Process one tick of Day 1 clearing.

        Simple logic - no VLM needed:
        1. Get surroundings
        2. Find debris in 4 cardinal directions
        3. Clear with appropriate tool
        4. If no debris, move toward next debris or go to bed
        """
        if not self._day1_clearing_active:
            return None

        # Get surroundings
        surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None
        if not surroundings:
            return None

        data = surroundings.get("data") or surroundings
        directions = data.get("directions", {})
        player = data.get("player", {})
        energy = player.get("stamina", 100)

        # Low energy - go to bed
        if energy < 15:
            logging.info("🧹 Day 1 clearing: Low energy, going to bed")
            self._finish_day1_clearing()
            return Action(action_type="go_to_bed", params={}, description="Low energy, ending day")

        # Tool mapping for debris types
        DEBRIS_TOOLS = {
            "Stone": ("clear_stone", 3),   # Pickaxe slot
            "Twig": ("clear_wood", 0),     # Axe slot
            "Weeds": ("clear_weeds", 4),   # Scythe slot
        }

        # Check each direction for adjacent debris (tilesUntilBlocked == 1)
        for direction in ["north", "east", "south", "west"]:
            dir_info = directions.get(direction, {})
            blocker = dir_info.get("blocker") or ""  # API uses "blocker" not "blockedBy"
            tiles_until = dir_info.get("tilesUntilBlocked", 99)

            if blocker and blocker in DEBRIS_TOOLS and tiles_until == 0:
                skill_name, tool_slot = DEBRIS_TOOLS[blocker]
                self._day1_tiles_cleared += 1
                self._day1_last_clear_time = time.time()

                logging.info(f"🧹 Day 1: Clearing {blocker} to {direction} (#{self._day1_tiles_cleared})")

                # Queue primitive actions: face, select_slot, use_tool
                self.action_queue.append(Action(
                    action_type="face",
                    params={"direction": direction},
                    description=f"Face {direction}"
                ))
                self.action_queue.append(Action(
                    action_type="select_slot",
                    params={"slot": tool_slot},
                    description=f"Select tool slot {tool_slot}"
                ))
                return Action(
                    action_type="use_tool",
                    params={},
                    description=f"Clear {blocker}"
                )

        # No adjacent debris - find direction with debris further away and move toward it
        for direction in ["north", "east", "south", "west"]:
            dir_info = directions.get(direction, {})
            blocker = dir_info.get("blocker") or ""
            tiles_until = dir_info.get("tilesUntilBlocked", 99)

            if blocker and blocker in DEBRIS_TOOLS and tiles_until >= 1:
                # Debris further away - move toward it
                logging.info(f"🧹 Day 1: Moving {direction} toward {blocker} ({tiles_until} tiles)")
                return Action(
                    action_type="move",
                    params={"direction": direction, "tiles": 1},
                    description=f"Move toward {blocker}"
                )

        # No debris found nearby - clearing done for now
        if self._day1_tiles_cleared > 0:
            logging.info(f"🧹 Day 1 clearing: No more debris nearby, cleared {self._day1_tiles_cleared} tiles")
        self._finish_day1_clearing()
        return None

    def _finish_day1_clearing(self) -> None:
        """Complete Day 1 clearing mode."""
        logging.info(f"🧹 Day 1 clearing complete: {self._day1_tiles_cleared} tiles cleared")
        self._day1_clearing_active = False

    # ========== END DAY 1 CLEARING ==========

    def _execute_obstacle_clear(self) -> Optional[Action]:
        """
        Execute one step of obstacle clearing sequence: face → select_tool → use_tool.
        
        Called when navigation is blocked by clearable debris.
        Returns Action to execute, or None when clearing is complete.
        """
        # Import tool mapping
        from planning.farm_surveyor import FarmSurveyor
        
        actions = ["face", "select_slot", "use_tool"]
        
        if self._cell_clear_action_index >= len(actions):
            # Clearing complete, reset state
            logging.info(f"🌱 Cleared {self._cell_clear_blocker}, continuing navigation")
            self._cell_clearing_obstacle = False
            self._cell_clear_action_index = 0
            self._cell_clear_direction = None
            self._cell_clear_blocker = None
            self._cell_nav_stuck_count = 0  # Reset stuck counter after clearing
            return None  # Will retry movement next tick
        
        action_type = actions[self._cell_clear_action_index]
        self._cell_clear_action_index += 1
        
        if action_type == "face":
            return Action(
                action_type="face",
                params={"direction": self._cell_clear_direction},
                description=f"Facing {self._cell_clear_direction} to clear obstacle"
            )
        elif action_type == "select_slot":
            tool_slot = FarmSurveyor.DEBRIS_TOOL_SLOTS.get(self._cell_clear_blocker, 4)
            return Action(
                action_type="select_slot",
                params={"slot": tool_slot},
                description=f"Selecting tool for {self._cell_clear_blocker}"
            )
        elif action_type == "use_tool":
            return Action(
                action_type="use_tool",
                params={},
                description=f"Clearing {self._cell_clear_blocker}"
            )
        
        return None

    def _remove_plant_prereqs_from_queue(self) -> None:
        """
        Remove plant_seeds prereqs from resolved queue.

        When cell farming takes over, we don't need the separate
        clear_debris and till_soil tasks since they're handled per-cell.
        """
        if not self.daily_planner:
            return

        queue = self.daily_planner.resolved_queue
        # Find tasks that are prereqs for plant_seeds (clear_debris, till_soil)
        prereq_indices = []
        for i, rt in enumerate(queue):
            prereq_for = rt.prereq_for if hasattr(rt, 'prereq_for') else rt.get('prereq_for', '')
            is_prereq = rt.is_prereq if hasattr(rt, 'is_prereq') else rt.get('is_prereq', False)
            task_type = rt.task_type if hasattr(rt, 'task_type') else rt.get('task_type', '')

            # Remove clear_debris and till_soil prereqs for plant_seeds
            if is_prereq and task_type in ("clear_debris", "till_soil"):
                prereq_indices.append(i)

        # Remove in reverse order to maintain indices
        for i in reversed(prereq_indices):
            removed = queue.pop(i)
            task_type = removed.task_type if hasattr(removed, 'task_type') else removed.get('task_type', '?')
            logging.info(f"🌱 Removed prereq from queue: {task_type} (handled by cell farming)")

    def _try_start_daily_task(self) -> bool:
        """
        Try to start the next task from the RESOLVED queue.

        Uses PrereqResolver's ordered queue (with prereqs baked in) instead
        of keyword-matching raw tasks. This ensures:
        1. Prerequisites execute before main tasks
        2. No VLM override of task order
        3. Locked execution until queue complete or 2hr re-plan

        Returns True if a task was started, False otherwise.
        """
        # Session 124: Trace early returns
        if not self.task_executor or not self.daily_planner:
            logging.info(f"🎯 _try_start_daily_task: early return (executor={self.task_executor is not None}, planner={self.daily_planner is not None})")
            return False

        # Don't start if executor is already active
        if self.task_executor.is_active():
            logging.debug(f"🎯 _try_start_daily_task: executor active, skip")
            return False

        # Don't start tasks if daily plan hasn't been created yet for today
        # This prevents race condition on first tick where tasks run before planning
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if state:
            data = state.get("data") or state
            time_data = data.get("time", {})
            current_day = time_data.get("day", 0)
            if current_day > 0 and current_day != self._last_planned_day:
                # Session 124: Changed to INFO to see this issue
                logging.info(f"🎯 _try_start_daily_task: waiting for daily plan (day {current_day}, last_planned={self._last_planned_day})")
                return False

        # Session 119: DISABLED cell farming entirely - batch mode (auto_farm_chores) is preferred
        # Cell farming was legacy code that caused VLM phantom failures and was less efficient
        # The daily planner now creates "Farm chores" tasks with skill_override=auto_farm_chores
        # which triggers _batch_farm_chores() for reliable batch execution
        #
        # if HAS_CELL_FARMING and not self.cell_coordinator:
        #     ... (removed - see git history for original code)

        # Get current game state for target generation
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return False

        data = state.get("data") or state
        location = data.get("location") or {}
        location_name = location.get("name", "")
        # Extract FRESH player position from state (not cached)
        player = data.get("player") or {}
        tile_x = player.get("tileX")
        tile_y = player.get("tileY")
        player_pos = (tile_x, tile_y) if tile_x is not None and tile_y is not None else self.last_position or (0, 0)

        # Get next task from resolved queue
        resolved_queue = getattr(self.daily_planner, 'resolved_queue', [])
        if not resolved_queue:
            # Session 124: INFO level to see this
            logging.info("🎯 _try_start_daily_task: no resolved queue, falling back to legacy")
            return self._try_start_daily_task_legacy()  # Fallback to old method

        logging.info(f"🎯 _try_start_daily_task: {len(resolved_queue)} items in resolved queue")

        # Find next task that can be executed
        for i, resolved_task in enumerate(resolved_queue):
            # Get task info (handle both ResolvedTask objects and dicts)
            if hasattr(resolved_task, 'task_type'):
                task_type = resolved_task.task_type
                task_id = resolved_task.original_task_id
                description = resolved_task.description
                is_prereq = resolved_task.is_prereq
                task_params = resolved_task.params if hasattr(resolved_task, 'params') else {}
            else:
                task_type = resolved_task.get('task_type', 'unknown')
                task_id = resolved_task.get('original_task_id', f'resolved_{i}')
                description = resolved_task.get('description', task_type)
                is_prereq = resolved_task.get('is_prereq', False)
                task_params = resolved_task.get('params', {})

            # Session 123: Check resolved task's skill_override first (from prereq resolver)
            resolved_skill_override = None
            if hasattr(resolved_task, 'skill_override'):
                resolved_skill_override = resolved_task.skill_override
            elif isinstance(resolved_task, dict):
                resolved_skill_override = resolved_task.get('skill_override')

            # Check if already completed
            if task_id and not task_id.endswith('_prereq'):
                daily_task = self.daily_planner._find_task(task_id)
                # Session 122: Debug logging for task flow
                logging.info(f"🔍 Task check: id={task_id}, type={task_type}, daily_task={daily_task is not None}, status={daily_task.status if daily_task else 'N/A'}, skill_override={resolved_skill_override or getattr(daily_task, 'skill_override', None) if daily_task else resolved_skill_override}")

                if daily_task and daily_task.status in ("completed", "skipped"):
                    continue

                # SKILL_OVERRIDE: Batch operations bypass TaskExecutor entirely
                # Check both resolved task and daily task for skill_override
                batch_skill = resolved_skill_override or (daily_task.skill_override if daily_task and hasattr(daily_task, 'skill_override') else None)
                if batch_skill:
                    logging.info(f"🚀 BATCH MODE: Task {task_id} uses skill_override={batch_skill}")

                    # Mark task as started
                    self.daily_planner.start_task(task_id)

                    # Store for async execution - caller will await
                    self._pending_batch = {
                        "skill": batch_skill,
                        "task_id": task_id,
                        "queue": resolved_queue,
                        "queue_index": i
                    }
                    return True  # Signal batch is pending

            # Check location requirements
            # Farm tasks need to be on Farm; navigation tasks can be anywhere
            FARM_TASKS = {"water_crops", "harvest_crops", "plant_seeds", "clear_debris", "till_soil", "refill_watering_can"}
            if task_type in FARM_TASKS and location_name != "Farm":
                logging.debug(f"🎯 Task {task_type} needs Farm, currently at {location_name}")
                # Queue navigate action to Farm
                # For now, skip - unified_agent should handle this
                continue

            # Try to start this task
            params_info = f" params={task_params}" if task_params else ""
            logging.info(f"🎯 Starting resolved task: {task_type} ({'prereq' if is_prereq else 'main'}){params_info}")

            # Session 119: DISABLED cell farming - batch mode (auto_farm_chores) handles planting
            # Cell farming was a legacy fallback that caused VLM phantom failures
            # if task_type == "plant_seeds" and HAS_CELL_FARMING and not is_prereq:
            #     started = self._start_cell_farming(state, player_pos, task_id, description)
            #     ...

            has_targets = self.task_executor.set_task(
                task_id=task_id,
                task_type=task_type,
                game_state=state,
                player_pos=player_pos,
                task_params=task_params,
            )

            if has_targets:
                # Mark task as in progress
                if not is_prereq and task_id:
                    try:
                        self.daily_planner.start_task(task_id)
                    except Exception:
                        pass

                logging.info(f"🎯 Started: {description} ({self.task_executor.progress.total_targets} targets)")
                return True
            else:
                # No targets - mark complete and try next
                logging.info(f"✅ No targets for {task_type} - moving to next")
                if not is_prereq and task_id:
                    try:
                        self.daily_planner.complete_task(task_id)
                    except Exception:
                        pass
                # Remove from resolved queue
                resolved_queue.pop(i)
                return self._try_start_daily_task()  # Recurse to try next

        return False

    def _try_start_daily_task_legacy(self) -> bool:
        """
        Legacy fallback: Use keyword matching when PrereqResolver not available.
        """
        state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if not state:
            return False

        data = state.get("data") or state
        location = data.get("location") or {}
        location_name = location.get("name", "")
        if location_name != "Farm":
            return False

        # Extract FRESH player position from state (not cached)
        player = data.get("player") or {}
        tile_x = player.get("tileX")
        tile_y = player.get("tileY")
        player_pos = (tile_x, tile_y) if tile_x is not None and tile_y is not None else self.last_position or (0, 0)

        CATEGORY_TO_TASK = {
            "water": "water_crops",
            "harvest": "harvest_crops",
            "plant": "plant_seeds",
            "clear": "clear_debris",
            "till": "till_soil",
        }

        for task in self.daily_planner.tasks:
            if task.status != "pending":
                continue

            task_lower = task.description.lower()
            task_type = None

            for keyword, executor_task in CATEGORY_TO_TASK.items():
                if keyword in task_lower:
                    task_type = executor_task
                    break

            if not task_type:
                continue

            has_targets = self.task_executor.set_task(
                task_id=task.id,
                task_type=task_type,
                game_state=state,
                player_pos=player_pos,
            )

            if has_targets:
                try:
                    self.daily_planner.start_task(task.id)
                except Exception:
                    pass
                logging.info(f"🎯 Started (legacy): {task_type}")
                return True
            else:
                try:
                    self.daily_planner.complete_task(task.id)
                except Exception:
                    pass

        return False

    def _get_task_executor_context(self) -> str:
        """Get context string for VLM about current task execution."""
        if not self.task_executor:
            return ""

        if self.task_executor.is_active():
            context = self.task_executor.get_context_for_vlm()

            # Add event context if there's a commentary event
            if self._commentary_event:
                context = f"💬 EVENT: {self._commentary_event}\n{context}"
                # Clear the event after using it
                self._commentary_event = None

            # CRITICAL: When TaskExecutor owns execution, VLM is observer only
            if self._task_executor_commentary_only:
                context = f"""🎯 TASK EXECUTOR ACTIVE - YOU ARE IN OBSERVER MODE
{context}

⚠️ IMPORTANT: TaskExecutor is handling this task. Your role:
1. OBSERVE what's happening on screen
2. COMMENT on progress (entertaining inner monologue)
3. Say "PAUSE" if you see a SERIOUS problem (stuck, wrong location, obstacle)
4. DO NOT output actions - they will be IGNORED

If everything looks normal, just provide commentary. Only say PAUSE if something is actually wrong."""

            return context

        return ""

    def _fix_active_popup(self, actions: List[Action]) -> List[Action]:
        """
        Override: If menu/event is active, handle it before continuing.
        This handles level-up screens, shipping summaries, dialogue boxes, etc.

        Special case: Sleep confirmation dialog should be CONFIRMED, not dismissed.
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

            # DIALOGUEBOX FIRST: Handle Yes/No questions (pet adoption, sleep, etc.)
            # This takes priority because events often show DialogueBox for choices
            if menu == "DialogueBox":
                recent_bed_action = any(
                    "bed" in a.lower() or "sleep" in a.lower()
                    for a in self.recent_actions[-3:]
                )
                if recent_bed_action:
                    logging.info(f"🛏️ SLEEP DIALOG: Confirming sleep (Yes)")
                elif event:
                    logging.info(f"🐕 EVENT DIALOG: {event} - answering Yes")
                else:
                    logging.info(f"📋 DIALOG BOX: Confirming (selecting Yes/first option)")
                return [Action("confirm_dialog", {}, "Confirm dialog")]

            # EVENTS: Advance through them naturally (don't skip!)
            # Events include cutscenes, character introductions, etc.
            if event:
                logging.info(f"🎬 EVENT: {event} - advancing (not skipping)")
                return [Action("confirm_dialog", {}, f"Advance event: {event}")]

            # DIALOGUE: Advance through dialogue (confirm/click through)
            if dialogue_up:
                logging.info(f"💬 DIALOGUE: Advancing dialogue")
                return [Action("confirm_dialog", {}, "Advance dialogue")]

            # OTHER MENUS: Dismiss them (inventory, shop when done, etc.)
            if menu:
                logging.info(f"🚫 MENU: {menu} active → dismiss_menu")
                return [Action("dismiss_menu", {}, f"Dismiss {menu}")]

            # PAUSED: Just unpause
            if paused:
                logging.info(f"⏸️ PAUSED: Unpausing")
                return [Action("dismiss_menu", {}, "Unpause")]

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

        # If in FarmHouse, override to warp to Farm first (with loop protection)
        if location == "FarmHouse":
            now = time.time()
            if self._pending_warp_location == "Farm":
                if now - self._pending_warp_time < 3.0:
                    logging.debug("📦 Warp to Farm pending, waiting...")
                    return []  # Wait for warp
                else:
                    self._pending_warp_location = None  # Timeout, retry

            logging.info(f"📦 OVERRIDE: Have {total_to_ship} sellables in FarmHouse → warp to Farm")
            self._pending_warp_location = "Farm"
            self._pending_warp_time = now
            return [Action("warp", {"location": "Farm"}, f"Auto-warp to ship {total_to_ship} crops")]

        # If adjacent to shipping bin (dist <= 2 to be safe), ship immediately
        if dist <= 2:
            face_dir = "north" if dy < 0 else "south" if dy > 0 else "west" if dx < 0 else "east"
            logging.info(f"📦 OVERRIDE: At shipping bin (dist={dist}) → ship_item")
            return [Action("face", {"direction": face_dir}, "Face bin"),
                    Action("ship_item", {}, f"Ship {total_to_ship} crops")]

        # AGGRESSIVE: Override ANY action to move toward bin when we have sellables
        original_action = actions[0].action_type if actions else "unknown"

        # Calculate primary and secondary directions to shipping bin
        if abs(dy) > abs(dx):
            primary = "north" if dy < 0 else "south"
            secondary = "east" if dx > 0 else "west" if dx != 0 else None
            primary_tiles = min(abs(dy), 5)
            secondary_tiles = min(abs(dx), 5) if dx != 0 else 0
        else:
            primary = "east" if dx > 0 else "west"
            secondary = "north" if dy < 0 else "south" if dy != 0 else None
            primary_tiles = min(abs(dx), 5)
            secondary_tiles = min(abs(dy), 5) if dy != 0 else 0

        direction = primary
        tiles = primary_tiles

        # Check surroundings to avoid blocked directions
        surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None
        if surroundings:
            data = surroundings.get("data") or surroundings
            directions = data.get("directions", {})
            primary_info = directions.get(primary, {})

            # If primary blocked, try secondary
            if not primary_info.get("clear", True):
                if secondary:
                    secondary_info = directions.get(secondary, {})
                    if secondary_info.get("clear", True):
                        direction = secondary
                        tiles = secondary_tiles if secondary_tiles else 1
                        logging.info(f"📦 Primary direction {primary} blocked, using {direction}")
                    else:
                        # Both blocked - try perpendicular directions
                        perpendiculars = ["north", "south"] if primary in ["east", "west"] else ["east", "west"]
                        for perp in perpendiculars:
                            perp_info = directions.get(perp, {})
                            if perp_info.get("clear", True):
                                direction = perp
                                tiles = min(perp_info.get("tilesUntilBlocked", 5), 3)
                                logging.info(f"📦 Both directions blocked, using perpendicular {direction}")
                                break
                        else:
                            # All directions blocked - return original actions
                            logging.info(f"📦 All directions blocked, letting VLM handle navigation")
                            return actions
                else:
                    # No secondary and primary blocked - return original
                    logging.info(f"📦 Direction {primary} blocked with no alternative")
                    return actions

        logging.info(f"📦 OVERRIDE: VLM wanted '{original_action}' but have {total_to_ship} sellables → move {direction} toward bin (dist={dist})")
        return [Action("move", {"direction": direction, "tiles": tiles}, f"Move to ship {total_to_ship} crops")]

    def _fix_no_seeds(self, actions: List[Action]) -> List[Action]:
        """
        Override: If we have no seeds and Pierre's is open, force go_to_pierre.
        If already at Pierre's, force buying optimal seeds from crop advisor.
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
                    seed_skill, seed_reason = get_recommended_seed_skill(state)
                    logging.info(f"🛒 OVERRIDE: In SeedShop with no seeds → {seed_skill} - {seed_reason} (have {money}g)")
                    return [Action(seed_skill, {}, f"Buy {seed_reason} at Pierre's ({money}g available)")]
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

        Session 119: Improved detection - also triggers on BLOCKED actions at edge.
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
        # Edges are: east > 75 (water), south > 50 (south water), north < 8 (north edge), west < 6
        # Session 119: Expanded edge zones to catch more edge cases
        at_edge = player_x > 73 or player_x < 7 or player_y > 48 or player_y < 9

        if not at_edge:
            return actions  # Not at edge

        # Session 119: Check if surrounded by water/impassable (worse than just being at edge)
        surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None
        blocked_dirs = 0
        if surroundings:
            dirs = surroundings.get("directions", {})
            for d in ["north", "south", "east", "west"]:
                dir_info = dirs.get(d, {})
                if not dir_info.get("clear", True) and dir_info.get("tilesUntilBlocked", 99) <= 1:
                    blocked_dirs += 1

        # Check if we're repeating stuck-prone actions
        stuck_actions = {"clear_stone", "clear_wood", "clear_weeds", "clear_debris",
                         "chop_tree", "mine_boulder", "break_stone", "move",
                         "plant_seed", "till_soil"}  # Session 119: Added plant_seed, till_soil
        first_action = actions[0].action_type if actions else ""

        if first_action not in stuck_actions:
            return actions  # Not a stuck-prone action

        # Check repetition in recent history (any stuck action OR BLOCKED messages)
        # Session 119: Also count BLOCKED messages as stuck indicators
        repeat_count = sum(1 for a in self.recent_actions[-5:]
                          if any(d in a for d in stuck_actions) or "BLOCKED" in a)

        # Session 119: Lower threshold if surrounded (2 instead of 3)
        threshold = 2 if blocked_dirs >= 2 else 3
        if repeat_count < threshold:
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

        # Fetch surroundings early - needed for daily planning (water locations)
        if hasattr(self.controller, "get_surroundings"):
            try:
                self.last_surroundings = self.controller.get_surroundings()
            except Exception:
                self.last_surroundings = None

        # Daily planning - trigger new day plan when day changes
        if self.daily_planner:
            time_data = state.get("time", {})
            day = time_data.get("day", 0)
            season = time_data.get("season", "spring")
            if day > 0 and day != self._last_planned_day:
                logging.info(f"🌅 New day detected: Day {day} - generating plan...")

                # CRITICAL: Reset task executor to prevent old tasks from continuing
                if self.task_executor:
                    logging.info("🔄 Resetting task executor for new day")
                    self.task_executor.clear()
                if hasattr(self, 'resolved_task_queue'):
                    self.resolved_task_queue = []
                if self.cell_coordinator:
                    self.cell_coordinator = None

                # Save previous day's summary BEFORE starting new day
                # This handles the case where agent passed out (didn't call go_to_bed)
                if self._last_planned_day > 0:
                    logging.info(f"📝 Saving Day {self._last_planned_day} summary (recovery from pass-out or missed save)")
                    self._save_daily_summary()
                # Pass VLM reasoning function if available
                reason_fn = self._vlm_reason if hasattr(self, '_vlm_reason') else None
                # Get farm state for planning (works even when in FarmHouse)
                farm_state = None
                if hasattr(self.controller, 'get_farm'):
                    farm_state = self.controller.get_farm()
                # Pass surroundings for water location detection
                plan_summary = self.daily_planner.start_new_day(
                    day, season, state, reason_fn, farm_state, self.last_surroundings
                )
                logging.info(f"📋 Daily plan:\n{plan_summary}")
                self._last_planned_day = day

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

    def _load_cell_stats(self) -> Dict[str, Any]:
        """
        Load persisted cell farming stats from file.
        
        Used when cell_coordinator is None (e.g., separate agent instance
        running go_to_bed after farming session ended).
        
        Returns:
            Dict with cells_completed, cells_skipped, skip_reasons, etc.
            Empty dict if file not found.
        """
        try:
            with open("logs/cell_farming_stats.json") as f:
                stats = json.load(f)
                logging.info(f"📊 Loaded persisted stats: {stats.get('cells_completed', 0)} completed, "
                           f"{stats.get('cells_skipped', 0)} skipped")
                return stats
        except FileNotFoundError:
            logging.debug("No persisted cell stats found")
            return {}
        except json.JSONDecodeError as e:
            logging.warning(f"Failed to parse cell stats: {e}")
            return {}

    def _save_daily_summary(self) -> None:
        """
        Save end-of-day summary for morning planning.

        Called before go_to_bed to persist:
        - Cells planted/watered/cleared
        - Cells skipped with reasons
        - Energy stats
        - Lessons learned
        """
        import json
        from pathlib import Path

        summary = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "day": 0,
            "season": "Spring",
            "year": 1,
        }

        # Get game state for day/season
        if self.last_state:
            player = self.last_state.get("player", {})
            location = self.last_state.get("location", {})
            summary["day"] = location.get("day") or self.last_state.get("day", 0)
            summary["season"] = location.get("season") or self.last_state.get("season", "Spring")
            summary["year"] = location.get("year") or self.last_state.get("year", 1)
            summary["energy_remaining"] = player.get("stamina", 0)
            summary["max_energy"] = player.get("maxStamina", 270)
            summary["gold"] = player.get("money", 0)

        # Get cell farming stats from coordinator or persisted file
        if self.cell_coordinator:
            cell_summary = self.cell_coordinator.get_daily_summary()
            summary["cells_completed"] = cell_summary.get("cells_completed", 0)
            summary["cells_skipped"] = cell_summary.get("cells_skipped", 0)
            summary["skip_reasons"] = cell_summary.get("skip_reasons", {})
            summary["total_cells"] = cell_summary.get("total_cells", 0)
            summary["completion_rate"] = cell_summary.get("completion_rate", 0)
        else:
            # No coordinator - load from persisted stats file
            persisted = self._load_cell_stats()
            summary["cells_completed"] = persisted.get("cells_completed", 0)
            summary["cells_skipped"] = persisted.get("cells_skipped", 0)
            summary["skip_reasons"] = persisted.get("skip_reasons", {})

        # Add session stats
        summary["actions_executed"] = self.action_count
        summary["actions_failed"] = self.action_fail_count
        summary["crops_watered"] = self.crops_watered_count
        summary["crops_harvested"] = self.crops_harvested_count

        # Derive lessons from skip reasons
        lessons = []
        skip_reasons = summary.get("skip_reasons", {})
        if skip_reasons:
            # Count by reason type
            reason_counts: Dict[str, int] = {}
            for reason in skip_reasons.values():
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            for reason, count in reason_counts.items():
                lessons.append(f"{count} cells skipped: {reason}")
        summary["lessons"] = lessons

        # Derive goals for tomorrow
        next_goals = []
        if summary.get("cells_skipped", 0) > 0:
            next_goals.append(f"Retry {summary['cells_skipped']} skipped cells (avoid blocked areas)")
        if summary.get("cells_completed", 0) > 0:
            next_goals.append(f"Water {summary['cells_completed']} planted crops")
        summary["next_day_goals"] = next_goals

        # Save to file
        summary_path = Path("logs/daily_summary.json")
        summary_path.parent.mkdir(parents=True, exist_ok=True)

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        logging.info(f"📊 Daily summary saved: {summary['cells_completed']} planted, "
                    f"{summary['cells_skipped']} skipped, {len(lessons)} lessons")

    def _send_commentary(self, action: Action, success: bool) -> None:
        """Push commentary event to background worker (non-blocking)."""
        if not self.commentary_worker:
            return

        # Sync UI settings to worker (cached - only fetch every 30s)
        now = time.time()
        if self.ui_enabled and self.ui:
            settings_refreshed = False
            if now - self._commentary_settings_last_fetch > self._commentary_settings_ttl:
                try:
                    self._commentary_settings_cache = self.ui.get_commentary()
                    self._commentary_settings_last_fetch = now
                    settings_refreshed = True
                except Exception:
                    pass  # Don't block agent on UI failures

            # Only apply settings to worker when refreshed or first time (Session 72 fix)
            if self._commentary_settings_cache and (settings_refreshed or not self._commentary_settings_applied):
                self.commentary_worker.set_settings(
                    tts_enabled=self._commentary_settings_cache.get("tts_enabled"),
                    voice=self._commentary_settings_cache.get("voice") or self._commentary_settings_cache.get("personality"),
                    volume=self._commentary_settings_cache.get("volume"),
                    coqui_voice=self._commentary_settings_cache.get("coqui_voice"),
                )
                self._commentary_settings_applied = True
            
        # Only push if there's a NEW monologue - avoids flooding queue with duplicates
        # VLM generates new monologue every ~6-10s, but _send_commentary is called after every action (~0.3s)
        # Without this check, queue fills with 20-30 identical events per VLM tick
        current_mood = self.last_mood or ""
        if not current_mood:
            logging.debug(f"📢 Commentary skip: no mood")
            return
        if current_mood == self._last_pushed_monologue:
            logging.debug(f"📢 Commentary skip: same as last push")
            return
        
        # Rate limit: don't push too frequently (TTS can't keep up)
        now = time.time()
        time_since_last = now - self._last_commentary_push_time
        if time_since_last < self._min_commentary_interval:
            logging.debug(f"📢 Commentary skip: rate limited ({time_since_last:.1f}s < {self._min_commentary_interval}s)")
            return

        # Build minimal state for commentary
        state = self.last_state or {}
        state_data = {
            "stats": {
                "crops_harvested_count": self.crops_harvested_count,
                "crops_watered_count": self.crops_watered_count,
                "distance_traveled": self.distance_traveled,
                "action_count": self.action_count,
            },
            "location": state.get("location", {}).get("name", ""),
            "crops": state.get("location", {}).get("crops", []),
        }

        # Push to worker queue (non-blocking)
        self.commentary_worker.push(
            action_type=action.action_type,
            state=state_data,
            vlm_monologue=current_mood,
        )
        self._last_pushed_monologue = current_mood
        self._last_commentary_push_time = time.time()
        logging.info(f"📢 Commentary pushed: {current_mood[:50]}...")

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
        
        # Tool slots for reference (from constants)
        tool_slots = TOOL_SLOTS
        
        # --- PRIORITY 1: Empty Watering Can ---
        if water_left <= 0 and unwatered:
            nearest_water = data.get("nearestWater")
            if nearest_water:
                water_dir = nearest_water.get("direction", "nearby")
                water_dist = nearest_water.get("distance", "?")
                hints.append(f"⚠️ WATERING CAN EMPTY! Use go_refill_watering_can (water {water_dist} tiles {water_dir})")
            else:
                hints.append("⚠️ WATERING CAN EMPTY! Use go_refill_watering_can")
        
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
                hints.append(f"⚠️ CROP HERE! Don't use {current_tool}! Use water_crop skill")
            elif water_left > 0:
                if "Watering" in current_tool:
                    hints.append(f"💧 PLANTED - use_tool to water! ({water_left}/{water_max})")
                else:
                    hints.append(f"💧 PLANTED - Use water_crop skill ({water_left}/{water_max})")
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
                hints.append("📍 CLEAR - Use till_soil skill to prepare ground")
        
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

        # Add Elias's character context (for personality continuity)
        if self.rusty_memory:
            elias_context = self.rusty_memory.get_context_for_prompt()
            if elias_context:
                result += f"\n\n--- ELIAS ---\n{elias_context}"

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

                        # Early skip check: have we already given up on this blocker?
                        position = surroundings.get("position", {})
                        px, py = position.get("x", 0), position.get("y", 0)
                        loc_name = self.last_state.get("location", {}).get("name", "Farm") if self.last_state else "Farm"
                        dx, dy = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0), "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
                        target_x, target_y = px + dx, py + dy
                        blocker_key = (loc_name, target_x, target_y, blocker)

                        if blocker_key in self._skip_blockers:
                            # Already know this is impassable, skip immediately
                            logging.debug(f"⏭️ Known impassable: {blocker} at ({target_x},{target_y})")
                            self.recent_actions.append(f"SKIP: {blocker} at ({target_x},{target_y}) (known impassable)")
                            self.recent_actions = self.recent_actions[-10:]
                            # Don't try to execute this move, let VLM pick alternative
                            return

                        # Check if blocker is clearable debris
                        # Use FarmSurveyor for tool slots, add tool names for logging
                        from planning.farm_surveyor import FarmSurveyor
                        TOOL_NAMES = {0: "AXE", 3: "PICKAXE", 4: "SCYTHE"}

                        # Build clearable dict from surveyor + extras
                        CLEARABLE_DEBRIS = {
                            k: (TOOL_NAMES.get(v, "TOOL"), v)
                            for k, v in FarmSurveyor.DEBRIS_TOOL_SLOTS.items()
                        }
                        # Add variants the surveyor doesn't track
                        CLEARABLE_DEBRIS.update({
                            "Tree Stump": ("AXE", 0),  # Large stump variant
                            "Boulder": ("PICKAXE", 3),
                            "Large Rock": ("PICKAXE", 3),  # May require upgraded pick
                        })

                        if blocker in CLEARABLE_DEBRIS:
                            # Get blocker position for failure tracking
                            position = surroundings.get("position", {})
                            px, py = position.get("x", 0), position.get("y", 0)
                            loc_name = self.last_state.get("location", {}).get("name", "Farm") if self.last_state else "Farm"
                            # Calculate target tile based on direction
                            dx, dy = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0), "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
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

                        # Non-clearable obstacle (or gave up) - track it so we don't loop
                        position = surroundings.get("position", {})
                        px, py = position.get("x", 0), position.get("y", 0)
                        loc_name = self.last_state.get("location", {}).get("name", "Farm") if self.last_state else "Farm"
                        dx, dy = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0), "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
                        target_x, target_y = px + dx, py + dy
                        blocker_key = (loc_name, target_x, target_y, blocker)

                        # Add to skip set if not already there (prevents infinite loops on non-clearable)
                        if blocker_key not in self._skip_blockers:
                            self._skip_blockers.add(blocker_key)
                            logging.warning(f"⚠️ Marking {blocker} at ({target_x},{target_y}) as impassable")
                            # Track for tool upgrade suggestions
                            inventory = self.last_state.get("inventory", []) if self.last_state else []
                            tracker = get_upgrade_tracker()
                            if tracker:
                                upgrade_suggestion = tracker.record_blocked(blocker, inventory)
                                if upgrade_suggestion:
                                    logging.warning(f"🔧 TOOL UPGRADE SUGGESTED: {upgrade_suggestion}")

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

            # Save daily summary before going to bed
            if action.action_type in ("go_to_bed", "sleep"):
                logging.info("🛏️ Going to bed - saving daily summary...")
                self._save_daily_summary()

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

        # STEP 1: Handle completed tasks FIRST (remove from queue before starting new)
        # This runs when state is TASK_COMPLETE - cleanup must happen before starting next task
        if self.task_executor and self.task_executor.is_complete() and self.task_executor.progress:
            task_id = self.task_executor.progress.task_id
            task_type = self.task_executor.progress.task_type
            completed = self.task_executor.progress.completed_targets
            total = self.task_executor.progress.total_targets
            logging.info(f"✅ Task complete: {task_type} ({completed}/{total} targets)")

            # Mark task complete in daily planner and remove from resolved queue
            if self.daily_planner:
                try:
                    self.daily_planner.complete_task(task_id)
                    logging.info(f"📋 Daily planner: marked {task_id} complete")
                    # Remove from resolved queue to prevent re-execution
                    resolved_queue = getattr(self.daily_planner, 'resolved_queue', [])
                    # Log queue IDs (handle both ResolvedTask objects and dicts)
                    rt_ids = [getattr(rt, 'original_task_id', None) or (rt.get('original_task_id', '?') if isinstance(rt, dict) else '?') for rt in resolved_queue[:5]]
                    logging.info(f"📋 Queue before removal: {rt_ids}")
                    removed = False
                    for i, rt in enumerate(resolved_queue):
                        rt_id = rt.original_task_id if hasattr(rt, 'original_task_id') else rt.get('original_task_id', '')
                        if rt_id == task_id:
                            resolved_queue.pop(i)
                            logging.info(f"📋 Removed {task_id} from resolved queue ({len(resolved_queue)} remaining)")
                            removed = True
                            break
                    if not removed:
                        logging.warning(f"⚠️ Could not find {task_id} in resolved queue to remove!")
                except Exception as e:
                    logging.warning(f"Failed to mark task complete: {e}")

            # Reset executor state to IDLE so next task can start
            self.task_executor.state = TaskState.IDLE
            self.task_executor.progress = None
            logging.info(f"📋 TaskExecutor reset to IDLE, ready for next task")

        # STEP 1b: Handle BLOCKED tasks (0 targets, need to retry from different position)
        # This happens when water task is started from FarmHouse - pathfinding fails
        if self.task_executor and self.task_executor.is_blocked() and self.task_executor.progress:
            task_id = self.task_executor.progress.task_id
            task_type = self.task_executor.progress.task_type
            
            # Check if we're now on Farm (can retry)
            current_loc = self.last_state.get("location", {}).get("name", "") if self.last_state else ""
            
            if current_loc == "Farm":
                # We're on Farm now - retry the blocked task
                logging.info(f"🔄 Retrying blocked task {task_type} - now on Farm")
                self.task_executor.state = TaskState.IDLE
                self.task_executor.progress = None
                # Let _try_start_daily_task() pick it up again
            else:
                # Still not on Farm - skip to next task
                logging.info(f"⏭️ Task {task_type} blocked (not on Farm yet), trying next task")
                # Don't mark as failed - it might work later
                self.task_executor.state = TaskState.IDLE
                self.task_executor.progress = None

        # STEP 2a: Day 1 clearing mode (systematic, no VLM)
        # Check if we should be in Day 1 clearing mode
        game_state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
        if game_state:
            data = game_state.get("data") or game_state
            time_data = data.get("time", {})
            current_day = time_data.get("day", 0)
            location = data.get("location", {}).get("name", "")

            if current_day == 1:
                # Warp to Farm if in FarmHouse (use pending warp to prevent loop)
                if location == "FarmHouse":
                    if self._pending_warp_location != "Farm":
                        logging.info("🧹 Day 1: Warping to Farm for clearing")
                        self._pending_warp_location = "Farm"
                        self._pending_warp_time = time.time()
                        self.action_queue.append(Action(
                            action_type="warp",
                            params={"location": "Farm"},
                            description="Day 1: Warp to Farm for clearing"
                        ))
                    return
                elif location == "Farm":
                    self._pending_warp_location = None  # Clear pending warp
                    if not self._day1_clearing_active:
                        self._start_day1_clearing()

        if self._day1_clearing_active:
            # Run VLM commentary every 25 seconds during clearing
            now = time.time()
            time_since_vlm = now - getattr(self, '_last_vlm_time', 0)

            if time_since_vlm < 25:
                # Process clearing
                clear_action = self._process_day1_clearing()
                if clear_action:
                    self.action_queue.append(clear_action)
                    self.vlm_status = f"Day 1 clearing: {self._day1_tiles_cleared} tiles cleared"
                    self._send_ui_status()
                    return  # Action queued - skip VLM this tick
            else:
                # Let VLM run for commentary, then resume clearing
                logging.debug("🧹 Day 1: Allowing VLM commentary")
                # VLM will run below, _last_vlm_time updated there

        # STEP 2b: Cell-by-cell farming execution (if active, Day 2+)
        if self.cell_coordinator and not self.cell_coordinator.is_complete():
            cell_action = self._process_cell_farming()
            if cell_action:
                self.action_queue.append(cell_action)
                self.vlm_status = f"Cell farming: {self.cell_coordinator.get_status_summary()}"
                self._send_ui_status()
                return  # Action queued - skip VLM this tick
            # No action = waiting for pathfinding - allow VLM commentary to run

        # STEP 2b: Try to start a task from daily planner if executor is idle
        # Skip task executor on Day 1 - Day 1 clearing handles everything
        # Session 124: Diagnostic logging BEFORE executor check
        logging.info(f"🔍 STEP 2b: day1_clearing={self._day1_clearing_active}, has_executor={self.task_executor is not None}, has_planner={self.daily_planner is not None}")
        if self._day1_clearing_active:
            pass  # Day 1 clearing is exclusive
        elif self.task_executor:
            executor_active = self.task_executor.is_active()
            executor_state = self.task_executor.state.value if hasattr(self.task_executor.state, 'value') else str(self.task_executor.state)
            if executor_active:
                logging.debug(f"📋 Task executor active: state={executor_state}")
            elif not executor_active:
                # Session 123: Debug logging for task queue
                if self.daily_planner:
                    queue = getattr(self.daily_planner, 'resolved_queue', [])
                    pending = [t for t in self.daily_planner.tasks if t.status == "pending"]
                    logging.info(f"📋 Task queue: {len(queue)} resolved, {len(pending)} pending tasks")
                    for t in pending[:3]:
                        logging.info(f"   📋 Pending: {t.id} ({t.category}) skill_override={getattr(t, 'skill_override', None)}")
                if self._try_start_daily_task():
                    # Check if batch operation is pending
                    if hasattr(self, '_pending_batch') and self._pending_batch:
                        batch = self._pending_batch
                        self._pending_batch = None  # Clear before execution

                        logging.info(f"🚀 Executing batch: {batch['skill']}")
                        self.vlm_status = f"Batch: {batch['skill']}"
                        self._send_ui_status()

                        try:
                            success = await self.execute_skill(batch['skill'], {})
                            if success:
                                logging.info(f"✅ Batch {batch['skill']} completed")
                                self.daily_planner.complete_task(batch['task_id'])
                            else:
                                logging.warning(f"⚠️ Batch {batch['skill']} returned False")
                            # Remove from queue
                            queue = batch['queue']
                            for j, rt in enumerate(queue):
                                rt_id = rt.original_task_id if hasattr(rt, 'original_task_id') else rt.get('original_task_id', '')
                                if rt_id == batch['task_id']:
                                    queue.pop(j)
                                    break
                        except Exception as e:
                            logging.error(f"❌ Batch {batch['skill']} failed: {e}")

                        return  # Done with this tick
                    # else: Task started - executor will handle it next iteration

        if self.task_executor and self.task_executor.is_active() and not self._day1_clearing_active:
            # Get FRESH game state for position and precondition checks
            game_state = self.controller.get_state() if hasattr(self.controller, "get_state") else None
            surroundings = self.controller.get_surroundings() if hasattr(self.controller, "get_surroundings") else None

            # Extract FRESH player position from game state (not cached last_position)
            if game_state:
                data = game_state.get("data") or game_state
                player = data.get("player") or {}
                tile_x = player.get("tileX")
                tile_y = player.get("tileY")
                if tile_x is not None and tile_y is not None:
                    player_pos = (tile_x, tile_y)
                else:
                    player_pos = self.last_position or (0, 0)
            else:
                player_pos = self.last_position or (0, 0)

            # Get next deterministic action from executor (checks preconditions first)
            executor_action = self.task_executor.get_next_action(player_pos, surroundings, game_state)
            
            if executor_action:
                # Precondition actions (e.g., refill watering can) must execute immediately
                # Don't let VLM override these - they're prerequisites for the task
                if self.task_executor.state == TaskState.NEEDS_REFILL:
                    action = Action(
                        action_type=executor_action.action_type,
                        params=executor_action.params,
                        description=executor_action.reason
                    )
                    self.action_queue.append(action)
                    logging.info(f"🎯 TaskExecutor (precondition): {executor_action.action_type} → {executor_action.reason}")
                    self.vlm_status = f"Precondition: {executor_action.action_type}"
                    self._send_ui_status()
                    return  # Execute precondition immediately, skip VLM

                # Check if VLM should provide commentary this tick (event-driven)
                should_comment, event_context = self.task_executor.should_vlm_comment(self._vlm_commentary_interval)

                if should_comment:
                    if event_context:
                        logging.info(f"🎭 Event-driven commentary: {event_context}")
                        # Store event context for VLM prompt injection
                        self._commentary_event = event_context
                    else:
                        logging.info(f"🎭 Fallback commentary: tick {self.task_executor.tick_count}")
                        self._commentary_event = None
                    # Store executor action - VLM will run in commentary-only mode
                    self._pending_executor_action = Action(
                        action_type=executor_action.action_type,
                        params=executor_action.params,
                        description=executor_action.reason
                    )
                    self._task_executor_commentary_only = True  # VLM observes, doesn't generate actions
                    logging.info(f"🎯 TaskExecutor owns execution, VLM commentary-only: {executor_action.action_type}")
                    # Continue to VLM for observation/commentary (don't return)
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
                # No executor action - VLM should run normally
                self._task_executor_commentary_only = False  # Ensure flag is cleared
                # Note: Task completion handling is now done in STEP 1 above (before is_active check)

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
            skill_context = self._get_skill_context(self.goal)  # Session 122: Pass goal for prioritization
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
            self._last_vlm_time = time.time()  # Track for Day 1 clearing commentary timing
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
                    # Send to UI - UI's JavaScript handles TTS for messages
                    self._ui_safe(self.ui.send_message, "agent", reply_text)
                self.awaiting_user_reply = False

            # Queue actions (with post-processing filters)
            if self.config.mode in ("single", "splitscreen"):
                # HARD BEDTIME CHECK - interrupts EVERYTHING including TaskExecutor
                _bedtime_forced = False
                if self.last_state:
                    _hour = self.last_state.get("time", {}).get("hour", 6)
                    if _hour >= 23:
                        logging.warning(f"🛏️ BEDTIME OVERRIDE: Hour {_hour} >= 23, forcing go_to_bed (interrupting all tasks)")
                        # Clear TaskExecutor state
                        if self.task_executor:
                            self.task_executor.clear()
                        self._task_executor_commentary_only = False
                        self._pending_executor_action = None
                        self.action_queue = [Action("go_to_bed", {}, "Auto-bed (very late override)")]
                        _bedtime_forced = True

                # Check if VLM said PAUSE (emergency interrupt) - skip if bedtime forced
                vlm_pause = "PAUSE" in (result.reasoning or "").upper() if not _bedtime_forced else False
                if _bedtime_forced:
                    # Already handled above - just log the action
                    logging.info(f"   [0] go_to_bed: {{}} (bedtime override)")
                elif vlm_pause and self._task_executor_commentary_only:
                    logging.warning(f"⚠️ VLM requested PAUSE: {result.reasoning[:100]}")
                    # Clear task executor state - VLM detected a problem
                    if self.task_executor:
                        self.task_executor.clear()
                    self._task_executor_commentary_only = False
                    self._pending_executor_action = None
                    # Let VLM take over with its actions
                    self.action_queue = result.actions
                    logging.info(f"   VLM taking control after PAUSE")
                    for i, a in enumerate(self.action_queue):
                        logging.info(f"   [{i}] {a.action_type}: {a.params}")
                elif self._task_executor_commentary_only:
                    # TaskExecutor owns execution - use executor action if available
                    logging.info(f"   🎭 VLM commentary: {result.reasoning[:80] if result.reasoning else 'no comment'}...")
                    if self._pending_executor_action:
                        # Use executor's action, ignore VLM actions
                        self.action_queue = [self._pending_executor_action]
                        logging.info(f"   [0] 🎯 {self._pending_executor_action.action_type}: {self._pending_executor_action.params} (executor)")
                        self._pending_executor_action = None
                    else:
                        # No executor action - fall back to VLM actions (Session 72 fix)
                        # This prevents agent from freezing when executor finishes but flag wasn't cleared
                        logging.info(f"   ⚠️ Commentary-only but no executor action - using VLM actions as fallback")
                        self.action_queue = result.actions
                        for i, a in enumerate(self.action_queue):
                            logging.info(f"   [{i}] {a.action_type}: {a.params} (VLM fallback)")
                    # Clear the commentary-only flag for next tick
                    self._task_executor_commentary_only = False
                else:
                    # Normal VLM mode - apply action overrides in sequence
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
                        logging.info(f"   [{i}] {a.action_type}: {a.params}")
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
        if self.commentary_worker:
            self.commentary_worker.stop()


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
