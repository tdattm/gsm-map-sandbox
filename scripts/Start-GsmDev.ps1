# Small local launcher; no service/container termination or graph preprocessing.
[CmdletBinding()]
param(
    [switch]$StatusOnly,
    [ValidateSet('Standard','Meeting','Benchmark')][string]$Profile='Standard',
    [ValidateSet('HanoiCar','HanoiBoth','All','None')][string]$Routers='HanoiBoth',
    [switch]$StartRouters,
    [int]$ApiPort = 8013,
    [int]$FrontendPort = 5183,
    [string]$Store = 'build/m3/jobs'
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'GsmDockerProbe.ps1')
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
$taskStore = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($Store)) { $Store } else { Join-Path $taskRoot $Store }))
$apiUrl = "http://127.0.0.1:$ApiPort"
$siteUrl = "http://127.0.0.1:$FrontendPort"
$logRoot = Join-Path $taskRoot 'build/s0-runtime'
$frontendKind=$(if($Profile -eq 'Standard'){'development'}else{'preview'})
$owned=[Collections.Generic.List[object]]::new()
function Require-StartupHeadroom {
    $available=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB
    $minimum=0.5 # Service startup only; worker/API enforce workload admission separately.
    if($available -lt $minimum){throw "Cannot start missing service: available RAM $available GiB < $minimum GiB startup reserve. Existing services were not stopped. Job admission is a separate check."}
}
function Read-JsonUrl([string]$Url) {
    try { Invoke-RestMethod -Uri $Url -TimeoutSec 5 } catch { $null }
}
function Port-Owned([int]$Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count -gt 0
}
function Listener-Is([int]$Port, [int]$ServicePid) {
    $ServicePid -gt 0 -and (@(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess) -contains $ServicePid)
}
function Same-Path([string]$A, [string]$B) {
    if (-not $A -or -not $B) { return $false }
    [IO.Path]::GetFullPath($A).TrimEnd('\','/') -ieq [IO.Path]::GetFullPath($B).TrimEnd('\','/')
}
function Launch([string]$Name, [string]$Exe, [string[]]$Arguments, [string]$Directory) {
    Require-StartupHeadroom
    New-Item -ItemType Directory -Force $logRoot | Out-Null
    $tag = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $logRoot "$Name-$tag.stdout.log"
    $stderr = Join-Path $logRoot "$Name-$tag.stderr.log"
    $process = Start-Process -FilePath $Exe -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Host "Started $Name PID $($process.Id). Logs: $stdout / $stderr"
    @{name=$Name;pid=$process.Id;executable=$Exe;arguments=$Arguments;stdout=$stdout;stderr=$stderr;startedAt=(Get-Date).ToString('o')} | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $logRoot "$Name-$tag.process.json")
    $owned.Add(@{name=$Name;pid=$process.Id;executable=$Exe;arguments=$Arguments;startTimeUtc=$process.StartTime.ToUniversalTime().ToString('o');store=$taskStore})
}
function Wait-Json([string]$Url) {
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        $value=Read-JsonUrl $Url
        if ($value) { return $value }
        Start-Sleep -Milliseconds 250
    }
    return $null
}
if ($ApiPort -lt 1024 -or $ApiPort -gt 65535 -or $FrontendPort -lt 1024 -or $FrontendPort -gt 65535 -or $ApiPort -eq $FrontendPort) { throw 'Choose distinct ports in 1024..65535.' }
Write-Host "Workspace: $taskRoot`nAbsolute shared store: $taskStore"
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Missing .venv. Run: py -3.11 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt' }
Push-Location $taskRoot
try {
    & $taskPython -c 'import fastapi, uvicorn, httpx, pydantic; import sys; assert sys.version_info >= (3,11)'
    if ($LASTEXITCODE -ne 0) { throw 'Python prerequisites failed. Run: .\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt' }
    $ramGiB = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
    Write-Host ('Available RAM: {0:N2} GiB ; profile={1}; frontend={2}. Missing-service startup floor=0.5 GiB; reuse/status has no startup floor. API/worker check workload admission separately.' -f $ramGiB,$Profile,$frontendKind)
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $vite = Join-Path $taskRoot 'frontend/node_modules/vite/bin/vite.js'
    if (-not $node -or -not (Test-Path -LiteralPath $vite)) { throw 'Node/Vite missing. Install Node 20.19+ or 22.12+, then run: Set-Location frontend; npm.cmd ci' }
    $nodeVersion = [version]((& $node.Source --version).Trim().TrimStart('v'))
    if (-not (($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19) -or ($nodeVersion.Major -eq 22 -and $nodeVersion.Minor -ge 12) -or $nodeVersion.Major -gt 22)) { throw 'Unsupported Node version for Vite. Use Node 20.19+ or 22.12+.' }
    if($frontendKind -eq 'preview'){
        & $node.Source (Join-Path $taskRoot 'frontend/scripts/build-identity.mjs') --check
        if($LASTEXITCODE -ne 0){if($StatusOnly){Write-Warning 'Production build missing/stale.'}else{throw 'Build first: Set-Location frontend; npm.cmd ci; npm.cmd run build. Then rerun Meeting/Benchmark launcher.'}}
    }
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        $dockerInfo=Get-GsmDockerProbe -Kind info
        if ($dockerInfo.exitCode -ne 0) {
            Write-Warning "Docker Engine unavailable: $($dockerInfo.stderr)"
            if($StartRouters -and -not $StatusOnly -and $Routers -ne 'None'){throw 'Cannot start routers until Docker Engine is ready; no graph rebuild attempted.'}
        } else { Write-Host $dockerInfo.stdout; $dockerPs=Get-GsmDockerProbe -Kind ps; if($dockerPs.exitCode -eq 0){Write-Host $dockerPs.stdout}else{Write-Warning $dockerPs.stderr} }
    } else {
        Write-Warning 'Docker CLI missing. Local OSRM readiness may be unavailable.'
        if($StartRouters -and -not $StatusOnly -and $Routers -ne 'None'){throw 'Docker CLI required to start routers'}
    }
    if($StartRouters -and -not $StatusOnly -and $Routers -ne 'None'){
        Require-StartupHeadroom
        if($Routers -eq 'All'){& $taskPython scripts/pipeline.py serve --detach;if($LASTEXITCODE -ne 0){throw 'HCM router serve failed'}}
        & $taskPython scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
        if($LASTEXITCODE -ne 0){throw 'Hanoi CAR serve failed; graph was not rebuilt'}
        if($Routers -in @('HanoiBoth','All')){& $taskPython scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach;if($LASTEXITCODE -ne 0){throw 'Hanoi MOTORBIKE serve failed'}}
    }
    # Readiness only. Never start/recreate an unverified Docker container here.
    foreach ($router in @(@(5000,'HCM CAR'),@(5001,'Hanoi CAR'),@(5002,'Hanoi MOTORBIKE'))) {
        Write-Host "Router $($router[1]) :$($router[0]) listening=$(Port-Owned $router[0]) (mode API verifies graph identity)"
    }
    $runtime = Read-JsonUrl "$apiUrl/api/v3/simulation/jobs/runtime"
    $apiMatches = $runtime.application -eq 'gsm-map-sandbox' -and (Same-Path $runtime.workspace $taskRoot) -and (Same-Path $runtime.store $taskStore) -and (Listener-Is $ApiPort $runtime.apiPid)
    if (Port-Owned $ApiPort) {
        if (-not $apiMatches) {
            $diagnostic="Port $ApiPort is occupied by an unverified/stale API or another store. Inspect: Get-NetTCPConnection -LocalPort $ApiPort; Get-CimInstance Win32_Process. For your own old API terminal, Ctrl+C then rerun this launcher; or choose -ApiPort with a free port. No process stopped."
            if ($StatusOnly) { Write-Warning $diagnostic } else { throw $diagnostic }
        } else { Write-Host "API verified/reused: $apiUrl ; worker=$($runtime.worker)" }
    } elseif (-not $StatusOnly) {
        $oldStore=$env:GSM_SIMULATION_STORE
        try { $env:GSM_SIMULATION_STORE=$taskStore; Launch 'api' $taskPython @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',"$ApiPort") $taskRoot }
        finally { $env:GSM_SIMULATION_STORE=$oldStore }
        $runtime=Wait-Json "$apiUrl/api/v3/simulation/jobs/runtime"
        if ($runtime.application -ne 'gsm-map-sandbox' -or -not (Same-Path $runtime.workspace $taskRoot) -or -not (Same-Path $runtime.store $taskStore) -or -not (Listener-Is $ApiPort $runtime.apiPid)) { throw "API startup/identity failed. Check $logRoot and: & '$taskPython' -m uvicorn backend.app.main:app --host 127.0.0.1 --port $ApiPort" }
    } else { Write-Warning "Backend FastAPI offline: $apiUrl" }
    $workerProbe = & $taskPython -c 'import sys,json; from backend.app.simulation_jobs import JobStore; print(json.dumps(JobStore(sys.argv[1]).runtime()))' $taskStore | ConvertFrom-Json
    if ($workerProbe.worker -eq 'locked') { Write-Host 'Worker lease verified on the same absolute store; reuse (not a heartbeat).' }
    elseif ($workerProbe.worker -eq 'offline' -and -not $StatusOnly) {
        Launch 'worker' $taskPython @('-m','backend.app.simulation_worker','--store',('"'+$taskStore+'"')) $taskRoot
        Start-Sleep -Milliseconds 700
        $workerProbe = & $taskPython -c 'import sys,json; from backend.app.simulation_jobs import JobStore; print(json.dumps(JobStore(sys.argv[1]).runtime()))' $taskStore | ConvertFrom-Json
        if ($workerProbe.worker -ne 'locked') { throw "Worker did not acquire store lease. Inspect $logRoot. Manual: & '$taskPython' -m backend.app.simulation_worker --store '$taskStore'" }
    } else { Write-Warning "Worker=$($workerProbe.worker). Manual: & '$taskPython' -m backend.app.simulation_worker --store '$taskStore'" }
    $dev=Read-JsonUrl "$siteUrl/__gsm_dev"
    if (Port-Owned $FrontendPort) {
        if ($dev.application -ne 'gsm-map-sandbox-vite' -or -not (Same-Path $dev.workspace $taskRoot) -or $dev.proxy -ne $apiUrl -or $dev.kind -ne $frontendKind -or -not (Listener-Is $FrontendPort $dev.pid)) {
            $diagnostic="Port $FrontendPort has a different/stale frontend or proxy. Reuse requires /__gsm_dev identity and proxy=$apiUrl. Restart only your Vite terminal, or choose -FrontendPort with a free port."
            if ($StatusOnly) { Write-Warning $diagnostic } else { throw $diagnostic }
        } else { Write-Host "Vite verified/reused; proxy=$($dev.proxy)" }
    } elseif (-not $StatusOnly) {
        & $node.Source (Join-Path $taskRoot 'frontend/scripts/copy-map-worker.mjs')
        if ($LASTEXITCODE -ne 0) { throw 'Local MapLibre worker copy failed. Run npm.cmd ci in frontend.' }
        $oldProxy=$env:GSM_API_PROXY
        try { $env:GSM_API_PROXY=$apiUrl; $frontArgs=@(('"'+$vite+'"'));if($frontendKind -eq 'preview'){$frontArgs+=@('preview')};$frontArgs+=@('--host','127.0.0.1','--port',"$FrontendPort",'--strictPort');Launch 'frontend' $node.Source $frontArgs (Join-Path $taskRoot 'frontend') }
        finally { $env:GSM_API_PROXY=$oldProxy }
        $dev=Wait-Json "$siteUrl/__gsm_dev"
        if ($dev.application -ne 'gsm-map-sandbox-vite' -or $dev.proxy -ne $apiUrl -or -not (Listener-Is $FrontendPort $dev.pid)) { throw "Vite startup failed. Check $logRoot. Manual: Set-Location frontend; `$env:GSM_API_PROXY='$apiUrl'; npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort --strictPort" }
    }
    $health=Read-JsonUrl "$apiUrl/api/health"
    Write-Host "FastAPI health: status=$($health.status) backend_ready=$($health.backend_ready)"
    $hcm=Read-JsonUrl "$apiUrl/api/dataset/status"
    if ($hcm) { Write-Host "HCM readiness: ready=$($hcm.ready) router=$($hcm.osrm.state)" }
    else { Write-Warning 'HCM dataset/router readiness unavailable. Check API and HCM pipeline serve command below.' }
    $modes=Read-JsonUrl "$apiUrl/api/v2/regions/nvmr-hanoi-core/modes"
    if ($modes) { $modes | ConvertTo-Json -Depth 8 } else { Write-Warning 'Cannot verify Hanoi mode/graph readiness. Check API then pipeline serve commands below.' }
    foreach ($asset in @('streets','water','green','buildings','places')) {
        # Exact configured URLs are documented by the render manifest/map style.
        $assetPath=Join-Path $taskRoot "data/regions/nvmr-hanoi-core/render/$asset.geojson"
        Write-Host "Local render $asset : $(Test-Path -LiteralPath $assetPath)"
    }
    Write-Host "Website: $siteUrl/?runtime=simulation&profile=$($Profile.ToLowerInvariant())"
    Write-Host 'Router recovery (no rebuild): .\.venv\Scripts\python.exe scripts/pipeline.py serve --detach'
    Write-Host 'Hanoi: .\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach'
    Write-Host 'Motorbike: .\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach'
    Write-Host "API store/worker status: $apiUrl/api/v3/simulation/jobs/runtime"
} finally {
    if($owned.Count){$receipt=Join-Path $logRoot ('session-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'.json');@{workspace=$taskRoot;profile=$Profile;services=$owned.ToArray()}|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 -LiteralPath $receipt;Write-Host "Task-created services receipt: $receipt"}
    Pop-Location
}
