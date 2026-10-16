# M1b — Hanoi Core GIS, CAR routing và pilot

Ngày kiểm chứng: **16/10/2026**, Windows/PowerShell, Docker Linux Engine. Hanoi Core đã chạy thật với OSM và OSRM CAR nội bộ. Nhu cầu và phản ứng giá là **synthetic/model-based**, không phải dữ liệu hay bằng chứng hành vi GSM Hà Nội. M0/M1a là tài liệu lịch sử được giữ nguyên.

## 1. Study area và dữ liệu

Các tọa độ WGS84 dưới đây theo thứ tự `[west,south,east,north]`. Đây là bbox kỹ thuật đô thị lõi, không phải địa giới hành chính hoặc phạm vi toàn NVMR.

| Phạm vi | Bbox / ý nghĩa |
|---|---|
| Display / initial viewport | `[105.802,21.002,105.875,21.055]`; tâm `[105.8385,21.0285]`, zoom 13.4 |
| Operating | `[105.815,21.012,105.855,21.045]`; sinh xe/potential, kiểm tra snap trong vùng |
| Routing | `[105.762,20.962,105.915,21.095]`; buffer 0.04° mỗi cạnh so với display; mọi route/snaps phải nằm trong vùng này |
| Render | `[105.797,20.997,105.880,21.060]`; buffer 0.005° cho bản đồ |

