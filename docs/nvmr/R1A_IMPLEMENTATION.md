# R1a — Hanoi + Bac Ninh Regional Foundation

> **Historical / Superseded direction (R1b, 19/10/2026):** The current target is Unified Connected NVMR: one connected CAR graph, one independent MOTORBIKE graph, one global engine/fleet/dispatch/clock and unified viewport. Independent N-region R1b expansion is superseded. This historical document retains its original evidence, metrics and limitations; it does not establish cross-province dispatch. See [current implementation](R1B_CONNECTED_IMPLEMENTATION.md), [runbook](R1B_CONNECTED_RUNBOOK.md) and [recovery checkpoint](R1B_PROGRESS.md).

Technical integration report, 18/10/2026, Asia/Saigon. This file is updated from executed evidence; the recovery checkpoint is [R1A_PROGRESS.md](R1A_PROGRESS.md). Domain details are in [R1A_BACKEND.md](R1A_BACKEND.md), GIS details in [R1A_GIS.md](R1A_GIS.md). Synthetic allocations, bookings and modeled durations are not observed GSM operational data.

## A. Current verified state

Initial source: clean `feature/nvmr-m0-architecture`, HEAD `43a6d09be2252c44743f9e78a429a3ed700502c1`. R1a is an unstaged implementation in the primary checkout. No stage, commit, push, merge or rebase has been performed. Historical M3/M4 worktrees are untouched. The owner explicitly closed M4 optimization; this implementation does not reopen the historical 1 FPS investigation.

| Capability | Evidence-backed state at this report checkpoint |
|---|---|
| Regional contract/backend | Implemented: separate v4 envelope, both regional allocations, same existing queue/worker, isolated contexts and immutable results |
| Hanoi v3 | Public configuration and scientific engine unchanged; incompatible regional job IDs return 404 in v3 |
| Frontend | Integrated through existing GSM Simulation navigation; scenario selector, allocation, overview, drill-down, selected journeys and common clock |
| National PBF | Reused and verified; snapshot 2026-10-09T20:21:04Z, SHA-256 below |
| Bac Ninh extract/render/CAR | Built and verified in isolated namespace, local CAR service :5003 |
| Bac Ninh MOTORBIKE | Built/served :5004 after resource recovery; independent generated/source-node/OD/boundary validation PASS; both Bac Ninh modes READY |
| Full backend source checks | Final artifact-free267 PASS /6 SKIP,22.62s; opt-in local GIS/OSRM273 PASS,50.53s; one dependency deprecation warning |
| Full frontend tests | Final189 PASS /23 files,33.24s |
| Typecheck/build | PASS; MapLibre chunk-size warning remains |
| Live regional scenario |20/100/500/5,000 PASS, persisted/reopened; real RUNNING cancellation stays CANCELLED/result409 |
| Browser | UI-created20, four region/mode journeys, common clock/global search, overview native drill-down and persisted replay observed; source/cluster correctness PASS in short captures; low RAF cadence recorded |
| GitHub Actions | NOT RUN remotely; local artifact-free workflow commands exercised |

The six artifact-free skips require explicit real GIS/OSRM integration opt-in; the273 opt-in run exercised them. They are not silently counted as PASS in the267/6 result. Historical reports and initial R1a248/6 backend,188 frontend checkpoints retain their own dates/results; no historical M4 performance number is used as R1a capacity proof. Final lint:0 errors/46 warnings, including existing and new hook warnings.

## B. Geographic scope and provenance

The label **Bắc Ninh Core · technical pilot** describes a designed rectangular study area around the former Bắc Ninh urban center and neighboring roads. It does not claim the whole post-2025 province. Administrative context, authoritative links and the distinction from the former Bắc Giang area are documented in the GIS report. The versioned technical rectangle itself comes from the checked-in server configuration, not from an administrative boundary polygon.

All coordinates are WGS84 `[longitude, latitude]`.

