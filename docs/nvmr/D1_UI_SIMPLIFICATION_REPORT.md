# D1 — Connected NVMR: giao diện tối giản, mặc định Hà Nội

Ngày kiểm tra: 20/10/2026 (Asia/Saigon). Checkout: `feature/nvmr-m0-architecture`.

## Kết quả và phạm vi

Đã triển khai frontend D1 trên checkout hiện tại bằng một agent. Git ban đầu sạch. Không dùng worktree, không stage/commit/push/reset. Không thay đổi backend, thuật toán điều phối, contracts, artifact OSM/OSRM hoặc persisted results; không tạo simulation job mới và không khởi động Docker/worker/router.

Root `/` mở trực tiếp Connected v5 với bản đồ OSM/MBTiles cục bộ, camera Hà Nội, hai trạng thái A/B. Không có scenario selector, menu engine cũ, form cấu hình hoặc JSON nghiên cứu trong giao diện trình bày mặc định. Metadata vẫn được giữ nguyên trong domain/result và dữ liệu đã lưu.

## Các file thay đổi

| File | Mục đích |
| --- | --- |
| `frontend/src/App.tsx` | Router ngoài chọn Connected presentation cho root/deep link v5; giữ shell legacy riêng và đồng bộ `popstate`. Tránh gọi các hook HCM trong presentation mặc định. |
| `frontend/src/lib/navigation.ts` | Root nhận simulation; URL Single Trip sinh rõ `mode=single`; xóa các tham số scenario/dev khi chuyển engine để không rơi về Connected ngoài ý muốn. |
| `frontend/src/components/simulation-workspace.tsx` | Connected trả workspace trực tiếp; đổi scenario phát `popstate` để shell ngoài đồng bộ ngay. Selector cũ còn trong giao diện legacy v3/v4. |
| `frontend/src/components/connected-workspace.tsx` | Header gọn, modal mở run, một KPI strip, Analytics trái, bảng global/zone/mode, cấu hình chỉ tại `dev=1`; giữ playback, filters, selection và route inspector. |
| `frontend/src/components/connected-map.tsx` | Bỏ fit toàn Connected bounds; resize bằng ResizeObserver trên chính instance map; giữ kiểm tra tiles/API và lỗi WebGL. |
| `frontend/src/lib/map-style.ts` | Tâm Hà Nội lấy từ operating-zone bbox trong config hiện có, zoom 11; giữ local MVT/font; attribution có liên kết bản quyền. |
| `frontend/src/App.css` | Grid 40/60, kích thước viewport ổn định, overflow cục bộ, map overlays, drawer mobile và playback responsive. |
| `frontend/tests/navigation.test.ts` | Root mới, Single Trip explicit, roundtrip mode URL và Saved Replay. |
| `frontend/tests/connected-workspace.test.tsx` | A/B, map DOM identity, filters/selection/time, không tự tạo job, empty KPI, loaded-result KPI, root và Back/Forward qua Single Trip/Saved Replay. |
| `frontend/tests/connected-map.test.tsx` | Tâm Hà Nội, không fit lại khi load/rerender, resize existing map và cleanup observer. |
| `frontend/tests/connected-simulation.test.ts` | Giữ kiểm tra mọi resource map/font là local; phân biệt legal attribution hyperlinks với URL tải tài nguyên. |
| `frontend/tests/dashboard.test.tsx`, `multimodal-ui.test.tsx`, `regions.test.tsx` | Các regression hành trình cũ bắt đầu bằng `?mode=single` thay cho root đã đổi mục đích; giữ nguyên các assertion hành vi legacy. |
| `docs/nvmr/d1-evidence/` | Logs kiểm tra, exit codes, screenshots và DOM bounding rectangles. |

`primary-navigation.tsx`, hook simulation/playback, component render MapLibre và backend không cần chỉnh sửa.

## Điều hướng và tương thích

