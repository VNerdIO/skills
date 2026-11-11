#Requires -Version 5.1
<#
  ZscalerApi.psm1 - read-only helpers for the ZPA and ZIA APIs.
  Supports OneAPI (ZIdentity OAuth) and legacy per-product auth.
  Only GET requests are allowed, plus an allowlist of read-only POSTs (ZIA urlLookup).
  Credentials are read from environment variables and never printed.
#>

$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { }

$script:State = @{
    Mode        = $null
    OneApiToken = $null
    OneApiExp   = [datetime]::MinValue
    ZpaToken    = $null
    ZpaExp      = [datetime]::MinValue
    ZiaSession  = $null
}

# Read-only POST endpoints (product|path)
$script:ReadOnlyPosts = @('ZIA|urlLookup')

function Get-EnvValue([string]$Name) {
    $v = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($v)) { return $null }
    return $v.Trim()
}

function Get-ZsAuthMode {
    if ($script:State.Mode) { return $script:State.Mode }
    $forced = Get-EnvValue 'ZSCALER_AUTH'
    if ($forced) {
        if ($forced -notin @('OneAPI', 'Legacy')) { throw "ZSCALER_AUTH must be 'OneAPI' or 'Legacy'." }
        $script:State.Mode = $forced
    }
    elseif ((Get-EnvValue 'ZSCALER_CLIENT_ID') -and (Get-EnvValue 'ZSCALER_VANITY_DOMAIN')) {
        $script:State.Mode = 'OneAPI'
    }
    else {
        $script:State.Mode = 'Legacy'
    }
    return $script:State.Mode
}

function Assert-ZsCredentials {
    param([ValidateSet('ZPA', 'ZIA')][string]$Product)
    $mode = Get-ZsAuthMode
    $need = @()
    if ($mode -eq 'OneAPI') {
        $need += 'ZSCALER_CLIENT_ID', 'ZSCALER_CLIENT_SECRET', 'ZSCALER_VANITY_DOMAIN'
        if ($Product -eq 'ZPA') { $need += 'ZPA_CUSTOMER_ID' }
    }
    elseif ($Product -eq 'ZPA') { $need += 'ZPA_CLIENT_ID', 'ZPA_CLIENT_SECRET', 'ZPA_CUSTOMER_ID' }
    else { $need += 'ZIA_USERNAME', 'ZIA_PASSWORD', 'ZIA_API_KEY', 'ZIA_CLOUD' }

    $missing = @($need | Where-Object { -not (Get-EnvValue $_) })
    if ($missing.Count -gt 0) {
        throw ("Missing environment variables for $Product ($mode auth): " + ($missing -join ', ') +
            ". See references/api-reference.md.")
    }
}

function Get-HttpStatus($ErrorRecord) {
    try {
        $resp = $ErrorRecord.Exception.Response
        if ($resp) { return [int]$resp.StatusCode }
    } catch { }
    return 0
}

function Get-ErrorBody($ErrorRecord) {
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        $m = $ErrorRecord.ErrorDetails.Message
        if ($m.Length -gt 500) { $m = $m.Substring(0, 500) + '...' }
        return $m
    }
    return $ErrorRecord.Exception.Message
}

# ---------- Auth ----------

function Get-OneApiToken {
    if ($script:State.OneApiToken -and (Get-Date) -lt $script:State.OneApiExp) { return $script:State.OneApiToken }
    $vanity = Get-EnvValue 'ZSCALER_VANITY_DOMAIN'
    $url = Get-EnvValue 'ZSCALER_TOKEN_URL'
    if (-not $url) { $url = "https://$vanity.zslogin.net/oauth2/v1/token" }
    $body = @{
        grant_type    = 'client_credentials'
        client_id     = (Get-EnvValue 'ZSCALER_CLIENT_ID')
        client_secret = (Get-EnvValue 'ZSCALER_CLIENT_SECRET')
        audience      = 'https://api.zscaler.com'
    }
    try {
        $r = Invoke-RestMethod -Uri $url -Method POST -ContentType 'application/x-www-form-urlencoded' -Body $body
    }
    catch { throw "OneAPI token request failed (HTTP $(Get-HttpStatus $_)): $(Get-ErrorBody $_)" }
    $ttl = 3600
    if ($r.PSObject.Properties['expires_in'] -and $r.expires_in) { $ttl = [int]$r.expires_in }
    $script:State.OneApiToken = $r.access_token
    $script:State.OneApiExp = (Get-Date).AddSeconds([Math]::Max(60, $ttl - 60))
    return $script:State.OneApiToken
}

