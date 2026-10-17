# M2 — CAR/MOTORBIKE routing và mixed Fleet/Booking

Tái dựng ngày **17/10/2026** từ baseline Git `455abeb`, source, tests, README và [m2-evidence](m2-evidence/). Đây là báo cáo phần mềm nghiên cứu: demand, giá cước và ETA là synthetic/model-based, không phải dữ liệu vận hành GSM. M3/M4 có báo cáo riêng; kết quả của chúng không được dùng để sửa lại lịch sử M2.

## 1. Phạm vi và contract

M2 mở rộng Hanoi Core từ CAR sang CAR/MOTORBIKE với graph/profile riêng, mode readiness, Single Trip, Fleet và Booking hỗn hợp. Không triển khai choice model NO_BOOK/CAR/MOTORBIKE hoặc Voucher đa phương tiện.

`VehicleType = CAR | MOTORBIKE`. `MixedRequest` kế thừa `PrepareRequest` nhưng thêm mảng `vehicleTypes` và `serviceTypes` có độ dài đúng fleet và booking count. Giới hạn M2: 1–10 xe, 10–30 bookings, horizon 60–3600 s, max wait 10–900 s. Không tăng giới hạn legacy để đạt fleet M3. Vehicle/booking IDs ổn định; service phải khớp đúng loại xe, không tự thay CAR bằng MOTORBIKE. M2 dùng dispatcher/lifecycle chung của `booking.py`, chia travel adapter và routing cache theo mode.

Response `gsm-multimodal-scenario/v1` chứa `regionId`, config, `routingIdentities`, plan và assumptions. Plan thêm `vehicleType` cho vehicles/assignments, `serviceType` cho demand và routing identity cho từng assignment. Tọa độ WGS84 `[longitude, latitude]`, distance m, duration s; simulation seconds độc lập wall-clock. Đây không phải Portable Saved Replay v1.

Routing identity chứa region, vehicle type, profile, profile SHA-256, graph manifest SHA-256, source/extract SHA-256 và algorithm MLD. `/driving` trong URL OSRM không chứng minh profile; identity phải khớp graph đã build và router đã kiểm tra.

## 2. MOTORBIKE profile, assumptions và giới hạn

[motorbike.lua](../../profiles/motorbike.lua) và [motorbike.json](../../profiles/motorbike.json) định nghĩa `hanoi-electric-motorcycle/v1`: mô tô điện hai bánh, giả định thiết kế 70 km/h, 6 kW, không phải moped. Tốc độ, surface/turn penalties chưa hiệu chuẩn với giao thông thực.

- Access ưu tiên motorcycle → motor_vehicle → vehicle → access; private/destination/conditional/ambiguous bị từ chối bảo thủ.
- Loại motorway, motorway_link, motorroad=yes ngay cả khi motorcycle=yes.
- One-way ưu tiên tag theo mode, xử lý roundabout; reversible/conditional bị từ chối.
- Turn restrictions theo hierarchy/except của parser upstream; conditional và via-way ngoài các fixture đã thử còn UNKNOWN.
- Barrier chỉ allowlist no/entrance/toll_booth/border_control; gate/bollard/unknown bị chặn bảo thủ.
- Bridge/tunnel theo highway/access/dimensional constraints, không có blanket permission.

Profile là giả định kỹ thuật cho pilot OSM tĩnh. Chưa chứng nhận biển báo hiện trường, tính pháp lý từng tuyến, đầy đủ turn restrictions hoặc ETA thực tế. Các nguồn được lưu trong JSON assumptions; nhiệm vụ M3/M4 không kiểm toán lại các nguồn pháp lý đó.

## 3. Graph/source identity và pipeline

Reuse Vietnam PBF snapshot `2026-10-09T20:21:04Z`, SHA-256 `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`; Hanoi extract SHA-256 `18fd3892f6d766387f2c3217d5d104e09a9319d3905a9172834b21c0064d6308`. Study area và render/routing buffers theo [M1b](M1B_IMPLEMENTATION.md), không phải địa giới toàn NVMR.

| Identity lịch sử | CAR | MOTORBIKE |
|---|---|---|
| Profile SHA-256 | `cb3df0546318665609606b746a1297f3d65ca3c2ff825f8a6f3c57247d86a2d3` | `075ecdbc70a3e75c4338d2c6a41597c132a1837ec2d27f1c2fcdd824a788b209` |
| Graph manifest SHA-256 | `a24d4957a01ceeb04a0de1ad680fe4c5dd51732a7b381d9368e249a65c1b29b5` | `fb97489d066397b11cb9178238cd56a5f52281bcf5711430bb7cf411496ca455` |
| Router | `gsm-map-osrm-hanoi-car`, :5001 | `gsm-map-osrm-hanoi-motorbike`, :5002 |

OSRM image pin: `ghcr.io/project-osrm/osrm-backend@sha256:855614a38f464b0558a2ad6eaa7cb8c139f39887da9b38b485ce453c6e6e6124`. HCM router :5000 và graph cũ giữ nguyên. Graph/PBF/render đặt trong `data/`, Git-ignore; clone Git không đủ dữ liệu để chạy live.

