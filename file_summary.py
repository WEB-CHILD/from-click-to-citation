#!/usr/bin/env python3
"""Per-file overview of the navigation_histories JSON files.

For every *.json file in the target folder, prints how many entries the file
has and how those entries break down by action type. Ends with totals plus
per-category average and median values across the files.

Usage:
    python3 file_summary.py                       # defaults to navigation_histories/
    python3 file_summary.py path/to/folder
"""

import glob
import json
import os
import statistics
import sys
from collections import Counter


MAP_FILE = "participant_map.json"


def load_records(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("not a JSON array")
    return [r for r in data if isinstance(r, dict)]


def load_or_create_mapping(filenames, map_path):
    """Map each filename to a stable participant id (P01, P02, ...).

    Existing assignments in ``map_path`` are preserved; any new files are
    appended with the next free number. The (updated) mapping is saved back so
    the same file always maps to the same participant.
    """
    mapping = {}
    if os.path.exists(map_path):
        with open(map_path, encoding="utf-8") as fh:
            mapping = json.load(fh)

    used = set(mapping.values())
    next_num = 1
    for name in filenames:
        if name in mapping:
            continue
        while f"P{next_num:02d}" in used:
            next_num += 1
        label = f"P{next_num:02d}"
        mapping[name] = label
        used.add(label)

    with open(map_path, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return mapping


def fmt_ratio(numerator, clicks):
    """numerator-per-search-result-click, or 'n/a' when there are no clicks."""
    if clicks == 0:
        return "n/a"
    return f"{numerator / clicks:.2f}"


def gather_counts(folder="navigation_histories"):
    """Load every JSON file and return anonymised per-participant action counts.

    Returns ``(per_participant, action_types)`` where ``per_participant`` maps a
    participant id (P01, ...) to a Counter of action -> count, and
    ``action_types`` is the ordered list of action names seen.
    """
    paths = sorted(glob.glob(os.path.join(folder, "*.json")))
    if not paths:
        raise SystemExit(f"No JSON files found in {folder!r}")

    # Discover every action type so the table has consistent columns.
    per_file = {}
    action_types = []
    for path in paths:
        try:
            records = load_records(path)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            print(f"  ! skipping {os.path.basename(path)}: {exc}", file=sys.stderr)
            continue
        counts = Counter(r.get("action", "(none)") for r in records)
        per_file[os.path.basename(path)] = counts
        for action in counts:
            if action not in action_types:
                action_types.append(action)

    # Anonymise: map each filename to a stable participant id (P01, P02, ...).
    mapping = load_or_create_mapping(per_file.keys(), MAP_FILE)
    per_file = {mapping[name]: counts for name, counts in per_file.items()}

    preferred = ["query", "search result clicked", "playback link clicked"]
    action_types.sort(
        key=lambda a: (preferred.index(a) if a in preferred else len(preferred), a)
    )
    return per_file, action_types


def compute_table(folder="navigation_histories"):
    """Build the anonymised summary table.

    Returns a dict with:
      headers     -> list of column titles
      rows        -> list of per-participant rows (list of strings)
      summary     -> list of (TOTAL/AVERAGE/...) rows (list of strings)
    so the same numbers can be printed as text or rendered as an image.
    """
    per_file, action_types = gather_counts(folder)
    ratio_labels = ["query/click", "playback/click"]
    headers = ["participant", "total"] + action_types + ratio_labels

    totals = Counter()
    grand_total = 0
    series = {"total": []}
    series.update({a: [] for a in action_types})
    ratio_series = {label: [] for label in ratio_labels}

    rows = []
    for name, counts in per_file.items():
        total = sum(counts.values())
        grand_total += total
        totals.update(counts)
        series["total"].append(total)
        for a in action_types:
            series[a].append(counts.get(a, 0))
        queries = counts.get("query", 0)
        playbacks = counts.get("playback link clicked", 0)
        clicks = counts.get("search result clicked", 0)
        if clicks:
            ratio_series["query/click"].append(queries / clicks)
            ratio_series["playback/click"].append(playbacks / clicks)
        row = [name, str(total)]
        row += [str(counts.get(a, 0)) for a in action_types]
        row += [fmt_ratio(queries, clicks), fmt_ratio(playbacks, clicks)]
        rows.append(row)

    def summary_row(label, fn, ratio_fn):
        out = [label, fn(series["total"])]
        out += [fn(series[a]) for a in action_types]
        for rlabel in ratio_labels:
            vals = ratio_series[rlabel]
            out.append(ratio_fn(vals) if vals else "n/a")
        return out

    total_q = totals.get("query", 0)
    total_pb = totals.get("playback link clicked", 0)
    total_clicks = totals.get("search result clicked", 0)
    total_out = ["TOTAL", str(grand_total)]
    total_out += [str(totals.get(a, 0)) for a in action_types]
    total_out += [fmt_ratio(total_q, total_clicks),
                  fmt_ratio(total_pb, total_clicks)]

    summary = [
        total_out,
        summary_row("AVERAGE", lambda v: f"{statistics.mean(v):.1f}",
                    lambda r: f"{statistics.mean(r):.2f}"),
        summary_row("MEDIAN", lambda v: f"{statistics.median(v):.1f}",
                    lambda r: f"{statistics.median(r):.2f}"),
        summary_row("MAX", lambda v: str(max(v)), lambda r: f"{max(r):.2f}"),
        summary_row("MIN", lambda v: str(min(v)), lambda r: f"{min(r):.2f}"),
    ]

    return {"headers": headers, "rows": rows, "summary": summary,
            "n_files": len(per_file), "grand_total": grand_total}


def print_table(table):
    headers = table["headers"]
    all_rows = [headers] + table["rows"] + table["summary"]
    widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

    def render(cells):
        out = cells[0].ljust(widths[0])
        for i in range(1, len(cells)):
            out += "  " + cells[i].rjust(widths[i])
        return out

    line = "-" * len(render(headers))
    print(render(headers))
    print(line)
    for row in table["rows"]:
        print(render(row))
    print(line)
    for row in table["summary"]:
        print(render(row))
    print(f"\n{table['n_files']} files, {table['grand_total']} entries total.")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "navigation_histories"
    print_table(compute_table(folder))


if __name__ == "__main__":
    main()
