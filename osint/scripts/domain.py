#!/usr/bin/env python3
"""Attribute a domain name to the person or organisation that runs it (no API keys needed).

Usage:
  domain.py DOMAIN        (a bare domain, subdomain or URL; the host part is used)

Prints JSON: RDAP registration (registrar, registrant if not redacted, dates, status,
nameservers, abuse contact), DNS (A/AAAA, MX, NS, TXT with SPF, DMARC and SaaS
verification tokens), the hosting network of each address, the website's title,
redirect target, generator and tracking IDs, emails on the home page, certificate
transparency (first certificate and subdomains from crt.sh) and the first Wayback
Machine capture. Optional keys: VT_KEY (VirusTotal reputation and categories),
IPINFO_TOKEN (higher rate limits for the hosting lookups).
"""
import datetime
import json
import os
import re
import sys
import urllib.parse

from common import dns, dump, fetch, fetch_json

# TXT verification prefixes -> the service the domain owner signed up for.
VERIFICATIONS = {
    "google-site-verification=": "Google Search Console / Workspace",
    "MS=": "Microsoft 365", "facebook-domain-verification=": "Meta Business",
    "apple-domain-verification=": "Apple", "atlassian-domain-verification=": "Atlassian",
    "docusign=": "DocuSign", "stripe-verification=": "Stripe", "zoom-verification=": "Zoom",
    "adobe-idp-site-verification=": "Adobe", "hubspot-site-verification=": "HubSpot",
    "slack-domain-verification=": "Slack", "openai-domain-verification=": "OpenAI",
    "notion-domain-verification=": "Notion", "dropbox-domain-verification=": "Dropbox",
    "yandex-verification:": "Yandex", "brave-ledger-verification=": "Brave Creators",
    "keybase-site-verification=": "Keybase", "_github-challenge": "GitHub org",
    "globalsign-domain-verification=": "GlobalSign", "have-i-been-pwned-verification=": "HIBP",
    "mailru-verification:": "Mail.ru", "status-page-domain-verification=": "Atlassian Statuspage",
}
# SPF include/redirect fragments -> mail vendor.
SPF_VENDORS = {
    "_spf.google.com": "Google Workspace", "spf.protection.outlook.com": "Microsoft 365",
    "zoho": "Zoho", "protonmail": "Proton", "mailgun": "Mailgun", "sendgrid": "SendGrid",
    "amazonses": "Amazon SES", "mcsv.net": "Mailchimp", "mandrillapp": "Mailchimp Transactional",
    "servers.mcsv.net": "Mailchimp", "hubspotemail": "HubSpot", "salesforce": "Salesforce",
    "zendesk": "Zendesk", "freshdesk": "Freshdesk", "messagingengine": "Fastmail",
    "secureserver.net": "GoDaddy", "emailsrvr.com": "Rackspace", "mimecast": "Mimecast",
    "pphosted": "Proofpoint", "sparkpostmail": "SparkPost", "postmarkapp": "Postmark",
}
TRACKERS = {
    "google_analytics": r"\b(UA-\d{4,10}-\d{1,4}|G-[A-Z0-9]{6,12})\b",
    "google_tag_manager": r"\b(GTM-[A-Z0-9]{4,8})\b",
    "adsense": r"\b(ca-pub-\d{10,20}|pub-\d{10,20})\b",
    "facebook_pixel": r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})['\"]",
    "yandex_metrica": r"ym\(\s*(\d{6,10})\s*,",
}
PRIVACY_HINTS = ("redacted", "privacy", "proxy", "withheld", "whoisguard", "domains by proxy",
                 "contact privacy", "perfect privacy", "data protected", "not disclosed",
                 "identity protect", "private by design", "statutory masking")


def host_of(arg):
    arg = arg.strip().lower()
    if "://" not in arg:
        arg = "http://" + arg
    host = urllib.parse.urlsplit(arg).hostname or ""
    return host.rstrip(".")


def rdap(domain):
    """RDAP for the registered domain. Walks up from a subdomain until a registry answers."""
    labels = domain.split(".")
    for i in range(len(labels) - 1):
        name = ".".join(labels[i:])
        status, j = fetch_json(f"https://rdap.org/domain/{name}", timeout=20)
        if status == 200 and j:
            return name, _parse_rdap(name, j)
    return domain, {"error": "no RDAP record (unregistered, or a ccTLD without RDAP: "
                             "try the registry's WHOIS site by hand)"}


