"""Stage simulation: run one layer, then chain six layers into a stage.

This module owns the *control flow* the original buried inside two 700-line
functions. The arithmetic itself lives in :mod:`physics`; here we only decide
which inlet/oxygen values feed each hour and stitch the layers together.

The bottom layer (index 0) breathes ambient air; every layer above it inhales
the layer below it. That single structural fact is what the original repeated
six times per stage with hand-edited variable suffixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .parameters import DAYS, HOURS_PER_DAY, LAYER_COUNT
from . import physics
from .physics import (
    InletAir,
    LayerBasis,
    LayerState,
    OxygenInputs,
    air_density,
    inlet_humidity_ambient,
    saturation_humidity,
    temperature_rate_factor,
    water_content_factor,
)
from .series import LayerSeries


@dataclass(frozen=True)
class LayerInit:
    """Initial conditions and constants needed to start one layer."""

    basis: LayerBasis
    initial_volatile_solid: float    # I_VS
    initial_water: float             # I_WC
    initial_water_content: float     # WC_p
    initial_temperature: float       # Ta seed (Ta_L1[0] for every layer)
    reaction_rate_const: float       # k
    air_density: float               # Air_d (constant per stage)


@dataclass(frozen=True)
class AmbientInlet:
    """Bottom-layer inlet: fresh air at a constant RH-weighted humidity."""

    daily_mass_flow: List[float]     # Day[i] * Air_d, one per day
    humidity: float                  # V_in (constant)
    air_temperature: float           # Ta_L1[0]


def _seed_layer(init: LayerInit, series: LayerSeries, seed_inlet_mass_flow: float) -> LayerState:
    """Append the hour-0 values to ``series`` and return the live state.

    Reproduces the "Initial Values" blocks: the first stored mai/mao/mc/... and
    the pre-loop kt/WCf evaluation. The hour-0 reaction rate uses a ceiling of
    60 degC (a quirk of the original; the loop body uses 65).
    """
    series.inlet_mass_flow.append(seed_inlet_mass_flow)
    series.outlet_mass_flow.append(seed_inlet_mass_flow)
    series.compost_mass.append(init.basis.fixed_solid + init.basis.non_volatile_solid
                               + init.initial_volatile_solid + init.initial_water)
    series.volatile_solid.append(init.initial_volatile_solid)
    series.water_mass.append(init.initial_water)
    series.delta_water.append(0.0)
    series.water_content_percent.append(init.initial_water_content)
    series.time_hours.append(0.0)
    # Seed Ta[0]: the original stored the ambient temperature (Ta_L1[0]) before
    # the loop for every layer, giving each series 1 + DAYS*HOURS_PER_DAY points.
    series.temperature.append(init.initial_temperature)

    return LayerState(
        volatile_solid=init.initial_volatile_solid,
        water_mass=init.initial_water,
        water_content_percent=init.initial_water_content,
        temperature=init.initial_temperature,
        # QUIRK: ceiling 60 on the pre-loop kt, 65 inside the loop.
        reaction_rate=temperature_rate_factor(init.reaction_rate_const,
                                              init.initial_temperature, ceiling=60),
        moisture_factor=water_content_factor(init.initial_water_content),
    )


def run_bottom_layer(init: LayerInit, ambient: AmbientInlet) -> LayerSeries:
    """Simulate layer 1 (fresh-air inlet, O2 fraction fixed at 0.21)."""
    series = LayerSeries()
    state = _seed_layer(init, series, ambient.daily_mass_flow[0])

    # hour-0 oxygen uses the seeded mai[0]/mao[0] and 0.21.
    series.oxygen_percent.append(_clamped_oxygen(
        ambient.daily_mass_flow[0], ambient.daily_mass_flow[0], 0.21, delta_bvs=0.0))

    x = 0  # lagging counter, mirrors the original `x`
    for day in range(DAYS):
        for _hour in range(HOURS_PER_DAY):
            inlet = InletAir(
                mass_flow=ambient.daily_mass_flow[day],
                humidity=ambient.humidity,
                temperature=ambient.air_temperature,
                cross_layer_evap=0.0,  # bottom layer has no layer below it
            )
            oxygen = OxygenInputs(
                lagged_inlet_mass_flow=series.inlet_mass_flow[x],
                lagged_outlet_mass_flow=series.outlet_mass_flow[x],
                inlet_fraction=0.21,
            )
            _advance(state, init.basis, init.reaction_rate_const, inlet, oxygen,
                     series, is_first_hour=(x == 0))
            x += 1
    return series


def run_upper_layer(init: LayerInit, lower: LayerSeries) -> LayerSeries:
    """Simulate a layer that inhales the layer below it (layers 2..6)."""
    series = LayerSeries()
    state = _seed_layer(init, series, lower.outlet_mass_flow[0])
    # Upper layers seed Ta with Ta_L1[0]; _seed_layer already used it.

    # hour-0 oxygen uses lower layer's first O2 fraction.
    series.oxygen_percent.append(_clamped_oxygen(
        lower.outlet_mass_flow[0], lower.outlet_mass_flow[0],
        lower.oxygen_percent[0] / 100, delta_bvs=0.0))

    x = 0
    for _day in range(DAYS):
        for _hour in range(HOURS_PER_DAY):
            # Inlet is the lower layer's outlet at index x+1 (the original lag).
            cross_layer = (
                (state.temperature - lower.temperature[x + 1])
                * 1.7829
                * lower.delta_water[x + 1]
            )
            inlet = InletAir(
                mass_flow=lower.outlet_mass_flow[x + 1],
                humidity=saturation_humidity(lower.temperature[x]),
                temperature=lower.temperature[x + 1],
                cross_layer_evap=cross_layer,
            )
            oxygen = OxygenInputs(
                lagged_inlet_mass_flow=series.inlet_mass_flow[x],
                lagged_outlet_mass_flow=series.outlet_mass_flow[x],
                inlet_fraction=lower.oxygen_percent[x + 1] / 100,
            )
            _advance(state, init.basis, init.reaction_rate_const, inlet, oxygen,
                     series, is_first_hour=(x == 0))
            x += 1
    return series


def run_stage(bottom_init: LayerInit, ambient: AmbientInlet,
              upper_init: LayerInit) -> List[LayerSeries]:
    """Run all six layers, chaining each to the one below it."""
    layers: List[LayerSeries] = [run_bottom_layer(bottom_init, ambient)]
    for _ in range(1, LAYER_COUNT):
        layers.append(run_upper_layer(upper_init, layers[-1]))
    return layers


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _advance(state: LayerState, basis: LayerBasis, k: float,
             inlet: InletAir, oxygen: OxygenInputs,
             series: LayerSeries, is_first_hour: bool) -> None:
    """Run one hourly step, append outputs to the series, update live state."""
    out = physics.hourly_step(state, basis, inlet, oxygen, is_first_hour=is_first_hour)

    series.inlet_mass_flow.append(out.inlet_mass_flow)
    series.outlet_mass_flow.append(out.outlet_mass_flow)
    series.delta_water.append(out.delta_water)
    series.compost_mass.append(out.compost_mass)
    series.volatile_solid.append(out.volatile_solid)
    series.water_mass.append(out.water_mass)
    series.water_content_percent.append(out.water_content_percent)
    series.time_hours.append(series.time_hours[-1] + (1 / HOURS_PER_DAY))
    series.temperature.append(out.temperature)
    series.oxygen_percent.append(out.oxygen_percent)
    series.total_degraded_bvs += out.delta_bvs

    # advance the live state for the next hour
    state.volatile_solid = out.volatile_solid
    state.water_mass = out.water_mass
    state.water_content_percent = out.water_content_percent
    state.temperature = out.temperature
    # QUIRK: loop body uses a 65 degC ceiling for kt (vs 60 in the seed).
    state.reaction_rate = temperature_rate_factor(k, out.temperature, ceiling=65)
    state.moisture_factor = water_content_factor(out.water_content_percent)


def _clamped_oxygen(mai: float, mao: float, fraction: float, delta_bvs: float) -> float:
    value = 100 * (mai * fraction - delta_bvs * 1.3) / mao
    return value if value > 0 else 0.0