function Get-ZpaLegacyBase {
    switch ((Get-EnvValue 'ZPA_CLOUD')) {
        'BETA'   { return 'https://config.zpabeta.net' }
        'GOV'    { return 'https://config.zpagov.net' }
        'GOVUS'  { return 'https://config.zpagov.us' }
        'ZPATWO' { return 'https://config.zpatwo.net' }
        default  { return 'https://config.private.zscaler.com' }
    }
}

function Get-ZpaLegacyToken {
    if ($script:State.ZpaToken -and (Get-Date) -lt $script:State.ZpaExp) { return $script:State.ZpaToken }
    $body = @{ client_id = (Get-EnvValue 'ZPA_CLIENT_ID'); client_secret = (Get-EnvValue 'ZPA_CLIENT_SECRET') }
    try {
        $r = Invoke-RestMethod -Uri ((Get-ZpaLegacyBase) + '/signin') -Method POST -ContentType 'application/x-www-form-urlencoded' -Body $body
    }
    catch { throw "ZPA sign-in failed (HTTP $(Get-HttpStatus $_)): $(Get-ErrorBody $_)" }
    $script:State.ZpaToken = $r.token
    $script:State.ZpaExp = (Get-Date).AddMinutes(50)
    return $script:State.ZpaToken
}

function Get-ZiaObfuscatedKey([string]$ApiKey, [string]$Timestamp) {
    $n = $Timestamp.Substring($Timestamp.Length - 6)
    $r = ([string]([long]$n -shr 1)).PadLeft(6, '0')
    $sb = New-Object System.Text.StringBuilder
    foreach ($c in $n.ToCharArray()) { [void]$sb.Append($ApiKey[[int][string]$c]) }
    foreach ($c in $r.ToCharArray()) { [void]$sb.Append($ApiKey[[int][string]$c + 2]) }
    return $sb.ToString()
}

function Get-ZiaLegacyBase { return "https://zsapi.$(Get-EnvValue 'ZIA_CLOUD').net/api/v1" }

