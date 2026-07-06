#!/usr/bin/env python3
"""Render the anonymised summary table as a publication-quality image.

Reuses the numbers computed by file_summary.compute_table() and draws a clean,
journal-style table (booktabs-like horizontal rules, no vertical lines) using
matplotlib. Saves to vector PDF/SVG (best for LaTeX/Word — scales without
pixelation) and a high-DPI PNG.

Usage:
    python3 render_table.py                         # -> output/table.{pdf,png,svg}
    python3 render_table.py navigation_histories    # explicit folder
    python3 render_table.py --out figures/summary   # custom basename/folder
    python3 render_table.py --formats pdf png        # choose output formats

Requires matplotlib:  pip install matplotlib
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")  # no display needed; just write files
import matplotlib.pyplot as plt

from file_summary import compute_table

# Nicer, shorter column titles for the figure than the raw action strings.
PRETTY = {
    "participant": "Participant",
    "total": "Total",
    "query": "Queries",
    "search result clicked": "Search result\nclicks",
    "playback link clicked": "Playback\nclicks",
    "query/click": "Queries /\nresult click",
    "playback/click": "Playbacks /\nresult click",
}


def render(table, out_base, formats, dpi):
    headers = [PRETTY.get(h, h) for h in table["headers"]]
    body = table["rows"]
    summary = table["summary"]
    data = body + summary

    ncols = len(headers)
    nrows = len(data)

    # Figure size scales with the table; tuned for a single-column-ish figure.
    fig_w = 1.0 + 1.4 * ncols  # extra width so columns don't crowd each other
    fig_h = 0.34 * (nrows + 1.9) + 0.4  # +0.9 extra for the two-line header
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    tbl = ax.table(cellText=data, colLabels=headers, loc="center",
                   cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.35)

    n_summary = len(summary)
    first_summary_row = 1 + len(body)  # +1 for the header row

    for (r, c), cell in tbl.get_celld().items():
        cell.PAD = 0.04
        cell.set_edgecolor("black")
        edges = ""  # booktabs style: only the horizontal rules we add below
        if r == 0:  # header
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f0f0f0")
            edges = "TB"          # rule above and below the header
            cell.set_linewidth(1.0)
            # Headers can be two lines tall; give the row room so the text
            # stays inside the top/bottom rules instead of overflowing them.
            cell.set_height(cell.get_height() * 1.9)
        else:
            # Left-align the participant/label column, centre the numbers.
            cell.set_text_props(ha="left" if c == 0 else "center")
            cell.set_linewidth(0.8)
            if r >= first_summary_row:
                cell.set_text_props(fontweight="bold")  # emphasise stats
        if r == first_summary_row:  # rule above the summary block
            edges += "T"
        if r == nrows:              # bottom rule under the whole table
            edges += "B"
        cell.visible_edges = edges

    out_dir = os.path.dirname(out_base)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    written = []
    for fmt in formats:
        path = f"{out_base}.{fmt}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight",
                    facecolor="white", pad_inches=0.05)
        written.append(path)
    plt.close(fig)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories",
                    help="folder of JSON files (default: navigation_histories)")
    ap.add_argument("--out", default="output/table",
                    help="output basename without extension "
                         "(default: output/table)")
    ap.add_argument("--formats", nargs="+", default=["pdf", "png", "svg"],
                    help="output formats (default: pdf png svg)")
    ap.add_argument("--dpi", type=int, default=300,
                    help="raster DPI for PNG (default: 300)")
    args = ap.parse_args()

    table = compute_table(args.folder)
    written = render(table, args.out, args.formats, args.dpi)
    print("Wrote: " + ", ".join(written))


if __name__ == "__main__":
    sys.exit(main())
