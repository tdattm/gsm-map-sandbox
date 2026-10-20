# D1.5 — Unified application & Connected presentation

Ngày: 20/10/2026 · Branch: `feature/nvmr-m0-architecture`. Git đầu phiên sạch. Thực hiện bởi một agent trên checkout hiện tại; không worktree, stage, commit, push hoặc đổi branch.

## 1. Tích hợp ứng dụng

`ApplicationShell` là shell nhẹ chung cho mọi module, chứa navigation popup dùng chính `PrimaryNavigation` và mode registry hiện có. `ApplicationBrand` thống nhất branding. Connected có nút menu nhỏ trong header; không có sidebar navigation cố định hoặc header thứ hai. Các hook HCM vẫn nằm trong `OperationalWorkspace`, không chạy khi root đang mở Connected.

Mục **Mô phỏng quy mô lớn** sinh `?runtime=simulation&scenario=connected`. Root `/` vẫn là Connected. Historical `?runtime=simulation` vẫn mở Hanoi v3; `scenario=regional` giữ v4; các URL `mode=single/fleet/booking/voucher`, `runtime=saved` và `scenario=connected&dev=1` được giữ. Back/Forward đã kiểm tra bằng component test và browser giữa HCM Single Trip và Connected.

A vẫn có một KPI strip và map toàn chiều rộng. B bỏ strip khỏi DOM, mở Analytics bên trái 40%, map phải 60%. Mobile dùng drawer B, không thêm layout mode. Menu và mở run là popup tạm thời; popup menu không phủ lên playback. Các thao tác A/B/menu không thay session hoặc remount map; đổi engine/reload là hành trình mới như trước.

## 2. Area Chart và độ đúng dữ liệu

