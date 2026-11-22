# IP addresses

An IP address identifies a **network**, not a person. Public sources name the
organisation that holds the block, roughly where it routes, and what it runs. The
individual behind a residential or mobile IP is known only to the ISP, which releases
it under subpoena or court order. State that limit in the report instead of guessing.

## Reading `ip.py` output

- **`rdap`**: the registry record (ARIN, RIPE, APNIC, LACNIC or AFRINIC, chosen by
  rdap.org). `entities` with role `registrant` is the block holder. Role `abuse` is
  where complaints go. A small reassigned block (a `/29`, or type `REASSIGNED`) can
  name the actual business customer. That is often the best attribution available.
- **`reverse_dns`**: hostnames such as `pool-…-dsl…` or `…res.spectrum.com` mean
  residential. `mail.company.com` or `vpn.company.com` names the organisation that
  runs it.
- **`ipinfo`**: ASN and org, plus city-level geolocation. Geolocation is approximate
  (often the ISP's regional hub) and wrong for VPNs and mobile carriers. Report it as
  "routes via", never "located at". With `IPINFO_TOKEN` set, `authenticated` is true.
  On a free token the fields are the same as without one, with higher rate limits.
  Paid plans add `privacy` (`vpn`, `proxy`, `tor`, `relay`, `hosting`, and `service`,
  which names the VPN provider), `asn.type` (`isp`, `hosting`, `business`,
  `education`), `company` (the organisation using the range, which can be more
  specific than the ASN) and `abuse`. `network_kind_guess` uses these flags when they
  are present and marks its answer "(IPinfo)". Without them, it falls back to keyword
  hints and marks the answer "(likely)". An `error` value usually means a bad token
  or an exhausted quota.
- **`shodan_internetdb`**: open ports, hostnames, CPEs and known CVEs from Shodan's
  last scan. Hostnames here often reveal the domain served from the IP, which you can
  pivot on.
- **`tor_exit`** / **`network_kind_guess`**: for Tor, VPN or hosting results, the
  attribution stops at "an anonymising service or a rented server". The provider's
  abuse contact is the next step.

## Manual sources (free; open in the browser and cite)

| Source | Use |
| --- | --- |
| `https://bgp.he.net/ip/<ip>` | ASN, prefix, peers, and other prefixes the same org announces |
| `https://stat.ripe.net/<ip>` | Routing history: when the prefix moved between orgs |
| `https://www.abuseipdb.com/check/<ip>` | Community abuse reports, ISP, usage type (free account for API: `ABUSEIPDB_KEY`) |
| `https://viz.greynoise.io/ip/<ip>` | Mass scanner or benign crawler (community key: `GREYNOISE_KEY`) |
| `https://www.virustotal.com/gui/ip-address/<ip>` | Malware verdicts, passive DNS (domains that resolved here) (`VT_KEY`) |
| `https://search.censys.io/hosts/<ip>` | TLS certificates; their subject/SAN names the domains and sometimes the org |
| `https://securitytrails.com/list/ip/<ip>` | Domains hosted on the IP (free account) |
| `https://www.shodan.io/host/<ip>` | Full banners when InternetDB is thin (free account) |
| `https://talosintelligence.com/reputation_center/lookup?search=<ip>` | Email/web reputation, owner |
| `https://mxtoolbox.com/SuperTool.aspx?action=blacklist%3a<ip>` | Spam blocklists |

Passive DNS and TLS certificates usually advance attribution most for a server IP:
they turn the IP into domains, and domains have registrants, websites and owners.
Pivot on those domains with RDAP (`https://rdap.org/domain/<domain>`) and the dorks.

## Where the IP came from

Context changes what the IP can tell you. Ask if it isn't clear.

- **Email headers**: the first external `Received:` hop is the sender's mail server or
  webmail provider. Gmail, Outlook and others strip the client IP, so the IP names the
  provider, not the sender.
- **Web or auth logs**: pair the IP with timestamps and user agent, and check whether
  other logins share it.
- **Abuse report or scan**: GreyNoise and AbuseIPDB tell you whether it is a known
  mass scanner, which is rarely worth attributing further.
