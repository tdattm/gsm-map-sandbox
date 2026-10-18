# R1a technical recovery checkpoint

Updated: 2026-10-18, Asia/Saigon. Final implementation/handoff checkpoint; this is not an ownership board.

## Goal and actual checkout

R1a implements one Hanoi Core + Bac Ninh Core technical-pilot scenario, one job/worker/store and one playback clock, with isolated local CAR/MOTORBIKE routing and immutable regional results. M4 optimization was explicitly closed by Owner and has not been reopened. R1b/M5 are not implemented here.

Initial primary checkout was clean: branch `feature/nvmr-m0-architecture`, HEAD `43a6d09be2252c44743f9e78a429a3ed700502c1`. HEAD is unchanged. All R1a code/docs/evidence are on disk in this one checkout, unstaged. No stage/commit/push/merge/rebase performed. See `R1A_GIT_DELIVERY.md` and `r1a-evidence/git-allowlists.json` for exact review-only lists.

Historical separate worktrees `gsm-map-sandbox-m3` and `gsm-map-sandbox-m4` remain detached at455abeb with their own old uncommitted files. Both were inventoried read-only and left untouched. Do not copy their older implementation over the integrated primary checkout or clean them up.

## Agent recovery history

Initial agents `bac_ninh_gis` and `regional_backend` split GIS and regional domain/API work. After Owner continuation they were no longer in the live agent list. Replacement agents `gis_resume` and `backend_resume_review` read actual source/checkpoint, reused verified stages and finished missing work. Both replacements finished. No heavy task or development agent remains working. No new worktree was created.

Main owned contracts/main.py/frontend/launcher/integration and final delivery. Shared-file edits were coordinated; completed code is integrated and tested in the primary checkout.

## Contract retained

- Request `gsm-nvmr-regional-scenario/v1`, exactly Hanoi and Bac Ninh allocations; <=5,000 fleet total, <=20,000 bookings total.
- `/api/v4/simulation/jobs`, one existing queue/worker lease, versioned result/snapshot envelope over the unchanged scientific v3 engine.
- Stable sorted region subseeds, region-scoped vehicle/booking IDs, same-mode/intra-region dispatch only.
- Sequential regional execution starts both timelines at0; common duration holds shorter final states. Weighted wait/utilization numerators sum before division.
- v3 stays Hanoi-only; HCM Booking/Voucher/Saved v1 contracts remain separate.

## Completed boundaries and evidence

1. Contract/API/domain/UI interfaces agreed and implemented.
2. Administrative context verified from Government sources; technical design rectangle documented separately from administrative province. Reused national PBF SHA256 `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`, snapshot2026-10-09T20:21:04Z, coverage contains study area.
3. Bac Ninh source/extract/check-refs/five real geographic layers/CAR graph completed in own namespace. Existing Hanoi/HCM graphs not rebuilt.
4. Regional fixture/domain/worker/persistence/readiness/cancellation/isolation tests completed.
5. Missing MOTORBIKE stage resumed only after physical/commit headroom recovered; built/served5004. Independent58 generated profile cases,552 directed pairs/mode, source-node one-way, near-boundary and NoSegment/NoRoute checks PASS. Both Bac Ninh modes READY; no incomplete markers.
6. Website Simulation scenario selector, allocation, overview, one-region lazy basemap, native icons/clusters, four region/mode journeys, one clock/global search/reopen integrated and browser-checked.
7. Domain-only5,000 PASS; live20/100/500/5,000 PASS; real RUNNING cancellation stays CANCELLED/result409; invalid5,001 allocation422/no job. HCM/Hanoi/v3/Saved regression completed.
8. Detailed reports/runbook/Git review-only handoff written. R1a functional local MVP GO, laptop smoothness CONDITIONAL, production NO-GO.

## Latest successful verification

- Artifact-free backend: **267PASS/6SKIP**,22.62s (`r1a-evidence/backend-artifact-free-final.txt`).
- Opt-in local GIS/OSRM backend: **273PASS**,50.53s (`backend-live-final.txt`). One dependency deprecation warning.
- Frontend: **189PASS/23files**,33.24s (`frontend-tests-final.txt`).
- Typecheck/build PASS; lint0errors/46warnings. Saved package verifier9assets PASS.
- Final MOTORBIKE serve reuse preserved bytes and mtime in Hanoi and Bac Ninh; current Hanoi proof matches archived M2 proof SHA25630747c76... (`router-proof-preservation.json`).
- Actual regional router launcher reuse PASS; no duplicate services (`launcher-regional-reuse.txt`).
- Browser captures100/500/5,000 total: cluster/source conservation PASS,0DOM markers, one map. Detailed fleets50/250/2,500, not all5,000 individual icons. RAF about1.86–1.89FPS/p95~1016ms in short embedded-browser captures; no smoothness/root-cause closure claimed.
- Browser716x659/no horizontal overflow; four live journeys at common t100, native map click/drill-down and persisted reopen observed. Final overview contains both extents. Independent Chrome/<=650px/Meet/soak NOT VERIFIED.
- GitHub Actions remote NOT RUN. CI commands were run locally without mandatory PBF/graph preprocessing.

