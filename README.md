# KMSWC — User & Developer Guide

This guide explains the cleaned-up version of the composting program from the ground up: how to run it, how the new files map to the original `KMSWC 2 step model.py`, and what changes are most commonly needed. No prior knowledge of "clean architecture" is assumed.

> The original file is **not changed**. Everything here lives in the new `kmswc/` folder next to it. If anything ever looks wrong, the original still works exactly as before.

---

## 1. What this project is

The exact same model — a Kinetic Model of Solid Waste Composting with two composting stages, six layers each, simulated hour-by-hour for 28 days, with the same six output graphs and the same output numbers.

The **only** thing that changed is the *organization* of the code. The original was one long 2285-line file where the physics, the window, and the graphs were all mixed together, and the layer calculation was copy-pasted 12 times. This version splits those concerns into small, named files so the project is easier to read, fix, and extend. The math is identical.

---

## 2. Before starting (one-time setup)

**Python 3.9 or newer** is required, along with two libraries: `numpy` and `matplotlib` (`tkinter` ships with Python on Windows).

Open a terminal (PowerShell) in the project folder `q:\Mahim_Q\Zarif_gorilla\Research_contents` and run:

```powershell
python --version          # should print 3.9 or higher
pip install numpy matplotlib
```

This only needs to be done once.

---

## 3. How to run it

There are **two ways** to run, depending on the goal.

### A) Run the full program with the window (same as before)

From the project folder (`Research_contents`, the folder that *contains* the `kmswc` folder — not inside it), run:

```powershell
python -m kmswc
```

The familiar two-stage window opens. Use it exactly like the original:

