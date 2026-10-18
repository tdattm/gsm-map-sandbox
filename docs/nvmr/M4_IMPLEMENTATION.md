# M4 — Multi-scale Map Visualization

> **Follow-up18/10:** [FPS profiler + resource policy](M4_FPS_RESOURCE_FOLLOWUP.md): own-page JS sampling profiler và application timeline, source-of-truth admission diagnostics; fresh1.000/5.000 completed với floor0,5/0,75 GiB. Không kết luận đã xử lý root cause1FPS khi lỗi không tái lập.

> **Performance/memory 18/10/2026:** [báo cáo stabilization](M4_PERFORMANCE_MEMORY_STABILIZATION.md) ghi Current Verified State, measured process/commit memory, Meeting preview, paused event-driven snapshots, idle result cache và CI. Controlled Live100 giảm source updates 48→20/5 s; lỗi lịch sử ~1 Hz chưa tái lập, chưa kết luận nguyên nhân. Real Meet/Chrome độc lập và fresh 1.000/5.000 chưa nghiệm thu. Các policy 100 ms polling bên dưới là lịch sử; hiện Standard tối đa 10 Hz, Meeting 4 Hz và paused unchanged không poll.

> **Cập nhật product integration 17/10/2026:** truy cập từ URL gốc → menu **Mô phỏng quy mô lớn**. Hanoi basemap mặc định bật, cùng shell GSM, mix/demand controls và run opener. Báo cáo chi tiết root cause, acceptance, phép đo mới basemap ON và giới hạn: [M4_UX_REMEDIATION.md](M4_UX_REMEDIATION.md). Các sections bàn giao ban đầu bên dưới ghi lại kiến trúc/measurements trước lượt remediation; link riêng, mix cố định và blank default đã được thay thế trong lượt mới. Số liệu lịch sử vẫn giữ nguyên.


Ngày thực hiện: 17/10/2026. Phạm vi: frontend NVMR M3/M4 trong `gsm-map-sandbox`; không thay model Voucher, Saved Replay v1 hoặc bộ tạo kịch bản M2. Đây là bản bàn giao triển khai; số đo browser chưa chạy không được suy ra từ unit tests.

## Kiến trúc và luồng sử dụng

Mở `http://127.0.0.1:5173/?runtime=simulation`, hoặc liên kết **M3/M4 · quy mô lớn** trên header workspace cũ. Workspace mới dùng cùng `Map`/`useMap`/`MapControls` trong `components/ui/map.tsx`, font Geist và MapLibre worker cục bộ. Nó có một map instance trong suốt vòng đời xem job/fixture/seek/selection; không tạo map mới mỗi snapshot. Chuyển bằng liên kết về workspace cũ là điều hướng trang, có tạo map mới có chủ đích.

UI có tạo job CAR/MOTORBIKE 40%/60%, số yêu cầu, online fraction, seed, trạng thái/progress, hủy job và xem kết quả cuối cùng. Job đang chạy chỉ được poll trạng thái; playback bắt đầu khi job `COMPLETED`. Đây **không phải streaming worker**. Region trong MVP này cố định `nvmr-hanoi-core`, tránh biểu diễn kết quả Hà Nội bằng cấu hình HCM đang mở ở workspace cũ.

`GET /api/v3/simulation/jobs/{id}/result?summary=true` chỉ lấy metadata/KPI/duration; không tải route store/timeline/event history vào React. Snapshot được lấy từ server theo thời gian clock; mỗi request hoàn tất rồi mới lập lịch request tiếp theo (100 ms nghỉ), không chồng requests khi router/API chậm. Geometry được tải riêng khi chọn route ref đang hoạt động.

## Native sources/layers

| Source | Nội dung | Cập nhật |
|---|---|---|
| `m4-fleet` | GeoJSON Point, feature ID là vehicle ID ổn định; properties type/state/heading | Full replacement `setData`, tối đa khoảng 10 Hz ở fixture; backend chậm thì tần suất thấp hơn |
| `m4-selection` | Một điểm selection | Nội suy hiển thị 100 ms giữa hai vị trí đã nhận, reset khi seek/run/ID đổi |
| `m4-selected-route` | Một LineString đã kiểm chứng provenance | Chỉ khi selected immutable route ref đổi |

