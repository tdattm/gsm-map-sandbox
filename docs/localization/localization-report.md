# Báo cáo Việt hóa GSM Map Sandbox

Ngày nghiệm thu: 13/10/2026. **CONDITIONAL PASS**: lớp hiển thị tiếng Việt và regression A1–A5 đạt các kiểm tra thực thi; điều kiện local `main` chứa A5 chưa đạt ngay từ preflight. Các lượt Batch bị OSRM từ chối vẫn tồn tại và phải được giữ trong diễn giải kết quả. Không kết luận tất cả lượt chạy thành công hoặc ứng dụng sẵn sàng production.

## 1. Git và phạm vi

Root duy nhất: `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`. Nhánh đã checkout `feature/i18n-vietnamese-ui`, HEAD bàn giao/không đổi `03ae48cfc1a87a740aa65c355fae8bdedfa62f78`. A5 có trên nhánh này. Local `main` ở `71dd995adb1947028cd32df38626dd6feceda175` (A4.1), chưa có A5. Bốn file evidence A4.1 untracked có sẵn được bảo toàn.

Không đổi nhánh/index hoặc tạo commit; không reset, stash, clean, fetch, cherry-pick, pull, push hay merge. Sau preflight, dừng thao tác Git theo yêu cầu; danh sách bên dưới là allowlist các nội dung đã chỉnh/tạo, không phải Git status lần cuối. Không đọc/chỉnh sửa/copy implementation từ `gms-voucher-research-demo`, fork `SIReal3103/gsm-map-sandbox` hay repository WP3/team khác. Chỉ code/tài liệu của checkout này được dùng để xác định chức năng và thuật ngữ.

## 2. Baseline và kết quả cuối

| Kiểm tra | Baseline thực thi | Final thực thi |
|---|---|---|
| Backend mặc định | 122 PASS, 5 SKIP | Chạy final với dữ liệu thật bên dưới |
| Backend, `RUN_REAL_DATA=1` | Chưa bật tại baseline | **127 PASS**, 0 SKIP, 1 cảnh báo deprecation FastAPI/httpx |
| Frontend | 125 PASS / 9 files | **140 PASS / 10 files** |
| Typecheck | PASS | PASS |
| Build | PASS | PASS; còn cảnh báo bundle >500 kB |
| Lint | Không chạy baseline | Exit 0; có cảnh báo hooks/fast refresh trong cấu trúc hiện tại |
| Replay package/schema/SHA | Gói hiện có được giữ | PASS: artifact và 9 tài nguyên |
| Protected file hashes | Ghi nhận trước QA | **2.844 file, 0 thay đổi** |

Nguồn: [frontend tests](frontend-tests.json), [backend final](backend-final.txt), [integrity](integrity-report.json), [browser QA](qa/browser-report.json), [Saved QA bổ sung](qa/saved-browser-report.json), [Batch exports](qa/batch-export-verification.json). Không xóa hoặc vô hiệu hóa tests để đạt PASS. 15 tests mới kiểm tra vi-VN/null, ngày giờ, trạng thái, lỗi, batch labels/guard, input timeline và file picker; tests cũ cập nhật accessible names và định dạng số tiếng Việt.

## 3. File có nội dung thay đổi hoặc được tạo

| Nhóm | Files |
|---|---|
| Hướng dẫn | `README.md`, `frontend/README.md` |
| App shell / formatting | `frontend/src/App.tsx`, `frontend/src/App.css`, **mới** `frontend/src/lib/vi.ts` |
| Navigation / playback | `frontend/src/components/primary-navigation.tsx`, `playback-dock.tsx` |
| A1/A2/A3 / map | `frontend/src/components/sandbox-map.tsx`, `fleet-panel.tsx`, `fleet-map.tsx`, `booking-panel.tsx`, `booking-map.tsx` |
| A4 | `frontend/src/components/voucher-panel.tsx`, `voucher-dashboard.tsx`, `financial-comparison.tsx`, `voucher-charts.tsx`, `voucher-analytics.tsx` |
| A5 | `frontend/src/components/batch-analysis.tsx`, các phần Saved/Live của voucher panel/dashboard |
| Shared UI | `frontend/src/components/ui/map.tsx`, `chart.tsx`, `slider.tsx` |
| Tests | `frontend/tests/booking.test.tsx`, `dashboard.test.tsx`, `voucher.test.tsx`, `workspace.test.tsx`, **mới** `localization.test.tsx` |
| QA tools mới | `frontend/scripts/audit-localization.mjs`, `frontend/scripts/qa-localization.mjs`, `frontend/scripts/verify-localization-exports.mjs` |
| Documentation/evidence mới | `docs/localization/terminology-vi.md`, `localization-audit.md`, báo cáo này, inventories/hashes/test results và thư mục `qa/` |

