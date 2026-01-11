"""
Farm Planning Module - Systematic farming instead of chaotic tile-by-tile work.

Provides:
- PlotDefinition: Define rectangular farm plots
- PlotState: Track per-plot progress
- FarmPlan: Overall planning state
- PlotManager: Orchestrate systematic work through plots
- PrereqResolver: Resolve prerequisites for tasks UPFRONT during planning

Prereq Resolution:
  PrereqResolver handles RESOURCE prerequisites at planning time:
  - water_crops needs water → insert refill_watering_can
  - plant_seeds needs seeds → insert go_to_pierre, buy_seeds
  - no money for seeds → insert ship_items first (smart selling)

  MOVEMENT obstacles (debris blocking path) are handled at RUNTIME
  by TaskExecutor, not during planning.
"""

from .models import PlotDefinition, PlotState, FarmPlan, TileState, PlotPhase
from .plot_manager import PlotManager
from .prereq_resolver import (
    PrereqResolver,
    PrereqAction,
    PrereqStatus,
    ResolvedTask,
    ResolutionResult,
    get_prereq_resolver,
)

__all__ = [
    # Plot-based planning
    "PlotDefinition",
    "PlotState",
    "FarmPlan",
    "TileState",
    "PlotPhase",
    "PlotManager",
    # Prerequisite resolution
    "PrereqResolver",
    "PrereqAction",
    "PrereqStatus",
    "ResolvedTask",
    "ResolutionResult",
    "get_prereq_resolver",
]
