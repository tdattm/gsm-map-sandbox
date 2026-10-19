# Connected NVMR — Windows PowerShell runbook

Workspace: `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`; branch
`feature/nvmr-m0-architecture`. This runbook describes commands, not a claim that
every prerequisite has passed. Read [implementation](R1B_CONNECTED_IMPLEMENTATION.md),
[GIS report](R1B_CONNECTED_GIS.md) and [checkpoint](R1B_PROGRESS.md) for executed evidence.
Inputs represent synthetic research fleet/demand, not actual GSM operations.

## 1. Inspect resources and existing artifacts

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
git status --short
git branch --show-current
git rev-parse HEAD
docker info --format '{{.OSType}}'
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
.\.venv\Scripts\python.exe -c "from scripts.m3_resources import memory; import json,shutil; print(json.dumps({'memory':memory(),'disk':shutil.disk_usage('.')._asdict()}))"
```

Docker must be Linux. Open installed Docker Desktop normally if stopped. Do not
change WSL/Docker/pagefile settings or terminate another task's containers.
Heavy GIS needs at least2GiB available physical and commit headroom, plus8GiB
free disk. A **fresh extract** now requires6GiB physical and commit headroom;
verified extract reuse retains the ordinary check. These are admission floors,
not memory reservations; actual extraction
briefly caused severe host memory pressure on this machine. CAR/MOTORBIKE and
rendering run sequentially. Do not run full tests/build/benchmarks alongside them.

GIS native dependencies, when absent:

```powershell
.\.venv\Scripts\python.exe -m pip install -r scripts/requirements-connected-gis.txt
```

Reused PBF: `data/raw/vietnam-latest.osm.pbf`, snapshot
`2026-10-09T20:21:04Z`, SHA-256
`2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`.
Do not download a replacement when that identity matches.

## 2. Reuse or build the isolated Connected namespace

Only run a missing stage after inspecting `R1B_PROGRESS.md` and any `.incomplete`
markers. Do not remove markers to force reuse or overwrite a failed build.
The pipeline refuses mismatched artifacts; preserve failed attempts and follow
the exact recovery commands in the GIS report.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py verify
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py extract
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py routing --mode CAR
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py routing --mode MOTORBIKE
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py render
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py anchors
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_routing.py --prepare-synthetic
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py serve --mode CAR
.\.venv\Scripts\python.exe -X utf8 scripts/connected_gis.py serve --mode MOTORBIKE
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_routing.py --snap-anchors
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_routing.py
```

Stop a command sequence on a nonzero exit. All data is under
`data/regions/nvmr-connected/`; HCM/Hanoi/Bac Ninh artifacts are retained.
Connected ports are CAR5005 and MOTORBIKE5006. A fresh Git clone contains source
and configuration but not ignored PBF/graphs/MBTiles/job stores.

`--prepare-synthetic` runs the small generated access/one-way/turn oracle before
the full graph routers occupy memory. The final validator reuses this oracle only
when its current profile, binary, generator, validator and evidence hashes match;
it still executes real connected-road probes. An incomplete or changed oracle
fails explicitly. This separates generated semantic evidence from real OSM routes.

## 3. Start one application stack

After GIS work has completed and resource headroom has recovered:

```powershell
Push-Location frontend
npm.cmd run build
Pop-Location
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Profile Meeting -Routers Connected -StartRouters -ApiPort 8022 -FrontendPort 5192 -Store build/r1b/jobs
```

This serves/reuses graphs; it does not preprocess them. Existing listener
identity/workspace/store checks and one worker lease are retained. Use different
free ports if those belong to another stack. The API/worker must load current
source; do not reuse an older interpreter just because its health endpoint works.

Open `http://127.0.0.1:5192/?runtime=simulation&scenario=connected&profile=meeting` or choose
**Mô phỏng quy mô lớn → Kịch bản mô phỏng → Miền Bắc liên thông** from the main
application. Select100/500/1.000/5.000 or customize exact zone/mode counts. Demand
weights default equal, independent of80/20 fleet. Set seed, request count, horizon,
pickup wait and mode/OD fractions, then **Tạo mô phỏng liên thông**.

The map fits the full rectangle, then supports normal pan/zoom without changing
region. Low zoom clusters use native layers; high zoom shows CAR/MOTORBIKE
symbols. Filters affect display only. Search a full global vehicle ID to select
it and clear map filters; click an icon for the same inspector. Only selected
pickup/trip geometry is requested. Pickup is dashed and trip is solid. Play,
pause, seek and reset use one clock. Save the job ID and use **Mở run đã lưu**
after reload; completed runs replay from immutable data without OSRM rerouting.

For completed replay with routers off, use `-Routers None` and omit
`-StartRouters`. API/store and local tiles are still required on a new page.
Missing artifacts, graph identity failures, router unavailable and explicit
NoRoute/NoSegment remain errors; no public map/router fallback is used.

## 4. API and live acceptance

```powershell
Invoke-RestMethod 'http://127.0.0.1:8022/api/v3/simulation/jobs/runtime'
Invoke-RestMethod 'http://127.0.0.1:8022/api/v5/connected/map/status'
Invoke-RestMethod 'http://127.0.0.1:8022/api/v5/simulation/jobs'
```

Create a new bounded live benchmark only when real routers/validated anchors are
ready. These commands are examples until reported as executed:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --fleet 100 --bookings 25 --output build/r1b/live-100.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --fleet 500 --bookings 125 --output build/r1b/live-500.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --fleet 1000 --bookings 250 --output build/r1b/live-1000.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --fleet 5000 --bookings 1250 --output build/r1b/live-5000.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --fleet 20 --bookings 20 --horizon 120 --seed connected-cross-zone/v1 --cross-zone-proof --output build/r1b/live-cross-zone.json
```

Reaudit/reopen an existing run with `--job-id <id>` instead of generating a
duplicate. Failed/queued/running jobs are retained; a timeout does not cancel or
repeat the POST. The verifier reports worker RSS samples/lifetime peak separately,
host/commit headroom, output bytes, telemetry, route identities and independently
reconstructed KPIs. Static modeled ETA is not live traffic or observed service.

## 5. Source and compatibility checks

When the heavy GIS slot is free:

```powershell
$env:RUN_REAL_DATA='0'
.\.venv\Scripts\python.exe -m pytest -q -rs
Push-Location frontend
npm.cmd test -- --maxWorkers=1
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run verify:replay
Pop-Location
git diff --check
git diff --stat
git status --short
```

Opt-in historical HCM/Hanoi real-data tests require their own verified routers;
set `RUN_REAL_DATA=1` only when those prerequisites are available. No skip is a
PASS. Domain fixture benchmarks in `validate_connected_domain.py` prove engine
and accounting behavior only and are always labelled separately from live OSRM.

The launcher prints a task-owned receipt under `build/s0-runtime/`. To stop only
that stack, pass its exact receipt to `scripts/Stop-GsmDev.ps1 -ReceiptPath ...`;
first inspect queued/running jobs. Do not kill by generic process name. No command
in this runbook stages, commits, pushes or merges.
