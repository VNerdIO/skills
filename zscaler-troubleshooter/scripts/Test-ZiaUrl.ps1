#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only check of how ZIA classifies and treats a URL.
.DESCRIPTION
  Looks up the URL's categories, then lists URL filtering and SSL inspection rules that
  target those categories (in evaluation order), custom categories containing the URL,
  allow/deny list and auth-exemption hits, and whether changes are pending activation.
  Uses GET requests plus ZIA's read-only urlLookup POST.
.EXAMPLE
  .\Test-ZiaUrl.ps1 -Url https://app.example.com/login
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Url,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ZscalerApi.psm1') -Force

$noScheme = ($Url -replace '^[a-zA-Z][a-zA-Z0-9+.-]*://', '').TrimEnd('/')
$hostName = (($noScheme -split '[/:?#]')[0]).ToLowerInvariant()

function Test-UrlEntry([string]$entry) {
    # ZIA list entries: "site.com", ".site.com" (site + subdomains), "site.com/path"
    $e = ($entry -replace '^[a-zA-Z]+://', '').Trim().ToLowerInvariant().TrimEnd('/')
    if (-not $e) { return $false }
    $eHost = ($e -split '[/:]')[0]
    $ePath = if ($e.Length -gt $eHost.Length) { $e.Substring($eHost.Length) } else { '' }
    $hostOk = if ($eHost.StartsWith('.')) { $hostName -eq $eHost.Substring(1) -or $hostName.EndsWith($eHost) } else { $hostName -eq $eHost }
    if (-not $hostOk) { return $false }
    if ($ePath) { return $noScheme.ToLowerInvariant().Substring($hostName.Length).StartsWith($ePath) }
    return $true
}

function Try-Read([string]$Path, [string]$Label) {
    try { return Invoke-ZsRead -Product ZIA -Path $Path }
    catch { Write-Host "  (skipped $Label`: $($_.Exception.Message))" -ForegroundColor DarkGray; return $null }
}

function Get-Names($list) {
    @(@($list) | Where-Object { $_ } | ForEach-Object { Get-ZsProp $_ @('name') (Get-ZsProp $_ @('id')) }) -join ', '
}

