#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only Zscaler checks to run on the affected user's device. No credentials needed.
.DESCRIPTION
  Reports ZCC service state, whether internet traffic goes through Zscaler
  (ip.zscaler.com), DNS answers for an internal FQDN (100.64.0.0/10 = ZPA intercept),
  TCP reachability, TLS certificate issuer for a URL (Zscaler = SSL inspected), and
  system proxy / PAC settings. Changes nothing.
.EXAMPLE
  .\Invoke-ZccEndpointCheck.ps1
.EXAMPLE
  .\Invoke-ZccEndpointCheck.ps1 -Fqdn erp.corp.local -Port 443 -Url https://github.com
#>
[CmdletBinding()]
param(
    [string]$Fqdn,
    [int]$Port = 0,
    [string]$Url,
    [switch]$Json
)

$ErrorActionPreference = 'Continue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$onWindows = ($PSVersionTable.PSEdition -eq 'Desktop') -or ((Get-Variable IsWindows -ErrorAction SilentlyContinue) -and $IsWindows)
$onMac = (Get-Variable IsMacOS -ErrorAction SilentlyContinue) -and $IsMacOS
$report = [ordered]@{ Computer = [Environment]::MachineName; Time = (Get-Date).ToString('o') }
$findings = New-Object System.Collections.ArrayList
function Add-Finding([string]$Severity, [string]$Text) { [void]$findings.Add([pscustomobject]@{ Severity = $Severity; Finding = $Text }) }

function Test-CgnatIp([string]$ip) {
    if ($ip -notmatch '^(\d+)\.(\d+)\.\d+\.\d+$') { return $false }
    return ([int]$Matches[1] -eq 100 -and [int]$Matches[2] -ge 64 -and [int]$Matches[2] -le 127)
}

# 1. ZCC services / process
Write-Host 'Zscaler Client Connector' -ForegroundColor Cyan
if ($onWindows) {
    $svcs = @(Get-Service -Name 'ZSA*' -ErrorAction SilentlyContinue | Select-Object Name, Status, StartType)
    $report.ZccServices = $svcs
    if ($svcs.Count -eq 0) { Add-Finding 'High' 'No Zscaler (ZSA*) services found - ZCC may not be installed.' }
    foreach ($s in $svcs) {
        Write-Host "  $($s.Name): $($s.Status)"
        if ($s.Status -ne 'Running' -and $s.Name -match 'ZSAService|ZSATunnel') { Add-Finding 'High' "Service $($s.Name) is $($s.Status)." }
    }
    try {
        $ver = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
            Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName -match 'Zscaler' } | Select-Object -First 1).DisplayVersion
        if ($ver) { $report.ZccVersion = $ver; Write-Host "  Version: $ver" }
    } catch { }
}
else {
    $procs = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'Zscaler|zstunnel|ZscalerTunnel|zsaservice' } | Select-Object -ExpandProperty ProcessName -Unique)
    $report.ZccProcesses = $procs
    if ($procs.Count -eq 0) { Add-Finding 'High' 'No Zscaler processes found - ZCC may not be running.' } else { Write-Host "  Processes: $($procs -join ', ')" }
}

# 2. Is internet traffic going through Zscaler?
Write-Host 'Internet path (ip.zscaler.com)' -ForegroundColor Cyan
try {
    $page = Invoke-WebRequest -Uri 'https://ip.zscaler.com' -UseBasicParsing -TimeoutSec 15
    $text = ($page.Content -replace '<[^>]+>', ' ' -replace '&nbsp;', ' ' -replace '\s+', ' ').Trim()
    $via = $null
    if ($text -match 'not going through the Zscaler') { $via = $false }
    elseif ($text -match 'via (the )?Zscaler|going through the Zscaler') { $via = $true }
    $report.ThroughZscaler = $via
    $snippet = ([regex]::Matches($text, '[^.]*Zscaler[^.]*\.') | Select-Object -First 3 | ForEach-Object { $_.Value.Trim() }) -join ' '
    $report.ZscalerIpPage = $snippet
    Write-Host "  $snippet"
    if ($via -eq $false) { Add-Finding 'High' 'Internet traffic is NOT going through Zscaler (ZIA). Check ZCC status, forwarding profile, trusted-network detection, or PAC/tunnel.' }
}
catch { Add-Finding 'Medium' "Could not reach ip.zscaler.com: $($_.Exception.Message)"; $report.ThroughZscaler = 'unknown' }

