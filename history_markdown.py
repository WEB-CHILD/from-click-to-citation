#!/usr/bin/env python3
"""Render each participant's navigation history as a Markdown document.

For every ``*.json`` file in the target folder this writes one Markdown file
that lists the participant's entries in chronological order: the time of day,
action, browser tab and the entry it came from (``from``), with its details
(the query string and any filters, or the url plus its archived copy and
capture date).

Files keep the participant ids of the anonymised data (P01, P02, ...) and are
written as ``output/markdown/{pid}.md``.

Usage:
    python3 history_markdown.py                       # all files
    python3 history_markdown.py path/to/folder
    python3 history_markdown.py --only P01 P05        # just these participants
    python3 history_markdown.py --out-dir figures/md
"""

import argparse
import os
from collections import Counter

from file_summary import DEFAULT_FOLDER, QUERY, load_histories

# Column widths are irrelevant in Markdown, so a table keeps things compact.
HEADERS = ["#", "time", "action", "tab", "from", "details"]
# Shown in their own columns, so not repeated in the details of unknown actions.
COLUMN_FIELDS = ("number", "timestamp", "action", "tab", "from")


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

    if "url" in record:
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
    extra = {k: v for k, v in record.items() if k not in COLUMN_FIELDS}
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
        cells = [record.get("number", ""), record.get("timestamp") or "–",
                 record.get("action", "(none)"), record.get("tab", ""),
                 record.get("from", "")]
        lines.append("| " + " | ".join(_cell(c) for c in cells)
                     + f" | {_details(record)} |")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    ap.add_argument("--out-dir", default="output/markdown",
                    help="folder for the .md files (default: output/markdown)")
    ap.add_argument("--only", nargs="+", metavar="PID",
                    help="only render these participant ids (e.g. P01 P05)")
    args = ap.parse_args()

    wanted = set(args.only) if args.only else None

    os.makedirs(args.out_dir, exist_ok=True)
    written = []
    for pid, records in load_histories(args.folder).items():
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
