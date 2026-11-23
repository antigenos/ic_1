# Sample ABC affinity on the registered cores. Keep only aggregate counts.
param([switch]$Phase)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$study = Join-Path $repo '.local/variants'
$owned = @((Join-Path $study 'orbit-control/abc.exe'), (Join-Path $study 'orbit-signed/abc.exe')) |
    ForEach-Object { [IO.Path]::GetFullPath($_) }
$directory = Join-Path $repo '.local/orbit-confirmation-300'
$cores = @(16, 18, 20, 22, 24, 26, 28, 30)
$worker = 'target-orbits-01a1fb7c[\\/]full\.py"?\s+--lane\s+\d+'
if ($Phase) {
    $directory = Join-Path $repo '.local/orbit-phase-ablation'
    $cores = @(16, 18)
    $worker = 'target-orbits-01a1fb7c[\\/]compare_orbits\.py"?\s+[0-9a-f]{4}\s+'
}
$parents = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match $worker } |
    Select-Object -ExpandProperty ParentProcessId -Unique)
if ($parents.Count -ne 1) { throw "Expected one live coordinator for the registered lanes" }
$coordinator = [Diagnostics.Process]::GetProcessById($parents[0])
$path = Join-Path $directory 'occupancy.jsonl'
$stream = [IO.File]::Open($path, 'Append', 'Write', 'Read')
$writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
try {
    do {
        $ownCores = @()
        $otherSingle = @()
        $multi = 0
        foreach ($abc in @(Get-Process -Name abc -ErrorAction SilentlyContinue)) {
            try {
                $mask = $abc.ProcessorAffinity.ToInt64()
                $binary = $abc.Path
            } catch { continue }
            $allowed = @($cores | Where-Object { $mask -band ([long]1 -shl $_) })
            if (!$allowed.Count) { continue }
            if ($binary -in $owned) {
                $ownCores += $allowed
            } elseif (($mask -band ($mask - 1)) -eq 0) {
                $otherSingle += $allowed
            } else {
                $multi++
            }
        }
        $row = [ordered]@{
            utc = [DateTime]::UtcNow.ToString('o')
            own = @($ownCores | Sort-Object)
            other_single_core = @($otherSingle | Sort-Object)
            other_multicore_intersecting = $multi
        }
        $writer.WriteLine(($row | ConvertTo-Json -Compress))
        $writer.Flush()
    } while (!$coordinator.WaitForExit(30000))
} finally {
    $writer.Dispose()
    $coordinator.Dispose()
}
