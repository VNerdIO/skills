#!/usr/bin/env python3
"""Attribute an IP address to the network that holds it (no API keys needed).

Usage:
  ip.py IP

Prints JSON: RDAP registration (owner org, netblock, abuse contact), reverse DNS,
ASN/geolocation, open ports and tags from Shodan InternetDB, Tor exit status and a
hosting/residential guess. Optional keys raise coverage when set in the environment:
ABUSEIPDB_KEY, GREYNOISE_KEY (community), VT_KEY (VirusTotal), IPINFO_TOKEN (higher
rate limits; paid IPinfo plans add VPN/proxy/hosting flags, ASN type, company and abuse
contact, which then drive network_kind_guess).
"""
import ipaddress
import os
import sys

from common import dns, dump, fetch, fetch_json

HOSTING_HINTS = ("amazon", "aws", "google", "microsoft", "azure", "digitalocean", "linode",
                 "akamai", "ovh", "hetzner", "vultr", "cloudflare", "oracle", "alibaba",
                 "leaseweb", "choopa", "contabo", "scaleway", "hosting", "datacenter",
                 "data center", "server", "colo", "vps")
VPN_HINTS = ("vpn", "proxy", "mullvad", "nord", "expressvpn", "surfshark", "proton",
             "private internet access", "m247", "datacamp", "tzulo")


def rdap(ip):
    status, j = fetch_json(f"https://rdap.org/ip/{ip}", timeout=20)
    if not j:
        return {"error": f"RDAP lookup failed (HTTP {status})"}
    out = {"handle": j.get("handle"), "name": j.get("name"), "type": j.get("type"),
           "range": f'{j.get("startAddress")} - {j.get("endAddress")}',
           "country": j.get("country"), "entities": []}
    for e in j.get("entities", []):
        out["entities"].extend(_entity(e))
    out["remarks"] = [" ".join(r.get("description", [])) for r in j.get("remarks", [])][:3]
    out["source"] = next((l["href"] for l in j.get("links", []) if l.get("rel") == "self"),
                         f"https://rdap.org/ip/{ip}")
    return out


def _entity(e, depth=0):
    vc = {}
    for item in (e.get("vcardArray") or [None, []])[1]:
        key, val = item[0], item[3]
        if key in ("fn", "email", "tel", "adr", "org"):
            if key == "adr":
                val = item[1].get("label") or " ".join(x for x in val if isinstance(x, str) and x)
            vc[key] = " ".join(val) if isinstance(val, list) else val
    rows = [{"roles": e.get("roles"), "handle": e.get("handle"), **vc}]
    if depth < 2:
        for sub in e.get("entities", []):
            rows.extend(_entity(sub, depth + 1))
    return rows


def main(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        sys.exit(f"not an IP address: {ip}")
    if not addr.is_global:
        dump({"ip": ip, "note": "Private, reserved or loopback address: it only means something "
              "inside the network it came from. Check that network's DHCP/VPN logs."})
        return

    rev = addr.reverse_pointer
    result = {"ip": ip, "version": addr.version, "reverse_dns": dns(rev, "PTR"), "rdap": rdap(ip)}

    token = os.environ.get("IPINFO_TOKEN")
    status, info = fetch_json(f"https://ipinfo.io/{ip}/json",
                              headers={"Authorization": f"Bearer {token}"} if token else {})
    if info and "error" in info:
        err = info["error"]
        err = err.get("title") or err.get("message") if isinstance(err, dict) else err
        result["ipinfo"] = {"error": f"HTTP {status}: {err}"}
        info = None
    elif info:
        # Free/unauthenticated responses carry only the first group; paid plans add the
        # nested privacy, asn, company and abuse objects. Missing keys are left out.
        keep = ("hostname", "city", "region", "country", "loc", "org", "postal", "timezone",
                "anycast", "privacy", "asn", "company", "abuse", "domains")
        result["ipinfo"] = {k: info[k] for k in keep if k in info}
        result["ipinfo"]["authenticated"] = bool(token)
    else:
        result["ipinfo"] = None

    _, sh = fetch_json(f"https://internetdb.shodan.io/{ip}")
    result["shodan_internetdb"] = sh if sh and "detail" not in sh else None

    _, tor, _ = fetch("https://check.torproject.org/torbulkexitlist", timeout=20)
    result["tor_exit"] = ip in set(tor.split()) if tor and "\n" in tor else None

    if os.environ.get("ABUSEIPDB_KEY"):
        _, j = fetch_json(f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=365",
                          headers={"Key": os.environ["ABUSEIPDB_KEY"]})
        result["abuseipdb"] = (j or {}).get("data")
    if os.environ.get("GREYNOISE_KEY"):
        _, j = fetch_json(f"https://api.greynoise.io/v3/community/{ip}",
                          headers={"key": os.environ["GREYNOISE_KEY"]})
        result["greynoise"] = j
    if os.environ.get("VT_KEY"):
        _, j = fetch_json(f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
                          headers={"x-apikey": os.environ["VT_KEY"]})
        a = ((j or {}).get("data") or {}).get("attributes", {})
        result["virustotal"] = {k: a.get(k) for k in ("as_owner", "last_analysis_stats", "reputation", "tags")}

    blob = " ".join(str(x) for x in (result["reverse_dns"], (info or {}).get("org"),
                                     result["rdap"].get("name"), result["rdap"].get("entities"))).lower()
    privacy = (info or {}).get("privacy") or {}
    asn_type = ((info or {}).get("asn") or {}).get("type")
    kind = "unknown"
    if result["tor_exit"] or privacy.get("tor"):
        kind = "tor-exit"
    elif privacy.get("vpn") or privacy.get("proxy") or privacy.get("relay"):
        service = privacy.get("service")
        kind = f"vpn-or-proxy (IPinfo{': ' + service if service else ''})"
    elif privacy.get("hosting") or asn_type == "hosting":
        kind = "hosting/cloud (IPinfo)"
    elif asn_type == "isp":
        kind = "residential/mobile ISP (IPinfo)"
    elif asn_type in ("business", "education", "government"):
        kind = f"{asn_type} network (IPinfo)"
    elif any(h in blob for h in VPN_HINTS):
        kind = "vpn-or-proxy (likely)"
    elif any(h in blob for h in HOSTING_HINTS):
        kind = "hosting/cloud (likely)"
    elif any(h in blob for h in ("dsl", "cable", "dhcp", "dyn", "pool", "res", "fios", "comcast",
                                 "charter", "spectrum", "verizon", "att", "cox", "tmobile", "mobile")):
        kind = "residential/mobile ISP (likely)"
    result["network_kind_guess"] = kind
    dump(result)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1].strip())