Sáu layers: cluster circle, cluster count, individual vehicle circle, motorbike center mark, selection ring, selected route. `clusterRadius=45`, `clusterMaxZoom=13`; từ zoom 14 hiển thị từng xe. Cluster properties đếm CAR/MOTORBIKE; màu cluster theo loại chiếm đa số và nhãn tổng số. Cluster click dùng `getClusterExpansionZoom`, điểm click mở inspector. Không tạo DOM marker cho xe và không vẽ mọi tuyến cùng lúc.

CAR màu xanh dương, MOTORBIKE màu tím với tâm trắng để khác nhau ngoài màu sắc. Viền vàng ASSIGNED, xanh lá ON_TRIP, trắng IDLE; OFFLINE mờ. Selection vòng cam. Inspector cho biết ID/type/state/heading/WGS84/active booking/ref, distance/duration và graph identity của tuyến đang xem. Có nhập ID chính xác và gợi ý 25 ID đầu (không tạo 5.000 `<option>` mỗi tick). Focus zoom đến xe. Không có route ref thì báo rõ đứng yên hoặc fixture không có tuyến; lỗi route không thay bằng CAR graph/tuyến đường thẳng.

## Hợp đồng snapshot và lifecycle

`gsm-simulation-snapshot/v1`: `runId`, `regionId`, `sequenceNumber`, `simulationTimeSeconds`, `counts`, `vehicles`, `routingIdentities`. Vehicle có ID, CAR/MOTORBIKE, OFFLINE/IDLE/ASSIGNED/ON_TRIP, `[longitude,latitude]`, heading, nullable active booking/ref. `SnapshotGate` kiểm tra tọa độ, ID trùng, assignment membership, identity và số đếm; bỏ sequence bằng/cũ hơn trong cùng epoch. Run/region khác bị từ chối. Seek tạo gate/epoch mới, cho phép quay về snapshot cũ có chủ đích; HTTP response trước seek không được publish vào epoch mới.

Backend là nguồn lifecycle/KPI. UI không tính dispatch outcome và không scan event history mỗi frame. Kiểm tra `TOTAL=OFFLINE+ONLINE`, `ONLINE=IDLE+ASSIGNED+ON_TRIP`; `moving` không được vượt assigned+onTrip. KPI result gồm requested/assigned/completed/unserved riêng, tránh gọi total fleet là xe đang chạy.

Một `FleetClock` có sẵn dùng cho play/pause/reset/seek/speed; fixture chỉ đọc clock mỗi 100 ms. RAF selection chỉ nội suy hai điểm hiển thị, không có simulation clock thứ hai. Reset/change fixture abort requests và tăng epoch; job status cũ không được làm job đã hủy xuất hiện lại. Map listeners, ResizeObserver, animation RAF, timers và sources/layers có cleanup. Không refit camera khi nhận mỗi snapshot. Route envelope `gsm-simulation-route/v1` được kiểm tra run/region/ref và toàn bộ `RoutingIdentity` trước render.

## Fixture và browser harness

URL ví dụ:

```text
http://127.0.0.1:5173/?runtime=simulation&fixture=1&fleet=100&zoom=13
```

Các quy mô: 100/500/1.000/3.000/5.000. Fixture seed cố định `m4-render-fixture/v1`, 40% CAR/60% MOTORBIKE, tỷ lệ trạng thái cố định, một phần điểm dao động theo simulation time. Đây là **synthetic render load**, không phải GPS, OSRM, domain simulation throughput hoặc research outcomes; không có route geometry giả.

Chọn quy mô → **Tải fixture render … xe** → **Đo 3 zoom cho quy mô hiện tại**. Mỗi lần chỉ đo một quy mô, tuần tự zoom 11/13/16, mỗi zoom chờ 700 ms và lấy 5 giây mẫu, tự phát fixture, pan nhẹ liên tục. Sau capture trả clock về paused nếu trước đó paused. Giữ tab foreground. `pre[data-testid="m4-benchmark-result"]` hiển thị JSON; nút tải JSON xuất tất cả mẫu của phiên. Main Orchestrator kiểm tra available RAM trước tăng quy mô; không tự stress toàn matrix một lượt.

