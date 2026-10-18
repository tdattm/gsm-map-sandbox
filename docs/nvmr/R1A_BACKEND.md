# R1a — Regional simulation backend

Ngày: **18/10/2026**, Asia/Saigon. Phạm vi tài liệu này: contract, backend execution, persistence, API, fixture verification và live acceptance command. Trạng thái GIS/routing thật và browser thuộc báo cáo tích hợp [R1A_IMPLEMENTATION.md](R1A_IMPLEMENTATION.md); không suy ra từ fixture PASS dưới đây.

## 1. Current verified backend state

Đã triển khai `gsm-nvmr-regional-scenario/v1` và `/api/v4/simulation/jobs`, dùng **một JobStore, một bounded queue và một worker lease hiện có**. Regional jobs gồm chính xác `nvmr-hanoi-core` và `nvmr-bac-ninh-core`; mỗi vùng có fleet, service mix, demand, online schedule, context và routing evidence riêng. Một kết quả cuối và một common playback clock bao bọc hai kết quả v1 đầy đủ.

Không sửa `SimulationConfig` hoặc thuật toán scientific engine trong `simulation.py`. HCM Booking/Voucher/Replay, M2 contract và Hanoi v3 giữ contract riêng. `_RegionalEngineConfig` là subclass nội bộ có allowlist hai vùng, sử dụng toàn bộ validation/thuật toán của engine hiện tại, không dùng `model_construct`, không sửa public v3 `regionId` và không bypass validation.

