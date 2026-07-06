#!/usr/bin/env python3
"""Chronological query-vs-result-click timeline for the query-based group.

For every participant whose history has more queries than playback-link clicks
(the "query-based" group), this draws one panel showing their search journey in
order: each ``query``, ``search result clicked`` and ``playback link clicked``
event is placed at its entry number on the x-axis and at one of three y-levels,
connected by a line so you can read the back-and-forth between searching,
clicking results, and following playback links. Dots are coloured by action
type.

Output: one file per participant in output/query_click_timeline/ (e.g.
output/query_click_timeline/P01.png).

Usage:
    python3 query_click_timeline.py
    python3 query_click_timeline.py path/to/folder
    python3 query_click_timeline.py --out-dir figures/timeline
"""

import argparse
import glob
import math
import os
import sys
from collections import Counter

from file_summary import MAP_FILE, load_records, load_or_create_mapping

QUERY = "query"
CLICK = "search result clicked"
PLAYBACK = "playback link clicked"

# Colour-blind-friendly (Wong) palette.
COLOR_QUERY = "#0072B2"  # blue
COLOR_CLICK = "#D55E00"  # vermillion
COLOR_PLAYBACK = "#009E73"  # green

# y-level for each action type (top to bottom).
LEVEL = {QUERY: 2, CLICK: 1, PLAYBACK: 0}


def gather_sequences(folder):
    """Return ``{participant: [(number, action), ...]}`` in chronological order."""
    paths = sorted(glob.glob(os.path.join(folder, "*.json")))
    if not paths:
        raise SystemExit(f"No JSON files found in {folder!r}")

    by_name = {}
    for path in paths:
        try:
            records = load_records(path)
        except (ValueError, OSError) as exc:
            print(f"  ! skipping {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        seq = [(r.get("number", i), r.get("action"))
               for i, r in enumerate(records)]
        seq.sort(key=lambda t: t[0])
        by_name[os.path.basename(path)] = seq

    mapping = load_or_create_mapping(by_name.keys(), MAP_FILE)
    return {mapping[name]: seq for name, seq in by_name.items()}


def query_based(sequences):
    """Participant ids with more queries than playback clicks, sorted."""
    selected = []
    for pid, seq in sequences.items():
        counts = Counter(action for _, action in seq)
        if counts.get(QUERY, 0) > counts.get(PLAYBACK, 0):
            selected.append(pid)
    return sorted(selected)


def click_based(sequences):
    """Participant ids with more playback clicks than queries, sorted."""
    selected = []
    for pid, seq in sequences.items():
        counts = Counter(action for _, action in seq)
        if counts.get(PLAYBACK, 0) > counts.get(QUERY, 0):
            selected.append(pid)
    return sorted(selected)


def _draw_panel(ax, sequences, pid):
    """Draw one participant's action timeline onto ``ax``."""
    # Keep the three action types, in chronological order.
    events = [(num, act) for num, act in sequences[pid] if act in LEVEL]
    xs = [num for num, _ in events]
    ys = [LEVEL[act] for _, act in events]

    ax.plot(xs, ys, color="0.7", lw=0.8, zorder=1)
    for action, color in ((QUERY, COLOR_QUERY), (CLICK, COLOR_CLICK),
                          (PLAYBACK, COLOR_PLAYBACK)):
        level = LEVEL[action]
        xa = [x for x, y in zip(xs, ys) if y == level]
        ax.scatter(xa, [level] * len(xa), s=22, color=color, zorder=2)

    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["playback\nclick", "result\nclick", "query"],
                       fontsize=8)
    ax.set_ylim(-0.6, 2.6)
    ax.set_title(pid, fontsize=10, loc="left", fontweight="bold")
    ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel("entry number", fontsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _legend_handles():
    from matplotlib.lines import Line2D
    return [
        Line2D([0], [0], marker="o", linestyle="", color=COLOR_QUERY,
               label="query", markersize=7),
        Line2D([0], [0], marker="o", linestyle="", color=COLOR_CLICK,
               label="search result clicked", markersize=7),
        Line2D([0], [0], marker="o", linestyle="", color=COLOR_PLAYBACK,
               label="playback link clicked", markersize=7),
    ]


def plot(sequences, participants, out_base, formats, dpi, ncols, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(participants)
    ncols = max(1, min(ncols, n))
    nrows = math.ceil(n / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(6.0 * ncols, 1.7 * nrows),
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
        fig, ax = plt.subplots(figsize=(6.0, 1.9))
        _draw_panel(ax, sequences, pid)

        fig.legend(handles=_legend_handles(), loc="upper center", ncol=3,
                   frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
        fig.suptitle(title, fontsize=10, y=1.06)
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
    ap.add_argument("folder", nargs="?", default="navigation_histories")
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

    title = ("Query-based group: chronological query ↔ result-click "
             "↔ playback sequence")
    written = plot_individual(sequences, participants, args.out_dir,
                              args.formats, args.dpi, title)
    print(f"Wrote {len(written)} files to {args.out_dir}/")


if __name__ == "__main__":
    main()
