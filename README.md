# GSM Map Sandbox

PoC mô phỏng hành trình, đội xe và voucher trên bản đồ OSM thật, dùng OSRM local. Ngoài TP.HCM và Hanoi Core, R1a bổ sung scenario thống nhất Hanoi + **Bắc Ninh Core technical pilot**, CAR/MOTORBIKE có graph riêng. Booking, phân bổ fleet, giá cước, ETA và voucher là giả định nghiên cứu, không phải dữ liệu vận hành hay GPS thực tế của GSM.

## R1b — Unified Connected NVMR

Kiến trúc mục tiêu hiện hành là **một miền Bắc liên thông**, thay cho kế hoạch mở rộng nhiều simulation tỉnh độc lập: một graph CAR, một graph MOTORBIKE riêng, một global fleet/booking/dispatch/event engine/clock và một bản đồ vector tiles offline. Phạm vi bản đồ liên tục bao phủ Hà Nội, Bắc Ninh, Hưng Yên, Phú Thọ và Thái Nguyên sau sáp nhập2025; operating zones là vùng kỹ thuật có phiên bản, không phải polygon hành chính chính thức. Địa phương lân cận nằm trong rectangle không tự được thêm vào nghiên cứu.

Trong **Mô phỏng quy mô lớn → Kịch bản mô phỏng → Miền Bắc liên thông**, v5 có default5.000 xe tổng (2.000CAR+3.000MOTORBIKE), phân bổ4.000/250/250/250/250. Custom allocations và nhu cầu theo zone độc lập với fleet. Xe cùng mode được shortlist trên toàn vùng rồi kiểm ETA bằng OSRM; không bị loại chỉ vì khác zone. v3 Hanoi, v4 R1a và HCM/Saved Replay tiếp tục có contract riêng.

Trạng thái triển khai, các bước đã chạy, blockers và quyết định GO/M5 nằm trong [báo cáo R1b](docs/nvmr/R1B_CONNECTED_IMPLEMENTATION.md), [runbook PowerShell](docs/nvmr/R1B_CONNECTED_RUNBOOK.md), [GIS/provenance](docs/nvmr/R1B_CONNECTED_GIS.md), [v5 contract](contracts/nvmr/CONNECTED_V1.md) và [checkpoint phục hồi](docs/nvmr/R1B_PROGRESS.md). Có source/UI không có nghĩa các graph và live acceptance đã READY; kiểm tra report/checkpoint trước khi demo. Không tải PBF mới khi snapshot cũ hợp lệ, không rebuild/overwrite artifact đã verify.

## R1a — Hanoi + Bắc Ninh Core (historical, v4 compatibility)

Từ **Mô phỏng quy mô lớn → Kịch bản mô phỏng**, chọn Hanoi legacy v3 hoặc NVMR hai vùng. Regional v4 có một job/store/worker, một clock, phân bổ tối đa **5.000 xe tổng qua hai vùng**, tổng và KPI theo vùng, overview extent, drill-down tải một basemap và immutable pickup/trip inspector. Bắc Ninh là vùng kỹ thuật thí điểm quanh đô thị cũ, **không phải toàn tỉnh sau hợp nhất năm 2025**. Không điều phối xuyên vùng hay đổi graph CAR/MOTORBIKE.

Local CAR/MOTORBIKE Bắc Ninh đã build/verify; live regional20/100/500/5.000 PASS, gồm persist/reopen và independent counts/KPI/route audit. Run5.000 có2.000CAR+3.000MOTORBIKE/1.250requests,1.225completed/25unserved. Đây là bằng chứng backend trong workload đã đo. Browser capture5.000 tổng/2.500 xe vùng chi tiết có cluster oracle PASS nhưng RAF thấp (~1,9FPS trong capture ngắn); **chưa chứng nhận UI5.000 mượt, Meet thật hoặc production**. M4 profiling đã được owner đóng, không mở lại trong R1a.

```powershell
# Chỉ serve graph đã verify; không preprocess hoặc download lại.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Profile Meeting -Routers Regional -StartRouters -ApiPort 8021 -FrontendPort 5191 -Store build/r1a/jobs
```

