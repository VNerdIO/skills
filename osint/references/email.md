# Email addresses

## Reading `mail.py` output

- **`domain.kind`**:
  - `organisation/custom`: the domain itself is strong attribution. The website title,
    RDAP registration date and MX host say who runs it. A domain registered days ago
    that imitates a brand is a phishing indicator. Say so.
  - `free-webmail`: the domain says nothing. Attribution rests on the local part and
    what the address is attached to.
  - `disposable`: a throwaway address. Expect little, and say why.
- **`accepts_mail: false`**: no MX record, so the address cannot receive mail. A
  sender using it forged the address.
- **`gravatar`**: a hit is **confirmed** ownership of that profile, because Gravatar
  verifies the address. `verified_accounts` lists accounts the owner proved, which
  are confirmed links. Download the avatar and reverse-search it (below).
- **`pgp`**: keys.openpgp.org publishes only addresses the owner verified. Open the
  URL. The key's other user IDs are confirmed linked emails and names.
- **`github.commit_author_logins`**: accounts whose commits use this email. GitHub
  links a commit to an account only when the email is verified on that account, so
  this is confirmed. `profile_email_logins` matched on profile text and is only
  **possible** until checked. The script calls GitHub without auth and can hit rate
  limits. If results are empty and `gh` is installed, retry with
  `gh api "search/commits?q=author-email:<email>"`.
- **`username_pivots`**: run `username.py` on each one. A distinctive local part
  (`jsmith1987`) pivots well. A common one (`john`, `info`) doesn't, so skip it and say
  so.
- **`hibp`**: breach names show which services held the address and when, which
  proves it was in use. They never give you the passwords or breached data; do not
  look up or use leaked data dumps.

## Manual sources (free; open in the browser and cite)

| Source | Use |
| --- | --- |
| `https://haveibeenpwned.com` | Breach list (the website is free; the API needs `HIBP_KEY`) |
| `https://epieos.com` | Google account name and photo, plus linked services (free tier) |
| `https://emailrep.io/<email>` | Reputation, first-seen date, profiles, whether it sends spam |
| `https://intelx.io` | Public pastes and documents mentioning the address (free tier; selector search only) |
| `https://www.google.com/search?q="<email>"` | See [`dorks.md`](dorks.md) |
| `https://hunter.io/email-verifier/<email>` | For org domains: whether the address exists, and the org's address pattern |
| `https://whois.domaintools.com/<domain>` | Registrant history for custom domains |
| `https://web.archive.org/web/*/<domain>*` | Old versions of the domain's site, often with names and "about" pages before they were removed |

## Phishing and scam senders

When the email came in a message, ask for the full headers (in Gmail: ⋮ → Show
original). Read `Return-Path`, `Reply-To` (often the scammer's real inbox, which
differs from `From`), the `Authentication-Results` SPF/DKIM/DMARC verdicts and the
first external `Received` IP. Run `ip.py` on that IP and `mail.py` on the `Reply-To`
address. Links in the body are domains to pivot on with RDAP and VirusTotal.