Lệnh focused gần nhất đã chạy:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_regional_simulation.py tests/test_m3.py -q
```

Kết quả tại checkpoint backend: **58 PASS**, 5,04 s; một Starlette/httpx deprecation warning. Đây là focused tests độc lập GIS/PBF/OSRM. Kết quả full regression và live tests chạy sau checkpoint phải đọc báo cáo tích hợp, không cộng dồn hoặc coi số focused là số full suite. `scripts/validate_regional_api.py --help` đã chạy thành công.

Tại checkpoint viết tài liệu này, **live regional OSRM acceptance chưa chạy bởi Agent B**, đang nhường resource slot cho GIS preprocessing. Không dùng fixture result làm bằng chứng Bắc Ninh graph ready, route legal, latency thực, khả năng 5.000 live vehicles hoặc FPS browser.

## 2. Source ownership và modules

| File | Vai trò |
|---|---|
| `backend/app/regional_simulation.py` | Strict regional scenario/allocation models, stable subseeds/global identities, validated v3 adapter, result combination, common-clock snapshot, weighted KPI and summaries |
| `backend/app/regional_jobs.py` | All-region/mode preflight, sequential local OSRM executor, versioned API, immutable booking/route/vehicle selection |
| `backend/app/simulation_worker.py` | Select v3/v4 config/executor from immutable input schema, retaining one queue/lease/cancellation/publication lifecycle |
| `backend/app/simulation_jobs.py` | Same durable queue; regional job manifest version/engine label and v3 namespace isolation |
| `tests/test_regional_simulation.py` | Artifact-free two-region deterministic, lifecycle, readiness, resource and API fixtures |
| `scripts/validate_regional_api.py` | Small/medium live acceptance runner with persisted reopen, route identities, counts, common time, router metrics, output size and labelled process/system memory samples |
| `scripts/validate_regional_domain.py` | Explicit domain-only scale verifier using frozen synthetic directed-ring travel, worker publication, persisted reopen and independent KPI audit |

`main.py` registers `create_regional_router()` in the existing FastAPI application. No worker starts on import; use the same existing `python -m backend.app.simulation_worker` command/store selected by the launcher.

## 3. Request contract and synthetic allocation preset

Example: **synthetic 20-vehicle allocation**, seed `r1a-live-pilot-20/v1`. This is a reproducible technical preset, not an observed GSM fleet split.

```json
{
  "schemaVersion": "gsm-nvmr-regional-scenario/v1",
  "seed": "r1a-live-pilot-20/v1",
  "horizonSeconds": 120,
  "maxWaitSeconds": 300,
  "workload": "typical",
  "regions": [
    {"regionId": "nvmr-hanoi-core", "fleetSize": 10, "carCount": 5,
     "motorbikeCount": 5, "bookingCount": 12, "onlineFraction": 1.0},
    {"regionId": "nvmr-bac-ninh-core", "fleetSize": 10, "carCount": 5,
     "motorbikeCount": 5, "bookingCount": 12, "onlineFraction": 1.0}
  ]
}
```

`motorbikeCount` may be omitted; validated output persists `fleetSize-carCount`. An explicitly supplied inconsistent value fails validation. Fleet sizes are strict integers, 1–5.000 **per allocation subject to a scenario sum ≤5.000**; bookings are 0–20.000 per allocation subject to sum ≤20.000. The same horizon, pickup deadline and dispatch shortlist settings apply to both regions. Unknown fields/router URLs/paths are rejected. Both allocations must exist exactly once; unknown, duplicated or missing region fails before execution.

Defaults common to the scenario: horizon 900 s, max pickup wait 300 s, workload `typical`, initial candidates 16, maximum candidates 128, grid cell .005 degrees. Each allocation defaults to 10 bookings, online fraction .8, empty online schedule. Float fractions reject booleans and nonfinite values. `onlineSchedule` uses the v3 `{timeSeconds,onlineFraction}` shape, sorted unique times within the common horizon. Empty service modes are allowed, with no router required for an absent mode.

`globalTotals` is **derived output**, not trusted request input:

```text
fleetSize = Σ allocation.fleetSize
carCount = Σ allocation.carCount
motorbikeCount = Σ (allocation.fleetSize - allocation.carCount)
bookingCount = Σ allocation.bookingCount
```

API admission runs the unchanged `require_simulation_headroom` against these aggregate workload counts. The worker rechecks admission before readiness/execution. Existing light/routine/extended memory and commit floors remain unchanged. A test explicitly checks two individually light 600-vehicle/600-booking regions become a routine 1.200/1.200 scenario, so a .7 GiB available snapshot is rejected by the .75 GiB floor.

## 4. Seeds, identities and routing isolation

The scenario treats `regions` as unordered: validation sorts by stable `regionId`. Immutable input hashes therefore match for a permutation of the same request. Region seeds use:

```text
SHA256("nvmr-regional-seed/v1:" + masterSeed + ":" + regionId)
```

The same hash-counter `m3-demand/v1` input generation runs independently with each regional seed and local verified candidate catalog. Stable global IDs are generated **before** dispatch:

```text
nvmr-hanoi-core:GSM-00001
nvmr-bac-ninh-core:GSM-00001
nvmr-hanoi-core:BK-000001
nvmr-bac-ninh-core:BK-000001
```

Every region has a separate `simulate` invocation, idle spatial index, demand queue, travels map and routing contexts. The core itself keeps CAR/MOTORBIKE partitions. Region/mode router identity is checked against each requested allocation; no context/router, candidate index or geometry crosses into another region. There is no inter-region passenger trip or dispatch in R1a.

Route references retain the existing content hash over mode, graph identity and route response. The graph identity includes region and mode, preventing the same coordinate pair on different regional graphs from becoming one route. Result combination checks global identity namespaces, duplicate identities, per-region config equality, region/mode identity, routeRef dictionary key, runId and route region. Selected routes come from that job's stored region route dictionary; detail readers never call OSRM.

All mode contexts are preflighted **before any regional execution**. Missing evidence, graph/profile unready, identity mismatch or router outage returns `REGIONAL_NOT_READY` with `{regionId,vehicleType,code,message}` entries. Its human-readable message includes region/mode/reason as well, because the UI may render only code/message. Public router fallback and CAR-for-MOTORBIKE substitution do not exist.

Readiness performs existing dataset checks and graph/profile/router validation. Blocking registry/config/identity/catalog work uses `asyncio.to_thread`; a heartbeat test verifies deliberately delayed identity hashing does not starve the event loop. The executor re-reads every pinned identity after **both** regions finish; changed evidence fails the whole job. Like M3, config is immutable at enqueue, while graph/catalog identities and demand inputs are pinned at **worker preparation**, not permanently reserved at POST time.

## 5. Execution and common simulation clock

The worker executes canonical sorted regions sequentially for bounded router cache use. Each regional engine starts simulation at **zero**; wall-clock preparation/run time never shifts the next region's simulation time. Existing event priorities, FIFO dispatch, inclusive wait deadlines, busy vehicle offline deferral, route continuity checks and queue draining remain v3 behavior.

Each per-region result is a complete `gsm-simulation-result/v1` object with its own region/config, exogenous vehicles/bookings, assignments, events, immutable routes and timelines. Results are retained until both succeed; then combination sets:

```text
scenario.simulationDurationSeconds = max(regional completion durations)
each regional simulationDurationSeconds = scenario.simulationDurationSeconds
```

This holds each shorter region's final checkpoint on the common clock. It adds no vehicle motion, events, bookings or assignments. All final booking outcomes were already terminal before padding. The common duration is used consistently in utilization denominators and every regional snapshot, including online schedules after the last booking. Final outcomes can occur after request horizon because the existing engine drains accepted requests/trips.

The root event log merges regional events by simulation timestamp, region ID and original padded event ID. Each root event ID has a regional namespace. Within each region, original same-time append order remains authoritative. Root merge ordering establishes a stable global serialization; it does not create cross-region dispatch dependencies.

Result schema:

```text
gsm-nvmr-regional-result/v1
  runId, simulationModelVersion=heap-grid-regional/v1
  config, globalTotals, simulationDurationSeconds
  regions[]: complete gsm-simulation-result/v1, plus provenance and weighted kpis
  counts: Σ final booking counts
  routingIdentities: {regionId: {mode: immutable graph/profile identity}}
  events: stable common-clock merged events
  kpis: scenario and by-mode wait/utilization accumulators and ratios
  metrics: execution label, total/preparation milliseconds, eventsProcessed
  assumptions: synthetic demand, local static OSRM, intra-region dispatch, seed/clock version