| Coverage | Bbox `[west,south,east,north]` | Meaning |
|---|---|---|
| Operating | `[106.02,21.15,106.10,21.21]` | Road-derived candidate anchors, synthetic demand and initial fleet |
| Viewport | `[106.00,21.13,106.12,21.23]` | Initial detailed map fit |
| Render | `[105.995,21.125,106.125,21.235]` | Actual local geographic layers |
| Routing | `[105.96,21.09,106.16,21.27]` | Buffered graph allowing local detours |

Technical boundary version: `technical-rectangle/2026-10-18`. No official administrative polygon was substituted for this rectangle. Overview outlines display the operating extents supplied by the server registry; the UI explains their technical nature. Routes outside the loaded render rectangle may be valid inside routing coverage; absence of drawn roads outside render coverage is not evidence that the route is fabricated or that those roads are loaded.

National source `data/raw/vietnam-latest.osm.pbf`: 330,248,138 bytes, SHA-256 `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`. Header bounds `[102.095945,7.382239,114.642323,23.402135]` include the entire routing rectangle. Snapshot metadata is read from this file; a current Geofabrik download page does not change the snapshot date of the reused file.

Extract `data/regions/nvmr-bac-ninh-core/extracted/coverage.osm.pbf`: 3,229,117 bytes; SHA-256 `5b18bc568bb2afd3a4914b97b89084663e7a1e72a84364367cb42eac7f7c3ebb`. Extract has 392,274 nodes / 60,618 ways / 275 relations and no missing node refs in the executed `check-refs` check.

Excluded: full new Bắc Ninh province, most former Bắc Giang territory, other NVMR provinces, continuous road coverage between the pilot areas, and any claim of calibrated operational catchment/demand.

## C. Regional GIS and local routing

Separate namespace: `data/regions/nvmr-bac-ninh-core/`. Hanoi/HCM graph, source, extract, render, configuration and profile contents are not moved, rebuilt or replaced. Existing Hanoi config/profile/validator bytes stay unchanged. Artifact capture contains actual output hashes and explicit preservation scope; there was no pre-task exhaustive hash inventory of every ignored historical graph file, so that stronger preservation claim is not made.

Final safe-reuse review also removed an inherited MOTORBIKE-serve rewrite of identical router proof: the final pipeline preserves both bytes and mtime when proof matches and refuses a changed proof. Actual Hanoi/Bac Ninh MOTORBIKE serve reuse preserved both hashes/mtimes (`router-proof-preservation.json`); current Hanoi proof SHA-256 `30747c76a803c43e7dbebe34fe77559564ebed4a06c3af05fce51b24af495a2473` also matches the archived M2 proof byte-for-byte. Earlier inherited serve calls could refresh that proof's mtime while keeping its bytes; the broader claim of never touching any ignored artifact metadata is therefore not made. Graphs, source/extract/render and Hanoi config/profile/validator identities were not rebuilt or changed.

Real local render layers contain 15,594 streets, 701 water features, 430 green features, 19,908 buildings and 55 places, about 11.5 MB of the five served GeoJSON layers. Overview does not download those layers; drill-down downloads only the selected region's five geographic sources.

| Mode | Port | Basename | Profile |
|---|---|---|---|
| Hanoi CAR | 5001 | Existing Hanoi basename | Existing car profile/evidence |
| Hanoi MOTORBIKE | 5002 | Existing Hanoi motorbike basename | Existing independent motorcycle profile/evidence |
| Bac Ninh CAR | 5003 | `bac-ninh-core` | OSRM `/opt/car.lua`, MLD |
| Bac Ninh MOTORBIKE | 5004 | `bac-ninh-motorbike` | `/profiles/motorbike.lua`, MLD; separate graph/evidence |

Region identity pins the server config hash and pipeline version. Mode identity pins region, mode config hash, root profile and assumptions hashes. Published routing identity additionally pins graph manifest, source/extract hashes, profile class and MLD algorithm. Container serve verifies pinned image, graph path, read-only mount, loopback port and graph-specific nearest hints. Merely answering HTTP nearest is insufficient for readiness.