Tái sử dụng `data/raw/vietnam-latest.osm.pbf` **330.248.138 bytes**, không download mới. Nguồn [Geofabrik Vietnam](https://download.geofabrik.de/asia/vietnam.html) / OpenStreetMap; PBF header replication snapshot **2026-10-09T20:21:04Z**, sequence **4934**. SHA-256 đã kiểm tra lại: `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`. Fileinfo xác nhận header bbox bao phủ routing study area. [Source verification](m1b-qa/source-verification.json).

Osmium 1.19.0, image digest `a67987f7d822d951ae1979de656ab7bd8051605f79d2751ea4800cc6057124be`; extract `smart`, complete relation types `multipolygon,restriction`, `--set-bounds`. Extract có **880.229 nodes / 209.749 ways / 4.147 relations**; `check-refs` xác nhận **0 missing nodes in ways**. SHA-256 extract: `18fd3892f6d766387f2c3217d5d104e09a9319d3905a9172834b21c0064d6308`. Complete ways/relations có thể chứa vertices ngoài bbox; backend vẫn kiểm tra toàn bộ tuyến theo routing coverage. Không tuyên bố đã kiểm toán mọi turn restriction relation hoặc địa giới hành chính. [Extract metadata](m1b-qa/extract-metadata.json).

Attribution giữ **© OpenStreetMap contributors · Geofabrik**; dữ liệu OSM theo ODbL, xem [OSM copyright/license](https://www.openstreetmap.org/copyright). Khi phân phối lại derived data cần giữ attribution và nghĩa vụ license tương ứng. Không dùng public tiles/routing API; GeoJSON, font và worker đều local.

## 2. Pipeline và artifact identity

`scripts/pipeline.py --region nvmr-hanoi-core --profile car` dispatch sang `scripts/region_pipeline.py`; mặc định và các lệnh HCM cũ giữ nguyên. Chỉ CAR được allowlist. Output mới ở **`data/regions/nvmr-hanoi-core/`**, được Git-ignore:

```text
source-verification.json
extracted/coverage.osm.pbf + coverage.osm.metadata.json
render/{streets,water,green,buildings,places}.geojson + manifest.json
render/geometry-errors.log
routing/car/hanoi-core.osrm.* + manifest.json + router-evidence.json
pilot/  # raw live routes, plans, candidate audit, zero-policy, short-wait release
render-failed-strict-export/  # retained first failed render attempt, never served
```

Các stage có identity `{region_id,config_sha256,pipeline_version}` (`hanoi-car-pilot/v1`), source/extract hashes và artifact hashes. Dry-run không đọc dữ liệu/chạy Docker/ghi output. Rerun thực tế **đã REUSE** source, extract, năm render layers, graph và running router. Artifact thiếu, sai input/config/version/hash hoặc `.incomplete` làm pipeline fail; không overwrite graph/partial output. Khi muốn thay snapshot/config phải bảo quản namespace cũ có chủ đích trước; CLI không tự xóa dữ liệu. Source cùng bytes sau khi di chuyển có thể refresh cached path/stat qua `verify`; source khác bytes bị từ chối.

Năm render layers có tổng **21.766.990 bytes**: streets 23.763 features, water 267, green 1.300, buildings 50.717, places 168. Geometry được Osmium dựng và Python kiểm tra WGS84/type/ring. Chọn feature giao bbox render, **không clip tọa độ từng feature**; geometry hoàn chỉnh có thể tiếp tục ngoài vùng render. Source streets giữ `oneway`, OSM ID và tên cho audit. [Render manifest](m1b-qa/render-manifest.json).

**Lỗi dữ liệu thực đã gặp:** strict Osmium export dừng vì `Could not build area geometry`. Output lỗi được chuyển nguyên trạng vào `render-failed-strict-export`; không ghi đè. Riêng render Hà Nội dùng `--show-errors`, bỏ geometry Osmium không dựng được và lưu nguyên diagnostic trong log/manifest; không tạo geometry thay thế. Log có một dòng diagnostic nhưng không cung cấp OSM ID hay một thống kê đầy đủ về area bị bỏ. Vì vậy không tuyên bố map bao phủ hoàn hảo mọi polygon. HCM tiếp tục dùng `--stop-on-error`. Routing dùng extract gốc, không dùng bản render đã lọc.

## 3. CAR graph và readiness

OSRM **v5.27.1**, MLD: `osrm-extract -p /opt/car.lua` → `osrm-partition` → `osrm-customize`. Image pinned:

```text
ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124
car.lua SHA-256: cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3
```

[Graph manifest](m1b-qa/graph-manifest.json) lưu **25 Lua files/dependencies**, profile path/hash, image/version, source/input/extract identity và hashes/sizes của mọi graph artifact (**48.366.492 bytes**, không tính bản sao input PBF). Không dùng URL `/driving` làm bằng chứng profile.

Router riêng: **`gsm-map-osrm-hanoi-car`**, read-only mount vào `/data`, loopback **`127.0.0.1:5001`**, 1 GiB / 2 CPUs. HCM `gsm-map-osrm`, port 5000, graph cũ được giữ nguyên. `serve` kiểm tra image/command/mount/port/labels trước khi reuse container, không chiếm tên/port của container khác.

`backend/app/integrity.py` thêm kiểm tra content dành riêng artifact M1b; hash cache theo absolute path + file stat, không hash national PBF mỗi HTTP request. Readiness cần source/extract/render/graph đúng identity/hash và router evidence gắn với hash manifest. `serve` ghi ba nearest probes gồm snapped location và **OSRM graph-specific hint/checksum** sau khi xác nhận container mount/image. Backend đối chiếu lại probes; router HCM trả HTTP 200 cũng không làm Hanoi ready. Đây là ràng buộc kỹ thuật cho trusted local pipeline, không phải remote attestation chống người có quyền sửa disk/Docker.

Đã đối chiếu [OSRM v5.27.1 `hint.hpp`](https://github.com/Project-OSRM/osrm-backend/blob/v5.27.1/include/engine/hint.hpp): `SegmentHint` chứa phantom node và `data_checksum`. Probe dùng toàn bộ hint + location, không dùng checksum 32-bit như chữ ký bảo mật.

Map vẫn có thể ready khi graph/router chưa có; chỉ live capability bị khóa. Scoped API phân biệt missing artifacts `REGION_NOT_READY`, outage `ROUTER_UNAVAILABLE`, wrong graph `ROUTER_IDENTITY_MISMATCH`, route `NOROUTE/NOSEGMENT`, snap và invalid geometry. HCM v1 errors không đổi. Không có mutable active region hoặc fallback geometry/router.

## 4. Candidates và live pilot

Giữ thuật toán 24 anchors hiện có vì audit thật đáp ứng pilot: **24/24 snaps 0 m**, **552/552 directed non-self OD Table pairs có ETA**, 0 null pairs. Không cần thay sampling/dispatcher. Cache vẫn theo path/stat/operating bbox; fingerprint Hà Nội bổ sung config/graph manifest/source identity. [Candidate audit](m1b-qa/candidate-audit.json).

Sampler legacy thu hẹp mỗi cạnh operating bbox 20% trước chia lưới 6×4, tức dùng 60% chiều rộng/chiều cao ở giữa. Pilot vì vậy chưa đại diện nhu cầu trên toàn study area; không có trọng số dân số/nhu cầu GSM thật.

Lệnh `scripts/hanoi_pilot.py` gọi API qua ASGI và OSRM **HTTP thật**, không mock router; lưu raw evidence và assertions để rerun. [Pilot summary](m1b-qa/pilot-summary.json), [OSM node audit](m1b-qa/osm-oneway-nodes.json).

- 10 directed OD routes: positive distance/duration, real geometry/snaps; thêm route xuất phát ngoài display tại `[105.790,21.030]` nhưng trong routing coverage: PASS.
- Expected one-way constraints lấy từ **OSM source ways**, không suy từ OSRM: Bà Triệu `w408818507` 209,8 m xuôi / 605,7 m ngược; Tràng Thi `w684044681` 124,6 / 539,8 m. Audit riêng lấy node refs bằng Osmium `getid`, kiểm tra OSRM annotations không đi ngược source edges và forward route thực sự đi qua way: PASS.
- Invalid WGS84, outside routing, identical points, NoSegment tại `[105.85,21.07]`: lỗi thật đúng contract. Fixture kiểm tra thêm NoRoute, max snap, geometry ngoài coverage, timeout, metrics sai; không trả geometry giả.
- Seed **`hanoi-car-m1b-2026`**, 5 CAR, 20 requests: Booking hoàn tất **16**, unserved **4**; validator kiểm tra terminal lifecycle và không overlap xe. Lặp seed/config cho semantic payload giống nhau (bỏ timestamp/preparation latency).
- Voucher 5 CAR / 20 potential: Baseline **8 accepted / 8 completed**, Treatment **10 / 10**, spend **200.000 VND**, pickup wait TB **79,225 / 95,7 s**. CPIC của run này **100.000 VND**, không phải ước tính kinh tế thực tế của GSM.
- Potential/draws và initial fleet chung; decisions, state/ledger riêng; stable draws kiểm tra theo identity/seed/fingerprint. Lặp seed và zero-budget exact plan parity PASS, không đổi hệ số/model/event ordering.
- Stress `maxWaitSeconds=10`: Treatment **13 accepted, 3 completed, 10 unserved**, **10 RELEASED**, 60.000 VND settled, 0 reserved cuối run. Conservation và không biến failure thành completion: PASS.
- HCM/Hanoi route + Voucher đồng thời: fingerprints/coverage/contexts đúng. Trỏ Hanoi tới HCM router hoặc port không có service bị chặn: PASS.

**NOT VERIFIED:** live NoRoute island cụ thể chưa tạo/chọn được; fixture NoRoute PASS. Hai one-way cases không kiểm chứng toàn bộ restriction relations, biển báo hiện hành hoặc ETA giao thông thực. Không diễn giải pilot một seed như kết luận nhân quả/thị trường.

## 5. Frontend và exports

Tái sử dụng selector, scoped APIs, map style, hooks/cancellation và một MapLibre instance từ M1a. Hanoi thực tải năm layer local và viewport riêng. WebGL dev browser 1280×720: Single Trip **0,90 km / 86,4 s**, Fleet **5 xe + play/pause**, Booking **prepare/seek 500 s**, Voucher **prepare/seek/play/pause/final KPI** đều PASS. HCM→Hanoi→HCM clear prepared state/routes/markers; một canvas. Instance/clock identity và stale requests còn được unit tests kiểm tra. [Single Trip](m1b-qa/hanoi-single-trip.png), [Booking](m1b-qa/hanoi-booking.png), [Voucher](m1b-qa/hanoi-voucher.png).

Hanoi xuất **raw JSON plan + 5 CSV**; Portable v1 bị disabled, UI giải thích cần contract mới ở M5. Không gắn Hanoi vào `gsm-voucher-experiment/v1`. [Browser JSON](m1b-qa/hanoi-browser-plan.json) đã qua validator live frontend (geometry/lifecycle/pairing/ledger/KPI); 5 browser CSV khớp chính xác `experimentCsv` của JSON.

Saved HCM vẫn schema v1 và static assets cũ. Browser chọn Hanoi live rồi chuyển Saved: selector theo HCM artifact, tắt API QA port 8001, load/validate gói mẫu, seek 500 s, play/pause tới 500,52 s thành công. `/api` resource count **9 → 9**. Routers được giữ chạy để không can thiệp dịch vụ HCM; Saved không gọi chúng. File import/validation được regression suite kiểm tra. [Browser audit](m1b-qa/browser-check.json), [Saved backend off](m1b-qa/saved-hcm-backend-off.png).

GeoJSON ~21,8 MB đã render được; chưa có FPS/heap/performance benchmark hay production browser QA. Chưa có bằng chứng cần vector tiles ở pilot này. Không tăng limits hoặc DOM marker count tới hàng nghìn.

## 6. Dựng/chạy lại

Prerequisites: Python venv/dependencies của repo, Docker Linux Engine, hai image trên đã pull, PBF cùng checksum ở `data/raw`; Git clone không có graph/PBF/GeoJSON được ignore. Đảm bảo khoảng trống disk/RAM cho Osmium; phiên chạy có Docker RAM ~8 GiB, mỗi Osmium command cap 5 GiB, preprocessing OSRM cap 2 GiB. Không chạy pipeline legacy để tạo Hanoi.

Root PowerShell, từng lệnh phải thành công trước khi sang stage phụ thuộc:

```powershell
.\.venv\Scripts\python.exe scripts/pipeline.py extract --region nvmr-hanoi-core --profile car --dry-run
.\.venv\Scripts\python.exe scripts/pipeline.py verify --region nvmr-hanoi-core --profile car
.\.venv\Scripts\python.exe scripts/pipeline.py extract --region nvmr-hanoi-core --profile car
.\.venv\Scripts\python.exe scripts/pipeline.py display --region nvmr-hanoi-core --profile car
.\.venv\Scripts\python.exe scripts/pipeline.py routing --region nvmr-hanoi-core --profile car
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/hanoi_pilot.py
```

HCM existing router được kiểm tra và không cần rebuild. Khi graph HCM đã có và không có container chiếm tên/port, workflow cũ: `python scripts/pipeline.py serve --detach`. Không tự dừng/xóa container đang chạy của người dùng.

Khởi động/restart FastAPI sau khi cập nhật source để registry snapshot nhận config mới:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# Terminal khác:
Set-Location frontend
npm.cmd run dev
```

Phiên QA dùng port **8001/5174** vì **8000/5173 đã có process của người dùng**. `GSM_API_PROXY` là override dev tùy chọn trong Vite, default vẫn 8000. Ví dụ API chạy 8001: `$env:GSM_API_PROXY='http://127.0.0.1:8001'; npm.cmd run dev -- --port 5174`. API 8001 đã tắt để kiểm tra Saved, sau đó mở lại bằng source cuối; **giữ 8001/5174 và router Hanoi chạy để review tại http://127.0.0.1:5174/**. Các process ban đầu được giữ nguyên. Nếu dùng lại port thường 8000/5173, backend cũ không có auto-reload cần restart để dùng source mới. Đây là dev runtime, không phải deployment production.

## 7. Verification thực chạy

| Command/check | Kết quả |
|---|---|
| `$env:RUN_REAL_DATA='1'; .\.venv\Scripts\python.exe -m pytest -q` | **PASS 149**, không skip, 83,37 s; gồm cả 5 opt-in real-data HCM |
| Trước integration: opt-in `-k real_` trong A1–A4 | **PASS 5**, 93 deselected; mọi protected input thực tồn tại |
| Backend không opt-in (trước 6 scoped negative cases cuối) | **PASS 138, SKIPPED 5**; final full opt-in ở trên đã chạy cả cases mới |
| `pytest -q tests/test_m1b.py` sau chỉnh pipeline cuối | **PASS 11** |
| `frontend`: `npm.cmd test -- --maxWorkers=2` | **PASS 151 / 13 files**, 26,98 s |
| `npm.cmd test` lần đầu, 13 workers đồng thời browser/build | **FAIL 1 timeout / PASS 150**; rerun toàn suite 2 workers PASS, không đổi assertion/timeout |
| `npm.cmd run lint` | **PASS exit 0**, 13 warnings React effects/refs/Fast Refresh có từ trước |
| `npm.cmd run typecheck`; `npm.cmd run build` | **PASS**; Vite warning main chunk >500 kB (~1.426 kB minified / 403 kB gzip) |
| `npm.cmd run verify:replay` | **PASS 9 assets**, digest v1 `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`; verifier `browserExports=NOT_RUN` cho HCM portable re-export |
| `node scripts/verify-region-pilot.mjs` (frontend) | **PASS** Hanoi browser JSON domain validation + **5 exact CSVs** |
| Pipeline dry-run / real build / stage reuse / live pilot | **PASS**; lỗi render đầu tiên và cách phục hồi ghi ở mục 2 |
| Browser dev WebGL | **PASS** các luồng ở mục 5; console warning/error captured rỗng trong audit cuối |
| SHA-256 296 protected baseline files | **PASS: 0 changed**, [preservation check](m1b-qa/preservation-check.json) |
| `git diff --check`; Python compileall module mới | **PASS**; Git LF→CRLF notices, không whitespace errors |

Starlette/httpx TestClient có deprecation warning. Uvicorn Windows ghi một `WinError 10054` khi kết nối client bị đóng trong thao tác hủy/chuyển region; các API/pilot vẫn PASS, không xuất partial plan. Browser automation từng timeout do chọn checkbox trong khi control là button; khôi phục bằng control đúng và xác minh Saved thành công. Không tính automation timeout là product PASS.

## 8. Files, compatibility và bước tiếp theo

Source/config sửa: `.gitignore`, `backend/app/{regions,dataset,fleet,main}.py`, `config/regions/nvmr-hanoi-core.json`, `scripts/{pipeline,render_data}.py`, `frontend/src/components/voucher-dashboard.tsx`, `frontend/vite.config.ts`, fixture setup `tests/test_regions.py`. Mới: `backend/app/integrity.py`, `scripts/{region_pipeline,hanoi_pilot}.py`, `tests/test_m1b.py`, `frontend/tests/region-export.test.tsx`, `frontend/scripts/verify-region-pilot.mjs`, báo cáo này và evidence `m1b-qa/`.

Không đổi schema v1, `booking.py`, `voucher.py`, model versions, ledger, event ordering, default seeds hoặc HCM fingerprint inputs. Test M1a placeholder giữ nguyên assertions, chuyển setup sang explicit disabled fixture để không phụ thuộc máy local đã dựng Hanoi hay chưa. Lưới 24 anchors/limits ≤10 xe/≤30 potential giữ nguyên. HCM PBF/extract/graph/render/manifests, `config/region.json`, M0/M1a và `docs/evidence` đều hash không đổi. Ba M0 docs và bốn file `docs/evidence/a4.1/*` untracked trước M1b được giữ nguyên. Không chạm repo khác; **chưa stage/commit/push/merge**.

M1 core pilot đã hoạt động; còn giới hạn xác minh live NoRoute, turn-restriction coverage sâu hơn, map performance/production smoke. Các mục này không được đánh dấu PASS ngầm. Hanoi portable replay còn ngoài phạm vi, dành M5.

**M2 đề xuất:** bổ sung service/vehicle type CAR/MOTORBIKE ở contract mới và registry mode-specific; giữ CAR v1 adapter. Xây MOTORBIKE profile độc lập có rules/fixtures và directed OD oracle phù hợp Việt Nam, pin dependencies/graph riêng, kiểm chứng access/oneway/restrictions/motorway/service-road trước mở readiness. Sau đó tích hợp fleet/request type và pickup ETA theo mode trên pilot nhỏ. Không lấy graph CAR hoặc chỉ đổi tốc độ để gọi là MOTORBIKE; chưa triển khai multimodal choice, worker hay scale 5.000 trong bước này.
