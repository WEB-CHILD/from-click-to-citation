#!/usr/bin/env python3
"""Group participants by browsing style and tabulate the two groups.

Each participant is classified from their raw action counts:

  * query-based  : more queries than playback-link clicks
  * click-based  : more playback-link clicks than queries
  * (balanced)   : exactly equal -- listed separately, if any

The table lists the participants in each group with their counts and the two
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
import statistics
import sys

from file_summary import gather_counts, fmt_ratio

COLUMNS = ["participant", "total", "query", "search result clicked",
           "playback link clicked", "query/click", "playback/click"]

PRETTY = {
    "participant": "Participant",
    "total": "Total",
    "query": "Queries",
    "search result clicked": "Search result\nclicks",
    "playback link clicked": "Playback\nclicks",
    "query/click": "Queries /\nresult click",
    "playback/click": "Playbacks /\nresult click",
}


def classify(per_file):
    """Return ordered (group_title, [participant ids]) buckets."""
    query_based, click_based, balanced = [], [], []
    for pid in sorted(per_file):
        counts = per_file[pid]
        queries = counts.get("query", 0)
        playbacks = counts.get("playback link clicked", 0)
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
    queries = counts.get("query", 0)
    playbacks = counts.get("playback link clicked", 0)
    clicks = counts.get("search result clicked", 0)
    return [
        pid,
        str(sum(counts.values())),
        str(queries),
        str(clicks),
        str(playbacks),
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
        clicks = per_file[p].get("search result clicked", 0)
        if clicks:
            ratios_q.append(per_file[p].get("query", 0) / clicks)
            ratios_p.append(per_file[p].get("playback link clicked", 0) / clicks)

    return [
        f"{label} (n={len(members)})",
        f"{fn(totals):.1f}",
        f"{col('query'):.1f}",
        f"{col('search result clicked'):.1f}",
        f"{col('playback link clicked'):.1f}",
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


def render_image(groups, per_file, out_base, formats, dpi):
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
    fig_h = 0.34 * (nrows + 1.9) + 0.4
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
    ap.add_argument("--out", default="output/grouped_table",
                    help="image basename without extension "
                         "(default: output/grouped_table)")
    ap.add_argument("--formats", nargs="+", default=["pdf", "png", "svg"],
                    help="image formats (default: pdf png svg)")
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