| URL | Giao diện |
| --- | --- |
| `/` | Connected v5 presentation, State A |
| `/?runtime=simulation&scenario=connected` | Connected v5 presentation |
| `/?runtime=simulation&scenario=connected&dev=1` | Cấu hình live Connected ngoài presentation mặc định; chỉ submit khi bấm nút tạo |
| `/?mode=single` | HCM Single Trip trong shell legacy |
| `/?mode=fleet` | HCM Fleet |
| `/?mode=booking` | HCM Booking/Dispatch |
| `/?mode=voucher` | HCM Voucher |
| `/?runtime=saved` | HCM Saved Replay, import/export cũ |
| `/?runtime=simulation` | Hanoi legacy v3, giữ fixture/developer links cũ |
| `/?runtime=simulation&scenario=hanoi` | Hanoi legacy v3 explicit |
| `/?runtime=simulation&scenario=regional` | R1a regional v4 |

Các tham số presentation profile hiện có tiếp tục được hook đọc. Navigation sinh Single Trip explicit để URL không bị hiểu là root Connected. Back/Forward đọc lại URL, bao gồm Saved runtime; component test thực hiện `history.back()`/`forward()` qua root, Single Trip và Saved Replay.

Mở run là dialog phụ, không phải layout mode thứ ba. Đổi sang engine khác có thể tạo session mới như hành vi trước; bảo toàn session được yêu cầu cho thao tác A/B trong cùng workspace, không phải qua reload hoặc đổi engine.

## Hai trạng thái

**State A:** header GSM Mobility Sandbox / NVMR v5 với Mở run và Analytics; đúng một strip gồm tổng xe, CAR, MOTORBIKE và số yêu cầu; map toàn chiều rộng; filters gọn trên map; legend CAR/MOTORBIKE trong map; playback phía dưới.

KPI lấy từ loaded result/config hoặc snapshot đã tải, không lấy từ form allocation đang nhập. Khi chưa có run, cả bốn giá trị là `—` và thông báo ngắn `Chưa mở run v5`. Preset 5.000 chỉ còn trong cấu hình developer, không xuất hiện như kết quả đã chạy.

**State B:** toàn bộ strip A bị bỏ khỏi DOM. Analytics nằm trái, map phải theo grid `minmax(0,2fr) minmax(0,3fr)`. Sidebar có kết quả global (requested/completed/unserved, mean pickup wait, busy/online), bảng vùng, bảng loại xe, trạng thái đội xe hiện tại và inspector xe/hành trình. Không thêm biểu đồ khi bảng đã đủ diễn đạt; không thêm thư viện. Run chưa có KPI dùng counts có thật; dữ liệu chưa có không sinh chart hoặc placeholder số liệu.

Map section luôn ở cùng vị trí cây React, không có key phụ thuộc Analytics. Sidebar chỉ đổi `hidden` và CSS; không tạo lại hook session/clock. Đóng/mở giữ filters, query, selected vehicle, camera và trạng thái playback. Chọn xe từ map mở Analytics để inspector có thể tiếp cận; tìm xe trên toàn vùng vẫn bỏ filter theo hành vi cũ. Focus xe/toàn tuyến vẫn là thao tác camera chủ động.

## Camera và tài nguyên bản đồ

Tâm khởi tạo là trung điểm bbox operating zone Hà Nội `[105.65,20.9,105.95,21.13]`, tương ứng xấp xỉ `[105.8,21.015]`; zoom 11. Giá trị được truyền khi MapLibre constructor tạo map, không chờ snapshot/load rồi fit. Vì vậy không có delayed fit ghi đè thao tác pan/zoom sớm của người dùng.

