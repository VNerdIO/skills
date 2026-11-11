# Zscaler Client Connector (ZCC) Playbook

## Start with the endpoint check

Have the user (or a remote session) run on the affected device:

```powershell
.\scripts\Invoke-ZccEndpointCheck.ps1 -Fqdn app.corp.local -Port 443 -Url https://example.com
```

It needs no credentials and changes nothing. It reports ZCC service state, whether
internet traffic goes through Zscaler, DNS answers (100.64.x.x = ZPA intercept), TCP
reachability, TLS cert issuer, and system proxy/PAC settings.

## ZCC status meanings

| ZCC shows | Meaning | Next step |
|---|---|---|
| Internet Security / Private Access **ON** | Tunnel up | Problem is policy or destination; go to ZIA/ZPA playbook |
| **Authentication required** / login loop | IdP/SAML problem or stale token | Re-authenticate; check IdP sign-in logs for the user; check user is provisioned |
| **Disabled** (by admin or user) | Service turned off by policy or a disable password | Check app profile / forwarding profile; was it disabled for a trusted network? |
| **Connection error** / **Network error** | Can't reach Zscaler cloud | Local firewall/proxy blocking Zscaler IPs, captive portal, DNS failure |
| **Captive portal detected** | Hotel/airport Wi-Fi login page | Complete the portal login; ZCC resumes |
| **Trusted network** / **Off** on corp network | Forwarding profile treats this network as trusted | Expected if office traffic is tunneled another way; otherwise check trusted network criteria |
| **Fail open** | ZCC couldn't connect and is letting traffic go direct | Find why the tunnel failed (logs) |

## Common causes

- **Another VPN or security agent** fighting ZCC for routes/DNS/packet filtering
  (legacy VPN clients, other SWG agents, some EDR network modules).
- **Third-party firewall** blocking ZCC's traffic to Zscaler.
- **Clock skew** breaking SAML assertions → check the device time.
- **Old ZCC version** with known bugs → compare against the version your app profile
  expects.
- **Tunnel mode** issues: Tunnel 2.0 (DTLS/TLS) can be blocked on some networks where
  Tunnel 1.0 works; the forwarding profile controls fallback.
- **DNS**: ZPA relies on ZCC intercepting DNS for app names. Hard-coded DNS servers,
  DoH in the browser, or another agent's DNS filter can bypass it.

## Reading ZCC logs

Ask the user to export logs from the ZCC tray app (Troubleshoot → Export Logs), then:

```powershell
.\scripts\Find-ZccLogErrors.ps1 -Path C:\Users\me\Downloads\ZCC-logs.zip
```

It summarizes known failure patterns (tunnel, auth/SAML, DNS, SSL, captive portal, PAC,
fail-open, ZPA) with timestamps and sample lines, and the most frequent error lines.
Focus on entries near the reported failure time.

If the scanner says files look encrypted/binary, the tenant has log encryption on;
those logs have to go to Zscaler Support or be viewed with Zscaler's tooling.

## Escalating to Zscaler Support

Include: user, device OS + ZCC version, time of failure with time zone, ZPA status code
or ZIA block details, `ip.zscaler.com` output, and the exported ZCC log bundle.