Cần fresh `npm.cmd run build` trong frontend trước Meeting; API/worker cũ phải được restart tại đúng process của mình để nhận v4. Xem [runbook PowerShell](docs/nvmr/R1A_RUNBOOK.md), [báo cáo tích hợp chi tiết](docs/nvmr/R1A_IMPLEMENTATION.md), [GIS/provenance](docs/nvmr/R1A_GIS.md), [backend contract](docs/nvmr/R1A_BACKEND.md), [checkpoint phục hồi](docs/nvmr/R1A_PROGRESS.md) và [Git review-only](docs/nvmr/R1A_GIT_DELIVERY.md). Các số liệu M0–M4/S0/S1 bên dưới là lịch sử riêng.

## Video demo

![GSM Map Sandbox demo preview](docs/media/gsm-map-sandbox-demo.gif)

GIF là bản xem trước 10 giây để GitHub hiển thị trực tiếp. [Mở hoặc tải video đầy đủ (MP4)](docs/media/gsm-map-sandbox-demo.mp4).

## S0/S1 — Khởi động và theo dõi hai chặng

Các kết quả và điều kiện delivery trong phần S0/S1–M4 dưới đây là **lịch sử**. Project Owner đã đóng milestone tối ưu FPS M4; R1b không mở lại milestone đó. Hướng dẫn Connected NVMR và quyết định hiện hành nằm ở các báo cáo R1b phía trên.

**Cập nhật performance/memory 18/10/2026:** [báo cáo đầy đủ và PowerShell runbook](docs/nvmr/M4_PERFORMANCE_MEMORY_STABILIZATION.md), [evidence hiện tại](docs/nvmr/m4-performance-evidence/validation-summary.json). Launcher có `-Profile Standard|Meeting|Benchmark`, `-Routers HanoiCar|HanoiBoth|Regional|All|None` và `-StartRouters`. Meeting dùng production preview fresh build, snapshot tối đa 4 Hz, clock hiển thị 10 Hz; paused unchanged không poll snapshot. Ví dụ sau `npm.cmd run build` trong frontend: `./scripts/Start-GsmDev.ps1 -Profile Meeting -Routers HanoiBoth -StartRouters`. Docker Desktop phải chạy để serve OSRM. Với `-Routers None`, vẫn có thể mở completed job khi routers tắt. Nhớ dùng cùng API/store/ports khi mở job đã lưu.

**Policy mới nhất sau follow-up18/10:** startup mọi profile0,5 GiB RAM trống. Light (≤1.000 xe/≤1.000 yêu cầu) dùng0,5 GiB physical/1 GiB commit; routine (tới5.000 xe/≤5.000 yêu cầu) dùng0,75/1,5 GiB. Cả hai giới hạn horizon≤3.600s, schedule≤8, candidates≤128; extended giữ2/2 GiB. API/worker/profiler cùng policy, không giảm ngầm counts/seed/routing. Fresh1.000/5.000 đã completed với250/1.250 requests; xem [FPS/resource follow-up](docs/nvmr/M4_FPS_RESOURCE_FOLLOWUP.md). Lỗi1FPS chưa tái lập/chốt nguyên nhân; Google Meet thật chưa kiểm thử. Commit/push chỉ được phép khi cả FPS/RAM tasks hoàn thành, nên chưa thực hiện.

Checkpoint trước follow-up và raw evidence vẫn giữ trong stabilization report; fresh5.000 NOT RUN ở checkpoint đó đã được thay bằng successful run mới, không sửa historical capture. GitHub Actions workflow có source nhưng chưa push/chạy remote.

Từ project root, PowerShell (Python/Node dependencies và GIS/graphs đã chuẩn bị):

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -StatusOnly
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1
```

Mặc định API **8013**, Vite **5183**, shared absolute store `build/m3/jobs`. Launcher kiểm RAM ≥0,5 GiB khi khởi động service; admission job theo workload riêng, prerequisites, PID đang listen, đúng application/workspace/store/proxy và OS worker lease; reuse dịch vụ đúng, chỉ start phần còn thiếu. Không kill process, start/recreate Docker container hoặc rebuild graph. API cũ chưa có `/api/v3/simulation/jobs/runtime` sẽ bị từ chối reuse trong chế độ start: Ctrl+C tại đúng terminal API của mình để nạp source mới, hoặc chọn cổng còn trống. Dùng `-StatusOnly` để xem lỗi mà không start service. Lease không thay cho heartbeat/progress health.

Trong lượt kiểm chứng S0/S1, Owner giữ 8013/5183, nên bản mới chạy riêng:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -ApiPort 8015 -FrontendPort 5186
```

