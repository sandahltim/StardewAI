"""
Data models for farm planning system.

Plots are rectangular farm zones worked systematically:
1. CLEARING - remove debris (weeds, stones, wood)
2. TILLING - hoe cleared dirt
3. PLANTING - plant seeds in tilled soil
4. WATERING - water planted crops
5. DONE - all phases complete, maintain

Each phase must complete for ALL tiles before moving to next phase.
Tiles are worked row-by-row in serpentine pattern for efficiency.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class TileState(Enum):
    """State of a single tile within a plot."""
    UNKNOWN = "unknown"
    DEBRIS = "debris"       # Has weeds, stone, wood - needs clearing
    CLEARED = "cleared"     # Debris removed, bare dirt
    TILLED = "tilled"       # Hoed, ready for planting
    PLANTED = "planted"     # Seed placed, needs water
    WATERED = "watered"     # Watered, growing
    GROWN = "grown"         # Ready to harvest

    def order(self) -> int:
        """Numeric ordering for state progression."""
        ordering = {
            "unknown": 0,
            "debris": 1,
            "cleared": 2,
            "tilled": 3,
            "planted": 4,
            "watered": 5,
            "grown": 6,
        }
        return ordering.get(self.value, 0)


class PlotPhase(Enum):
    """Current work phase for a plot."""
    CLEARING = "clearing"
    TILLING = "tilling"
    PLANTING = "planting"
    WATERING = "watering"
    DONE = "done"

    def next_phase(self) -> Optional["PlotPhase"]:
        """Get the next phase in sequence."""
        order = [PlotPhase.CLEARING, PlotPhase.TILLING, PlotPhase.PLANTING,
                 PlotPhase.WATERING, PlotPhase.DONE]
        idx = order.index(self)
        return order[idx + 1] if idx < len(order) - 1 else None


@dataclass
class PlotDefinition:
    """A rectangular farm plot zone."""
    id: str                           # e.g., "plot_1"
    origin_x: int                     # Top-left corner X (game tile coords)
    origin_y: int                     # Top-left corner Y
    width: int = 5                    # Tiles wide (columns)
    height: int = 3                   # Tiles tall (rows)
    crop_type: str = ""               # Optional: what to plant (e.g., "Parsnip Seeds")

    def contains(self, x: int, y: int) -> bool:
        """Check if a tile coordinate is within this plot."""
        return (self.origin_x <= x < self.origin_x + self.width and
                self.origin_y <= y < self.origin_y + self.height)

    def all_tiles(self) -> List[tuple]:
        """Return all tile coordinates in this plot."""
        return [(self.origin_x + col, self.origin_y + row)
                for row in range(self.height)
                for col in range(self.width)]

    def tile_count(self) -> int:
        """Total number of tiles in the plot."""
        return self.width * self.height


@dataclass
class PlotState:
    """Current working state of a plot."""
    plot_id: str
    phase: PlotPhase = PlotPhase.CLEARING
    tiles: Dict[str, TileState] = field(default_factory=dict)  # "(x,y)" -> TileState
    current_row: int = 0              # Which row we're working (0-indexed)
    current_col: int = 0              # Which column in the row
    started_at: str = ""              # ISO timestamp
    completed_phases: List[str] = field(default_factory=list)

    def get_tile_state(self, x: int, y: int) -> TileState:
        """Get state of a specific tile."""
        key = f"{x},{y}"
        return self.tiles.get(key, TileState.UNKNOWN)

    def set_tile_state(self, x: int, y: int, state: TileState):
        """Set state of a specific tile."""
        key = f"{x},{y}"
        self.tiles[key] = state

    def count_tiles_in_state(self, state: TileState) -> int:
        """Count how many tiles are in a given state."""
        return sum(1 for s in self.tiles.values() if s == state)

    def phase_target_state(self) -> TileState:
        """What tile state completes the current phase."""
        mapping = {
            PlotPhase.CLEARING: TileState.CLEARED,
            PlotPhase.TILLING: TileState.TILLED,
            PlotPhase.PLANTING: TileState.PLANTED,
            PlotPhase.WATERING: TileState.WATERED,
        }
        return mapping.get(self.phase, TileState.WATERED)


@dataclass
class FarmPlan:
    """Overall farm planning state."""
    plots: List[PlotDefinition] = field(default_factory=list)
    plot_states: Dict[str, PlotState] = field(default_factory=dict)
    active_plot_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    location: str = "Farm"            # Game location name

    def get_active_plot(self) -> Optional[PlotDefinition]:
        """Get the currently active plot definition."""
        if not self.active_plot_id:
            return None
        return next((p for p in self.plots if p.id == self.active_plot_id), None)

    def get_active_state(self) -> Optional[PlotState]:
        """Get the state of the currently active plot."""
        if not self.active_plot_id:
            return None
        return self.plot_states.get(self.active_plot_id)

    def add_plot(self, plot: PlotDefinition) -> PlotState:
        """Add a new plot and initialize its state."""
        self.plots.append(plot)
        state = PlotState(
            plot_id=plot.id,
            started_at=datetime.now().isoformat()
        )
        # Initialize all tiles as UNKNOWN
        for x, y in plot.all_tiles():
            state.set_tile_state(x, y, TileState.UNKNOWN)
        self.plot_states[plot.id] = state

        # Set as active if first plot
        if self.active_plot_id is None:
            self.active_plot_id = plot.id

        return state

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for persistence."""
        return {
            "active": self.active_plot_id is not None,
            "location": self.location,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "active_plot_id": self.active_plot_id,
            "plots": [
                {
                    "id": p.id,
                    "origin_x": p.origin_x,
                    "origin_y": p.origin_y,
                    "width": p.width,
                    "height": p.height,
                    "crop_type": p.crop_type,
                    "phase": self.plot_states[p.id].phase.value if p.id in self.plot_states else "unknown",
                    "tiles": {k: v.value for k, v in self.plot_states[p.id].tiles.items()} if p.id in self.plot_states else {},
                    "current_row": self.plot_states[p.id].current_row if p.id in self.plot_states else 0,
                    "current_col": self.plot_states[p.id].current_col if p.id in self.plot_states else 0,
                }
                for p in self.plots
            ],
            "current_tile": None,  # Filled by PlotManager
            "next_tile": None,     # Filled by PlotManager
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FarmPlan":
        """Load from JSON dict."""
        plan = cls(
            location=data.get("location", "Farm"),
            created_at=data.get("created_at", ""),
            active_plot_id=data.get("active_plot_id"),
        )

        for p_data in data.get("plots", []):
            plot = PlotDefinition(
                id=p_data["id"],
                origin_x=p_data["origin_x"],
                origin_y=p_data["origin_y"],
                width=p_data.get("width", 5),
                height=p_data.get("height", 3),
                crop_type=p_data.get("crop_type", ""),
            )
            plan.plots.append(plot)

            state = PlotState(
                plot_id=plot.id,
                phase=PlotPhase(p_data.get("phase", "clearing")),
                current_row=p_data.get("current_row", 0),
                current_col=p_data.get("current_col", 0),
            )
            # Load tile states
            for key, val in p_data.get("tiles", {}).items():
                state.tiles[key] = TileState(val)
            plan.plot_states[plot.id] = state

        return plan
