# GSM Map Sandbox

PoC mô phỏng hành trình, đội xe và voucher trên bản đồ OSM thật tại TP.HCM và Hanoi Core, dùng OSRM local. Hanoi hỗ trợ pilot CAR/MOTORBIKE với graph riêng; booking, giá cước, ETA và voucher là giả định nghiên cứu, không phải dữ liệu vận hành hay GPS thực tế của GSM.

## Video demo

![GSM Map Sandbox demo preview](docs/media/gsm-map-sandbox-demo.gif)

GIF là bản xem trước 10 giây để GitHub hiển thị trực tiếp. [Mở hoặc tải video đầy đủ (MP4)](docs/media/gsm-map-sandbox-demo.mp4).

## Chạy ứng dụng Live trên Windows

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