Mở **<http://127.0.0.1:5186/>** → **Mô phỏng quy mô lớn**. Chọn 10 xe, 5 CAR, 20 requests, online 1, seed `s0-s1-live-10`; chờ COMPLETED rồi seek thời điểm có xe đến đón/chở khách. Dùng filter active + tìm ID hoặc click silhouette ô tô/xe máy. Inspector đọc booking và tối đa hai route từ immutable run, không gọi lại OSRM. Pickup nét đứt, passenger trip nét liền, chặng active đậm hơn; khách chờ chỉ hiện trong ASSIGNED, sau đó pickup là mốc đã đón. Có focus xe/toàn hành trình, thời điểm/deadline/progress/graph identity. IDLE/OFFLINE không có chuyến active. Những run lịch sử thiếu evidence báo unavailable, không dựng lại tuyến.

Fresh run đã kiểm: `d944b4be727e46ae8a6a580ad66430cb`. **Mở run đã có** rồi seek 245/chọn `GSM-00004` (CAR pickup), seek 400 (CAR ON_TRIP); seek 330/chọn `GSM-00008` (MOTORBIKE pickup), seek 500 (MOTORBIKE ON_TRIP). Run chỉ tồn tại trên máy đã tạo nó; clone Git không mang theo `build/`.

**Fixture đồ họa — không phải hành trình OSRM** nằm trong Developer Tools. Synthetic positions/motion chỉ kiểm render, không có booking/passenger/route nghiệp vụ. 5.000 xe (2.000 CAR/3.000 MOTORBIKE) ở đây là **Hanoi Core capacity/render stress case**, chưa phải fleet phân bổ toàn NVMR. Regional Expansion là R1 tiếp theo; S0/S1 không thêm tỉnh/graph.

Backend mất kết nối: UI ghi **Backend FastAPI chưa kết nối**; nút kiểm tra chỉ GET, không gửi lại POST. Kiểm `/api/health`, proxy và runtime store trước khi tạo job mới (POST mất kết nối có thể đã được server nhận). QUEUED + worker lease offline khác router/graph MODE_NOT_READY; NoRoute/NoSegment là OD/snap không khả thi. Bản đồ đã tải không bị xóa vì worker/API mất kết nối; lần mở mới vẫn cần API để tải GIS. Launcher logs/PID receipts ở ignored `build/s0-runtime/`. Chế độ terminal thủ công, Docker và Ctrl+C ở các phần bên dưới; chỉ dừng service mình sở hữu.

Audit tái lập, đọc-only trên completed job; không tải toàn bộ route xuống UI:

```powershell
.\.venv\Scripts\python.exe scripts/audit_route_fidelity.py --job-dir build/m3/jobs/d944b4be727e46ae8a6a580ad66430cb --limit 40 --output build/s0-s1/audit-rerun.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_s0_s1_live.py
```

Lệnh thứ hai là diagnostic riêng với bridge/one-way trong routing buffer, ngoài M3 operating box; không phải accepted simulation job và không nới coverage. Chi tiết RCA, contracts, evidence, regression, performance, GO/NO-GO và Git allowlists: [S0_S1_IMPLEMENTATION.md](docs/nvmr/S0_S1_IMPLEMENTATION.md). Kết quả lịch sử M2–M4 được giữ nguyên.

## Chạy ứng dụng Live trên Windows (terminal thủ công legacy)

Cần Python 3.11+, Node.js 20.19+ hoặc 22.12+, và Docker Desktop với Linux Engine. PBF, GeoJSON và graph OSRM không được lưu trong Git; cần có dữ liệu và artifact đã chuẩn bị theo [báo cáo A1](docs/A1-report.md). Không chạy lại pipeline dữ liệu nếu artifact hiện có đã dùng được.

