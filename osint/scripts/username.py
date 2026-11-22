#!/usr/bin/env python3
"""Find where a username is registered, using the WhatsMyName site list (~700 sites).

Usage:
  username.py USERNAME [--cat CATEGORY ...] [--workers 40] [--timeout 12]
  username.py --profiles USERNAME      # pull public profile fields from APIs that expose them

Prints JSON. "hits" are sites where the page matched WhatsMyName's "account exists"
signature (status code AND marker string), so false positives are rare but not zero:
open each hit before relying on it. The site list is cached for a day in
~/.cache/osint-skill/wmn-data.json.
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.parse

from common import dump, fetch, fetch_json

WMN = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
CACHE = os.path.expanduser("~/.cache/osint-skill/wmn-data.json")


def sites():
    if not os.path.exists(CACHE) or time.time() - os.path.getmtime(CACHE) > 86400:
        status, body, _ = fetch(WMN, timeout=30)
        if status == 200:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w") as f:
                f.write(body)
        elif not os.path.exists(CACHE):
            sys.exit(f"could not download WhatsMyName list: {body[:200]}")
    with open(CACHE) as f:
        return json.load(f)["sites"]


def check(site, user, timeout):
    u = user
    for ch in site.get("strip_bad_char", ""):
        u = u.replace(ch, "")
    q = urllib.parse.quote(u, safe="")
    url = site["uri_check"].replace("{account}", q)
    body = site.get("post_body")
    status, text, _ = fetch(url, data=body.replace("{account}", q) if body else None,
                            headers=site.get("headers"), timeout=timeout)
    if status is None:
        return "error", site, url
    if status == site["e_code"] and site["e_string"] in text:
        if site.get("m_string") and site["m_string"] in text and site.get("m_code") == status:
            return "unclear", site, url
        return "hit", site, url
    return "miss", site, url


def enumerate_sites(user, cats, workers, timeout):
    todo = [s for s in sites() if s.get("valid", True) and (not cats or s["cat"] in cats)]
    hits, unclear, errors = [], [], 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for res, site, url in ex.map(lambda s: check(s, user, timeout), todo):
            pretty = site.get("uri_pretty", site["uri_check"]).replace("{account}", user)
            row = {"site": site["name"], "category": site["cat"], "url": pretty}
            if res == "hit":
                hits.append(row)
            elif res == "unclear":
                unclear.append(row)
            elif res == "error":
                errors += 1
    key = lambda r: (r["category"], r["site"].lower())
    return {"username": user, "checked": len(todo), "errors": errors,
            "hits": sorted(hits, key=key), "unclear": sorted(unclear, key=key)}


def profiles(user):
    """Public profile fields from sites whose APIs return them without a key."""
    out = {}
    s, j = fetch_json(f"https://api.github.com/users/{urllib.parse.quote(user)}")
    if s == 200 and j:
        out["github"] = {k: j.get(k) for k in ("login", "name", "company", "blog", "location", "email",
                                               "bio", "twitter_username", "created_at", "html_url")}
        _, ev = fetch_json(f"https://api.github.com/users/{urllib.parse.quote(user)}/events/public?per_page=100")
        emails = set()
        for e in ev or []:
            for c in (e.get("payload") or {}).get("commits", []) or []:
                em = (c.get("author") or {}).get("email", "")
                if em and "noreply" not in em:
                    emails.add(f'{(c.get("author") or {}).get("name")} <{em}>')
        out["github"]["commit_author_emails"] = sorted(emails)
    s, j = fetch_json(f"https://gitlab.com/api/v4/users?username={urllib.parse.quote(user)}")
    if s == 200 and j:
        out["gitlab"] = {k: j[0].get(k) for k in ("username", "name", "web_url", "avatar_url")}
    s, j = fetch_json(f"https://www.reddit.com/user/{urllib.parse.quote(user)}/about.json")
    if s == 200 and j and j.get("data"):
        d = j["data"]
        out["reddit"] = {"name": d.get("name"), "created_utc": d.get("created_utc"),
                         "karma": d.get("total_karma"),
                         "description": (d.get("subreddit") or {}).get("public_description")}
    s, j = fetch_json(f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={urllib.parse.quote(user)}")
    them = (j or {}).get("them") or []
    if them and them[0]:
        t = them[0]
        proofs = (t.get("proofs_summary") or {}).get("all", [])
        out["keybase"] = {"full_name": ((t.get("profile") or {}).get("full_name")),
                          "location": ((t.get("profile") or {}).get("location")),
                          "proofs": [{"service": p.get("proof_type"), "name": p.get("nametag"),
                                      "url": p.get("service_url")} for p in proofs]}
    s, j = fetch_json(f"https://hacker-news.firebaseio.com/v0/user/{urllib.parse.quote(user)}.json")
    if s == 200 and j:
        out["hackernews"] = {"id": j.get("id"), "created": j.get("created"), "about": j.get("about")}
    s, j = fetch_json(f"https://api.chess.com/pub/player/{urllib.parse.quote(user.lower())}")
    if s == 200 and j and j.get("username"):
        out["chess.com"] = {k: j.get(k) for k in ("name", "username", "location", "country", "joined", "url")}
    return {"username": user, "profiles": out}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("username")
    ap.add_argument("--profiles", action="store_true")
    ap.add_argument("--cat", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=12)
    a = ap.parse_args()
    dump(profiles(a.username) if a.profiles else enumerate_sites(a.username, set(a.cat), a.workers, a.timeout))
