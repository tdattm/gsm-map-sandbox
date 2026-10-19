# R1b Connected NVMR — GIS acceptance hiện hành

Cập nhật **19/10/2026, Asia/Saigon**, từ manifests và JSON evidence thực tế. **GIS PASS trong phạm vi đã kiểm tra**: basemap offline, hai graph độc lập, snapped anchors và routing probes hoàn tất. Quyết định end-to-end/M5 thuộc [implementation report](R1B_CONNECTED_IMPLEMENTATION.md).

## Coverage và identity hiện tại

Map/viewport WGS84 **[104.35,20.06,107.25,22.85]**; routing **[104.25,20.05,107.35,22.95]**, liên tục, có buffer. Năm actual OSM relation extents đều nằm trong map rectangle, thiếu member ways/nodes **0/0**; chi tiết ở [coverage proof](r1b-evidence/gis/coverage-evidence.json) và phụ lục dưới đây. Operating membership dùng năm technical rectangles không chồng lấn, version `technical-operating-zones/2026-10-18-v1`, **không phải địa giới chính thức**. Địa phương lân cận trong basemap không tự thành phạm vi nghiên cứu. Zones không chia dispatch pool.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| National PBF đã reuse | 330,248,138 | `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a` |
| Connected extract | 115,227,528 | `3243998cec519953323d369e4b569631edc7bef9a4fd4765c7b1e761c22a11f2` |
| Frozen config | — | `c815a2d299193161a19fff43b66bcc71a79dd78a912c165f5be6377f6a1a2aa1` |

PBF timestamp **2026-10-09T20:21:04Z**. Extract có **16,081,232 nodes / 1,719,773 ways / 10,135 relations**, check-refs không thiếu node references. Không tải nguồn mới. Attribution: © OpenStreetMap contributors, ODbL 1.0; Geofabrik Vietnam. Nhãn hành chính dựa trên thông tin sáp nhập chính thức được dẫn trong phụ lục; OSM extents không chứng nhận legal boundaries.

## Basemap offline đã hoàn tất

Paths dưới `data/regions/nvmr-connected/`:

| Archive | Zoom / tiles | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `render/tiles.mbtiles` | z6–13 / **5,503** | 136,577,024 | `a27003b3bef79f2cc56d809e3874d1cbbf393962e3e986bf7fa1647056a34087` |
| `render-overview/tiles.mbtiles` | z0–5 / **8** | 1,679,360 | `90e4d485a9c12aaf9b02a7fb42ac982f7bdaec7684b61f2ed07c08954827ec62` |

Detailed tile counts z6→13: **4/4/8/23/80/283/1,054/4,047**; overview z0→5: **1/1/1/1/2/2**. Một XYZ API phục vụ viewport MVT, SQLite lưu TMS rows; không tải GeoJSON toàn miền Bắc hoặc external map CDN runtime.

Source layers `streets/water/green/places`: **1,249,448/25,775/14,815/4,849** features, geometry error counters rỗng. Không có buildings; mọi road class đã chọn có ở z12–13 rồi overzoom. Geometry SQLite **558,923,776 bytes**, SHA `d5257bbd866c85c57f0b3115a2e70026e858da18f40dcbabbdf07aa8018058e5`. [Query plan](r1b-evidence/gis/tile-query-plan.json) dùng bounded Rtree rồi feature primary-key lookup.

Overview sửa lỗi fit toàn vùng có thể xuống dưới z6 trong map pane laptop thấp. Nó được sinh riêng từ geometry DB mở **read-only**, chọn source `minzoom<=6`: arterials, water polygons, city/town labels; Mercator clipping, topology-preserving simplification 0,6 pixel, MVT extent4096. Không bịa geometry, không overwrite detailed archive/config/graphs. Green/đường nhỏ/waterways chi tiết vẫn ở archive gốc.

