#!/usr/bin/env python3
"""Look up current weekly-ad specials for grocery list items at Publix or Food City.

Usage: specials.py --store publix|foodcity --zip ZIP [--top N] ITEM [ITEM ...]
       specials.py --store publix --zip 37919 --file list.txt

Searches Flipp (the weekly-ad aggregator both chains publish to) once per item,
keeps only that store's deals that are valid today, and prints JSON:

  {"store": ..., "zip": ..., "fetched": ..., "results": {"milk": [deal, ...], ...}}

Each deal has name, price, sale_story, valid_to and a match score (0-1, the share of
the item's words found in the deal name). Search results are fuzzy ("milk" can return
milk chocolate), so the caller decides which deals really match. Standard library only.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SEARCH_URL = "https://backflipp.wishabi.com/flipp/items/search"
MERCHANTS = {"publix": "Publix", "foodcity": "FoodCity"}  # Flipp's merchant_name values
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
DELAY = 0.4  # seconds between requests, to be polite


def search(query, postal_code):
    params = urllib.parse.urlencode({"locale": "en-us", "postal_code": postal_code, "q": query})
    req = urllib.request.Request(f"{SEARCH_URL}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def price_text(item):
    """Join Flipp's price pieces, e.g. '2/$5', '$3.99 lb', 'BOGO'."""
    parts = [item.get("pre_price_text"), None, item.get("post_price_text")]
    if item.get("current_price") is not None:
        parts[1] = f"${item['current_price']:.2f}"
    text = " ".join(p.strip() for p in parts if p and p.strip())
    if not text and "BOGO" in (item.get("name") or ""):
        text = "BOGO"
    return text or None


def deals_for(query, merchant, postal_code, now, top):
    data = search(query, postal_code)
    want = words(query)
    deals = []
    for it in data.get("items", []):
        if it.get("merchant_name") != merchant:
            continue
        valid_to = it.get("valid_to")
        if valid_to and datetime.fromisoformat(valid_to) < now:
            continue
        name = it.get("name") or ""
        score = len(want & words(name)) / len(want) if want else 0
        deals.append({
            "name": name,
            "price": price_text(it),
            "original_price": it.get("original_price"),
            "sale_story": it.get("sale_story"),
            "valid_from": it.get("valid_from"),
            "valid_to": valid_to,
            "score": round(score, 2),
        })
    deals.sort(key=lambda d: -d["score"])  # stable: keeps Flipp's ranking within a score
    return deals[:top]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True, choices=sorted(MERCHANTS))
    ap.add_argument("--zip", required=True, help="ZIP code of the store (deals are regional)")
    ap.add_argument("--top", type=int, default=5, help="max deals per item (default 5)")
    ap.add_argument("--file", help="read items from a file, one per line")
    ap.add_argument("items", nargs="*")
    args = ap.parse_args()

    items = list(args.items)
    if args.file:
        with open(args.file) as f:
            items += [line.strip() for line in f if line.strip()]
    if not items:
        ap.error("no items given")

    now = datetime.now(timezone.utc)
    results, errors = {}, {}
    for i, item in enumerate(items):
        if i:
            time.sleep(DELAY)
        try:
            results[item] = deals_for(item, MERCHANTS[args.store], args.zip, now, args.top)
        except Exception as e:  # one bad lookup shouldn't sink the whole list
            errors[item] = str(e)

    out = {"store": args.store, "zip": args.zip, "fetched": now.isoformat(timespec="seconds"), "results": results}
    if errors:
        out["errors"] = errors
    json.dump(out, sys.stdout, indent=1)
    print()
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
