"""
Farm Planning Module - Systematic farming instead of chaotic tile-by-tile work.

Provides:
- PlotDefinition: Define rectangular farm plots
- PlotState: Track per-plot progress
- FarmPlan: Overall planning state
- PlotManager: Orchestrate systematic work through plots
"""

from .models import PlotDefinition, PlotState, FarmPlan, TileState, PlotPhase
from .plot_manager import PlotManager

__all__ = [
    "PlotDefinition",
    "PlotState",
    "FarmPlan",
    "TileState",
    "PlotPhase",
    "PlotManager",
]
