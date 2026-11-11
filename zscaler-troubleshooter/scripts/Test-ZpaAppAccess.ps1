#Requires -Version 5.1
<#
.SYNOPSIS
  Read-only check of why a ZPA application may be unreachable.
.DESCRIPTION
  Walks the ZPA chain for an FQDN/IP and port:
  app segment match -> port coverage -> segment group -> access rules -> server groups
  -> connector groups -> connector health. Makes GET requests only.
.EXAMPLE
  .\Test-ZpaAppAccess.ps1 -Fqdn erp.corp.local -Port 443
.EXAMPLE
  .\Test-ZpaAppAccess.ps1 -Fqdn 10.20.30.40 -Port 3389 -Json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Fqdn,
    [int]$Port = 0,
    [ValidateSet('TCP', 'UDP')][string]$Protocol = 'TCP',
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'ZscalerApi.psm1') -Force

function Convert-IPv4ToUInt32([string]$ip) {
    $b = ([System.Net.IPAddress]::Parse($ip)).GetAddressBytes()
    [Array]::Reverse($b)
    return [BitConverter]::ToUInt32($b, 0)
}

function Get-MatchScore([string]$target, [string]$pattern) {
    # Returns 0 for no match; higher = more specific (ZPA prefers the most specific match).
    $t = $target.ToLowerInvariant().TrimEnd('.')
    $p = $pattern.ToLowerInvariant().Trim().TrimEnd('.')
    if (-not $p) { return 0 }
    if ($t -eq $p) { return 10000 + $p.Length }
    if ($p.StartsWith('*.')) {
        $suffix = $p.Substring(1)
        if ($t.EndsWith($suffix)) { return $p.Length }
        return 0
    }
    $cidr = [regex]::Match($p, '^(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})$')
    if ($cidr.Success -and $t -match '^\d{1,3}(\.\d{1,3}){3}$') {
        $net = $cidr.Groups[1].Value
        $bits = [int]$cidr.Groups[2].Value
        if ($bits -lt 0 -or $bits -gt 32) { return 0 }
        $full = [uint64]4294967295
        $mask = if ($bits -eq 0) { [uint32]0 } else { [uint32](($full -shl (32 - $bits)) -band $full) }
        if (((Convert-IPv4ToUInt32 $t) -band $mask) -eq ((Convert-IPv4ToUInt32 $net) -band $mask)) { return 5000 + $bits }
    }
    return 0
}

function Get-PortRanges($segment, [string]$proto) {
    $ranges = @()
    $lower = $proto.ToLowerInvariant()
    $objs = Get-ZsProp $segment @("${lower}PortRange")
    if ($objs) {
        foreach ($o in @($objs)) { $ranges += , @([int](Get-ZsProp $o @('from')), [int](Get-ZsProp $o @('to'))) }
    }
    else {
        $flat = @(Get-ZsProp $segment @("${lower}PortRanges") @())
        for ($i = 0; $i + 1 -lt $flat.Count; $i += 2) { $ranges += , @([int]$flat[$i], [int]$flat[$i + 1]) }
    }
    return , $ranges
}

function Test-Enabled($obj) {
    $e = Get-ZsProp $obj @('enabled')
    if ($null -eq $e) { return $true }
    return [bool]$e -and ([string]$e -ne 'false')
}

function Format-Conditions($rule) {
    $parts = @()
    foreach ($c in @(Get-ZsProp $rule @('conditions') @())) {
        $ops = @(Get-ZsProp $c @('operands') @())
        if ($ops.Count -eq 0) { continue }
        $byType = $ops | Group-Object { Get-ZsProp $_ @('objectType') 'UNKNOWN' }
        $sub = foreach ($g in $byType) {
            $vals = $g.Group | ForEach-Object {
                $n = Get-ZsProp $_ @('name'); $l = Get-ZsProp $_ @('lhs'); $r = Get-ZsProp $_ @('rhs')
                if ($n) { $n } elseif ($l -and $l -ne 'id') { "$l=$r" } else { $r }
            }
            "$($g.Name): " + ((@($vals) | Select-Object -First 6) -join ', ')
        }
        $op = Get-ZsProp $c @('operator') 'OR'
        $parts += '(' + ($sub -join " $op ") + ')'
    }
    if ($parts.Count -eq 0) { return '(no conditions - matches everything)' }
    return ($parts -join ' AND ')
}

