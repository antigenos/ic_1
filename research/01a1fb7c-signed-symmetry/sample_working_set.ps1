param(
    [Parameter(Mandatory)][int]$Coordinator,
    [Parameter(Mandatory)][string]$StartedUtc,
    [Parameter(Mandatory)][string]$Binary,
    [Parameter(Mandatory)][string]$OutputFile
)
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Binary).Path
$expected=([datetimeoffset]::Parse($StartedUtc)).UtcDateTime
$parent=Get-Process -Id $Coordinator
if ([math]::Abs(($parent.StartTime.ToUniversalTime()-$expected).TotalSeconds) -gt 1) {throw 'Coordinator PID has been reused'}
$stream=[System.IO.File]::Open($OutputFile,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::Read)
$writer=[System.IO.StreamWriter]::new($stream,[System.Text.UTF8Encoding]::new($false))
try {
    while (-not $parent.HasExited) {
        foreach ($p in (Get-Process -Name ([System.IO.Path]::GetFileNameWithoutExtension($exe)) -ErrorAction SilentlyContinue)) {
            try {
                if ($p.Path -ne $exe) {continue}
                $row=[ordered]@{pid=$p.Id;created_utc=$p.StartTime.ToUniversalTime().ToString('o');sample_utc=[datetime]::UtcNow.ToString('o');peak_working_set_bytes=$p.PeakWorkingSet64}
                if ($row.peak_working_set_bytes -gt 0) {$writer.WriteLine(($row|ConvertTo-Json -Compress))}
            } catch [System.InvalidOperationException] {
                # The solver can exit between enumeration and reading its counters.
                continue
            } catch [System.ComponentModel.Win32Exception] {
                if ($p.HasExited) {continue}
                throw
            }
        }
        $writer.Flush()
        [void]$parent.WaitForExit(25000)
    }
} finally {
    $writer.Dispose()
    $parent.Dispose()
}
