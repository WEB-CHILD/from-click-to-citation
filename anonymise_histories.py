#!/usr/bin/env python3
"""Anonymise the corrected navigation histories into anonymised/.

Reads navigation_histories_corrected/ (the PR #11 format made by
correct_histories.py) and writes one ``Pnn.json`` per participant to
anonymised/, with the same pseudonyms as the first anonymised release:

- host names become ``site-NN.example``; ``www``/``wwwN`` prefixes are kept and
  other subdomains become ``subN.``
- URL path segments become ``seg-x`` (web file extensions are kept), query
  parameters ``pN=vN`` and fragments ``#frag-x``
- the archive host becomes ``archive.example``
- ``timestamp`` keeps only the time of day (UTC), not the session date
- search terms and domains in queries and filters use the same pseudonyms

The pseudonyms are kept in anonymisation_key.json (gitignored: it maps the
pseudonyms back to the real values). On the first run the key is learned by
lining up navigation_histories/ with the first release in anonymised/, which
had the same entries in the same order. Values the key has never seen (the
URLs of the added PLAYBACK_FAILED entries) get the next free pseudonym, and
the key is saved again, so later runs give the same output.

Queries, facets and filters must already be in the key: the corrections add no
new searches, so an unknown one stops the run instead of being guessed.

Usage:
    python3 anonymise_histories.py
"""

import json
import os
import re
import sys
from urllib.parse import urlsplit

from file_summary import MAP_FILE, load_records


SOURCE_DIR = "navigation_histories_corrected"
TARGET_DIR = "anonymised"
ORIGINAL_DIR = "navigation_histories"
KEY_FILE = "anonymisation_key.json"

ARCHIVE_PREFIX = "https://archive.example/solrwayback/services/web/"
WEB_RE = re.compile(r"^https?://[^/]+/solrwayback/services/web/(\d{14})/(.*)$", re.S)
WWW_RE = re.compile(r"^www\d*$")
# Second-level labels under a country TLD that belong to the public suffix,
# as in example.co.uk or example.com.ar
SECOND_LEVEL = {"co", "com", "org", "net", "or", "ac", "gov", "edu", "ne", "go"}
# Extensions kept on pseudonymised path segments
WEB_EXT = {"asp", "aspx", "cfm", "cgi", "htm", "html", "jsp", "pdf", "php", "php3", "pl", "shtml", "mp3"}

TEXT_FIELDS = ("query", "facets")


def letters(n):
    """1 -> a, 26 -> z, 27 -> aa: the suffixes of seg-x and frag-x."""
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(97 + r) + out
    return out


def letters_value(code):
    n = 0
    for c in code:
        n = n * 26 + ord(c) - 96
    return n


def registered_domain(host):
    if re.fullmatch(r"[\d.]+", host):
        return host
    labels = host.split(".")
    if (len(labels) > 2 and len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL
            and not WWW_RE.match(labels[-3])):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def split_segment(segment):
    base, dot, ext = segment.rpartition(".")
    if dot and base and ext.lower() in WEB_EXT:
        return base, "." + ext
    return segment, ""


