---
name: zscaler-troubleshooter
description: Diagnose Zscaler problems (ZPA private app access, ZIA web/SSL blocks, Client Connector tunnel and auth issues) with read-only checks. Use for "can't reach app over ZPA", "site blocked by Zscaler", "ZCC won't connect", ZPA status codes, or ZCC logs.
---

# Zscaler Troubleshooter

Diagnose Zscaler issues the way a senior Zscaler engineer would: classify the problem,
collect the few facts that matter, run read-only checks, then name the most likely cause
with evidence and the exact fix for a human to make.

## Ground rules

- **Read-only.** Never create, change, delete or activate anything in Zscaler. The scripts
  only send GET requests (plus ZIA `urlLookup`, which only reads). If a fix is needed,
  describe it; the admin makes it in the portal.
- **Never print secrets.** Credentials come from environment variables only. Don't echo
  them, write them to files or put them on a command line.
- **Never disable TLS verification.** If API calls fail certificate checks because the
  machine itself sits behind Zscaler SSL inspection, trust the company root CA instead
  (see `references/api-reference.md`).
- **Evidence over guesses.** Every conclusion cites what was observed (a status code, a
  rule, a connector state, a DNS answer). If something can't be checked, say so.

## Step 1 — Classify the problem

| Symptom | Product | Playbook |
|---|---|---|
| Internal app / server / RDP / SSH / file share unreachable | ZPA | `references/zpa-playbook.md` |
| ZPA status code (`BRK_MT_…`, `AST_MT_…`, `CLT_…`) | ZPA | `references/zpa-playbook.md` |
| Website blocked, wrong category, block page, cert error, app breaks only on Zscaler | ZIA | `references/zia-playbook.md` |
| ZCC shows error / "Disabled" / "Connection error", login loops, slow everything, captive portal | ZCC | `references/zcc-playbook.md` |
| Unsure | Start with ZCC basics, then branch | `references/zcc-playbook.md` |

Quick discriminators:
- Resolve the hostname on the affected device. A `100.64.x.x` answer means ZPA is
  intercepting it (ZPA problem). A real internal IP means ZPA isn't handling it (it's
  going direct/VPN, or the app segment doesn't match).
- Internet site + cert issued by "Zscaler" = SSL inspection is in play.
- One user broken vs. everyone broken: one user → identity, posture, device, ZCC. Everyone
  → policy change, connector outage, segment config, or a Zscaler cloud incident
  (check trust.zscaler.com).

## Step 2 — Collect the facts (ask only for what's missing)

- User (UPN), device OS, ZCC version, and the time it failed (with time zone)
- Exact FQDN or URL, port, protocol
- Exact error text, block page text or ZPA status code (screenshot is fine)
- Scope: one user, a group, a site, everyone? Did it ever work? What changed?

## Step 3 — Run checks

Scripts are in `scripts/` next to this file (PowerShell 5.1 or 7, Windows/macOS/Linux).
Load the API module first; all API scripts import it automatically.

| Script | Runs where | What it does |
|---|---|---|
| `Test-ZpaAppAccess.ps1 -Fqdn app.corp.local -Port 443` | Admin machine with API creds | Finds the matching app segment(s), checks port coverage, segment group, server groups → connector groups → connector health, and lists the access rules that reference it in order |
| `Get-ZpaConnectorHealth.ps1` | Admin machine | Flags disconnected, disabled, outdated or upgrade-stuck connectors and groups with no healthy connector |
| `Test-ZiaUrl.ps1 -Url https://site.com` | Admin machine | Category lookup, pending-activation check, URL filtering rules hitting those categories, custom categories containing the URL, SSL inspection rules, allow/deny lists |
| `Invoke-ZccEndpointCheck.ps1 [-Fqdn x] [-Port n] [-Url y]` | The affected user's device (no creds needed) | ZCC services, whether traffic goes through Zscaler, DNS (100.64 check), TCP reachability, TLS cert issuer, system proxy/PAC |
| `Find-ZccLogErrors.ps1 -Path <zip or folder>` | Anywhere | Scans exported ZCC logs for known failure patterns and summarizes them |

Before API scripts: check credentials are present (`references/api-reference.md` lists the
variables for OneAPI and legacy auth). If they're missing, tell the user which variables
to set and continue with the manual portal checks from the playbook instead of stopping.

Use `-Json` on API scripts when you want machine-readable output to reason over.

If a script errors, read the message: 401/403 usually means a missing API scope or wrong
auth mode; a TLS error usually means the local Zscaler root CA isn't trusted.

## Step 4 — Report

Use this structure, kept short:

1. **Most likely cause** — one sentence.
2. **Evidence** — the specific observations that support it.
3. **Fix** — what to change, where in the portal, and the blast radius (who else it affects).
   Prefer the narrowest fix (a scoped rule or exception, not widening an allow-all).
4. **Verify** — how the user confirms it's fixed (e.g. retry, new status code in
   User Activity diagnostics, `ip.zscaler.com`).
5. **If that's not it** — the next one or two things to check.

If the evidence doesn't support a single cause, say what's ruled out and what single
piece of information would decide it.

## Reference files

- `references/zpa-playbook.md` — ZPA decision tree and session status codes
- `references/zia-playbook.md` — ZIA blocks, categories, SSL inspection, auth
- `references/zcc-playbook.md` — Client Connector states, logs, endpoint checks
- `references/api-reference.md` — auth modes, environment variables, endpoints
