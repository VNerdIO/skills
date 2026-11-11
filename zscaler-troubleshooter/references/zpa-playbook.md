# ZPA Playbook

ZPA access works only when every link in this chain holds. Walk it in order and stop at
the first broken link:

```
User/ZCC (ZPA tunnel on, authenticated)
  → App segment matches FQDN + port (and is enabled; segment group enabled)
    → Access policy: first matching rule is ALLOW (user/group/posture/client type)
      → Server group (enabled) → App connector group (enabled)
        → At least one healthy connector in that group
          → Connector can resolve the FQDN and reach the server on that port
```

The fastest way to know which link broke is the **session status code** in the ZPA
portal's User Activity diagnostics for that user, FQDN and time. Ask for it first.

## Session status codes (common ones)

Prefixes: `CLT` Client Connector, `BRK`/SE Service Edge (policy), `AST`/AC App
Connector, `CA` Central Authority. For any code not listed here, look it up on Zscaler's
"Understanding ZPA Session Status Codes" help page rather than guessing.

| Code | Meaning | Where to look |
|---|---|---|
| `BRK_MT_SETUP_FAIL_NO_POLICY_FOUND` | No ALLOW rule matched, or the segment/segment group is disabled | Access policy; segment and segment group enabled flags |
| `BRK_MT_SETUP_FAIL_REJECTED_BY_POLICY` | A rule matched and its action is block/deny | The matched rule; user's SAML/SCIM groups vs. the rule's criteria |
| `BRK_MT_SETUP_FAIL_REJECTED_BY_POLICY_POSTURE_FAILED` | Device failed a posture profile on the rule | Posture profile (OS, disk encryption, EDR, cert); fix the device |
| `BRK_MT_SETUP_FAIL_SAML_EXPIRED` | Re-auth timeout reached | Timeout policy; user re-authenticates in ZCC |
| `AST_MT_SETUP_ERR_APP_NOT_FOUND` | Connector doesn't have the app in its config | Segment enabled/synced; connector group bound via server group |
| `AST_MT_SETUP_ERR_NO_DNS_TO_SERVER` | Connector can't resolve the FQDN | Connector's DNS servers / search domains |
| `AST_MT_SETUP_TIMEOUT` / connect errors | Connector resolved but couldn't connect | Firewall between connector and server, wrong port, server down |
| `AST_MT_SETUP_ERR_AST_CFG_DISABLE` / paused for upgrade | Connector disabled or upgrading | Connector state; wait or enable |

A User Activity row with **no App Connector** listed means ZPA never selected one —
it's policy or segment config, not connector health.

## Decision tree (no status code available)

1. **Is ZPA intercepting?** On the device, resolve the FQDN.
   - `100.64.x.x` → ZPA has a matching segment. Go to step 3.
   - Real IP or NXDOMAIN → no segment matched on the client side. Go to step 2.
   - Also confirm ZCC shows Private Access **ON** (not "Disabled" or "Authentication
     required"). If not, use the ZCC playbook.
2. **Segment match.** Run `Test-ZpaAppAccess.ps1 -Fqdn <fqdn> -Port <port>`.
   - No match → add the FQDN (or a wildcard) to a segment, or the user is using a short
     name / IP that isn't defined. ZPA matches what the client asks for: `app` and
     `app.corp.local` are different unless search domains are configured.
   - Match but port not covered → add the port range.
   - Most-specific match wins: an exact FQDN segment beats `*.corp.local`. A user can be
     allowed on the wildcard segment and still be blocked because a more specific
     segment exists with a stricter policy.
3. **Policy.** The script lists rules referencing the segment or its segment group, in
   rule order. Rules are evaluated top-down; the first match wins. Check:
   - Is the user actually in the IdP group the rule uses? SCIM/SAML groups only update
     after re-auth; nested groups often don't sync.
   - Posture or client-type conditions on the rule.
   - A higher-order deny rule that also matches.
4. **Connectors.** For the segment's server groups → connector groups, is there at least
   one connector that is enabled, authenticated (control channel up) and on the expected
   version? `Get-ZpaConnectorHealth.ps1` flags this across the tenant.
   - All connectors in a group down → outage for every app on that group.
5. **Connector → server.** If ZPA picked a connector and it still fails: from the
   connector's network, test DNS and TCP to the server. Firewalls, ACLs or the server
   itself are the usual cause.

## Patterns worth recognizing

- **Works on VPN / in office, fails on ZPA** → segment missing, or a split-DNS name the
  connector can't resolve.
- **Works for most, fails for one** → group membership, posture, or that user's ZCC
  (stale auth). Have them re-authenticate ZPA in ZCC.
- **Everyone broke at once** → recent policy/segment change (check the admin audit log),
  connector group outage, or Zscaler incident (trust.zscaler.com).
- **Slow, not broken** → connectors far from the server or overloaded; latency in
  connector health; consider ZDX if licensed.
- **Double-intercept** → app also matched by a ZIA rule or a VPN route; client forwarding
  profile / bypass sends it the wrong way.
