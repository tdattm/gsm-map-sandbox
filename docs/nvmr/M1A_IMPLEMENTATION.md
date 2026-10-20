# M1a — Multi-region foundation

Ngày bàn giao: **16/10/2026**, Asia/Saigon. M1a đã triển khai; chưa tạo dữ liệu/graph Hà Nội và chưa triển khai M1b/M2–M7. Ba tài liệu M0 được giữ nguyên.

## Implementation

- `RegionRegistry` là allowlist server-side, mapping read-only; mỗi `RegionContext` là frozen snapshot với nested region/coverage tuples bất biến. Không có mutable `active_region`. Cả legacy HCM và region-explicit requests resolve/pin context trước khi dùng paths/router.
- `hcm-center` giữ `config/region.json`, PBF/render/graph paths, loopback URL và fingerprint algorithm/input hiện có. `nvmr-hanoi-core` có technical viewport định hướng từ config riêng; operating/routing/render coverage đều null, router chưa cấu hình và `enabled=false`. File có sẵn trong namespace khác không thể làm Hanoi ready.
- Context phân biệt viewport, operating bbox để chọn/snap anchors, routing bbox để validate đường đi và render bbox để kiểm tra manifest/assets. HCM giữ cả điều kiện route trong display của A2/A3/A4; region mới dùng routing coverage cho geometry. Đây là bbox foundation; polygon/admission/data verification còn ở M1b.
- Route/Booking/Voucher adapters dùng chung `calculate_route`, `LocalTravel`, `build_plan`, `prepare_experiment`; không nhân bản dispatcher/ledger. Candidate cache dùng path/stat/bbox; fingerprint region mới thêm identity/coverage, HCM không thêm field. Travel cache sống trong một preparation, không share mutable simulation state giữa region/run.
- Frontend mặc định HCM và tiếp tục dùng `/api/*` legacy cho HCM. Selector đọc registry; region khác dùng scoped URL. Đổi region abort và clear live state/selection/focus/cache; stale responses bị bỏ qua. Catalog/plan/experiment kiểm tra provenance region trước publish; metadata status cũng kiểm tra identity.
- Map styles resolve năm source theo region; viewport sync dùng MapLibre instance hiện tại, không remount map/clock. Hanoi hiển thị NOT READY và khóa cả Single/Fleet/Booking/Voucher preparation.
- Saved v1 bỏ registry/dataset polling, region selector bị khóa theo HCM artifact. Import/seek/playback vẫn dùng validator/model/assets v1; thay live region không giải thích lại Saved payload. Schema/versions/canonicalization không đổi.

## API mới

| Method/path | Ý nghĩa |
|---|---|
| `GET /api/regions` | Default ID và metadata/readiness/mapReady của allowlist |
| `GET /api/regions/{id}/dataset/status` | Public status đã bỏ system paths, manifest nội bộ và router URL |
| `GET /api/regions/{id}/map/{layer}` | GeoJSON đúng namespace, allowlist năm layer; không cần OSRM online khi render assets đã ready |
| `GET /api/regions/{id}/fleet/candidates` | Candidate catalog đúng operating area/artifacts |
| `POST /api/regions/{id}/route` | Body giữ `{start,end}`, CAR routing theo context |
| `POST /api/regions/{id}/booking-simulation/prepare` | Body giữ PrepareRequest, dùng dispatcher chung |
| `POST /api/regions/{id}/voucher-experiment/prepare` | Body giữ ExperimentRequest, pairing/ledger/KPI chung |

Unknown ID: HTTP 404 `UNKNOWN_REGION`; region chưa ready: HTTP 503 `REGION_NOT_READY`. Không fallback HCM/router công cộng/geometry giả. Strict v1/new preparation bodies vẫn từ chối extra `regionId`, arbitrary path/router URL. `/api/route`, `/api/dataset/status`, `/api/fleet/candidates`, `/api/map/*` và prepare v1 giữ contracts/error semantics hiện có.

Metadata/status API mới chỉ trả thông tin công khai cần cho UI. Provenance của payload legacy HCM được giữ nguyên, bao gồm `router_url`, để bảo toàn fingerprint và exports v1; không tuyên bố endpoint legacy đã được redaction.

Ví dụ khi chưa làm M1b:

```text
GET /api/regions/nvmr-hanoi-core/dataset/status
→ 200, ready=false, coverage={operating:null,routing:null,render:null}

POST /api/regions/nvmr-hanoi-core/voucher-experiment/prepare   {}
→ 503, error.code=REGION_NOT_READY
```

## Verification thực chạy

| Check | Kết quả |
|---|---|
| Root: `.\.venv\Scripts\python.exe -m pytest -q` | **PASS: 133 passed, 5 skipped**, 33,08 s; 1 Starlette/httpx TestClient deprecation warning |
| `frontend`: `npm.cmd test` | **PASS: 150 tests, 12 files**, 12,97 s |
| `frontend`: `npm.cmd run lint` | **PASS exit 0**, 13 React effect/ref/fast-refresh warnings; không warning-free |
| `frontend`: `npm.cmd run typecheck` và `npm.cmd run build` | **PASS**; build gồm `tsc -b`; Vite có warning chunk >500 kB (main ~1.426 kB minified / 403 kB gzip) |
| `frontend`: `npm.cmd run verify:replay` | **PASS package + 9 assets**; digest `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`; verifier `browserExports=NOT_RUN` |
| Test region bổ sung cuối: `npm.cmd test -- tests/regions.test.tsx` | **PASS 9/9** sau khi thêm assertions cả bốn live modes đều disabled ở Hanoi; không thay product code sau full suite |
| Actual local HCM catalog: Settings legacy vs frozen context | **PASS equality**, 24 candidates, fingerprint `9193a3a34bd10f14a21da7121552503971f85419d7241aeb71bc7193eaac3341` |
| SHA-256 năm render layers vs existing manifest | **PASS** |
| Hash baseline 253 files: M0, toàn bộ `docs/evidence`, `config/region.json`, contracts | **PASS: 0 thay đổi** |
| `git diff --check` | **PASS**; Git có LF→CRLF notices trên một số file, không whitespace errors |