Các thao tác ghi UTF-8/LF trong components cũng có thể chỉ chuẩn hóa newline ở file không đổi nội dung. Không có thay đổi nội dung model/backend/API/schema/GIS. Build cập nhật `frontend/dist` và `.replay-tools` là output dẫn xuất được ignore; không đóng gói lại thí nghiệm nguồn.

## 4. Các khu vực đã Việt hóa

- Menu chính desktop/mobile, header, inspector, thao tác mở/ẩn/thu gọn và footer cục bộ.
- Một hành trình: điểm xuất phát/đích, quãng đường/thời gian dự kiến, trạng thái tính tuyến, lỗi và thông tin điểm trên đường.
- Đội xe/đặt xe: Seed, cấu hình nhu cầu, chuẩn bị kịch bản, trạng thái xe/yêu cầu, bộ lọc, KPI, ETA, sự kiện, chọn xe và xem vùng tuyến.
- Thí nghiệm voucher: cấu hình giá/hành vi/ngân sách, giải thích mô hình và mẫu ngẫu nhiên chung, Baseline/Treatment, ledger, tài chính, chart mặc định/nâng cao, tooltip và nút xuất.
- Saved Replay: Live/Saved, tải mẫu, chọn/nhập JSON, trạng thái kiểm chứng, lỗi định dạng/schema/hash, metadata bao quanh và xuất Portable/legacy/CSV.
- Batch: nhiều Seed, OFAT, yếu tố độ nhạy, tiến độ/hủy/thành công/thất bại, thống kê mẫu hợp lệ, chart và export controls.

Xem [glossary](terminology-vi.md) và [string audit](localization-audit.md) để biết preferred labels, thuật ngữ giữ English, ngoại lệ và những cách dịch cần tránh.

## 5. Ngôn ngữ, accessibility và định dạng

Nhãn tiếng Việt giữ đúng phân biệt giữa **Ngân sách đang giữ trước**, **Chi phí voucher đã sử dụng** và **Ngân sách còn khả dụng**. GFV, tiền hành khách, số chuyến hoàn tất và CPIC không bị đổi ý nghĩa. Không áp dụng/— giữ nguyên null; không biến null thành 0. Status, statistical definitions và JSON/CSV fields của export giữ nguyên giá trị kỹ thuật.

Các accessible names được dịch: bốn chế độ/menu mobile; mở/đóng inspector; thu gọn/mở rộng/ẩn menu; trường Seed/cấu hình; Phát/Tạm dừng/Tiếp tục/Về đầu/Đến thời điểm/Tốc độ tùy chỉnh; nhập file/batch; zoom/la bàn/popup; marker xe, điểm đón/trả. Locale của MapLibre cũng được đặt tiếng Việt. Slider chuyển tên tới input thật để screen reader và bàn phím nhận đúng. Native file input dùng nút **Chọn file JSON**, trạng thái **Chưa chọn file**; tên file gốc giữ nguyên. Dialog chọn file của hệ điều hành theo ngôn ngữ hệ điều hành/trình duyệt, ngoài phần text của ứng dụng.

Tiền và số dùng `vi-VN` (200.000 ₫, 1.234, 12,5%, 3,14 km, 179,5 giây). Precision hiển thị theo từng chỉ số được giữ; không làm tròn lại dữ liệu nội bộ. Simulation time dùng giây/phút; timestamp chuẩn bị hiển thị giờ Việt Nam, không sửa ISO timestamp. Tọa độ WGS84 và fingerprint giữ dạng kỹ thuật để đối chiếu. Tooltip và trục số được rà soát; `k` trên trục tiền nghĩa là nghìn VND.

English còn lại có chủ đích: tên riêng/công nghệ, Voucher, Baseline/Treatment, Seed, Sigmoid, Alpha/Beta/log-odds, Live/Saved Replay/Portable v1, KPI/ETA/GFV/CPIC/OFAT/FIFO/RAF/FPS/MLD/ODbL, copyright OSM, schema/versions/IDs/paths/keys và diagnostics chưa biết. Không có heading/nút/hướng dẫn English thông thường chưa xử lý được xác định trong các luồng hiện tại. Metadata hoặc lỗi mới chưa có mapping sẽ giữ nguyên để tránh diễn giải sai.

## 6. Functional regression A1–A5

