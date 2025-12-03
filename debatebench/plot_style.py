"""Shared plotting style that matches the dashboard dark theme."""

from __future__ import annotations

import matplotlib.pyplot as plt
import seaborn as sns

# Core palette draws from dashboard accent blues.
PRIMARY_SEQ = ["#4dd3ff", "#6fe1ff", "#8fc7ff", "#b5e8ff", "#d9f7ff"]
TEXT = "#e9eef7"
MUTED = "#98a7bf"
CARD = "#141d28"
BORDER = "#1f2c3a"


def apply_dark_theme():
    """
    Configure matplotlib/seaborn to render on a dark card with transparent
    figure background so PNGs drop onto the dashboard cleanly.
    Returns commonly used palettes/cmaps.
    """
    sns.set_theme(style="ticks")
    plt.rcParams.update(
        {
            "figure.facecolor": "none",  # keep transparent for embedding
            "savefig.facecolor": "none",
            "axes.facecolor": CARD,
            "axes.edgecolor": BORDER,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "axes.titleweight": "semibold",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "grid.color": BORDER,
            "grid.alpha": 0.18,
            "text.color": TEXT,
            "figure.dpi": 140,
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    sns.set_palette(PRIMARY_SEQ)
    seq_cmap = sns.color_palette(PRIMARY_SEQ, as_cmap=True)
    div_cmap = sns.diverging_palette(191, 24, s=80, l=55, center="light", as_cmap=True)
    return {"seq": PRIMARY_SEQ, "seq_cmap": seq_cmap, "div_cmap": div_cmap}


def style_axes(ax):
    """Apply light grid + despine for consistency."""
    ax.grid(alpha=0.18)
    sns.despine(ax=ax)
