"""Domain value objects: the inputs that describe one composting run.

These dataclasses replace the loose `float(p_entryN.get())` reads scattered
through the original GUI callbacks. Nothing here knows about Tkinter; the GUI
builds these objects and hands them to the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


#: Number of vertical layers the compost pile is divided into.
LAYER_COUNT = 6

#: Number of simulated days.
DAYS = 28

#: Sub-steps (hours) per day.
HOURS_PER_DAY = 24


@dataclass(frozen=True)
class CompostParameters:
    """Physical / operational parameters shared by every layer of a stage.

    Field names mirror the symbols used in the original model so the equations
    stay recognisable to the authors:

    * ``tci``      - initial composting temperature, Tci (degC)
    * ``ta``       - ambient temperature, Ta (degC)
    * ``hl``       - heat energy from BVS degradation (kJ/kg)
    * ``kc``       - specific heat-transfer coefficient (W/m^2.K)
    * ``k``        - reaction rate constant (per hour)
    * ``rh``       - relative humidity (%) used as the K factor
    * ``wc_p``     - initial water content (%)
    """

    tci: float
    ta: float
    hl: float
    kc: float
    k: float
    rh: float
    wc_p: float


@dataclass(frozen=True)
class Stage1Composition:
    """Composition inputs unique to stage 1 (fresh waste).

    Stage 1 starts from an overall mass plus percentage breakdowns, whereas
    stage 2 starts from the absolute masses produced by stage 1.
    """

    initial_mass: float       # I_mass  (kg/m^2)
    fs_percent: float         # FS_p    fixed solid, % of total solid
    nvs_percent: float        # NVS_p   non-volatile solid, % of total solid
    vs_percent: float         # VS_p    volatile solid, % of total solid
    density: float            # d_density (kg/m^3)
    height: float             # hh3     pile height (cm)


@dataclass(frozen=True)
class Stage2Composition:
    """Composition inputs unique to stage 2 (carried over from stage 1)."""

    initial_mass: float       # F_mass from stage 1
    total_solid: float        # F_TS
    fixed_solid: float        # F_FS
    non_volatile_solid: float # F_NVS
    volatile_solid: float     # F_VS
    height: float             # hh3 = stage-1 final layer height * LAYER_COUNT
    density: float            # reused stage-1 density


@dataclass(frozen=True)
class AirFlowSchedule:
    """The 28 daily aeration rates (m^3 m^-2 h^-1)."""

    daily_rates: Sequence[float]

    def __post_init__(self) -> None:
        if len(self.daily_rates) != DAYS:
            raise ValueError(f"Expected {DAYS} daily air-flow values, got {len(self.daily_rates)}")

    def total(self) -> float:
        return sum(self.daily_rates)

    def for_day(self, day_index: int) -> float:
        return self.daily_rates[day_index]
