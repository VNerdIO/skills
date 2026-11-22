#!/usr/bin/env python3
"""Gather public signals about an email address (no API keys needed).

Usage:
  mail.py ADDRESS

Prints JSON: domain kind (free webmail, disposable, or organisation) with MX/SPF and
the domain's website title, Gravatar profile, PGP keys on keys.openpgp.org, GitHub
commits and accounts tied to the address, and the local part to pivot on as a username.
Breach exposure (Have I Been Pwned) needs HIBP_KEY; without it, check by hand at
https://haveibeenpwned.com.
"""
import hashlib
import os
import re
import sys
import urllib.parse

from common import dns, dump, fetch, fetch_json

FREE = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
        "yahoo.com", "ymail.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me",
        "protonmail.com", "pm.me", "gmx.com", "gmx.net", "mail.com", "zoho.com", "yandex.com",
        "yandex.ru", "mail.ru", "tutanota.com", "tuta.io", "fastmail.com", "hey.com", "qq.com",
        "163.com", "comcast.net", "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net",
        "charter.net", "cox.net", "earthlink.net", "web.de", "btinternet.com", "orange.fr"}
DISPOSABLE = "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/main/disposable_email_blocklist.conf"


def domain_info(domain):
    mx = dns(domain, "MX")
    spf = [t for t in dns(domain, "TXT") if "v=spf1" in t]
    _, block, _ = fetch(DISPOSABLE, timeout=20)
    disposable = domain in set(block.split()) if block and "\n" in block else None
    kind = "disposable" if disposable else "free-webmail" if domain in FREE else "organisation/custom"
    out = {"domain": domain, "kind": kind, "mx": mx, "spf": spf, "accepts_mail": bool(mx)}
    mxs = " ".join(mx).lower()
    out["mail_host"] = ("Google Workspace" if "google" in mxs else "Microsoft 365" if "outlook" in mxs
                        else "Proton" if "proton" in mxs else "Zoho" if "zoho" in mxs else None)
    if kind == "organisation/custom":
        status, html, final = fetch(f"https://{domain}", timeout=15)
        m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
        out["website"] = {"status": status, "url": final, "title": m.group(1).strip()[:200] if m else None}
        _, r = fetch_json(f"https://rdap.org/domain/{domain}", timeout=20)
        if r:
            events = {e.get("eventAction"): e.get("eventDate") for e in r.get("events", [])}
            regs = []
            for e in r.get("entities", []):
                if "registrant" in (e.get("roles") or []) or "registrar" in (e.get("roles") or []):
                    fn = next((i[3] for i in (e.get("vcardArray") or [None, []])[1] if i[0] in ("fn", "org")), None)
                    regs.append({"roles": e.get("roles"), "name": fn})
            out["rdap"] = {"registered": events.get("registration"), "expires": events.get("expiration"),
                           "entities": regs}
    return out


def gravatar(email):
    h = hashlib.sha256(email.encode()).hexdigest()
    status, j = fetch_json(f"https://api.gravatar.com/v3/profiles/{h}")
    if status != 200 or not j:
        return None
    keep = ("display_name", "profile_url", "avatar_url", "location", "description", "job_title",
            "company", "pronouns", "verified_accounts", "links")
    return {k: j.get(k) for k in keep if j.get(k)}


def pgp(email):
    status, body, _ = fetch(f"https://keys.openpgp.org/vks/v1/by-email/{urllib.parse.quote(email)}")
    if status != 200:
        return None
    return {"found": True, "url": f"https://keys.openpgp.org/search?q={urllib.parse.quote(email)}"}


def github(email):
    q = urllib.parse.quote(f"author-email:{email}")
    _, j = fetch_json(f"https://api.github.com/search/commits?q={q}&per_page=20")
    commits = []
    logins = set()
    for it in (j or {}).get("items", []):
        a = it.get("author") or {}
        if a.get("login"):
            logins.add(a["login"])
        commits.append({"repo": (it.get("repository") or {}).get("full_name"),
                        "author_name": ((it.get("commit") or {}).get("author") or {}).get("name"),
                        "date": ((it.get("commit") or {}).get("author") or {}).get("date"),
                        "url": it.get("html_url")})
    _, u = fetch_json(f"https://api.github.com/search/users?q={urllib.parse.quote(email + ' in:email')}")
    profile_logins = sorted({it.get("login") for it in (u or {}).get("items", [])})
    return {"commit_author_logins": sorted(logins), "profile_email_logins": profile_logins,
            "commits": commits[:10]}


def hibp(email):
    key = os.environ.get("HIBP_KEY")
    if not key:
        return {"skipped": "set HIBP_KEY, or check by hand at https://haveibeenpwned.com"}
    status, j = fetch_json(f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}"
                           "?truncateResponse=false", headers={"hibp-api-key": key})
    if status == 404:
        return {"breaches": []}
    return {"breaches": [{"name": b.get("Name"), "date": b.get("BreachDate"),
                          "data": b.get("DataClasses")} for b in (j or [])]}


def main(email):
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        sys.exit(f"not an email address: {email}")
    local, domain = email.split("@", 1)
    dump({"email": email,
          "local_part": local,
          "username_pivots": sorted({local, re.sub(r"[._-]", "", local), local.split("+")[0]}),
          "domain": domain_info(domain),
          "gravatar": gravatar(email),
          "pgp": pgp(email),
          "github": github(email),
          "hibp": hibp(email)})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