```

Detailed per-region `metrics.routing` includes actual nearest/Table/Route counts, cache hits, request failures, p50/p95/total service latency and final bounded cache sizes. Metrics measure preparation/HTTP wall time separately from simulation time. The combined result avoids duplicating all route geometries at root; root events are an additional serialization of the regional events, which costs space but keeps inherited durable event-log publication compatible.

## 6. KPI semantics

Final booking `counts` sum requested, assigned, completed, unserved, pending and activeTrips from complete regional results. With the unchanged draining engine, final pending/activeTrips are zero. Final counts **are not playback-time outcome counts**.

At any playback time, snapshot counts aggregate `total`, `offline`, `online`, `idle`, `assigned`, `onTrip`, `moving`:

```text
total = offline + online
online = idle + assigned + onTrip
moving <= assigned + onTrip
global state count = Σ same-time regional state count
```

Fleet CAR/MOTORBIKE totals live in `globalTotals`, per-region config and per-mode KPIs. Global snapshot counts remain independent of UI viewport/filter.

Pickup waits use actual stored pickup minus request time for every assigned booking. `pickupWait.sumSeconds/count/meanSeconds/maximumSeconds` are available by region, scenario and mode. Global mean is **sum waits / number of pickups**, never an arithmetic mean of regional means.

Utilization integrates timeline intervals in simulation seconds through the common duration. Busy means ASSIGNED or ON_TRIP; online means all non-OFFLINE states. Outputs store `busyVehicleSeconds`, `onlineVehicleSeconds`, `fleetVehicleSeconds`, `busyFractionOfOnline` and `busyFractionOfFleet`. Global/mode ratios divide summed numerators by summed appropriate denominators. Zero denominators yield null, including a mode absent in a region. End state after a shorter region finishes remains part of its common-clock denominator.

## 7. Persistence, cancellation and interruption

The same `JobStore` holds both v3 and v4 jobs. Queue capacity is shared, and worker `claim` selects globally by creation time/ID. Regional input manifests use `gsm-nvmr-regional-job/v1` with engine label `heap-grid-regional/v1`; v3 labels remain unchanged. Status keeps immutable config/inputHash. The worker verifies the manifest hash and canonical configuration before dispatching by scenario schema.

Regional `prepared-input.json` includes scenario config and full prepared regional vehicles/bookings/catalog/graph identities. During preparation it explicitly has `complete=false`; only after both regions and final graph checks does it become `complete=true`. This is preparation evidence, not a resumable partial scientific result. The existing `status.json` is authoritative.

Atomic publication writes final event log/result before transitioning RUNNING→COMPLETED. A region failure prevents successful publication of the entire scenario. No partial result endpoint exists. Cancelling a queued/running job is terminal and cannot be undone by late completion. Cancellation is checked at preparation anchors and core event/router boundaries. An already in-flight OSRM request can finish before the next check; cancellation prevents final publication even when compute finishes late. It is not a hard process kill or streaming cancellation of OSRM computation.

On worker restart, the lifetime OS lock proves sole ownership of this store; abandoned RUNNING jobs become INTERRUPTED. Retry means **create a new job with the same canonical config**, yielding a new runId and unchanged inputHash. Old persisted completed results remain readable. Mid-region continuation is not implemented and not claimed.

## 8. Versioned API

| Method/path, prefix `/api/v4/simulation/jobs` | Behavior |
|---|---|
| `POST ''` | 202 only after strict contract, aggregate resources and all-region/mode readiness; enqueue one job |
| `GET ''` | `{jobs:[...]}` of regional jobs in the shared store, including persisted terminal runs |
| `GET /{id}` | Regional job status/progress/error |
| `POST /{id}/cancel` | Terminal cancel, preserving completed/failed/interrupted states |
| `GET /{id}/result?summary=true` | Metadata/config/globalTotals/counts/KPI/identities/per-region summaries; omits routes, events, timelines and vehicle/demand arrays |
| `GET /{id}/result` | Full immutable regional envelope, completed only |
| `GET /{id}/snapshot?timeSeconds=t` | `gsm-nvmr-regional-snapshot/v1`, global time/counts, `regions` array of valid v1 snapshots, flattened vehicles with regionId |
| `GET /{id}/routes/{routeRef}` | Existing v1 immutable route envelope, omitting internal cumulativeMeters |
| `GET /{id}/bookings/{globalBookingId}` | Existing v1 immutable booking detail with correct region/mode and pickup/trip refs |
| `GET /{id}/vehicles/{globalVehicleId}?timeSeconds=t` | Regional vehicle state/progress position, regional routing identity and active immutable booking detail if present |

Final/snapshot/detail reads before COMPLETED return 409 `RESULT_NOT_FINAL`. Unknown global IDs/refs return 404. Unassigned booking detail preserves v1 409 `BOOKING_NOT_ASSIGNED`. Time must be finite/nonnegative and clamps at the shared final duration. V4 rejects v3 job IDs; incompatible v3 endpoints reject v4 job IDs with 404. Neither endpoint can cancel the other namespace accidentally.

Readers use an idle result cache with one parsed immutable result per API namespace. Geometry loads only on selected routes. V4 vehicle detail currently computes a regional snapshot before selecting a vehicle; it is intended for sparse inspector requests, not polling 5.000 individual vehicle endpoints. Snapshots flatten vehicles for convenience and also include per-region snapshots, so HTTP snapshot payload duplicates point/state metadata; native renderer should consume the appropriate one, not create two visual copies.

## 9. Fixture verification matrix

`tests/test_regional_simulation.py` covers:

- Canonical region permutations, stable subseeds, repeated identical semantic results.
- Exact aggregate fleet bounds, derived MOTORBIKE totals, rejected inconsistent/unknown/missing/duplicate allocations, booleans, invalid schedules and client router fields.
- Public v3 remains Hanoi-only while internal adapter validates Bac Ninh.
- Separate region/mode travels and coordinate bounds, globally unique IDs, no cross-region assignment/graph/route leakage.
- Shared clock, padded shorter duration, fleet/state conservation and geometry-free point projections.
- Weighted pickup wait/utilization by scenario/region/mode, zero-denominator behavior.
- Explicit NOROUTE unserved outcomes and no mode fallback; infrastructure error in second region fails entire scenario.
- Cancellation queued/running/late-completion, interrupted worker recovery, retry new ID/same hash, persistent completed reopen, tampered immutable input refusal.
- Shared v3/v4 queue capacity and API namespace isolation.
- API create/list/summary/snapshot/selected booking/route/vehicle, invalid time/IDs, incomplete result gating.
- Missing mode readiness failure before enqueue, every requested mode checked with precise errors.
- Aggregate admission floors, asynchronous hashing heartbeat, sequential live-adapter fixture and end-of-run changed-graph refusal.

`tests/test_m3.py` additionally reruns frozen legacy golden, v3 lifecycle, route/table failures, schedules, determinism, worker locks and v3 API contracts. The broader HCM/M2/S0/Saved/full-suite result belongs to the orchestrator integration verification.

## 10. Live API acceptance and resource measurements

Reuse the existing launcher/store with one API/worker and all region/mode routers requested by the run. Run the following **sequentially**, only after GIS releases its heavy-processing slot and readiness is verified:

```powershell
.\.venv\Scripts\python.exe scripts/validate_regional_api.py --base-url http://127.0.0.1:8000 --total-fleet 20 --bookings-per-region 12 --output build/r1a/regional-20.json
.\.venv\Scripts\python.exe scripts/validate_regional_api.py --base-url http://127.0.0.1:8000 --total-fleet 100 --bookings-per-region 50 --output build/r1a/regional-100.json
.\.venv\Scripts\python.exe scripts/validate_regional_api.py --base-url http://127.0.0.1:8000 --total-fleet 500 --bookings-per-region 125 --output build/r1a/regional-500.json
```

The default equal split allocates half each regional fleet to CAR and the remainder MOTORBIKE; odd total fleets preserve exact sum. `--fleet-per-region` and `--car-per-region` permit explicit alternatives. These are synthetic examples. `--job-id <id>` reopens an already-created job without repeating scientific work; timeout/failure preserves the job and reports its ID for recovery.

The verifier waits for completion, audits full per-region lifecycles, independently recombines counts/weighted KPIs directly from bookings, assignments, terminal events and timeline intervals (without calling production `combine_regions`), checks three common-clock snapshots, selects at least one assigned booking per requested region/mode, reads full immutable pickup/trip routes, verifies geometry cardinality and positive distance/duration, and confirms run/region/mode/profile identity. A stationary pickup may correctly omit its zero-duration route. A requested mode with no assignment causes acceptance failure rather than silently skipping route evidence. Domain fixtures are rejected as live evidence unless they actually use the expected MLD CAR/MOTORBIKE identity shapes.

The JSON report includes API result byte length, per-region routing request/failure/cache/latency metrics, wall time, API/worker RSS samples, process lifetime RSS peak, minimum available physical/commit headroom and sample counts. Sampling is at .5 s while polling; it can miss transient peaks. Lifetime peak may predate the measured run. `resourcesBefore/After` describe the verifier process and system; they must not be labelled worker RSS. The command only inspects existing local processes/services and never starts/stops/reconfigures them.

This command does **not** certify NoSegment/NoRoute/access/barrier/one-way fixtures, endpoint snapping thresholds, browser interaction/FPS, observed traffic, legal road access or 5.000-vehicle live capacity. Those require separate GIS/browser evidence. Artifact-free domain 5.000, live OSRM 5.000 and browser render 5.000 remain separate claims.

## 11. Limits and recovery boundary

R1a backend correctness fixture GO does not imply full geographic MVP GO. Both real regions and requested modes must pass live readiness/selected-route/scenario verification for regional acceptance. The namespace denotes a Bac Ninh **technical pilot**, not full 2026 province coverage. Synthetic demand is uncalibrated, OSRM durations are static, dispatch is intra-region and mode only, and there is no new Voucher model.

There is one local queue, one worker and atomic JSON persistence, with no production supervision/auth/distributed scheduling/retention guarantees. Readiness checks can be expensive because they verify local evidence; IO is offloaded, not omitted. Worker cancellation cooperates at request/event boundaries. Partial computation restarts as a new run rather than resuming an event heap. Small fixture inputs do not establish maximum retained history or memory under all 20.000-booking schedules.

Recovery: retain source changes, existing graphs, `input.json`, `prepared-input.json` markers, status and completed `result.json`. Read [R1A_PROGRESS.md](R1A_PROGRESS.md), recheck actual Git/service/manifest state, reuse valid artifacts and completed run IDs, then run the next missing acceptance step. No stage, commit, push or graph cleanup is performed by the backend workstream.

## 12. Recovery review and additional verification

The resumed backend review found no confirmed defect in production regional clock, mode isolation, persistence or cancellation paths. It did identify an acceptance-evidence weakness: the initial verifier reused production aggregation as its audit. The verifier now reconstructs region/scenario/mode counts, pickup waits and utilization from raw histories using a separate implementation; six mutation cases prove it rejects corrupted global mean, mode utilization, regional wait, mode totals, region run identity and region config.

A dedicated schedule regression has a shorter region switch online at t=8, a second region start a 20-second trip at t=9 and request offline while busy at t=10. At common t=29, the shorter region contributes 21 online vehicle-seconds and the busy region contributes 29; the trip stays active at t=15 and finishes offline at t=29. Root event projection preserves each region's original event order.

Executed after recovery:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_regional_simulation.py -q -k 'common_clock_holds or independent_acceptance'
```