function Connect-ZiaLegacy {
    if ($script:State.ZiaSession) { return $script:State.ZiaSession }
    $ts = [string][long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
    $body = @{
        apiKey    = (Get-ZiaObfuscatedKey (Get-EnvValue 'ZIA_API_KEY') $ts)
        username  = (Get-EnvValue 'ZIA_USERNAME')
        password  = (Get-EnvValue 'ZIA_PASSWORD')
        timestamp = $ts
    } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod -Uri ((Get-ZiaLegacyBase) + '/authenticatedSession') -Method POST `
            -ContentType 'application/json' -Body $body -SessionVariable zs
    }
    catch { throw "ZIA sign-in failed (HTTP $(Get-HttpStatus $_)): $(Get-ErrorBody $_)" }
    $script:State.ZiaSession = $zs
    return $zs
}

function Disconnect-Zscaler {
    <# Ends a legacy ZIA session (session-only call, changes no configuration). #>
    if ($script:State.ZiaSession) {
        try { $null = Invoke-RestMethod -Uri ((Get-ZiaLegacyBase) + '/authenticatedSession') -Method DELETE -WebSession $script:State.ZiaSession } catch { }
        $script:State.ZiaSession = $null
    }
}

function Reset-ZsTokens {
    $script:State.OneApiToken = $null; $script:State.ZpaToken = $null; $script:State.ZiaSession = $null
}

# ---------- Requests ----------

function Invoke-ZsRead {
    <#
      .SYNOPSIS Read-only request to ZPA or ZIA.
      .PARAMETER Path  ZPA: path under the customer base, e.g. 'application'.
                       ZIA: path under /api/v1, e.g. 'urlFilteringRules'.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('ZPA', 'ZIA')][string]$Product,
        [Parameter(Mandatory)][string]$Path,
        [ValidateSet('GET', 'POST')][string]$Method = 'GET',
        [hashtable]$Query,
        $Body,
        [ValidateSet('v1', 'v2')][string]$ZpaVersion = 'v1'
    )
    $cleanPath = $Path.TrimStart('/')
    if ($Method -ne 'GET') {
        $key = "$Product|" + ($cleanPath -split '\?')[0]
        if ($script:ReadOnlyPosts -notcontains $key) { throw "Blocked: $Method $Product/$cleanPath is not on the read-only allowlist." }
    }
    Assert-ZsCredentials -Product $Product
    $mode = Get-ZsAuthMode

    $qs = ''
    if ($Query -and $Query.Count -gt 0) {
        $qs = '?' + (($Query.GetEnumerator() | ForEach-Object { [uri]::EscapeDataString([string]$_.Key) + '=' + [uri]::EscapeDataString([string]$_.Value) }) -join '&')
    }

    for ($attempt = 1; $attempt -le 4; $attempt++) {
        $params = @{ Method = $Method; ContentType = 'application/json' }
        if ($null -ne $Body) { $params.Body = (ConvertTo-Json -InputObject $Body -Depth 10 -Compress) }

        if ($Product -eq 'ZPA') {
            $cid = Get-EnvValue 'ZPA_CUSTOMER_ID'
            $rel = "mgmtconfig/$ZpaVersion/admin/customers/$cid/$cleanPath"
            if ($mode -eq 'OneAPI') {
                $base = Get-EnvValue 'ZSCALER_API_BASE'; if (-not $base) { $base = 'https://api.zsapi.net' }
                $params.Uri = "$base/zpa/$rel$qs"
                $params.Headers = @{ Authorization = "Bearer $(Get-OneApiToken)" }
            }
            else {
                $params.Uri = "$(Get-ZpaLegacyBase)/$rel$qs"
                $params.Headers = @{ Authorization = "Bearer $(Get-ZpaLegacyToken)" }
            }
        }
        else {
            if ($mode -eq 'OneAPI') {
                $base = Get-EnvValue 'ZSCALER_API_BASE'; if (-not $base) { $base = 'https://api.zsapi.net' }
                $params.Uri = "$base/zia/api/v1/$cleanPath$qs"
                $params.Headers = @{ Authorization = "Bearer $(Get-OneApiToken)" }
            }
            else {
                $params.Uri = "$(Get-ZiaLegacyBase)/$cleanPath$qs"
                $params.WebSession = (Connect-ZiaLegacy)
            }
        }

        try { return Invoke-RestMethod @params }
        catch {
            $code = Get-HttpStatus $_
            if ($code -eq 401 -and $attempt -eq 1) { Reset-ZsTokens; continue }
            if ($code -eq 429 -and $attempt -lt 4) { Start-Sleep -Seconds (5 * $attempt); continue }
            $err = New-Object System.Exception ("$Product $Method /$cleanPath failed (HTTP $code): $(Get-ErrorBody $_)")
            $err.Data['HttpStatus'] = $code
            throw $err
        }
    }
}

function Get-ZpaList {
    <# Returns all items from a paginated ZPA list endpoint. #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Endpoint, [ValidateSet('v1', 'v2')][string]$ZpaVersion = 'v1', [int]$PageSize = 500)
    $all = New-Object System.Collections.ArrayList
    $page = 1
    while ($true) {
        $r = Invoke-ZsRead -Product ZPA -Path $Endpoint -ZpaVersion $ZpaVersion -Query @{ page = $page; pagesize = $PageSize }
        $items = @()
        if ($r -and $r.PSObject.Properties['list'] -and $r.list) { $items = @($r.list) }
        foreach ($i in $items) { [void]$all.Add($i) }
        $totalPages = 0
        if ($r -and $r.PSObject.Properties['totalPages']) { $totalPages = [int]$r.totalPages }
        if ($items.Count -eq 0 -or ($totalPages -gt 0 -and $page -ge $totalPages) -or ($totalPages -eq 0 -and $items.Count -lt $PageSize)) { break }
        $page++
        if ($page -gt 200) { break }
    }
    return , $all.ToArray()
}

function Get-ZsProp {
    <# Safe property access for objects whose shape varies by tenant/API version. #>
    param($Object, [string[]]$Names, $Default = $null)
    if ($null -eq $Object) { return $Default }
    foreach ($n in $Names) {
        $p = $Object.PSObject.Properties[$n]
        if ($p -and $null -ne $p.Value) { return $p.Value }
    }
    return $Default
}

Export-ModuleMember -Function Get-ZsAuthMode, Assert-ZsCredentials, Invoke-ZsRead, Get-ZpaList, Get-ZsProp, Disconnect-Zscaler