def _vcard(e):
    out = {}
    for item in (e.get("vcardArray") or [None, []])[1]:
        key, val = item[0], item[3]
        if key in ("fn", "org", "email", "tel", "adr"):
            if key == "adr":
                val = item[1].get("label") or " ".join(x for x in val if isinstance(x, str) and x)
            out[key] = " ".join(val) if isinstance(val, list) else val
    return out


def _parse_rdap(name, j):
    events = {e.get("eventAction"): e.get("eventDate") for e in j.get("events", [])}
    entities = []

    def walk(e, depth=0):
        entities.append({"roles": e.get("roles"), "handle": e.get("handle"), **_vcard(e)})
        if depth < 2:
            for sub in e.get("entities", []):
                walk(sub, depth + 1)
    for e in j.get("entities", []):
        walk(e)

    registrant = [e for e in entities if "registrant" in (e.get("roles") or [])]
    blob = json.dumps(registrant).lower()
    reg_date = events.get("registration")
    age = None
    if reg_date:
        try:
            d = datetime.datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
            age = (datetime.datetime.now(datetime.timezone.utc) - d).days
        except ValueError:
            pass
    return {
        "registered": reg_date, "age_days": age, "expires": events.get("expiration"),
        "last_changed": events.get("last changed"), "status": j.get("status"),
        "nameservers": sorted(n.get("ldhName", "").lower() for n in j.get("nameservers", [])),
        "registrar": next((e.get("fn") or e.get("org") for e in entities
                           if "registrar" in (e.get("roles") or [])), None),
        "registrant": registrant,
        "registrant_redacted": (not registrant) or any(h in blob for h in PRIVACY_HINTS),
        "abuse": [e for e in entities if "abuse" in (e.get("roles") or [])],
        "source": next((l["href"] for l in j.get("links", []) if l.get("rel") == "self"),
                       f"https://rdap.org/domain/{name}"),
    }


def dns_records(domain, apex):
    txt = dns(domain, "TXT")
    spf = [t for t in txt if "v=spf1" in t]
    dmarc = [t for t in dns(f"_dmarc.{apex}", "TXT") if "v=DMARC1" in t]
    verifications = sorted({svc for t in txt for k, svc in VERIFICATIONS.items()
                            if t.strip('"').startswith(k)})
    vendors = sorted({v for s in spf for k, v in SPF_VENDORS.items() if k in s})
    mx = dns(domain, "MX")
    mxs = " ".join(mx).lower()
    mail_host = ("Google Workspace" if "google" in mxs else "Microsoft 365" if "outlook" in mxs
                 else "Proton" if "proton" in mxs else "Zoho" if "zoho" in mxs
                 else "Fastmail" if "messagingengine" in mxs else None)
    return {"a": dns(domain, "A"), "aaaa": dns(domain, "AAAA"), "cname": dns(domain, "CNAME"),
            "ns": dns(apex, "NS"), "mx": mx, "mail_host": mail_host, "spf": spf,
            "spf_senders": vendors, "dmarc": dmarc, "txt_verifications": verifications,
            "txt_other": [t for t in txt if "v=spf1" not in t
                          and not any(t.strip('"').startswith(k) for k in VERIFICATIONS)][:15]}


def hosting(ips):
    token = os.environ.get("IPINFO_TOKEN")
    out = []
    for ip in ips[:3]:
        _, j = fetch_json(f"https://ipinfo.io/{ip}/json",
                          headers={"Authorization": f"Bearer {token}"} if token else {})
        j = j or {}
        out.append({"ip": ip, "org": j.get("org"), "hostname": j.get("hostname"),
                    "country": j.get("country")})
    return out


def website(domain, apex):
    status, html, final = fetch(f"https://{domain}", timeout=15)
    if status is None:
        status, html, final = fetch(f"http://{domain}", timeout=15)
    if status is None:
        return {"error": html}
    html = html or ""

    def meta(name):
        m = re.search(rf'<meta[^>]+(?:name|property)=["\']{name}["\'][^>]+content=["\']([^"\']*)',
                      html, re.I)
        return m.group(1).strip()[:300] if m else None
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    trackers = {k: sorted(set(re.findall(p, html))) for k, p in TRACKERS.items()}
    emails = sorted({e.lower() for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", html)
                     if not e.lower().endswith((".png", ".jpg", ".gif", ".svg", ".webp"))})[:20]
    social = sorted(set(re.findall(
        r'https?://(?:www\.)?(?:twitter\.com|x\.com|facebook\.com|instagram\.com|linkedin\.com/'
        r'(?:in|company)|github\.com|youtube\.com|t\.me|tiktok\.com)/[\w@./-]+', html)) - {u for u in re.findall(r"https?://[^\s\"']+", html)
                 if (urllib.parse.urlsplit(u).hostname or "").endswith(apex)})[:20]
    final_host = urllib.parse.urlsplit(final).hostname or ""
    return {"status": status, "final_url": final,
            "redirects_offsite": bool(final_host) and not (final_host == apex or final_host.endswith("." + apex)),
            "title": t.group(1).strip()[:200] if t else None,
            "description": meta("description") or meta("og:description"),
            "site_name": meta("og:site_name"), "generator": meta("generator"),
            "trackers": {k: v for k, v in trackers.items() if v},
            "emails": emails, "social_links": social}