**7 PASS, 33 deselected**, 0.47 s. These are seven new focused cases; the earlier 58-test checkpoint and orchestrator's full-suite result are separate executions. No scientific v3 engine code changed during this review. An intermediate fixture-only tuple/list comparison in the new verifier failed, was corrected by validating the configuration model before equality, then all seven final cases passed.

The new domain-only scale command and its `--help` were verified. Execution ran once after the GIS agent released its preprocessing/validation resource slot:

```powershell
.\.venv\Scripts\python.exe scripts/validate_regional_domain.py --total-fleet 5000 --total-bookings 1000 --output docs/nvmr/r1a-evidence/backend/domain-5000.json
```

**PASS** — job `c6453b9aa844440ca3c40cb51a82e79c`; retained evidence [backend/domain-5000.json](r1a-evidence/backend/domain-5000.json). Exact synthetic allocation: 2.500 vehicles per region, 1.000 CAR + 1.500 MOTORBIKE per region, 500 bookings per region, horizon 900 s, initial online fraction .8, no schedule transitions. All 1.000 bookings completed; pending/active final counts were zero. The common drained duration was 1.342,193 simulation seconds. These workload-specific outcomes do not establish real service quality.

Measured worker/publication/reopen/audit interval: wall **1.756 s**, CPU **1.750 s**, sample interval .05 s (27 samples). Sampled peak process RSS **87.822.336 bytes**; OS lifetime process RSS peak **95.408.128 bytes**. Minimum available physical memory **6.590.242.816 bytes**, minimum commit headroom **10.947.182.592 bytes**. Serialized persisted result **6.230.495 bytes**, containing 5.000 regional events plus the root merged event serialization. The command's full process elapsed time was 2,687 s; monitor wall time covers the bounded workload and audits, not interpreter startup. RSS describes this domain runner/embedded worker process, not API/server RSS, Docker or browser memory.