Tại PowerShell, từ project root:

```powershell
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Set-Location frontend
npm.cmd ci
Set-Location ..
docker start gsm-map-osrm
```

Mở hai terminal tại project root. Chạy backend trong terminal thứ nhất:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

Chạy frontend trong terminal thứ hai:

```powershell
Set-Location frontend
npm.cmd run dev
```

Mở <http://127.0.0.1:5173>. Chọn một trong bốn chế độ: **Một hành trình**, **Mô phỏng đội xe**, **Đặt xe và điều phối** hoặc **Phòng thí nghiệm voucher**. Tài liệu API ở <http://127.0.0.1:8000/docs>. Nếu OSRM container đang chạy, bỏ qua `docker start`. Nếu graph đã có nhưng container chưa được tạo, chạy `python scripts\pipeline.py serve --detach`. Kiểm tra port 5000, 8000 và 5173 trước nếu ứng dụng đã mở.

Nếu chưa có PBF, bản đồ/render GeoJSON hoặc graph OSRM, xem [hướng dẫn dữ liệu A1](docs/A1-report.md). Không có fallback sang dịch vụ bản đồ hay routing công cộng.

## Hanoi CAR + MOTORBIKE pilot (M2)

MOTORBIKE là mô tô điện hai bánh, giả định thiết kế 70 km/h, 6 kW, **không phải moped**. Tốc độ/penalty chưa hiệu chuẩn. Profile cấm motorway/motorroad, xử lý access/oneway/turn restrictions theo motorcycle và barrier bảo thủ; conditional/via-way restrictions ngoài fixtures, biển báo hiện trường và ETA giao thông chưa được chứng nhận. [Quy tắc/nguồn](profiles/motorbike.json), [profile](profiles/motorbike.lua), [bằng chứng](docs/nvmr/m2-evidence/).

Dùng lại PBF `data/raw/vietnam-latest.osm.pbf` (snapshot 2026-10-09, SHA-256 `2fbd2ee6b4dc151eecf04fa6823cddf584b47423e190118b10fce8b6115e9d8a`). PBF, render và graph là Git-ignored: clone Git không có các dữ liệu này. Các lệnh Hanoi kiểm tra hash và reuse; artifact không khớp sẽ dừng, không ghi đè CAR/HCM.

Từ project root, Docker Linux Engine đang chạy; lần đầu thiếu Hanoi artifacts:

```powershell
.\.venv\Scripts\python.exe scripts/pipeline.py verify --region nvmr-hanoi-core
.\.venv\Scripts\python.exe scripts/pipeline.py extract --region nvmr-hanoi-core
.\.venv\Scripts\python.exe scripts/pipeline.py display --region nvmr-hanoi-core
.\.venv\Scripts\python.exe scripts/pipeline.py routing --region nvmr-hanoi-core --profile car
```

Khởi chạy routers; có thể bỏ lệnh routing nếu artifacts đã được kiểm tra và không đổi:

```powershell
.\.venv\Scripts\python.exe scripts/pipeline.py serve --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/pipeline.py routing --region nvmr-hanoi-core --profile motorbike --dry-run
.\.venv\Scripts\python.exe scripts/pipeline.py routing --region nvmr-hanoi-core --profile motorbike
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
.\.venv\Scripts\python.exe scripts/validate_motorbike.py
.\.venv\Scripts\python.exe scripts/multimodal_pilot.py
```

Validation tạo graph synthetic nhỏ trong `build/m2`, dùng container tạm/cổng tự cấp và chỉ dừng container do nó tạo. Evidence cập nhật trong `docs/nvmr/m2-evidence`; kiểm chứng thất bại giữ marker để MOTORBIKE NOT READY. Không sửa `validation.json` để ép readiness. Lần chạy lại không cần validation/build nếu profile, graph, validator và evidence vẫn khớp.

