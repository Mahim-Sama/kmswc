"""Drive the KMSWC engine with no GUI - proof that the engine stands alone.

Run from the project root:  python -m kmswc.examples.run_headless

This is also a convenient regression check: the printed stage-1 / stage-2
summaries match the original "KMSWC 2 step model.py" to display precision for the
sample inputs below.
"""

from __future__ import annotations

from ..application import stage_runner
from ..domain.parameters import (
    AirFlowSchedule,
    CompostParameters,
    Stage1Composition,
)


def main() -> None:
    air = AirFlowSchedule([0.5] * 28)

    params1 = CompostParameters(tci=25, ta=25, hl=18000, kc=0.5, k=0.005, rh=0.7, wc_p=60)
    comp1 = Stage1Composition(initial_mass=600, fs_percent=20, nvs_percent=30,
                              vs_percent=50, density=600, height=100)

    stage1 = stage_runner.execute(stage_runner.prepare_stage1(params1, comp1, air))
    _print_summary("STAGE 1", stage1.summary)

    # stage-1 results flow into stage 2 explicitly (no globals)
    comp2 = stage_runner.stage2_composition_from(stage1.summary, density=comp1.density)
    params2 = CompostParameters(tci=25, ta=25, hl=18000, kc=0.5, k=0.005, rh=0.7, wc_p=60)
    stage2 = stage_runner.execute(stage_runner.prepare_stage2(params2, comp2, air))
    _print_summary("STAGE 2", stage2.summary)


def _print_summary(title, summary) -> None:
    print(f"\n=== {title} ===")
    for field in (
        "initial_mass", "mb_water", "mb_total_solid", "mb_fixed_solid",
        "mb_non_volatile_solid", "mb_volatile_solid", "final_mass", "final_water",
        "final_total_solid", "final_fixed_solid", "final_non_volatile_solid",
        "final_volatile_solid",
    ):
        print(f"  {field:28s} = {getattr(summary, field):.2f}")


if __name__ == "__main__":
    main()
