#!/usr/bin/env python3
"""Find consecutive repeats of the *exact same* action in each history.

For every ``*.json`` file this walks the participant's entries in chronological
order and looks for runs where the identical event repeats back-to-back -- e.g.
the same playback link clicked again and again, or the same query fired several
times in a row. "Identical" means same action *and* same target: the url for a
``search result clicked`` / ``playback link clicked``, or the query string plus
its filters for a ``query``.

It renders booktabs-style table images into output/repeat_runs/: one table per
participant listing their runs of length >= --min-run (longest first), plus a
``summary`` table of everyone's longest run. Each is saved as a PNG (pass
--formats for vector PDF/SVG instead). Files are anonymised through
participant_map.json (the same P01, P02, ... ids the other scripts use).

Output: output/repeat_runs/{P01,...}.png and
        output/repeat_runs/summary.png

Usage:
    python3 repeat_runs.py                    # all files, runs of length >= 2
    python3 repeat_runs.py path/to/folder
    python3 repeat_runs.py --min-run 3        # only tables for runs of 3+
    python3 repeat_runs.py --out-dir figures/repeats
"""

import argparse
import glob
import os
import sys

from file_summary import MAP_FILE, load_records, load_or_create_mapping

QUERY = "query"
CLICK = "search result clicked"
PLAYBACK = "playback link clicked"


def signature(record):
    """A hashable identity for an event: (action, target).

    Two records with the same signature are treated as the exact same action.
    """
    action = record.get("action", "(none)")
    if action == QUERY:
        filters = tuple(record.get("filterQueries") or ())
        return (action, record.get("query", ""), filters)
    if action in (CLICK, PLAYBACK):
        return (action, record.get("url", ""))
    # Fall back to the whole record (minus its position) for unknown actions.
    return (action, tuple(sorted(
        (k, str(v)) for k, v in record.items() if k not in ("action", "number"))))


def describe(sig):
    """Short human-readable label for a signature."""
    action = sig[0]
    if action == QUERY:
        _, query, filters = sig
        label = f"`{query}`" if query != "" else "(empty query)"
        if filters:
            label += " — filters: " + ", ".join(filters)
        return action, label
    if action in (CLICK, PLAYBACK):
        return action, sig[1] or "(no url)"
    return action, str(sig[1])


def find_runs(records, min_run):
    """Return runs of consecutive identical events as a list of dicts.

    Each run: {"length", "sig", "start", "end"} where start/end are the entry
    numbers of the first and last event in the run. Only runs with
    ``length >= min_run`` are returned, sorted longest first.
    """
    ordered = sorted(records, key=lambda r: r.get("number", 0))
    runs = []
    i = 0
    n = len(ordered)
    while i < n:
        j = i + 1
        while j < n and signature(ordered[j]) == signature(ordered[i]):
            j += 1
        length = j - i
        if length >= min_run:
            runs.append({
                "length": length,
                "sig": signature(ordered[i]),
                "start": ordered[i].get("number", i + 1),
                "end": ordered[j - 1].get("number", j),
            })
        i = j
    runs.sort(key=lambda r: r["length"], reverse=True)
    return runs


def _truncate(text, width=70):
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(headers, rows, aligns=None):
    """Render a monospace text table.

    ``aligns`` is an optional list of "l"/"r" per column (default: left).
    """
    aligns = aligns or ["l"] * len(headers)
    cells = [[str(c) for c in row] for row in rows]
    widths = [max(len(headers[i]), *(len(r[i]) for r in cells)) if cells
              else len(headers[i]) for i in range(len(headers))]

    def render(row):
        out = []
        for i, cell in enumerate(row):
            out.append(cell.rjust(widths[i]) if aligns[i] == "r"
                       else cell.ljust(widths[i]))
        return "  ".join(out).rstrip()

    lines = [render(headers), "  ".join("-" * w for w in widths)]
    lines += [render(r) for r in cells]
    return "\n".join(lines)


