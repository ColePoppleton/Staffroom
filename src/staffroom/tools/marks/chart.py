"""Grade distribution as a PNG. Single series, one hue, counts labelled,
recessive axes, drawn in the app's theme colours. Writes a file; not logic."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from staffroom.core.table import Table
from staffroom.core.theme_tokens import palette


def distribution_chart(
    distribution: Table, path: Path, theme: str = "dark", title: str = ""
) -> Path:
    p = palette(theme)
    grades = [str(g) for g in distribution.column("Grade")]
    counts = [int(c or 0) for c in distribution.column("Count")]

    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    fig.patch.set_facecolor(p.surface)
    ax.set_facecolor(p.surface)
    bars = ax.bar(grades, counts, width=0.62, color=p.accent, linewidth=0)
    for bar, count in zip(bars, counts, strict=True):
        if count:
            ax.annotate(
                str(count),
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                color=p.text,
            )
    ax.set_ylim(0, max([*counts, 1]) * 1.18)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.grid(True, color=p.border, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(p.border_strong)
    ax.tick_params(colors=p.text_muted, labelsize=9, length=0)
    ax.set_xlabel("Grade", color=p.text_muted, fontsize=9)
    ax.set_ylabel("Scripts", color=p.text_muted, fontsize=9)
    if title:
        ax.set_title(title, color=p.text, fontsize=11, loc="left", pad=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
