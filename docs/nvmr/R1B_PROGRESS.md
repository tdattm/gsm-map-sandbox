# R1b Connected NVMR — recovery checkpoint

## Latest verified state — 19/10/2026 09:46 Asia/Saigon

This section supersedes earlier in-progress state descriptions, while preserving their evidence below.

| Part | State verified on resume | Evidence / remaining work |
|---|---|---|
| GIS coverage/source/extract | DONE | Existing source+extract hashes and five-relation coverage proof; no extraction rerun |
| CAR graph | DONE file integrity / PARTIAL live acceptance |26 hashed files,1,710,038,464 bytes, correct pinned profile/binary/source/extract; no rebuild |
| MOTORBIKE graph | DONE file integrity / PARTIAL live acceptance |26 hashed files,1,714,422,808 bytes, independent profile; no rebuild |
| Offline basemap | PARTIAL / active native renderer |Geometry complete558.9MB, errors{}; z6/7/8 tiles complete; z9–13 pending. Incomplete attempts preserved, final manifest not yet published |
| Routing validation / snapped anchors | NOT STARTED live |Routers stopped; new live OD/profile/source-node proof and snappedcatalog still needed |
| Global engine / distribution / independent demand | DONE source+focusedfixtures / PARTIAL acceptance |One global engine, exact5000allocations; liveworld evidence pending |
| v5 API/contracts/persistence | DONE source+focusedfixtures / PARTIAL acceptance |Worker/store integration, strict version boundaries; livecompletion/reopen/cancel pending |
| Frontend | DONE source+focusedfixtures / PARTIAL acceptance |Connected selector/map/session/inspector/playback; actualmap/browser pending |
| Full tests/benchmark | PARTIAL |Backend315PASS/6SKIP; frontend208PASS; typecheck/lint/build/replaypackagePASS; domainbenchmark running; live scales/browser pending |
| Documentation / M5 handoff | PARTIAL |Reports/runbook/contract drafted; final evidence+engineeringhandoff required |

- Initial resume found no surviving task processes. Native renderer now active under GIS recovery; Docker Desktop remains normally stopped to preserve RAM. No API/worker/frontend services yet.
- Both graph verifiers were executed against current bytes on resume and passed. Source/extract/config identities retained; no heavy rebuild triggered.
- Available physical RAM initially0.62GiB, then1.35GiB; ordinary idle Docker shutdown recovered>4GiB. Guards remain unchanged; no ownerChrome/app process is terminated.
- Full backend315PASS/6SKIP/1warning89.76s (`build/r1b-backend-tests-final.txt`); frontend208PASS70.23s (`build/r1b-frontend-tests.txt`). Lint0errors/53warnings, including7new-connectedwarnings; buildPASS2.38s Vite stage with chunk-size warning. ReplaypackagePASS9assets, browserExportsNOT_RUN. Source checks are distinct from live acceptance.
- New GIS agent owns only connected GIS scripts/artifacts/report and will validate C++ filter ordering using a tiny relation fixture, preserve interruptedattempt2, then resume missingrender only when guardpasses.
- No stage/commit/push/merge/reset/checkout/worktree operation performed.

Date: 2026-10-18 (Asia/Saigon). **Implementation in progress; acceptance NOT YET established.**

## Scope and preserved baseline

- Confirmed clean working tree, branch `feature/nvmr-m0-architecture`, HEAD `cd0bd26abd5c2ff83843d15a4555ba89f9d83b3f` before edits.
- Target replaces the proposed independent N-region R1b expansion: one connected graph per mode, global engine/fleet/dispatch/clock/playback. Historical R1a v4 remains isolated and unchanged in meaning.
- No branch/worktree/stage/commit/push/merge/rebase/reset/clean. Historical M4 FPS work stays closed.
- Synthetic research fleet/demand; no claim of observed GSM operations.

## Current workstreams

- PARTIAL — connected GIS/source/coverage/vector tile pipeline and separate CAR/MOTORBIKE namespace. Agent owns new connected GIS scripts/config/artifacts; heavy stages strictly sequential.
- PARTIAL — v5 global simulation/domain/jobs/road-based distribution and fixture acceptance. Backend agent owns `backend/app/connected*.py`, focused tests and domain benchmark script.
- PARTIAL — unified frontend through existing scenario selector, native MapLibre layers, v5 session/replay. Frontend agent owns connected components/modules plus `simulation-workspace.tsx` and `map-style.ts`.
- PARTIAL — root integration in main/worker/store, compatibility checks, documentation migration and end-to-end acceptance.

