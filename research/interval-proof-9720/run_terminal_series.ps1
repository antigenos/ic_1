param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$RunId,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$StorageRevision,
    [string]$ContinueHoldoutFrom,
    [string]$HoldoutRevision = '053b9fdf2141a33d87f015720767970e0d57db09'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = (Get-Command python).Source
$shell = (Get-Process -Id $PID).Path
$series = ".local/terminal-series-$RunId"
New-Item -ItemType Directory -Path $series -ErrorAction Stop | Out-Null
foreach ($panel in @('holdout','storage')) {
    $tag = "terminal-$panel-$RunId"
    $raw = ".local/$tag.jsonl"
    $samples = ".local/host-$tag"
    $csv = "$series/$panel.csv"
    if ((Test-Path $raw) -or (Test-Path $samples) -or (Test-Path ".local/terminal-comparisons/$tag")) {
        throw "Existing trial data for $tag; inspect the previous controller first"
    }
    $flag = if ($panel -eq 'holdout') {'--holdout'} else {'--storage-control'}
    $rev = if ($panel -eq 'holdout') {$HoldoutRevision} else {$StorageRevision}
    $arguments = @('-u','terminal_compare.py',$raw,$flag,'--candidate-ref',$rev,'--cpu','0','--host-samples',$samples)
    if ($panel -eq 'holdout' -and $ContinueHoldoutFrom) {
        $arguments += @('--continue-from', ('"' + (Resolve-Path -LiteralPath $ContinueHoldoutFrom).Path + '"'))
    }
    $controller = Start-Process $python -ArgumentList $arguments -PassThru -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$series/$panel.out" -RedirectStandardError "$series/$panel.err"
    for ($n=0; $n -lt 120 -and -not (Test-Path "$samples/controller.json"); $n++) {
        if ($controller.HasExited) { throw "$panel exited before registration, see $series/$panel.err" }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path "$samples/controller.json")) {throw "$panel did not register, inspect its process and logs"}
    $observer = Start-Process $shell -ArgumentList @('-NoProfile','-File','watch-host.ps1','-SampleDirectory',$samples,'-LaneCpus','0','-Siblings','1') -PassThru -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$series/$panel-watch.out" -RedirectStandardError "$series/$panel-watch.err"
    $controller.WaitForExit()
    if ($controller.ExitCode -ne 0) {throw "$panel failed, see $series/$panel.err"}
    $observer.WaitForExit()
    if ($observer.ExitCode -ne 0) {throw "$panel observer failed, see $series/$panel-watch.err"}
    & $python terminal_compare.py $raw $flag --public-csv $csv
    if ($LASTEXITCODE -ne 0) {throw "$panel verification failed"}
    & $python terminal_report.py $csv $panel | Set-Content -Encoding utf8 "$series/$panel-summary.json"
    if ($LASTEXITCODE -ne 0) {throw "$panel paired report failed"}
}
