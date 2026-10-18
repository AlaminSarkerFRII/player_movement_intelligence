"""Shared figure style and helpers (static matplotlib figures for the report).

Colours follow a validated categorical palette; the first three slots stay
distinguishable for colour-blind readers even when all pairs are compared
(scatter plots), so per-game figures use at most three colours.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: works in Docker and over SSH
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, Circle, Rectangle  # noqa: E402

from pmi.config import Config  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
PITCH_LINE = "#b9b8b2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3 (blue, orange, aqua)


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "font.size": 10,
        "legend.frameon": False,
        "legend.labelcolor": TEXT,
        "lines.linewidth": 2,
        "figure.dpi": 110,
    })


def game_colors(match_ids: list[str]) -> dict[str, str]:
    """Fixed colour per match, assigned in sorted order (never by rank or value)."""
    ids = sorted(match_ids)
    if len(ids) > len(SERIES):
        raise ValueError("more than three series: facet the figure instead")
    return dict(zip(ids, SERIES, strict=False))


def draw_pitch(ax, length: float = 105.0, width: float = 68.0) -> None:
    """Draw a pitch centred at (0, 0) in meters, attacking towards +x."""
    hl, hw = length / 2, width / 2
    kw = {"fill": False, "edgecolor": PITCH_LINE, "linewidth": 1.2, "zorder": 0}
    ax.add_patch(Rectangle((-hl, -hw), length, width, **kw))
    ax.plot([0, 0], [-hw, hw], color=PITCH_LINE, lw=1.2, zorder=0)
    ax.add_patch(Circle((0, 0), 9.15, **kw))
    for s in (-1, 1):
        ax.add_patch(Rectangle((s * hl - (16.5 if s > 0 else 0), -20.16), 16.5, 40.32, **kw))
        ax.add_patch(Rectangle((s * hl - (5.5 if s > 0 else 0), -9.16), 5.5, 18.32, **kw))
        ax.add_patch(Arc((s * (hl - 11), 0), 18.3, 18.3, theta1=127 if s > 0 else -53,
                         theta2=233 if s > 0 else 53, edgecolor=PITCH_LINE, lw=1.2))
    ax.set_xlim(-hl - 3, hl + 3)
    ax.set_ylim(-hw - 3, hw + 3)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def save(fig, name: str, cfg: Config) -> Path:
    out = cfg.path("figures")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path