`scripts/pipeline.py` dispatch profile MOTORBIKE sang `motorbike_pipeline.py`. Mỗi mode có graph manifest, source/extract/profile/dependency hashes, router evidence và validation riêng. `modes.py` pin frozen context, kiểm tra graph files và validation/evidence digests; `.incomplete` hoặc `.validation-incomplete` làm fail-closed. Router probes kiểm tra graph-specific hint/checksum, không chỉ HTTP 200 từ nearest. Không fallback CAR graph hoặc public router.

## 4. Backend, frontend và API

Backend chính: `backend/app/modes.py`, `multimodal.py`, mode endpoints trong `main.py`, mode filtering trong `booking.py`. Metadata/catalog validation chạy bằng `asyncio.to_thread` để checksum I/O không chặn event loop. Config MOTORBIKE là server allowlist, không nhận arbitrary OSRM URL/path từ client.

Frontend chính: `frontend/src/lib/multimodal.ts`, mode selector và các Single/Fleet/Booking adapters trong shell. `validateMixed` kiểm tra schema/region/config/type/assignment/candidate/routing identity trước publish. Đổi region/mode abort và bỏ response cũ. Fleet hỗn hợp tạo từng mode riêng rồi ghép identity; cache không dùng chéo graph. Tổng xe/yêu cầu giữ nghĩa tổng, mix xen kẽ (10 xe = 5 CAR + 5 MOTORBIKE).

| API | Ý nghĩa |
|---|---|
| `GET /api/v2/regions/{regionId}/modes` | Readiness từng mode và public routing identity |
| `GET .../modes/{CAR|MOTORBIKE}/candidates` | Catalog/provenance theo mode |
| `POST .../modes/{CAR|MOTORBIKE}/route` | `{start,end}` → `gsm-mode-route/v1` |
| `POST /api/v2/regions/{regionId}/booking-simulation/prepare` | MixedRequest → mixed scenario |

Legacy `/api/*`, region-scoped CAR v1, Voucher model/ledger và Saved checksums/contracts giữ riêng. Unknown region/type, mode not ready, graph mismatch, no route và router unavailable có lỗi rõ ràng; outage không tạo partial plan hoặc geometry giả.

## 5. Mixed dispatch và lifecycle

FIFO theo request time/booking ID, full pickup route phải đến trước hoặc đúng inclusive maximum wait. Chỉ Table ETA của idle vehicles cùng loại được xét. Full route xác nhận snap continuity trước assignment; null pickup route chỉ khi xe thực sự đứng tại validated pickup. Giải phóng xe trước arrivals/dispatch ở cùng timestamp; không double assignment hoặc overlap. Horizon là cửa sổ arrivals, sau đó drain đến terminal demand; không ép hoàn tất tại horizon.

M2 vẫn exhaustive Table trên toàn bộ compatible idle fleet nhỏ và scan lịch sử theo legacy engine. Giới hạn 24 catalog anchors là sampling của M2, không chứng minh giới hạn capacity M3. M3 thêm contract/engine riêng thay vì sửa legacy model.

## 6. Bằng chứng lịch sử M2 (không phải rerun M3/M4)

Nguồn: [verification.json](m2-evidence/verification.json), [pilot-summary.json](m2-evidence/pilot-summary.json), [browser-check.json](m2-evidence/browser-check.json), [synthetic-validation.json](m2-evidence/synthetic-validation.json), [real-mode-cases.json](m2-evidence/real-mode-cases.json).

| Check lịch sử, 17/10/2026 trước nhiệm vụ này | Kết quả lưu trong evidence |
|---|---|
| Backend với `RUN_REAL_DATA=1` | 164 PASS, 0 skipped; Starlette/httpx deprecation warning |
| Frontend | 159 PASS, 15 files |
| Lint/typecheck/build | Exit 0; lint 13 warnings; main chunk 1433,42 kB warning |
| Mixed pilot | 5 CAR + 5 MOTORBIKE, 20 requests, 20 completed, 0 unserved; 10 assignments/mode |
| Repeat | Semantic equality bỏ wall-clock preparation metadata |
| Profile validation | 58 synthetic directed cases PASS; real directed OSM cases và one-way checks PASS trong phạm vi lưu |
| Router identity/outage | CAR router không được nhận như MOTORBIKE; CAR outage không chặn MOTORBIKE; HCM live route PASS |
| Candidate audit | 24 MOTORBIKE anchors, nearest/table audit; không đại diện mọi đường Hà Nội |
| Browser | Single CAR/MOTORBIKE, mixed Fleet/Booking, typed inspector PASS |
| Hanoi Voucher CAR | Baseline 8 completed, Treatment 10 trong seed mẫu; model-based, không phải empirical uplift |
| Exports | Mixed raw JSON và Hanoi CAR Voucher JSON + 5 CSV validated |
| Saved HCM | Offline sample validate/seek/play PASS khi backend kiểm chứng ngừng kết nối; browser file chooser import NOT VERIFIED |
| Replay package | PASS, 9 assets; browser portable re-export NOT RUN |
| Preservation | 2897 protected files, changed=[] trong evidence lịch sử |

