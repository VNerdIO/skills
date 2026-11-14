#!/usr/bin/env python3
"""Build a single-file, offline four-generation pedigree chart from tree.json.

Usage: chart.py TREE.json OUT.html [--subject ID|NAME] [--ged FILE.ged] [--title TEXT] [--hide-living]

The subject plus parents, grandparents and great-grandparents (Ahnentafel 1-15) go into
the page, with only the sources those 15 cite. --ged embeds that file for a Download
GEDCOM button. --hide-living shows living people as "Living" with no dates or places.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from gedcom import normalize_date

GENERATIONS = 4
TEMPLATE = Path(__file__).with_name("chart_template.html")


def pick_subject(tree, wanted):
    people = tree["people"]
    if not wanted:
        wanted = tree.get("subject")
    if not wanted:
        sys.exit("No subject: pass --subject or set \"subject\" in tree.json")
    if wanted in people:
        return wanted
    needle = wanted.lower().split()
    hits = [pid for pid, p in people.items()
            if all(n in f"{p.get('given', '')} {p.get('surname', '')}".lower() for n in needle)]
    if len(hits) == 1:
        return hits[0]
    for pid in hits:
        p = people[pid]
        print(f"{pid}\t{p.get('given', '')} {p.get('surname', '')}\t{(p.get('birth') or {}).get('date', '')}")
    sys.exit(f"{len(hits)} people match {wanted!r}; pass --subject with an id" if hits
             else f"Nobody matches {wanted!r}")


def pedigree(tree, subject):
    """Ahnentafel number -> person id: 1 subject, 2n father of n, 2n+1 mother of n."""
    people, slots = tree["people"], {1: subject}
    for n in range(1, 2 ** (GENERATIONS - 1)):
        p = people.get(slots.get(n) or "")
        if p:
            for k, child in (("father", 2 * n), ("mother", 2 * n + 1)):
                if p.get(k) in people:
                    slots[child] = p[k]
    return slots


def strip_living(p):
    return {"given": "Living", "surname": p.get("surname", ""), "sex": p.get("sex"), "living": True}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tree")
    ap.add_argument("out")
    ap.add_argument("--subject")
    ap.add_argument("--ged")
    ap.add_argument("--title")
    ap.add_argument("--hide-living", action="store_true")
    args = ap.parse_args()

    tree = json.loads(Path(args.tree).read_text(encoding="utf-8"))
    subject = pick_subject(tree, args.subject)
    slots = pedigree(tree, subject)
    people = {}
    for n, pid in slots.items():
        p = dict(tree["people"][pid])
        for k in ("birth", "death", "burial"):
            if p.get(k):
                p[k] = {**p[k], "date": normalize_date(p[k].get("date"))}
        people[pid] = strip_living(p) if args.hide_living and p.get("living") else p
    cited = set()
    for p in people.values():
        for item in [p] + [p.get(k) or {} for k in ("birth", "death", "burial")]:
            cited |= {c if isinstance(c, str) else c["id"] for c in item.get("sources", [])}
    marriages = [m for m in tree.get("marriages", []) if m.get("husband") in people and m.get("wife") in people]
    marriages = [{**m, "date": normalize_date(m.get("date"))} for m in marriages]
    for m in marriages:
        cited |= {c if isinstance(c, str) else c["id"] for c in m.get("sources", [])}
    s = tree["people"][subject]
    surname = s.get("surname") or "Family"
    data = {
        "title": args.title or f"{surname} Family Tree",
        "subject": subject,
        "slots": {str(n): pid for n, pid in slots.items()},
        "people": people,
        "marriages": [] if args.hide_living else marriages,
        "sources": {k: v for k, v in tree.get("sources", {}).items() if k in cited},
        "generated": dt.date.today().isoformat(),
        "ged_name": Path(args.ged).name if args.ged else None,
        "ged": Path(args.ged).read_text(encoding="utf-8") if args.ged else None,
    }
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__TITLE__", data["title"].replace("&", "&amp;").replace("<", "&lt;"))
    html = html.replace("__DATA__", blob)
    Path(args.out).write_text(html, encoding="utf-8")
    found = len(slots)
    print(f"{found} of {2 ** GENERATIONS - 1} pedigree slots filled -> {args.out}")
    empty = [n for n in range(2, 2 ** GENERATIONS) if n not in slots and (n // 2) in slots]
    if empty:
        print("Unknown:", ", ".join(f"#{n} ({'father' if n % 2 == 0 else 'mother'} of "
                                    f"{tree['people'][slots[n // 2]].get('given', '')})" for n in empty))


if __name__ == "__main__":
    main()
