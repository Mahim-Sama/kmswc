# KMSWC — Clean-Architecture Redesign

A refactor of `KMSWC 2 step model.py` (Kinetic Model of Solid Waste Composting)
into a layered, testable package. **The original script is untouched** — this is a
parallel implementation that produces the same numbers.

## Why

The original is a working but hard-to-maintain script:

- The hourly heat/mass-balance arithmetic was **copy-pasted 12 times**
  (6 layers × 2 stages), each copy differing only by a variable suffix.
- Physics, GUI layout, and plotting were interleaved inside two ~700-line
  functions (`main_fuction_s1`, `main_fuction_s2`).
- Stage 1 passed results to stage 2 through **module globals** (`F_mass`, `hh2`, …).
- Inputs/outputs were hand-numbered widgets (`p_entry1..28`, `output_value1..24`).

## Structure

```
kmswc/
├── domain/                 # pure model — no tkinter, no matplotlib
│   ├── parameters.py       # input value objects (dataclasses)
│   ├── physics.py          # the hourly heat & mass balance — written ONCE
│   ├── series.py           # per-layer / per-stage time-series containers
│   ├── simulation.py       # run one layer; chain 6 layers into a stage
│   └── mass_balance.py     # final masses + pile-height geometry
├── application/
│   └── stage_runner.py     # builds engine inputs; stage1 → stage2 hand-off
├── presentation/
│   ├── plots.py            # the 6-panel matplotlib figure — written ONCE
│   └── gui.py              # tkinter front-end (two reusable StagePanels)
├── examples/
│   └── run_headless.py     # drive the engine with no GUI
├── __main__.py             # `python -m kmswc` launches the GUI
└── README.md
```

The dependency direction is one-way: `presentation → application → domain`.
The domain layer imports nothing from the outer layers, so the engine can be
run from a script, a notebook, or a test without a display.

## The key idea: one physics function, two structural differences

Every layer runs the *same* equations. Layers differ only in:

1. **Inlet air** — the bottom layer breathes ambient air; every layer above it
   inhales the layer below. Captured by `physics.InletAir`.
2. **Oxygen lag** — the original indexed `mai`/`mao`/`o2` with a trailing
   counter. Captured by `physics.OxygenInputs`.

So `physics.hourly_step` is the model in exactly one place, and
`simulation.run_bottom_layer` / `run_upper_layer` only decide what to feed it.

## Running

```bash
# GUI (same interface as the original)
python -m kmswc

# headless engine demo / regression check
python -m kmswc.examples.run_headless
```

## Fidelity

Outputs match the original to the 2-decimal precision the GUI displays, for both
stages. The original stored series in 32-bit `array('f')`; this version uses
native float64, so intermediate values are *more* precise — differences appear
only below the displayed precision.

Several apparent quirks in the original were **reproduced deliberately**, not
fixed, so the numbers stay identical. They are flagged with `QUIRK:` comments:

- the pre-loop reaction-rate ceiling is 60 °C while the loop body uses 65 °C;
- the O₂ balance reads *lagged* mass flows, not the current hour's;
- a couple of `Ta[x]` vs `Ta[-1]` indexings that happen to coincide.

If you ever want to "correct" these, change them in `physics.py` /
`simulation.py` and re-check against the original before trusting the output.
```