Pipelines reuse verified input/extract/render/graph bytes and refuse corrupt, stale or incomplete outputs. `.incomplete` / `.validation-incomplete` prevent accidental READY publication. Changing source/config/profile requires deliberately isolated new artifacts; the pipeline does not overwrite the old graph to fix a mismatch. The CAR/MOTORBIKE commands and independent validation sequence are in the runbook/GIS report.

Independent acceptance must include directed OD geometry, source-node one-way checks, Table/route agreement, bounded snaps, NoRoute/NoSegment, generated access/barrier/turn fixtures and graph identity. OSM/profile evidence does not prove current legal signage, all conditional access restrictions or live traffic. See final evidence section for which commands actually ran.

Final Bac Ninh routing proof:58 generated profile cases PASS;552 directed non-diagonal pairs per mode; CAR46 unreachable pairs (8.33%), MOTORBIKE0; eleven reachable CAR full geometries plus one explicit NoRoute and twelve MOTORBIKE full geometries; two exercised source-node one-way examples per mode; all four operating-corner route samples per mode and bounded NoSegment PASS. A separate bounded CAR comparison checked all552 Table/route pairs with zero duration/reachability mismatches. Detailed raw/provenance and scoped limitations are in `r1a-evidence/gis/` and the GIS report.

CAR manifest SHA-256 `4e393c9025c9b73a08d27d0aca7108071989d06e8913e7e37f534671375ddb9c`; MOTORBIKE manifest SHA-256 `86d2f963d327875a59411b87b212b038f5dd222592e5c58e513c5edfc00ef4e0`. Neither mode has a remaining incomplete marker. CAR/MB duration differences are model/profile differences, not evidence of live travel times or legal privileges.

## D. Regional simulation, API and execution

### Version boundary

Request `gsm-nvmr-regional-scenario/v1` requires exactly the allowlisted Hanoi and Bac Ninh pilot allocations. Result is `gsm-nvmr-regional-result/v1`, model `heap-grid-regional/v1`; snapshot is `gsm-nvmr-regional-snapshot/v1`. A validated internal subclass adapts region context to the existing event engine. The public Hanoi-only v3 `SimulationConfig` and historical v1 result meanings are unchanged.

API namespace: `/api/v4/simulation/jobs`.

| Operation | Method/path suffix |
|---|---|
| Create/list | `POST` / `GET` collection |
| Status | `GET /{id}` |
| Cancel | `POST /{id}/cancel` |
| Final/persisted summary | `GET /{id}/result[?summary=true]` |
| Common-clock projection | `GET /{id}/snapshot?timeSeconds=...` |
| Immutable route | `GET /{id}/routes/{ref}` |
| Immutable selected booking | `GET /{id}/bookings/{booking_id}` |
| Selected vehicle and booking | `GET /{id}/vehicles/{vehicle_id}?timeSeconds=...` |

Regional and v3 endpoints share one bounded store and OS worker lease, but reject incompatible job schema IDs. No additional background worker starts on API import. The existing worker chooses executor from the immutable manifest schema. Queue bound and cancellation terminality apply across both versions. Result caches are keyed by immutable job ID; route references include graph/region/mode evidence, and selected details must belong to that run.

### Allocation and deterministic semantics

`TOTAL_FLEET = sum(regionalFleetSize)`; CAR and MOTORBIKE totals are likewise sums. The 5,000 limit is aggregate, not per region; booking count limit is 20,000 aggregate. Motorbike count is derived and validated against fleet minus CAR. Each region has its own online fraction/schedule, demand catalog and routing context. The preset is 10 vehicles/5 CAR/5 MOTORBIKE per region, 12 requests each, seed `r1a-synthetic-20-v1`; it is explicitly synthetic and configurable.

