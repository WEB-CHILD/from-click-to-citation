#!/usr/bin/env python3
"""Group participants by browsing style and tabulate the two groups.

Each participant is classified from their raw action counts:

  * query-based  : more queries than link clicks (PLAYBACK_LINK_CLICKED)
  * click-based  : more link clicks than queries
  * (balanced)   : exactly equal -- listed separately, if any

The table lists the participants in each group with their counts (including
failed playbacks: links to pages that were never harvested) and the two
per-search-result-click ratios, plus a per-group mean row. It prints as text and
(if matplotlib is available) renders a publication-quality image to output/.

Usage:
    python3 grouped_table.py                       # text + output/grouped_table.*
    python3 grouped_table.py path/to/folder
    python3 grouped_table.py --no-image            # text only
    python3 grouped_table.py --out figures/groups  # custom image basename
"""

import argparse
import os
import re
import shutil
import statistics
import sys

from file_summary import (DEFAULT_FOLDER, QUERY, RESULT, LINK, FAILED,
                          gather_counts, fmt_ratio)

ARTICLE_DIR = os.path.join("output", "figures_in_article")

COLUMNS = ["participant", "total", QUERY, RESULT, LINK, FAILED,
           "query/click", "link/click"]

PRETTY = {
    "participant": "Participant",
    "total": "Total",
    QUERY: "Queries",
    RESULT: "Search result\nclicks",
    LINK: "Link\nclicks",
    FAILED: "Failed\nplayback",
    "query/click": "Queries /\nresult click",
    "link/click": "Links /\nresult click",
}


def classify(per_file):
    """Return ordered (group_title, [participant ids]) buckets."""
    query_based, click_based, balanced = [], [], []
    for pid in sorted(per_file):
        counts = per_file[pid]
        queries = counts.get(QUERY, 0)
        playbacks = counts.get(LINK, 0)
        if queries > playbacks:
            query_based.append(pid)
        elif playbacks > queries:
            click_based.append(pid)
        else:
            balanced.append(pid)

    groups = [
        ("Query-based", query_based),
        ("Click-based", click_based),
    ]
    if balanced:
        groups.append(("Balanced", balanced))
    return [(title, members) for title, members in groups if members]


def data_cells(pid, counts):
    queries = counts.get(QUERY, 0)
    playbacks = counts.get(LINK, 0)
    clicks = counts.get(RESULT, 0)
    return [
        pid,
        str(sum(counts.values())),
        str(queries),
        str(clicks),
        str(playbacks),
        str(counts.get(FAILED, 0)),
        fmt_ratio(queries, clicks),
        fmt_ratio(playbacks, clicks),
    ]


def stat_cells(label, members, per_file, fn):
    """Per-group summary row; ``fn`` is statistics.mean or statistics.median."""
    def col(action):
        return fn([per_file[p].get(action, 0) for p in members])

    totals = [sum(per_file[p].values()) for p in members]
    ratios_q, ratios_p = [], []
    for p in members:
        clicks = per_file[p].get(RESULT, 0)
        if clicks:
            ratios_q.append(per_file[p].get(QUERY, 0) / clicks)
            ratios_p.append(per_file[p].get(LINK, 0) / clicks)

    return [
        f"{label} (n={len(members)})",
        f"{fn(totals):.1f}",
        f"{col(QUERY):.1f}",
        f"{col(RESULT):.1f}",
        f"{col(LINK):.1f}",
        f"{col(FAILED):.1f}",
        f"{fn(ratios_q):.2f}" if ratios_q else "n/a",
        f"{fn(ratios_p):.2f}" if ratios_p else "n/a",
    ]


def build_rows(groups, per_file):
    """Return a flat list of (kind, cells) where kind is section/data/stat."""
    rows = []
    for title, members in groups:
        rows.append(("section", [title] + [""] * (len(COLUMNS) - 1)))
        for pid in members:
            rows.append(("data", data_cells(pid, per_file[pid])))
        rows.append(("stat", stat_cells("Group mean", members, per_file,
                                         statistics.mean)))
        rows.append(("stat", stat_cells("Group median", members, per_file,
                                         statistics.median)))
    return rows


def print_table(groups, per_file):
    rows = build_rows(groups, per_file)
    header = [PRETTY[c].replace("\n", " ") for c in COLUMNS]
    body = [cells for _, cells in rows]
    widths = [max(len(r[i]) for r in [header] + body) for i in range(len(COLUMNS))]

    def render(cells):
        out = cells[0].ljust(widths[0])
        for i in range(1, len(cells)):
            out += "  " + cells[i].rjust(widths[i])
        return out

    line = "-" * len(render(header))
    print(render(header))
    print(line)
    for kind, cells in rows:
        if kind == "section":
            print(f"\n{cells[0]}")
        else:
            print(render(cells))
    print(line)


