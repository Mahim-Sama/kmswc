"""The six-panel result figure, built once and reused by both stages.

The original repeated this ~120-line plotting block for stage 1 and stage 2 with
only the title font sizes and y-limits tweaked. Here it is a single function
parameterised by those small differences.
"""

from __future__ import annotations

from typing import List

import numpy as np
from matplotlib.figure import Figure

from ..domain.parameters import LAYER_COUNT
from ..domain.series import LayerSeries, StageSummary

_LABEL_FONT = {"size": 10}
_HEIGHT_COLORS = ["tomato", "darkorange", "burlywood",
                  "antiquewhite", "lightseagreen", "teal"]
_COMPOSITION_COLORS = ["midnightblue", "steelblue", "skyblue", "gold"]


def _line_panel(ax, layers: List[LayerSeries], attr: str, ylabel: str,
                title: str, title_size: int, ylim, label_prefix: str) -> None:
    for index, layer in enumerate(layers, start=1):
        ax.plot(layer.time_hours, getattr(layer, attr), label=f"{label_prefix}{index}")
    ax.set_xlabel("Time", fontdict=_LABEL_FONT)
    ax.set_ylabel(ylabel, fontdict=_LABEL_FONT)
    ax.set_title(title, fontsize=title_size, color="steelblue", fontweight="bold")
    ax.set_xlim(0)
    ax.set_ylim(*ylim)
    ax.legend(fontsize="x-small")


def _height_panel(ax, summary: StageSummary, title_size: int) -> None:
    x = ["I.ht", "F.ht"]
    layer_pair = np.array([summary.initial_layer_height, summary.final_layer_height])
    bars = []
    bottom = np.zeros(2)
    for color in _HEIGHT_COLORS:
        bars.append(ax.bar(x, layer_pair, bottom=bottom, color=color))
        bottom = bottom + layer_pair
    ax.set_ylabel("Height in cm")
    ax.set_title("Height at Initial State VS Final State",
                 fontsize=title_size, color="steelblue", fontweight="bold")

    for level, bar in enumerate(bars):
        for col, rect in enumerate(bar):
            height = rect.get_height()
            ax.text(rect.get_x() + rect.get_width() / 2, height, f"{height:.0f}",
                    ha="center", va="center", color="midnightblue", fontweight="bold")
            if level > 0:
                cumulative = sum(bars[lv][col].get_height() for lv in range(level))
                ax.text(rect.get_x() + rect.get_width() / 2, cumulative + height,
                        f"{cumulative + height:.0f}", ha="center", va="center",
                        color="midnightblue", fontweight="bold")


def _composition_panel(ax, summary: StageSummary, title_size: int) -> None:
    x = ["Initial Composition", "Final Composition"]
    fs = np.array([summary.mb_fixed_solid, summary.final_fixed_solid])
    nvs = np.array([summary.mb_non_volatile_solid, summary.final_non_volatile_solid])
    vs = np.array([summary.mb_volatile_solid, summary.final_volatile_solid])
    water = np.array([summary.mb_water, summary.final_water])

    stacks = [fs, nvs, vs, water]
    bottom = np.zeros(2)
    for values, color in zip(stacks, _COMPOSITION_COLORS):
        ax.bar(x, values, bottom=bottom, color=color)
        bottom = bottom + values

    running = np.zeros(2)
    for values in stacks:
        text_color = "white" if values is fs or values is nvs else "black"
        for col, value in enumerate(values):
            ax.text(col, running[col] + value / 2, f"{value:.2f}",
                    ha="center", va="center", color=text_color, fontweight="bold")
        running = running + values

    ax.set_ylabel("MB in kg/m3")
    ax.legend(["FS", "N-VS", "B-VS", "Water"], fontsize="xx-small")
    ax.set_title("Composition at Initial State VS Final State",
                 fontsize=title_size, color="steelblue", fontweight="bold")


def build_figure(layers: List[LayerSeries], summary: StageSummary,
                 *, title_size: int = 12, temperature_ylim=(0, 80),
                 oxygen_ylim=(0, 25), wc_ylim=(0, None)) -> Figure:
    """Assemble the full 2x3 result figure for one stage."""
    assert len(layers) == LAYER_COUNT
    fig = Figure(figsize=(15, 7.5))
    fig.subplots_adjust(hspace=0.6)
    ax = fig.subplots(2, 3)

    _line_panel(ax[0, 0], layers, "temperature", "Temperature(°C)",
                "Time vs Temperature(°C)", title_size, temperature_ylim, "Ta_L")
    _line_panel(ax[0, 1], layers, "volatile_solid", "VS%",
                "Time vs VS%", title_size, (0, None), "Vs_L")
    _line_panel(ax[1, 0], layers, "water_content_percent", "WC%",
                "Time vs WC%", title_size, wc_ylim, "WC_L")
    _line_panel(ax[1, 1], layers, "oxygen_percent", "O2%",
                "Time vs O2%", title_size, oxygen_ylim, "O2%_L")
    _height_panel(ax[0, 2], summary, title_size)
    _composition_panel(ax[1, 2], summary, title_size)

    fig.suptitle("Changes of Different Parameters of KMSWC",
                 fontweight="bold", fontsize=28, color="navy")
    fig.tight_layout()
    return fig