Tham khảo [Area Charts chính thức](https://ui.shadcn.com/charts/area), đặc biệt [stacked](https://ui.shadcn.com/view/new-york-v4/chart-area-stacked), [interactive](https://ui.shadcn.com/view/new-york-v4/chart-area-interactive), [gradient](https://ui.shadcn.com/view/new-york-v4/chart-area-gradient), [legend](https://ui.shadcn.com/view/new-york-v4/chart-area-legend). Tái sử dụng `ui/chart.tsx`, Recharts v3, ChartContainer, tooltip và legend hiện có; không cài thư viện hoặc tạo chart infrastructure mới.

Biểu đồ chính stack bốn state OFFLINE, IDLE, ASSIGNED, ON_TRIP, với màu và nhãn tiếng Việt. X là simulation timestamp, Y là số xe. Gradient nhẹ; đường bậc `stepAfter`, không animation. Tooltip hiển thị timestamp và số giây đến ba chữ số thập phân, kèm đúng counts ở mốc được chọn. Không dùng đường smooth để suy ra trạng thái phân số. Chart chỉ mount khi B mở, có chiều cao hữu hạn 230px desktop/210px mobile và không nhận clock/snapshot tick làm props.

API summary không có timelines; full result chứa toàn bộ route geometry. Vì vậy thêm đúng một endpoint chỉ đọc trong FastAPI hiện có:

`GET /api/v5/simulation/jobs/{id}/analytics/fleet-states`

Endpoint đọc timelines bất biến từ result cache hiện có, gom các chuyển trạng thái cùng timestamp theo thứ tự persisted (phù hợp `bisect_right` của snapshot). Mỗi hàng kiểm tra tổng bốn state bằng fleetSize, không âm. Có checkpoint đầu/cuối; nếu hơn 120 điểm thì chọn tối đa 120 checkpoint thực, giữ hai đầu, không nội suy counts. Cờ `sampled` và tổng số checkpoint giữ thông tin về việc rút gọn; UI ghi `mốc chọn lọc`, tooltip giải thích các chuyển trạng thái ở giữa không được biểu diễn. Không thay dữ liệu gốc, job/result contract hoặc engine. `moving` không thuộc bốn series và không được gán bằng ASSIGNED + ON_TRIP.

Aggregate cache backend giữ một run, idle timeout 300s; frontend giữ tối đa bốn aggregate theo run ID. Không tải mọi route sang browser, không gọi OSRM, không gọi hàng loạt snapshot để dựng chart và không tính timeline theo playback frame. Thiếu/sai timeline trả lỗi unavailable; frontend không vẽ chart giả. Không thêm click-to-seek vào chart; seek vẫn qua timeline playback để tránh hành vi khó đoán.

Run QA có sẵn `271d116d28f64d75a7a49b3f300d7b24`: **100 xe / 40 CAR / 60 MOTORBIKE / 25 requests**, 28 checkpoint, không downsample. Đối chiếu cả 28 điểm với `connected_snapshot` từ persisted result: PASS; tổng state luôn 100. Đây là run nghiên cứu tổng hợp đã lưu, không phải GPS/vận hành thực tế hoặc run mới. Xem `d15-evidence/persisted-series.json` và `persisted-oracle.json`.

## 3. Mở run, Analytics và playback

**Mở run → chọn một completed run** từ danh sách API v5 hiện có. Mỗi hàng có số xe, số yêu cầu, trạng thái hoàn tất, seed và ID ngắn; vẫn nhập ID thủ công được. Có loading, empty, API unavailable, error và retry riêng. Không hard-code ID/default run hoặc tự enqueue. Đã sửa lifecycle popup để backdrop được dọn sau khi chọn run; có regression test và browser xác nhận.

Analytics tổ chức: KPI cuối run → fleet-state chart → bảng vùng/loại xe → đội xe hiện tại dạng details → inspector. Bảng giữ dữ liệu tĩnh đúng ý nghĩa, không ép vào area chart. Các state counters và vùng chi tiết vẫn truy cập được.

Playback Connected dùng biến thể compact của dock hiện có: một nút Play/Pause, reset, timestamp, slider và tốc độ 0.25×–16× (giữ được giá trị tùy chỉnh hiện hành nếu có). Desktop cao khoảng 52px, mobile khoảng 53px trong các phép đo. Timestamp `hh:mm:ss` dễ đọc, số giây chính xác hơn có trong tooltip. Dock legacy giữ cách hoạt động cũ. Không sửa FleetClock hoặc hook session.

Camera Hà Nội, native clustering, selected-route-on-demand và attribution của D1 được giữ. Drawer chừa vùng dưới cho legend/attribution; sidebar cuộn riêng, chart resize theo vùng chứa. Không thay source map bằng ảnh hoặc public service.

## 4. File đã sửa/thêm

| Nhóm | File |
| --- | --- |
| Shell và URL | `frontend/src/App.tsx`, `components/application-shell.tsx` (mới), `components/primary-navigation.tsx`, `lib/navigation.ts` |
| Connected UI | `components/connected-workspace.tsx`, `components/connected-run-dialog.tsx` (mới), `components/connected-fleet-chart.tsx` (mới), `components/playback-dock.tsx`, `App.css` |
| Adapter/validation | `frontend/src/lib/connected-analytics.ts` (mới) |
| API đọc dữ liệu | `backend/app/connected_analytics.py` (mới), `backend/app/connected_jobs.py` |
| Frontend tests | `frontend/tests/navigation.test.ts`, `connected-workspace.test.tsx`, `connected-analytics.test.ts` (mới), `connected-presentation.test.tsx` (mới) |
| Backend tests | `tests/test_connected_analytics.py` (mới) |
| Báo cáo/evidence | Báo cáo này và `docs/nvmr/d15-evidence/` |

Các path `components/`, `lib/`, `App.css` trong bảng thuộc `frontend/src/`. Không thay package manifests, `ui/chart.tsx`, simulation dispatch logic, contracts, persisted artifacts, MapLibre renderer hoặc session hooks.

## 5. Kiểm thử thực thi

| Kiểm tra | Kết quả cuối |
| --- | --- |
| `npm.cmd test -- --maxWorkers=1` | **227 PASS**, 28 files |
| `npm.cmd run typecheck` | PASS, exit 0 |
| `npm.cmd run lint` | PASS, exit 0; còn warning hiện hữu và một warning Fast Refresh do module shell export hook chung |
| `npm.cmd run build` | PASS, exit 0; còn warning chunk lớn |
| `npm.cmd run verify:replay` | Package PASS, 9 assets; browserExports NOT_RUN |
| `pytest -q tests/test_connected_analytics.py tests/test_connected_api.py tests/test_connected_domain.py` | **20 PASS**; một warning Starlette/httpx deprecation |
| Persisted 100-vehicle series vs snapshot projector | **28/28 PASS** |
| `git diff --check` | PASS |

Test bao gồm cùng-timestamp transitions, conservation, rút gọn checkpoint thực, unavailable/409/404/422, cache, frontend validation, chart không giả dữ liệu, abort khi đóng B, danh sách run chỉ GET, đóng backdrop, menu target và Back/Forward. Toàn frontend regression giữ các kiểm tra HCM, Saved Replay, v3/v4 và Connected có sẵn. Đây không phải kiểm tra live routing mới.

## 6. Browser evidence

QA bằng in-app browser/WebGL với Vite 5173 và API 8000, store `build/r1b/jobs`. Không khởi động OSRM/worker hoặc tạo live job.

Đã kiểm tra A/B ở **1920×1080, 1366×768, 1024×768, 390×844**. Cả tám phép đo cuối: một header, một canvas; KPI chỉ ở A; chart chỉ ở B; không overflow tài liệu; legend/attribution/zoom/compass nằm trong map và không đè playback. Sidebar desktop đạt 40/60. Chart SVG khớp vùng chứa trong sai số dưới 1px, chiều rộng B lần lượt khoảng 720/498.55/361.6/296.35px. Tooltip desktop/mobile nằm trong sidebar và không che dock. Console warnings/errors của lượt cuối là mảng rỗng.

Đã seek qua slider đến 461s, chọn `NVMR-CAR-hanoi-00027`, mở booking `NVMR-BK-hanoi-000002` và route inspector. Đã focus xe, pan thủ công, chuyển B→A→B: vẫn 461s, filter CAR, speed 4× và đúng xe/booking. Tiếp tục phát 4× qua A/B: đồng hồ tăng từ khoảng 465s lên 468s rồi pause khoảng 473s; không quay về 0. Cặp ảnh camera trước/sau giữ địa vật tương ứng. Component test kiểm tra map DOM identity; browser kiểm tra một canvas và source constructor lifecycle ổn định, không gắn bộ đếm nội bộ vào UI.

Evidence chính:

- `browser-final-bounds.json`, `browser-summary.json`: đủ tám trường hợp, kiểm tra bounds đều PASS.
- `1920-a/b.jpg`, `1366-a/b.jpg`, `1024-a/b.jpg`, `390-a/b.jpg`: ảnh cuối từng trạng thái/kích thước.
- `saved-runs.jpg`, `mobile-menu.jpg`, `chart-tooltip.jpg`, `mobile-tooltip.jpg` và `mobile-tooltip.json`.
- `camera-before-toggle.jpg`, `camera-after-toggle.jpg`, `route-inspector.jpg`, `interaction-bounds.json`.
- `check-exit-codes.json`, các log tests/typecheck/lint/build/replay và `console.json`.

## 7. Chạy local và phần còn lại

Frontend: `cd frontend; npm.cmd run dev`, mở `http://127.0.0.1:5173/`. API phải chạy source mới để có endpoint chart. Với store QA hiện có, từ project root:

```powershell
$env:GSM_SIMULATION_STORE = (Resolve-Path build/r1b/jobs).Path
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Hiện Vite/API đã được để chạy cho owner review; không khởi động trùng cổng. Không cần router hoặc worker để mở completed run. Live configuration vẫn ở `?runtime=simulation&scenario=connected&dev=1`; chuẩn bị worker/router cho live là công việc riêng.

Chưa tạo/đánh giá artifact 5.000 xe/1.750 requests, chưa đo playback 5.000 lâu hoặc trên browser khác/mobile thật, chưa test browser export/download, chưa làm production deployment. Với hơn 120 checkpoint, chart là bản xem chọn lọc; các chuyển trạng thái bị lược không hiển thị, dữ liệu gốc vẫn nguyên. Không tự chọn default run. Cần chọn artifact chính thức, xác minh tải replay/hiệu năng ở quy mô đó và chuẩn bị deployment trong các bước sau; M5–M7 vẫn hoãn.
