[CmdletBinding()]
param([int]$Seconds=30,[int]$IntervalMs=1000,[string]$Label='manual',
      [string]$Output='build/m4-performance/memory.json')
$ErrorActionPreference='Stop'
if($Seconds -lt 1 -or $IntervalMs -lt 200){throw 'Seconds >=1 and IntervalMs >=200 required'}
$root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'GsmDockerProbe.ps1')
$path=[IO.Path]::GetFullPath($(if([IO.Path]::IsPathRooted($Output)){$Output}else{Join-Path $root $Output}))
$samples=[Collections.Generic.List[object]]::new()
$started=(Get-Date).ToUniversalTime()
$until=$null
do {
    $os=Get-CimInstance Win32_OperatingSystem
    $mem=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $cpu=Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
    $processes=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^(chrome|ChatGPT|vmmemWSL|Docker Desktop|com.docker.backend|Code|node|python|Zalo)\.exe$' -or $_.Name -eq 'vmmemWSL'
    } | ForEach-Object {
        $service=if($_.CommandLine -match '-m uvicorn backend.app.main:app'){'api'}elseif($_.CommandLine -match '-m backend.app.simulation_worker'){'worker'}elseif($_.CommandLine -match 'frontend[\\/]node_modules[\\/]vite[\\/]bin[\\/]vite.js'){'frontend'}elseif($_.CommandLine -match 'profile_simulation_memory.py'){'profiler'}else{'other'}
        # No window titles, URLs, environment or unrelated command lines are recorded.
        [ordered]@{pid=$_.ProcessId;parentPid=$_.ParentProcessId;name=$_.Name;service=$service;
            gsmCommand=[bool]($_.CommandLine -and ($_.CommandLine.Contains($root) -or $_.CommandLine -match 'backend.app.(main|simulation_worker)'));
            workingSetBytes=[long]$_.WorkingSetSize;privateBytes=[long]$_.PrivatePageCount;
            peakWorkingSetBytes=[long]$_.PeakWorkingSetSize*1024;pageFaultsCumulative=[long]$_.PageFaults;
            kernelTime100ns=[long]$_.KernelModeTime;userTime100ns=[long]$_.UserModeTime}
    })
    $samples.Add([ordered]@{at=(Get-Date).ToUniversalTime().ToString('o');
        totalPhysicalBytes=[long]$os.TotalVisibleMemorySize*1024;availablePhysicalBytes=[long]$os.FreePhysicalMemory*1024;
        committedBytes=[long]$mem.CommittedBytes;commitLimitBytes=[long]$mem.CommitLimit;
        commitHeadroomBytes=[long]$mem.CommitLimit-[long]$mem.CommittedBytes;
        pagesInputPerSecond=$mem.PagesInputPersec;pageReadsPerSecond=$mem.PageReadsPersec;pageFaultsPerSecond=$mem.PageFaultsPersec;
        cpuPercent=$cpu.PercentProcessorTime;processes=$processes;
        pagefiles=@(Get-CimInstance Win32_PageFileUsage | Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage)})
    # CIM can take several seconds to warm up. Measure the requested window
    # after the first sample instead of spending it on provider startup.
    if($null -eq $until){$until=(Get-Date).AddSeconds($Seconds)}
    if((Get-Date) -lt $until){Start-Sleep -Milliseconds $IntervalMs}
} while((Get-Date) -lt $until)
$dockerProbe=Get-GsmDockerProbe -Kind stats
$docker=@();if($dockerProbe.exitCode -eq 0){$docker=@($dockerProbe.stdout -split '\r?\n' | Where-Object {$_})}
$parent=Split-Path -Parent $path;New-Item -ItemType Directory -Force $parent | Out-Null
[ordered]@{schemaVersion='gsm-memory-profile/v1';label=$Label;requestedSeconds=$Seconds;startedAt=$started.ToString('o');finishedAt=(Get-Date).ToUniversalTime().ToString('o');intervalMs=$IntervalMs;samples=$samples.ToArray();dockerStatsAtEnd=$docker;dockerProbe=$dockerProbe;
    notes=@('Process working sets can share pages; do not sum them as total system usage.','PageFaults includes soft faults. PagesInput/PageReads are system paging indicators, not attribution to GSM.','Docker stats excludes WSL VM/desktop overhead. Private bytes is commit, not resident RAM.')} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding utf8
Write-Output $path
