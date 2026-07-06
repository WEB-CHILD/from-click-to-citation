#!/usr/bin/env python3
"""Chronological action timeline for the click-based group.

The click-based group is every participant with more playback-link clicks than
queries. For each of them this draws one panel showing their history in order:
each ``query``, ``search result clicked`` and ``playback link clicked`` event is
placed at its entry number on the x-axis and at one of three y-levels, connected
by a line and coloured by action type -- so you can read the back-and-forth
between searching, clicking results, and following playback links.

This is the click-based counterpart of query_click_timeline.py and reuses its
plotting code.

Output: one file per participant in output/click_timeline/ (e.g.
output/click_timeline/P03.{pdf,png,svg}).

Usage:
    python3 click_timeline.py
    python3 click_timeline.py path/to/folder
    python3 click_timeline.py --out-dir figures/click_timeline
"""

import argparse

from query_click_timeline import gather_sequences, click_based, plot_individual


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories")
    ap.add_argument("--out-dir", default="output/click_timeline",
                    help="folder for per-participant files "
                         "(default: output/click_timeline)")
    ap.add_argument("--formats", nargs="+", default=["pdf", "png", "svg"])
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    sequences = gather_sequences(args.folder)
    participants = click_based(sequences)
    if not participants:
        raise SystemExit("No click-based participants found.")
    print(f"Click-based participants ({len(participants)}): "
          + ", ".join(participants))

    title = ("Click-based group: chronological query ↔ result-click "
             "↔ playback sequence")
    written = plot_individual(sequences, participants, args.out_dir,
                              args.formats, args.dpi, title)
    print(f"Wrote {len(written)} files to {args.out_dir}/")


if __name__ == "__main__":
    main()