| Luồng | Bằng chứng |
|---|---|
| A1 | Chọn A/B trên bản đồ và tính tuyến với OSRM thật; unit tests kiểm tra loading/error/stale response/clear |
| A2 | Chuẩn bị 5 xe có tuyến thật; chọn xe; phát/tạm dừng/về đầu; kiểm tra màn hình ở cả ba kích thước |
| A3 | Tạo nhu cầu/kế hoạch điều phối thật; metrics/event/seek/selection/bộ lọc có unit coverage; ba kích thước |
| A4 | Chuẩn bị hai kịch bản thật; 1x/2x/4x/8x/16x/32x/64x; phát/tạm dừng/seek/reset; đổi Baseline/Treatment giữ nguyên thời điểm |
| Accounting | Unit tests ledger/KPI/null/final/time series PASS; KPI Saved cuối khớp actual artifact; các cặp Batch khớp A5 gốc |
| A5 Saved | Actual Portable artifact, nhập lại/xuất, sai JSON/schema/hash không thay session đã kiểm chứng |
| A5 Batch | 10 lượt thường và Beta OFAT 30 lượt; hủy; xuất JSON/CSV; kết quả thống kê/numerical fields khớp A5 gốc |

## 7. Saved Replay, import/export và tính toàn vẹn

Actual artifact: `frontend/public/replay/demo-experiment.json`, nguồn A4 local-OSRM đã có trong checkout. Digest trước/sau và sau browser roundtrip:

`b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`

- Browser export Portable v1 qua validator rồi đối chiếu canonical JSON với artifact gốc: PASS.
- Nhập lại file vừa xuất trong browser: PASS.
- Legacy JSON bằng canonical payload gốc: PASS.
- 5 CSV `summary`, `decisions`, `bookings`, `ledger`, `series` bằng từng byte output của exporter gốc: PASS. Không dịch headers hoặc enum values.
- JSON sai, schema không hỗ trợ và checksum sai: thông điệp Việt hóa, giữ session/ID thí nghiệm cũ; PASS.
- Static host QA tại 4183 chỉ phục vụ dist và từ chối `/api/*`/POST. Saved không gửi API, OSRM hoặc external requests. FastAPI/OSRM đang chạy ở các port khác nhưng không được viewer dùng; không tắt các dịch vụ của người dùng.
- Không chạy lại OSM preprocessing, không tạo tuyến fallback, không sửa original JSON/CSV, GeoJSON/PBF/graph, contracts, canonicalization/hash hoặc provenance.
- Hash report đối chiếu bytes 2.844 file ở backend/core/contracts/evidence/data/static replay; cả bốn evidence untracked có sẵn cũng nằm trong kiểm tra.

Các bản xuất browser mới nằm riêng trong `docs/localization/qa/`, không ghi đè `docs/evidence/`.

## 8. Batch và độ nhạy

Base Seed `a5-real-2026`, cấu hình A4 mặc định, OSRM cục bộ thật:

| Nhóm | Thành công / yêu cầu | Thất bại | Mean Δ | Median | Sample SD |
|---|---:|---:|---:|---:|---:|
| Thường | 7/10 | 3 | 3,142857 | 3 | 1,069045 |
| Beta = 1 | 7/10 | 3 | 0,142857 | 0 | 0,899735 |
| Beta = 2 | 7/10 | 3 | 3,142857 | 3 | 1,069045 |
| Beta = 3 | 7/10 | 3 | 4 | 4 | Xem JSON |

Tổng Beta OFAT: 21/30 thành công, 9 thất bại. Các lỗi đều `ROUTER_BAD_RESPONSE: Table ETA/snaps không hợp lệ.`; browser ghi nhận HTTP 502 tương ứng. Đây là những lượt bị bộ kiểm tra định tuyến từ chối, không phải exception JavaScript. Không sửa validator hay giả số liệu để có 100% thành công. So sánh per-run `baseline`, `treatment`, `increment`, `cpic`, `status` và toàn bộ summary với `docs/evidence/a5/real-batch-none.json`/`real-batch-beta.json`: PASS về ngữ nghĩa số học. CSV từng lượt được đối chiếu byte-exact với exporter; CSV tổng hợp giữ status/definitions/field semantics. Hủy chạy giữ kết quả một phần và không gửi tiếp toàn bộ hàng đợi.

Thống kê dùng cặp thành công, số mẫu hợp lệ riêng và CPIC gộp theo định nghĩa gốc. Không suy ra hiệu quả thương mại, nhân quả thực địa hoặc ROI từ các số này.

## 9. Browser, layout, keyboard, console và network

Chromium thật, production dist, Live preview 4174 và static Saved 4183. A1–A4 kiểm tra desktop 1440×900, laptop 1366×768, mobile 390×844. Saved kiểm tra cả ba, với Map/Analytics riêng trên mobile. Desktop giữ Map/Analytics/Playback đồng thời; chỉ một map canvas. Navigation/inspector thu gọn/ẩn/mở không tạo lại phiên dữ liệu. Menu mobile mở/Escape, input timeline ArrowRight và focus kiểm tra thực tế; unit tests kiểm tra giữ input khi đóng section.