def copy_to_article(path, title):
    """Copy the figure at ``path`` to the article folder; return the new path.

    The copy is named after ``title``, with spaces as underscores. Punctuation
    is dropped because colons are not valid in filenames on every system and
    apostrophes need quoting in a shell.
    """
    name = re.sub(r"[^\w ]", "", title).replace(" ", "_")
    target = os.path.join(ARTICLE_DIR, name + os.path.splitext(path)[1])
    os.makedirs(ARTICLE_DIR, exist_ok=True)
    shutil.copyfile(path, target)
    return target


def seat_title(fig, ax, tbl, title, note=None):
    """Put ``title`` directly above table ``tbl``; return the box to save.

    The table is centred in the axes, so a default title (top of axes) floats
    well above it. This seats the title on the table's top edge, adds the
    optional ``note`` under the table, and returns a crop around them for
    ``bbox_inches``, since "tight" would keep the axes' empty margins.
    """
    from matplotlib.transforms import Bbox

    renderer = fig.canvas.get_renderer()
    table_box = tbl.get_window_extent(renderer)
    table_top = ax.transAxes.inverted().transform((0, table_box.y1))[1]
    label = ax.set_title(title, fontsize=11, fontweight="bold",
                         y=table_top, pad=6)
    boxes = [table_box, label.get_window_extent(renderer)]
    if note:
        corner = ax.transAxes.inverted().transform((table_box.x0, table_box.y0))
        text = ax.annotate(note, xy=corner, xycoords="axes fraction",
                           xytext=(0, -6), textcoords="offset points",
                           fontsize=9, ha="left", va="top")
        boxes.append(text.get_window_extent(renderer))
    return (Bbox.union(boxes)
            .transformed(fig.dpi_scale_trans.inverted())
            .padded(0.05))


def render_image(groups, per_file, out_base, formats, dpi, title=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  (matplotlib not installed -> skipping image; "
              "see README Setup)", file=sys.stderr)
        return []

    rows = build_rows(groups, per_file)
    headers = [PRETTY[c] for c in COLUMNS]
    data = [cells for _, cells in rows]
    kinds = [kind for kind, _ in rows]
    ncols = len(headers)
    nrows = len(data)

    fig_w = 1.0 + 1.4 * ncols
    fig_h = 0.34 * (nrows + 1.9) + (0.7 if title else 0.4)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    tbl = ax.table(cellText=data, colLabels=headers, loc="center",
                   cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.35)

    for (r, c), cell in tbl.get_celld().items():
        cell.PAD = 0.04
        cell.set_edgecolor("black")
        edges = ""
        if r == 0:  # column header
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f0f0f0")
            cell.set_linewidth(1.0)
            cell.set_height(cell.get_height() * 1.9)
            edges = "TB"
        else:
            kind = kinds[r - 1]
            cell.set_linewidth(0.8)
            if kind == "section":
                cell.set_facecolor("#dcdcdc")
                cell.set_text_props(fontweight="bold",
                                    ha="left" if c == 0 else "center")
                edges = "TB"
            elif kind == "stat":
                cell.set_text_props(fontweight="bold",
                                    ha="left" if c == 0 else "center")
                # Rule above the first stat row, separating it from the data.
                if kinds[r - 2] == "data":
                    edges += "T"
            else:  # data
                cell.set_text_props(ha="left" if c == 0 else "center")
        if r == nrows:  # bottom rule under the whole table
            edges += "B"
        cell.visible_edges = edges

    crop = seat_title(fig, ax, tbl, title) if title else "tight"

    out_dir = os.path.dirname(out_base)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    written = []
    for fmt in formats:
        path = f"{out_base}.{fmt}"
        fig.savefig(path, dpi=dpi, bbox_inches=crop,
                    facecolor="white", pad_inches=0.05)
        written.append(path)
    plt.close(fig)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=DEFAULT_FOLDER,
                    help=f"folder of JSON files (default: {DEFAULT_FOLDER})")
    ap.add_argument("--out", default="output/grouped_table",
                    help="image basename without extension "
                         "(default: output/grouped_table)")
    ap.add_argument("--formats", nargs="+", default=["png"],
                    help="image formats (default: png)")
    ap.add_argument("--dpi", type=int, default=300, help="PNG DPI (default: 300)")
    ap.add_argument("--no-image", action="store_true",
                    help="print the text table only, skip the image")
    args = ap.parse_args()

    per_file, _ = gather_counts(args.folder)
    groups = classify(per_file)
    print_table(groups, per_file)

    if not args.no_image:
        written = render_image(groups, per_file, args.out, args.formats, args.dpi)
        if written:
            print("\nWrote: " + ", ".join(written))


if __name__ == "__main__":
    main()
