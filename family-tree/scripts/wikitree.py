#!/usr/bin/env python3
"""Look people up in WikiTree's public API (no login; private profiles are not returned).

Usage:
  wikitree.py search FIRST LAST [--birth YYYY[-MM-DD]] [--death YYYY] [--place TEXT] [--limit N]
  wikitree.py ancestors WIKITREE-ID [--depth 3]
  wikitree.py profile WIKITREE-ID

Prints JSON. Parents are given as WikiTree IDs. Dates come back ISO with 00 for unknown
parts; gedcom.py write converts them. Each person carries a "url" to cite as the source.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

API = "https://api.wikitree.com/api.php"
APP_ID = "family-tree-skill"
FIELDS = ("Id,Name,FirstName,MiddleName,Nicknames,LastNameAtBirth,LastNameCurrent,Gender,"
          "BirthDate,DeathDate,BirthLocation,DeathLocation,BirthDateDecade,IsLiving,Father,Mother")


def call(**params):
    data = urllib.parse.urlencode({"appId": APP_ID, **params}).encode()
    req = urllib.request.Request(API, data=data, headers={"User-Agent": APP_ID})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    return body[0] if isinstance(body, list) and body else body


def get_people(keys, ancestors=0):
    """getPeople by WikiTree IDs or numeric person Ids -> {numeric Id: raw person}."""
    q = {"action": "getPeople", "keys": ",".join(str(k) for k in keys), "fields": FIELDS}
    if ancestors:
        q["ancestors"] = ancestors
    r = call(**q)
    return {int(k): v for k, v in (r.get("people") or {}).items() if v.get("Name")}, r


def parent_ids(people):
    """Numeric Father/Mother Ids -> WikiTree IDs, fetching any parents not already in hand."""
    ids = {x["Id"]: x["Name"] for x in people}
    missing = {x[k] for x in people for k in ("Father", "Mother") if x.get(k) and x[k] not in ids}
    if missing:
        ids.update({i: x["Name"] for i, x in get_people(sorted(missing))[0].items()})
    return ids


def clean(ev):
    return {k: v for k, v in ev.items() if v and v != "0000-00-00"}


def tidy(p, ids):
    out = {
        "wikitree_id": p.get("Name"),
        "url": f"https://www.wikitree.com/wiki/{p['Name']}" if p.get("Name") else None,
        "given": " ".join(x for x in (p.get("FirstName"), p.get("MiddleName")) if x),
        "surname_at_birth": p.get("LastNameAtBirth"),
        "surname_current": p.get("LastNameCurrent"),
        "sex": {"Male": "M", "Female": "F"}.get(p.get("Gender"), "U"),
        "birth": clean({"date": p.get("BirthDate"), "place": p.get("BirthLocation")}),
        "death": clean({"date": p.get("DeathDate"), "place": p.get("DeathLocation")}),
        "living": bool(p.get("IsLiving")),
    }
    for k in ("Father", "Mother"):
        if p.get(k):
            out[k.lower()] = ids.get(p[k], p[k])
    return {k: v for k, v in out.items() if v not in (None, "", {})}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("first")
    s.add_argument("last")
    s.add_argument("--birth")
    s.add_argument("--death")
    s.add_argument("--place")
    s.add_argument("--limit", type=int, default=10)
    a = sub.add_parser("ancestors")
    a.add_argument("key")
    a.add_argument("--depth", type=int, default=3)
    p = sub.add_parser("profile")
    p.add_argument("key")
    args = ap.parse_args()

    try:
        if args.cmd == "search":
            q = {"action": "searchPerson", "FirstName": args.first, "LastName": args.last,
                 "limit": args.limit, "fields": FIELDS}
            if args.birth:
                q["BirthDate"] = args.birth
            if args.death:
                q["DeathDate"] = args.death
            if args.place:
                q["BirthLocation"] = args.place
            r = call(**q)
            matches = r.get("matches") or []
            ids = parent_ids(matches)
            out = {"total": r.get("total", 0), "matches": [tidy(m, ids) for m in matches]}
        else:
            people, r = get_people([args.key], args.depth if args.cmd == "ancestors" else 0)
            if not people:
                sys.exit(json.dumps({"error": f"no public profile for {args.key}", "status": r.get("status")}))
            ids = parent_ids(list(people.values()))
            found = [tidy(x, ids) for x in people.values()]
            out = {"root": args.key, "people": found} if args.cmd == "ancestors" else found[0]
        if isinstance(r, dict) and r.get("status") not in (0, None, ""):
            out["status"] = r["status"]  # e.g. "Illegal key" or a privacy refusal
    except Exception as e:  # network, HTTP or JSON failure: report it, don't guess
        sys.exit(json.dumps({"error": f"{type(e).__name__}: {e}"}))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
