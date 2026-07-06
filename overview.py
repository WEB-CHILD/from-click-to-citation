#!/usr/bin/env python3
"""Overview tool for navigation-history JSON files.

Each file is a JSON array of event records produced while browsing a web
archive (SolrWayback). Records share a ``number`` and ``action`` and, depending
on the action, carry extra fields:

    query                  -> query [, facets, filterQueries]
    search result clicked  -> date, url, archivedUrl
    playback link clicked  -> date, url, archivedUrl

Usage:
    python3 overview.py navigation_histories/markus_nissen.json
    python3 overview.py navigation_histories/            # all *.json in a dir
    python3 overview.py navigation_histories/*.json      # shell glob
    python3 overview.py navigation_histories/ --top 20   # show more queries/domains
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse


def load_records(path):
    """Return the list of records in a file, or raise with a clear message."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("expected a top-level JSON array")
    return [r for r in data if isinstance(r, dict)]


def parse_date(value):
    """Parse an ISO-8601 'Z' timestamp; return None if unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def domain_of(url):
    try:
        host = urlparse(url).netloc
        return host.split(":")[0] or url
    except (ValueError, AttributeError):
        return url


def summarize(path, top):
    try:
        records = load_records(path)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"  ! could not read {path}: {exc}\n")
        return None

    actions = Counter(r.get("action") for r in records)
    queries = [r.get("query") for r in records if r.get("action") == "query"]
    faceted = sum(1 for r in records if r.get("filterQueries"))

    dates = [d for d in (parse_date(r.get("date")) for r in records) if d]
    domains = Counter(domain_of(r["url"]) for r in records if r.get("url"))

    print(f"=== {os.path.basename(path)} ===")
    print(f"  records         : {len(records)}")
    for action, count in actions.most_common():
        print(f"    - {action:<22}: {count}")

    if dates:
        span = f"{min(dates).date()}  ->  {max(dates).date()}"
        print(f"  archived date range : {span}")

    print(f"  unique queries  : {len(set(q for q in queries if q))}"
          f"  (total {len(queries)}, {faceted} with filters)")
    if queries:
        print(f"  top queries (of {len(queries)}):")
        for q, c in Counter(q for q in queries if q).most_common(top):
            print(f"    {c:>3}x  {q}")

    if domains:
        print(f"  top domains ({len(domains)} unique):")
        for dom, c in domains.most_common(top):
            print(f"    {c:>3}x  {dom}")
    print()

    return {
        "records": len(records),
        "queries": len(queries),
        "actions": actions,
        "dates": dates,
    }


def collect_paths(args):
    paths = []
    for arg in args:
        if os.path.isdir(arg):
            paths.extend(sorted(glob.glob(os.path.join(arg, "*.json"))))
        else:
            paths.append(arg)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+",
                    help="JSON file(s) or a directory of JSON files")
    ap.add_argument("--top", type=int, default=10,
                    help="how many top queries/domains to show (default 10)")
    args = ap.parse_args()

    paths = collect_paths(args.paths)
    if not paths:
        print("No JSON files found.", file=sys.stderr)
        sys.exit(1)

    totals = Counter()
    all_dates = []
    parsed = 0
    for path in paths:
        result = summarize(path, args.top)
        if result:
            parsed += 1
            totals["records"] += result["records"]
            totals["queries"] += result["queries"]
            totals.update(result["actions"])
            all_dates.extend(result["dates"])

    if parsed > 1:
        print("=== TOTAL across", parsed, "files ===")
        print(f"  records : {totals.pop('records', 0)}")
        totals.pop("queries", None)
        for action, count in totals.most_common():
            print(f"    - {action:<22}: {count}")
        if all_dates:
            print(f"  overall date range : {min(all_dates).date()}"
                  f"  ->  {max(all_dates).date()}")


if __name__ == "__main__":
    main()