try {
    Write-Host "ZIA check for $noScheme (auth: $(Get-ZsAuthMode))" -ForegroundColor Cyan
    Assert-ZsCredentials -Product ZIA
    $findings = New-Object System.Collections.ArrayList
    function Add-Finding([string]$Severity, [string]$Text) { [void]$findings.Add([pscustomobject]@{ Severity = $Severity; Finding = $Text }) }

    # Categories
    $lookup = @(Invoke-ZsRead -Product ZIA -Path 'urlLookup' -Method POST -Body @($noScheme))
    $cats = @(); $secCats = @()
    if ($lookup.Count -gt 0) {
        $cats = @(Get-ZsProp $lookup[0] @('urlClassifications') @())
        $secCats = @(Get-ZsProp $lookup[0] @('urlClassificationsWithSecurityAlert') @())
    }
    if ($secCats.Count -gt 0) { Add-Finding 'High' "Zscaler flags this URL with a security classification: $($secCats -join ', '). Blocks here are threat protection, not URL filtering." }

    # Custom categories containing the URL
    $customHits = @()
    $custom = Try-Read 'urlCategories?customOnly=true' 'custom categories'
    if (-not $custom) {
        try { $custom = Invoke-ZsRead -Product ZIA -Path 'urlCategories' -Query @{ customOnly = 'true' } } catch { }
    }
    foreach ($c in @($custom)) {
        if (-not $c) { continue }
        $entries = @(Get-ZsProp $c @('urls') @()) + @(Get-ZsProp $c @('dbCategorizedUrls') @())
        $hit = @($entries | Where-Object { Test-UrlEntry ([string]$_) })
        if ($hit.Count -gt 0) {
            $cid = [string](Get-ZsProp $c @('id'))
            $customHits += [pscustomobject]@{ Id = $cid; Name = Get-ZsProp $c @('configuredName', 'name') $cid; Entries = ($hit -join ', ') }
            if ($cats -notcontains $cid) { $cats += $cid }
        }
    }

    Write-Host "  Categories: $(if ($cats) { $cats -join ', ' } else { '(none returned)' })"

    # URL filtering rules
    $urlRules = @(Try-Read 'urlFilteringRules' 'URL filtering rules')
    $matchingUrlRules = @($urlRules | Where-Object { $_ } | ForEach-Object {
        $rc = @(Get-ZsProp $_ @('urlCategories') @())
        $any = ($rc.Count -eq 0) -or ($rc -contains 'ANY')
        $hit = @($rc | Where-Object { $cats -contains $_ })
        if ($any -or $hit.Count -gt 0) {
            [pscustomobject]@{
                Order = [int](Get-ZsProp $_ @('order') 0)
                Name = Get-ZsProp $_ @('name')
                State = Get-ZsProp $_ @('state') 'ENABLED'
                Action = Get-ZsProp $_ @('action')
                MatchedOn = if ($hit.Count -gt 0) { $hit -join ', ' } else { 'any category' }
                Users = Get-Names (Get-ZsProp $_ @('users'))
                Groups = Get-Names (Get-ZsProp $_ @('groups'))
                Departments = Get-Names (Get-ZsProp $_ @('departments'))
                Locations = Get-Names (Get-ZsProp $_ @('locations'))
            }
        }
    } | Sort-Object Order)

    $firstEnabled = $matchingUrlRules | Where-Object { $_.State -ne 'DISABLED' } | Select-Object -First 1
    if ($firstEnabled -and $firstEnabled.Action -match 'BLOCK') {
        Add-Finding 'High' "First enabled URL filtering rule for these categories is '$($firstEnabled.Name)' (order $($firstEnabled.Order)) with action $($firstEnabled.Action). Check whether its user/group/location criteria include the affected user."
    }
    elseif ($firstEnabled -and $firstEnabled.Action -match 'CAUTION|ISOLATE') {
        Add-Finding 'Medium' "First enabled matching rule '$($firstEnabled.Name)' uses $($firstEnabled.Action); users see a warning or isolation page, not a hard block."
    }

    # SSL inspection rules (newer tenants)
    $sslRules = @(Try-Read 'sslInspectionRules' 'SSL inspection rules')
    $matchingSsl = @($sslRules | Where-Object { $_ } | ForEach-Object {
        $rc = @(Get-ZsProp $_ @('urlCategories') @())
        $hit = @($rc | Where-Object { $cats -contains $_ })
        if ($hit.Count -gt 0) {
            $act = Get-ZsProp $_ @('action')
            $actType = if ($act -and $act.PSObject.Properties['type']) { $act.type } else { [string]$act }
            [pscustomobject]@{ Order = [int](Get-ZsProp $_ @('order') 0); Name = Get-ZsProp $_ @('name'); State = Get-ZsProp $_ @('state'); Action = $actType; MatchedOn = $hit -join ', ' }
        }
    } | Sort-Object Order)

    # Allow / deny lists and auth exemptions
    $allow = Try-Read 'security' 'security allowlist'
    $deny = Try-Read 'security/advanced' 'security denylist'
    $exempt = Try-Read 'authSettings/exemptedUrls' 'auth exemptions'
    $allowHits = @(@(Get-ZsProp $allow @('whitelistUrls') @()) | Where-Object { Test-UrlEntry ([string]$_) })
    $denyHits = @(@(Get-ZsProp $deny @('blacklistUrls') @()) | Where-Object { Test-UrlEntry ([string]$_) })
    $exemptHits = @(@(Get-ZsProp $exempt @('urls') @()) | Where-Object { Test-UrlEntry ([string]$_) })
    if ($denyHits.Count -gt 0) { Add-Finding 'High' "URL is on the global security denylist: $($denyHits -join ', ')." }
    if ($allowHits.Count -gt 0) { Add-Finding 'Info' "URL is on the global security allowlist (bypasses threat checks, not URL filtering): $($allowHits -join ', ')." }
    if ($exemptHits.Count -gt 0) { Add-Finding 'Info' "URL is exempt from authentication: $($exemptHits -join ', ')." }

    # Pending activation
    $status = Try-Read 'status' 'activation status'
    $statusValue = [string](Get-ZsProp $status @('status'))
    if ($statusValue -and $statusValue -ne 'ACTIVE') { Add-Finding 'Medium' "ZIA configuration status is '$statusValue' - saved changes are not live until activated." }

    if ($findings.Count -eq 0) { Add-Finding 'Info' 'No blocking rule or list entry found for this URL. If users still see a block, get the block page text (it names the policy), and check Cloud App Control, File Type Control and firewall rules.' }

    $result = [ordered]@{
        Url = $noScheme; Categories = $cats; SecurityCategories = $secCats
        CustomCategoryHits = $customHits; UrlFilteringRules = $matchingUrlRules
        SslInspectionRules = $matchingSsl; ActivationStatus = $statusValue
        Findings = $findings.ToArray()
    }
    if ($Json) { $result | ConvertTo-Json -Depth 6; return }

    if ($customHits.Count) { Write-Host "  Custom categories containing it: $(($customHits | ForEach-Object { "$($_.Name) [$($_.Entries)]" }) -join '; ')" }
    Write-Host ''
    Write-Host 'URL filtering rules for these categories (top-down, first match wins):' -ForegroundColor Yellow
    if ($matchingUrlRules.Count -eq 0) { Write-Host '  (none)' }
    foreach ($r in $matchingUrlRules) {
        $col = if ($r.State -eq 'DISABLED') { 'DarkGray' } elseif ($r.Action -match 'BLOCK') { 'Red' } elseif ($r.Action -match 'ALLOW') { 'Green' } else { 'Yellow' }
        Write-Host ("  [{0}] {1} - {2} ({3}) on {4}" -f $r.Order, $r.Name, $r.Action, $r.State, $r.MatchedOn) -ForegroundColor $col
        $who = @(); foreach ($k in 'Users', 'Groups', 'Departments', 'Locations') { if ($r.$k) { $who += "$k`: $($r.$k)" } }
        Write-Host "      $(if ($who) { $who -join ' | ' } else { 'applies to everyone' })" -ForegroundColor DarkGray
    }
    if ($matchingSsl.Count) {
        Write-Host ''
        Write-Host 'SSL inspection rules for these categories:' -ForegroundColor Yellow
        foreach ($r in $matchingSsl) { Write-Host ("  [{0}] {1} - {2} ({3}) on {4}" -f $r.Order, $r.Name, $r.Action, $r.State, $r.MatchedOn) }
    }
    Write-Host ''
    Write-Host 'Findings:' -ForegroundColor Cyan
    foreach ($f in $result.Findings) {
        $col = switch ($f.Severity) { 'High' { 'Red' } 'Medium' { 'Yellow' } default { 'Gray' } }
        Write-Host "  [$($f.Severity)] $($f.Finding)" -ForegroundColor $col
    }
}
finally { Disconnect-Zscaler }
