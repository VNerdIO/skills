# osint

Works out who is behind an IP address, domain, username or email from free public sources and
writes a cited report that grades every claim. See [`SKILL.md`](SKILL.md) for the
workflow and [`references/`](references/) for how to read each script's output.

The scripts need only Python 3 (standard library) and work with no account or API key.
The keys below are optional. Each one adds coverage that otherwise has to be checked by
hand in the browser.

## API keys

### Supported now

Set these as environment variables and the scripts pick them up automatically.

| Variable | Service | Used by | Cost | What it adds |
| --- | --- | --- | --- | --- |
| `HIBP_KEY` | [Have I Been Pwned](https://haveibeenpwned.com/API/Key) | `mail.py` | Paid (lowest tier is a few dollars a month) | Which data breaches an email appears in, and when. Without a key, `mail.py` skips this step. |
| `ABUSEIPDB_KEY` | [AbuseIPDB](https://www.abuseipdb.com/register) | `ip.py` | Free, 1,000 checks/day | Community abuse reports, a confidence score, and the usage type (residential, datacenter, VPN) |
| `GREYNOISE_KEY` | [GreyNoise Community](https://viz.greynoise.io/signup) | `ip.py` | Free | Whether an IP is a known mass scanner or a harmless crawler, which screens out background noise |
| `VT_KEY` | [VirusTotal](https://www.virustotal.com/gui/join-us) | `ip.py`, `domain.py` | Free, 500 checks/day at 4 per minute | Malware verdicts, plus passive DNS: the domains that have pointed at the IP |
| `IPINFO_TOKEN` | [IPinfo](https://ipinfo.io/signup) | `ip.py`, `domain.py` | Free, about 50,000 lookups/month; paid plans add more fields | Higher rate limits on the free plan. Paid plans add VPN/proxy/Tor/hosting flags with the VPN provider's name, the ASN type, the company using the range and an abuse contact, which make `network_kind_guess` more reliable. |

If you add only two, start with **HIBP** for email checks and **AbuseIPDB** for IP
investigations. GreyNoise and VirusTotal are free and take a couple of minutes to sign
up for.

### Worth adding (not supported yet)

These would need code changes in the scripts. Until then, use them by hand in the
browser.

| Service | Cost | What it would add |
| --- | --- | --- |
| [Shodan](https://account.shodan.io/register) | Free account; a low-cost lifetime membership unlocks the API | Full service banners for a server. `ip.py` uses the free InternetDB summary today. |
| [Censys](https://search.censys.io/register) | Free tier | TLS certificates on a host. Their names often identify the domain or organisation behind a server. |
| [SecurityTrails](https://securitytrails.com/app/signup) | Free tier | Domains hosted on an IP, and a domain's DNS history (the origin IP behind a CDN) |
| [urlscan.io](https://urlscan.io/user/signup) | Free | Safe scans of links from phishing emails, with screenshots and the domains they contact |
| [Hunter.io](https://hunter.io/users/sign_up) | Free tier | For company domains: whether an address exists, and the company's address format |
| GitHub token | Free | Higher rate limits for `mail.py`'s commit search, which runs without signing in today. It could reuse an existing `gh auth token`. |

Free tiers and prices change, so check each site before you sign up.

## Setting keys

Put the keys in your shell profile, never in this folder, so they can't be committed:

```bash
# ~/.zshrc
export HIBP_KEY="..."
export ABUSEIPDB_KEY="..."
export GREYNOISE_KEY="..."
export VT_KEY="..."
export IPINFO_TOKEN="..."
```

Then open a new terminal, or run `source ~/.zshrc`. A missing key is skipped, and the
script's output says which check it skipped.

## Reports

The skill writes reports as `osint-<selector>-<date>.md` in the current directory.
They can hold personal data, so keep them out of git (see the repo's `.gitignore`).