Harness ghi user agent, viewport, DPR, WebGL renderer, FPS/RAF-frame p50/p95, longtask count/total nếu browser hỗ trợ, JS heap nếu browser có `performance.memory`, DOM marker count, tổng source/layer count, `setData` submission p50/p95, source-loaded lag p95, số update, snapshot age, selection-to-next-frame, visible cluster/vehicle counts, tổng visible represented vehicles và map lifetime token. Lag là source-loaded cho **submission mới nhất đang chờ**, không phải kết quả render/GPU completion riêng cho từng update. Source/layer count gồm basemap khi bật. Heap không phải process RSS/VRAM.

Đây là mẫu **warm in-page**, không có restart browser/process. `pageAgeMs` và số updates trước capture được lưu. Không gán nhãn cold-start hay suy ra leak-free từ capture 5 giây. FPS là RAF cadence khi pan, không phải số lần GPU hoàn tất khung hình. Selection-to-next-frame là click callback→RAF, chưa thay thế kiểm tra người dùng đọc được inspector và route fetch latency. Sau timed capture, harness tạm dừng clock, đợi 250 ms cho source ổn định rồi gọi getClusterLeaves cho từng visible cluster: kiểm tra leaf count, CAR/MOTORBIKE counts, ID hợp lệ/không trùng giữa cụm và điểm riêng. clusterOracle ghi checked/failures/representedLeafCount/uniqueLeafCount/passed; phạm vi viewport, chỉ ghi full fleet khi visible represented bằng total. Oracle chạy ngoài FPS window.

Mặc định basemap trống/offline để tách render load. Checkbox bật basemap Hà Nội từ API cục bộ; số đo cần ghi rõ trạng thái đó. Không gọi tile/glyph/sprite server công cộng.

## Validation thực thi trong Agent M4

| Kiểm tra | Kết quả tại worktree M4 |
|---|---|
| `npm.cmd run test -- tests/simulation.test.ts tests/use-simulation.test.ts` | PASS — 7 tests, 2 files (agent); main thêm paused-transfer test |
| `npm.cmd run typecheck` | PASS |
| Focused oxlint trên 6 modules/tests mới | Exit 0, warnings hooks/ref/immutability; chưa coi là sạch warning |
| `git diff --check` | PASS |
| Full frontend tests/build/lint | NOT RUN bởi Agent M4; Main chạy tuần tự tại checkout tích hợp |
| Browser/WebGL/final API integration | NOT VERIFIED bởi Agent M4; Main bổ sung evidence thực |

Tests bao phủ toàn bộ 5 fixture sizes, deterministic IDs/coordinates/counts, validation failures, stale/out-of-order/run/region rejection, explicit seek gate, selected route provenance, late-create after fixture/reset, old-completion after cancellation không publish final result; cancel HTTP thất bại khởi động lại status polling và vẫn chặn response cũ. jsdom tests không được tính là browser performance evidence.

## Benchmark browser thực chạy

Production Vite build, preview `127.0.0.1:5184`; Chrome155 IAB, Windows11/i5-11320H/16GB, ANGLE Intel Iris Xe Direct3D11 (không phải NVIDIA). Viewport desktop1280×800, canvas920×658, DPR≈1. Mỗi scale một warm sample5s/zoom11/13/16, pan liên tục, fixture10Hz, ~1833 moving/5000 fleet. API/worker đã dừng khi đo frontend độc lập; ba OSRM routers vẫn idle, không stop dịch vụ người dùng. Không có cold browser/process restart hoặc soak test. [Raw15 rows](m3-m4-evidence/browser-benchmark.json).

| Fleet | FPS zoom11 /13 /16 | Frame p95 max ms | JS heap max MiB | setData submit p95 max ms | Source loaded lag p95 max ms | Correctness |
|---:|---|---:|---:|---:|---:|---|
| 100 | 59.95 / 60.01 / 60.14 | 17.00 | 49.89 | 0.20 | 5.20 | PASS |
| 500 | 60.04 / 59.99 / 60.04 | 17.00 | 45.10 | 0.20 | 12.90 | PASS |
| 1000 | 59.93 / 60.16 / 60.01 | 17.00 | 51.16 | 0.40 | 29.50 | PASS |
| 3000 | 59.95 / 60.42 / 60.05 | 17.00 | 55.90 | 0.70 | 36.60 | PASS |
| 5000 | 59.90 / 60.02 / 59.91 | 16.90 | 69.96 | 0.90 | 51.40 | PASS |

