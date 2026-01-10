"""
Plot Manager - Orchestrates systematic farming work through defined plots.

Key responsibilities:
- Define and manage farm plots
- Generate serpentine traversal order for efficient pathing
- Track phase progression (clearing -> tilling -> planting -> watering)
- Provide VLM context for current work target
- Persist state to JSON for recovery
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from .models import (
    PlotDefinition, PlotState, FarmPlan, TileState, PlotPhase
)


class PlotManager:
    """Manages farm plots and systematic work progression."""

    def __init__(self, persistence_dir: str = "logs/farm_plans"):
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        self.farm_plan: Optional[FarmPlan] = None
        self._current_file = self.persistence_dir / "current.json"
        self._load_plan()

    def _load_plan(self):
        """Load existing plan from disk if available."""
        if self._current_file.exists():
            try:
                with open(self._current_file, "r") as f:
                    data = json.load(f)
                self.farm_plan = FarmPlan.from_dict(data)
                logging.info(f"Loaded farm plan with {len(self.farm_plan.plots)} plots")
            except Exception as e:
                logging.warning(f"Failed to load farm plan: {e}")
                self.farm_plan = None

    def _save_plan(self):
        """Persist current plan to disk."""
        if self.farm_plan:
            try:
                with open(self._current_file, "w") as f:
                    json.dump(self.farm_plan.to_dict(), f, indent=2)
            except Exception as e:
                logging.error(f"Failed to save farm plan: {e}")

    def create_plan(self, location: str = "Farm") -> FarmPlan:
        """Create a new empty farm plan."""
        self.farm_plan = FarmPlan(
            location=location,
            created_at=datetime.now().isoformat(),
        )
        self._save_plan()
        return self.farm_plan

    def define_plot(
        self,
        origin_x: int,
        origin_y: int,
        width: int = 5,
        height: int = 3,
        crop_type: str = ""
    ) -> PlotDefinition:
        """Create a new plot definition and add to plan."""
        if not self.farm_plan:
            self.create_plan()

        # Generate unique ID
        plot_id = f"plot_{len(self.farm_plan.plots) + 1}"

        plot = PlotDefinition(
            id=plot_id,
            origin_x=origin_x,
            origin_y=origin_y,
            width=width,
            height=height,
            crop_type=crop_type,
        )

        self.farm_plan.add_plot(plot)
        self._save_plan()

        logging.info(f"Created plot {plot_id}: {width}x{height} at ({origin_x}, {origin_y})")
        return plot

    def get_serpentine_order(self, plot: PlotDefinition) -> List[Tuple[int, int]]:
        """
        Generate serpentine traversal order for a plot.

        Row 0: → → → → →  (left to right)
        Row 1: ← ← ← ← ←  (right to left)
        Row 2: → → → → →  (left to right)

        This minimizes backtracking when working through tiles.
        """
        order = []
        for row in range(plot.height):
            cols = range(plot.width)
            if row % 2 == 1:  # Odd rows go right-to-left
                cols = reversed(cols)
            for col in cols:
                order.append((plot.origin_x + col, plot.origin_y + row))
        return order

    def get_next_tile(self) -> Optional[Tuple[int, int, str]]:
        """
        Return (x, y, action) for the next tile to work in current phase.

        Returns None if all work is complete or no plan exists.
        """
        if not self.farm_plan:
            return None

        plot = self.farm_plan.get_active_plot()
        state = self.farm_plan.get_active_state()

        if not plot or not state:
            return None

        if state.phase == PlotPhase.DONE:
            return None

        # Get serpentine order
        order = self.get_serpentine_order(plot)

        # Determine target state for current phase
        phase_target = state.phase_target_state()

        # Find first tile not yet in target state
        for x, y in order:
            tile_state = state.get_tile_state(x, y)

            # For clearing: tile must become CLEARED
            if state.phase == PlotPhase.CLEARING:
                if tile_state in (TileState.UNKNOWN, TileState.DEBRIS):
                    return (x, y, "clear")

            # For tilling: tile must become TILLED (only if already cleared)
            elif state.phase == PlotPhase.TILLING:
                if tile_state == TileState.CLEARED:
                    return (x, y, "till")

            # For planting: tile must become PLANTED (only if tilled)
            elif state.phase == PlotPhase.PLANTING:
                if tile_state == TileState.TILLED:
                    return (x, y, "plant")

            # For watering: tile must become WATERED (only if planted)
            elif state.phase == PlotPhase.WATERING:
                if tile_state == TileState.PLANTED:
                    return (x, y, "water")

        # No tiles need work in current phase - try to advance
        if self._try_advance_phase():
            return self.get_next_tile()  # Recursively get next from new phase

        return None

    def _try_advance_phase(self) -> bool:
        """Try to advance to next phase. Returns True if advanced."""
        if not self.farm_plan:
            return False

        state = self.farm_plan.get_active_state()
        plot = self.farm_plan.get_active_plot()

        if not state or not plot:
            return False

        next_phase = state.phase.next_phase()
        if next_phase is None:
            return False

        # Mark current phase complete
        state.completed_phases.append(state.phase.value)
        state.phase = next_phase
        state.current_row = 0
        state.current_col = 0

        logging.info(f"Plot {state.plot_id} advanced to phase: {next_phase.value}")
        self._save_plan()

        return True

    def update_tile_state(self, x: int, y: int, new_state: TileState):
        """Mark a tile as having reached a new state."""
        if not self.farm_plan:
            return

        state = self.farm_plan.get_active_state()
        if state:
            state.set_tile_state(x, y, new_state)
            self._save_plan()

    def update_from_game_state(self, surroundings: Dict[str, Any], game_state: Dict[str, Any]):
        """
        Sync tile states from actual game data.

        Called each tick to ensure our state matches reality.
        """
        if not self.farm_plan:
            return

        plot = self.farm_plan.get_active_plot()
        state = self.farm_plan.get_active_state()

        if not plot or not state:
            return

        # Get current tile info from surroundings
        current_tile = surroundings.get("currentTile", {})
        tile_state_str = current_tile.get("state", "unknown")
        tile_obj = current_tile.get("object")

        # Map game state to our TileState
        if tile_obj in ("Weeds", "Stone", "Twig", "Wood", "Grass", "Tree"):
            game_tile_state = TileState.DEBRIS
        elif tile_state_str == "clear" and current_tile.get("canTill"):
            game_tile_state = TileState.CLEARED
        elif tile_state_str == "tilled":
            game_tile_state = TileState.TILLED
        elif tile_state_str == "planted":
            game_tile_state = TileState.PLANTED
        elif tile_state_str == "watered":
            game_tile_state = TileState.WATERED
        else:
            game_tile_state = TileState.UNKNOWN

        # Get player position from game state
        player = game_state.get("player", {})
        player_x = player.get("tileX", 0)
        player_y = player.get("tileY", 0)

        # The "currentTile" from surroundings is actually the FACING tile
        # So we need to calculate the facing tile position
        facing_dir = player.get("facingDirection", 2)  # 0=N, 1=E, 2=S, 3=W
        dx = 1 if facing_dir == 1 else -1 if facing_dir == 3 else 0
        dy = 1 if facing_dir == 2 else -1 if facing_dir == 0 else 0
        facing_x = player_x + dx
        facing_y = player_y + dy

        # Update tile state if it's in our plot
        if plot.contains(facing_x, facing_y):
            old_state = state.get_tile_state(facing_x, facing_y)
            if game_tile_state != old_state:
                state.set_tile_state(facing_x, facing_y, game_tile_state)
                logging.debug(f"Tile ({facing_x},{facing_y}) state: {old_state.value} -> {game_tile_state.value}")

        # Also check crops array for more detailed info
        crops = game_state.get("location", {}).get("crops", [])
        for crop in crops:
            cx, cy = crop.get("x", 0), crop.get("y", 0)
            if plot.contains(cx, cy):
                is_watered = crop.get("isWatered", False)
                is_ready = crop.get("isReadyForHarvest", False)
                if is_ready:
                    state.set_tile_state(cx, cy, TileState.GROWN)
                elif is_watered:
                    state.set_tile_state(cx, cy, TileState.WATERED)
                else:
                    state.set_tile_state(cx, cy, TileState.PLANTED)

        self._save_plan()

    def get_prompt_context(self, player_x: int, player_y: int) -> str:
        """
        Generate VLM prompt context for the current farm plan.

        Returns emphatically-formatted text to guide the agent.
        """
        if not self.farm_plan or not self.farm_plan.active_plot_id:
            return ""

        plot = self.farm_plan.get_active_plot()
        state = self.farm_plan.get_active_state()

        if not plot or not state:
            return ""

        if state.phase == PlotPhase.DONE:
            return ">>> FARM PLAN: All plots complete! Clear more area or do other tasks. <<<"

        # Get next tile
        next_tile = self.get_next_tile()
        if not next_tile:
            return ">>> FARM PLAN: Current phase complete, advancing... <<<"

        target_x, target_y, action = next_tile

        # Calculate direction to target
        dx = target_x - player_x
        dy = target_y - player_y
        dist = abs(dx) + abs(dy)

        dirs = []
        if dy < 0:
            dirs.append(f"{abs(dy)}N")
        elif dy > 0:
            dirs.append(f"{dy}S")
        if dx < 0:
            dirs.append(f"{abs(dx)}W")
        elif dx > 0:
            dirs.append(f"{dx}E")

        direction = " ".join(dirs) if dirs else "HERE"

        # Progress calculation
        total_tiles = plot.tile_count()
        target_state = state.phase_target_state()
        done_count = sum(
            1 for x, y in plot.all_tiles()
            if state.get_tile_state(x, y).order() >= target_state.order()
        )

        # Action hint based on phase - USE SKILLS (auto-equip tools)
        action_hints = {
            "clear": "USE SKILL: clear_weeds (grass/weeds), clear_stone (rocks), clear_wood (branches). Skills auto-equip correct tool!",
            "till": "USE SKILL: till_soil - auto-equips Hoe",
            "plant": "USE SKILL: plant_seed - uses equipped seeds",
            "water": "USE SKILL: water_crop - auto-equips Watering Can",
        }
        action_hint = action_hints.get(action, "use appropriate skill")

        # Add navigation instruction if far from target
        if dist > 2:
            nav_instr = f">>> NAVIGATE FIRST! Go {direction} to reach target tile, THEN work. <<<"
        else:
            nav_instr = ">>> IN POSITION - do the action below. <<<"

        # Emphatic prompt
        return f""">>> FARM PLAN ACTIVE <<<
📋 Plot: {plot.id} ({plot.width}x{plot.height}) at ({plot.origin_x},{plot.origin_y})
🔄 Phase: {state.phase.value.upper()} ({done_count}/{total_tiles} tiles)
🎯 Target: ({target_x},{target_y}) - {direction} from you (dist={dist})
{nav_instr}
✅ Action: {action.upper()} - {action_hint}
>>> WORK THIS TILE, STAY IN PLOT, SYSTEMATIC! <<<"""

    def is_active(self) -> bool:
        """Check if there's an active farm plan."""
        return (
            self.farm_plan is not None and
            self.farm_plan.active_plot_id is not None
        )

    def clear_plan(self):
        """Clear the current farm plan."""
        self.farm_plan = None
        if self._current_file.exists():
            self._current_file.unlink()
        logging.info("Farm plan cleared")