Allocations are canonicalized by region ID. Each region receives a stable SHA-256 subseed derived from the master seed plus region ID, independent of request array order. Vehicle/booking IDs use `${regionId}:GSM-...` and `${regionId}:BK-...`. Preparation routes, spatial index and mode caches are region-owned. No cross-region or cross-mode dispatch or CAR fallback exists.

Readiness validates every requested region/mode before API enqueue and again before worker execution. Missing graph/router/validation evidence returns a structured `REGIONAL_NOT_READY` error listing region and mode; it creates no successful partial scenario. An infrastructure error in the second region prevents publication of the first region as a completed scenario. Individual NoRoute bookings remain explicit unserved outcomes according to existing engine semantics; no synthetic straight-line geometry is supplied.

### Live-discovered source continuity issue and correction

The initial100-vehicle job `e226e776595e4c3b91e34f69a4ff3ae1` failed correctly with `ROUTER_BAD_RESPONSE`. Raw Bac Ninh MOTORBIKE Table evidence showed sources12/13 at verified position `[106.068406,21.184321]` silently moved to `[106.067787,21.184043]`, about71.235m, even though ETA dimensions/numbers were valid. Null ETAs were already supported; this was not a null parsing bug. The existing1m continuity assertion caught a real movement of a parked vehicle.

Bounded probes of that exact Table demonstrated that explicit1m source radiuses preserve all sixteen source positions, leave fourteen other ETAs unchanged and correctly return null for the two disconnected sources. V4 now uses `RegionalInstrumentedTravel` to request those1m source radiuses while retaining the configured destination threshold and all response/coverage checks. One shared LocalTravel query-construction line preserves explicitly supplied radiuses while retaining identical defaults for HCM/v3. No scientific engine, profile, geometry or assertion was weakened. The failed job/report, full response and probes remain under `r1a-evidence/backend/table-live-100-*.json` and `live-100.json`; same-seed/config fresh retry `9cca52e88d214266810f59788785b88b` PASS. Focused regional+M3+A3 after this correction:103PASS/1SKIP; final full suites are reported separately.

### Clock and KPI accounting

Regions execute sequentially to release each region's bounded routing caches before the next region. Each simulation starts at t=0. Execution wall time/preparation is recorded separately and never offsets the second region's simulation clock. The final scenario duration is the maximum regional duration, with shorter regions holding their final state for common-clock replay. No events or fabricated movement are appended to extend them.

Counts sum exactly across regions. Snapshot state accounting retains `total = offline + online`, `online = idle + assigned + onTrip`; moving is a subset of assigned/onTrip. Final booking counts are distinguished from playback-time fleet states. Pickup waits aggregate sum/count; utilization aggregates busy/online/fleet vehicle-seconds before division. Per-mode KPI evidence is included. Averages of regional averages are not used.

### Persistence and cancellation

The existing atomic write/lock store publishes complete result/event files before COMPLETED status. Cancelled jobs cannot resurrect when a late executor returns. Worker restart marks abandoned RUNNING work INTERRUPTED; a new explicit POST creates a retry with preserved inputs/config. R1a does not promise exact instruction-level simulation resume after a crash. Completed results reopen without live OSRM rerouting; the local map API is still needed for geographic assets on a fresh page.

## E. Frontend and product flow

Existing website → **Mô phỏng quy mô lớn** → **Kịch bản mô phỏng** → legacy Hanoi v3 or regional Hanoi+Bac Ninh. The default remains Hanoi; the choice is reflected by `scenario=regional`, with Back/Forward restoration. Existing HCM Single/Fleet/Booking/Voucher/Saved navigation remains in the same application.

The regional form exposes per-region fleet/CAR/request/online allocation and shared seed/horizon/wait; totals are visible and the aggregate cap is validated. Job status/progress, cancellation, persisted run opening, structured errors and API/worker lease status are surfaced. A lost POST is not retried automatically. Leaving a scenario does not cancel its persisted job; the UI tells users to retain the run ID.