## Environment evidence

- National PBF present, 330,248,138 bytes; digest/header verification in GIS workstream pending.
- Docker CLI present at per-user Docker Desktop install. Initial daemon probe failed: missing `dockerDesktopLinuxEngine` named pipe.
- Started installed Docker Desktop normally with hidden window; no Docker/WSL/pagefile changes. Daemon recovery not yet verified.
- Initial physical RAM: 16,948,453,376 bytes total / 4,816,769,024 available; commit headroom 8,865,386,496 bytes; workspace disk free 44,543,008,768 bytes.
- No heavy GIS stage completed at this checkpoint. No new graph/tiles/run artifacts claimed.

## Tests / services / open issues

- Tests NOT RUN yet. Existing R1a/M3/M4 evidence is historical, not R1b proof.
- Task-started service: Docker Desktop application only; API/worker/frontend not started yet.
- Critical pending proof: full five-province coverage, connected artifacts, real cross-province routing/dispatch, 5,000 live execution, browser replay.

## Resume exactly

1. Read this checkpoint and `git status --short`; retain all present uncommitted R1b work.
2. Inspect connected source/config and evidence before launching anything; do not duplicate an active GIS job or worker.
3. `docker info --format '{{.OSType}}'` and resource inventory; reuse validated artifacts only.
4. Finish v5 integration and focused tests, then sequential full checks and real/browser evidence when artifacts permit.
5. Update this file after each substantive phase with actual commands, artifact identities and remaining blockers.

## Phase 1 checkpoint — 2026-10-19 Asia/Saigon

- DONE: actual national PBF SHA-256 matches R1a; header timestamp `2026-10-09T20:21:04Z` verified. Docker Linux recovered by ordinary Docker Desktop startup.
- DONE: connected routing extract `[104.25,20.05,107.35,22.95]`, SHA-256 `3243998cec519953323d369e4b569631edc7bef9a4fd4765c7b1e761c22a11f2`; 16,081,232 nodes / 1,719,773 ways / 10,135 relations; check-refs zero missing nodes.
- Extract manifest: `data/regions/nvmr-connected/extracted/coverage.osm.metadata.json`; config SHA-256 `3b3204d0f2c1fff08ba4677b1e39ecdc453781d55e6065dc05bfe15d96cc7372`.
- Resource limitation: extract wall21.98s; wrapper process peak RSS51.5MB; host physical minimum26,218,496 bytes and commit headroom minimum1,843,888,128 bytes. This is severe transient system pressure; the wrapper RSS is not Docker/OSRM memory. CAR build subsequently admitted with3.01GiB free physical/4.50GiB commit and unchanged2GiB container cap. Build in progress; no successful graph claimed.
- PARTIAL source implemented: connected v5 domain/jobs/context, one global engine, exact allocations/demand/distribution, unified frontend and map style/session; root worker/store/main integration, separate MBTiles transport and Connected launcher option.
- Historical/Superseded banners added to M0 target/assessment/plan and R1a implementation/backend/GIS/runbook/progress; original evidence and metrics retained.
- Executed focused tests: backend connected domain+integration19 PASS; root worker/store integration5 PASS (overlapping subset, do not sum as independent suite). Frontend connected16 PASS across3files; typecheck PASS; lint exit0 with warnings. Full suites/build/replay NOT RUN yet.
- Root added `scripts/validate_connected_api.py` (live run/reopen audit+independent numerator reconstruction); not yet run against real connected routers.
- Services: Docker Desktop running; connected CAR preprocessing in progress under GIS agent. No R1b API/worker/frontend stack yet.
- Next: finish sequential CAR/MOTORBIKE/artifact validation, render/anchors; run broad checks when heavy slot free; start `Start-GsmDev.ps1 -Routers Connected ...` only after graphs verify; actual live/browser acceptance still pending.

## Phase 2 checkpoint — 2026-10-19 Asia/Saigon