Ba router: `gsm-map-osrm` :5000, `gsm-map-osrm-hanoi-car` :5001, `gsm-map-osrm-hanoi-motorbike` :5002, chỉ loopback. Hanoi `serve` reuse/start đúng container đã kiểm tra; nếu name/port/mount/image khác, báo lỗi. HCM container đúng nhưng đang dừng: `docker start gsm-map-osrm`, rồi kiểm tra lại pipeline serve.

Backend cần khởi động lại sau cập nhật source/config. Khi 8000/5173 đã có dịch vụ, dùng hai terminal:

```powershell
# Terminal backend, project root
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8002
```

```powershell
# Terminal frontend
Set-Location frontend
$env:GSM_API_PROXY='http://127.0.0.1:8002'
npm.cmd run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Mở <http://127.0.0.1:5175/>. Chọn Hanoi Core rồi **Loại dịch vụ**: CAR, MOTORBIKE, hoặc Hỗn hợp trong Fleet/Booking. Số xe/yêu cầu là tổng, mix xen kẽ theo ID (10 xe = 5+5); booking chỉ nhận xe đúng loại. Chọn MOTORBIKE sẽ kiểm tra metadata riêng; nếu NOT READY, chọn CAR hoặc kiểm tra lại dữ liệu. Single Trip chọn A/B, Fleet **Tạo kịch bản**, Booking **Tạo kịch bản đặt xe**; dùng thanh phát/seek chung. Booking đa phương tiện xuất JSON contract `gsm-multimodal-scenario/v1`, không phải Portable Replay. Voucher vẫn CAR v1, chưa có multimodal price-response. Saved HCM v1 vẫn offline.

API mới: `GET /api/v2/regions/{regionId}/modes`, `POST .../modes/{CAR|MOTORBIKE}/route`, `GET .../modes/{type}/candidates`, `POST .../booking-simulation/prepare` (mảng `vehicleTypes`, `serviceTypes` khớp số xe/yêu cầu). Xem `/docs` backend; v1 không nhận các field mới.

```powershell
Invoke-RestMethod http://127.0.0.1:8002/api/v2/regions/nvmr-hanoi-core/modes | ConvertTo-Json -Depth 8
$env:RUN_REAL_DATA='1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_REAL_DATA
Set-Location frontend
npm.cmd test -- --maxWorkers=2
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run verify:replay
node scripts/verify-multimodal.mjs
```

Ctrl+C dừng backend/frontend. Khi cần dừng router, dùng đúng tên: `docker stop gsm-map-osrm-hanoi-motorbike`; tương tự hai CAR routers sau khi kiểm tra không có phiên khác dùng. Giữ graph để reuse, không xóa volumes/data. Map hiện nhưng không route: kiểm tra mode readiness; `/nearest` chỉ là health sơ bộ. Graph/profile mismatch cần kiểm tra manifests. `NoRoute`/`NoSegment` là OD/snap không khả thi; chọn điểm đường phù hợp trong coverage. Không có public/fake route fallback.

## M3/M4 — Jobs và bản đồ đội xe lớn

Chế độ mới giữ riêng contracts/limits M2 và Saved v1. Một API + **một worker process** dùng chung local store; job hoàn tất mới có result/snapshot playback. CAR/MOTORBIKE dùng hai graph Hà Nội đã xác minh. Không có streaming simulation đang chạy, multimodal Voucher hoặc GPS thực. Quy mô/workload đã đo và giới hạn nằm trong [M3](docs/nvmr/M3_IMPLEMENTATION.md), [M4](docs/nvmr/M4_IMPLEMENTATION.md), [integration review](docs/nvmr/M3_M4_INTEGRATION_REVIEW.md).

Kiểm tra môi trường và artifacts trước, không rebuild khi graph còn hợp lệ:

```powershell
Set-Location D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox
.\.venv\Scripts\python.exe --version
node --version
npm.cmd --version
docker version
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
Get-Item data/raw/vietnam-latest.osm.pbf
Get-Item data/routing/manifest.json
Get-Item data/regions/nvmr-hanoi-core/routing/car/manifest.json
Get-Item data/regions/nvmr-hanoi-core/routing/motorbike/manifest.json
Get-Item data/regions/nvmr-hanoi-core/render/manifest.json
# Chỉ khi router chưa chạy; serve kiểm tra và reuse graph/container đúng identity:
.\.venv\Scripts\python.exe scripts/pipeline.py serve --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
```

Mở ba terminal **tại project root**. Dùng ports riêng dưới đây khi các phiên cũ còn chạy; không dừng chúng để chiếm port.

```powershell
# Terminal 1: API. Store mặc định build/m3/jobs; nếu đổi env phải đổi ở cả API/worker.
$env:GSM_SIMULATION_STORE=Join-Path (Get-Location) 'build/m3/jobs'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8013
```

```powershell
# Terminal 2: đúng một worker. Không dùng --reload hoặc mở thêm worker cùng store.
.\.venv\Scripts\python.exe -m backend.app.simulation_worker --store build/m3/jobs
```

```powershell
# Terminal 3: frontend
Set-Location frontend
$env:GSM_API_PROXY='http://127.0.0.1:8013'
npm.cmd run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

