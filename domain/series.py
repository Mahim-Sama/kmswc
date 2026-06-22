"""Time-series containers for one layer and one full stage.

A :class:`LayerSeries` accumulates the per-hour history the original kept in a
dozen parallel ``arr.array`` objects (``Ta_L1``, ``VS_L1`` ...). Bundling them
into one object per layer is what lets the layers be chained generically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class LayerSeries:
    """Per-hour history for a single layer."""

    inlet_mass_flow: List[float] = field(default_factory=list)   # mai
    outlet_mass_flow: List[float] = field(default_factory=list)  # mao
    compost_mass: List[float] = field(default_factory=list)      # mc
    volatile_solid: List[float] = field(default_factory=list)    # VS
    water_mass: List[float] = field(default_factory=list)        # H2O
    water_content_percent: List[float] = field(default_factory=list)  # WC%
    delta_water: List[float] = field(default_factory=list)       # D_H2O
    temperature: List[float] = field(default_factory=list)       # Ta
    oxygen_percent: List[float] = field(default_factory=list)    # O2%
    time_hours: List[float] = field(default_factory=list)        # Time (in days)
    total_degraded_bvs: float = 0.0                              # running sum of D_BVS

    def total_delta_water(self) -> float:
        return sum(self.delta_water)


@dataclass
class StageResult:
    """The six layer series plus the mass-balance summary for a stage."""

    layers: List[LayerSeries]
    summary: "StageSummary"


@dataclass
class StageSummary:
    """Scalar mass-balance / geometry results displayed in the output panel."""

    initial_mass: float
    mb_water: float
    mb_total_solid: float
    mb_fixed_solid: float
    mb_non_volatile_solid: float
    mb_volatile_solid: float
    final_mass: float
    final_water: float
    final_total_solid: float
    final_fixed_solid: float
    final_non_volatile_solid: float
    final_volatile_solid: float
    # geometry (heights in cm, for the stacked height bar chart)
    initial_layer_height: float   # hh1
    final_layer_height: float     # hh2
