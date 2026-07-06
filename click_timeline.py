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

Output: output/click_timeline.{pdf,png,svg}

Usage:
    python3 click_timeline.py
    python3 click_timeline.py path/to/folder
    python3 click_timeline.py --ncols 3 --out figures/click_timeline
"""

import argparse

from query_click_timeline import gather_sequences, click_based, plot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories")
    ap.add_argument("--out", default="output/click_timeline",
                    help="image basename (default: output/click_timeline)")
    ap.add_argument("--formats", nargs="+", default=["pdf", "png", "svg"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--ncols", type=int, default=2,
                    help="number of panel columns (default: 2)")
    args = ap.parse_args()

    sequences = gather_sequences(args.folder)
    participants = click_based(sequences)
    if not participants:
        raise SystemExit("No click-based participants found.")
    print(f"Click-based participants ({len(participants)}): "
          + ", ".join(participants))

    title = ("Click-based group: chronological query ↔ result-click "
             "↔ playback sequence")
    written = plot(sequences, participants, args.out, args.formats,
                   args.dpi, args.ncols, title)
    print("Wrote: " + ", ".join(written))


if __name__ == "__main__":
    main()
