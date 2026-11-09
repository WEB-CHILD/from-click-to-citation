#!/usr/bin/env python3
"""Trace how each participant moves through *time* while playing back archives.

Every ``SEARCH_RESULT_CLICKED`` entry opens a new browser tab on a capture with
a harvest date. Everything that happens in that tab afterwards -- links
followed, toolbar clicks to other captures, back/forward, reloads, failed
playbacks -- stays in it (the ``tab`` field). This script cuts each history
into **chains**, one per result tab:

    SEARCH_RESULT_CLICKED  ->  PLAYBACK_LINK_CLICKED  ->  PLAYBACK_LINK_CLICKED ...

A query does not end a chain: the participant can go back to the search tab
and later return to a result tab, and the tab field says where each entry
belongs.

Only ``PLAYBACK_LINK_CLICKED`` entries are counted as navigational **steps**.
The *step delta* of a link is the signed difference between its capture date
and the capture date of the page it was clicked on (its ``from`` entry).
Negative means the participant moved **backward** in time, positive
**forward**. A link that leads back to the URL it was on (``Same page``) is
still counted: the participant clicked it, and the archive served whichever
capture was nearest.

``TOOLBAR_LINK_CLICKED`` entries (First/Previous/Next/Last capture) also change
the capture date, but by choice of date rather than by following a link, so
they are listed and counted separately and left out of the step statistics.
Failed playbacks reach no capture and are only counted. Back/forward, reloads,
automatic and typed navigation are shown in the detail but not measured.

Per chain we also report the *end offset* (the capture date of the last page
shown in the tab minus the anchor's) and the *span* (the summed absolute size
of its steps).

Outputs a plain-text report (stdout or --out-file) and, with --markdown, a
Markdown version. ``--png`` additionally renders the per-participant summary
table -- the same table the reports open with -- as a publication-quality
image (needs matplotlib; everything else is standard library). Participants
keep the P01, P02, ... ids of the anonymised files, and archived URLs are
replaced by per-participant ``site N / page M`` labels.

Usage:
    python3 time_travel.py                       # summary table for everyone
    python3 time_travel.py path/to/folder
    python3 time_travel.py --detail              # every chain, step by step
    python3 time_travel.py --detail --only P03   # just one participant
    python3 time_travel.py --min-steps 2         # skip one-hop chains in detail
    python3 time_travel.py --markdown --out-file output/time_travel.md
    python3 time_travel.py --png                  # -> output/time_travel_overview.png
    python3 time_travel.py --png figures/tt.png   # custom path
"""

import argparse
import os
import re
import statistics
import sys
from datetime import datetime
from urllib.parse import urlsplit

from file_summary import (DEFAULT_FOLDER, RESULT, LINK, TOOLBAR, FAILED,
                          load_histories)

DAY = 86400.0

DEFAULT_PNG = os.path.join("output", "time_travel_overview.png")