Mở **<http://127.0.0.1:5183/>**, chọn **Mô phỏng quy mô lớn** trong menu chính (mobile: nút mở menu ở góc trái). Bản đồ **Hanoi Core** dùng năm lớp GeoJSON OSM cục bộ xuất hiện trước khi tạo job; không dùng public tiles. Khi map đã tải, worker/OSRM không quyết định khả năng zoom/pan. Assets hiện do API phục vụ nên lần mở mới cần API/proxy truy cập được. Thông báo tải bản đồ, lỗi GeoJSON và lỗi job là ba trạng thái riêng. **Tải lại bản đồ** thử lại assets mà không tạo job.

Smoke nhỏ: đặt **Tổng đội xe 10**, **Số xe CAR 5** (còn lại 5 MOTORBIKE), **20 yêu cầu**, **online 1**, seed `m4-ux-pilot`, rồi **Tạo mô phỏng**. Có thể mở **Tham số nhu cầu** để chọn horizon, pickup wait và low/typical/burst. Mặc định live form là 100 xe, 40 CAR, 20 yêu cầu, online 0,8. Simulation chỉ hỗ trợ Hà Nội; region legacy được giữ lại khi quay về. Menu năm chức năng dùng cùng shell, đổi mode không reload trang. Back/Forward và deep link `?runtime=simulation` vẫn hỗ trợ.

Chờ `COMPLETED`, dùng Phát/seek/tốc độ, nhấp cụm để zoom, nhấp xe hoặc nhập ID để xem inspector. Đây là **phát lại kịch bản đã tính xong**, không phải GPS/worker streaming. Đội xe Online/Offline/Rảnh/Đến đón/Chở khách/Moving lấy từ snapshot tại thời điểm playback; **kết quả cuối toàn run** là phần riêng. Geometry chỉ đọc từ immutable route store đúng run/profile. Lưu mã run và dùng **Mở run đã có** để mở lại sau reload/đổi chức năng; selection/clock được dọn khi rời chế độ. **Hủy job** không xuất partial result; **Xóa phiên hiển thị** chỉ clear UI, không xóa/cancel job. Job ở QUEUED lâu có thể chờ worker hoặc worker chưa chạy; UI không có heartbeat xác nhận worker.

**Benchmark / Developer Tools** mặc định thu gọn. Fixture 100–5.000 chỉ đo render; không có outcome điều phối. Nền trống là checkbox opt-in trong mục này. Bản đồ Hà Nội mặc định bật cả khi đo; chọn 5/30/60 giây mỗi zoom, kiểm RAM trước tăng tải, tải JSON để lưu điều kiện ON/OFF. Báo cáo sửa UX và phép đo basemap mới: [M4 UX remediation](docs/nvmr/M4_UX_REMEDIATION.md).

Ví dụ API nhỏ (cũng chạy được khi không mở browser):

