# R1a local PowerShell runbook

> **Historical / Superseded direction (R1b, 19/10/2026):** The current target is Unified Connected NVMR: one connected CAR graph, one independent MOTORBIKE graph, one global engine/fleet/dispatch/clock and unified viewport. Independent N-region R1b expansion is superseded. This historical document retains its original evidence, metrics and limitations; it does not establish cross-province dispatch. See [current implementation](R1B_CONNECTED_IMPLEMENTATION.md), [runbook](R1B_CONNECTED_RUNBOOK.md) and [recovery checkpoint](R1B_PROGRESS.md).

Workspace: `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`. Verified on 18 October 2026. Commands below operate on local services/artifacts only. Do not stage PBF/graphs/job stores. The implementation/evidence report distinguishes actual executed checks from optional commands.

## 1. Inspect and reuse before starting

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
git status --short
git worktree list
docker info --format '{{.OSType}}'
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -StatusOnly -Profile Meeting -Routers Regional -ApiPort 8021 -FrontendPort 5191 -Store build/r1a/jobs
```

Docker must report `linux`. If it is unavailable, open Docker Desktop normally and wait for its engine; this runbook does not reset Docker/WSL/settings, kill owner containers or change pagefile/registry. `-StatusOnly` is read-only and never rebuilds graphs. The existing launcher performs bounded Docker probing and checks ports/PID/workspace/store/proxy/worker lease.

The R1a verification stack uses API8021/preview5191 and absolute store `build/r1a/jobs`. The owner's earlier8016/5187 stack was left intact. Reusing an old process with a correct port is insufficient to load new Python source; stop only a process you own with its verified receipt, then restart. Do not run a duplicate worker against the same store.

## 2. Build frontend and start/reuse one stack

```powershell
Push-Location frontend
npm.cmd run build
Pop-Location
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Profile Meeting -Routers Regional -StartRouters -ApiPort 8021 -FrontendPort 5191 -Store build/r1a/jobs
```

`-Routers Regional` selects Hanoi CAR/MOTORBIKE plus Bac Ninh CAR/MOTORBIKE. `-StartRouters` invokes safe **serve/reuse** commands, never `routing`, `extract`, or `display`. Existing verified containers are inspected and reused. Launcher defaults remain HanoiBoth; Regional is an explicit choice. Meeting serves a fresh production build and changes presentation cadence only. It does not change fleet, demand, seed, dispatch, profiles, geometries or scientific outcomes.

For development instead of production preview, use `-Profile Standard` with a distinct free frontend port or restart your own existing frontend first. For persisted replay with routers off, use `-Routers None` and omit `-StartRouters`. API and local geographic asset files are still needed on a fresh page.

Services can also be served individually without rebuilding:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe -X utf8 scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
.\.venv\Scripts\python.exe -X utf8 scripts/pipeline.py serve --region nvmr-bac-ninh-core --profile car --detach
.\.venv\Scripts\python.exe -X utf8 scripts/pipeline.py serve --region nvmr-bac-ninh-core --profile motorbike --detach
```

To exercise HCM legacy, its existing graph can be served separately:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/pipeline.py serve --detach
```

That HCM command was executed for R1a regression; it did not preprocess or alter HCM graph files.

## 3. Website flow and persisted examples

Open `http://127.0.0.1:5191/`, choose **Mô phỏng quy mô lớn**, then **Kịch bản mô phỏng → NVMR · Hanoi + Bắc Ninh Core pilot**. Legacy Hanoi v3 remains the default choice. Direct regional link: `http://127.0.0.1:5191/?runtime=simulation&scenario=regional&profile=meeting`.

For a small scenario, keep10 vehicles/5CAR per region, requests12 each, online1; set a seed and horizon. These are synthetic inputs. **Tạo mô phỏng hai vùng** submits one v4 job. Save its ID, wait for COMPLETED, and use the shared playback controls. No partial region is published as final. Failed readiness names the missing region/mode; fix that prerequisite instead of substituting a different router.

Overview shows technical operating extents and per-region counts. Click an extent or choose **Vùng hiển thị**. Only one detailed local basemap loads. **Tìm global vehicle ID** searches both regions and changes view to the owning region. Native clustered symbols and selected journey layers use the existing M4/S1 implementation. Pickup is dashed; passenger trip is solid. **Theo dõi vị trí xe** and **Xem toàn hành trình** provide useful camera views. Zoom in to see individual CAR/MOTORBIKE symbols; low zoom uses clusters.

Run created through the website in this task:

- ID `6920edfece7042dd9a98fa42c52edcf6`, seed `r1a-ui-20-v1`, horizon120, fleet20,24 requests,19 completed/5 unserved.
- At t100, global fleet20 = Bac Ninh10 + Hanoi10; search/select the following active examples:

| Region/mode | Vehicle | At t100 |
|---|---|---|
| Bac Ninh CAR | `nvmr-bac-ninh-core:GSM-00003` | ON_TRIP, booking `nvmr-bac-ninh-core:BK-000004` |
| Bac Ninh MOTORBIKE | `nvmr-bac-ninh-core:GSM-00007` | ASSIGNED, booking `nvmr-bac-ninh-core:BK-000011` |
| Hanoi CAR | `nvmr-hanoi-core:GSM-00002` | ASSIGNED, booking `nvmr-hanoi-core:BK-000005` |
| Hanoi MOTORBIKE | `nvmr-hanoi-core:GSM-00006` | ASSIGNED, booking `nvmr-hanoi-core:BK-000003` |

Use **Mở regional run đã lưu** to reopen the run after reload. Region switching keeps the same result and simulation clock. Pause/seek/reset act on both regional snapshots. Geometry/details come from the persisted immutable run, not a new OSRM query. A clone of Git does not contain ignored local job stores; these IDs are local examples.

Other verified jobs:

| Total fleet | ID | Evidence |
|---|---|---|
|20|`cf7f7073fc974b2184181fe8ce58a36e`|`live-20.json`|
|100, corrected same-seed retry|`9cca52e88d214266810f59788785b88b`|`live-100-retry.json`|
|500|`a099e68a5ed04741a26d44889470768c`|`live-500.json`|
|5,000,2,000CAR+3,000MOTORBIKE|`370d1b3f87f4465ab7446e23b8852ae4`|`live-5000.json`|

The original failed100-vehicle job `e226e776595e4c3b91e34f69a4ff3ae1` remains FAILED. Do not use it as a completed run. Its Table source-resnap failure and correction are documented in the implementation/backend reports; no assertion was weakened.

## 4. API acceptance and no-repeat recovery

Readiness and runtime:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8021/api/v3/simulation/jobs/runtime'
Invoke-RestMethod 'http://127.0.0.1:8021/api/v2/regions/nvmr-bac-ninh-core/modes'
Invoke-RestMethod 'http://127.0.0.1:8021/api/v4/simulation/jobs'
```

Reaudit an existing result first; this avoids generating a duplicate benchmark:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/validate_regional_api.py --base-url http://127.0.0.1:8021 --job-id 370d1b3f87f4465ab7446e23b8852ae4 --output build/r1a/reopen-5000-audit.json
```

Create a fresh small synthetic run only when new evidence is needed:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/validate_regional_api.py --base-url http://127.0.0.1:8021 --total-fleet 20 --bookings-per-region 12 --seed r1a-live-20-v1 --output build/r1a/new-live-20.json
```

The same verifier supports `--total-fleet 100`/`500` and explicit `--car-per-region`; large workload commands and exact metrics are recorded in the report. It measures independent counts/KPI/route identities, output bytes and sampled API/worker memory. It is not a browser benchmark.

Missing GIS stage recovery is covered in [R1A_GIS.md](R1A_GIS.md). The current Bac Ninh graph/extract/render stages are already verified: do not rerun preprocessing. If an artifact changes, inspect hashes/manifests/incomplete markers and choose a deliberate isolated namespace instead of overwriting it. The independent routing validator uses its own source hash in readiness; editing that validator requires revalidation, not graph rebuild.

## 5. Tests and resource inspection

Run source checks sequentially; never combine full regression/stress/WebGL measurement with graph preprocessing.

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
```

For the opt-in local HCM/Hanoi/OSRM checks, ensure local mode readiness first, then set `$env:RUN_REAL_DATA='1'` and run pytest. Final R1a executed results are in the report; remote GitHub Actions was not run.

Lightweight resource commands:

```powershell
docker stats --no-stream
.\.venv\Scripts\python.exe -c "from scripts.m3_resources import memory; import json; print(json.dumps(memory()))"
```

Optional existing read-only sampler for a new resource question (not required to resume completed work):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Profile-GsmMemory.ps1 -Seconds 5 -IntervalMs 1000 -Label r1a-manual -Output build/r1a/memory-manual.json
```

The sampler command is an existing diagnostic; R1a capacity evidence comes from the actual live/domain reports, not from an unexecuted manual example. In the UI, **Đo render regional** captures five seconds in the selected region. The5,000-total run displays2,500 vehicles when one region is selected; do not relabel that as5,000 individual icons. Save the run/region/profile context with any benchmark. A short low-RAF capture is not proof of a new R1a cause or a completed M4 performance fix.

## 6. Stop only task-owned services

Current successful task startup receipt:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Stop-GsmDev.ps1 -ReceiptPath 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox\build\s0-runtime\session-20261018-141504-780.json'
```

Before stopping, wait/cancel all QUEUED/RUNNING jobs. The script verifies receipt path/workspace, PID/executable/start UTC instant, command line and allowed Python child before any termination; it refuses stale/mismatched identities. The prior task receipt was used successfully to stop/restart only R1a-created services. The source correction handles Windows PowerShell UTC parsing/trailing whitespace without lowering identity checks.

The receipt does not own historical Owner services or Docker containers. It will not stop Hanoi routers or the Owner's separate API/frontend. Do not select processes solely by a generic name or use an unrestricted process-tree kill. Bac Ninh CAR/MOTORBIKE and the HCM regression container were task-created; leave verified graph files intact if deliberately stopping their named containers after inspecting image/mount/labels. Starting completed replay does not require running those routers again.