`ConnectedCamera` chỉ quan sát kích thước container và gọi `map.resize()`. Nó không gọi fit/jump/ease khi sidebar, filter, snapshot hoặc trạng thái style thay đổi. Không giới hạn camera vào Hà Nội; người dùng vẫn zoom/pan ra toàn coverage miền Bắc. MVT URL tiếp tục là `/api/v5/connected/map/tiles/{z}/{x}/{y}.pbf`, font đóng gói cục bộ. Hyperlinks OSM/Geofabrik/ODbL trong attribution chỉ là liên kết bản quyền, không phải nguồn map công cộng.

## Legend, attribution và responsive

Legend nằm trong `.simulation-map`, chỉ gồm hai biểu tượng và nhãn loại xe. Attribution luôn hiện chữ (`compact:false`), có links truy cập bản quyền; nằm trong control viewport góc dưới phải. Legend đặt cao hơn attribution. Zoom/compass nằm bên phải, phía trên attribution; playback là vùng riêng bên dưới map. Lỗi API/tiles/WebGL vẫn hiển thị alert và nút thử lại; success không có đoạn health text dài.

Desktop/tablet rộng hơn 760px dùng 40/60. Màn nhỏ dùng drawer trái có nút đóng sticky; chừa 82px dưới drawer cho legend/attribution vẫn nhìn thấy. Sidebar cuộn độc lập; trang giữ chiều cao viewport. Playback mobile có hàng nút play/pause/reset/speed và hàng timeline riêng. Seek bằng slider vẫn có ở mọi kích thước; nhập thời điểm/tốc độ tùy chỉnh có trên desktop rộng. Không có chart bị co hoặc kéo giãn canvas bằng CSS.

## Kiểm tra đã thực thi

| Lệnh trong `frontend` | Kết quả cuối |
| --- | --- |
| `npm.cmd test -- --maxWorkers=1` | PASS: 26 files, 215 tests |
| `npm.cmd run typecheck` | PASS, exit 0 |
| `npm.cmd run lint` | PASS, exit 0; vẫn có các warning React/hooks ở mã hiện hữu, không phải lint sạch warning |
| `npm.cmd run build` | PASS, exit 0; còn cảnh báo chunk lớn, gồm MapLibre |
| `npm.cmd run verify:replay` | PASS package, 9 assets; `browserExports: NOT_RUN` |
| `git diff --check` | PASS |

Xem `d1-evidence/check-exit-codes.json` và các log cùng thư mục. Chạy đầu tiên phát hiện test legacy còn dùng root cũ; đã chuyển sang URL explicit. Lần tiếp theo phát hiện assertion cấm mọi chuỗi HTTPS cũng bắt cả legal links; đã giữ assertion local resource và kiểm tra attribution riêng. Kết quả cuối ở bảng trên là rerun sau các chỉnh sửa.

Các regression toàn frontend bao gồm HCM, multi-mode, saved assets, Hanoi/regional và Connected concurrency/replay. Chúng sử dụng mocks/fixtures; không chứng nhận live routing mới hoặc backend throughput.

## Browser evidence thực tế

QA dùng in-app browser/WebGL, Vite 127.0.0.1:5173 và API 127.0.0.1:8000. API được khởi động với store `build/r1b/jobs` để đọc lại run có sẵn `271d116d28f64d75a7a49b3f300d7b24`: 100 xe, 40 CAR, 60 MOTORBIKE, 25 yêu cầu. Đây là kết quả nghiên cứu tổng hợp đã tồn tại, không phải simulation mới hay dữ liệu vận hành/GPS thực tế.

Đã đo A và B tại 1920×1080, 1366×768, 1024×768, 390×844. Cả tám phép đo cuối có một canvas; `scrollWidth/scrollHeight` tài liệu bằng viewport; KPI chỉ tồn tại ở A. Sidebar desktop đo lần lượt khoảng 768/1152px, 546.55/819.85px, 409.6/614.4px. Map canvas khớp container trong sai số làm tròn dưới 1 CSS pixel. Bounding rectangles legend, attribution, zoom và compass nằm trong map; playback bên dưới map. Attribution cuối vẫn có đầy đủ chữ ở cả tám trường hợp.

