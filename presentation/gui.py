"""Tkinter front-end - decoupled from the engine.

The window is built from two reusable :class:`StagePanel` widgets instead of the
original's hand-numbered ``p_entry1 .. p_entry28`` / ``output_value1 .. 24``. Each
panel only knows how to (a) collect its fields into domain dataclasses and (b)
display a :class:`StageSummary`; the actual physics is invoked through the
application layer, so this file imports no equations.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ..application import stage_runner
from ..domain.parameters import (
    AirFlowSchedule,
    CompostParameters,
    DAYS,
    Stage1Composition,
)
from ..domain.series import StageResult, StageSummary
from . import plots

WIN_FONT = ("Arial", 11)
WIN_PAD = 3.5
TITLE_FONT = ("Arial Bold", 14)


# --- output field definitions, shared label text for both stages -----------
_OUTPUT_FIELDS: List[tuple[str, str]] = [
    ("initial_mass", "Initial Mass of Composting (kg/m²): "),
    ("mb_water", "Initial Mass of Water (kg/m²): "),
    ("mb_total_solid", "Initial Mass of Total Solid (kg/m²): "),
    ("mb_fixed_solid", "Initial Mass of Fix Solid (kg/m²): "),
    ("mb_non_volatile_solid", "Initial Mass of N-VS (kg/m²): "),
    ("mb_volatile_solid", "Initial Mass of Volatile Solid (kg/m²): "),
    ("final_mass", "Final Mass of Composting (kg/m²): "),
    ("final_water", "Final Mass of Water (kg/m²): "),
    ("final_total_solid", "Final Mass of Total Solid (kg/m²): "),
    ("final_fixed_solid", "Final Mass of Fix Solid (kg/m²): "),
    ("final_non_volatile_solid", "Final Mass of N-VS (kg/m²): "),
    ("final_volatile_solid", "Final Mass of Volatile Solid (kg/m²): "),
]


class _LabeledEntries:
    """A small grid of (label, entry) pairs keyed by name."""

    def __init__(self, master: tk.Widget):
        self.frame = master
        self._entries: Dict[str, tk.Entry] = {}

    def add(self, key: str, text: str, row: int, col: int) -> None:
        tk.Label(self.frame, text=text, font=WIN_FONT).grid(
            row=row, column=col, pady=WIN_PAD, sticky="w")
        entry = tk.Entry(self.frame, font=WIN_FONT, width=10)
        entry.grid(row=row, column=col + 1, pady=WIN_PAD)
        self._entries[key] = entry

    def value(self, key: str) -> float:
        return float(self._entries[key].get())


class StagePanel:
    """One composting stage: aeration column, parameters, outputs, graph.

    Subclasses/instances differ only in which parameter fields they expose and
    how they build their domain objects, supplied via the constructor callbacks.
    """

    def __init__(self, parent: tk.Widget, base_row: int, title: str,
                 build_param_fields: Callable[["_LabeledEntries"], None],
                 on_run: Callable[["StagePanel"], None]):
        self._on_run = on_run

        info = tk.Frame(parent)
        info.grid(row=base_row, column=0, columnspan=3, sticky="nsew")
        tk.Label(info, text=title, font=("Arial Bold", 20), fg="steelblue").grid(
            row=0, column=0, pady=WIN_PAD, sticky="nsew")
        info.grid_columnconfigure(0, weight=1)

        # aeration column (28 daily air-flow entries + RUN button)
        aeration = tk.Frame(parent)
        aeration.grid(row=base_row + 1, column=0, rowspan=2, sticky="nsew")
        tk.Label(aeration, text="Aeration Rate", font=TITLE_FONT, fg="Navy Blue").pack(side="top")
        self._air_entries: List[tk.Entry] = []
        for day in range(DAYS):
            row = tk.Frame(aeration)
            row.pack(fill=tk.X, padx=5, pady=WIN_PAD)
            tk.Label(row, text=f"Air Flow of Day {day + 1}: ", font=WIN_FONT).pack(side=tk.LEFT)
            entry = tk.Entry(row, font=WIN_FONT, width=10)
            entry.pack(side=tk.LEFT)
            self._air_entries.append(entry)
            tk.Label(row, text="m³ m⁻²h⁻¹ ", font=("Arial", 12)).pack(side=tk.LEFT)
        tk.Button(aeration, text="RUN", command=self._run, font=WIN_FONT, bg="green",
                  fg="white", relief=tk.RAISED, padx=30, pady=4, cursor="hand2").pack(ipadx=2)
        self._result_label = tk.Label(aeration, text="", font=WIN_FONT)
        self._result_label.pack()

        # parameter column
        param_frame = tk.Frame(parent, padx=2)
        param_frame.grid(row=base_row + 1, column=1, sticky="nsew")
        tk.Label(param_frame, text="Input Parameters", font=TITLE_FONT, fg="Navy Blue").grid(
            row=0, column=0, columnspan=4, pady=WIN_PAD, sticky="ew")
        self.params = _LabeledEntries(param_frame)
        build_param_fields(self.params)

        # output column
        output_frame = tk.Frame(parent, padx=20, pady=2)
        output_frame.grid(row=base_row + 1, column=2, sticky="nsew")
        tk.Label(output_frame, text="Output Parameters", font=TITLE_FONT, fg="Navy Blue").grid(
            row=0, column=0, columnspan=4, pady=WIN_PAD, sticky="ew")
        self._outputs = self._build_outputs(output_frame)

        # graph row
        self._graph_frame = tk.Frame(parent)
        self._graph_frame.grid(row=base_row + 2, column=1, columnspan=2, sticky="nsew")
        self._canvas: Optional[FigureCanvasTkAgg] = None

    # -- field helpers --
    def air_schedule(self) -> AirFlowSchedule:
        return AirFlowSchedule([float(e.get()) for e in self._air_entries])

    def _build_outputs(self, frame: tk.Widget) -> Dict[str, tk.StringVar]:
        variables: Dict[str, tk.StringVar] = {}
        for index, (key, text) in enumerate(_OUTPUT_FIELDS):
            # first six in the left column, last six in the right column
            col = 0 if index < 6 else 2
            row = (index % 6) + 1
            tk.Label(frame, text=text, font=WIN_FONT).grid(
                row=row, column=col, pady=WIN_PAD, sticky="w")
            var = tk.StringVar()
            tk.Entry(frame, textvariable=var, state="readonly", width=10,
                     font=WIN_FONT).grid(row=row, column=col + 1, pady=WIN_PAD)
            variables[key] = var
        return variables

    # -- run / display --
    def _run(self) -> None:
        try:
            self._on_run(self)
        except ValueError:
            self._result_label.config(text="Invalid input. Please enter valid numbers.")

    def show_total_air_flow(self, total: float) -> None:
        self._result_label.config(text=f"Total Air Flow: {total}",
                                  font=("Arial", 12, "bold"), pady=2)

    def display(self, result: StageResult, *, title_size: int,
                wc_ylim, oxygen_ylim) -> None:
        for key, var in self._outputs.items():
            var.set("{:.2f}".format(getattr(result.summary, key)))
        figure = plots.build_figure(result.layers, result.summary,
                                    title_size=title_size, wc_ylim=wc_ylim,
                                    oxygen_ylim=oxygen_ylim)
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
        self._canvas = FigureCanvasTkAgg(figure, master=self._graph_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().grid(row=0, column=0, sticky="N")


# --- parameter field layouts for each stage --------------------------------

def _stage1_fields(p: _LabeledEntries) -> None:
    p.add("tci", "Initial Temperature of composting,Tci (°C): ", 1, 0)
    p.add("ta", "Ambient Temperature,Ta (°C): ", 2, 0)
    p.add("hl", "Heat energy from BVS degradation (kJ/kg): ", 3, 0)
    p.add("cpc", "Specific heat capacity of wet material (J/kg.K): ", 4, 0)
    p.add("kc", "Specific heat transfer coefficient,kc (W/m².K): ", 5, 0)
    p.add("k", "Reaction rate,(K_hr): ", 6, 0)
    p.add("rh", "Relative Humidity, K(%): ", 7, 0)
    p.add("initial_mass", "Initial mass of composting waste (kg/m²): ", 1, 2)
    p.add("wc_p", "Initial percentage of water content (%): ", 2, 2)
    p.add("fs_percent", "Initial percentage of Fixed Solid (%): ", 3, 2)
    p.add("nvs_percent", "Initial percentage of N-VS (%): ", 4, 2)
    p.add("vs_percent", "Initial percentage of Volatile Solid (%): ", 5, 2)
    p.add("density", "Density,(kg/m³): ", 6, 2)
    p.add("height", "Height ,(cm): ", 7, 2)


def _stage2_fields(p: _LabeledEntries) -> None:
    p.add("tci", "Initial Temperature of composting,Tci (°C): ", 1, 0)
    p.add("ta", "Ambient Temperature,Ta (°C): ", 2, 0)
    p.add("hl", "Heat energy from BVS degradation (kJ/kg): ", 3, 0)
    p.add("cpc", "Specific heat capacity of wet material (J/kg.K): ", 4, 0)
    p.add("kc", "Specific heat transfer coefficient,kc (W/m².K): ", 1, 2)
    p.add("k", "Reaction rate,(K_hr): ", 2, 2)
    p.add("rh", "Relative Humidity, K(%): ", 3, 2)
    p.add("wc_p", "Initial percentage of water content (%): ", 4, 2)


@dataclass
class _Carryover:
    """Holds stage-1 results so stage 2 can pick them up (replaces globals)."""

    summary: Optional[StageSummary] = None
    density: float = 0.0


def build_app() -> tk.Tk:
    """Construct the full two-stage window and wire the run callbacks."""
    root = tk.Tk()
    root.title("Kinetic Model of Solid Waste Composting")
    root.geometry("1520x920+5+5")

    canvas = tk.Canvas(root)
    canvas.grid(row=0, column=0, sticky="nsew")
    vsb = tk.Scrollbar(root, orient="vertical", command=canvas.yview, width=30)
    vsb.grid(row=0, column=1, sticky="ns")
    hsb = tk.Scrollbar(root, orient="horizontal", command=canvas.xview, width=30)
    hsb.grid(row=1, column=0, sticky="ew")
    canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=frame, anchor="nw")
    frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    tk.Label(root, text="Developed by Q.H. Bari (Prof. @ KUET) & Z.T. Aziz (CE 2k18)",
             font=("Arial", 12, "italic"), fg="Navy Blue").grid(
        row=0, column=0, pady=WIN_PAD, sticky="se")

    carryover = _Carryover()

    def run_stage1(panel: StagePanel) -> None:
        air = panel.air_schedule()
        panel.show_total_air_flow(air.total())
        params = CompostParameters(
            tci=panel.params.value("tci"), ta=panel.params.value("ta"),
            hl=panel.params.value("hl"), kc=panel.params.value("kc"),
            k=panel.params.value("k"), rh=panel.params.value("rh"),
            wc_p=panel.params.value("wc_p"))
        comp = Stage1Composition(
            initial_mass=panel.params.value("initial_mass"),
            fs_percent=panel.params.value("fs_percent"),
            nvs_percent=panel.params.value("nvs_percent"),
            vs_percent=panel.params.value("vs_percent"),
            density=panel.params.value("density"),
            height=panel.params.value("height"))
        result = stage_runner.execute(stage_runner.prepare_stage1(params, comp, air))
        carryover.summary = result.summary
        carryover.density = comp.density
        panel.display(result, title_size=12, wc_ylim=(0, None), oxygen_ylim=(0, 25))

    def run_stage2(panel: StagePanel) -> None:
        if carryover.summary is None:
            panel.show_total_air_flow(0)
            panel._result_label.config(text="Run Stage 1 first.")
            return
        air = panel.air_schedule()
        panel.show_total_air_flow(air.total())
        params = CompostParameters(
            tci=panel.params.value("tci"), ta=panel.params.value("ta"),
            hl=panel.params.value("hl"), kc=panel.params.value("kc"),
            k=panel.params.value("k"), rh=panel.params.value("rh"),
            wc_p=panel.params.value("wc_p"))
        comp = stage_runner.stage2_composition_from(carryover.summary, density=carryover.density)
        result = stage_runner.execute(stage_runner.prepare_stage2(params, comp, air))
        panel.display(result, title_size=14, wc_ylim=(0, 80), oxygen_ylim=(0, 30))

    StagePanel(frame, base_row=1, title="Welcome to KMSWC",
               build_param_fields=_stage1_fields, on_run=run_stage1)
    StagePanel(frame, base_row=4, title="2nd Stage Composting",
               build_param_fields=_stage2_fields, on_run=run_stage2)

    return root