Tất cả15 samples: DOM markers0, sources3, layers7 (6 M4 + background), long tasks0 trong cửa sổ5s. Low zoom đại diện đúng toàn fleet mỗi scale và cluster leaves/type/unique identity oracle PASS; mid/high chỉ vùng nhìn, không đếm số xe nhìn thấy như toàn fleet. High zoom focus một xe hoạt động trước warmup, vì viewport tùy ý không có xe không đủ làm benchmark hợp lệ. Native click thực trên fixture5000 chọn fixture-00003 CAR/ON_TRIP và đúng booking, không fake route. Frame cadence ≈60Hz, vượt mục tiêu30FPS/p9533,4ms trong phạm vi đã đo; RAF không chứng minh GPU hoàn tất từng frame.

Đã phát hiện/sửa trong browser: string feature IDs cần `promoteId:id` và fallback properties.id khi query, tránh collapse individual counts thành một undefined ID; nhãn numeric point_count cần to-string để hiển thị. Harness thêm viewport/source diagnostics, từ chối capture không có xe nhìn thấy; camera high zoom focus active vehicle. Lượt đầu viewport trống đã giữ [evidence không được chấp nhận](m3-m4-evidence/browser-initial-invalid.json); không dùng FPS của lượt đó làm PASS. Sau sửa chạy lại toàn15-row matrix trên final build.

Source-loaded lag là acknowledgement mới nhất đang chờ từ worker source, không GPU completion. setData submission không bao gồm toàn bộ thời gian worker clustering; hai số được tách. Selection callback→next RAF và snapshot age giữ raw; chưa phải full inspector/route-network latency SLO. JS heap đo tại end sample, không phải process RSS/VRAM hoặc peak transient. Camera pan là jumpTo nhỏ liên tục, không thay kiểm thử mọi gesture/input device. Không có memory-leak soak certification.

Ảnh: [5000 clusters có nhãn](m3-m4-evidence/clusters-5000.jpg), [native inspector](m3-m4-evidence/native-inspector-5000.jpg). Map lifetime token không đổi suốt15 samples/scale swaps/seek; sources/layers không nhân lên. Final actual source3/layer7 được browser xác nhận; mọi source vẫn full replacement, chưa có delta protocol.

## Compatibility, limitations và bước tiếp theo

Các legacy `fleet-map.tsx`, `booking-map.tsx`, `sandbox-map.tsx`, Saved readers/checksums, HCM v1 limits, Voucher CAR Baseline/Treatment và routing pipelines không bị sửa. Workspace cũ tiếp tục dùng rendering legacy cho kịch bản nhỏ; native M4 path dành riêng M3 contract. Chưa tuyên bố đã browser regression HCM/Hanoi/Saved chỉ dựa trên không sửa file.

MVP không stream worker, không delta snapshots, không predictive positions, không chuyển Saved v1 thành artifact quy mô lớn. Selected ring nội suy 100 ms, toàn đội xe update theo snapshot; không extrapolate future domain state. API polling/projecting 5.000 xe và browser stress có thể bị RAM/router contention; chỉ tăng tải sau đo riêng. Chưa có soak test memory leak; cluster leaves oracle chỉ bao phủ phần viewport đã đo, cần lưu evidence thực trước công bố capability. Browser benchmark route latency/end-to-end cần chọn xe có active route trong run live, khác fixture không có route.

## Files và lệnh thực thi

Modified: `frontend/src/App.tsx`, `frontend/src/App.css`. Added: `frontend/src/lib/simulation.ts`, `frontend/src/lib/use-simulation.ts`, `frontend/src/components/simulation-map.tsx`, `frontend/src/components/simulation-workspace.tsx`, `frontend/tests/simulation.test.ts`, `frontend/tests/use-simulation.test.ts`, báo cáo này. Không thêm dependencies.

```powershell
Set-Location D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox\frontend
npm.cmd run typecheck
npm.cmd run test -- tests/simulation.test.ts tests/use-simulation.test.ts
# Main điều phối full tests/build tuần tự khi đủ RAM:
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run verify:replay
# Vite proxy mặc định 127.0.0.1:8000; port frontend 5173, strictPort.
npm.cmd run dev
# Mở URL runtime=simulation nêu trên bằng browser thật có WebGL.
```