- `browser-final-bounds.json`: số đo cuối trên source có attribution cố định; `browser-summary.json`: kiểm tra containment/không đè playback/không overflow đều PASS ở tám tổ hợp; `console-errors.json`: mảng rỗng trong lượt cuối.
- `desktop-empty.jpg`: root Hà Nội, không có run, bốn KPI rỗng.
- `desktop-a.jpg`, `desktop-b.jpg`: hai layout ở 1366×768 sau mở saved run.
- `mobile-a.jpg`, `mobile-b.jpg`: 390px, controls và attribution nằm trong viewport.
- `camera-before-toggle.jpg`, `camera-after-toggle.jpg`: đã drag map, zoom thủ công rồi B→A→B; các địa vật/xe giữ vị trí tương ứng, không trở về full extent. Cặp ảnh camera được ghi trước bước đổi attribution sang luôn hiện chữ.
- `browser-bounds.json`: ghi nhận thêm mốc seek 400s và playback đang chạy qua A/B (đồng hồ tiếp tục tăng, không về 0); không dùng làm số đo layout cuối.

Đã mở route inspector cho `NVMR-CAR-hanoi-00027` tại 400s, booking `NVMR-BK-hanoi-000002`: pickup 3720.8m/350.5s, trip 55351.7m/3004.5s từ persisted geometry. Đã thử focus vị trí xe và toàn hành trình; bộ lọc CAR giữ nguyên khi chuyển A/B. Đã thử phát, mở/đóng Analytics và tạm dừng: clock tiếp tục tăng qua chuyển layout. Không có console error trong các lượt browser đã đọc.

Một map/canvas được kiểm tra bằng số lượng canvas trong browser, DOM identity trong component test và source lifecycle constructor với dependency rỗng. Không gắn bộ đếm constructor nội bộ vào production UI; không đo FPS hoặc chứng nhận tải 5.000 xe.

## Cách chạy và review local

Tại project root, terminal API (chỉ cần cho map/replay; không cần worker/OSRM để đọc completed run):

```powershell
cd D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox
$env:GSM_SIMULATION_STORE = (Resolve-Path build/r1b/jobs).Path
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal frontend:

```powershell
cd D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox\frontend
npm.cmd run dev
```

Mở `http://127.0.0.1:5173/`. Bấm Mở run, nhập ID ở trên, sau đó thử Analytics, filters và playback. Root không tự khôi phục hoặc tự tạo run. Để cấu hình live, dùng `/?runtime=simulation&scenario=connected&dev=1`; submit live cần worker/router tương ứng được chủ repository chuẩn bị riêng theo runbook, ngoài kiểm thử D1.

API/Vite được để chạy phục vụ owner review; không có worker/router mới. Nếu đã có service dùng cổng đó, dùng service đang chạy hoặc dừng đúng terminal của phiên trước, không khởi động trùng cổng. `Ctrl+C` tại terminal tương ứng để dừng.

## Giới hạn và phần để lần UX/UI sau

Không còn defect chức năng D1 đã biết trong phạm vi kiểm tra trên. Chưa kiểm tra trình duyệt khác/thiết bị mobile thật, touch gesture, screenshot automation trên Safari/Firefox, exports qua browser hoặc full HCM live journeys sau thay đổi; các flow legacy được kiểm tra ở regression stage. Browser camera đối chiếu bằng ảnh, không xuất số tọa độ camera nội bộ. Không benchmark lâu hoặc chạy 5.000 xe.

Lượt UX/UI tiếp theo có thể tiếp tục typography, mật độ bảng/inspector, khả năng tìm run thuận tiện hơn và custom playback controls trên màn nhỏ; D1 giữ các thành phần sẵn có. Chunk splitting/cảnh báo lint hiện hữu chưa xử lý trong phạm vi này. M5–M7, Voucher M5, dịch vụ analytics mới và production deployment vẫn hoãn.