class Key:
    """Real value -> pseudonym, per kind, with the next free pseudonym on demand."""

    def __init__(self, data=None):
        data = data or {}
        self.exact = data.get("exact", {})  # field -> {real: pseudonym}
        self.sites = data.get("sites", {})
        self.hosts = data.get("hosts", {})
        self.segments = data.get("segments", {})
        self.params = data.get("params", {})
        self.values = data.get("values", {})
        self.fragments = data.get("fragments", {})

    def to_json(self):
        return {
            "exact": self.exact, "sites": self.sites, "hosts": self.hosts,
            "segments": self.segments, "params": self.params,
            "values": self.values, "fragments": self.fragments,
        }

    def learn(self, table, real, pseudonym):
        known = table.setdefault(real, pseudonym)
        if known != pseudonym:
            raise ValueError(f"{real!r} has two pseudonyms: {known!r} and {pseudonym!r}")

    # -- new pseudonyms -----------------------------------------------------

    @staticmethod
    def _next_number(table, pattern):
        numbers = [int(m.group(1)) for v in table.values() if (m := re.fullmatch(pattern, v))]
        return max(numbers, default=0) + 1

    def site(self, domain):
        if domain not in self.sites:
            self.sites[domain] = "site-%02d.example" % self._next_number(self.sites, r"site-(\d+)\.example")
        return self.sites[domain]

    def host(self, host):
        if host not in self.hosts:
            domain = registered_domain(host)
            prefix = host[: -len(domain)].rstrip(".")
            site = self.site(domain)
            if not prefix:
                self.hosts[host] = site
            elif WWW_RE.match(prefix):
                self.hosts[host] = prefix + "." + site
            else:
                n = self._next_number(self.hosts, r"sub(\d+)\..*")
                self.hosts[host] = "sub%d.%s" % (n, site)
        return self.hosts[host]

    def segment(self, base):
        if base not in self.segments:
            codes = [letters_value(v[4:]) for v in self.segments.values()]
            self.segments[base] = "seg-" + letters(max(codes, default=0) + 1)
        return self.segments[base]

    def param(self, name):
        if name not in self.params:
            self.params[name] = "p%d" % self._next_number(self.params, r"p(\d+)")
        return self.params[name]

    def value(self, value):
        if value not in self.values:
            self.values[value] = "v%d" % self._next_number(self.values, r"v(\d+)")
        return self.values[value]

    def fragment(self, fragment):
        if fragment not in self.fragments:
            codes = [letters_value(v[5:]) for v in self.fragments.values()]
            self.fragments[fragment] = "frag-" + letters(max(codes, default=0) + 1)
        return self.fragments[fragment]

    # -- URLs -----------------------------------------------------------------

    def url(self, url):
        """Pseudonymise a URL part by part, the way the first release did."""
        known = self.exact.get("url", {}).get(url)
        if known is not None:
            return known
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            # e.g. a javascript: link: keep the scheme, hide the rest
            scheme, _, rest = url.partition(":")
            return scheme + ":" + self.segment(rest)
        out = parts.scheme + "://" + self.host(parts.hostname)
        if parts.port:
            out += ":%d" % parts.port
        segments = [s for s in parts.path.split("/") if s]
        if segments:
            names = []
            for segment in segments:
                base, ext = split_segment(segment)
                names.append(self.segment(base) + ext)
            out += "/" + "/".join(names)
        if parts.path.endswith("/"):
            out += "/"
        if parts.query:
            pairs = []
            for pair in parts.query.split("&"):
                if not pair:
                    pairs.append("")
                    continue
                name, eq, value = pair.partition("=")
                pairs.append(self.param(name) + eq + (self.value(value) if value else ""))
            out += "?" + "&".join(pairs)
        if "#" in url:
            out += "#" + (self.fragment(parts.fragment) if parts.fragment else "")
        return out

    def archived_url(self, archived_url):
        known = self.exact.get("archivedUrl", {}).get(archived_url)
        if known is not None:
            return known
        m = WEB_RE.match(archived_url)
        if not m:
            raise ValueError(f"not a playback URL: {archived_url}")
        return ARCHIVE_PREFIX + m.group(1) + "/" + self.url(m.group(2))

    def text(self, field, value):
        try:
            return self.exact[field][value]
        except KeyError:
            raise SystemExit(f"No pseudonym for {field} {value!r}: add it to {KEY_FILE} by hand") from None


def learn_url(key, real, pseudonym):
    """Record the parts of a URL pair from the first release."""
    a, b = urlsplit(real), urlsplit(pseudonym)
    if a.scheme not in ("http", "https") or not a.hostname or "site-" not in (b.hostname or ""):
        return
    key.learn(key.hosts, a.hostname, b.hostname)
    domain = registered_domain(a.hostname)
    key.learn(key.sites, domain, re.search(r"site-\d+\.example$", b.hostname).group(0))
    real_segments = [s for s in a.path.split("/") if s]
    fake_segments = [s for s in b.path.split("/") if s]
    if len(real_segments) == len(fake_segments):
        for s, t in zip(real_segments, fake_segments):
            base, ext = split_segment(s)
            key.learn(key.segments, base, t[: len(t) - len(ext)] if ext else t)
    real_pairs = [p for p in a.query.split("&") if p]
    fake_pairs = [p for p in b.query.split("&") if p]
    if len(real_pairs) == len(fake_pairs):
        for p, q in zip(real_pairs, fake_pairs):
            name, _, value = p.partition("=")
            fname, _, fvalue = q.partition("=")
            key.learn(key.params, name, fname)
            if value:
                key.learn(key.values, value, fvalue)
    if a.fragment and b.fragment:
        key.learn(key.fragments, a.fragment, b.fragment)


