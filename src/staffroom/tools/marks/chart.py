"""Grade distribution as a PNG. Single series, one hue, counts labelled,
recessive axes. Writes a file; not logic.

The file is for paper and slides, not for the screen: it is always drawn on
white in the light palette's ink, whatever theme the launcher is using (#13).
The panel shows the same file; a white chart reads as a card on the dark
theme."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from staffroom.core.table import Table
from staffroom.core.theme_tokens import LIGHT

PAPER = "#ffffff"


def distribution_chart(distribution: Table, path: Path, title: str = "") -> Path:
    p = LIGHT
    grades = [str(g) for g in distribution.column("Grade")]
    counts = [int(c or 0) for c in distribution.column("Count")]
    percents = (
        [p_ or 0 for p_ in distribution.column("Percent")]
        if "Percent" in distribution.columns
        else []
    )

    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
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
    if percents:  # the share under each grade, as the panel shows it (#87)
        ax.set_xticks(range(len(grades)))
        ax.set_xticklabels([f"{g}\n{v:g}%" for g, v in zip(grades, percents, strict=True)])
    ax.set_xlabel("Grade", color=p.text_muted, fontsize=9)
    ax.set_ylabel("Scripts", color=p.text_muted, fontsize=9)
    if title:
        ax.set_title(title, color=p.text, fontsize=11, loc="left", pad=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)
    return path
