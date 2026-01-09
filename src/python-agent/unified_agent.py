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
from typing import Optional, List, Dict, Any, Tuple

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
    from memory import get_memory, get_context_for_vlm, should_remember
    from memory.game_knowledge import get_npc_info
    from memory.spatial_map import SpatialMap
    HAS_MEMORY = True
except ImportError:
    get_memory = None
    get_context_for_vlm = None
    should_remember = None
    get_npc_info = None
    SpatialMap = None
    HAS_MEMORY = False

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

@dataclass
class Config:
    """Configuration loaded from settings.yaml."""

    # Server
    server_url: str = "http://localhost:8765"
    model: str = "Qwen3VL-30B-A3B-Instruct-Q4_K_M"

    # Mode
    mode: str = "coop"  # "coop" or "helper"
    coop_region: Dict[str, float] = field(default_factory=lambda: {
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
                if 'coop_region' in data['mode']:
                    config.coop_region = data['mode']['coop_region']

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
            spatial_context: Optional directional info (e.g., "up: clear | down: BLOCKED")
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
        text = re.sub(r'(["\d])\s+("(?:perception|mood|reasoning|actions|farming_eval)")', r'\1, \2', text)

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

                # Personality & Planning
                result.mood = data.get("mood", "")
                result.reasoning = data.get("reasoning", "")

                # Actions
                for action_data in data.get("actions", []):
                    action_type = action_data.get("type", "wait")
                    params = {}

                    if action_type == "move":
                        params["direction"] = action_data.get("direction", "down")
                        params["duration"] = action_data.get("duration", 0.5)
                    elif action_type == "button":
                        params["button"] = action_data.get("button", "a")
                    elif action_type == "wait":
                        params["seconds"] = action_data.get("seconds", 1)
                    elif action_type == "interact":
                        pass  # No extra params needed
                    elif action_type == "use_tool":
                        pass  # No extra params needed
                    elif action_type == "cancel":
                        pass  # No extra params needed
                    elif action_type == "menu":
                        pass  # No extra params needed
                    elif action_type == "warp":
                        params["location"] = action_data.get("location", "farm")
                    elif action_type == "face":
                        params["direction"] = action_data.get("direction", "down")
                    elif action_type == "select_slot":
                        params["slot"] = action_data.get("slot", 0)

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

        dirs = data.get("directions", {})

        # Get facing direction from game state
        facing_dir = None
        if state:
            facing_map = {0: "up", 1: "right", 2: "down", 3: "left"}
            facing_dir = facing_map.get(state.get("player", {}).get("facingDirection"))

        # Format all directions
        parts = []
        front_info = ""
        for direction in ["up", "down", "left", "right"]:
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
                else:
                    desc = f"{direction}: BLOCKED ({blocker}, {tiles} tile{'s' if tiles != 1 else ''})"
                if direction == facing_dir:
                    if "water" in blocker.lower():
                        front_info = f">>> 💧 WATER SOURCE! select_slot 2 (Watering Can), use_tool to REFILL! <<<"
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
        for direction in ["up", "down", "left", "right"]:
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
                directions = data.get("directions", {})
                water_adjacent = None
                for dir_name, dir_info in directions.items():
                    blocker = dir_info.get("blocker", "")
                    tiles_until = dir_info.get("tilesUntilBlocked", 99)
                    if blocker and "water" in blocker.lower() and tiles_until <= 1:
                        water_adjacent = dir_name
                        break

                if water_adjacent:
                    # AT THE WATER - select watering can, then use_tool to refill!
                    if "Watering" in current_tool:
                        front_info = f">>> ⚠️ AT WATER! Face {water_adjacent}, use_tool to REFILL! <<<"
                    else:
                        front_info = f">>> ⚠️ AT WATER! select_slot 2 (Watering Can), face {water_adjacent}, use_tool to REFILL! <<<"
                else:
                    nearest_water = data.get("nearestWater")
                    if nearest_water:
                        water_dir = nearest_water.get("direction", "nearby")
                        water_dist = nearest_water.get("distance", "?")
                        front_info = f">>> ⚠️ WATERING CAN EMPTY! Go {water_dist} tiles {water_dir} to water, select_slot 2, use_tool to REFILL! <<<"
                    else:
                        front_info = ">>> ⚠️ WATERING CAN EMPTY! Find water (pond/river), select_slot 2, use_tool to REFILL! <<<"
            elif crop_here and crop_here.get("isReadyForHarvest"):
                crop_name = crop_here.get("cropName", "crop")
                front_info = f">>> 🌾 HARVEST TIME! {crop_name} is READY! use_tool to PICK IT! <<<"
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
                    # No seeds - treat as empty tillable ground, suggest finding crops to water
                    if unwatered_crops:
                        front_info = ">>> TILE: TILLED (empty, no seeds) - Move to find PLANTED crops to water! <<<"
                    else:
                        front_info = ">>> TILE: TILLED (empty, no seeds) - All crops watered! <<<"
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
                            water_dir = nearest_water.get("direction", "nearby")
                            water_dist = nearest_water.get("distance", "?")
                            front_info = f">>> WATERING CAN EMPTY! Water is {water_dist} tiles {water_dir} - go there and use_tool to REFILL! <<<"
                        else:
                            front_info = ">>> WATERING CAN EMPTY! Find water (pond/river) and use_tool to REFILL! <<<"
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
                            front_info = ">>> TILE: WET SOIL (no seeds) - All crops watered! <<<"
                else:
                    # Actually planted and watered - give specific direction to next unwatered crop
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
                            if dist == 1:
                                face_dir = "up" if dy < 0 else "down" if dy > 0 else "left" if dx < 0 else "right"
                                front_info = f">>> TILE: WATERED ✓ - NEXT CROP 1 tile {face_dir.upper()}! DO: face {face_dir}, use_tool ({len(unwatered_others)} more) <<<"
                            else:
                                dirs = []
                                if dy < 0:
                                    dirs.append(f"{abs(dy)} UP")
                                elif dy > 0:
                                    dirs.append(f"{abs(dy)} DOWN")
                                if dx < 0:
                                    dirs.append(f"{abs(dx)} LEFT")
                                elif dx > 0:
                                    dirs.append(f"{abs(dx)} RIGHT")
                                direction_str = " then ".join(dirs) if dirs else "nearby"
                                front_info = f">>> TILE: WATERED ✓ - NEXT CROP: move {direction_str}! ({len(unwatered_others)} more to water) <<<"
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
                    dist = abs(dx) + abs(dy)

                    # If crop is exactly 1 tile away, use FACE + use_tool
                    if dist == 1:
                        face_dir = "up" if dy < 0 else "down" if dy > 0 else "left" if dx < 0 else "right"
                        front_info = f">>> {len(unwatered)} CROPS NEED WATERING! One is 1 tile {face_dir.upper()}! DO: select_slot 2, face {face_dir}, use_tool <<<"
                    else:
                        dirs = []
                        if dy < 0:
                            dirs.append(f"{abs(dy)} UP")
                        elif dy > 0:
                            dirs.append(f"{abs(dy)} DOWN")
                        if dx < 0:
                            dirs.append(f"{abs(dx)} LEFT")
                        elif dx > 0:
                            dirs.append(f"{abs(dx)} RIGHT")
                        direction_str = " and ".join(dirs) if dirs else "here"
                        front_info = f">>> {len(unwatered)} CROPS NEED WATERING! Nearest: {direction_str}. GO THERE FIRST! <<<"
                elif "Hoe" in current_tool:
                    front_info = f">>> TILE: CLEAR DIRT - You have {current_tool}, use_tool to TILL! <<<"
                else:
                    front_info = ">>> TILE: CLEAR DIRT - select_slot 1 for HOE, then use_tool to TILL! <<<"
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

                    # Build directional guidance
                    dirs = []
                    if dy < 0:
                        dirs.append(f"{abs(dy)} tiles UP")
                    elif dy > 0:
                        dirs.append(f"{abs(dy)} tiles DOWN")
                    if dx < 0:
                        dirs.append(f"{abs(dx)} tiles LEFT")
                    elif dx > 0:
                        dirs.append(f"{abs(dx)} tiles RIGHT")

                    direction_str = " and ".join(dirs) if dirs else "here"
                    front_info = f">>> TILE: NOT FARMABLE - {len(unwatered)} UNWATERED CROPS! Nearest is {direction_str}. Move there to water! <<<"
                else:
                    # Check for harvestable crops first
                    harvestable = [c for c in crops if c.get("isReadyForHarvest", False)]
                    if harvestable:
                        nearest_h = min(harvestable, key=lambda c: abs(c["x"] - player_x) + abs(c["y"] - player_y))
                        dx = nearest_h["x"] - player_x
                        dy = nearest_h["y"] - player_y
                        dirs = []
                        if dy < 0:
                            dirs.append(f"{abs(dy)} UP")
                        elif dy > 0:
                            dirs.append(f"{abs(dy)} DOWN")
                        if dx < 0:
                            dirs.append(f"{abs(dx)} LEFT")
                        elif dx > 0:
                            dirs.append(f"{abs(dx)} RIGHT")
                        direction_str = " and ".join(dirs) if dirs else "here"
                        front_info = f">>> 🌾 {len(harvestable)} CROPS READY TO HARVEST! Nearest: {direction_str}. GO PICK THEM! <<<"
                    elif crops:
                        front_info = ">>> TILE: NOT FARMABLE - All crops watered, none ready to harvest. <<<"
                    else:
                        front_info = ">>> TILE: NOT FARMABLE - move to find tillable ground <<<"

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
                    bin_dirs.append(f"{abs(dy)} UP")
                elif dy > 0:
                    bin_dirs.append(f"{abs(dy)} DOWN")
                if dx < 0:
                    bin_dirs.append(f"{abs(dx)} LEFT")
                elif dx > 0:
                    bin_dirs.append(f"{abs(dx)} RIGHT")
                bin_dir_str = " and ".join(bin_dirs) if bin_dirs else "here"
                shipping_info = f"📦 SHIPPING BIN: {distance} tiles away ({bin_dir_str})"

        # Location-specific navigation hints
        location_hint = ""
        if location_name == "FarmHouse":
            # FarmHouse exit is at south edge - walk DOWN to exit through door
            # Door mat is around (3, 12) - walk south to trigger exit
            exit_y = 12  # Exit triggers when walking south past y=11
            exit_x = 3
            dy_to_exit = exit_y - player_y
            dx_to_exit = exit_x - player_x
            if abs(dx_to_exit) > 1 or dy_to_exit < 0:
                # Need to get to exit area first
                dirs = []
                if dy_to_exit > 0:
                    dirs.append(f"{dy_to_exit} DOWN")
                if dx_to_exit > 0:
                    dirs.append(f"{dx_to_exit} RIGHT")
                elif dx_to_exit < 0:
                    dirs.append(f"{abs(dx_to_exit)} LEFT")
                location_hint = f"🚪 EXIT: Go {' then '.join(dirs)} to reach door, then keep going DOWN to exit!"
            else:
                # At or near exit - just go down
                location_hint = "🚪 EXIT: Walk DOWN (south) to exit the farmhouse!"
        elif location_name == "Farm":
            # Farmhouse entrance is around (64, 15)
            farmhouse_x, farmhouse_y = 64, 15
            dx = farmhouse_x - player_x
            dy = farmhouse_y - player_y
            distance = abs(dx) + abs(dy)
            if distance > 0:
                dirs = []
                if dy < 0:
                    dirs.append(f"{abs(dy)} UP")
                elif dy > 0:
                    dirs.append(f"{abs(dy)} DOWN")
                if dx < 0:
                    dirs.append(f"{abs(dx)} LEFT")
                elif dx > 0:
                    dirs.append(f"{abs(dx)} RIGHT")
                location_hint = f"🏠 FARMHOUSE DOOR: {distance} tiles away ({' and '.join(dirs)})"

        # Assemble result with explicit tool context always visible
        header_parts = [location_header, tool_info]
        if location_hint:
            header_parts.append(location_hint)
        if shipping_info:
            header_parts.append(shipping_info)

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
        """Get hint when all crops are watered - suggest clearing debris or bed."""
        if not state:
            return ">>> ALL CROPS WATERED! ✓ Go to bed or explore. <<<"

        hour = state.get("time", {}).get("hour", 12)
        energy = state.get("player", {}).get("energy", 100)
        energy_pct = (energy / state.get("player", {}).get("maxEnergy", 270) * 100) if state.get("player", {}).get("maxEnergy", 270) > 0 else 100
        player_x = state.get("player", {}).get("tileX", 0)
        player_y = state.get("player", {}).get("tileY", 0)

        # Check for nearby debris in surroundings
        nearby_debris = []
        if surroundings:
            for direction, info in surroundings.get("directions", {}).items():
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
            return f">>> ALL CROPS WATERED! ✓ Clear {debris_type} {dist} tiles {direction.upper()} with {tool}, or use action 'go_to_bed'. <<<"

        # Default
        return ">>> ALL CROPS WATERED! ✓ Clear debris to expand farm, or use action 'go_to_bed' (auto-warps + sleeps). <<<"

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
                direction = action.params.get("direction", "").lower()
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

            elif action_type == "use_tool":
                direction = action.params.get("direction", "")
                return self._send_action({
                    "action": "use_tool",
                    "direction": direction
                })

            elif action_type == "face":
                direction = action.params.get("direction", "down")
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

            elif action_type == "sleep" or action_type == "go_to_bed":
                return self._send_action({"action": "go_to_bed"})

            elif action_type in ("toolbar_next", "toolbar_right"):
                return self._send_action({"action": "toolbar_next"})

            elif action_type in ("toolbar_prev", "toolbar_left"):
                return self._send_action({"action": "toolbar_prev"})

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
        "up": (0, 1),
        "down": (0, -1),
        "left": (-1, 0),
        "right": (1, 0),
        "up_left": (-0.7, 0.7),
        "up_right": (0.7, 0.7),
        "down_left": (-0.7, -0.7),
        "down_right": (0.7, -0.7),
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
                direction = action.params.get("direction", "").lower()
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
            dirs.append(f"{abs(dy)} UP")
        elif dy > 0:
            dirs.append(f"{abs(dy)} DOWN")
        if dx < 0:
            dirs.append(f"{abs(dx)} LEFT")
        elif dx > 0:
            dirs.append(f"{abs(dx)} RIGHT")
        direction_str = " and ".join(dirs) if dirs else "here"
        return f"SPATIAL MAP: TILLED but UNPLANTED tile at {nearest.x},{nearest.y} ({direction_str})."

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
            direction = action.params.get("direction", "down")
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
        }
        if result:
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

    async def _tick(self):
        """Single tick of the agent loop."""
        now = time.time()

        # Execute queued actions first
        if self.action_queue:
            action = self.action_queue.pop(0)

            # Collision check for move actions - skip if direction is blocked
            if action.action_type == "move" and isinstance(self.controller, ModBridgeController):
                direction = action.params.get("direction", "").lower()
                surroundings = self.controller.get_surroundings()
                if surroundings:
                    dirs = surroundings.get("directions", {})
                    dir_info = dirs.get(direction, {})
                    if not dir_info.get("clear", True) and dir_info.get("tilesUntilBlocked", 1) == 0:
                        blocker = dir_info.get('blocker', 'obstacle')
                        logging.warning(f"⚠️ Skipping move {direction} - blocked by {blocker}")
                        # Still record the ATTEMPTED action so VLM learns from failed attempts
                        self.recent_actions.append(f"BLOCKED: move {direction} (hit {blocker})")
                        self.recent_actions = self.recent_actions[-10:]
                        self.movement_attempts += 1
                        self.last_blocked_direction = f"{direction} ({blocker})"
                        self._send_ui_status()
                        return

            self.vlm_status = "Executing"
            if action.action_type == "move":
                self.movement_attempts += 1
            self.recent_actions.append(self._format_action(action))
            self.recent_actions = self.recent_actions[-10:]  # Keep last 10 for pattern detection
            logging.info(f"🎮 Executing: {action.action_type} {action.params}")
            success = self.controller.execute(action)
            self._record_action_event(action, success)
            await asyncio.sleep(self.config.action_delay)
            self._send_ui_status()
            return

        # Time to think?
        if now - self.last_think_time >= self.config.think_interval:
            self.last_think_time = now

            self.vlm_status = "Thinking"
            self._send_ui_status()
            self._refresh_state_snapshot()

            # Capture screen (crop for co-op mode)
            crop = self.config.coop_region if self.config.mode == "coop" else None
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
            user_context = self._get_recent_user_messages()
            if user_context:
                action_context_parts.append(
                    f"USER MESSAGES (respond in reasoning):\n{user_context}"
                )
            spatial_hint = self._get_spatial_hint()
            if spatial_hint:
                action_context_parts.append(spatial_hint)
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
                    warning += "👁️ LOOK AT THE SCREENSHOT! There's probably an obstacle blocking you.\n"
                    warning += "USE YOUR EYES to find a path around it:\n"
                    warning += "- See a TREE or ROCK blocking? Move sideways first to go AROUND it\n"
                    warning += "- Can't go south? Try going LEFT or RIGHT first, THEN south\n"
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
            logging.info("🧠 Thinking...")
            result = self.vlm.think(img, self.goal, spatial_context=spatial_context, memory_context=memory_context, action_context=action_context)
            self.think_count += 1
            if result.latency_ms:
                self.latency_history.append(result.latency_ms)
                self.latency_history = self.latency_history[-60:]
            self._track_vlm_parse(result)

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

            if self.config.mode == "coop" and result.actions:
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

            # Queue actions
            if self.config.mode in ("coop", "single"):
                self.action_queue = result.actions
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
    parser.add_argument("--mode", "-m", choices=["coop", "helper"],
                        help="Override mode from config")
    parser.add_argument("--observe", "-o", action="store_true",
                        help="Observe only (disable controller)")
    parser.add_argument("--ui", action="store_true",
                        help="Enable UI updates")
    parser.add_argument("--ui-url", default=None,
                        help="UI base URL (default http://localhost:9001)")
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

    print("\n" + "=" * 60)
    print("   🎮 StardewAI - Unified VLM Agent")
    print("=" * 60)
    print(f"   Mode: {config.mode.upper()}")
    print(f"   Model: {config.model}")
    print(f"   Server: {config.server_url}")
    print(f"   Goal: {args.goal or 'Explore and help'}")
    if config.mode == "coop":
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
