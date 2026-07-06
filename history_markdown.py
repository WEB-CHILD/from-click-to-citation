#!/usr/bin/env python3
"""Render each participant's navigation history as a Markdown document.

For every ``*.json`` file in the target folder this writes one Markdown file
that lists the participant's entries in chronological order: each ``query``,
``search result clicked`` and ``playback link clicked`` event with its details
(the query string and any filters, or the clicked url plus its archived copy
and capture date).

Files are anonymised through participant_map.json (the same P01, P02, ... ids
used by the other scripts) and written as ``output/markdown/{pid}.md``.

Usage:
    python3 history_markdown.py                       # all files
    python3 history_markdown.py path/to/folder
    python3 history_markdown.py --only P01 P05        # just these participants
    python3 history_markdown.py --out-dir figures/md
"""

import argparse
import glob
import os
import sys
from collections import Counter

from file_summary import MAP_FILE, load_records, load_or_create_mapping

QUERY = "query"
CLICK = "search result clicked"
PLAYBACK = "playback link clicked"

# Column widths are irrelevant in Markdown, so a table keeps things compact.
HEADERS = ["#", "action", "details"]


def _cell(text):
    """Make a string safe to drop inside a Markdown table cell."""
    return str(text).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _details(record):
    """Human-readable detail string for one history record."""
    action = record.get("action")
    if action == QUERY:
        query = record.get("query", "")
        detail = f"`{query}`" if query != "" else "*(empty query)*"
        filters = record.get("filterQueries") or []
        if filters:
            detail += " — filters: " + ", ".join(f"`{f}`" for f in filters)
        return detail

    if action in (CLICK, PLAYBACK):
        url = record.get("url", "")
        parts = [f"[{url}]({url})"] if url else ["*(no url)*"]
        archived = record.get("archivedUrl")
        if archived:
            parts.append(f"[archived]({archived})")
        date = record.get("date")
        if date:
            parts.append(f"captured {date}")
        return " · ".join(parts)

    # Unknown action type: dump remaining fields so nothing is silently lost.
    extra = {k: v for k, v in record.items() if k not in ("action", "number")}
    return _cell(extra) if extra else ""


def render_markdown(pid, records):
    """Return the Markdown document (as a string) for one participant."""
    ordered = sorted(records, key=lambda r: r.get("number", 0))
    counts = Counter(r.get("action", "(none)") for r in ordered)

    lines = [f"# {pid} — navigation history", ""]
    breakdown = " · ".join(f"{counts[a]} {a}"
                           for a in sorted(counts, key=lambda a: -counts[a]))
    lines.append(f"**{len(ordered)} entries** — {breakdown}")
    lines.append("")
    lines.append("| " + " | ".join(HEADERS) + " |")
    lines.append("| " + " | ".join("---" for _ in HEADERS) + " |")
    for record in ordered:
        number = record.get("number", "")
        action = record.get("action", "(none)")
        lines.append(f"| {_cell(number)} | {_cell(action)} | {_details(record)} |")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="navigation_histories")
    ap.add_argument("--out-dir", default="output/markdown",
                    help="folder for the .md files (default: output/markdown)")
    ap.add_argument("--only", nargs="+", metavar="PID",
                    help="only render these participant ids (e.g. P01 P05)")
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
    wanted = set(args.only) if args.only else None

    os.makedirs(args.out_dir, exist_ok=True)
    written = []
    for name, records in by_name.items():
        pid = mapping[name]
        if wanted is not None and pid not in wanted:
            continue
        out_path = os.path.join(args.out_dir, f"{pid}.md")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(pid, records))
        written.append(out_path)

    if not written:
        raise SystemExit("No participants matched.")
    print(f"Wrote {len(written)} Markdown files to {args.out_dir}/")


if __name__ == "__main__":
    main()