Overview uses technical extent polygons plus local packaged font labels and per-region CAR/MOTORBIKE counts. No road assets are loaded for overview, no fake network is drawn between regions, and no static image replaces GIS data. Region controls and clickable extents drill down to one region. One MapLibre instance survives style swaps; only selected region assets and fleet projection are loaded. Existing native M4 clusters/silhouettes/state badges and S1 journey layers are reused. There are no per-vehicle DOM markers or full-fleet routes.

There is one playback clock for both region snapshots. Switching view does not reset the run, time, global counts or seed. Global ID search can move to a vehicle's owning region. Selected immutable booking details load at most pickup/trip geometry; the active leg changes with state and shows pickup/dropoff, timing and progress. Stale/aborted snapshot or detail responses cannot replace newer selections/runs/seeks. Paused unchanged time does not repeatedly download snapshots. Standard/Meeting retain existing cadence policies; Meeting is not a Google Meet certification.

Keyboard controls use labelled inputs/selects/buttons, status/alert roles and the existing focus treatment. A region select duplicates map-only drill-down, and global search duplicates icon selection. Mobile reuses the current map-first Simulation layout with bounded panel inputs. Browser evidence is required separately from jsdom tests; final verification records its actual scope.

Actual browser QA used the embedded Chromium/Iris Xe surface at716×659, not independent Chrome. A responsive refinement gives the regional page map-first scrolling below900px; the final DOM had no horizontal overflow. A camera bug observed while returning from detail to overview could initially crop Hanoi. The final overview explicitly resizes and fits after style/layout transition, observes container resizes and does not refit on playback ticks. The final browser capture verifies both viewport extents contained, and a focused regression checks union bounds/resize/no playback refit/cleanup. The earlier cropped overview capture is retained as pre-correction evidence; use `browser/overview-5000-final.png` for the final state.

UI-created run `6920edfece7042dd9a98fa42c52edcf6` used20 vehicles/24 requests, seed `r1a-ui-20-v1`, horizon120. It completed19/24, with5 explicit unserved. At t100, root states total20=sum10+10 and four region/mode active journeys were inspected via global IDs. The map lifetime remained `bfe41854-6408-4b05-8c02-037d1e2a09dc` across those region switches, one canvas and0 DOM vehicle markers. Pickup/trip progress, immutable detail and native MOTORBIKE icon/selected route were observed. The screenshot/functional summary and local API audit after a real task-stack restart prove persisted recovery; they do not claim hard OS crash resume.

## F. Resource budget and operational configuration

Target: Windows, i5-11320H, 16 GB RAM, Docker Desktop Linux, Iris Xe. Existing admission policy is unchanged: startup 0.5 GiB physical; light jobs 0.5 GiB physical/1 GiB commit; routine jobs 0.75/1.5 GiB; extended 2/2 GiB within the previously documented workload envelopes. Regional API/worker apply these policies to total scenario fleet/bookings. These are admission floors, not measured peak consumption or reserved memory.

New GIS heavy preprocessing requires >=2 GiB available physical and commit headroom, Docker Linux readiness and resource inventory before work. OSRM build containers retain the existing 2 GiB limit, four CPUs; router service containers use the existing 1 GiB limit, two CPUs. Those limits are caps, not actual RSS. CAR and MOTORBIKE build sequentially, without full test/build/stress/browser benchmark concurrently. An initial MOTORBIKE attempt correctly stopped before output writes when memory dipped below the floor. No owner process was killed, no WSL/pagefile/registry/Docker settings changed, and no guard was lowered.

After test/build child processes exited, physical/commit headroom was measured at about 6.13/10.91 GiB, allowing the missing stage to resume. This is an environment change, not proof of memory saved by R1a code. Peak build/router/worker/browser evidence must be read from its own timed measurement; historical M4 RAM or FPS is not reused as regional capacity evidence.

