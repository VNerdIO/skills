# Domains

A domain points to whoever **registered** it and whoever **runs** it, who are often
different. Since GDPR (2018), most registrars redact the registrant's name and
address, so a WHOIS lookup rarely names a person today. Attribution then rests on
what the operator left in public: DNS, the website, certificates and archived pages.
Anything after the registrar needs the registrar's or host's cooperation, which goes
through their abuse contact or legal process.

## Reading `domain.py` output

- **`registered_domain`**: the name RDAP answered for. A subdomain
  (`login.example.com`) is walked up to the registered domain. Free subdomain hosts
  such as `*.github.io`, `*.netlify.app`, `*.blogspot.com` or `*.duckdns.org` put the
  platform in RDAP, not the user. For those, the subdomain label is the selector to
  pivot on (often a username), and the platform's abuse report is the next step.
- **`rdap`**:
  - `registrant` and `registrant_redacted`: an unredacted organisation is
    **confirmed** registry data. `redacted` or a privacy service ("Domains By Proxy",
    "Withheld for Privacy") says nothing about the owner. Don't treat the proxy as the
    owner.
  - `registered` / `age_days`: a domain registered in the last 30 days that imitates a
    brand or service is a strong phishing indicator. Say so in the Answer.
  - `registrar` and `abuse`: where to report the domain. `status` with
    `clientHold` or `serverHold` means the registrar has already suspended it.
  - `nameservers`: custom nameservers (`ns1.<other-domain>`) name a related domain to
    pivot on. Cloudflare's paired names (`katelyn.ns.cloudflare.com`) are assigned per
    account, so other domains on the same pair are **possible** siblings.
- **`dns`**:
  - `mx`, `mail_host`, `spf_senders`: which mail and marketing services the operator
    pays for. No MX with an SPF of `v=spf1 -all` means the domain never sends mail.
  - `dmarc`: the `rua`/`ruf` addresses often sit on a different domain or name a
    reporting vendor, which can identify the operator or its IT provider.
  - `txt_verifications` and `txt_other`: each token proves the owner holds an account
    at that service (Google, Microsoft 365, Meta Business, Atlassian). Tokens are
    unique per account. The same token on another domain means the same account owns
    both: **likely** to confirmed. Search the token string in quotes and on
    SecurityTrails.
- **`hosting`**: the network behind each address. A shared host or CDN
  (Cloudflare, Akamai, Fastly) hides the origin server, so `ip.py` on that address
  attributes the CDN, not the operator. A dedicated or small-host IP is worth running
  through `ip.py`.
- **`website`**:
  - `title`, `description`, `site_name`, `emails`, `social_links`: what the operator
    says about itself. Emails go to `mail.py`, handles from social links to
    `username.py`.
  - `trackers`: Google Analytics (`UA-`/`G-`), Tag Manager (`GTM-`), AdSense
    (`ca-pub-`) and Meta Pixel IDs belong to one account. Another site with the same
    ID is run by the same account: **likely**, or confirmed when it is an old `UA-`
    ID with the same property number. Search the ID in quotes, on
    `https://builtwith.com/relationships/<domain>` and on
    `https://spyonweb.com/<id>`.
  - `redirects_offsite`: a redirect to another domain makes that domain the real
    destination. Run `domain.py` on it.
  - `generator`: the CMS (WordPress, Shopify). A Shopify or Wix site names that
    platform as the host and abuse contact.
- **`cert_transparency`**: every public TLS certificate for the domain and its
  subdomains. `first_issued` is a floor for when the site went live, independent of
  the registration date. Subdomains such as `vpn.`, `mail.`, `staging.` or
  `<company>-portal.` reveal the organisation's infrastructure and, sometimes, its
  real name. An organisation-validated (OV/EV) certificate names the organisation in
  its subject: open the certificate on crt.sh. The script falls back to Cert Spotter,
  which returns only recent certificates, when crt.sh is down.
- **`wayback`**: the first capture shows what the domain was before. Old "About",
  "Contact" and "Impressum" pages often name the owner before they were removed or
  the domain changed hands. A first capture years before `registered` means the
  domain lapsed and was re-registered by someone else. Treat the old owner as
  **unrelated** to the new one.
- **`virustotal`** (`VT_KEY`): vendor verdicts and categories. With the key, the
  website's relations tab also lists passive DNS and files that contacted the domain.

## Manual sources (free; open in the browser and cite)

| Source | Use |
| --- | --- |
| `https://lookup.icann.org/en/lookup?name=<domain>` | ICANN's RDAP lookup, including the registrar's own record, which can hold more than the registry's |
| `https://whois.domaintools.com/<domain>` | Current WHOIS, plus registrant history for older, pre-GDPR records (history needs an account) |
| `https://crt.sh/?q=%25.<domain>` | Full certificate history and subdomains; open a certificate to read its subject organisation |
| `https://securitytrails.com/domain/<domain>/dns` | Historical A, MX and NS records: the origin IP before a CDN was added (free account) |
| `https://web.archive.org/web/*/<domain>*` | Every archived URL; open early About, Contact, Impressum and Privacy pages |
| `https://builtwith.com/relationships/<domain>` | Other sites sharing the same analytics, ad or tag IDs |
| `https://urlscan.io/search/#domain:<domain>` | Earlier scans with screenshots, the page's requests and the IPs it contacts |
| `https://www.virustotal.com/gui/domain/<domain>` | Verdicts, passive DNS, subdomains and related files |
| `https://dnstwister.report/search/<domain>` | Lookalike domains registered against a brand, for a phishing campaign's siblings |
| `https://viewdns.info/reversewhois/?q=<registrant email or name>` | Other domains registered with the same registrant details, when they are not redacted |
| Registry or national WHOIS site | ccTLDs without RDAP (many country codes): look up the registry by TLD at `https://www.iana.org/domains/root/db` |

## Phishing and scam domains

Run `domain.py` on the link's host, not the display text. A young domain, a privacy
registrant, a brand name with extra words (`paypal-account-verify.com`) or a
look-alike character (`rnicrosoft.com`), a free certificate issued the same week and
no Wayback history together make a phishing site **likely**. The next step is the
registrar's `abuse` address, the host's abuse contact from `ip.py`, and a report to
`https://safebrowsing.google.com/safebrowsing/report_phish/`. Don't submit
credentials or interact with the site's forms. Use urlscan.io to view it safely.
