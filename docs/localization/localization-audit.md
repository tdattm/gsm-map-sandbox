# L10N-P0–P5: phạm vi và kiểm kê chuỗi

Ngày kiểm tra: 13/10/2026. Một agent, làm tuần tự trong `gsm-map-sandbox`; không đọc implementation hay tài liệu từ repository khác.

## Preflight

- Root thực tế: `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`.
- Nhánh đã tồn tại và đang checkout: `feature/i18n-vietnamese-ui`.
- HEAD bàn giao: `03ae48cfc1a87a740aa65c355fae8bdedfa62f78` (`feat(a5): add portable replay and batch analysis`). Có contracts và báo cáo A5 tại HEAD này.
- Local `main`: `71dd995adb1947028cd32df38626dd6feceda175`, A4.1, chưa có A5. Không tự cập nhật main, merge, fetch hoặc đổi nhánh.
- Tracked worktree ban đầu sạch; bốn file untracked có sẵn: `docs/evidence/a4.1/dataset-status.json`, `desktop-1440-overview.png`, `desktop-advanced-playing.png`, `desktop-advanced-windowed.png`. Giữ nguyên cả bốn file. Dừng các thao tác Git sau preflight; tiếp tục code trên nhánh mục tiêu đã có A5, không reset/stash/clean/stage/commit/push/merge.
- Không có AGENTS.md được tìm thấy trong repository bằng `rg --files -g AGENTS.md`.

## Baseline thực thi