def parse_date(text):
    """Parse an ISO-8601 capture date (``2012-10-16T06:11:28Z``) to datetime."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def humanise(seconds):
    """Signed, human-readable duration: ``-1y 88d``, ``+3h 12m``, ``0``."""
    if seconds is None:
        return "n/a"
    sign = "-" if seconds < 0 else ("+" if seconds > 0 else "")
    s = abs(seconds)
    if s == 0:
        return "0"
    days, rem = divmod(int(s), 86400)
    years, days = divmod(days, 365)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if years:
        parts.append(f"{years}y")
    if days:
        parts.append(f"{days}d")
    if not years:                      # only show sub-day detail for short hops
        if hours and len(parts) < 2:
            parts.append(f"{hours}h")
        if minutes and len(parts) < 2:
            parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{int(s)}s")
    return sign + " ".join(parts[:2])


def page_key(url):
    """Identity of the *page* an archived URL points at, ignoring the capture.

    ``www``/``wwwN`` prefixes and explicit ports are stripped and a trailing
    slash is ignored, so ``http://www4.example.com:80/a/`` and
    ``http://example.com/a`` are recognised as the same page, as the archive
    itself treats them. Returns ``None`` for a missing url, which never
    compares equal to anything at the call sites below.
    """
    if not url:
        return None
    parts = urlsplit(url)
    host = re.sub(r"^www\d*\.", "", parts.netloc.lower().split(":")[0])
    return (host, parts.path.rstrip("/"), parts.query)


class SiteAnonymiser:
    """Turn archived URLs into labels like ``site 1 · page 3``.

    The labels are shorter than the pseudonymised URLs and still tell you a
    participant reached the *same* page again rather than a different one,
    which is most of what the step deltas mean.

    Numbering restarts for every participant, so ``site 1`` in one history has
    no relation to ``site 1`` in another and the labels cannot be used to link
    participants to each other.
    """

    def __init__(self):
        self._hosts = {}
        self._pages = {}

    def label(self, url):
        if not url:
            return "(no url)"
        key = page_key(url)
        host = key[0]
        if host not in self._hosts:
            self._hosts[host] = len(self._hosts) + 1
        if key not in self._pages:
            self._pages[key] = sum(1 for k in self._pages if k[0] == host) + 1
        return f"site {self._hosts[host]} · page {self._pages[key]}"


def build_chains(records):
    """Cut a participant's history into one chain per search-result tab.

    Returns a list of dicts with keys ``anchor`` (the search-result-click
    record), ``entries`` (every later record in that tab, in order) and
    ``start`` (the anchor's entry number). An entry without a ``tab`` belongs
    to the tab of the entry it came from.
    """
    by_number = {r.get("number"): r for r in records}
    chains = {}
    tab_of = {}
    for record in records:
        tab = record.get("tab")
        if tab is None and record.get("from") in tab_of:
            tab = tab_of[record["from"]]
        tab_of[record.get("number")] = tab
        if record.get("action") == RESULT:
            chains[tab] = {"anchor": record, "entries": [],
                           "start": record.get("number"), "by_number": by_number}
        elif tab in chains:
            chains[tab]["entries"].append(record)
    return sorted(chains.values(), key=lambda c: c["start"])


def analyse_chain(chain):
    """Add step deltas, end offset and span to a chain, in seconds.

    Every entry in the tab gets a row; only link clicks get a counted delta,
    measured from the capture date of the page the link was on.
    """
    anchor = chain["anchor"]
    anchor_date = parse_date(anchor.get("date"))
    rows = []
    last_date = anchor_date
    for record in chain["entries"]:
        action = record.get("action")
        date = parse_date(record.get("date"))
        source = chain["by_number"].get(record.get("from"))
        delta = None
        if action in (LINK, TOOLBAR) and source is not None:
            source_date = parse_date(source.get("date"))
            if date is not None and source_date is not None:
                delta = (date - source_date).total_seconds()
        rows.append({
            "record": record, "date": date, "delta": delta,
            "counted": action == LINK and delta is not None,
            "same_page": (action == LINK and source is not None
                          and page_key(record.get("url"))
                          == page_key(source.get("url"))),
        })
        if action != FAILED and date is not None:
            last_date = date

    measured = [r["delta"] for r in rows if r["counted"]]
    actions = [r["record"].get("action") for r in rows]
    chain["anchor_date"] = anchor_date
    chain["rows"] = rows
    chain["counted"] = len(measured)
    chain["same_page"] = sum(1 for r in rows if r["counted"] and r["same_page"])
    chain["toolbar"] = actions.count(TOOLBAR)
    chain["failed"] = actions.count(FAILED)
    chain["end"] = ((last_date - anchor_date).total_seconds()
                    if measured and anchor_date and last_date else None)
    chain["span"] = sum(abs(d) for d in measured) if measured else None
    return chain


def summarise(chains):
    """Aggregate one participant's chains into a stats dict."""
    values = [r["delta"] for chain in chains for r in chain["rows"]
              if r["counted"]]
    magnitudes = [abs(v) for v in values if v != 0]
    ends = [c["end"] for c in chains if c["end"] is not None]

    return {
        "chains": len(chains),
        "with_steps": sum(1 for c in chains if c["counted"]),
        "steps": len(values),
        "same_page": sum(c["same_page"] for c in chains),
        "toolbar": sum(c["toolbar"] for c in chains),
        "failed": sum(c["failed"] for c in chains),
        "backward": sum(1 for v in values if v < 0),
        "forward": sum(1 for v in values if v > 0),
        "same": sum(1 for v in values if v == 0),
        "median_jump": statistics.median(magnitudes) if magnitudes else None,
        "max_jump": max(magnitudes) if magnitudes else None,
        "longest_chain": max((c["counted"] for c in chains), default=0),
        "median_end": statistics.median(ends) if ends else None,
    }


def render_table(headers, rows, aligns=None):
    """Render a monospace text table with journal-style horizontal rules."""
    aligns = aligns or ["l"] * len(headers)
    cells = [[str(c) for c in row] for row in rows]
    widths = [max([len(headers[i])] + [len(r[i]) for r in cells])
              for i in range(len(headers))]

    def line(row):
        out = []
        for i, cell in enumerate(row):
            out.append(cell.rjust(widths[i]) if aligns[i] == "r"
                       else cell.ljust(widths[i]))
        return "  ".join(out).rstrip()

    rule = "-" * len(line(headers))
    return "\n".join([rule, line(headers), rule]
                     + [line(r) for r in cells] + [rule])


def summary_table(results):
    """The per-participant summary as ``(headers, rows, aligns)``.

    Single source of truth for the text, Markdown and PNG renderings, so the
    figure can never drift from the table in the reports.

    The ``Same`` column (link steps that did not move in time at all) is
    dropped when it is empty for everyone.
    """
    headers = ["Participant", "Chains", "w/steps", "Longest", "Steps",
               "Same page", "Back", "Fwd", "Same", "Toolbar", "Failed",
               "Median jump", "Max jump", "Median end"]
    rows = []
    for label, stats in results:
        rows.append([
            label, stats["chains"], stats["with_steps"], stats["longest_chain"],
            stats["steps"], stats["same_page"],
            stats["backward"], stats["forward"], stats["same"],
            stats["toolbar"], stats["failed"],
            humanise(stats["median_jump"]).lstrip("+"),
            humanise(stats["max_jump"]).lstrip("+"),
            humanise(stats["median_end"]),
        ])

    same_col = headers.index("Same")
    if not any(row[same_col] for row in rows):
        headers.pop(same_col)
        for row in rows:
            row.pop(same_col)

    aligns = ["l"] + ["r"] * (len(headers) - 1)
    return headers, rows, aligns


# Two-line titles read better in a figure than the compact text-table ones.
PNG_HEADERS = {
    "w/steps": "With\nsteps",
    "Longest": "Longest\nchain",
    "Same page": "Same\npage",
    "Median jump": "Median\njump",
    "Max jump": "Max\njump",
    "Median end": "Median end\noffset",
}


def render_png(results, path, dpi=300):
    """Draw the summary table as a publication-quality image.

    Journal/booktabs styling to match the project's other figures: horizontal
    rules only, bold header, numbers centred and the participant column left
    aligned. matplotlib is imported here rather than at module scope so the
    text reports keep working without it installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")            # no display needed; just write a file
        import matplotlib.pyplot as plt
    except ImportError:                  # pragma: no cover - depends on env
        raise SystemExit(
            "--png needs matplotlib: pip install matplotlib")

    headers, rows, aligns = summary_table(results)
    titles = [PNG_HEADERS.get(x, x) for x in headers]
    body = [[str(c) for c in r] for r in rows]

    # Column widths follow the widest cell so narrow numeric columns stay
    # narrow instead of every column sharing the table width equally.
    widths = []
    for i, title in enumerate(titles):
        longest_title = max(len(part) for part in title.split("\n"))
        widest = max([longest_title] + [len(r[i]) for r in body])
        widths.append(widest + 2)
    total = float(sum(widths))
    widths = [w / total for w in widths]

    fig_w = 0.105 * total + 0.6
    fig_h = 0.30 * (len(body) + 2.6)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    tbl = ax.table(cellText=body, colLabels=titles, colWidths=widths,
                   loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.32)

    nrows = len(body)
    for (r, c), cell in tbl.get_celld().items():
        cell.PAD = 0.04
        cell.set_edgecolor("black")
        edges = ""                       # booktabs: only the rules added here
        if r == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f0f0f0")
            cell.set_linewidth(1.0)
            cell.set_height(cell.get_height() * 1.85)
            edges = "TB"
        else:
            cell.set_text_props(
                ha="left" if aligns[c] == "l" else "center")
            cell.set_linewidth(0.8)
        if r == nrows:
            edges += "B"                 # closing rule under the last row
        cell.visible_edges = edges

    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight",
                facecolor="white", pad_inches=0.05)
    plt.close(fig)
    return path


def format_summary(results, markdown=False):
    headers, rows, aligns = summary_table(results)
    if markdown:
        out = ["| " + " | ".join(headers) + " |",
               "|" + "|".join("---" if a == "l" else "---:" for a in aligns) + "|"]
        out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        return "\n".join(out)
    return render_table(headers, rows, aligns)


def step_text(row):
    """The delta cell of a detail row: a jump, or what kind of entry it was."""
    action = row["record"].get("action")
    if row["counted"]:
        return humanise(row["delta"])
    if action == TOOLBAR:
        return f"(toolbar {humanise(row['delta'])})"
    if action == FAILED:
        return "(failed)"
    return "–"


def format_detail(label, chains, min_steps, markdown=False):
    """Per-chain, step-by-step breakdown for one participant.

    URLs are replaced by per-participant ``site N · page M`` labels; see
    :class:`SiteAnonymiser`.
    """
    sites = SiteAnonymiser()
    shown = [c for c in chains if c["counted"] >= min_steps]
    lines = []
    heading = (f"{label} — {len(shown)} chain(s) with >= {min_steps} "
               f"link step(s)")
    lines.append(f"### {heading}" if markdown else heading)
    lines.append("")
    if not shown:
        lines.append("(none)")
        lines.append("")
        return "\n".join(lines)

    for index, chain in enumerate(shown, 1):
        anchor = chain["anchor"]
        lines.append(
            f"Chain {index} (entry #{chain['start']}, tab {anchor.get('tab')}) — "
            f"anchor capture {anchor.get('date')}  ·  "
            f"{sites.label(anchor.get('url'))}")
        headers = ["#", "Action", "From", "Capture date", "Step delta",
                   "From anchor", "Page"]
        rows = []
        for row in chain["rows"]:
            record = row["record"]
            # A failed playback's date is that of the page the link was on;
            # it reached no capture, so it has no offset of its own.
            from_anchor = "–"
            if (record.get("action") != FAILED and row["date"] is not None
                    and chain["anchor_date"] is not None):
                from_anchor = humanise(
                    (row["date"] - chain["anchor_date"]).total_seconds())
            rows.append([
                record.get("number"),
                record.get("action"),
                record.get("from", ""),
                record.get("date"),
                step_text(row),
                from_anchor,
                sites.label(record.get("url")),
            ])
        aligns = ["r", "l", "r", "l", "r", "r", "l"]
        if markdown:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---:" if a == "r" else "---"
                                        for a in aligns) + "|")
            lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        else:
            lines.append(render_table(headers, rows, aligns))
        summary = (f"{chain['counted']} link step(s)  ·  "
                   f"end offset {humanise(chain['end'])}  ·  "
                   f"total travelled {humanise(chain['span']).lstrip('+')}")
        if chain["toolbar"]:
            summary += f"  ·  {chain['toolbar']} toolbar click(s)"
        if chain["failed"]:
            summary += f"  ·  {chain['failed']} failed"
        lines.append(summary)
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", default=DEFAULT_FOLDER,
                        help="folder of *.json histories (default: %(default)s)")
    parser.add_argument("--detail", action="store_true",
                        help="print every chain step by step, not just the summary")
    parser.add_argument("--only", metavar="ID", action="append",
                        help="restrict to these participant ids (repeatable)")
    parser.add_argument("--min-steps", type=int, default=1, metavar="N",
                        help="in --detail, skip chains with fewer than N link "
                             "steps (default: %(default)s)")
    parser.add_argument("--markdown", action="store_true",
                        help="emit Markdown tables instead of plain text")
    parser.add_argument("--out-file", metavar="PATH",
                        help="write the report here instead of stdout")
    parser.add_argument("--png", nargs="?", metavar="PATH",
                        const=DEFAULT_PNG, default=None,
                        help="also render the summary table as an image "
                             f"(default: {DEFAULT_PNG}); needs matplotlib")
    parser.add_argument("--dpi", type=int, default=300, metavar="N",
                        help="raster resolution for --png (default: %(default)s)")
    args = parser.parse_args(argv)

    results = []
    details = []
    for label, records in load_histories(args.folder).items():
        if args.only and label not in args.only:
            continue
        chains = [analyse_chain(c) for c in build_chains(records)]
        results.append((label, summarise(chains)))
        details.append((label, chains))

    if not results:
        parser.error("no participants matched")

    blocks = []
    title = "Movement through time in archive playback"
    blocks.append(f"# {title}" if args.markdown else title + "\n" + "=" * len(title))
    blocks.append("")
    blocks.append(format_summary(results, args.markdown))
    blocks.append("")
    if args.detail:
        blocks.append("## Per-chain detail" if args.markdown else
                      "Per-chain detail\n" + "-" * len("Per-chain detail"))
        blocks.append("")
        for label, chains in details:
            blocks.append(format_detail(label, chains, args.min_steps, args.markdown))

    if args.png:
        print(f"wrote {render_png(results, args.png, args.dpi)}")

    text = "\n".join(blocks)
    if args.out_file:
        os.makedirs(os.path.dirname(args.out_file) or ".", exist_ok=True)
        with open(args.out_file, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out_file}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
