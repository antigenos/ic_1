param(
    [Parameter(Mandatory)][string]$SampleDirectory,
    [int[]]$LaneCpus = @(4, 6, 8, 10, 14),
    [int[]]$Siblings = @(5, 7, 9, 11, 15),
    [switch]$Once
)
$ErrorActionPreference = 'Stop'
$dir = (Resolve-Path -LiteralPath $SampleDirectory).Path
$controller = Get-Content -LiteralPath (Join-Path $dir 'controller.json') -Raw | ConvertFrom-Json
if ($LaneCpus.Count -ne $Siblings.Count -or ($controller.cpus -join ',') -ne ($LaneCpus -join ',')) {
    throw 'Lane CPUs and sibling mapping must cover the actual manifest'
}
$controllerId = [int]$controller.pid
$free = @{}
$coreMasks = @{}
for ($i=0; $i -lt $LaneCpus.Count; $i++) {
    $cpu = $LaneCpus[$i]
    $free[[string]$cpu] = 0
    $coreMasks[$cpu] = ([int64]1 -shl $cpu) -bor ([int64]1 -shl $Siblings[$i])
}
$lastEpoch = 0
$previousBusy = $null
do {
    $observed = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='abc.exe'")
    $owner = @($observed | Where-Object {
        $_.ProcessId -eq $controllerId -and $_.CommandLine -match '(?:^|[/\\\s"])family\.py[" ]+run\b' -and
        ([DateTimeOffset]$_.CreationDate).ToUnixTimeSeconds() -le $controller.started
    })
    if ($owner.Count -ne 1) {
        Write-Output 'Experiment controller exited'
        break
    }
    $workerIds = @($observed | Where-Object { $_.Name -eq 'python.exe' -and $_.ParentProcessId -eq $controllerId } | ForEach-Object ProcessId)
    $busy = @{}
    $ourSolvers = @()
    foreach ($item in @($observed | Where-Object Name -eq 'abc.exe')) {
        if ($workerIds -contains $item.ParentProcessId) {
            $ourSolvers += [int]$item.ProcessId
            continue
        }
        $foreign = Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $foreign) { continue }
        try { $mask = $foreign.ProcessorAffinity.ToInt64() } catch { $mask = 0 }
        foreach ($cpu in $LaneCpus) {
            if ($mask -eq 0 -or ($mask -band $coreMasks[$cpu]) -ne 0) { $busy[$cpu] = $true }
        }
    }
    $epoch = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    foreach ($cpu in $LaneCpus) {
        $key = [string]$cpu
        if ($busy.ContainsKey($cpu)) { $free[$key] = 0 }
        elseif ($epoch - $lastEpoch -gt 45 -or $epoch -lt $lastEpoch) { $free[$key] = 1 }
        else { $free[$key]++ }
    }
    $lastEpoch = $epoch
    $occupied = @($LaneCpus | Where-Object { $busy.ContainsKey($_) })
    $sample = [ordered]@{epoch=$epoch; occupied=$occupied; consecutive_free=$free; own_pids=$ourSolvers}
    $line = $sample | ConvertTo-Json -Depth 4 -Compress
    [IO.File]::AppendAllText((Join-Path $dir 'samples.jsonl'), $line + [Environment]::NewLine)
    $tmp = Join-Path $dir 'latest.tmp'
    [IO.File]::WriteAllText($tmp, $line)
    [IO.File]::Move($tmp, (Join-Path $dir 'latest.json'), $true)
    $label = $occupied -join ','
    if ($label -ne $previousBusy -or $Once) {
        Write-Output $line
        $previousBusy = $label
    }
    if (-not $Once) { Start-Sleep -Seconds 25 }
} while (-not $Once)
