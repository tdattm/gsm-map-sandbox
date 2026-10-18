# R1a — Bac Ninh Core GIS and local routing

Verified on 2026-10-18 (Asia/Saigon). This report distinguishes the technical study rectangle, the administrative province and measured graph coverage. The interrupted GIS agent was replaced during recovery; existing verified national source, extract, render layers and CAR graph were reused. Only the missing MOTORBIKE build and independent regional validation were resumed.

## Coverage and sources

The authoritative administrative reference is National Assembly Resolution **202/2025/QH15, dated 12 June 2025**. Its Bắc Ninh provision merges Bắc Giang and Bắc Ninh. The [Government resolution publication](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-quyet-so-202-2025-qh15-ve-sap-xep-don-vi-hanh-chinh-cap-tinh-119250612174148722.htm) and the [Government's province detail page](https://xaydungchinhsach.chinhphu.vn/chi-tiet-34-don-vi-hanh-chinh-cap-tinh-tu-12-6-2025-119250612141845533.htm) were opened on 18 October 2026; the latter explicitly identifies the merger. These sources establish the administrative naming change. They are **not** a downloaded administrative polygon or a validation that this pilot covers the new province.

The study boundary source is the versioned **project design rectangle** in `config/regions/nvmr-bac-ninh-core.json`, version `technical-rectangle/2026-10-18`, checked against the existing national PBF header bounds and actual OSM road vertices. It is intentionally centered around the former Bắc Ninh urban area and nearby roads. No administrative-boundary geometry is used. This compact area has a verified 24-cell spread of road-derived anchors and a separate routing buffer, allowing small local MLD graphs on this laptop. Its inclusion of the entire province, newly merged Bắc Giang territory, all wards or any business service territory is **NOT VERIFIED and not claimed**.

Coordinates use WGS84 `[west, south, east, north]`:

| Purpose | Bounds | Meaning |
| --- | --- | --- |
| Operating area | `[106.02,21.15,106.10,21.21]` | Technical synthetic-demand/vehicle area |
| Viewport | `[106.00,21.13,106.12,21.23]` | Initial map view only |
| Render | `[105.995,21.125,106.125,21.235]` | Locally prepared display features |
| Routing | `[105.96,21.09,106.16,21.27]` | Extract/graph coverage including buffer |

The operating rectangle is approximately 8.3 by 6.7 km at this latitude (a geometric approximation, not measured service coverage). `candidate_catalog` samples its inner 60%, spreading candidates over a 6×4 grid; it does not infer access legality or graph connectivity from a street name. Explicit near-boundary probes additionally use source street vertices nearest all four operating corners.

The [Geofabrik Vietnam source page](https://download.geofabrik.de/asia/vietnam.html) was opened on 18 October 2026. The page's moving `latest` file is newer than the **reused local** snapshot; no download was performed. The local provenance is:

| Item | Verified identity |
| --- | --- |
| National source | `data/raw/vietnam-latest.osm.pbf` |
| PBF replication timestamp | `2026-10-09T20:21:04Z` |
| PBF SHA-256 | `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a` |
| PBF coverage box | `[102.095945,7.382239,114.642323,23.402135]` |
| Regional extract | 3,229,117 bytes; SHA-256 `5b18bc568bb2afd3a4914b97b89084663e7a1e72a84364367cb42eac7f7c3ebb` |
| Extract method | Osmium `smart`, multipolygon/restriction relation completion; `check-refs` PASS |
| OSRM version/image | `v5.27.1`, `ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124` |
| Osmium image | `iboates/osmium@sha256:a67987f7d822d951ae1979de656ab7bd8051605f79d2751ea4800cc6057124be` |

Attribution: © OpenStreetMap contributors. All render/routing inputs are local; no public OSRM/Overpass or CDN map fallback is used.

## Artifacts, isolation and readiness

Runtime namespace: `data/regions/nvmr-bac-ninh-core/`. These large ignored artifacts must not be force-added to Git. The tracked compact evidence is under `docs/nvmr/r1a-evidence/gis/`.

Five real OSM render layers exist: streets **15,594** features, water **701**, green **430**, buildings **19,908**, places **55**. The geometry error log is empty. Layer sizes/hashes, extract source identity, graph suffix hashes and graph-specific router evidence are recorded by `artifact-audit.json`; no layer is replaced with invented geometry.

| Mode | Namespace/service | Profile | Current outcome |
| --- | --- | --- | --- |
| CAR | `routing/car`; `gsm-map-osrm-bac-ninh-car`; loopback `:5003` | Image `/opt/car.lua`; SHA-256 `cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3` | Built, identity-checked, independently sampled, READY |
| MOTORBIKE | `routing/motorbike`; `gsm-map-osrm-bac-ninh-motorbike`; loopback `:5004` | Local `/profiles/motorbike.lua`; SHA-256 `075ecdbc70a3e75c4338d2c6a41597c132a1837ec2d27f1c2fcdd824a788b209` | Built after resource recovery, independent validation PASS, READY |

Both graph manifests pin source/extract/config/image/profile dependencies and all MLD file hashes. MOTORBIKE uses the existing explicit motorcycle profile and assumptions, a separate graph and separate router. The pipeline never substitutes CAR. Its manifest SHA-256 is `86d2f963d327875a59411b87b212b038f5dd222592e5c58e513c5edfc00ef4e0`.

Serve checks image, exact routed command, region/mode labels, read-only graph mount, loopback binding and graph-specific nearest hints. Backend readiness also verifies artifact bytes and its own graph-specific probes; HTTP 200 alone is insufficient. MOTORBIKE readiness additionally requires the independent validator digest, its own regional evidence hashes and no incomplete markers. Hanoi M2 evidence cannot satisfy Bắc Ninh readiness. Tests cover wrong-region, stale-graph, failed-proof, source-change and incomplete-proof rejection.

Historical Hanoi/HCM config/profile/validator source files were checked with `git diff --exit-code` and unchanged. Existing Hanoi/HCM runtime manifests were read only; hashes captured after GIS support subsequent comparison. There was no pre-task full hash inventory of all ignored artifacts, so complete byte-for-byte before/after preservation of every historical file is not asserted. Temporary generated profile fixtures reuse the existing validator's deterministic `build/m2/synthetic-<profilehash>/` workspace and write R1a evidence separately; historical `docs/nvmr/m2-evidence/` and routing manifests are untouched.

## Independent validation results

Evidence: `nvmr-bac-ninh-core/regional-routing.json`, `synthetic-validation.json` and `source-oneway-ways.xml` under the GIS evidence folder. The earlier `car-only/` capture remains preserved and is superseded by the both-mode capture for current readiness.

| Check | CAR | MOTORBIKE |
| --- | --- | --- |
| Road-derived anchors / bounded snaps | 24 / all PASS | 24 / all PASS |
| Directed non-diagonal table pairs | 552 | 552 |
| Unreachable pairs | 46 (8.33%) | 0 |
| Selected full-geometry OD routes | 11 reachable + 1 `NoRoute` | 12 reachable |
| Identical-input Table/route comparison | 12 exact duration/reachability matches | 12 exact duration/reachability matches |
| Exercised source one-way ways | `1031063725`, `1175814566`; no reversed source edges | Same two ways; no reversed source edges |
| Operating-corner source-vertex routes | Four recorded; geometry/snaps checked | Four recorded; geometry/snaps checked |
| Remote bounded-snap query | `NoSegment` | `NoSegment` |

All selected route distances/durations are positive and finite, full geometry has at least two points, and every geometry vertex stays inside the routing box. These checks describe sampled static graph behavior, not complete OD connectivity. CAR's disconnected candidate components are retained as `NoRoute`/null table cells; the capture does not determine whether the root cause is missing OSM links, modeled access restrictions or an actual physical disconnection. No straight-line route, retry on a different mode or a different regional graph is fabricated.

An interruption note mentioned a raw-coordinate Table/route discrepancy without identifying its pair. A recovery read-only comparison of all **552** CAR raw directed pairs found **zero** duration or reachability mismatches with identical radius options. No cause for that earlier unlocated observation is established. The persistent validator now fails on an exact duration/reachability mismatch in its 12 selected samples; no threshold was loosened. The OSRM [general API options](https://project-osrm.org/docs/v5.24.0/api/#general-options) explain radius/hint controls; no inference about the earlier observation is drawn from those options.

The independent generated oracle has **58 PASS** cases across both profiles, including motorcycle/motorcar differences, access hierarchy, private/ambiguous/conditional restrictions, motorway/motorroad exclusion, path access, forward/reverse one-way behavior, bridges/tunnels, barriers, ordinary/mode-specific/exception turn restrictions, disconnected components and maximum snapping. This is a generated model check, not a claim about real legal access/signage at every Bắc Ninh road. Exhaustive live real-world turns/barriers/conditional restrictions and traffic ETA calibration remain **NOT VERIFIED**.

Artifact-free focused GIS tests: original combined regional/region/mode suite **48 PASS, 1 SKIP** (`build/r1a-gis-tests-final.log`); recovery GIS suite including six exact Table/route mismatch cases **18 PASS** (`build/r1a-gis-resume-tests.log`). Main integration/regression results are reported separately, not inferred from these GIS checks.

Final safe-reuse review added two source-only MOTORBIKE router-proof tests: matching evidence keeps both bytes/mtime, and changed evidence is refused without overwrite. Final GIS+M2 focused run **34 PASS /1 SKIP**, including20 GIS cases (`r1a-evidence/gis-reuse-tests.txt`). Actual Hanoi/Bac Ninh MOTORBIKE serve reuse preserved both proof hashes and mtimes (`router-proof-preservation.json`); the current Hanoi proof also matches the archived M2 proof bytes. Earlier inherited MOTORBIKE serve could refresh an identical proof's mtime, so immutable graph/config/profile contents are distinguished from historical metadata touches. The final full suites are267PASS/6SKIP artifact-free and273PASS with local real data, recorded in the integration report.

## Resource recovery and safe operation

Initial MOTORBIKE attempts stopped **before writing graph inputs** because available physical/commit headroom did not pass the unchanged **2 GiB** floor. Historical `r1a-gis-motorbike.log` and `r1a-gis-motorbike-retry.log` remain recorded. During recovery the main agent finished regression/build children and released the heavy slot; fresh MOTORBIKE preflight measured **6,542,790,656 physical available bytes** and **11,835,281,408 commit available bytes**. It then completed extract/partition/customize sequentially. OSRM tool-reported RAM peaks were **142,897,152**, **55,648,256** and **38,129,664** bytes; these are individual tool reports, not total-host peak memory or a simulation benchmark. Neither the RAM guard nor Docker/Windows/WSL settings were lowered.

No verified CAR/extract/render preprocessing was repeated during recovery. No Hanoi router was stopped. Both Bắc Ninh services run alongside Hanoi on separate ports. `.incomplete`/`.validation-incomplete` markers are absent after successful final validation; errors must retain pending markers rather than create successful readiness.

From the repository root, inspect current readiness without rebuilding:

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/capture_regional_gis.py
docker ps --format '{{.Names}} {{.Ports}}'
```

To resume a stopped **unchanged** regional graph, run the identity-checking serve commands serially. These preserve existing inputs and refuse an identity/mount/profile mismatch:

```powershell
.venv/Scripts/python.exe scripts/pipeline.py serve --region nvmr-bac-ninh-core --profile car --detach
.venv/Scripts/python.exe scripts/pipeline.py serve --region nvmr-bac-ninh-core --profile motorbike --detach
```

If a MOTORBIKE graph is genuinely absent, only after the heavy slot is free and the unchanged preflight passes:

```powershell
.venv/Scripts/python.exe scripts/pipeline.py routing --region nvmr-bac-ninh-core --profile motorbike
.venv/Scripts/python.exe scripts/pipeline.py serve --region nvmr-bac-ninh-core --profile motorbike --detach
.venv/Scripts/python.exe scripts/validate_regional_routing.py
.venv/Scripts/python.exe scripts/capture_regional_gis.py
```

For an unchanged already-verified R1a generated profile oracle, `scripts/validate_regional_routing.py --skip-synthetic` reuses only an existing PASS proof whose profile digest matches; it still reruns the local regional source/OD/boundary audit. This is needed after validator changes because readiness binds its exact source hash. Stop on any failed command. Do not delete incomplete markers or artifacts to force reuse; inspect identity and choose an explicit new output/config version if reconstruction is necessary. Do not run full regression, frontend builds, simulation benchmarks or browser benchmarks concurrently with graph preprocessing.

GIS readiness is GO for this bounded static pilot on the captured machine. It does not establish total-scenario 5,000-vehicle runtime, browser performance, production deployment, full new-province coverage or R1b/M5 acceptance; the orchestrator's separate live integration and UI evidence decides those boundaries.
