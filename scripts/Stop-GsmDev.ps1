[CmdletBinding()]
param([Parameter(Mandatory)][string]$ReceiptPath)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\','/')
$receipt=[IO.Path]::GetFullPath($ReceiptPath)
$allowed=[IO.Path]::GetFullPath((Join-Path $root 'build/s0-runtime')).TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
if(-not $receipt.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Only a launcher receipt inside this workspace build/s0-runtime is accepted'}
$data=Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json
if([IO.Path]::GetFullPath($data.workspace).TrimEnd('\','/') -ine $root){throw 'Receipt workspace mismatch'}
foreach($service in $data.services){
    if($service.name -in @('api','worker')){
        $active=@(Get-ChildItem -LiteralPath $service.store -Filter status.json -Recurse -ErrorAction SilentlyContinue | ForEach-Object {Get-Content -LiteralPath $_.FullName -Raw|ConvertFrom-Json}|Where-Object {$_.status -in @('QUEUED','RUNNING')})
        if($active.Count){throw 'An active job exists. Cancel/wait first; no services stopped.'}
    }
}
$plan=[Collections.Generic.List[object]]::new()
foreach($service in @($data.services|Sort-Object @{Expression={if($_.name -eq 'frontend'){0}elseif($_.name -eq 'worker'){1}else{2}}})){
    $process=Get-CimInstance Win32_Process -Filter "ProcessId=$($service.pid)" -ErrorAction SilentlyContinue
    if(-not $process){Write-Host "Already stopped $($service.name) PID $($service.pid)";continue}
    if([math]::Abs(($process.CreationDate.ToUniversalTime()-[datetime]$service.startTimeUtc).TotalSeconds) -gt 1 -or $process.ExecutablePath -ine $service.executable){throw 'PID identity changed; refusing to stop'}
    # venv python may have one interpreter child. Never select by process name alone.
    $children=@(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($service.pid)")
    foreach($child in $children){
        if($child.ExecutablePath -ieq (Join-Path $env:WINDIR 'System32/conhost.exe')){continue}
        $suffix=$service.arguments -join ' '
        if($child.Name -ne 'python.exe' -or -not $child.CommandLine.EndsWith($suffix) -or $child.CreationDate -lt $process.CreationDate){throw 'Unexpected child command; inspect manually, no automatic tree termination'}
        $plan.Add(@{pid=$child.ProcessId;created=$child.CreationDate;name=$service.name})
    }
    $plan.Add(@{pid=$service.pid;created=$process.CreationDate;name=$service.name})
}
foreach($item in $plan){
    $current=Get-CimInstance Win32_Process -Filter "ProcessId=$($item.pid)"
    if($current -and $current.CreationDate -eq $item.created){Stop-Process -Id $item.pid -ErrorAction SilentlyContinue;Write-Host "Stopped task-created $($item.name) PID $($item.pid)"}
}