```powershell
$api='http://127.0.0.1:8013'
Invoke-RestMethod "$api/api/v2/regions/nvmr-hanoi-core/modes" | ConvertTo-Json -Depth 8
$body=@{regionId='nvmr-hanoi-core';seed='m3-small';fleetSize=10;carCount=5;bookingCount=20;horizonSeconds=900;maxWaitSeconds=300;onlineFraction=1} | ConvertTo-Json
$job=Invoke-RestMethod "$api/api/v3/simulation/jobs" -Method Post -ContentType 'application/json' -Body $body
$job.id
Invoke-RestMethod "$api/api/v3/simulation/jobs/$($job.id)" | ConvertTo-Json -Depth 6
# Khi COMPLETED:
Invoke-RestMethod "$api/api/v3/simulation/jobs/$($job.id)/result?summary=true" | ConvertTo-Json -Depth 8
$snapshot=Invoke-RestMethod "$api/api/v3/simulation/jobs/$($job.id)/snapshot?timeSeconds=100"
$snapshot.counts
# Hủy một job còn QUEUED/RUNNING: POST .../$($job.id)/cancel.
# Explicit schedules optional: onlineSchedule=[{timeSeconds:300,onlineFraction:0.4},...].
```

Kiểm tra end-to-end thật và TypeScript contract (API/worker đang chạy, không chạy benchmark khác):

```powershell
.\.venv\Scripts\python.exe scripts/validate_simulation_api.py --base-url http://127.0.0.1:8013 --check-cancel
$proof=Get-Content -Raw build/m3-m4/api-integration.json | ConvertFrom-Json
Set-Location frontend
node scripts/verify-simulation.mjs http://127.0.0.1:8013 $proof.jobId
Set-Location ..
```

Đo lần lượt, giữ ít nhất 2 GiB available RAM. Domain benchmark có 5 seeds × 3 workloads mỗi scale và guard trước mỗi run; live script đo một config độc lập (không phải browser FPS). Không mở stress browser cùng lúc:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize
docker stats --no-stream
Get-Process python,node -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,WorkingSet64
.\.venv\Scripts\python.exe scripts/benchmark_simulation.py --scales 100 500 1000 3000 5000 --seeds 5 --output build/m3/domain-rerun.json
foreach($n in 100,500,1000,3000,5000) {
  .\.venv\Scripts\python.exe scripts/benchmark_simulation_live.py --fleet-size $n --booking-count 20 --output "build/m3/live-rerun-$n.json"
  if($LASTEXITCODE -ne 0) { break }
}
```

Browser độc lập: từ URL gốc mở menu **Mô phỏng quy mô lớn**, mở **Benchmark / Developer Tools**, chọn fixture100 và **Tải fixture render 100 xe**, chọn thời lượng30giây rồi **Đo 3 zoom cho quy mô hiện tại** (11/13/16, tổng khoảng90s). Deep link fixture vẫn có: `?runtime=simulation&fixture=1&fleet=100&zoom=11`. Tăng lên 500→1000→3000→5000, bấm **Tải fixture render…** trước đo; kiểm tra RAM giữa mỗi mức. Fixture ghi rõ SYNTHETIC, không tạo dispatch outcomes/route. Kết quả gồm FPS/frame times/long tasks/heap nếu có, source update lag/DOM/cluster oracle; tải JSON bằng nút UI. Để đo production build, chạy `npm.cmd run build` rồi `npm.cmd run preview -- --host 127.0.0.1 --port 5184 --strictPort` với `GSM_API_PROXY` cùng giá trị.

Regression, chạy tuần tự:

```powershell
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

Ctrl+C trong đúng terminal của task để dừng worker/API/frontend, rồi chạy lại cùng lệnh. Worker restart đánh RUNNING cũ thành INTERRUPTED; tạo job mới, không sửa status/result bằng tay. `RESULT_NOT_FINAL` trước COMPLETED là đúng; FAILED có error.code/message. Worker không nhận job: kiểm tra cùng store/env, `.worker.lock` chỉ một process và worker console; không xóa lock file để vượt khóa OS. Port conflict: xem `Get-NetTCPConnection -State Listen`, đổi port và frontend proxy, không kill process khác. RAM <2 GiB: ngừng tăng tải, đóng tab/terminal của chính lượt đo khi xong; không stop router của người khác. Stale UI: **Xóa phiên hiển thị**, tạo run mới; seek chủ động reset snapshot gate, không đổi outcome. Đổi graph/profile phải xác minh lại readiness, không đổi graph để mở route cũ. Saved v1 vẫn độc lập jobs/OSRM.