Recommended runtime: one API, one worker/store, four local routers only while generating both-region CAR/MOTORBIKE results, one selected detailed basemap. Completed replay does not need all routers to stay running. Do not run a second worker against the same store or start duplicate frontend/API ports. Isolated verification ports are used when an owner stack is already running; task receipts identify only task-created processes for cleanup.

### Launcher and guarded stop/recovery

`Start-GsmDev.ps1` adds explicit `Regional` router selection without changing default HanoiBoth or resource floors. The four-router `-StartRouters` serve/reuse path was executed (`launcher-regional-reuse.txt`) against the existing API/worker/preview; no duplicate services or graph rebuild occurred.

The stop script initially refused a valid task receipt because Windows PowerShell DateTime subtraction compared different time kinds. It now normalizes UTC instants explicitly, handles PowerShell7 auto-parsed DateTime values and tolerates only insignificant trailing command whitespace while verifying the actual command. A real guarded task-stack stop/restart succeeded; a deliberately wrong2000UTC receipt was then rejected in Windows PowerShell and pwsh with all3 current services still alive (`stop-identity-summary.json`).

One **test setup mistake** is retained explicitly: the first attempted invalid receipt used a date parser incompatible with PowerShell7's auto-converted DateTime objects. Those nonterminating setup errors left a valid receipt, and the test stopped only the3 task-created services. The Owner's separate services were untouched. The task stack was restarted from the same persisted store; a fresh independent audit of the UI-created20 result PASS (`ui-created-20-audit-recovery.json`). The erroneous setup summary and the temporary API-audit connection refusal are preserved as `stop-identity-setup-failure.json` and `ui-created-20-audit.json`; they are not counted as application/regression PASS. The corrected test constructs/checks a literal invalid ISO timestamp and uses terminating setup errors before invoking stop.

### Executed live resource/capacity matrix

Each row is one sequential local HTTP/API/worker run with independent aggregation and route-detail audits. Horizon120; small/medium allocations are equal fleet splits with half CAR per region;5,000 has1,000CAR+1,500MOTORBIKE per region. Unserved outcomes are retained; PASS means invariants/evidence are valid, not that every request must complete.

| Total fleet | Requests / completed / unserved | Worker total incl. preparation (s) | Verifier wall (s) | Result bytes | Sampled worker peak RSS (MiB) |
|---|---|---:|---:|---:|---:|
|20|24 /20 /4|4.566|7.749|232,389|89.13|
|100, corrected retry|50 /48 /2|5.206|8.597|548,752|104.18|
|500|250 /248 /2|7.347|11.007|2,402,980|76.60|
|5,000|1,250 /1,225 /25|15.829|23.086|11,323,043|101.23|

Full run IDs, exact floats, routing telemetry and sampled physical/commit minimums are in `live-matrix-summary.json` plus the individual reports. The5,000 run's sampled minimum physical available was5,672,755,200 bytes (~5.28GiB), minimum commit headroom10,622,181,376 bytes (~9.89GiB); sampled API peak RSS72,871,936 bytes and worker106,143,744 bytes. Sampling every0.5s can miss transient peaks; lifetime peak includes earlier jobs and is labelled separately. These are not whole-browser/WSL/system-memory attribution measurements.

Domain-only5,000 is distinct: job `c6453b9aa844440ca3c40cb51a82e79c`,2,000CAR+3,000MOTORBIKE/1,000 requests,all1,000 completed,6,230,495 persisted bytes, monitored wall1.756s/CPU1.75s, sampled peak RSS87,822,336 bytes. It uses frozen synthetic directed-ring matrices with **no OSRM queries**. Do not compare its fixture outcomes with real geography as if they were the same workload.

### Browser resource/performance scope

All three short captures used the same embedded Chromium/Iris Xe renderer, Meeting presentation, region-fit zoom, five seconds playback+small pan, with no backend stress/preprocess/full regression concurrently. The one selected detailed region is Bac Ninh; root snapshots still contain both regions.