Hướng dẫn worker/routers thực tế và quyết định GO/CONDITIONAL GO/NO-GO cuối cùng nằm trong README/M3/integration review. Đã có browser evidence cho phạm vi trong bảng; chưa coi đó là nghiệm thu soak/operational capacity mọi workload.

## Kiểm chứng cuối tại checkout tích hợp

Full frontend:167 PASS/17 files; lint/typecheck/build/replay/mixed-export exit0, lint29 warnings và chunk>500kB. Main sửa polling để không reproject/chuyển lại cùng immutable snapshot khi pause; seek epoch mới vẫn fetch và network failure retry. Một test fake-clock kiểm số request khi pause/seek đã PASS trong full suite. Backend189 PASS gồm live HCM/M2/Voucher; Saved HCM sample seek/play khi API tắt được browser xác nhận. [Integration review](M3_M4_INTEGRATION_REVIEW.md) ghi API/live browser và quyết định readiness cuối.

Live UI đã tạo100 fleet/20 requests và5000 fleet/1250 requests, đều COMPLETED toàn demand trong hai configs này. Large persisted job10,644 s; snapshot time100 có total5000/offline1000/online4000/idle3882/onTrip118/moving118, khớp API và TS validators. Playback large bằng snapshot HTTP (không fixture) đạt60,05 FPS, p9516,8 ms, source lag p9539,4 ms, ~4,6 updates/s; [raw](m3-m4-evidence/browser-integrated-5000.json). Worker kết thúc trước playback; chưa concurrent worker+map stress/streaming.

Inspector thực: MOTORBIKE GSM-00051/BK-000020 dùng motorbike graph `fb97489d...`, CAR GSM-00001/BK-000804 dùng car graph `a24d4957...`. Bật/tắt Hanoi basemap giữ map instance, selected route và source cleanup; [MOTORBIKE trên basemap](m3-m4-evidence/live-motorbike-inspector.jpg), [CAR5000](m3-m4-evidence/live-car-5000.jpg). Saved HCM production sample đã seek500→play505,2→pause khi API task tắt; [ảnh](m3-m4-evidence/saved-api-off.jpg). Không rerun browser file chooser import/export roundtrip hoặc mobile390.

## Kiểm chứng product integration và Hanoi basemap — lượt remediation 17/10/2026

Luồng hiện tại: URL gốc → menu **Mô phỏng quy mô lớn**, cùng header/navigation GSM; deep link vẫn tương thích, Back/Forward không reload trang. Hanoi basemap local mặc định bật trước job; readiness kiểm năm geographic assets, lỗi assets khác lỗi jobs/OSRM. Form có mix tùy chọn (kể cả10 xe5 CAR/5 MOTORBIKE), demand/seed, run opener và metadata immutable; KPI playback tách khỏi final run. Developer tools thu gọn, blank background opt-in. Clock subscription30Hz chỉ ở dock; map instance được giữ qua run/fixture/seek.

Backend regression mới **189 PASS**, frontend cuối **174 PASS/19 files**, lint33 warnings / 0 errors, typecheck/buildPASS; Saved checksum9 assets và browser sample seek500PASS. LiveM2run(write=False)20/20 PASS, không ghi đèevidenceM2. FreshM3small 10 xe/20 requests20 completed; fresh5.000 xe (2.000 CAR/3.000 MOTORBIKE)/1.250 requests1.250 completed, worker 11,080 s, không có routing request failures. Snapshot tại giây 100: total5000/offline1000/online4000/idle3861/assigned1/onTrip138/moving139. Current/provenance/TSvalidator/cancel409 được kiểm riêng.

**Browser mới có Hanoi basemap ON:**100 fixture59,53–60,00FPS;1.000 fixture57,80–59,29FPS (mỗizoom30s);5.000 fixture sau táchclock48,19–54,91FPS,p95 tới 49,9 ms;API thật5000playbackzoom 11/30s56,97FPS,p95 16,9 ms.8 sources / 15 layers/0 DOM fleet markers; cluster oraclePASS,zoom 11đủ 5.000 xerepresented. Canvas764×543 trên1280×800Chrome155/IrisXeANGLE-D3D11. Không so ngang FPSblank/canvas920×658/5s trước đó. Táchclock chưa chứng minh cải thiện đồng đều; giữ cảraw metrics trước/sau.