## Phát lại đã lưu (Saved Replay) và phân tích nhiều lượt chạy

Saved Replay chạy riêng, không cần FastAPI hoặc OSRM. Sau khi có render assets và sample A4 trên máy, trong PowerShell:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run package:replay
npm.cmd run verify:replay
npm.cmd run build
Set-Location ..
py -3 scripts\serve_replay.py
```

Mở <http://127.0.0.1:4173/?runtime=saved>, mở **Chi tiết**, rồi chọn **Tải kịch bản mẫu** hoặc **Nhập thí nghiệm đã lưu** với file được tạo bằng **Xuất thí nghiệm Portable v1**. Server chỉ phục vụ tài nguyên cục bộ và chặn `/api/*`. Khi chia sẻ demo, gửi thư mục `frontend/dist` đã build; không cần gửi PBF hay graph OSRM.

Phân tích nhiều lượt cần backend Live và OSRM: trong **Phòng thí nghiệm voucher**, chọn **Thí nghiệm trực tiếp (Live)**, bấm **Chuẩn bị thí nghiệm**, rồi mở **Phân tích kinh doanh nâng cao → Phân tích nhiều lượt chạy**. Chọn Seed gốc, số Seed và yếu tố phân tích độ nhạy; bấm **Chạy nhiều lượt**. **Hủy các lượt chạy** giữ kết quả đã có. Kiểm tra số lượt thành công/thất bại trước khi xuất JSON hoặc CSV. Định nghĩa thống kê và giới hạn được ghi trong [báo cáo A5](docs/A5-report.md). Legacy A4 JSON cần đóng gói trước khi nhập vào Saved Replay; xem README A5 trong báo cáo để biết lệnh.

Thanh phát lại dùng **Phát**, **Tạm dừng**, **Về đầu**, **Đến thời điểm** và **Tốc độ tùy chỉnh** (1x–64x). **Tại thời điểm hiện tại** phản ánh tiến độ mô phỏng; **Kết quả cuối kịch bản** hiển thị kết quả toàn bộ kế hoạch. Baseline là kịch bản không voucher; Treatment là kịch bản áp dụng voucher. Xem [bảng thuật ngữ](docs/localization/terminology-vi.md) và [báo cáo Việt hóa](docs/localization/localization-report.md).

## Tài liệu theo giai đoạn

- [A1 — bản đồ và routing local](docs/A1-report.md)
- [A2 — mô phỏng đội xe](docs/A2-report.md)
- [A3 — booking và điều phối](docs/A3-report.md)
- [A4 — voucher experiment](docs/A4-report.md)
- [A4.1 — workspace và responsive UI](docs/A4.1-report.md)
- [A5 — Saved Replay, batch analysis và handoff WP3](docs/A5-report.md)
- [A5 — hướng dẫn tích hợp WP3](docs/A5-integration-handoff.md)
- [M2 — CAR/MOTORBIKE và mixed pilot](docs/nvmr/M2_IMPLEMENTATION.md)
- [M3 — scalable simulation, jobs và benchmark](docs/nvmr/M3_IMPLEMENTATION.md)
- [M4 — native MapLibre và browser benchmark](docs/nvmr/M4_IMPLEMENTATION.md)
- [M3/M4 — integration, regression và GO/NO-GO](docs/nvmr/M3_M4_INTEGRATION_REVIEW.md)

Trạng thái kiểm tra sau khi tiếp tục phiên 17/10/2026: API/worker/Vite đã khởi động lại ở 8015/5186; Docker Engine/OSRM đang offline, cần bật Docker Desktop rồi dùng các lệnh `serve` trước tạo run mới. Replay completed jobs vẫn đọc dữ liệu đã lưu. Performance capture sau resume không ổn định, kể cả fixture100; chưa nghiệm thu cam kết ≥30FPS ổn định/5.000. Chi tiết và raw evidence trong phần G/J của báo cáo S0/S1; không dùng kết quả FPS trước interruption thay cho trạng thái hiện tại.
