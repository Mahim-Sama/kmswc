"""Application layer: assemble engine inputs and orchestrate the two stages.

This replaces the role the original globals (`F_mass`, `F_TS`, `hh2`, ...) played
in passing stage-1 results into stage-2. Here the hand-off is an explicit return
value, so nothing is hidden in module globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.parameters import (
    AirFlowSchedule,
    CompostParameters,
    LAYER_COUNT,
    Stage1Composition,
    Stage2Composition,
)
from ..domain import mass_balance
from ..domain.physics import LayerBasis, air_density, inlet_humidity_ambient
from ..domain.series import StageResult, StageSummary
from ..domain.simulation import AmbientInlet, LayerInit, run_stage


@dataclass(frozen=True)
class StageInputs:
    """Everything needed to run one stage, assembled by the helpers below."""

    bottom_init: LayerInit
    upper_init: LayerInit
    ambient: AmbientInlet
    # mass-balance inputs carried to the summary step
    initial_mass: float
    mb_water: float
    mb_total_solid: float
    mb_fixed_solid: float
    mb_non_volatile_solid: float
    mb_volatile_solid: float
    density: float
    water_content_percent: float
    total_height_cm: float


def _build_inits(params: CompostParameters, air: AirFlowSchedule,
                 *, i_fs: float, i_nvs: float, i_vs: float, i_water: float,
                 air_d: float) -> tuple[LayerInit, AmbientInlet, LayerInit]:
    """Build the bottom/upper LayerInit and the ambient inlet from per-layer masses."""
    basis = LayerBasis(
        fixed_solid=i_fs,
        non_volatile_solid=i_nvs,
        initial_temperature=params.tci,
        ambient_temperature=params.ta,
        hl=params.hl,
        kc=params.kc,
    )

    def make_init() -> LayerInit:
        return LayerInit(
            basis=basis,
            initial_volatile_solid=i_vs,
            initial_water=i_water,
            initial_water_content=params.wc_p,
            initial_temperature=params.ta,   # Ta_L1[0] seed shared by all layers
            reaction_rate_const=params.k,
            air_density=air_d,
        )

    ambient = AmbientInlet(
        daily_mass_flow=[rate * air_d for rate in air.daily_rates],
        humidity=inlet_humidity_ambient(params.rh, params.ta),
        air_temperature=params.ta,
    )
    # Bottom and upper layers share the same per-layer composition basis here;
    # they differ only in their inlet wiring (handled in the simulation layer).
    return make_init(), ambient, make_init()


def prepare_stage1(params: CompostParameters, comp: Stage1Composition,
                   air: AirFlowSchedule) -> StageInputs:
    """Translate fresh-waste percentages into per-layer masses (stage 1)."""
    layer_mass = comp.initial_mass / LAYER_COUNT
    i_water = (params.wc_p * layer_mass) / 100
    i_total_solid = layer_mass - i_water
    i_fs = (i_total_solid * comp.fs_percent) / 100
    i_nvs = (i_total_solid * comp.nvs_percent) / 100
    i_vs = (i_total_solid * comp.vs_percent) / 100

    air_d = air_density(params.ta)
    bottom, ambient, upper = _build_inits(
        params, air, i_fs=i_fs, i_nvs=i_nvs, i_vs=i_vs, i_water=i_water, air_d=air_d)

    mb_water = comp.initial_mass * params.wc_p * 0.01
    mb_total_solid = comp.initial_mass - mb_water
    mb_fixed = comp.fs_percent * mb_total_solid * 0.01
    mb_nvs = comp.nvs_percent * mb_total_solid * 0.01
    mb_vs = comp.vs_percent * mb_total_solid * 0.01

    return StageInputs(
        bottom_init=bottom, upper_init=upper, ambient=ambient,
        initial_mass=comp.initial_mass,
        mb_water=mb_water, mb_total_solid=mb_total_solid,
        mb_fixed_solid=mb_fixed, mb_non_volatile_solid=mb_nvs, mb_volatile_solid=mb_vs,
        density=comp.density, water_content_percent=params.wc_p,
        total_height_cm=comp.height,
    )


def prepare_stage2(params: CompostParameters, comp: Stage2Composition,
                   air: AirFlowSchedule) -> StageInputs:
    """Translate carried-over absolute masses into per-layer masses (stage 2)."""
    i_fs = comp.fixed_solid / LAYER_COUNT
    i_nvs = comp.non_volatile_solid / LAYER_COUNT
    i_vs = comp.volatile_solid / LAYER_COUNT
    layer_mass = comp.initial_mass / LAYER_COUNT
    i_water = (params.wc_p * layer_mass) / 100

    air_d = air_density(params.ta)
    bottom, ambient, upper = _build_inits(
        params, air, i_fs=i_fs, i_nvs=i_nvs, i_vs=i_vs, i_water=i_water, air_d=air_d)

    mb_water = comp.initial_mass * params.wc_p * 0.01
    mb_fixed = comp.fixed_solid
    mb_nvs = comp.non_volatile_solid
    mb_vs = comp.volatile_solid
    mb_total_solid = comp.total_solid
    initial_mass = mb_total_solid + mb_water  # original recomputes I_mass here

    return StageInputs(
        bottom_init=bottom, upper_init=upper, ambient=ambient,
        initial_mass=initial_mass,
        mb_water=mb_water, mb_total_solid=mb_total_solid,
        mb_fixed_solid=mb_fixed, mb_non_volatile_solid=mb_nvs, mb_volatile_solid=mb_vs,
        density=comp.density, water_content_percent=params.wc_p,
        total_height_cm=comp.height,
    )


def execute(inputs: StageInputs) -> StageResult:
    """Run the six-layer simulation and produce the mass-balance summary."""
    layers = run_stage(inputs.bottom_init, inputs.ambient, inputs.upper_init)
    summary = mass_balance.summarise(
        layers,
        initial_mass=inputs.initial_mass,
        mb_water=inputs.mb_water,
        mb_total_solid=inputs.mb_total_solid,
        mb_fixed_solid=inputs.mb_fixed_solid,
        mb_non_volatile_solid=inputs.mb_non_volatile_solid,
        mb_volatile_solid=inputs.mb_volatile_solid,
        density=inputs.density,
        water_content_percent=inputs.water_content_percent,
        total_height_cm=inputs.total_height_cm,
    )
    return StageResult(layers=layers, summary=summary)


def stage2_composition_from(summary: StageSummary, *, density: float) -> Stage2Composition:
    """Build the stage-2 composition from a stage-1 summary (the global hand-off).

    ``height`` reproduces ``hh3 = hh2 * LAYER_COUNT`` from the original: stage 2's
    total starting height is six times stage 1's final per-layer height.
    """
    return Stage2Composition(
        initial_mass=summary.final_mass,
        total_solid=summary.final_total_solid,
        fixed_solid=summary.final_fixed_solid,
        non_volatile_solid=summary.final_non_volatile_solid,
        volatile_solid=summary.final_volatile_solid,
        height=summary.final_layer_height * LAYER_COUNT,
        density=density,
    )