1. Fill in the **28 daily air-flow values** in the left column.
2. Fill in the **Input Parameters** in the middle column.
3. Click the green **RUN** button. The output numbers and the six graphs appear.
4. Scroll down to the **2nd Stage Composting** section, fill its inputs, and click its **RUN** button. (Stage 1 must be run first — Stage 2 uses Stage 1's result.)

> Note: the original tried to load an icon file `K.ico` on startup and would crash if it was missing. This version simply skips the icon, so it always opens. To restore the icon, see §7.

### B) Run the calculation with no window (for quick checks / research)

This is new and handy: the model can be run and numbers printed without opening the GUI at all — useful for testing or batch runs.

```powershell
python -m kmswc.examples.run_headless
```

This prints the Stage 1 and Stage 2 output tables for a sample set of inputs. To use different inputs, open [`kmswc/examples/run_headless.py`](examples/run_headless.py) and edit the numbers near the top — the comments identify which is which.

---

## 4. Where everything lives (and how it maps to the original)

```
kmswc/
├── domain/         ← the MODEL (physics & math). No window, no graphs.
│   ├── parameters.py    the input values (Tci, Ta, HL, percentages, …)
│   ├── physics.py       the hour-by-hour calculation — written ONCE
│   ├── series.py        the lists that store Ta, VS, WC, O2 over time
│   ├── simulation.py    runs one layer, then chains all six layers
│   └── mass_balance.py  the final-mass and pile-height math (after the loops)
│
├── application/
│   └── stage_runner.py  prepares inputs and passes Stage 1 → Stage 2
│
├── presentation/   ← the SCREEN (window + graphs).
│   ├── plots.py         the six-panel figure — written ONCE
│   └── gui.py           the tkinter window and the input/output fields
│
├── examples/
│   └── run_headless.py  run the model without the window
│
├── __main__.py     what runs when you type `python -m kmswc`
├── README.md       short technical overview (for a developer reviewing it)
└── GUIDE.md        this file
```

### Mapping to the original file

| In the original `KMSWC 2 step model.py` | Now lives in |
|---|---|
| The `for i in range(n): for c in range(24):` layer loop (repeated 12×) | `domain/physics.py` — written **once** |
| Setting up Layer 1, Layer 2, … initial values | `domain/simulation.py` |
| `MB_water`, `F_mass`, `dh3`, `hh2` height/mass block | `domain/mass_balance.py` |
| Reading `p_entry1.get()`, `Day_S1[i].get()` | `presentation/gui.py` (collects them) → `domain/parameters.py` (stores them) |
| `output_value1.set(...)` … `output_value12.set(...)` | `presentation/gui.py` (displays them) |
| The `fig, ax = plt.subplots(2,3)` graph block (repeated 2×) | `presentation/plots.py` — written **once** |
| Stage 1 → Stage 2 via the `global F_mass, hh2, …` lines | `application/stage_runner.py` — passed explicitly, no globals |

### The one big idea

In the original, the layer calculation appears 12 times (6 layers × 2 stages), each copy nearly identical. Here it appears **exactly once**, in `physics.hourly_step()`. The only real differences between layers are:

- **Layer 1** breathes fresh outside air; **Layers 2–6** breathe the layer below.
- The oxygen formula reads the previous hour's air values.

Those two differences are handled in `simulation.py`, so the equations themselves never get copied. Fix a formula once → it's fixed everywhere.

---

## 5. Common changes

### Change a physics formula (e.g. the temperature equation)
Open [`kmswc/domain/physics.py`](domain/physics.py) and edit `hourly_step()`. The terms are named after the original (`h1`…`h8`, `kl`, `delta_bvs`, …) with comments. Because it's written once, any edit applies to all 12 layer/stage combinations automatically.

### Change a graph (colors, titles, y-axis limits)
Open [`kmswc/presentation/plots.py`](presentation/plots.py). Each of the six panels is a small function (`_line_panel`, `_height_panel`, `_composition_panel`).

### Change the window (labels, fields, layout)
Open [`kmswc/presentation/gui.py`](presentation/gui.py). The two stages are built from one reusable `StagePanel`. The input field labels are in the `_stage1_fields()` and `_stage2_fields()` functions near the bottom.

### Change the number of days, hours, or layers
Open [`kmswc/domain/parameters.py`](domain/parameters.py) and edit the constants at the top: `DAYS = 28`, `HOURS_PER_DAY = 24`, `LAYER_COUNT = 6`.

---

## 6. Will the numbers be exactly the same as the original?

Yes, to the two decimal places the program displays. Both the original script and this version were run side-by-side with the same inputs — all 24 output values matched for both stages.

There can be a difference far past the decimal point (e.g. the 5th–6th digit) because the original stored its lists as 32-bit numbers (`array('f', ...)`) while this version uses Python's standard 64-bit numbers, which are *more* accurate. This never affects what appears on screen.

A few small inconsistencies in the original (for example, one temperature check uses 60 °C while the same check inside the loop uses 65 °C) were **kept on purpose** so the results stay identical to the original. They are marked with `QUIRK:` comments in the code. If one is ever determined to be a genuine mistake, it can be fixed in one place — but the output should be re-checked against the original afterward.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Install Python from python.org; tick "Add to PATH". |
| `No module named numpy` / `matplotlib` | Run `pip install numpy matplotlib`. |
| `No module named kmswc` | Make sure the command is run from the `Research_contents` folder (the one that *contains* `kmswc`), not from inside `kmswc`. |
| "Invalid input. Please enter valid numbers." | A field is empty or has a non-number. Every box must contain a number. |
| Stage 2 says "Run Stage 1 first." | Click Stage 1's RUN button before Stage 2's. |
| The `K.ico` icon is missing | In `kmswc/presentation/gui.py`, after `root.title(...)`, add: `root.iconbitmap("K.ico")` and keep `K.ico` in the folder the program is run from. |

---

## 8. Quick reference card

```powershell
# one-time setup
pip install numpy matplotlib

# run the program with the window
python -m kmswc

# run the model and print numbers, no window
python -m kmswc.examples.run_headless
```

Files most commonly edited:
- Physics → `kmswc/domain/physics.py`
- Graphs  → `kmswc/presentation/plots.py`
- Window  → `kmswc/presentation/gui.py`