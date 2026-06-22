"""Pure composting physics - the hourly heat & mass balance, written once.

In the original program this block of arithmetic was copy-pasted twelve times
(6 layers x 2 stages). Every copy was identical except for:

  * which array it read the *inlet* air humidity from, and
  * a cross-layer evaporation term that only the non-bottom layers carry.

Those two differences are captured by the ``InletAir`` abstraction below, so the
equations themselves live in exactly one place: :func:`hourly_step`.

NOTE ON FIDELITY: the formulas here reproduce the original behaviour
*bit-for-bit*, including a few quirks that look like typos in the source. Those
spots are flagged with `QUIRK:` comments. Do not "fix" them without re-validating
the numeric output against the original script.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Standalone helper relations (each was an inline expression in the original)
# ---------------------------------------------------------------------------

def saturation_humidity(temperature_c: float) -> float:
    """Antoine-style saturation humidity ratio at the given temperature.

    Mirrors the repeated expression
        0.622 * 10**(8.896 - 2238/(273+T)) / (760 - 10**(...))
    used for both inlet and outlet air streams.
    """
    p = 10 ** (8.896 - (2238 / (273 + temperature_c)))
    return 0.622 * p / (760 - p)


def inlet_humidity_ambient(relative_humidity: float, temperature_c: float) -> float:
    """Inlet humidity for the *bottom* layer, weighted by relative humidity.

    This is the original ``V_in`` term - it differs from
    :func:`saturation_humidity` only by the ``RH`` weighting.
    """
    p = 10 ** (8.896 - (2238 / (273 + temperature_c)))
    return 0.622 * (relative_humidity * p) / (760 - relative_humidity * p)


def air_density(temperature_c: float) -> float:
    """Air density as a linear function of temperature (original ``Air_d``)."""
    return 1.3009 - 0.0046 * temperature_c


def water_content_factor(water_content_percent: float) -> float:
    """Moisture limitation factor WCf, ramping 0->1 between 30% and 45% WC."""
    if water_content_percent < 30:
        return 0.0
    if water_content_percent > 45:
        return 1.0
    return (water_content_percent - 30) / 15


def temperature_rate_factor(k: float, temperature_c: float, ceiling: float) -> float:
    """Temperature-dependent reaction rate kt.

    Above ``ceiling`` degC the reaction is switched off (kt = 0). The original
    code used an inconsistent ceiling: 60 for the very first evaluation and 65
    inside the loop. Callers pass the ceiling explicitly so that quirk is
    preserved rather than hidden.
    """
    if temperature_c > ceiling:
        return 0.0
    return k * ((1.07) ** (temperature_c - 25) - (1.3) ** (temperature_c - 55))


# ---------------------------------------------------------------------------
# Inlet-air abstraction: the ONLY thing that varies between layers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InletAir:
    """Describes the air entering a layer for one hourly step.

    * ``mass_flow``      - inlet dry-air mass flow (mai) for this hour
    * ``humidity``       - inlet humidity ratio
    * ``temperature``    - inlet air temperature (feeds the convective term)
    * ``cross_layer_evap`` - extra evaporation coupling term, 0 for the bottom
      layer and ``(Ta_this - Ta_inlet) * 1.7829 * D_H2O_inlet`` for the rest.
    """

    mass_flow: float
    humidity: float
    temperature: float
    cross_layer_evap: float


@dataclass(frozen=True)
class OxygenInputs:
    """Inputs to the oxygen balance, kept separate to preserve a source quirk.

    The original used *lagged* mass flows (the previous hour's stored values)
    and, for upper layers, the previous layer's O2 fraction. ``inlet_fraction``
    is 0.21 for the bottom layer (fresh air) or ``prev_layer_o2 / 100`` above.
    """

    lagged_inlet_mass_flow: float
    lagged_outlet_mass_flow: float
    inlet_fraction: float


# ---------------------------------------------------------------------------
# Constant composition basis for a layer (set once when the layer starts)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayerBasis:
    """Per-layer constants that never change during the hourly loop."""

    fixed_solid: float            # I_FS
    non_volatile_solid: float     # I_NVS
    initial_temperature: float    # Tci, used only on the first hour
    ambient_temperature: float    # Ta_L1[0] - the stage's reference ambient
    hl: float
    kc: float


# ---------------------------------------------------------------------------
# Mutable per-layer state that the hourly step advances
# ---------------------------------------------------------------------------

@dataclass
class LayerState:
    """The compost state that evolves hour by hour within one layer."""

    volatile_solid: float          # VS  (current)
    water_mass: float              # H2O (current)
    water_content_percent: float   # WC%
    temperature: float             # Ta  (current)
    reaction_rate: float           # kt
    moisture_factor: float         # WCf


@dataclass
class StepOutput:
    """Everything the hourly step produces, ready to be appended to series."""

    inlet_mass_flow: float         # mai
    outlet_mass_flow: float        # mao
    compost_mass: float            # mc
    volatile_solid: float          # VS
    water_mass: float              # H2O
    water_content_percent: float   # WC%
    delta_water: float             # D_H2O
    delta_bvs: float               # D_BVS (this hour)
    temperature: float             # Ta (new)
    oxygen_percent: float          # O2%


def hourly_step(
    state: LayerState,
    basis: LayerBasis,
    inlet: InletAir,
    oxygen: "OxygenInputs",
    is_first_hour: bool,
) -> StepOutput:
    """Advance one layer by a single hour. This is the model, in one place.

    The oxygen balance is computed from :class:`OxygenInputs` rather than the
    live ``mai``/``mao`` because the original code indexed those arrays with a
    lagging counter (see :class:`OxygenInputs`).
    """

    # --- degradation of biodegradable volatile solids this hour ---
    delta_bvs = state.moisture_factor * state.reaction_rate * state.volatile_solid

    # --- air mass balance ---
    mai = inlet.mass_flow
    mao = mai + (delta_bvs * 0.5)

    # --- water vapour exchange ---
    # Outlet humidity is evaluated at this layer's previous-hour temperature,
    # which is exactly the live ``state.temperature`` at the top of the step
    # (the original used Ta[-1] for the bottom layer and Ta[x] for upper layers;
    # both resolve to "this layer's last stored temperature").
    humidity_out = saturation_humidity(state.temperature)
    delta_water = (humidity_out * mao) - (inlet.humidity * mai)

    # --- solids / water bookkeeping ---
    compost_mass = (
        basis.fixed_solid
        + basis.non_volatile_solid
        + state.volatile_solid
        - (0.5 * delta_bvs)
        + state.water_mass
        - delta_water
    )
    new_vs = state.volatile_solid - delta_bvs
    new_water = state.water_mass + (0.5 * delta_bvs) - delta_water
    new_wc_percent = new_water * (100 / compost_mass)

    # --- thermal coefficient KL (heat capacity per unit mass) ---
    kl = (
        (basis.fixed_solid * 0.8)
        + (basis.non_volatile_solid * 2.5)
        + (new_vs * 2.5)
        + (new_water * 4.2)
    ) / compost_mass

    # --- heat balance numerator (D) and denominator (N) ---
    # Term 1 uses Tci on the first hour, then the layer's own current temp.
    if is_first_hour:
        h1 = compost_mass * kl * basis.initial_temperature
    else:
        h1 = compost_mass * kl * state.temperature
    h2 = mai * 1.005 * inlet.temperature
    h3 = delta_bvs * basis.hl
    h4 = 0.00005 * kl * compost_mass * basis.ambient_temperature
    # Term 5 carries the cross-layer evaporation coupling (0 for bottom layer).
    h5 = delta_water * (2502.1 - 2.4 * state.temperature) + inlet.cross_layer_evap
    h6 = compost_mass * kl
    h7 = mao * 1.005
    h8 = basis.kc * kl * compost_mass

    numerator = h1 + h2 + h3 + h4 - h5
    denominator = h6 + h7 + h8
    new_temperature = numerator / denominator

    # --- oxygen balance (clamped at 0) ---
    # QUIRK: the original computes O2 from mai[x]/mao[x] where x is the running
    # counter *before* this hour's append - i.e. the PREVIOUS hour's stored
    # mass flows, not the values just computed above. The caller supplies those
    # lagged flows via OxygenInputs so the behaviour is reproduced exactly.
    oxygen_raw = 100 * (
        oxygen.lagged_inlet_mass_flow * oxygen.inlet_fraction
        - delta_bvs * 1.3
    ) / oxygen.lagged_outlet_mass_flow
    oxygen_percent = oxygen_raw if oxygen_raw > 0 else 0.0

    return StepOutput(
        inlet_mass_flow=mai,
        outlet_mass_flow=mao,
        compost_mass=compost_mass,
        volatile_solid=new_vs,
        water_mass=new_water,
        water_content_percent=new_wc_percent,
        delta_water=delta_water,
        delta_bvs=delta_bvs,
        temperature=new_temperature,
        oxygen_percent=oxygen_percent,
    )