| Lệnh | Kết quả trước thay đổi |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 122 PASS, 5 SKIP; các kiểm tra dữ liệu thật cần `RUN_REAL_DATA=1` |
| `npm.cmd test` trong frontend | 125 PASS / 9 files |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run build` | PASS; cảnh báo bundle >500 kB |

Không dùng con số nghiệm thu A5 cũ thay cho việc chạy lại. Không sửa backend hoặc thư viện tính toán để xử lý tiếng Việt.

## Kiểm kê và phân loại

`string-inventory.json` ghi các JSX text và thuộc tính hiển thị trước khi dịch, gồm cả accessible names trong component tests. `final-string-inventory.json` ghi các candidate literals từ toàn bộ TSX và helper tiếng Việt, gồm các literal kỹ thuật cần xét ngữ cảnh; số lượng cuối nằm trong `integrity-report.json`. Hai danh mục là dữ liệu audit; không phải dictionary runtime hoặc bằng chứng rằng mọi literal đều là UI. Đã đọc components, hooks, validators và exporters để phân biệt giá trị contract với nhãn hiển thị.

| Nhóm | Vị trí | Xử lý |
|---|---|---|
| 1. Nội dung cần Việt hóa | App, navigation, panel A1–A4, playback, chart, batch, file input, status/alert, MapLibre controls | Dịch câu/nút/heading/accessible names theo ngữ cảnh; tooltip và lỗi qua helpers |
| 2. Thuật ngữ giữ English | Voucher, Baseline/Treatment, Seed, Sigmoid, Alpha/Beta, ETA/KPI/GFV/CPIC và tên công nghệ | Giải thích tiếng Việt ở khu vực đầu; nhãn ngắn trong chart và nút |
| 3. Nội dung kỹ thuật không dịch | CSS selectors, data-* telemetry, enums, IDs, paths, MIME, JSON keys, schema/version, CSV headers, error codes, [lon,lat] | Giữ nguyên; ánh xạ riêng cho nội dung nhìn thấy |
| 4. Lịch sử/provenance bất biến | docs/evidence, contracts, GeoJSON/PBF/OSRM, payload/manifest/hash, metadata mô hình, OSM attribution | Không sửa; chỉ dịch nhãn bao quanh; kiểm tra bytes bằng SHA-256 |

## Checkpoints

| Checkpoint | Phạm vi đã rà soát và thực hiện |
|---|---|
| P0 | Git, A5 hiện tại, baseline, inventory, thuật ngữ, file allowlist và nội dung bất biến |
| P1 | Header, menu desktop/mobile, inspector, thu gọn/ẩn/đóng, controls và timeline playback, map controls/locale |
| P2 | Điểm A/B, route loading/error, thời gian/quãng đường, đội xe, Seed, điều phối, bộ lọc/trạng thái, sự kiện và KPI vận hành |
| P3 | Cấu hình giá/hành vi/voucher, giải thích Sigmoid và mẫu ngẫu nhiên chung, Baseline/Treatment, ledger, KPI tài chính, chart/legend/tooltip và export labels |
| P4 | Live/Saved, nhập mẫu/file, validation và lỗi schema/hash, thống kê nhiều Seed, OFAT, tiến độ/hủy/lỗi, JSON/CSV labels |
| P5 | vi-VN, glossary, README, component tests, Chromium desktop/laptop/mobile, roundtrip/exports, byte-level preservation và báo cáo |

## Chiến lược

Không thêm thư viện i18n hay language toggle. `frontend/src/lib/vi.ts` chứa trạng thái, mode labels, preset/factor/CSV labels, lỗi đã biết, thống kê hiển thị, MapLibre locale và định dạng số/tiền/ngày. Dịch literal chỉ trong presentation components khi đã xác định ngữ cảnh; không replace toàn cục một từ trong repository. Các giá trị Low/Medium/High, baseline/treatment, success/error/cancelled, OFFERED/RESERVED/SETTLED/RELEASED vẫn giữ nguyên trong dữ liệu. `status` và statistical definitions trong batch export giữ nguyên; UI dùng bản dịch riêng.

Chart giữ nguyên dataKey, series, stacking, proportion domain, nulls và cách lấy mẫu. CSV giữ nguyên keys, headers và nội dung; chỉ tên nút xuất được Việt hóa. Validators vẫn trả mã lỗi gốc; UI ánh xạ thông điệp đã biết và giữ mã để tra cứu.

Accessible names thay đổi cho menu, inspector, zoom/la bàn/popup, các trường Seed/cấu hình, nút phát/reset/seek, nhập file, batch controls và marker đón/trả/điều phối. Đồng thời chuyển aria-label/aria-labelledby của Slider xuống input focusable của Base UI; Chromium xác nhận điều khiển bằng phím. Không thay phím tắt.

## English còn lại có chủ đích

- GSM Map Sandbox, Geofabrik Vietnam, OpenStreetMap, OSRM, MapLibre, Docker và các tên thư viện là tên riêng.
- Voucher, Baseline, Treatment, Seed, Sigmoid, Alpha/Beta/log-odds, Live, Saved Replay, Portable v1 và các viết tắt trong glossary giữ thuật ngữ nghiên cứu/định dạng.
- `© OpenStreetMap contributors`, ODbL 1.0 giữ nguyên attribution/giấy phép; không chỉnh GIS để dịch tên đường.
- Raw IDs, model versions, fingerprint, WGS84 coordinates, paths, schemas và export fields giữ nguyên để bảo toàn khả năng đối chiếu.
- Diagnostics chưa biết được giữ nguyên thay vì đoán bản dịch; các mã lỗi đang biết có giải thích tiếng Việt. Trường hợp metadata hoặc thông điệp mới từ dịch vụ chưa nằm trong mapping vẫn có thể chứa tiếng Anh. Đây là ngoại lệ kỹ thuật có chủ đích, không phải lỗi được che bằng chuỗi thành công.
- `k` trên trục tiền = nghìn VND; RAF/FPS/Hz/ms là đơn vị/chỉ số kỹ thuật. Công thức thống kê original trong export không dịch; phần hiển thị có bản Việt riêng.

Không còn heading, nút hay hướng dẫn English thông thường được xác định trong các luồng hiện tại. Search đối chiếu các nhãn cũ (Generate/Prepare/Import/Export/Observed/Planned/Focus/Pickup/Dropoff/Timeline…) và kiểm tra literals ASCII còn lại bằng inventory; identifiers không được tính là UI chưa dịch. Kiểm tra cuối và hạn chế được ghi trong [báo cáo](localization-report.md).
