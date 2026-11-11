# ZIA Playbook

## First, confirm the traffic is actually going through ZIA

On the affected device, open `https://ip.zscaler.com` (or run
`Invoke-ZccEndpointCheck.ps1`). It reports whether the request came through Zscaler and
which data center. If it's not going through Zscaler, the problem is forwarding (ZCC,
PAC, GRE/IPsec tunnel), not ZIA policy.

## Classify the failure

| What the user sees | Likely area |
|---|---|
| Zscaler block page naming a category or rule | URL filtering / Cloud App Control |
| Block page mentioning a file type, malware, sandbox | File type control / ATP / Sandbox |
| Browser cert warning, or app says "can't connect / untrusted" | SSL inspection |
| Repeated login prompt or "authentication required" page | ZIA authentication / IdP |
| Page loads but parts broken; app works off-network | SSL inspection breaking pinning, or blocked dependency domain |
| Site slow or times out, no block page | Forwarding, DNS, or the destination itself |

## URL filtering / wrong category

1. Run `Test-ZiaUrl.ps1 -Url <url>`. It returns the URL's categories, rules that target
   those categories (in order, with action), and any custom category containing the URL.
2. Rules evaluate top-down; first match wins. A higher-order block on a broad category
   (e.g. a "Miscellaneous or Unknown" rule) is a common culprit.
3. Wrong category → the narrowest fix is adding the URL to a custom category used by an
   allow rule, or submitting a recategorization request to Zscaler. Avoid unblocking the
   whole category.
4. If the script reports **pending activation**, a change was saved but not activated —
   it isn't live yet.

## SSL inspection problems

Symptoms: certificate errors, apps that pin certificates (many desktop apps, mobile
apps, dev tools like git/npm/pip/Docker/Python) failing only on Zscaler.

1. Check the cert issuer on the device (`Invoke-ZccEndpointCheck.ps1 -Url <url>`). Issuer
   containing "Zscaler" (or your company's intermediate) = inspected.
2. Browser errors on every site → the Zscaler/company root CA isn't in the device's trust
   store (deployment problem, often new or non-domain devices).
3. One app/tool fails, browsers fine → the app uses its own trust store or pins certs.
   Fix options, narrowest first:
   - Point the tool at the company CA bundle (e.g. `NODE_EXTRA_CA_CERTS`,
     `REQUESTS_CA_BUNDLE`, `git config http.sslCAInfo`, Java keystore).
   - Add the app's domains to an SSL inspection **Do Not Inspect** rule.
   Never recommend turning off certificate verification in the tool.
4. `Test-ZiaUrl.ps1` lists SSL inspection rules so you can see whether a do-not-inspect
   rule already exists for the domain.

## Authentication

- Login loops or auth pages in non-browser apps → the app can't do the auth flow.
  Consider adding the destination to authentication exemptions (the script lists
  existing exempted URLs) or fix the ZCC/IdP side (user not provisioned, SAML errors).
- Wrong policy applied to a user → user/group/department not synced (SCIM) or the user
  is being seen as a location's default (unauthenticated) user.

## Everything slow or failing for a site/office

- Check trust.zscaler.com for incidents on your cloud.
- For tunnels (GRE/IPsec) from an office, check tunnel status in the portal and the
  location's configuration; a failover to a far data center adds latency.
