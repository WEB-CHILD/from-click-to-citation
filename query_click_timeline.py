#!/usr/bin/env python3
"""Chronological query-vs-result-click timeline for the query-based group.

For every participant whose history has more queries than link clicks (the
"query-based" group), this draws one panel showing their search journey in
order: every entry is placed at its entry number on the x-axis and at one of
five y-levels -- query, search result click, link click, failed playback (a
link to a page that was never harvested) and other navigation (toolbar,
back/forward, reloads, automatic and typed navigation) -- connected by a line
so you can read the back-and-forth between searching, clicking results, and
following links. Dots are coloured by level.

Output: one file per participant in output/query_click_timeline/ (e.g.
output/query_click_timeline/P01.png).

Usage:
    python3 query_click_timeline.py
    python3 query_click_timeline.py path/to/folder
    python3 query_click_timeline.py --out-dir figures/timeline
"""

import argparse
import math
import os
from collections import Counter

from file_summary import (DEFAULT_FOLDER, QUERY, RESULT, LINK, FAILED,
                          load_histories)

# Colour-blind-friendly (Wong) palette. Failed and link clicks sit next to each
# other at only ~7.6 ΔE for deuteranopes, which is fine here because every
# colour also has its own labelled y-level.
COLOR_QUERY = "#0072B2"  # blue
COLOR_CLICK = "#D55E00"  # vermillion
COLOR_PLAYBACK = "#009E73"  # green
COLOR_FAILED = "#CC79A7"  # reddish purple
COLOR_OTHER = "#8C8C8C"  # grey: navigation the participant did not pick a page for

# Every action that is not a query, result, link or failure is drawn together.
NAVIGATION = "other navigation"

# y-level for each group (top to bottom), with its tick label and colour.
LEVELS = [
    (QUERY, "query", COLOR_QUERY),
    (RESULT, "result\nclick", COLOR_CLICK),
    (LINK, "link\nclick", COLOR_PLAYBACK),
    (FAILED, "failed\nplayback", COLOR_FAILED),
    (NAVIGATION, "other\nnavigation", COLOR_OTHER),
]
LEVEL = {group: len(LEVELS) - 1 - i for i, (group, _, _) in enumerate(LEVELS)}
LEGEND = {QUERY: "QUERY", RESULT: "SEARCH_RESULT_CLICKED",
          LINK: "PLAYBACK_LINK_CLICKED", FAILED: "PLAYBACK_FAILED",
          NAVIGATION: "other navigation"}


def group_of(action):
    return action if action in LEVEL else NAVIGATION


def gather_sequences(folder):
    """Return ``{participant: [(number, action), ...]}`` in chronological order."""
    return {pid: [(r.get("number", i), r.get("action"))
                  for i, r in enumerate(records)]
            for pid, records in load_histories(folder).items()}


def query_based(sequences):
    """Participant ids with more queries than link clicks, sorted."""
    selected = []
    for pid, seq in sequences.items():
        counts = Counter(action for _, action in seq)
        if counts.get(QUERY, 0) > counts.get(LINK, 0):
            selected.append(pid)
    return sorted(selected)


def click_based(sequences):
    """Participant ids with more link clicks than queries, sorted."""
    selected = []
    for pid, seq in sequences.items():
        counts = Counter(action for _, action in seq)
        if counts.get(LINK, 0) > counts.get(QUERY, 0):
            selected.append(pid)
    return sorted(selected)


def _draw_panel(ax, sequences, pid):
    """Draw one participant's action timeline onto ``ax``."""
    xs = [num for num, _ in sequences[pid]]
    ys = [LEVEL[group_of(act)] for _, act in sequences[pid]]

    ax.plot(xs, ys, color="0.7", lw=0.8, zorder=1)
    for group, _, color in LEVELS:
        level = LEVEL[group]
        xa = [x for x, y in zip(xs, ys) if y == level]
        ax.scatter(xa, [level] * len(xa), s=22, color=color, zorder=2)

    ax.set_yticks([LEVEL[group] for group, _, _ in LEVELS])
    ax.set_yticklabels([label for _, label, _ in LEVELS], fontsize=7)
    ax.set_ylim(-0.6, len(LEVELS) - 0.4)
    ax.set_title(pid, fontsize=10, loc="left", fontweight="bold")
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel("entry number", fontsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _legend_handles():
    from matplotlib.lines import Line2D
    return [Line2D([0], [0], marker="o", linestyle="", color=color,
                   label=LEGEND[group], markersize=7)
            for group, _, color in LEVELS]


def plot(sequences, participants, out_base, formats, dpi, ncols, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(participants)
    ncols = max(1, min(ncols, n))
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(6.0 * ncols, 2.4 * nrows),
                             squeeze=False)

    for idx, pid in enumerate(participants):
        _draw_panel(axes[idx // ncols][idx % ncols], sequences, pid)

    # Blank out any unused panels in the grid.
    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].axis("off")

    fig.legend(handles=_legend_handles(), loc="upper center", ncol=3,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(title, fontsize=11, y=1.02)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    out_dir = os.path.dirname(out_base)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    written = []
    for fmt in formats:
        path = f"{out_base}.{fmt}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
        written.append(path)
    plt.close(fig)
    return written


def plot_individual(sequences, participants, out_dir, formats, dpi, title):
    """Write one figure file per participant into ``out_dir``.

    Each participant ``pid`` produces ``out_dir/{pid}.{fmt}`` for every format.
    Returns the list of written paths.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for pid in participants:
        fig, ax = plt.subplots(figsize=(6.0, 2.6))
        _draw_panel(ax, sequences, pid)

        fig.legend(handles=_legend_handles(), loc="upper center", ncol=3,
                   frameon=False, fontsize=7, bbox_to_anchor=(0.5, 1.02))
        fig.suptitle(title, fontsize=10, y=1.1)
        fig.tight_layout(rect=(0, 0, 1, 0.95))

        for fmt in formats:
            path = os.path.join(out_dir, f"{pid}.{fmt}")
            fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
            written.append(path)
        plt.close(fig)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    ap.add_argument("--out-dir", default="output/query_click_timeline",
                    help="folder for per-participant files "
                         "(default: output/query_click_timeline)")
    ap.add_argument("--formats", nargs="+", default=["png"])
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    sequences = gather_sequences(args.folder)
    participants = query_based(sequences)
    if not participants:
        raise SystemExit("No query-based participants found.")
    print(f"Query-based participants ({len(participants)}): "
          + ", ".join(participants))

    title = "Query-based strategy"
    written = plot_individual(sequences, participants, args.out_dir,
                              args.formats, args.dpi, title)
    print(f"Wrote {len(written)} files to {args.out_dir}/")


if __name__ == "__main__":
    main()