- DONE: all five administrative relation extents audited from real PBF with zero missing ways/nodes. Evidence `data/regions/nvmr-connected/coverage-evidence.json`. Hưng Yên offshore boundary south20.0771551 required map south correction20.15→20.06; routing south20.05 was already sufficient. Map now `[104.35,20.06,107.25,22.85]`.
- Config frozen SHA-256 `c815a2d299193161a19fff43b66bcc71a79dd78a912c165f5be6377f6a1a2aa1`. Previous config/source/extract proofs preserved under `data/regions/nvmr-connected/audit/map-coverage-correction/`; current metadata explicitly records migration and unchanged source/extract bytes/routing extent.
- Initial CAR attempt was deliberately stopped for sustained memory pressure, exit137 caused by task stop, NOT provenOOM. Preserved under `routing/car-interrupted-attempt-1/`, including incomplete marker and logs.
- DONE: full CAR MLD build, same coverage, unchanged2GiB cap, explicit2threads. Tool wall times extract180.685s / partition75.31s / customize22.75s. Manifest `data/regions/nvmr-connected/routing/car/manifest.json`; exact hashes copied to tracked GIS evidence at final capture.
- MOTORBIKE graph now building sequentially with its real profile. CAR live routing validation NOT YET run; graph existence is not live readiness.
- Backend connected context/domain/jobs and API implemented; strict catalog/schema/source/extract/config/boundary checks plus current graph/profile/validator evidence. Worker cancellation/failure/interruption/namespace tests exist. Independent live audit checks numerators, ratios, bymode and selectedjourney evidence.
- Frontend connected19tests PASS plus18focused historical regressions PASS, typecheck PASS. Meetingprofile initialization/cadence now honored; map south20.06 synchronized.
- Added strict v5 JSON request schema + contract, current implementation draft/runbook, README and historical/superseded direction banners. Do not interpret draftreport as finished acceptance.
- Root tiletransport2PASS; rootworkerintegration5PASS; backend latest reported30connectedtests total include those5, not additive separatecounts. Fullcombinedrun pending. Additional independent audit tamper tests written but not yet executed.
- Services: Docker Desktop + one task-owned MOTORBIKE build container; no R1b API/worker/frontend started. No unrelated process/container stopped.
- Next: finish MB, then render/anchors/serve/independent validation+snapping; once heavy slot free run source suites/domainbenchmarks/live scales and browser smoke. Preserve original graph attempts and rerun only necessary stages.

## Phase 3 checkpoint — graph builds complete, native tiles in progress

- DONE: MOTORBIKE independent MLD graph, profile motorbike.lua; extract249.83s / partition68.33s / customize21.59s. Both connected graphs now exist with content manifests; neither has yet earned full live routing readiness.
- Native render now running sequentially: sparse-file pyosmium location storage, spatial SQLite geometry store, MVT pyramid z6–13. Admission4.76GiB physical /7.55GiB commit /36.87GiBdisk. Do not launch broad source checks or browser/render benchmarks concurrently.
- Safety improvement: future fresh extract requires6GiB physical AND commit headroom, ordinary2GiB guard remains for other stages; verified reuse avoids fresh-extract guard. Actual successful extract was earlier under2GiB admission and severe transient pressure, preserved as measured history.
- Backend catalog version and routing-proof checks hardened; error message includes specific mode and cause. Frontend validates exact zone/state/isMoving counts and honors presentation profiles.
- Root new focused execution: `pytest -q tests/test_connected_acceptance.py tests/test_connected_gis_integrity.py` =>13PASS1.14s. These are small explicit integrity/domain fixtures, not live GIS/OSRM proof.
- `validate_connected_api.py` now has targeted `--cross-zone-proof` (all fleet Bac Ninh, demand Hanoi, maxwait3600s) and optional-resource-telemetry failure handling. Both live benchmark and targeted proof NOT RUN yet.
- Current services: Docker Desktop and native render Python process; graph routers/API/worker/frontend not started by R1b yet. Historical containers/services not terminated.
- Next exact pipeline: render completion → anchors → serve CAR then MB → independent routing validation → `validate_connected_routing.py --snap-anchors` → capture GIS evidence. Then stop heavy work and execute full suites/fixture benchmarks/live stack/scales/browser. All graph paths remain `data/regions/nvmr-connected/routing/{car,motorbike}`.

