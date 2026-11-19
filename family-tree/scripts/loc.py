#!/usr/bin/env python3
"""Search Chronicling America (Library of Congress digitized newspapers, ~1770-1963; no login).

Usage:
  loc.py search "FIRST LAST" [--state tennessee] [--county knox] [--from YYYY] [--to YYYY] [--limit N] [--context N]
  loc.py text PAGE-URL [--grep TEXT] [--context N]

search runs an exact-phrase query and, for each hit, reads the page's OCR and prints the
lines around the phrase, so a hit can be judged without opening it. OCR is noisy: a name
may be split across a line break or misread, and the phrase can match the wrong person.
Prints JSON. Cite each accepted page by its "url"; the page image is the evidence.
LOC rate-limits hard (HTTP 429), so requests are spaced out and retried; run one search
at a time, not several in parallel.
"""
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SEARCH = "https://www.loc.gov/collections/chronicling-america/"
UA = "family-tree-skill"
GAP = 3.0  # seconds between requests; LOC allows only a few per 10 s
_last = 0.0


def get(url, params=None, timeout=90, tries=5):
    global _last
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for n in range(tries):
        time.sleep(max(0.0, _last + GAP - time.time()))
        _last = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or n == tries - 1:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 0) or 20 * (n + 1))


def search(phrase, state=None, county=None, start=None, end=None, limit=20):
    q = {"ops": "PHRASE", "qs": phrase, "searchType": "advanced", "fo": "json",
         "c": limit, "at": "results,pagination"}
    facets = [f"location_state:{state.lower()}"] if state else []
    facets += [f"location_county:{county.lower()}"] if county else []
    if facets:
        q["fa"] = "|".join(facets)
    if start or end:
        q["dates"] = f"{start or 1700}/{end or 1963}"
    body = json.loads(get(SEARCH, q))
    return body["pagination"].get("of", 0), body.get("results", [])


def alto_url(page_url):
    """The page's ALTO XML (OCR with layout), from its loc.gov resource record."""
    base = page_url.split("&q=")[0]
    sep = "&" if "?" in base else "?"
    rec = json.loads(get(base + sep + "fo=json&at=page"))
    return next((x["url"] for x in rec.get("page", []) if x.get("mimetype") == "text/xml"), None)


def page_lines(page_url):
    """OCR text as lines in reading order, rejoining words hyphenated across lines."""
    xml = get(alto_url(page_url)).decode("utf-8", "ignore")
    lines = []
    for line in re.findall(r"<TextLine\b.*?</TextLine>", xml, re.S):
        words = []
        for s in re.findall(r"<String\b[^>]*>", line):
            content = re.search(r'CONTENT="([^"]*)"', s)
            subs = re.search(r'SUBS_CONTENT="([^"]*)"', s)
            part = re.search(r'SUBS_TYPE="([^"]*)"', s)
            if part and part.group(1) == "HypPart2":
                continue  # already emitted whole with HypPart1
            words.append((subs or content).group(1) if subs and part else content.group(1))
        lines.append(" ".join(words).replace("&quot;", '"').replace("&amp;", "&"))
    return lines


def around(lines, needle, context):
    """Line windows around each place the needle occurs, ignoring case and punctuation
    (OCR often drops or doubles the periods in initials, as the search index does)."""
    pat = re.compile(r"\W+".join(map(re.escape, re.findall(r"\w+", needle))), re.I)
    text = "\n".join(lines)
    out = []
    for m in pat.finditer(text):
        a = text.count("\n", 0, m.start())
        out.append("\n".join(lines[max(0, a - context):a + context + 1]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("phrase")
    s.add_argument("--state")
    s.add_argument("--county", help="county where the paper was published, e.g. knox")
    s.add_argument("--from", dest="start", type=int)
    s.add_argument("--to", dest="end", type=int)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--context", type=int, default=6, help="lines of OCR either side of the phrase")
    t = sub.add_parser("text")
    t.add_argument("url")
    t.add_argument("--grep")
    t.add_argument("--context", type=int, default=6)
    a = ap.parse_args()

    if a.cmd == "text":
        lines = page_lines(a.url)
        print("\n\n---\n\n".join(around(lines, a.grep, a.context)) if a.grep else "\n".join(lines))
        return

    total, results = search(a.phrase, a.state, a.county, a.start, a.end, a.limit)
    hits = []
    for r in results:
        hit = {"date": r.get("date"), "paper": (r.get("partof_title") or [""])[0],
               "url": r["url"].split("&q=")[0]}
        try:
            hit["excerpts"] = around(page_lines(hit["url"]), a.phrase, a.context)
        except Exception as e:  # one unreadable page shouldn't sink the search
            hit["error"] = str(e)
        hits.append(hit)
    print(json.dumps({"phrase": a.phrase, "total": total, "hits": hits}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
