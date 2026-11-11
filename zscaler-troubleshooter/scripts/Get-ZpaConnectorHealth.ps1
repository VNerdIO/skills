#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only health summary of all ZPA App Connectors and connector groups.
.DESCRIPTION
  Flags connectors that are disabled, not authenticated, on a different version than
  expected, or stuck upgrading, and connector groups with no (or one) healthy connector.
.EXAMPLE
  .\Get-ZpaConnectorHealth.ps1
.EXAMPLE
  .\Get-ZpaConnectorHealth.ps1 -GroupName "DC1*" -Json
#>
[CmdletBinding()]
param(
    [string]$GroupName = '*',
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ZscalerApi.psm1') -Force

function Convert-ZpaTime($v) {
    if ($null -eq $v -or [string]$v -eq '' -or [string]$v -eq '0') { return $null }
    $n = 0.0
    if (-not [double]::TryParse([string]$v, [ref]$n)) { return $null }
    if ($n -gt 1e14) { $n = $n / 1e6 } elseif ($n -gt 1e11) { $n = $n / 1e3 }
    return [DateTimeOffset]::FromUnixTimeSeconds([long]$n).LocalDateTime
}

try {
    Write-Host "ZPA connector health (auth: $(Get-ZsAuthMode))" -ForegroundColor Cyan
    Assert-ZsCredentials -Product ZPA
    $groups = Get-ZpaList 'appConnectorGroup'
    $connectors = Get-ZpaList 'connector'

    $rows = foreach ($c in $connectors) {
        $enabledRaw = Get-ZsProp $c @('enabled')
        $enabled = ($null -eq $enabledRaw) -or ([string]$enabledRaw -ne 'false' -and [bool]$enabledRaw)
        $status = [string](Get-ZsProp $c @('controlChannelStatus', 'runtimeStatus') 'UNKNOWN')
        $cur = [string](Get-ZsProp $c @('currentVersion'))
        $exp = [string](Get-ZsProp $c @('expectedVersion'))
        $upg = [string](Get-ZsProp $c @('upgradeStatus'))
        $issues = @()
        if (-not $enabled) { $issues += 'disabled' }
        if ($status -notmatch 'AUTHENTICATED|^UP$|CONNECTED') { $issues += "status $status" }
        if ($exp -and $cur -and $cur -ne $exp) { $issues += "version $cur (expected $exp)" }
        if ($upg -and $upg -notmatch 'COMPLETE|NONE|^$') { $issues += "upgrade $upg" }
        [pscustomobject]@{
            Group = [string](Get-ZsProp $c @('appConnectorGroupName'))
            GroupId = [string](Get-ZsProp $c @('appConnectorGroupId'))
            Name = Get-ZsProp $c @('name')
            Healthy = ($enabled -and $status -match 'AUTHENTICATED|^UP$|CONNECTED')
            Status = $status
            Version = $cur
            PrivateIp = Get-ZsProp $c @('privateIp')
            PublicIp = Get-ZsProp $c @('publicIp')
            LastConnect = Convert-ZpaTime (Get-ZsProp $c @('lastBrokerConnectTime'))
            LastDisconnect = Convert-ZpaTime (Get-ZsProp $c @('lastBrokerDisconnectTime'))
            Issues = ($issues -join '; ')
        }
    }
    $rows = @($rows)

    # Fill missing group names from the groups list
    foreach ($r in $rows) {
        if (-not $r.Group -and $r.GroupId) {
            $g = $groups | Where-Object { [string](Get-ZsProp $_ @('id')) -eq $r.GroupId } | Select-Object -First 1
            if ($g) { $r.Group = Get-ZsProp $g @('name') }
        }
    }
    $rows = @($rows | Where-Object { $_.Group -like $GroupName -or ($GroupName -eq '*') })

    $groupSummary = foreach ($g in $groups) {
        $gname = Get-ZsProp $g @('name')
        if ($gname -notlike $GroupName) { continue }
        $gid = [string](Get-ZsProp $g @('id'))
        $members = @($rows | Where-Object { $_.GroupId -eq $gid -or ($_.Group -eq $gname) })
        $healthy = @($members | Where-Object { $_.Healthy }).Count
        $risk = if ($members.Count -eq 0) { 'EMPTY' } elseif ($healthy -eq 0) { 'DOWN' } elseif ($healthy -eq 1) { 'NO REDUNDANCY' } else { 'OK' }
        [pscustomobject]@{ Group = $gname; Enabled = Get-ZsProp $g @('enabled') $true; Connectors = $members.Count; Healthy = $healthy; Risk = $risk }
    }
    $groupSummary = @($groupSummary | Sort-Object @{ e = { @('DOWN', 'EMPTY', 'NO REDUNDANCY', 'OK').IndexOf($_.Risk) } }, Group)

    if ($Json) { [ordered]@{ Groups = $groupSummary; Connectors = $rows } | ConvertTo-Json -Depth 5; return }

    Write-Host ''
    Write-Host 'Connector groups:' -ForegroundColor Yellow
    $groupSummary | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
    $bad = @($rows | Where-Object { $_.Issues })
    Write-Host "Connectors with issues: $($bad.Count) of $($rows.Count)" -ForegroundColor Yellow
    if ($bad.Count -gt 0) {
        $bad | Sort-Object Group, Name | Format-Table Group, Name, Status, Version, LastDisconnect, Issues -AutoSize | Out-String -Width 250 | Write-Host
    }
}
finally { Disconnect-Zscaler }