Overview manifest SHA `15af85e4ca45765875e008b606071fc3780fe209f66dc66ad1c521675cc68aa5` khóa config/source/extract/base archive/features DB/script. `verify_overview()` PASS; **8 actual tiles decode thành công**, **8 focused tests PASS** về TMS/XYZ, coordinates/properties, filtering, base-byte preservation, tampering/incomplete/resource admission. Browser acceptance thuộc báo cáo tích hợp.

Software sidecar: Python3.11.9; osmium4.2.0; shapely2.1.2; mapbox-vector-tile2.2.0; protobuf6.33.6; GEOS3.13.1. Artifact checksum là exact-output identity; rebuild khác thư viện có thể đổi bytes.

## Graphs và road anchors

OSRM v5.27.1 image pin: `ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124`.

| Mode | Profile SHA-256 | Graph manifest SHA-256 | 26 suffixes: bytes |
| --- | --- | --- | ---: |
| CAR `/opt/car.lua` | `cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3` | `ad52e520c72f8374ebbe8add5d219f5e48c533ac72cc2b23dfb73bb8e5c2528c` | 1,710,038,464 |
| MOTORBIKE `/profiles/motorbike.lua` | `075ecdbc70a3e75c4338d2c6a41597c132a1837ec2d27f1c2fcdd824a788b209` | `be9140840ce9293ddd747344e6b9d899d02d347ad0b1321143d5bc77eb5677f0` | 1,714,422,808 |

Paths `routing/{car,motorbike}/`, basename `connected`, MLD; mỗi suffix và Lua dependency có hash. CAR không đáp ứng MOTORBIKE readiness. HCM/Hanoi/R1a namespaces giữ nguyên.

Raw catalog có **39,805 road-derived candidates**. Snapping riêng mode loại `NoSegment`/trùng/sai zone-radius, không tạo tọa độ thay thế:

| Mode | Hà Nội | Bắc Ninh | Hưng Yên | Phú Thọ | Thái Nguyên | Accepted | Loại NoSegment / duplicate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CAR |13,101|3,267|6,853|7,455|9,001|**39,677**|62/66|
| MOTORBIKE |13,143|3,276|6,853|7,455|9,000|**39,727**|50/28|

`anchors/road-candidates.json`: **4,668,491 bytes**, SHA `1413a5284af96d67a81cbbdcad300a0c39b5f1a61896ab5cd93484efe1a21826`; `anchors/snapped-anchors.json`: **12,971,063 bytes**, SHA `2d917217a5299997859b10103f2576ccf17d5c1f8976af87aec1b71dd16253ae`. Manifest gắn source/extract/config và cả hai routing identities.

[Road input audit](r1b-evidence/real-road-inputs.json) PASS ở100/500/1.000/5.000xe. 5.000xe đúng **4.000/250/250/250/250**, **2.000CAR/3.000MOTORBIKE**, 5.000ID/positions duy nhất, 0duplicates, 888cells, max36xe/cell, không cell>50. NN128 sample: min1,90m/median245,87m/p952.259,67m. Same-seed repeat và demand độc lập khi đổi fleet size PASS. Đây là **input preparation**, không phải completed live simulation benchmark; geographic NN không phải travel distance.

## Routing acceptance thực tế

Hai `routing-validation.json` đều **PASS:20/20 directed hub pairs/mode**, gồm Hà Nội↔4vệ tinh và12hướng giữa vệ tinh; thêm **5local-zone routes/mode PASS**. Nearest hub≤100m; `(0,0)` radius10m trả `NoSegment`. Kiểm full LineString, finite positive distance/duration và geometry trong routing rectangle.

Bảng lấy trực tiếp Route responses, đơn vị **mét / giây**, static modeled travel:

| Mode | Vệ tinh | Hà Nội → vệ tinh | Vệ tinh → Hà Nội |
| --- | --- | ---: | ---: |
| CAR | Bắc Ninh |31.465,7 /2.154,0|30.149,0 /2.105,6|
| CAR | Hưng Yên |60.255,5 /3.023,3|59.319,4 /2.941,3|
| CAR | Phú Thọ |73.171,1 /3.684,4|72.033,1 /3.636,7|
| CAR | Thái Nguyên |71.551,0 /3.782,7|72.222,6 /3.790,8|
| MOTORBIKE | Bắc Ninh |30.332,1 /2.965,7|30.076,7 /2.907,2|
| MOTORBIKE | Hưng Yên |62.292,0 /4.896,7|60.724,9 /4.961,3|
| MOTORBIKE | Phú Thọ |71.007,3 /7.235,6|70.236,5 /7.219,7|
| MOTORBIKE | Thái Nguyên |69.508,8 /7.636,8|70.492,5 /7.697,6|

Table/Route dùng cùng snapped inputs/radius10m. `tableDuration` được persist, duration consistency được kiểm tra. Distance consistency so trực tiếp với Table trong validator bằng tolerance **max(0,11m; Route distance×0,0001)** = **0,01%**. Evidence hiện **không persist `tableDistance` hoặc raw Table matrix**: không thể tái tính independent distance difference chỉ từ JSON đã lưu; cần rerun validator với routers thật. Route distance trong bảng không phải Table distance đã persist.

**Generated oracle:58cases PASS tổng cộng**, gồm cả hai modes: access hierarchy/private/barriers/motorway/motorroad, one-way/reverse/exception, turn-restriction/mode-turn/except-motorcycle, conditional assumptions, disconnected và max-snap. Một shared oracle gắn vào hai proofs, **không phải58real-road cases/mode**.

**Real OSM one-way:2cases/mode**, source-node sequence đối chiếu route annotations, forbidden reversed edges=0. CAR ways9656653(Mã Mây:69,1m thuận/910,5m vòng ngược),9656730(Chương Dương:607,3/2.313,3m). MOTORBIKE ways9656730(607,3/2.314,4m),9978719(35,7/686,1m).

**Restriction limitation:** chưa audit exhaustively actual access/turn relations toàn graph; chưa có acceptance survey độc lập toàn bộ real OSM turn restrictions. Generated oracle chứng minh semantics trên mạng kiểm soát; không chứng nhận biển báo thực địa, mọi legal route hoặc speed calibration.

Anchor capture dùng64bounded concurrent nearest requests và retry tối đa3 lần riêng cho `RemoteProtocolError`. CLI validator có scoped compatibility patch cho private `h11._connection._keep_alive`, chỉ với OSRM HTTP/1.0 explicit keep-alive + Content-Length; luôn restore sau scope. Đây là tooling dependency nhạy phiên bản, đã có focused protocol tests; không cài patch vào API/worker runtime, không retry mọi lỗi hoặc đổi kết quả routing. Cần revalidate nếu nâng httpx/h11/OSRM.

**NoRoute thực được giữ nguyên:** survey100snapped anchors/mode về Hanoi hub, quan sát Table null+Route`NoRoute`: CAR`[105.745179,22.049582]`→`[105.840802,21.028008]`; MOTORBIKE`[105.915036,21.053735]`→cùng hub. Proof lưu ví dụ đầu tiên, không ước lượng tỷ lệ disconnected toàn graph.20/20hub pairs không bảo đảm mọi OD kết nối; snap hợp lệ không bảo đảm cùng component. Không vá bằng tuyến thẳng.

`validation.json` khóa graph manifest, validatorSHA`41f730a3193d0aa25a7b48fbdfb01294a339bdff76ad3791fc50b35e76e775df` và evidence hashes. PASS là executed evidence đã lưu; bytes/incomplete/router hints thay đổi phải fail-closed.

## Runtime mmap và tài nguyên16GB

Routers `gsm-map-osrm-connected-car` tại127.0.0.1:5005 và `gsm-map-osrm-connected-motorbike` tại127.0.0.1:5006. Actual pinned binary help và router evidence xác nhận:

```text
osrm-routed --algorithm mld --mmap=1 /data/connected.osrm --max-table-size 256
```