Last successful command families (do not rerun merely to resume):

```powershell
$env:RUN_REAL_DATA='0'; .\.venv\Scripts\python.exe -m pytest -q -rs
$env:RUN_REAL_DATA='1'; .\.venv\Scripts\python.exe -m pytest -q -rs
# From frontend/: npm.cmd test -- --maxWorkers=1; npm.cmd run typecheck; npm.cmd run build; npm.cmd run lint; npm.cmd run verify:replay
.\.venv\Scripts\python.exe -X utf8 scripts/validate_regional_api.py --base-url http://127.0.0.1:8021 --job-id 6920edfece7042dd9a98fa42c52edcf6 --output docs/nvmr/r1a-evidence/ui-created-20-audit-recovery.json
```

## Persisted IDs and reusable artifacts

- Live20 `cf7f7073fc974b2184181fe8ce58a36e`.
- Corrected live100 `9cca52e88d214266810f59788785b88b`.
- Live500 `a099e68a5ed04741a26d44889470768c`.
- Live5,000 `370d1b3f87f4465ab7446e23b8852ae4`:2,000CAR+3,000MOTORBIKE,1,250requests,1,225completed/25unserved;15.829s worker total,23.086s verifier wall,11,323,043result bytes.
- UI-created20 `6920edfece7042dd9a98fa42c52edcf6`, seedr1a-ui-20-v1,19completed/5unserved, four region/mode journeys at t100. Independent audit after task-stack restart PASS.
- Domain-only5,000 `c6453b9aa844440ca3c40cb51a82e79c`, separate `build/r1a/domain-jobs`, synthetic directed-ring/no OSRM evidence.
- Real cancelled RUNNING job `febbd58d90de4112aa894b01775300d1`; never exposes final result.
- Hanoi v3 live `d51966759c464d34a2345ef392a2380c` PASS10vehicles/20requests.
- Bac Ninh data: `data/regions/nvmr-bac-ninh-core/`; original national PBF retained. Do not rebuild verified stages merely to resume.
- Raw compact reports under `docs/nvmr/r1a-evidence/`; all actual job stores/graphs/PBF/build output ignored.

## Failures preserved and corrected

- Initial MOTORBIKE preprocess RESOURCE_STOP below2GiB; no guard lowering. Later safe missing-stage build succeeded.
- Original live100 `e226e776595e4c3b91e34f69a4ff3ae1` remains FAILED: MOTORBIKE Table resnapped two parked sources71.235m. V4 now requests1m source radiuses, preserves null/disconnected outcomes and all assertions; shared query plumbing retains HCM/v3 defaults. Raw diagnostic/probes/failed report retained.
- Cropped return-to-overview camera corrected with post-layout/resize union fit; final both-extents oracle PASS, no playback refitting.
- Valid receipt initially refused by inherited UTC DateTime comparison. Final stop handles explicit UTC and PS7 DateTime values, keeps PID/exe/command/child guards.
- One invalid-receipt test SETUP mistake produced a valid fixture and stopped only the3 task-created services. Owner services untouched; same-store restart and persisted audit recovered. Failure summaries retained. Corrected literal2000UTC fixture rejects in both Windows PowerShell and pwsh with all3 current services still alive.
- Low browser RAF remains a measured limitation; no M4 profiler task reopened. A transient historical gsm-car load warning is retained; final fresh overview page has its own console capture.

## Current services and next precise action

Task API8021 / production preview5191 / one worker, store `build/r1a/jobs`. Current receipt: `build/s0-runtime/session-20261018-141504-780.json`. Owner's earlier8016/5187 services were not stopped. Hanoi routers5001/5002 were not stopped/rebuilt. Bac Ninh5003/5004 and HCM5000 regression router are task-created; final runtime readiness is captured in `validation-summary.json`. Lease is not a heartbeat.

No required implementation/preprocessing/benchmark remains. Next action is Owner review of `R1A_IMPLEMENTATION.md`, runbook and exact Git allowlists. Agent must not stage/commit/push/merge or implement R1b without new authorization. If resuming a new change: read this checkpoint, current Git status, final reports/manifests and relevant agent statuses first; reuse verified data/results, and run only checks justified by that change. Retain all uncommitted R1a source plus unrelated historical worktree files.
