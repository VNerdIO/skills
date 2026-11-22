---
name: osint
description: Attribute an IP address, username or email address to the person or organisation behind it using free public sources (RDAP/WHOIS, Shodan InternetDB, WhatsMyName's ~700 sites, GitHub, Gravatar, PGP keyservers, Google dorks) and write a cited report with a confidence grade for every claim. Use this whenever the user wants to know who is behind an IP, handle or email: a phishing or scam sender, an abusive account, a suspicious login, a contact to verify, or their own footprint, even if they don't say "OSINT".
---

# OSINT attribution

Take one **selector** (an IP, username or email) and answer *who controls it* from
public sources, with every claim cited and graded. The answer is often an organisation
or an online persona, not a legal name. Say so plainly rather than stretching the
evidence.

Scripts live in `scripts/` next to this file. They need only the Python 3 standard
library and no API keys. Run them from that folder (`cd scripts`) so `common.py`
imports. Each prints JSON.

## 0. Scope

Ask what the lookup is for if the request doesn't say. One line is enough. Legitimate
purposes include checking your own exposure, investigating phishing, fraud, spam or
abuse aimed at the user or their organisation, verifying that a contact is who they
claim to be, and authorised security work.

The deliverable is **online attribution**: who runs the account or network, their
public persona, employer or organisation, and the other accounts they operate. Stop at
that line. Leave out home addresses, phone numbers, relatives, daily routines and
photos of a private person's home, even when you stumble on them. When the purpose
is to find, contact or confront a private person who has cut contact, or anything
that looks like stalking or harassment, decline and point to the right channel:
the platform's report button, the IP's abuse contact, or the police.

## 1. Classify and run the selector's script

| Selector | Command | Then read |
| --- | --- | --- |
| IPv4/IPv6 | `python3 ip.py 203.0.113.7` | [`references/ip.md`](references/ip.md) |
| Email | `python3 mail.py someone@example.com` | [`references/email.md`](references/email.md) |
| Username | `python3 username.py handle` then `python3 username.py --profiles handle` | [`references/username.md`](references/username.md) |

`username.py` checks about 700 sites in roughly 90 seconds. Run it in the background
while you work the other sources. Read the matching reference file before you
interpret the output. Each one lists the manual sources to check after the script.

## 2. Search Google (and others)

Run the dorks in [`references/dorks.md`](references/dorks.md) for the selector with
WebSearch. If WebSearch results are thin, use the browser (Claude in Chrome) for
google.com, bing.com and duckduckgo.com directly. Different engines index different
corners. Open every promising hit and quote the exact text that ties it to the
selector.

## 3. Pivot

Each finding yields new selectors: an email in a GitHub commit, a username in an
email's local part, a domain from a profile link, a real name on Gravatar. Run step 1
on each new selector that is **likely** or better (see grades below). Stop after two
hops from the original selector, or sooner when new hops add nothing. Track every
selector and the source that produced it, because the report needs the chain.

## 4. Correlate and grade

A username existing on a site is not evidence that the same person owns it. Common
handles are registered by thousands of strangers. Link two accounts only through
**corroboration**: at least two independent shared attributes such as the same avatar
image, a profile linking to the other account, the same real name plus location, the
same email in commits, a verified-accounts list (Gravatar, Keybase, Mastodon
`rel=me`), or matching bio text. Grade every claim:

- **Confirmed**: the subject asserts the link themselves (a profile links the other
  account, verified-account proofs, an email in their own signed commits) or registry
  data states it (RDAP owner of an IP block).
- **Likely**: two or more independent shared attributes, nothing contradicting.
- **Possible**: one shared attribute, such as the same handle on a niche site.
- **Unrelated**: contradicted by evidence (different country, creation dates, language
  or persona). List these too, so nobody re-chases them.

## 5. Report

Write `osint-<selector-slug>-<YYYY-MM-DD>.md` in the current directory (or the
user's chosen folder) with these sections:

1. **Answer.** One paragraph: who most likely controls the selector, the overall
   confidence, and the single strongest piece of evidence.
2. **Identity.** A table of claims (name, organisation, location to city level,
   persona), each with grade and source URL.
3. **Linked selectors.** Accounts, emails and domains, each with grade, source and the
   pivot that found it.
4. **Unrelated or unverified hits.** Grouped, one line each.
5. **Limits.** What public sources cannot tell (for example, a residential IP's
   subscriber is known only to the ISP and is released under legal process), and
   the next step: the abuse contact, a platform report, or a request through
   law enforcement.
6. **Sources.** Every URL consulted, with access date.

The step is done when every claim in the report carries a grade and a URL, and every
**likely** or better selector has been pivoted on or is listed as not pivoted, with a
reason. Give the user the Answer paragraph in chat with the report's full path.
