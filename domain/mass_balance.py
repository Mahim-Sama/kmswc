"""Post-simulation mass balance and pile-height geometry.

Reproduces the block after the six-layer loops that turns degraded VS / lost
water into final masses, plus the height calculation feeding the stacked bar
chart. Porosity terms from the original are computed but were never displayed;
they are omitted here (add back if a future panel needs them).
"""

from __future__ import annotations

from typing import List

from .parameters import LAYER_COUNT
from .series import LayerSeries, StageSummary


def _total_degraded_vs(layers: List[LayerSeries]) -> float:
    return sum(layer.total_degraded_bvs for layer in layers)


def _total_delta_water(layers: List[LayerSeries]) -> float:
    return sum(layer.total_delta_water() for layer in layers)


def _layer_heights(initial_mass: float, final_mass: float, density: float,
                   water_content_percent: float, total_height_cm: float):
    """Return (initial_layer_height, final_layer_height) in cm.

    Mirrors the hh1/hh2 derivation: a dry-density driven shrinkage model where
    the pile settles from ``total_height_cm`` to a reduced final height, then is
    split across the six layers.
    """
    height_density = initial_mass * 100 / total_height_cm
    dry_density = height_density * ((100 - water_content_percent) / 100)
    settled = 104.98 - 0.373 * dry_density
    final_total_height = total_height_cm - settled
    return total_height_cm / LAYER_COUNT, final_total_height / LAYER_COUNT


def summarise(
    layers: List[LayerSeries],
    *,
    initial_mass: float,
    mb_water: float,
    mb_total_solid: float,
    mb_fixed_solid: float,
    mb_non_volatile_solid: float,
    mb_volatile_solid: float,
    density: float,
    water_content_percent: float,
    total_height_cm: float,
) -> StageSummary:
    """Combine simulation series with the mass-balance inputs into a summary."""
    degraded_vs = _total_degraded_vs(layers)
    lost_water = _total_delta_water(layers)

    final_water = mb_water - lost_water
    final_fixed = mb_fixed_solid
    final_nvs = mb_non_volatile_solid
    final_vs = mb_volatile_solid - degraded_vs
    final_ts = final_fixed + final_nvs + final_vs
    final_mass = final_water + final_ts

    initial_height, final_height = _layer_heights(
        initial_mass, final_mass, density, water_content_percent, total_height_cm)

    return StageSummary(
        initial_mass=initial_mass,
        mb_water=mb_water,
        mb_total_solid=mb_total_solid,
        mb_fixed_solid=mb_fixed_solid,
        mb_non_volatile_solid=mb_non_volatile_solid,
        mb_volatile_solid=mb_volatile_solid,
        final_mass=final_mass,
        final_water=final_water,
        final_total_solid=final_ts,
        final_fixed_solid=final_fixed,
        final_non_volatile_solid=final_nvs,
        final_volatile_solid=final_vs,
        initial_layer_height=initial_height,
        final_layer_height=final_height,
    )