`parallel-pilot-failure.txt` giữ một lần lỗi đã xảy ra: checksum I/O đồng bộ gây event-loop blocking và false ROUTER_UNAVAILABLE dưới concurrency. Evidence cuối ghi đã sửa bằng thread offload và heartbeat regression, không tăng timeout hoặc nới assertion. Không xóa evidence thất bại này.

Ảnh lịch sử: [mixed Booking](m2-evidence/mixed-booking.png), [mixed Fleet](m2-evidence/mixed-fleet.png), [Hanoi CAR Voucher](m2-evidence/hanoi-car-voucher.png), [Saved backend off](m2-evidence/saved-hcm-backend-off.png).

## 7. Kiểm chứng trong nhiệm vụ M3/M4

Baseline thực chạy trước sửa source: `.venv\Scripts\python.exe -X utf8 -m pytest -q` → **158 passed, 6 skipped**, 17,18 s. Sáu test live là opt-in; kết quả này không thay thế 164 PASS lịch sử. Log local `build/m3-m4/baseline-backend.log` (ignored).

Đã bật lại `RUN_REAL_DATA=1` trên baseline hiện tại: **164 passed, 0 skipped**, 39,56 s (`baseline-backend-live.log`). Frontend baseline thực chạy `npm.cmd test -- --maxWorkers=2`: **159 passed, 15 files**, 15,84 s (`baseline-frontend.log`). Đây là kết quả mới của nhiệm vụ này; không bao gồm rerun preprocessing/profile certification hoặc browser import đã nêu UNKNOWN.

Các kết quả rerun live, frontend và integration sau tích hợp được ghi riêng trong [M3/M4 integration review](M3_M4_INTEGRATION_REVIEW.md). File evidence M2 lịch sử được giữ nguyên; rerun pilot dùng `run(write=False)` và output namespace `build/m3-m4/`.

Sau tích hợp: full backend live **189 PASS**, frontend **167 PASS** (có thêm tests M3/M4). Hanoi CAR Voucher cũng rerun hai lần với seed mới `m3-m4-hanoi-car-regression`,5 CAR/20 potentials: Baseline14 completed, Treatment18, semantic repeat và existing `check_experiment` paired/lifecycle/ledger audit PASS; [evidence mới](m3-m4-evidence/hanoi-car-voucher-regression.json). Đây là seed/config khác, không thay thế8/10 lịch sử, không phải observed uplift. Saved HCM production sample seek/play được kiểm chứng lại khi task API8013 tắt; browser chooser roundtrip vẫn NOT VERIFIED. Không rebuild hoặc kiểm toán lại profile58 cases trong nhiệm vụ này vì source/profile/evidence hashes không đổi và live readiness/regression PASS.

## 8. Chạy lại và reproducibility

Từ project root PowerShell; reuse artifacts đã xác minh, không rebuild mặc định:

```powershell
.\.venv\Scripts\python.exe scripts/pipeline.py serve --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
.\.venv\Scripts\python.exe -X utf8 -c "import json; from scripts.multimodal_pilot import run; print(json.dumps(run(write=False)))"
$env:RUN_REAL_DATA='1'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
Remove-Item Env:RUN_REAL_DATA
Set-Location frontend
npm.cmd test -- --maxWorkers=2
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run verify:replay
node scripts/verify-multimodal.mjs
Set-Location ..
```

`scripts/multimodal_pilot.py` không có `write=False` CLI flag: gọi hàm như trên để giữ evidence lịch sử. Chạy CLI trực tiếp sẽ ghi lại ba evidence pilot. `validate_motorbike.py` có tạo synthetic graphs/container tạm và cập nhật validation evidence: chỉ chạy khi cần xác minh lại profile/graph, không cần cho mỗi startup.

Seed/config/dataset/graph/profile identities trong payload đủ pin semantic input của pilot; createdAt/preparationMilliseconds không dùng cho semantic equality. Không coi HTTP response order là dispatch ordering. Saved v1 vẫn dùng geometry artifact, không gọi OSRM để thay tuyến.

## 9. Chưa hỗ trợ và rủi ro còn lại

M2 không có large-fleet engine, durable jobs, online schedules, spatial shortlist, multimodal Voucher choice, multimodal portable replay, traffic calibration, GPS/observed demand hoặc production deployment. MOTORBIKE chỉ Hanoi Core; HCM MOTORBIKE fail-closed. OSM thiếu/sai tag, conditional/via-way ngoài coverage, surface/barrier assumptions và route endpoint feasibility vẫn là giới hạn. Mixed contracts mới không được coi như Saved v1. Pilot nhỏ và fixture PASS không chứng minh mọi OD, mọi graph hoặc capacity 5000 xe.
