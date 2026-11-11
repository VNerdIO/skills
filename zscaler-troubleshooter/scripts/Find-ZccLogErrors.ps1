#Requires -Version 5.1
<#
.SYNOPSIS
  Summarize known failure patterns in exported Zscaler Client Connector logs.
.DESCRIPTION
  Accepts the exported .zip or an extracted folder. Scans text log files for tunnel,
  auth/SAML, DNS, SSL, captive portal, PAC, fail-open and ZPA patterns; reports counts,
  first/last timestamps and sample lines, plus the most frequent error lines.
  Detects encrypted/binary logs. Read-only (extracts a zip to a temp folder only).
.EXAMPLE
  .\Find-ZccLogErrors.ps1 -Path .\ZCC-Logs.zip
.EXAMPLE
  .\Find-ZccLogErrors.ps1 -Path C:\Temp\zcclogs -Since "2026-11-10 14:00" -Json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Path,
    [datetime]$Since,
    [int]$Samples = 3,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

$patterns = [ordered]@{
    'Tunnel'         = '(?i)tunnel.{0,40}(down|disconnect|fail|error|timed? ?out|retry)|(dtls|tls).{0,30}(handshake )?fail|fallback to tunnel ?1'
    'Auth / SAML'    = '(?i)saml.{0,40}(fail|error|invalid|expired)|authenticat\w*.{0,30}(fail|error|required|expired)|token.{0,20}(expired|invalid|refresh fail)|re-?auth'
    'DNS'            = '(?i)dns.{0,40}(fail|error|timeout|timed out|servfail|nxdomain|no response)'
    'SSL / Cert'     = '(?i)(certificate|cert).{0,40}(fail|error|invalid|untrusted|expired|verify)|ssl.{0,30}(error|fail)'
    'Captive portal' = '(?i)captive ?portal'
    'PAC'            = '(?i)\bpac\b.{0,40}(fail|error|download|unreachable|invalid)'
    'Fail open'      = '(?i)fail[- ]?open'
    'ZPA'            = '(?i)\bzpa\b.{0,60}(fail|error|denied|timeout|disconnect)|broker.{0,30}(fail|error|disconnect)'
    'Network change' = '(?i)network (change|changed)|interface (down|up)|trusted network'
    'Connectivity'   = '(?i)(connection|connect) (refused|reset|timed out|failed)|unreachable|no route'
    'Crash / exit'   = '(?i)\b(crash|exception|unhandled|fatal|terminated unexpectedly)\b'
}
$tsRegex = '(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})|(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})'

function Get-LineTime([string]$line) {
    $m = [regex]::Match($line, $tsRegex)
    if (-not $m.Success) { return $null }
    $d = [datetime]::MinValue
    if ([datetime]::TryParse($m.Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$d)) { return $d }
    return $null
}

function Test-LooksBinary([string]$file) {
    $fs = [IO.File]::OpenRead($file)
    try {
        $buf = New-Object byte[] 4096
        $n = $fs.Read($buf, 0, $buf.Length)
        if ($n -eq 0) { return $false }
        $bad = 0
        for ($i = 0; $i -lt $n; $i++) { $b = $buf[$i]; if (($b -lt 9) -or ($b -gt 13 -and $b -lt 32)) { $bad++ } }
        return ($bad / $n) -gt 0.10
    }
    finally { $fs.Close() }
}