| Scenario total | Detailed source vehicles | RAF FPS | Frame p95 (ms) | JS heap used (bytes) | Cluster oracle |
|---:|---:|---:|---:|---:|---|
|100|50|1.868|1,016.5|47,095,794|PASS|
|500|250|1.855|1,016.9|50,029,043|PASS|
|5,000|2,500|1.888|1,016.5|66,718,273|PASS|

Each capture had10 MapLibre sources/20 layers,0 DOM vehicle markers,7 source updates and all selected-region source IDs represented exactly once by the settled low-zoom cluster oracle. Tab visibility/focus was true and no hidden frames were recorded. This does **not** establish smooth playback or GPU completed-frame throughput. In particular, it is not5,000 simultaneously visible individual icons; the detailed source has2,500 and was clustered. UI actions/selected journeys worked, but the measured RAF cadence is poor even at the two smaller sizes. The cause is unresolved and the owner-directed closure of M4 profiling is respected. Independent Chrome, wider desktop viewport,650px-and-smaller physical browser, Meet, long soak/leak and performance acceptance remain NOT VERIFIED.

One captured console warning reports a temporarily missing `gsm-car` image during earlier map/style loading; later native icons/journeys were observed and no fatal console error was captured in that console file. The raw timestamp is retained. Whole-process browser/GPU memory was not isolated; JS heap is not browser process RSS.

## G. Verification record

Raw evidence root: `docs/nvmr/r1a-evidence/`. Runtime stores, PBF and graphs remain ignored. Source-only GitHub Actions remains artifact-free; no workflow now downloads PBF or preprocesses graphs.

| Command/check | Executed result |
|---|---|
| `RUN_REAL_DATA=0 python -m pytest -q -rs` | Final267 PASS /6 SKIP,22.62s, `backend-artifact-free-final.txt` |
| `RUN_REAL_DATA=1 python -m pytest -q -rs` |273PASS,50.53s, `backend-live-final.txt` |
| `npm.cmd test -- --maxWorkers=1` | Final189PASS /23 files,33.24s, `frontend-tests-final.txt` |
| `npm.cmd run typecheck` | PASS, `typecheck-final.txt` |
| `npm.cmd run build` | PASS, `build-final.txt`; expected large MapLibre chunk warning |
| Focused regional/M3 backend | 58 PASS before full suite; not added to full count |
| Focused regional/map health frontend | 9 PASS before full suite; not added to full count |
| Lint | Final0 errors /46 warnings, `lint-final.txt` |
| Saved Replay package verifier | PASS9 assets, sealed artifact digest unchanged, `saved-verifier.txt` |
| Real CAR/MOTORBIKE directed route validation | PASS, GIS source/OD/profile/boundary proof |
| Live two-region20/100/500/5,000 | PASS; separate raw reports and failure/retry evidence |
| Real regional cancellation | RUNNING→CANCELLED stays terminal after2s; result409/no file;5001-total invalid422/no new job; `live-lifecycle.json` |
| Hanoi v3 live |10 vehicles/20 requests,17 completed/3 unserved; `hanoi-v3-live.json`, job `d51966759c464d34a2345ef392a2380c` |
| Domain-only5,000 | PASS, independent frozen fixture proof, `backend/domain-5000.json` |
| Browser/WebGL | Functional/cluster checks PASS in recorded scope; short low-RAF measurements are a performance limitation, not smoothness PASS |

Meaningful fixture coverage includes canonical region order/subseed determinism, global cap and identities, spatial/mode isolation, shared-clock conservation, weighted waits/utilization, NoRoute, all-mode readiness, missing/unknown/invalid configs, partial failure, cancellation/late completion, interrupt/retry/persisted reopen, v3 namespace compatibility and API event-loop heartbeat. Frontend tests verify wrong region/clock/identity/count rejection, paused polling, region selection retaining run, seek/retry preserving time, stale responses, duplicate POST and cancellation races.

