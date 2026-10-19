# R1b Connected NVMR — GIS, vector tiles and independent local graphs

Implementation date: 18–19 October 2026, Asia/Saigon. The integration report and progress checkpoint remain the source of the final end-to-end acceptance decision. This report records actual GIS evidence; a generated profile oracle is distinguished from a local real-road probe.

## Geographic scope and boundary provenance

The [Government's 34-province publication](https://xaydungchinhsach.chinhphu.vn/chi-tiet-34-don-vi-hanh-chinh-cap-tinh-tu-12-6-2025-119250612141845533.htm), opened during this implementation, confirms the 2025 mergers: Bắc Ninh + Bắc Giang; Hưng Yên + Thái Bình; Phú Thọ + Vĩnh Phúc + Hòa Bình; Thái Nguyên + Bắc Kạn. Hanoi remains the fifth study label. The publication establishes naming/mergers, not a machine-readable authoritative polygon.

`scripts/connected_gis_coverage.py` independently reads relation members, boundary ways and their actual node coordinates from the pinned national PBF. It requires every selected way/node to exist and every resulting extent to fit the display rectangle. The complete compact proof is `r1b-evidence/gis/coverage-evidence.json`; the rebuildable ignored original is `data/regions/nvmr-connected/coverage-evidence.json`.

| Study label | OSM relation | Actual WGS84 boundary-node extent `[W,S,E,N]` |
| --- | --- | --- |
| Hanoi | 1903516 | `[105.2889615,20.5645154,106.0200407,21.3854176]` |
| Bắc Ninh merged | 1902690 | `[105.8805752,20.9693320,107.0335769,21.6262727]` |
| Hưng Yên merged | 1901032 | `[105.8953248,20.0771551,107.1192846,21.0069902]` |
| Phú Thọ merged | 1902930 | `[104.8142890,20.3053594,105.8571482,21.7196447]` |
| Thái Nguyên merged | 1902967 | `[105.4311192,21.3264833,106.2469976,22.7413755]` |

All five extents fit the final map rectangle; missing member ways/nodes: **0/0**. These are OSM descriptive extents, including the merged Hưng Yên marine boundary, not certification of legal administrative boundaries. The snapshot's Bắc Ninh administrative relation has inconsistent city wording. Consequently operating membership uses the explicitly versioned, nonoverlapping technical zones in `config/connected-nvmr.json`, never an assumption that OSM administrative labels are legally authoritative.

| Purpose | WGS84 rectangle | Meaning |
| --- | --- | --- |
| Map/viewport | `[104.35,20.06,107.25,22.85]` | Continuous offline real-OSM map; adjacent localities may appear |
| Routing | `[104.25,20.05,107.35,22.95]` | One shared coverage extract feeding independently preprocessed CAR/MOTORBIKE profile graphs, with exterior buffer |
| Operating membership | Five separate technical rectangles in config | Synthetic vehicle/demand allocation and zone analytics; no legal-boundary claim |
| Study labels | The five named merged provinces/city | Research filtering, independent from global dispatch eligibility |

The initial display south edge 20.15 failed the full boundary-node audit because the merged Hưng Yên marine relation reaches 20.0771551. It was expanded to 20.06. The routing rectangle/extract already covered that point, so their bytes were preserved and independently rehashed. Previous task-created proofs are preserved under `data/regions/nvmr-connected/audit/map-coverage-correction/`; current proofs explicitly record the configuration migration. This does not modify R1a/HCM artifacts or silently shrink coverage.

## Source, extraction and build isolation

The existing national file was reused, with no source download:

- `data/raw/vietnam-latest.osm.pbf`: **330,248,138 bytes**, SHA-256 `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`.
- Header replication timestamp: **2026-10-09T20:21:04Z**; header box `[102.095945,7.382239,114.642323,23.402135]`.
- `data/regions/nvmr-connected/extracted/coverage.osm.pbf`: **115,227,528 bytes**, SHA-256 `3243998cec519953323d369e4b569631edc7bef9a4fd4765c7b1e761c22a11f2`.
- Osmium smart extraction completes multipolygon/restriction relations; `check-refs` found **16,081,232 nodes, 1,719,773 ways, 10,135 relations; 0 missing way-node references**.
- Final configuration SHA-256: `c815a2d299193161a19fff43b66bcc71a79dd78a912c165f5be6377f6a1a2aa1`.

Attribution: © OpenStreetMap contributors, ODbL 1.0; Geofabrik Vietnam source. Docker Osmium image is pinned by digest in source verification. OSRM uses `ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124` (v5.27.1). CAR is `/opt/car.lua`, SHA-256 `cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3`; MOTORBIKE is the existing independently modeled `/profiles/motorbike.lua`, SHA-256 `075ecdbc70a3e75c4338d2c6a41597c132a1837ec2d27f1c2fcdd824a788b209`. Every Lua dependency and graph suffix is hashed in its graph manifest.

New graph paths are `data/regions/nvmr-connected/routing/car/` and `routing/motorbike/`; both basename `connected`, MLD. Loopback routers use only ports **5005/5006** and container names **gsm-map-osrm-connected-car / gsm-map-osrm-connected-motorbike**. CAR cannot satisfy MOTORBIKE readiness. Source/config/profile/graph bytes, MLD files, graph-specific nearest hints and independent validation proof must match. Readiness fails on incomplete outputs, changed validators/evidence and router mismatch. HTTP 200 alone is insufficient.

The CLI has a cross-process heavy-stage lock, ≥2 GiB physical and commit admission floors, ≥8 GiB disk floor, isolated `.incomplete` markers and write-once outputs. All heavy stages execute sequentially. OSRM preprocessing uses two explicit worker threads, 2 GiB Docker memory cap and 4 CPU cap; existing Docker/WSL/pagefile settings were not changed. Reuse requires matching identities and content hashes. Pipeline/runtime hash checks cache immutable file stats rather than hashing gigabytes for every viewport tile.

## Resource evidence and recovery

Source/extract verification was executed. Extraction took **21.978 s**. Its sampled host physical minimum was only **26,218,496 bytes**, and commit minimum **1,843,888,128 bytes**. This is severe transient memory pressure despite passing the admission guard; it must not be interpreted as a comfortable whole-laptop resource margin. After this observation, fresh Connected extraction now additionally requires **6 GiB free physical RAM and commit headroom** (the existing 5 GiB Osmium cap plus 1 GiB host reserve). Verified extract reuse retains the unchanged ≥2 GiB general floor and does not repeat extraction. This increased fresh-stage admission requirement is a resource safeguard, not a claim that a new 6 GiB-admitted extraction was rerun.

The first CAR preprocessing attempt used the OSRM default eight threads. It was explicitly stopped by this task after sustained memory pressure, preserving its `.incomplete` marker, files, tool logs and resources in `routing/car-interrupted-attempt-1/`. Its exit 137 is **task-requested termination, not demonstrated OOM**; no unrelated container/process was stopped. The safe retry used two explicit threads with unchanged geographic coverage, profile, 2 GiB memory cap and admission floors.

CAR retry completed extract **180.685 s**, partition **75.314 s**, customize **22.746 s**. Docker's sampled extract peak reached its 2 GiB cap; OSRM itself reported extract peak **2,148,614,144 bytes**. Python orchestration RSS of about 49 MiB is a separate measurement and does not represent OSRM RSS. Per-stage Docker samples and host memory minima are stored in `build-resources.json`; source/tool logs remain available in each namespace.

Subsequent graph/render/routing/anchor results are added below after their actual stages complete. A section absent from this checkpoint is **NOT YET VERIFIED**, never an implied PASS.

## Rebuild and safe reuse in Windows PowerShell

From the repository root, with Docker Linux engine available, run each command to completion and stop on a nonzero exit. Do not run broad tests, browser benchmarks or another heavy preprocessing stage concurrently:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m pip install -r scripts/requirements-connected-gis.txt
.venv/Scripts/python.exe scripts/connected_gis.py verify
.venv/Scripts/python.exe -m scripts.connected_gis_coverage
.venv/Scripts/python.exe scripts/connected_gis.py extract
.venv/Scripts/python.exe scripts/connected_gis.py routing --mode CAR
.venv/Scripts/python.exe scripts/connected_gis.py routing --mode MOTORBIKE
.venv/Scripts/python.exe scripts/connected_gis.py render
.venv/Scripts/python.exe scripts/connected_gis.py anchors
.venv/Scripts/python.exe scripts/connected_gis.py serve --mode CAR
.venv/Scripts/python.exe scripts/connected_gis.py serve --mode MOTORBIKE
.venv/Scripts/python.exe scripts/validate_connected_routing.py --snap-anchors
.venv/Scripts/python.exe scripts/validate_connected_routing.py
```

The default independent validator rebuilds/runs the generated profile oracle into the new namespace. `--skip-synthetic` explicitly reuses the R1a semantic oracle only after checking the exact current motorcycle profile digest; it still reruns Connected NVMR real local graph probes. This distinction is persisted in evidence. Completed artifacts can be reused without repeating preprocessing; the commands refuse stale or incomplete outputs rather than deleting pending markers to force readiness.

## Resume audit — 19 October 2026

Both CAR and MOTORBIKE manifests/file checks/source/extract/profile identities were reverified successfully without rebuilding. Each graph contains 26 hashed suffixes; compact current audit and original build resource measurements are copied into `r1b-evidence/gis/artifact-audit.json` and `routing/{car,motorbike}/`.

The interrupted native rendering attempt had only `.incomplete` and a 28,672-byte geometry SQLite database, with no database or tile manifest. It was preserved by an absolute-path-checked move into `data/regions/nvmr-connected/render-interrupted-attempt-2/`; attempt 1 is also retained. Neither attempt is claimed to contain a usable basemap.

A tiny native-filter regression exposed and fixed the interrupted code's incorrect `TagFilter('place')` constructor: pyosmium 4.2 requires `KeyFilter` for tag-key presence. The executed regression verifies both node locations from untagged referenced nodes and multipolygon assembly from untagged referenced ways, while irrelevant Python callbacks are filtered. `pytest -q tests/test_connected_gis_render.py tests/test_connected_gis_integrity.py`: **10 PASS**. These are fixture/source integrity tests, not live map/routing acceptance.

Resume render admission remains resource-guarded: `r1b-evidence/gis/recovery-render-admission.log` records the actual failed admission when available physical RAM was below 2 GiB. Commit headroom exceeded the floor. No source extraction, graph rebuild, unrelated termination, guard reduction or Docker/WSL/pagefile setting change occurred. Rendering/anchors/router probes remain pending until admission succeeds.

After root normally shut down the task-owned idle Docker Desktop (no running containers, no force kill or settings change), native rendering was admitted with 3,093,962,752 bytes available physical RAM and 7,907,258,368 bytes commit headroom. The geometry stage completed in **1,151.472 s**, peak process RSS **431,554,560 bytes**, minimum physical headroom **2,778,583,040 bytes**, minimum commit headroom **7,642,562,560 bytes**. It retained **1,249,448 street features, 25,775 water features, 14,815 green features, 4,849 place labels**, with empty invalid/missing-geometry error counters. The spatial SQLite database is **558,923,776 bytes**, SHA-256 `d5257bbd866c85c57f0b3115a2e70026e858da18f40dcbabbdf07aa8018058e5`. These are real OSM-derived geometries; this source-stage result does not by itself certify finished viewport tiles or live routers.

The actual tile query plan is captured in `r1b-evidence/gis/tile-query-plan.json`: SQLite scans the bounded Rtree index first and looks up each selected feature by primary key. It does not scan the entire geometry table for each tile. The native-filter plus tiny OSM-to-MVT fixture, integrity fixtures and prepared-oracle identity fixtures were executed separately from real source processing. Expected OSRM HTTP 400 `NoSegment` is treated as an anchor rejection; malformed, transport and server failures still abort catalog generation.

Before serving both full graphs, `.venv/Scripts/python.exe scripts/validate_connected_routing.py --prepare-synthetic` can run the fresh generated profile oracle while router RAM is free. Later normal validation reuses that fresh proof only if the exact current profile, generator, Connected validator, OSRM image and evidence hashes still match. This avoids rerunning preprocessing or silently accepting a stale historical oracle.

A normal idle Docker Desktop startup was attempted after a 4.12 GiB physical admission check, for lightweight historical compatibility probes. The Linux daemon became ready with no running containers, but physical headroom dropped to **1,304,776,704 bytes** (commit headroom **4,027,641,856 bytes**). No routers were started. Desktop was stopped normally, recovering **3,972,665,344 bytes** physical headroom. The active native renderer was preserved. This measured startup footprint is greater than the estimated 1 GiB reserve; future runtime admission must use actual post-startup memory, not that estimate. Evidence: `r1b-evidence/gis/docker-runtime-admission-attempt.json`; no Docker/WSL/pagefile setting changes or unrelated process terminations occurred.