Root/navigation/pre-job map/live 10/live 5.000/play-seek-selection-focus/Back-Forward/mobile390 đều cóbrowser evidence. MobilepageWidth390/canvas373×358, mộtcanvas; mở lạirun 5.000 vàfocusMOTORBIKE. Faultproxy riêng kiểm503jobsAPI,404assets+retry,QUEUED12s,FAILEDrouter,INTERRUPTED,CANCELLED; **physical whole API/worker/routershutdown và real hard crash vẫnNOT VERIFIED**, không dừng Owner services để tạo lỗi. RealcancelAPIvàrealCANCELLED/FAILED UI mở từstore đã kiểm riêng. QAports8014/5185 đã dừng; Owner8013/5183/router5000–5002 giữ nguyên.

Quyết định: **GO MVP local cho luồng sản phẩm đã thử**, **CONDITIONAL GO M4 ở quy mô5000 nếu yêu cầu frame/soak ổn định hơn**, **GO bắt đầu M5 pilot nhỏ**, **NO-GO production**. P0blankmap/navigation đã xử lý; cònP1framejank/profiling/soak/worker heartbeat/physicaloutages, P2chunks/lint/co-locatedpicking. Không triển khaiM5model và không thay backendM3/routing/Voucher/Saved.

Chi tiết không rút gọn (RCA,actions,rawmetrics,limits,commands,Gitallowlists): [M4_UX_REMEDIATION.md](M4_UX_REMEDIATION.md). [Manifest evidence mới](m4-ux-evidence/validation-summary.json). Số liệu các sections bàn giao trước được giữ nguyên như lịch sử.

## S0/S1 — cập nhật tiếp theo ngày 17/10/2026

[S0_S1_IMPLEMENTATION.md](S0_S1_IMPLEMENTATION.md) ghi implementation và kiểm chứng mới: launcher/PID/store/worker lease, explicit FastAPI outage UX, native local CAR/MOTORBIKE silhouettes, selected-booking detail API hai chặng, passenger/pickup/dropoff, filter/overlap picking và route progress. Selected ring không còn nội suy chord; vị trí dùng authoritative snapshot. Backend dispatch/projection, graphs, Voucher và Saved contracts không đổi.

Các phần mô tả points/circle hoặc ring interpolation ở trên là lịch sử M4 trước S1. Source hiện tại có thêm selected native symbol và two-leg sources; không dùng source/layer count, FPS blank-map hoặc test totals cũ để nghiệm thu S1. Fixture có nhãn đồ họa và không booking ID giả. 5.000 xe tại Hanoi Core chỉ là capacity/render stress case, chưa phải fleet phân bổ toàn NVMR; R1 mở rộng vùng là task riêng. Báo cáo S0/S1 giữ cả capture oracle lỗi và final rerun, cùng các giới hạn performance/soak.

### Bổ sung bàn giao sau quota interruption — 17/10/2026

S0/S1 source cuối có thêm sửa depot hit numeric ID về business vehicle ID và kiểm thử hồi quy; frontend 181 PASS/21 files, typecheck/lint/build/replay PASS (39 lint warnings, chunk warning còn). Backend 194 PASS và M2 live PASS được thực thi trước gián đoạn; không chạy lại full real-router suite khi Docker hiện offline. Launcher đã dựng lại API8015/worker/Vite5186, health/store/proxy đúng; không dừng process Owner.

Các capture browser sau resume không ổn định: Live5.000 28.90 rồi khoảng1FPS, render-idle timeout; đối chứng fixture100 cũng khoảng1FPS (cluster oracle PASS). Chưa xác định nguyên nhân, không dùng kết quả55FPS trước đó để nghiệm thu môi trường hiện tại. **NO-GO cam kết ≥30FPS ổn định/5.000 và soak**, GO tiếp tục phát triển chức năng đã kiểm. Source counts10/20/0DOM giữ nguyên; toàn bộ raw captures và phân tích ở [S0_S1_IMPLEMENTATION.md](S0_S1_IMPLEMENTATION.md). R1/M5 chỉ GO phát triển phạm vi riêng, không GO nghiệm thu coverage/model/production.