function Get-RuleAppRefs($rule) {
    $apps = @(); $groups = @()
    foreach ($c in @(Get-ZsProp $rule @('conditions') @())) {
        foreach ($o in @(Get-ZsProp $c @('operands') @())) {
            $t = Get-ZsProp $o @('objectType')
            $v = [string](Get-ZsProp $o @('rhs'))
            if ($t -eq 'APP') { $apps += $v }
            elseif ($t -eq 'APP_GROUP') { $groups += $v }
        }
    }
    return @{ Apps = $apps; Groups = $groups }
}

try {
    Write-Host "ZPA access check for $Fqdn$(if ($Port) { ":$Port/$Protocol" }) (auth: $(Get-ZsAuthMode))" -ForegroundColor Cyan
    Assert-ZsCredentials -Product ZPA

    Write-Host '  Fetching app segments, groups and connectors...'
    $segments   = Get-ZpaList 'application'
    $segGroups  = Get-ZpaList 'segmentGroup'
    $srvGroups  = Get-ZpaList 'serverGroup'
    $conGroups  = Get-ZpaList 'appConnectorGroup'
    $connectors = Get-ZpaList 'connector'

    $rules = @()
    try { $rules = Get-ZpaList 'policySet/rules/policyType/ACCESS_POLICY' }
    catch {
        $ps = Invoke-ZsRead -Product ZPA -Path 'policySet/global'
        $rules = @(Get-ZsProp $ps @('rules') @())
    }

    $findings = New-Object System.Collections.ArrayList
    function Add-Finding([string]$Severity, [string]$Text) {
        [void]$findings.Add([pscustomobject]@{ Severity = $Severity; Finding = $Text })
    }

    # 1. Segment match
    $segMatches = foreach ($s in $segments) {
        $best = 0; $bestPattern = $null
        foreach ($d in @(Get-ZsProp $s @('domainNames') @())) {
            $score = Get-MatchScore $Fqdn ([string]$d)
            if ($score -gt $best) { $best = $score; $bestPattern = [string]$d }
        }
        if ($best -gt 0) { [pscustomobject]@{ Segment = $s; Score = $best; Pattern = $bestPattern } }
    }
    $segMatches = @($segMatches | Sort-Object Score -Descending)

    $result = [ordered]@{
        Target = $Fqdn; Port = $Port; Protocol = $Protocol
        Segments = @(); Findings = $null
    }

    if ($segMatches.Count -eq 0) {
        Add-Finding 'High' "No app segment contains '$Fqdn' (exact, wildcard or CIDR). ZPA will not intercept it. Add it to a segment, or check whether users use a different name (short name, alias, IP)."
    }
    else {
        if ($segMatches.Count -gt 1) {
            Add-Finding 'Info' "$($segMatches.Count) segments match. ZPA uses the most specific one: '$(Get-ZsProp $segMatches[0].Segment @('name'))' via '$($segMatches[0].Pattern)'."
        }
        $rank = 0
        foreach ($m in $segMatches) {
            $rank++
            $s = $m.Segment
            $sid = [string](Get-ZsProp $s @('id'))
            $sname = Get-ZsProp $s @('name')
            $primary = ($rank -eq 1)
            $tag = if ($primary) { 'Most-specific segment' } else { 'Also matches (less specific)' }

            $segInfo = [ordered]@{ Name = $sname; Id = $sid; MatchedOn = $m.Pattern; Enabled = (Test-Enabled $s); Primary = $primary }

            if (-not (Test-Enabled $s)) { Add-Finding 'High' "$tag '$sname' is DISABLED." }

            # Ports
            if ($Port -gt 0) {
                $ranges = Get-PortRanges $s $Protocol
                $covered = @($ranges | Where-Object { $Port -ge $_[0] -and $Port -le $_[1] }).Count -gt 0
                $segInfo.PortCovered = $covered
                $segInfo.PortRanges = @($ranges | ForEach-Object { if ($_[0] -eq $_[1]) { "$($_[0])" } else { "$($_[0])-$($_[1])" } })
                if (-not $covered -and $primary) { Add-Finding 'High' "$tag '$sname' does not include $Protocol port $Port (has: $($segInfo.PortRanges -join ', '))." }
            }

            # Segment group
            $sgId = [string](Get-ZsProp $s @('segmentGroupId'))
            $sg = $segGroups | Where-Object { [string](Get-ZsProp $_ @('id')) -eq $sgId } | Select-Object -First 1
            $segInfo.SegmentGroup = Get-ZsProp $sg @('name') (Get-ZsProp $s @('segmentGroupName'))
            if ($sg -and -not (Test-Enabled $sg) -and $primary) { Add-Finding 'High' "Segment group '$($segInfo.SegmentGroup)' is DISABLED." }

            # Access rules referencing this segment or its group (or all apps)
            $applicable = foreach ($r in $rules) {
                $refs = Get-RuleAppRefs $r
                $hasAppCriteria = ($refs.Apps.Count + $refs.Groups.Count) -gt 0
                if ((-not $hasAppCriteria) -or ($refs.Apps -contains $sid) -or ($sgId -and $refs.Groups -contains $sgId)) {
                    $disabledRaw = Get-ZsProp $r @('disabled')
                    [pscustomobject]@{
                        Order = [int](Get-ZsProp $r @('ruleOrder', 'priority') 0)
                        Name = Get-ZsProp $r @('name')
                        Action = Get-ZsProp $r @('action') 'ALLOW'
                        Disabled = ($disabledRaw -eq $true -or [string]$disabledRaw -eq '1' -or [string]$disabledRaw -eq 'true')
                        Scope = if ($hasAppCriteria) { 'This app/group' } else { 'All apps' }
                        Conditions = Format-Conditions $r
                    }
                }
            }
            $applicable = @($applicable | Sort-Object Order)
            $segInfo.AccessRules = $applicable
            if ($primary) {
                $active = @($applicable | Where-Object { -not $_.Disabled })
                if (@($active | Where-Object { $_.Action -match 'ALLOW' }).Count -eq 0) {
                    Add-Finding 'High' "No enabled ALLOW access rule covers '$sname' or its segment group. Expect BRK_MT_SETUP_FAIL_NO_POLICY_FOUND."
                }
                $firstDeny = $active | Where-Object { $_.Action -notmatch 'ALLOW' } | Select-Object -First 1
                $firstAllow = $active | Where-Object { $_.Action -match 'ALLOW' } | Select-Object -First 1
                if ($firstDeny -and $firstAllow -and $firstDeny.Order -lt $firstAllow.Order) {
                    Add-Finding 'Medium' "Deny rule '$($firstDeny.Name)' (order $($firstDeny.Order)) is evaluated before allow rule '$($firstAllow.Name)' (order $($firstAllow.Order)). Users matching both are blocked."
                }
            }

            # Server groups -> connector groups -> connectors
            $chain = @()
            foreach ($sgRef in @(Get-ZsProp $s @('serverGroups') @())) {
                $sgrId = [string](Get-ZsProp $sgRef @('id'))
                $srv = $srvGroups | Where-Object { [string](Get-ZsProp $_ @('id')) -eq $sgrId } | Select-Object -First 1
                if (-not $srv) { $srv = $sgRef }
                $srvName = Get-ZsProp $srv @('name')
                if (-not (Test-Enabled $srv) -and $primary) { Add-Finding 'High' "Server group '$srvName' is DISABLED." }
                $acgRefs = @(Get-ZsProp $srv @('appConnectorGroups') @())
                if ($acgRefs.Count -eq 0 -and $primary) { Add-Finding 'High' "Server group '$srvName' has no app connector groups." }
                foreach ($acgRef in $acgRefs) {
                    $acgId = [string](Get-ZsProp $acgRef @('id'))
                    $acg = $conGroups | Where-Object { [string](Get-ZsProp $_ @('id')) -eq $acgId } | Select-Object -First 1
                    if (-not $acg) { $acg = $acgRef }
                    $acgName = Get-ZsProp $acg @('name')
                    $members = @($connectors | Where-Object { [string](Get-ZsProp $_ @('appConnectorGroupId')) -eq $acgId })
                    if ($members.Count -eq 0) {
                        $ids = @(Get-ZsProp $acg @('connectors') @()) | ForEach-Object { [string](Get-ZsProp $_ @('id')) }
                        $members = @($connectors | Where-Object { $ids -contains [string](Get-ZsProp $_ @('id')) })
                    }
                    $conInfo = foreach ($c in $members) {
                        $status = [string](Get-ZsProp $c @('controlChannelStatus', 'runtimeStatus') 'UNKNOWN')
                        $healthy = (Test-Enabled $c) -and ($status -match 'AUTHENTICATED' -or $status -match '^UP$|CONNECTED')
                        [pscustomobject]@{
                            Name = Get-ZsProp $c @('name'); Enabled = (Test-Enabled $c); Status = $status
                            Version = Get-ZsProp $c @('currentVersion'); Healthy = $healthy
                        }
                    }
                    $conInfo = @($conInfo)
                    $groupHealthy = @($conInfo | Where-Object { $_.Healthy }).Count
                    if ($primary -and -not (Test-Enabled $acg)) { Add-Finding 'High' "Connector group '$acgName' is DISABLED." }
                    if ($primary -and $groupHealthy -eq 0) { Add-Finding 'High' "Connector group '$acgName' has no healthy connectors ($($conInfo.Count) total)." }
                    elseif ($primary -and $groupHealthy -eq 1 -and $conInfo.Count -gt 1) { Add-Finding 'Medium' "Connector group '$acgName' has only 1 of $($conInfo.Count) connectors healthy (no redundancy)." }
                    $chain += [pscustomobject]@{ ServerGroup = $srvName; ConnectorGroup = $acgName; Connectors = $conInfo; HealthyCount = $groupHealthy }
                }
            }
            if ($primary -and @(Get-ZsProp $s @('serverGroups') @()).Count -eq 0) { Add-Finding 'High' "Segment '$sname' has no server groups." }
            $segInfo.ConnectorChain = $chain
            $result.Segments += [pscustomobject]$segInfo
        }
    }

    if (@($findings | Where-Object { $_.Severity -eq 'High' }).Count -eq 0 -and $segMatches.Count -gt 0) {
        Add-Finding 'Info' "Config chain looks intact. If it still fails, check the user's group membership against the rules above, posture, and the session status code in User Activity diagnostics; then connector-to-server DNS/firewall."
    }
    $result.Findings = $findings.ToArray()

    if ($Json) { $result | ConvertTo-Json -Depth 8; return }

    foreach ($seg in $result.Segments) {
        Write-Host ''
        Write-Host "Segment: $($seg.Name)  [matched '$($seg.MatchedOn)'$(if ($seg.Primary) { ', most specific' })]  enabled=$($seg.Enabled)  group=$($seg.SegmentGroup)" -ForegroundColor Yellow
        if ($seg.PSObject.Properties['PortRanges']) { Write-Host "  Ports ($Protocol): $($seg.PortRanges -join ', ')   covers $Port = $($seg.PortCovered)" }
        Write-Host '  Access rules (evaluated top-down, first match wins):'
        if ($seg.AccessRules.Count -eq 0) { Write-Host '    (none)' -ForegroundColor Red }
        foreach ($r in $seg.AccessRules) {
            $col = if ($r.Disabled) { 'DarkGray' } elseif ($r.Action -match 'ALLOW') { 'Green' } else { 'Red' }
            Write-Host ("    [{0}] {1} - {2}{3} ({4})" -f $r.Order, $r.Name, $r.Action, $(if ($r.Disabled) { ' (disabled)' }), $r.Scope) -ForegroundColor $col
            Write-Host "        $($r.Conditions)" -ForegroundColor DarkGray
        }
        Write-Host '  Connector path:'
        foreach ($c in $seg.ConnectorChain) {
            Write-Host "    $($c.ServerGroup) -> $($c.ConnectorGroup): $($c.HealthyCount)/$($c.Connectors.Count) healthy"
            foreach ($k in $c.Connectors) {
                $col = if ($k.Healthy) { 'Green' } else { 'Red' }
                Write-Host "      - $($k.Name)  $($k.Status)  v$($k.Version)" -ForegroundColor $col
            }
        }
    }
    Write-Host ''
    Write-Host 'Findings:' -ForegroundColor Cyan
    foreach ($f in $result.Findings) {
        $col = switch ($f.Severity) { 'High' { 'Red' } 'Medium' { 'Yellow' } default { 'Gray' } }
        Write-Host "  [$($f.Severity)] $($f.Finding)" -ForegroundColor $col
    }
}
finally { Disconnect-Zscaler }