Backend fixtures dùng bytes/GeoJSON synthetic và mocked loopback OSRM; không coi chúng là Hanoi GIS/graph thật. Tests mới chứng minh immutable snapshots, namespace/path/router isolation, concurrent preparation/route use, HCM explicit-vs-legacy semantic parity, strict extras, unknown/unready và coverage không đồng nhất viewport. Tests không so timestamp/preparation latency như outcome khoa học.

Frontend tests chứng minh HCM→Hanoi→HCM, metadata/viewport commands, map mount/clock reuse, stale status/route/preparation rejection, cache isolation kể cả fixture cố tình reuse fingerprint và Saved v1 import/seek độc lập region. `dashboard.test.tsx` chỉ thêm mock cho dependency registry mới; toàn bộ assertions legacy được giữ nguyên. New region tests dùng network mocks riêng cho integration.

### Browser QA thực tế

IAB browser, Vite dev, MapLibre WebGL thật; đã xem narrow layout 716×659 và desktop 1440×900. HCM→Hanoi→HCM giữ một canvas và cùng lifetime token. Hanoi không hiển thị xe HCM, thông báo graph/coverage chưa xác minh, khóa live actions. HCM map layer requests trả 200 khi routing offline; các mode vẫn mở/hiển thị trạng thái readiness.

Sau khi chọn Hanoi live rồi chuyển Saved, **tắt backend do phiên QA khởi chạy**, tải/validate gói HCM v1, seek 500 s, play/pause thành công. Canvas vẫn cùng token; số resource `/api/*` giữ 11 trước/sau thao tác Saved, không có API mới. Không thấy console error/warn trong lượt kiểm tra. [QA JSON](m1a-qa/browser-check.json), [Hanoi NOT READY](m1a-qa/hanoi-not-ready.png), [Saved với backend tắt](m1a-qa/saved-backend-off.png).

Giới hạn: browser QA dùng dev runtime, không phải production browser/performance benchmark. Viewport values/jumpTo được kiểm thử qua unit adapter; actual map center không được instrument trong browser. Fresh browser export/CSV roundtrip không chạy lại, dù package verification/import/seek đã PASS.

**SKIPPED:** năm opt-in `RUN_REAL_DATA` tests cần dữ liệu/OSRM thật. **NOT VERIFIED:** live routing/booking/voucher completion vì router local không chạy; Hanoi live GIS/OSRM chưa tồn tại theo scope. Docker CLI/Engine phản hồi nhưng không có running OSRM container trong phiên kiểm tra; không tự start/rebuild routing services.

## Còn lại cho M1b

Chọn và kiểm chứng technical operating/render/routing coverage Hà Nội, mapping ranh giới/tên OSM/snapshot; chuẩn bị source verification, GeoJSON/candidates và CAR graph MLD ở namespace Hanoi, manifests/hashes và endpoint loopback riêng. Chỉ enable registry entry khi đủ coverage/service/assets được kiểm chứng. Không dùng viewport định hướng trong config hiện tại làm graph coverage mặc định.

Chạy directed live route/snapping/NoRoute/boundary/detour cases; phục hồi HCM OSRM và chạy năm real-data regressions; smoke HCM/Hanoi concurrent API + browser. Kiểm tra route đi ngoài viewport nhưng trong routing coverage và asset coverage tương ứng. Packaging Saved v1 vẫn phục vụ HCM; chưa cung cấp Hanoi replay package hoặc schema mới. Không thêm MOTORBIKE/worker/5.000 xe trong M1b foundation nếu chưa có task tương ứng.

## File thay đổi trong M1a

- Backend: `backend/app/regions.py` (mới), `main.py`, `dataset.py`, `fleet.py`, `booking.py`.
- Config: `config/regions/nvmr-hanoi-core.json` (mới).
- Frontend shell/map: `frontend/src/App.tsx`, `App.css`, `components/sandbox-map.tsx`, `lib/map-style.ts`.
- Frontend transport/state: `frontend/src/lib/api.ts`, `use-region.ts` (mới), `use-fleet.ts`, `use-booking.ts`, `use-voucher.ts`, `fleet.ts`.
- Batch integration: `frontend/src/components/batch-analysis.tsx`, `voucher-dashboard.tsx`.
- Tests: `tests/test_regions.py` (mới), `frontend/tests/regions.test.tsx` và `region-map.test.tsx` (mới), mock setup trong `frontend/tests/dashboard.test.tsx`.
- Handoff: tài liệu này và `docs/nvmr/m1a-qa/{browser-check.json,hanoi-not-ready.png,saved-backend-off.png}`.

Không sửa `schemas.py`, `voucher.py`, `config/region.json`, artifact/replay decoder/schema, package/lockfiles, ba tài liệu M0 hoặc repo `gms-voucher-research-demo`. Không chạy pipeline GIS/OSRM, không đổi graph/render assets hoặc evidence cũ. Bốn file evidence untracked từ trước vẫn giữ nguyên. Build/verifier chỉ cập nhật output đã Git-ignore. Chưa stage/commit/push/merge. API/Vite phục vụ QA đã được dừng sau kiểm tra.