It uses one ordinary worker lease and an isolated `build/r1a/domain-jobs` store, saves the immutable result, reopens it through a new store instance, verifies IDs/state conservation/common snapshots and audits weighted KPIs. The frozen synthetic M3 ring graph is duplicated as separate regional travel contexts. Its geometry is not proof of Hanoi/Bac Ninh coverage. This is **5.000-domain fixture PASS** only; 5.000 live OSRM and browser acceptance require separate evidence. Do not repeat this verified benchmark merely to recover another interrupted session.

## 13. Live 100-vehicle Table failure and bounded correction

The first 20-vehicle live run passed, but the first 100-vehicle run with seed `r1a-live-100-v1`, 25 bookings per region and horizon 120 s failed honestly as `ROUTER_BAD_RESPONSE`. The failed run `e226e776595e4c3b91e34f69a4ff3ae1`, incomplete prepared-input marker and [original live-100 report](r1a-evidence/live-100.json) are preserved. This failure is distinct from the earlier artifact-free review and is not relabelled PASS by fixture tests.

One bounded diagnostic replay used the already persisted Bac Ninh inputs and the same local MOTORBIKE graph. In a 16-source Table request, sources 12 and 13 represented vehicles at `[106.068406,21.184321]`, already verified by Nearest. OSRM returned `Ok` and finite ETA 386 s while moving those sources to `[106.067787,21.184043]`: **71,235 m** displacement (OSRM reported 71,272 m). The existing one-meter vehicle continuity assertion correctly rejected the response. All ETA dimensions/types and the destination snap were valid; this was not a null/NaN parsing problem. Full request, response and per-source checks: [table-live-100-diagnostic.json](r1a-evidence/backend/table-live-100-diagnostic.json).