Graph mount read-only; container mới cap **1GiB RAM/2CPU**. Mmap tránh copy toàn graph vào heap nhưng page cache/file-backed working set và Docker/WSL vẫn tiêu thụ RAM.1GiB không phải toàn bộ system memory hay bảo đảm mọi workload. Startup/reuse kiểm image/command/mount/loopback binding; đánh giá container đang chạy cần actual Docker config.

Heavy lock và build tuần tự; admission **≥2GiB physical VÀ commit, ≥8GiB disk**. Fresh extraction tăng≥6GiB sau pressure đã đo. Admission không reserve RAM, headroom có thể giảm trong stage. Không sửa Docker/WSL/pagefile settings hoặc hạ guards.

| Stage thực tế | Wall time | Resource evidence |
| --- | ---: | --- |
| Extract |21,978s|Min physical26.218.496bytes: severe pressure, không phải comfortable margin|
| CAR extract/partition/customize |180,685/75,314/22,746s|2threads; preprocessing cap2GiB/4CPU; OSRM reported peak2.148.614.144bytes|
| MOTORBIKE extract/partition/customize |249,827/68,327/21,593s|Cùng limits, chạy sau CAR; extract min physical1.515.728.896/commit1.621.147.648bytes|
| Source geometry |1.151,472s|Peak RSS431.554.560bytes; min physical2.778.583.040bytes|
| Detailed MVT |2.165,000s|Sampled RSS135.913.472; lifetime peak431.554.560 gồm geometry; min physical927.346.688bytes|
| Overview MVT |221,667s|Peak RSS120.438.784; admission physical2.158.776.320; min physical1.725.198.336/commit5.512.507.392bytes|

Python wrapper RSS~49MiB khi graph build **không phải OSRM RSS**; Dockerstats sau run không phải execution peak. Full samples giữ trong manifests/build-resources; simulation benchmarks nằm ở báo cáo tích hợp.

## Recovery và reuse

Giữ nguyên các lỗi lịch sử trong phụ lục: map south20,15→20,06 sau Hưng Yên marine audit; task-stopped CAR8threads exit137 không chứng minh OOM→retry2threads; hai interrupted render attempts; pyosmium TagFilter→KeyFilter và fixtures giữ references; admission thiếu RAM/Docker startup footprint. Active outputs đã hoàn tất; `.incomplete` chỉ còn trong **render-interrupted-attempt-1/2 và routing/car-interrupted-attempt-1**. Không xóa markers để ép READY.

[Runbook](R1B_CONNECTED_RUNBOOK.md) có full rebuild/demo commands. Artifact hợp lệ phải reuse; không chạy full preprocessing lại cho demo. Overview có command riêng:

```powershell
.venv/Scripts/python.exe -m scripts.connected_overview_tiles
.venv/Scripts/python.exe -c "from scripts.connected_gis import verify_render; from scripts.connected_overview_tiles import verify_overview; verify_render(); verify_overview(); print('basemap identities PASS')"
.venv/Scripts/python.exe -m scripts.validate_connected_inputs
```

Nếu validator/evidence thực sự thay đổi, phục hồi acceptance tuần tự với routers thật và đủ headroom:

```powershell
.venv/Scripts/python.exe scripts/connected_gis.py serve --mode CAR
.venv/Scripts/python.exe scripts/connected_gis.py serve --mode MOTORBIKE
.venv/Scripts/python.exe scripts/validate_connected_routing.py --snap-anchors
.venv/Scripts/python.exe scripts/validate_connected_routing.py
```

`--prepare-synthetic` chuẩn bị oracle trước full routers khi cần giảm cạnh tranh RAM; reuse chỉ khi exact identities khớp. `--skip-synthetic` là dùng lại historical R1a semantics oracle đã kiểm profile hash, không phải oracle vừa chạy. GIS PASS không thay thế dispatch/persistence/browser/compatibility acceptance.

---

# Phụ lục lịch sử — checkpoint trước khi hoàn tất

**Historical/Superseded:** Phần dưới giữ nguyên audit trail. Những câu “pending/NOT YET VERIFIED” mô tả checkpoint cũ; trạng thái hiện tại là phần tiếng Việt phía trên.

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