def cert_transparency(apex):
    status, j = fetch_json(f"https://crt.sh/?q=%25.{urllib.parse.quote(apex)}&output=json", timeout=45)
    if not isinstance(j, list):
        return certspotter(apex, f"crt.sh HTTP {status}")
    names, orgs, first = set(), set(), None
    for c in j:
        for n in (c.get("name_value") or "").split("\n"):
            n = n.strip().lower().lstrip("*.")
            if n == apex or n.endswith("." + apex):
                names.add(n)
        issued = c.get("not_before")
        if issued and (first is None or issued < first):
            first = issued
        m = re.search(r"O=([^,]+)", c.get("issuer_name") or "")
        if m:
            orgs.add(m.group(1).strip('"'))
    return {"certificates": len(j), "first_issued": first, "issuers": sorted(orgs)[:10],
            "subdomains": sorted(names)[:100], "subdomain_count": len(names),
            "source": f"https://crt.sh/?q=%25.{apex}"}


def certspotter(apex, why):
    """Fallback when crt.sh is down (it often is). Unauthenticated: recent issuances only."""
    q = urllib.parse.urlencode([("domain", apex), ("include_subdomains", "true"),
                                ("expand", "dns_names"), ("expand", "issuer")])
    status, j = fetch_json(f"https://api.certspotter.com/v1/issuances?{q}", timeout=30)
    if not isinstance(j, list):
        return {"error": f"{why}; Cert Spotter HTTP {status}. Open https://crt.sh/?q={apex} by hand"}
    names = {n.lower().lstrip("*.") for c in j for n in c.get("dns_names", [])}
    names = {n for n in names if n == apex or n.endswith("." + apex)}
    firsts = [c.get("not_before") for c in j if c.get("not_before")]
    return {"via": f"Cert Spotter ({why}); partial, so check crt.sh by hand for full history",
            "certificates": len(j), "first_issued": min(firsts) if firsts else None,
            "issuers": sorted({(c.get("issuer") or {}).get("friendly_name") for c in j} - {None}),
            "subdomains": sorted(names)[:100], "subdomain_count": len(names),
            "source": f"https://sslmate.com/certspotter/api/ ; https://crt.sh/?q=%25.{apex}"}


def wayback(apex):
    q = urllib.parse.urlencode({"url": apex, "output": "json", "limit": "1", "fl": "timestamp,original"})
    _, j = fetch_json(f"https://web.archive.org/cdx/search/cdx?{q}", timeout=30)
    first = j[1] if isinstance(j, list) and len(j) > 1 else None
    return {"first_capture": first[0] if first else None,
            "first_capture_url": f"https://web.archive.org/web/{first[0]}/{first[1]}" if first else None,
            "all_captures": f"https://web.archive.org/web/*/{apex}*"}


def virustotal(apex):
    key = os.environ.get("VT_KEY")
    if not key:
        return {"skipped": f"set VT_KEY, or open https://www.virustotal.com/gui/domain/{apex}"}
    _, j = fetch_json(f"https://www.virustotal.com/api/v3/domains/{apex}", headers={"x-apikey": key})
    a = ((j or {}).get("data") or {}).get("attributes", {})
    return {k: a.get(k) for k in ("last_analysis_stats", "reputation", "categories", "tags",
                                  "creation_date", "registrar")}


def main(arg):
    domain = host_of(arg)
    if not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z0-9-]{2,}", domain or ""):
        sys.exit(f"not a domain name: {arg}")
    apex, reg = rdap(domain)
    records = dns_records(domain, apex)
    dump({"domain": domain, "registered_domain": apex, "rdap": reg, "dns": records,
          "hosting": hosting(records["a"] + records["aaaa"]),
          "website": website(domain, apex), "cert_transparency": cert_transparency(apex),
          "wayback": wayback(apex), "virustotal": virustotal(apex)})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