## Resume implementation checkpoint — 19/10/2026 morning

- Fresh artifact-free full backend command completed312PASS/6SKIP/1deprecationwarning in71.96s. Log `build/r1b-backend-tests.txt`. Six skips are explicit real-data opt-ins, notPASS. This collection preceded two new GIS recovery tests; final combined rerun still needed.
- Recovery found actual render API error: osmium4.2 TagFilter does not accept stringkeys. Replaced with KeyFilter and added tiny reference-order/OSM→fourMVTlayer regression tests.11focused GIS testsPASS (includes9integrity tests).
- Preserved interruptedrenderattempt2 with absolute-path checks; no data marker deleted to forceREADY. Attempt1/attempt2 and failedCARattempt remain available.
- Confirmed Dockerhad no runningcontainers, then normally stopped task-started Docker Desktop to freeidleWSLRAM. No forcekill, unrelatedapptermination or Docker/WSLsettings change. Docker will startnormally after nativeheavy stage.
- Native render resumed with2.88GiBphysical/7.36GiBcommit; source geometry pass now100,000features including4,849places/90,175streets/4,363water/613green; process~360MiBRSS. No completedtilesmanifest yet; do notclaimmapready.
- Added `docs/nvmr/M5_ENGINEERING_HANDOFF.md`, explicit currentinterfaces vs futurepotentialcohort/choice/pairedworld/ledger work and commonhorizon warning. Added structured partial acceptance summary `docs/nvmr/r1b-evidence/validation-summary.json`.
- New graphsmanifestSHA256: CAR `ad52e520c72f8374ebbe8add5d219f5e48c533ac72cc2b23dfb73bb8e5c2528c`; MOTORBIKE `be9140840ce9293ddd747344e6b9d899d02d347ad0b1321143d5bc77eb5677f0`.
- Next: nativeMVT+rawanchors complete; inspect actual pinned osrm-routedhelp/cap ifneeded; servefullgraphrouters, snap+validate; then combinedsourcechecks, domain/livebenchmarks, browser+replay and finaldecision. Root does not run fullfrontend/build/benchmarks concurrently withGIS.

## Recovery checkpoint — real geometry complete / bounded regression underway

- DONE native geometry pass: 1,249,448 streets /25,775 water /14,815 green /4,849 places, errors `{}`. Wall1151.472s, process peakRSS431,554,560bytes, minimum physical2,778,583,040bytes /commit7,642,562,560bytes. `render/features.sqlite`558,923,776bytes SHA256 `d5257bbd866c85c57f0b3115a2e70026e858da18f40dcbabbdf07aa8018058e5`.
- PARTIAL map pyramid: z6 and z7 each4tiles complete; z8–13 still executing. The map `.incomplete` marker remains intentionally. No mapREADY claim.
- Root started bounded frontend regression `npm.cmd test -- --maxWorkers=1`, log `build/r1b-frontend-tests.txt`, while availablephysical>4GiB and native tileprocess~100MiBRSS. No parallel heavy GIS/build/benchmark jobs.
- Current services: native renderer only; DockerDesktop stopped normally, no connected routers/API/worker/frontend yet. Graph bytes remain reusable; live routing/dispatch/scale/browser still NOTRUN.
- Root read-only source review continues; next action after tiles is rawanchors → normalDockerstartup → connectedserve → snapcatalog → independentroutingvalidation. Do not rebuild graphs/extract or remove incomplete markers manually.

## Source acceptance and domain fixture checkpoint — 09:47 Asia/Saigon