def render_table_image(headers, rows, out_base, formats, dpi, title=None,
                       left_cols=(0,)):
    """Render a booktabs-style table image (matches render_table.py's look).

    ``left_cols`` are column indices whose body cells are left-aligned (the
    rest are centred). Column widths scale with the longest string per column
    so long targets/URLs get the room they need. Returns written paths.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [[str(c) for c in row] for row in rows]
    ncols = len(headers)
    nrows = len(rows)

    widths = [max([len(headers[i])] + [len(r[i]) for r in rows])
              for i in range(ncols)]
    total = sum(widths) or 1
    col_widths = [w / total for w in widths]

    fig_w = max(4.0, 0.105 * total + 0.6)
    fig_h = 0.34 * (nrows + 1.9) + (0.7 if title else 0.4)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    tbl = ax.table(cellText=rows, colLabels=headers, loc="center",
                   cellLoc="center", colWidths=col_widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.35)

    for (r, c), cell in tbl.get_celld().items():
        cell.PAD = 0.04
        cell.set_edgecolor("black")
        edges = ""
        if r == 0:  # column header
            cell.set_text_props(fontweight="bold",
                                ha="left" if c in left_cols else "center")
            cell.set_facecolor("#f0f0f0")
            cell.set_linewidth(1.0)
            edges = "TB"
        else:
            cell.set_linewidth(0.8)
            cell.set_text_props(ha="left" if c in left_cols else "center")
        if r == nrows:  # bottom rule under the whole table
            edges += "B"
        cell.visible_edges = edges

    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=12)

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
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories")
    ap.add_argument("--min-run", type=int, default=2,
                    help="smallest run length to report (default: 2)")
    ap.add_argument("--out-dir", default="output/repeat_runs",
                    help="folder for the table images "
                         "(default: output/repeat_runs)")
    ap.add_argument("--formats", nargs="+", default=["png"])
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.folder, "*.json")))
    if not paths:
        raise SystemExit(f"No JSON files found in {args.folder!r}")

    by_name = {}
    for path in paths:
        try:
            by_name[os.path.basename(path)] = load_records(path)
        except (ValueError, OSError) as exc:
            print(f"  ! skipping {os.path.basename(path)}: {exc}", file=sys.stderr)

    mapping = load_or_create_mapping(by_name.keys(), MAP_FILE)
    per_participant = sorted((mapping[name], recs) for name, recs in by_name.items())

    os.makedirs(args.out_dir, exist_ok=True)
    summary = []
    written = []
    no_runs = []
    for pid, records in per_participant:
        runs = find_runs(records, args.min_run)
        longest = runs[0]["length"] if runs else 1
        repeated_events = sum(r["length"] for r in runs)
        summary.append((pid, len(records), longest, repeated_events))

        if not runs:
            no_runs.append(pid)
            continue
        # One table image per participant listing their runs (longest first).
        rows = []
        for run in runs:
            action, label = describe(run["sig"])
            span = (str(run["start"]) if run["start"] == run["end"]
                    else f"{run['start']}–{run['end']}")
            rows.append([str(run["length"]), action, span, _truncate(label)])
        title = f"{pid} — {len(records)} entries · longest run {longest}×"
        written += render_table_image(
            ["run", "action", "entries", "target"], rows,
            os.path.join(args.out_dir, pid), args.formats, args.dpi,
            title=title, left_cols=(1, 3))

    # Summary table image, worst offenders first.
    summary_rows = [[pid, str(total), str(longest), str(repeated)]
                    for pid, total, longest, repeated in
                    sorted(summary, key=lambda s: s[2], reverse=True)]
    written += render_table_image(
        ["participant", "entries", "longest run", "in runs"], summary_rows,
        os.path.join(args.out_dir, "summary"), args.formats, args.dpi,
        title="Longest identical-action streak per participant",
        left_cols=(0,))

    print(f"Wrote {len(written)} files to {args.out_dir}/")
    if no_runs:
        print(f"No run of {args.min_run}+ (no per-participant table): "
              + ", ".join(no_runs))


if __name__ == "__main__":
    main()