def learn_query(key, real, pseudonym):
    """Record the URLs and domains typed into a query, e.g. domain:c19.dk."""
    split = re.compile(r'(\s+|["()])')
    real_tokens, fake_tokens = split.split(real), split.split(pseudonym)
    if len(real_tokens) != len(fake_tokens):
        return
    for r, f in zip(real_tokens, fake_tokens):
        if "site-" not in f:
            continue
        field = re.match(r"^[a-z_]+:(?!//)", f)
        if field and r.startswith(field.group(0)):
            r, f = r[field.end():], f[field.end():]
        if "://" in r:
            learn_url(key, r, f)
        else:
            learn_url(key, "http://" + r, "http://" + f)


def bootstrap_key(participants):
    """Learn the pseudonyms of the first release in TARGET_DIR."""
    key = Key()
    for filename, pid in participants:
        real = load_records(os.path.join(ORIGINAL_DIR, filename))
        fake = load_records(os.path.join(TARGET_DIR, pid + ".json"))
        if len(real) != len(fake) or any("timestamp" in e for e in fake):
            raise SystemExit(
                f"{TARGET_DIR}/{pid}.json is not the first release, so {KEY_FILE} can't be "
                "learned from it. Restore the first release or the key file."
            )
        for r, f in zip(real, fake):
            for field in ("url", "archivedUrl") + TEXT_FIELDS:
                if field in r:
                    key.learn(key.exact.setdefault(field, {}), r[field], f[field])
            if "query" in r:
                learn_query(key, r["query"], f["query"])
            for rq, fq in zip(r.get("filterQueries", []), f.get("filterQueries", [])):
                key.learn(key.exact.setdefault("filterQueries", {}), rq, fq)
            if "archivedUrl" in r:
                learn_url(key, r["url"], f["url"])
                learn_url(key, WEB_RE.match(r["archivedUrl"]).group(2),
                          WEB_RE.match(f["archivedUrl"]).group(2))
            for fq_real, fq_fake in zip(r.get("filterQueries", []), f.get("filterQueries", [])):
                m, n = re.match(r'domain:"(.*)"$', fq_real), re.match(r'domain:"(.*)"$', fq_fake)
                if m and n:
                    key.learn(key.sites, m.group(1), n.group(1))
    return key


def anonymise_entry(entry, key):
    out = {}
    for field, value in entry.items():
        if field == "url":
            out[field] = key.url(value)
        elif field == "archivedUrl":
            out[field] = key.archived_url(value)
        elif field in TEXT_FIELDS:
            out[field] = key.text(field, value)
        elif field == "filterQueries":
            out[field] = [key.text(field, v) for v in value]
        elif field == "timestamp":
            # Keep the time of day only: the session date tells who took part when
            out[field] = value.split("T", 1)[1] if value else None
        else:
            out[field] = value
    return out


def main():
    with open(MAP_FILE, encoding="utf-8") as fh:
        mapping = json.load(fh)
    participants = sorted(
        ((name, pid) for name, pid in mapping.items()
         if os.path.exists(os.path.join(SOURCE_DIR, name))),
        key=lambda p: p[1],
    )
    if not participants:
        sys.exit(f"No corrected histories in {SOURCE_DIR}/; run correct_histories.py first")

    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as fh:
            key = Key(json.load(fh))
    else:
        key = bootstrap_key(participants)

    total = 0
    for name, pid in participants:
        entries = [anonymise_entry(e, key) for e in load_records(os.path.join(SOURCE_DIR, name))]
        with open(os.path.join(TARGET_DIR, pid + ".json"), "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        total += len(entries)

    with open(KEY_FILE, "w", encoding="utf-8") as fh:
        json.dump(key.to_json(), fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    print(f"Wrote {len(participants)} files ({total} entries) to {TARGET_DIR}/; key in {KEY_FILE}")


if __name__ == "__main__":
    main()