Hai lỗi layout phát hiện và sửa: hàng playback mobile dài sau dịch; input file ẩn bị CSS cũ width 100% ghi đè làm tràn ngang. Sau sửa: document scrollWidth không vượt viewport; không button bị cắt theo phép đo scrollWidth/clientWidth ở các ảnh final. Legends/tooltip funnel và budget có nhãn đúng, tooltip nằm trong chart viewport. Các panel nội bộ vẫn cuộn độc lập, bảng tài chính có vùng cuộn riêng khi cần.

Không có uncaught JavaScript exception ở lượt QA thành công. Saved không có API/external failures. Live có HTTP 502 cho các lượt Batch bị từ chối như trên; có cảnh báo GPU ReadPixels của Chromium khi chụp ảnh. Lint có cảnh báo hooks/fast refresh, build có cảnh báo kích thước bundle; chưa thay kiến trúc để xử lý vì ngoài phạm vi localization.

Ảnh final tiêu biểu (toàn bộ danh sách trong `qa/` và browser report):

- [A4 desktop 1440×900](qa/live-a4-desktop.png), [A4 laptop 1366×768](qa/live-a4-1366.png).
- [A4 mobile analytics 390×844](qa/live-a4-390.png), [A4 mobile map](qa/live-a4-mobile-map.png).
- [A1 desktop](qa/live-a1-desktop.png), [A1 laptop](qa/live-a1-1366-inspector.png), [A1 mobile](qa/live-a1-390-map.png).
- [A2 desktop](qa/live-a2-desktop.png), [A2 laptop](qa/live-a2-1366-inspector.png), [A2 mobile](qa/live-a2-390-map.png).
- [A3 desktop](qa/live-a3-desktop.png), [A3 laptop](qa/live-a3-1366-inspector.png), [A3 mobile inspector](qa/live-a3-390-inspector.png).
- [Saved desktop](qa/saved-1440-analytics.png), [Saved laptop](qa/saved-1366-analytics.png), [Saved mobile](qa/saved-390-analytics.png).
- [Tooltip funnel](qa/chart-funnel.png), [Tooltip ngân sách](qa/chart-budget.png), [Batch](qa/live-batch-desktop.png).

## 10. Hạn chế và hướng dẫn trải nghiệm

- Chưa đáp ứng điều kiện A5 có trong local main; người dùng cần xử lý Git theo quy trình riêng. Nhánh localization hiện có A5 và không bị đổi HEAD.
- Ba Seed trong mỗi nhóm Batch vẫn bị ETA/snap guard từ chối giống A5. Không phải báo cáo 10/10 hoặc 30/30 PASS cho mọi lượt mô phỏng.
- Chromium QA và unit tests không thay thế kiểm thử screen reader chuyên biệt trên mọi tổ hợp thiết bị. Cửa sổ chọn file, thông báo validation gốc của trình duyệt/hệ điều hành có ngôn ngữ phụ thuộc môi trường; text do ứng dụng sở hữu đã Việt hóa.
- SHA-256 kiểm tra tính toàn vẹn, không phải chữ ký/xác thực nguồn. Giới hạn và bất biến import gốc vẫn giữ.

Mở ứng dụng theo [README](../../README.md). Với Live, chọn bốn chế độ bằng menu chính; **Chi tiết** mở cấu hình. Với Saved, mở `?runtime=saved`, chọn **Tải kịch bản mẫu** hoặc **Chọn file JSON** để nhập Portable v1. Dùng **Phát**, **Tạm dừng**, **Về đầu**, **Đến thời điểm**, **Tốc độ tùy chỉnh**. Để chạy Batch, chuyển Live, chuẩn bị thí nghiệm, mở phân tích nâng cao rồi chọn phân tích nhiều lượt; xuất kết quả trước khi đóng.

Lệnh QA chạy từ frontend (Playwright cần được cài/cung cấp ở môi trường QA; có thể đặt `PLAYWRIGHT_MODULE` trỏ module đã có):

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run verify:replay
node scripts/audit-localization.mjs
# Chạy preview trong terminal riêng; backend/OSRM Live đã sẵn sàng.
npm.cmd run preview -- --host 127.0.0.1 --port 4174 --strictPort
# Terminal frontend khác:
node scripts/qa-localization.mjs
node scripts/verify-localization-exports.mjs
```

Backend final từ project root:

```powershell
$env:RUN_REAL_DATA = '1'
.\.venv\Scripts\python.exe -m pytest -q
```

Kết thúc ở trạng thái reviewable, không commit, push hoặc merge.