# 3. DNS + TCP for an internal app
if ($Fqdn) {
    Write-Host "DNS / reachability for $Fqdn" -ForegroundColor Cyan
    $ips = @()
    try { $ips = @([System.Net.Dns]::GetHostAddresses($Fqdn) | ForEach-Object { $_.IPAddressToString }) }
    catch { Add-Finding 'High' "DNS lookup for $Fqdn failed: $($_.Exception.InnerException.Message). If it's a ZPA app, ZCC isn't intercepting DNS for it (no matching segment, ZPA off, or DNS bypassing ZCC)." }
    $report.DnsAnswers = $ips
    if ($ips.Count) {
        Write-Host "  Resolves to: $($ips -join ', ')"
        if (@($ips | Where-Object { Test-CgnatIp $_ }).Count -gt 0) { Add-Finding 'Info' "$Fqdn resolves to 100.64.x.x - ZPA is intercepting it. Next: ZPA policy/connector checks (Test-ZpaAppAccess.ps1 or User Activity diagnostics)." }
        else { Add-Finding 'Medium' "$Fqdn resolves to a real IP ($($ips -join ', ')), so ZPA is NOT intercepting it. Either no app segment matches this name, ZPA is off in ZCC, or another DNS path is in use." }
    }
    if ($Port -gt 0 -and $ips.Count) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $ar = $client.BeginConnect($Fqdn, $Port, $null, $null)
            $ok = $ar.AsyncWaitHandle.WaitOne(8000) -and $client.Connected
            $report.TcpConnect = $ok
            Write-Host "  TCP $Port`: $(if ($ok) { 'connected' } else { 'FAILED / timed out' })"
            if (-not $ok) { Add-Finding 'High' "TCP connection to $Fqdn`:$Port failed. With a 100.64 answer, look at the ZPA session status code for this attempt." }
        }
        catch { $report.TcpConnect = $false; Add-Finding 'High' "TCP connection to $Fqdn`:$Port failed: $($_.Exception.Message)" }
        finally { $client.Close() }
    }
}

# 4. TLS certificate issuer
if ($Url) {
    Write-Host "TLS certificate for $Url" -ForegroundColor Cyan
    $u = [uri]$(if ($Url -match '^[a-z]+://') { $Url } else { "https://$Url" })
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $tcp.Connect($u.Host, $(if ($u.Port -gt 0) { $u.Port } else { 443 }))
        $script:certValidationErrors = 'None'
        $cb = [System.Net.Security.RemoteCertificateValidationCallback] { param($s, $c, $ch, $e) $script:certValidationErrors = [string]$e; return $true }
        # The callback only records validation errors so we can report them; nothing is sent over this connection.
        $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $cb)
        $ssl.AuthenticateAsClient($u.Host)
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
        $report.CertSubject = $cert.Subject; $report.CertIssuer = $cert.Issuer; $report.CertValidation = $script:certValidationErrors
        Write-Host "  Issuer: $($cert.Issuer)"
        Write-Host "  Trust check: $($script:certValidationErrors)"
        $ssl.Dispose()
        if ($cert.Issuer -match 'Zscaler') { Add-Finding 'Info' "$($u.Host) is SSL-inspected by Zscaler (issuer: $($cert.Issuer)). Apps with their own trust store or cert pinning may fail; see the ZIA playbook." }
        if ($script:certValidationErrors -ne 'None') { Add-Finding 'High' "This device does not trust the certificate for $($u.Host) ($($script:certValidationErrors)). If the issuer is Zscaler or your company CA, the root CA isn't installed in this device's trust store." }
    }
    catch { Add-Finding 'Medium' "TLS check for $($u.Host) failed: $($_.Exception.Message)" }
    finally { $tcp.Close() }
}

# 5. Proxy / PAC settings
Write-Host 'Proxy settings' -ForegroundColor Cyan
if ($onWindows) {
    try {
        $ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction Stop
        $report.UserProxy = [ordered]@{
            ProxyEnable = if ($ie.PSObject.Properties['ProxyEnable']) { $ie.ProxyEnable } else { 0 }
            ProxyServer = if ($ie.PSObject.Properties['ProxyServer']) { $ie.ProxyServer } else { $null }
            AutoConfigURL = if ($ie.PSObject.Properties['AutoConfigURL']) { $ie.AutoConfigURL } else { $null }
        }
        Write-Host "  User proxy enabled: $($report.UserProxy.ProxyEnable)  server: $($report.UserProxy.ProxyServer)  PAC: $($report.UserProxy.AutoConfigURL)"
    } catch { }
    try { $wh = (& netsh winhttp show proxy) -join ' '; $report.WinHttpProxy = ($wh -replace '\s+', ' ').Trim(); Write-Host "  WinHTTP: $($report.WinHttpProxy)" } catch { }
}
elseif ($onMac) {
    try { $p = (& scutil --proxy) -join "`n"; $report.SystemProxy = $p; Write-Host ($p -split "`n" | Where-Object { $_ -match 'Enable|Proxy |URL' } | ForEach-Object { "  $($_.Trim())" }) -Separator "`n" } catch { }
}
foreach ($v in 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY') {
    $val = [Environment]::GetEnvironmentVariable($v)
    if ($val) { $report["Env_$v"] = $val; Write-Host "  `$env:$v = $val" }
}

# 6. Clock (SAML depends on it)
$report.LocalTimeUtc = [DateTime]::UtcNow.ToString('o')

$report.Findings = $findings.ToArray()
if ($Json) { $report | ConvertTo-Json -Depth 5; return }

Write-Host ''
Write-Host 'Findings:' -ForegroundColor Cyan
if ($findings.Count -eq 0) { Write-Host '  No problems detected by these checks.' }
foreach ($f in $findings) {
    $col = switch ($f.Severity) { 'High' { 'Red' } 'Medium' { 'Yellow' } default { 'Gray' } }
    Write-Host "  [$($f.Severity)] $($f.Finding)" -ForegroundColor $col
}