# Resolve input
$resolved = (Resolve-Path -LiteralPath $Path).ProviderPath
$tempDir = $null
if ((Test-Path -LiteralPath $resolved -PathType Leaf) -and $resolved -match '\.zip$') {
    $tempDir = Join-Path ([IO.Path]::GetTempPath()) ('zcclogs_' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $resolved -DestinationPath $tempDir
    $root = $tempDir
}
elseif (Test-Path -LiteralPath $resolved -PathType Container) { $root = $resolved }
else { $root = Split-Path $resolved; }

try {
    $files = @(Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Extension -match '^\.(log|txt|out)$' -or $_.Name -match '\.log\.\d+$' })
    if ((Test-Path -LiteralPath $resolved -PathType Leaf) -and $resolved -notmatch '\.zip$') { $files = @(Get-Item -LiteralPath $resolved) }
    if ($files.Count -eq 0) { throw "No .log/.txt files found under $root." }

    $stats = @{}
    foreach ($k in $patterns.Keys) { $stats[$k] = [pscustomobject]@{ Category = $k; Count = 0; First = $null; Last = $null; Files = @{}; Samples = New-Object System.Collections.ArrayList } }
    $errorLines = @{}
    $binary = @(); $scanned = 0; $lines = 0

    foreach ($f in $files) {
        if (Test-LooksBinary $f.FullName) { $binary += $f.Name; continue }
        $scanned++
        foreach ($line in [IO.File]::ReadLines($f.FullName)) {
            $lines++
            if ($line.Length -gt 4000) { $line = $line.Substring(0, 4000) }
            $t = $null
            if ($Since) { $t = Get-LineTime $line; if ($t -and $t -lt $Since) { continue } }
            foreach ($k in $patterns.Keys) {
                if ($line -match $patterns[$k]) {
                    if (-not $t) { $t = Get-LineTime $line }
                    $s = $stats[$k]; $s.Count++
                    $s.Files[$f.Name] = $true
                    if ($t) { if (-not $s.First -or $t -lt $s.First) { $s.First = $t }; if (-not $s.Last -or $t -gt $s.Last) { $s.Last = $t } }
                    if ($s.Samples.Count -lt $Samples) { [void]$s.Samples.Add("[$($f.Name)] $($line.Trim())") }
                }
            }
            if ($line -match '(?i)\b(error|fail(ed|ure)?|err)\b') {
                # Normalize numbers/hex/ids so repeated messages group together
                $norm = ($line -replace $tsRegex, '' -replace '0x[0-9a-fA-F]+', '<hex>' -replace '\b\d+\b', '<n>' -replace '[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}', '<guid>' -replace '\s+', ' ').Trim()
                if ($norm.Length -gt 220) { $norm = $norm.Substring(0, 220) }
                if ($errorLines.ContainsKey($norm)) { $errorLines[$norm]++ } else { $errorLines[$norm] = 1 }
            }
        }
    }

    $summary = @($stats.Values | Where-Object { $_.Count -gt 0 } | Sort-Object Count -Descending | ForEach-Object {
        [pscustomobject]@{ Category = $_.Category; Count = $_.Count; First = $_.First; Last = $_.Last; Files = (@($_.Files.Keys) -join ', '); Samples = $_.Samples.ToArray() }
    })
    $topErrors = @($errorLines.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 15 | ForEach-Object { [pscustomobject]@{ Count = $_.Value; Message = $_.Key } })

    $result = [ordered]@{
        Source = $resolved; FilesScanned = $scanned; LinesScanned = $lines
        EncryptedOrBinaryFiles = $binary; Patterns = $summary; TopErrorLines = $topErrors
    }
    if ($Json) { $result | ConvertTo-Json -Depth 5; return }

    Write-Host "Scanned $scanned files, $lines lines$(if ($Since) { " since $Since" })." -ForegroundColor Cyan
    if ($binary.Count) { Write-Host "Skipped $($binary.Count) encrypted/binary file(s): $(($binary | Select-Object -First 8) -join ', ')$(if ($binary.Count -gt 8) { ', ...' })" -ForegroundColor Yellow }
    if ($scanned -eq 0) { Write-Host 'All logs look encrypted. Log encryption is likely on for this tenant; send the bundle to Zscaler Support.' -ForegroundColor Yellow; return }
    Write-Host ''
    Write-Host 'Known failure patterns:' -ForegroundColor Yellow
    if ($summary.Count -eq 0) { Write-Host '  None matched.' }
    foreach ($s in $summary) {
        Write-Host ("  {0}: {1} hits  ({2} -> {3})" -f $s.Category, $s.Count, $s.First, $s.Last)
        foreach ($l in $s.Samples) { Write-Host "      $(if ($l.Length -gt 200) { $l.Substring(0, 200) + '...' } else { $l })" -ForegroundColor DarkGray }
    }
    Write-Host ''
    Write-Host 'Most frequent error lines:' -ForegroundColor Yellow
    foreach ($e in $topErrors) { Write-Host ("  {0,6}x  {1}" -f $e.Count, $e.Message) -ForegroundColor DarkGray }
}
finally {
    if ($tempDir -and (Test-Path -LiteralPath $tempDir)) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
}