- Full backend315PASS/6SKIP/1warning (89.76s); subsequent GIS-only new oracle-proof tests passed independently13GISfocused total, finalcombined collection will be refreshed after GIS source freezes. Logs retained under `build/r1b-*`.
- Full frontend26files/208testsPASS70.23s, typecheckPASS, lint0errors/53warnings (7connected), productionbuildPASS (Vite2.38s, chunk-size warning). SavedReplaypackage9assets/checksumPASS; browserExportsNOTRUN.
- DOMAIN FIXTURE ONLY benchmark complete at100/500/1000/5000 vehicles, each100syntheticrequests: wall2.368/3.216/3.857/7.857s; lifetimepeakRSS54.9/56.4/58.1/72.5MB; output538028/664327/819575/2047006bytes;100completed/0unserved each. This is engine/distribution/accounting evidence, NOT liveOSRM or runtimebasemap evidence. `docs/nvmr/r1b-evidence/domain-benchmark.json`.
- Read-only second source review found no concrete correctness blocker. Existing hooktests cover seek/races/create/cancel; browserstillneeded foractualpolling/selectedroute/mapintegration. No review-agent codechanges.
- NativeMVTstillactive, indexedRtreeplanconfirmed. GISagent added safe pinned `--prepare-synthetic` to runtinyprofileoracle beforefullrouters and reuse only exactcurrentproof; avoids avoidableRAMcontention withoutweakeningguards.

## Browser-discovered regression fixed — 09:54 Asia/Saigon

- Started owned API/worker/preview via `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Profile Meeting -Routers None -ApiPort 8022 -FrontendPort 5192 -Store build/r1b/jobs`. Receipt `build/s0-runtime/session-20261019-095104-757.json`; no Docker/router/GIS stage launched by root.
- Actual IAB browser navigated mainmenu → largefleet → Connected selector; exact default5000/2000CAR/3000MOTORBIKE and100preset80/5/5/5/5 shown. BrowserBack/Forward restored Hanoi v3/Connected correctly.
- A create attempt while routingproofabsent was rejected HTTP503 `CONNECTED_NOT_READY`; no job enqueued. UI displayed causes for bothmodes, no duplicatePOST.
- New demonstrated bug: initial missingtiles prevented MapLibreload, so ConnectedMapHealth's `isLoaded` gate suppressederrortracking indefinitely. Fixed connected-map.tsx to subscribe/readartifact immediately whenmapexists, requireloadonlyforREADY, retainrootcause ontimeout. Added regressiontest;6focusedmaphealthtestsPASS. Rebuiltproduction and reloadedactualbrowser; explicit missingmanifest/HTTP503 maperror nowvisible. Screenshot `docs/nvmr/r1b-evidence/browser/map-not-ready.jpg`.
- This is a new R1b errorhandling regression fix; historical M4FPS remainsclosed. Successfulbasemap/load/clustering/liveplayback notyetclaimed. Renderer nowz11; hostheadroom~3.5–4.2GiB remainsabove2GiBguard.

## Compatibility checkpoint — 10:05 Asia/Saigon

- Full frontend afterinitialmapfix209PASS/26files152.31s (`build/r1b-frontend-tests-final.txt`), concurrentnativeencoding; notaperformancebenchmark.
- Actual historical v3run77bae3c7611849eeac7a9ab4dd375cc6 andv4run370d1b3f87f4465ab7446e23b8852ae4 reopenedvia currentinprocessAPI whileallrouterports5000–5006offline:5000vehicles at0/mid/end, selectedbooking/routeHTTP200, v5IDrejection404, resultSHAunchanged. Evidence `docs/nvmr/r1b-evidence/historical-replay.json`. HistoricalcountsarenotfreshR1bthroughput.
- ActualHCM SavedReplaybrowser: sealedlocaldemo→play→seek500s→Baseline/TreatmentanalyticsPASS withroutersoffline. Portableexportclick didnotyieldcapturedIABdownloadeventwithin15s; nonewJSerror. BrowserexportbytesNOTVERIFIED, packagevalidatorPASSseparately. Screenshot `docs/nvmr/r1b-evidence/browser/hcm-saved-replay.jpg`.
- FirstDockerrestartactualoverhead~3GiBdroppedphysical4.12→1.22GiB, soidleDesktopnormallystoppedwithoutservingrouters. DelayedVMshutdownsubsequentlyrestored~6.7GiB; secondnormalstartupnowadmittedwith6.85GiBphysical/10.93GiBcommit, readinesspending. Neverloweredguards/stoppedownerapps.
- Nativez11complete283tiles; z12encodingactive. Mainstackstillownedbyreceipt095104. NoConnectedjobaccepted/livebenchmarkyet.
