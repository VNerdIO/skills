# Zscaler API Reference (read-only use)

The scripts support two auth modes. Use **OneAPI** if your tenant has moved to
ZIdentity; otherwise use **legacy** per-product credentials. Set `ZSCALER_AUTH` to
`OneAPI` or `Legacy` to force a mode; otherwise the module picks OneAPI when
`ZSCALER_CLIENT_ID` and `ZSCALER_VANITY_DOMAIN` are set.

Give the API client **read-only** roles/scopes. The scripts never write, but least
privilege means a mistake can't either.

## OneAPI (ZIdentity)

| Variable | Description |
|---|---|
| `ZSCALER_CLIENT_ID` | API client ID from the ZIdentity admin portal |
| `ZSCALER_CLIENT_SECRET` | API client secret |
| `ZSCALER_VANITY_DOMAIN` | Just the vanity part, e.g. `acme` for `acme.zslogin.net` |
| `ZPA_CUSTOMER_ID` | ZPA tenant ID (needed for ZPA calls) |
| `ZSCALER_TOKEN_URL` | Optional override (non-production clouds) |
| `ZSCALER_API_BASE` | Optional override, default `https://api.zsapi.net` |

- Token: `POST https://<vanity>.zslogin.net/oauth2/v1/token` with form fields
  `grant_type=client_credentials`, `client_id`, `client_secret`,
  `audience=https://api.zscaler.com`.
- ZIA base: `https://api.zsapi.net/zia/api/v1`
- ZPA base: `https://api.zsapi.net/zpa/mgmtconfig/v1/admin/customers/<customerId>`
- A 401/403 usually means the API client lacks a scope on its Resources tab.
- Not available on GOV clouds; use legacy there.

## Legacy ZPA

| Variable | Description |
|---|---|
| `ZPA_CLIENT_ID` / `ZPA_CLIENT_SECRET` | ZPA API key pair |
| `ZPA_CUSTOMER_ID` | ZPA tenant ID |
| `ZPA_CLOUD` | Empty for production, or `BETA`, `GOV`, `GOVUS`, `ZPATWO` |

Base URLs: production `https://config.private.zscaler.com`, BETA
`https://config.zpabeta.net`, GOV `https://config.zpagov.net`, GOVUS
`https://config.zpagov.us`, ZPATWO `https://config.zpatwo.net`.
Auth: `POST <base>/signin` (form `client_id`, `client_secret`) → `token`.

## Legacy ZIA

| Variable | Description |
|---|---|
| `ZIA_USERNAME` / `ZIA_PASSWORD` | Admin (ideally a read-only API admin) |
| `ZIA_API_KEY` | API key from the ZIA portal |
| `ZIA_CLOUD` | e.g. `zscaler`, `zscalerone`, `zscalertwo`, `zscalerthree`, `zscloud`, `zscalerbeta`, `zscalergov`, `zscalerten` |

Base: `https://zsapi.<cloud>.net/api/v1`. Auth: `POST /authenticatedSession` with the
obfuscated API key + timestamp (the module handles this); session cookie is reused and
the session is closed when the script ends.

## Endpoints the scripts use

ZPA (relative to the customer base; paginated with `page` / `pagesize`, results in `list`):

| Path | Purpose |
|---|---|
| `application` | App segments (domains, ports, segment group, server groups) |
| `segmentGroup` | Segment groups (enabled flag) |
| `serverGroup` | Server groups → app connector groups |
| `appConnectorGroup` | Connector groups → connectors |
| `connector` | Connector status, version, last connect |
| `policySet/rules/policyType/ACCESS_POLICY` | Access policy rules (falls back to `policySet/global`) |

ZIA:

| Path | Purpose |
|---|---|
| `POST urlLookup` (body: array of URLs) | Categories for a URL (read-only) |
| `status` | Whether config changes are pending activation |
| `urlFilteringRules` | URL filtering rules |
| `urlCategories?customOnly=true` | Custom categories and their URLs |
| `sslInspectionRules` | SSL inspection rules (newer tenants) |
| `security`, `security/advanced` | Global allowlist / denylist |
| `authSettings/exemptedUrls` | URLs exempt from authentication |

## When the admin machine is itself behind Zscaler SSL inspection

API calls may fail TLS validation in tools that don't use the Windows trust store.
PowerShell on Windows uses the OS store, so if the company root CA is deployed it works.
On macOS/Linux, add the company root CA to the system trust store. Don't bypass
certificate validation.