Read-only probes of the exact same request established that one-meter source radiuses preserve all source coordinates and return `null` for the two disconnected source ETAs, with all other 14 ETAs unchanged. Pinning the Nearest hints gave the same null outcomes; `snapping=any` still displaced the sources. Evidence: [table-live-100-probes.json](r1a-evidence/backend/table-live-100-probes.json). This is consistent with OSRM selecting a different reachable component when permitted to snap widely; the concrete evidence is the coordinate shift and the bounded-query response, not a legal-access conclusion.

Correction:

- `LocalTravel.service` preserves explicitly supplied `radiuses`; all existing callers retain the same configured-radius default.
- `RegionalInstrumentedTravel`, used only by v4 regional execution, sends radius 1 m for each already verified vehicle Table source and the existing configured snap radius for its destination.
- The original one-meter response assertion, coverage checks, ETA validation, null-disconnected behavior and full-route confirmation remain active. A response that violates the tighter query still fails. No vehicle position, mode profile, scientific v3 engine or frozen fixture is rewritten.

Verification after this correction:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_regional_simulation.py tests/test_m3.py tests/test_a3.py -q
```

**103 PASS, 1 SKIP, 7,69 s**, one Starlette/httpx deprecation warning. Additional adapter regressions prove default-radius compatibility, explicit-radius preservation, null disconnected ETAs, no vehicle-position mutation, cache reuse and continued refusal of a shifted source. The skip is the existing opt-in live A3 test. Fresh live retry needs the task-owned API/worker to load the corrected source; its job ID and acceptance result belong to the orchestrator integration report. These tests alone do not turn the failed live run into a successful regional scenario.
