#!/usr/bin/env python3
"""Grouped summary table with long repeat-runs removed ("cleaned").

This is the same two-group table as grouped_table.py, but before the actions
are counted, any run of the *exact same action* repeated more than --max-run
times in a row is dropped entirely. Some histories contain long stretches of
one identical event -- the same playback link (same url *and* harvest date) or
the same query fired again and again, e.g. one participant clicks the same page
359 times in a row -- which swamps the totals. Removing those runs shows the
deliberate browsing underneath the noise.

"Exact same action" matches repeat_runs.py: same url *and* harvest date for a
click, or the query string plus its filters for a query. Participants are then
re-classified (query- vs click-based) from the cleaned counts, so a history that
was only "click-based" because of a stuck playback loop can move groups.

Output: output/grouped_table_cleaned.png  (needs matplotlib)

Usage:
    python3 grouped_table_cleaned.py
    python3 grouped_table_cleaned.py path/to/folder
    python3 grouped_table_cleaned.py --max-run 5      # drop runs longer than 5
    python3 grouped_table_cleaned.py --no-image       # text only
"""

import argparse
import glob
import os
import sys
from collections import Counter

from file_summary import MAP_FILE, load_records, load_or_create_mapping
from repeat_runs import signature
from grouped_table import classify, print_table, render_image


def clean_records(records, max_run):
    """Drop every run of the exact same action longer than ``max_run``.

    Walks the entries in chronological order; a maximal block of consecutive
    identical events (by repeat_runs.signature) longer than ``max_run`` is
    removed in full. Returns ``(kept_records, removed_count)``.
    """
    ordered = sorted(records, key=lambda r: r.get("number", 0))
    kept = []
    removed = 0
    i = 0
    n = len(ordered)
    while i < n:
        j = i + 1
        while j < n and signature(ordered[j]) == signature(ordered[i]):
            j += 1
        run_len = j - i
        if run_len > max_run:
            removed += run_len
        else:
            kept.extend(ordered[i:j])
        i = j
    return kept, removed


def cleaned_counts(folder, max_run):
    """Return ``(per_file, removals)`` with over-long repeat runs removed.

    ``per_file`` maps participant id -> Counter(action -> count) after cleaning
    (the shape grouped_table's helpers expect); ``removals`` maps participant id
    -> number of entries dropped.
    """
    paths = sorted(glob.glob(os.path.join(folder, "*.json")))
    if not paths:
        raise SystemExit(f"No JSON files found in {folder!r}")

    by_name = {}
    for path in paths:
        try:
            by_name[os.path.basename(path)] = load_records(path)
        except (ValueError, OSError) as exc:
            print(f"  ! skipping {os.path.basename(path)}: {exc}", file=sys.stderr)

    mapping = load_or_create_mapping(by_name.keys(), MAP_FILE)
    per_file = {}
    removals = {}
    for name, records in by_name.items():
        kept, removed = clean_records(records, max_run)
        pid = mapping[name]
        per_file[pid] = Counter(r.get("action", "(none)") for r in kept)
        removals[pid] = removed
    return per_file, removals


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories")
    ap.add_argument("--max-run", type=int, default=10,
                    help="drop runs of the same action longer than this "
                         "(default: 10)")
    ap.add_argument("--out", default="output/grouped_table_cleaned",
                    help="image basename (default: output/grouped_table_cleaned)")
    ap.add_argument("--formats", nargs="+", default=["png"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--no-image", action="store_true",
                    help="print the text table only, skip the image")
    args = ap.parse_args()

    per_file, removals = cleaned_counts(args.folder, args.max_run)
    groups = classify(per_file)
    print_table(groups, per_file)

    dropped = {p: n for p, n in removals.items() if n}
    total = sum(dropped.values())
    print(f"\nRemoved {total} entries in runs longer than {args.max_run}"
          + (f" — {', '.join(f'{p}:-{n}' for p, n in sorted(dropped.items()))}"
             if dropped else " (none found)"))

    if not args.no_image:
        title = (f"Grouped summary — runs of >{args.max_run} identical "
                 "actions removed")
        written = render_image(groups, per_file, args.out, args.formats,
                               args.dpi, title=title)
        if written:
            print("Wrote: " + ", ".join(written))


if __name__ == "__main__":
    main()