Browser legacy smoke additionally reached HCM Single with dataset ready, generated Fleet5 and Booking5/20 with replay enabled, prepared the default paired Voucher experiment, and loaded Saved Replay demo with the UI's SHA-256-verification indicator. Raw accessibility captures are under `browser/hcm-*.ax.txt`. These are bounded browser smoke checks; backend source/live regressions and Saved package verification supply separate correctness evidence. No new HCM scientific outcomes/ledger model were introduced.

## H. Limitations

- Intra-region, same-mode dispatch only; no cross-province routing guarantee or transfer model.
- Technical rectangular study areas, not full administrative coverage; disconnected OSM components may produce NoRoute.
- Static OSM/profile durations; no live traffic, observed GSM fleet/demand, market share, ROI, calibrated preference/choice or legal-access certification.
- One local durable queue/worker, no production supervision/auth/retention/distributed lease or exact mid-simulation crash resume.
- No new regional Voucher Baseline/Treatment behavior, ledger changes or M5 scientific model extension.
- A domain-only5,000 PASS cannot establish live regional routing throughput or browser5,000 capacity.
- Short embedded-browser captures cannot establish independent Chrome/GPU diversity, Google Meet behavior, 30–60-minute soak/leak behavior or production readiness.

## I. GO / NO-GO decision

| Decision | Verdict and boundary |
|---|---|
| R1a functional local MVP | **GO** for the verified two technical areas: both-mode local routing, one scenario/job/clock, correct regional counts/KPI, persisted replay and native selected journeys |
| Bac Ninh GIS/routing | **GO within the documented technical coverage/model**; not full new province or legal/live-traffic certification |
| Regional simulation correctness | **GO within fixture/live workloads measured**; includes failure, cancellation, namespace/seed/isolation and independent KPI auditing |
| Multi-region MapLibre functionality | **GO for overview/drill-down/selected journeys/clusters in the captured embedded browser** |
| Laptop interactive performance | **CONDITIONAL / not accepted as smooth5,000 UI**; measured low RAF cadence, no broad browser/GPU/Meet/soak certification |
| R1b | **GO for bounded development** using the new versioned region/mode pattern and resource guards; each added area needs fresh source/coverage/router proof and owner choice |
| M5 pilot | **CONDITIONAL GO for separately scoped design/development**; no regional Voucher/choice scientific acceptance supplied by R1a |
| M6 analytics | **CONDITIONAL GO for implementation against immutable denominators/provenance**; observational calibration/analysis validity is a separate task |
| M7 local demo | **CONDITIONAL GO** when current services/data are ready and performance limitations are disclosed; deployment operations and broad UX evidence are not complete |
| Production | **NO-GO**: auth/supervision/retention/distributed failure and larger operational validation absent |

No part of this decision authorizes implementing R1b/M5, committing/pushing, or reopening M4 profiling. “MVP GO” describes the demonstrated functionality, not a blanket performance/commercial/production acceptance.

## J. Next steps and delivery

The missing MOTORBIKE stage, live scenario matrix, actual website creation/selection and current full regression are complete. Final handoff preserves raw failed/limited checks as well as successful reruns. Current task services use8021/5191 and `build/r1a/jobs`; the latest receipt/runbook, Git allowlists and checkpoint identify exactly what to preserve or stop.

R1b is not implemented here. Candidate future additions Hưng Yên, Thái Nguyên, Phú Thọ, Ninh Bình and any owner-selected area need their own administrative context/source snapshot/technical boundary, graph/profile/evidence, scenario allocation and resource envelope. Do not automatically multiply the 5,000 cap per region. M5 requires a separately authorized scientific design/validation task; M6 needs analytics definitions grounded in immutable regional numerators; M7 requires release/deployment operations and broader environment evidence.

See [R1A_RUNBOOK.md](R1A_RUNBOOK.md) for verified local commands and [R1A_GIT_DELIVERY.md](R1A_GIT_DELIVERY.md) for actual file allowlists and review-only staging/commit suggestions. These documents do not authorize the agent to stage or commit.
