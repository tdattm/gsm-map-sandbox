# GSM M4 — Performance, memory efficiency và Lightweight Development Mode

> **Current update sau yêu cầu tiếp theo ngày18/10:** [M4_FPS_RESOURCE_FOLLOWUP.md](M4_FPS_RESOURCE_FOLLOWUP.md) thay thế policy small-only bên dưới bằng light0,5/routine0,75 GiB và ghi fresh5.000 completed. Các bảng trong bản này là checkpoint trước follow-up, giữ nguyên số đo lịch sử. Lỗi1FPS vẫn chưa tái lập/chốt root cause; commit/push có điều kiện chưa được thực hiện.

## A. Current Verified State — 18/10/2026

| Hạng mục | Trạng thái đã xác minh, phạm vi và giới hạn |
|---|---|
| Checkout | `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`; branch `feature/nvmr-m0-architecture`; baseline sạch khi bắt đầu: `3ef9160940e6129c911889add7d8aed0d6022bd1`. HEAD vẫn ở baseline; thay đổi nhiệm vụ chưa stage/commit/push. Source hashes nằm trong `m4-performance-evidence/validation-summary.json`. |
| Thời gian | Phép đo chính: tối **17/10/2026**, khoảng 22:50–23:28 giờ Việt Nam; xác minh tiếp sau quota: sáng **18/10/2026**. Raw JSON giữ nguyên UTC/timestamps của từng capture. Không coi số đo tối hôm trước là ảnh chụp hệ thống hiện tại. |
| Môi trường | Windows build 26300, i5-11320H 4 cores/8 threads, physical usable **15,78 GiB**, Python 3.11.9, Node 24.18.0/npm 11.16.0. CI khai báo Python 3.11/Node 22; Node 22 trên Linux chưa được chạy trong GitHub. |
| Browser/GPU | Chỉ điều khiển **Chromium nhúng**, UA Chrome 155; WebGL ANGLE D3D11 **Intel Iris Xe**. Máy có RTX 3050 nhưng capture không dùng renderer NVIDIA. Chrome độc lập: **NOT VERIFIED**. |
| Runtime lúc bàn giao | API **8016**, production preview **5187**, một worker lease đúng store `build/m4-performance/jobs`; HTTP direct/proxy và đọc persisted jobs PASS. Lease chứng minh khóa store đang được giữ, **không phải heartbeat**. Receipt hiện tại được ghi trong validation summary. |
| Docker/OSRM hiện tại | **READY sau khi owner khởi động lại Docker**: Linux Engine trả lời, Hanoi CAR/MOTORBIKE modes đều `ready=true`, :5001/:5002. Lỗi Inference manager ở lần thử trước được giữ nguyên làm historical failure; không reset/sửa settings. HCM không chạy, container task cũ đã kiểm `no such object`. |
| Docker/OSRM trong phiên đo 17/10 | Hanoi CAR :5001, MOTORBIKE :5002 chạy đúng mode/profile/manifest; HCM :5000 chỉ được mở riêng cho regression. Live 10/100, M2 và S1 directed probes đã chạy thật. Không dùng trạng thái lịch sử đó để báo router hiện tại READY. |
| M3 correctness | Hai run UI 10/100 cùng seeds/config/routing identity có semantic hashes khớp baseline; sáu run lặp dưới tải RAM tổng hợp cũng khớp. Job 5.000 persisted giữ nguyên SHA-256 file. **Fresh 1.000 / 250 requests completed** sau khi owner bật Docker, lifecycle/geometric audit và HTTP→TS validator PASS. |
| FPS | Lỗi lịch sử ~1 Hz **không tái lập**. Plain RAF và matrix dev/preview hiện đo khoảng **60 FPS RAF**, p95 khoảng 16,9 ms. Không có trace đủ để xác định nguyên nhân lỗi cũ. |
| RAM | Phiên tối có free RAM quanh 1,8–2,3 GiB; không phải engine tự dùng hết 16 GB. Worker trực tiếp 10/100 có sampled peak RSS khoảng 102/71 MiB; phân biệt với process lifetime peak. Phiên sáng Docker/stack cũ tắt có free RAM ~7,74 GiB trước khởi động stack mới: **khác môi trường**, không được nhận là RAM tiết kiệm nhờ patch. |
| Meeting Mode | Đã triển khai preview, snapshot tối đa 4 Hz, clock presentation 10 Hz, health 30 s, paused unchanged không poll snapshot. A–C chạy với **video tổng hợp 640×360, 30 Hz**, không phải Google Meet. Small Live completed và playback/inspector PASS trong capture ngắn. Real Meet/Chrome độc lập/soak: **NOT VERIFIED**. |
| Tests | Artifact-free backend **195 PASS / 6 SKIP**, focused final **37 PASS**, frontend **182 PASS / 21 files**, focused **14 PASS**; typecheck/build PASS; lint **0 errors / 39 warnings**. Local Saved package verifier PASS 9 assets. GitHub Actions **NOT RUN**. |
| Guard theo yêu cầu owner cuối lượt | Standard/Meeting startup floor **0,5 GiB physical available**; small job floor **0,5 GiB physical / 1 GiB commit** trong envelope mục E. Workload lớn giữ 2/2 GiB, Benchmark startup 2 GiB; stress profiler 3/4 GiB riêng. **Chưa đo vận hành sát 0,5 GiB**; đây là lựa chọn owner, không phải calibrated safety threshold. |
| Blockers | Chưa chứng minh nguyên nhân lỗi 1 Hz; chưa Meet thật/soak; fresh5.000 chưa chạy vì free3,89<reserve4 GiB; chưa có full boot attribution/GPU trace; floor0,5 được test boundary, không stress máy xuống mức đó. |
| GO/NO-GO | **GO có điều kiện để tiếp tục phát triển và dùng small pilot** sau router readiness; **NO-GO nghiệm thu Meet thật, full 5.000 live capacity hoặc production**. Chi tiết mục I. |

Bản này bổ sung bằng chứng mới, giữ nguyên historical reports/evidence M3/M4/S0/S1. Không đổi scientific engine, Voucher Baseline/Treatment, routing geometry/identity hoặc Saved v1.

## B. Root cause analysis: hiện tượng khoảng 1 FPS

### B1. Điều đã biết và chưa biết

Lịch sử trước nhiệm vụ có Live 5.000 khoảng 1,19 FPS, fixture 100 khoảng 1,05 FPS, frame p95 khoảng 1.016 ms dù `document.visibilityState=visible`. Đó là observation cần điều tra, chưa phải bằng chứng SVG, fleet size hay MapLibre gây lỗi.

Trong phiên này, plain RAF được đo **trước khi dynamic import MapLibre**. Plain RAF đạt 60,15–60,31 FPS; map trống, basemap thật và các mức xe đều gần 60 trong cửa sổ 5 giây. Thử ẩn/hiện host không làm document chuyển hidden/focus=false và không tạo 1 Hz. Thử nghiệm đó không chứng minh host không bao giờ throttle; nó chỉ không tái lập điều kiện cũ.

**Kết luận chắc chắn:** trong các capture hiện có không thấy hồi quy cố định theo fleet size hoặc riêng Vite dev. Không có bằng chứng để quy nguyên nhân 1 Hz cho icons, MapLibre, GPU hay simulation engine. **Nguyên nhân lỗi lịch sử vẫn UNRESOLVED.** Không thể gọi lượt này là đã sửa triệt để lỗi 1 Hz.

### B2. Isolation matrix

Mỗi hàng 5 s, tuần tự, document visible/focused; viewport 1280×720, DPR 1,25; map canvas 764×543 ở lab. Dev/preview cùng browser/GPU nhưng chạy lần lượt, cache/warm age khác nhau; đây là đối chiếu ngắn, không phải randomized benchmark. Basemap luôn bật trong các hàng có Hanoi.

| Stage | Vite dev: RAF FPS | Production preview: RAF FPS |
|---|---:|---:|
| Plain RAF, chưa import MapLibre | 60,31 | 60,25 |
| MapLibre background trống | 60,33 | 60,35 |
| Hanoi basemap, 0 xe | 60,38 | 60,29 |
| Hanoi + 100 xe tĩnh | 60,20 | 60,27 |
| Hanoi + 100 playback | 60,36 | 60,18 |
| Hanoi + 1.000 playback fixture | 60,25 | 60,37 |
| Hanoi + 5.000 playback fixture | 60,15 | 60,28 |
| Production 5.000 fixture + pan | — | 60,14 |

Raw RAF timestamps, timer gaps, main-thread long tasks, map render/source events, source update counts, renderer, viewport, heap, GeoJSON UTF-8 bytes, visibility/focus được giữ trong các JSON `browser-isolation-*`. Pan 5.000 capture có p95 16,9 ms, pan callback p95 khoảng 0,3 ms, không có long task trong cửa sổ đó. Không suy ra tất cả execution/GC/GPU đều nhẹ trong toàn phiên.

**RAF FPS không đồng nghĩa GPU completed frames.** Map tĩnh có thể có RAF 60 nhưng map render event bằng 0 khi không có dirty state; raw render count được giữ để tránh nhập nhằng. Lab fixture cũng không có route fetch/dispatch engine như Live run. Không dùng fixture PASS để nghiệm thu toàn bộ Live.

### B3. Product capture và oracle

| Capture thật trong product, Hanoi ON | RAF FPS | p95 frame gap | Source updates | Phạm vi |
|---|---:|---:|---:|---|
| UI Live 10, Meeting | 60,18 | ~16,9 ms | 21 | CAR pickup/booking inspector |
| UI Live 100, Meeting | 59,96 | ~16,9 ms | 21 | MOTORBIKE trip inspector |
| Cùng run 100, Standard, controlled | 60,14 | ~16,9 ms | 48 | Pan ON, cùng seek/canvas/selection |
| Cùng run 100, Meeting, controlled | 60,10 | ~16,9 ms | 20 | Pan ON, cùng seek/canvas/selection |
| Cùng run 100, paused, pan OFF | 60,19 | ~16,9 ms | **0** | Không đổi simulation time |
| Persisted 5.000, Meeting | 60,08 | ~16,8 ms | 22 | Mở output cũ, không chạy lại engine |

Controlled 100 pair: canvas 764×463, DPR 1,25; cùng first idle vehicle để tránh inspector khác nhau. Benchmark có thao tác tự chọn xe đầu sau capture; đã kiểm soát selection giữa hai lần. Giảm `(48−20)/48 = 58,3%` source updates, không phải giảm 58% toàn bộ RAM/CPU/network. Source update gồm cập nhật cuối sau freeze; không gọi con số này là request throughput chính xác.

Product có **10 sources / 20 layers**, không có 5.000 DOM fleet markers. Strict oracle không bị nới assertion: persisted 5.000 kiểm tra source fleet 5.000, 5.000 unique cluster leaves, counts và render-settled PASS. Tại t=100, job đó có 1.000 offline, 4.000 online, 3.861 idle, 1 assigned, 138 onTrip, 139 moving. **Không phải 5.000 xe cùng chuyển động.**

Baseline product fixture 100 trước tối ưu đo 60,31 FPS, nhưng canvas 764×488, scenario khác Live controlled; không dùng nó làm before/after FPS có đối chứng. Hình screenshot 5.000 và resume sau đó ở viewport hẹp hơn cũng không thay raw dimensions của benchmark.

### B4. Instrumentation đã bổ sung và bước bắt lỗi tiếp theo

- `performance.html`: plain RAF, map trống, Hanoi, fleet matrix; pan ON/OFF; video tổng hợp tùy chọn; raw DOM metrics có thể tải/lưu lại.
- Product benchmark: focus/visibility, raw frame gaps, bounded wall timeout, chẩn đoán low cadence. Timeout vẫn là lỗi, không đổi thành PASS.
- Nếu tái xuất hiện 1 Hz: giữ nguyên session, chụp plain RAF trước. Plain cũng 1 Hz thì ưu tiên host/scheduler/foreground/driver; plain bình thường nhưng map chậm thì lấy Chrome Performance trace, map render/source placement, GC/WebGL workload; chỉ dev chậm thì so build preview tương ứng.

Phiên này không có Chrome CDP Performance trace, GPU/compositor trace, GC pause attribution hoặc independent Chrome driver. Raw longtask/RAF/network/CPU samples đủ tái xem observation ngắn nhưng **không thay thế profiler trace**. Không sửa MapLibre theo giả thuyết khi chưa có evidence.

## C. Memory attribution và khả năng dùng laptop 16 GB

### C1. Định nghĩa, tránh double-count

Physical available lấy từ Windows; commit headroom = CommitLimit − CommittedBytes. Private Bytes biểu diễn process private commit, có thể lớn hơn working set; không gọi private bytes là RAM vật lý đang resident. `processPagefileBytes` từ Windows process counters cũng không phải lượng file pagefile thực tế của riêng process. Pagefile actual usage lấy riêng `Win32_PageFileUsage`.

Working sets giữa process có thể chia sẻ pages. Docker container memory nằm trong VM/WSL accounting; JS heap nằm trong browser process. **Không cộng container RSS + WSL + browser heap + process working sets thành “tổng RAM máy”.** Tổng system pressure đọc trực tiếp Windows physical/commit.

### C2. Process/service evidence

| Thành phần / trạng thái | Working set/RSS | Private/commit | Nhận xét |
|---|---:|---:|---|
| Vite dev cũ, phiên dài PID 27928 | ~513 MiB | ~1.108 MiB | Có chiếm đáng kể; không chứng minh leak/nguồn retained objects bằng một sample |
| Fresh dev chưa mở client PID 21116 | ~90,4 MiB | ~115,1 MiB | Cold startup |
| Fresh dev đã mở full UI | ~143,7 MiB | ~217,9 MiB | Warm state; peak working set ~243 MiB |
| Fresh production preview PID 24472 | ~94,7 MiB | ~113,4 MiB | Cùng comparison window |
| API trước load persisted 5.000 | ~57,0 MiB | ~45,4 MiB | Cache empty |
| API sau load persisted 5.000 | ~87,8 MiB | ~76,0 MiB | Cache entries=1 |
| API sau ~32 s idle | ~64,8 MiB | ~52,9 MiB | Cache entries=0; không về hoàn toàn baseline |
| Worker direct live 10, sampled peak | **101,59 MiB** | **90,18 MiB** | Bao gồm prepare/audit/persist, 20 requests |
| Worker direct live 100, sampled peak | **71,38 MiB** | **59,64 MiB** | Warm Python process; không suy 100 rẻ hơn 10 theo quy luật |
| Fresh worker live 1.000, 18/10 | **114,11 MiB** | **102,47 MiB** | 400 CAR/600 MOTORBIKE, 250 requests, seed m4-memory-1000; khác session, không phải đồng thời Meet |
| Hanoi CAR container trong baseline | ~34 MiB | Docker metric riêng | Limit 1 GiB không phải 1 GiB được reserve |
| Hanoi MOTORBIKE container | ~44 MiB | Docker metric riêng | Sau route warm ~47–48 MiB |
| WSL VM tại một sample | ~837 MiB WS | ~1.505 MiB private | Bao gồm Linux/VM/caches, không chỉ OSRM; biến động theo phiên |
| Browser heap persisted 5.000 product | ~159,9 MiB | JS heap estimate | Không phải browser total RSS/VRAM |
| Browser heap lab 5.000 warm matrix | ~180 MiB | JS heap estimate | Page tích lũy stage/GC khác product; không so trực tiếp để kết luận leak |

Fresh dev warm so preview trong capture chênh khoảng **104,5 MiB private / 49 MiB working set**. Cold dev và preview gần nhau. **Không được quảng cáo tiết kiệm 1 GiB chỉ nhờ đổi dev sang preview**: phần extra của dev cũ còn phụ thuộc lifetime/HMR/cache và cần Node heap trace để giải thích. Không stop Vite cũ của người dùng để tạo số đo đẹp.

Worker `processPeakRssBytes` là lifetime peak (cold 10 khoảng 113,6 MiB), còn `peakRssBytesSampled` chỉ max của samples mỗi 50 ms; đỉnh rất ngắn có thể bị bỏ lỡ. Bảng dùng sampled peak có nhãn rõ. Không lấy peak của process profiler làm peak riêng OSRM hoặc API.

### C3. System commit, pagefile và paging

Các cửa sổ không phải baseline boot có kiểm soát; ứng dụng khác vẫn hoạt động. Tất cả process samples có trong ignored raw files; compact summary giữ max theo process và không lưu title/URL/commandline riêng tư.

| Cửa sổ 17/10 | Samples | Minimum physical available | Maximum system commit | Minimum commit headroom | Max page reads/s |
|---|---:|---:|---:|---:|---:|
| Baseline initial | 2 | 2,250 GiB | 21,100 GiB | 3,914 GiB | 498 |
| Production isolation | 26 | 1,817 GiB | 21,196 GiB | 3,753 GiB | 1.358 |
| Constrained/synthetic acceptance window | 59 | 1,844 GiB | 20,798 GiB | 3,470 GiB | 2.432 |
| UI 100/persisted window | 46 | 1,987 GiB | 20,468 GiB | 3,800 GiB | 23 |

Page reads là system-wide, median phần lớn các cửa sổ bằng 0; bursts không thể gán cho GSM từ dữ liệu này. Baseline pagefile allocated ~9.451 MiB, current ~1.105 MiB, peak ~2.793 MiB; các cửa sổ sau allocated giảm ~8.686 MiB, current ~1.075 MiB. Commit limit có thể thay đổi cùng pagefile; xem raw theo sample, không cố định limit bằng physical RAM.

Baseline recorder ban đầu yêu cầu 12 s nhưng CIM warmup làm cửa sổ chỉ 2,07 s. File cũ được giữ và **không gọi đó là 12 s đo**. Recorder đã sửa để tính requested duration sau first sample; resume 5 s có 4 samples trong 5,68 s, tổng wall ~14,3 s gồm warmup. Đây cũng giải thích vì sao không dùng requested interval như số sample chắc chắn.

Phiên sáng 18/10, trước stack mới và Docker tắt, có free ~7,74 GiB. Chênh với tối trước chủ yếu là **khác session/app/service state chưa kiểm soát**; không phải estimate memory saved của patch. Không có complete before-Docker → after-Docker → each-service boot series trong nhiệm vụ. Trạng thái trước Docker/Chrome thật/Meet thật, browser toàn bộ RSS riêng của tab, kernel hard faults riêng từng process, GPU memory: **NOT VERIFIED**.

### C4. Live workload, payload và cache

Baseline seeds `m4-memory-10` và `m4-memory-100`: 40% CAR, 60% MOTORBIKE, onlineFraction=1, 20 requests, horizon=900, maxWait=300, candidate max=128. Result 10 là 148.860 bytes, snapshot t=100 là 3.276 bytes; result 100 là 157.617 bytes, snapshot 18.780 bytes. Những số đó không bao gồm Python object overhead, JSON copies hoặc basemap.

Persisted job 5.000: JSON **6.654.976 bytes**, 5.000 vehicles, 1.250 bookings, 6.250 events, 714 routes. Parse/release experiment có private delta khoảng 14,8 MiB, gần quay về baseline sau release/GC. API thực tế load làm private tăng ~30,6 MiB; idle cache expiry giải phóng ~**23,1 MiB private**, còn ~7,6 MiB cao hơn ban đầu. Hai phép đo có allocator/lifetime khác nhau, không dùng parse delta thay cho API footprint.

Route/table caches đã có bound, chỉ tồn tại trong router client của một execute_live và close sau job. Telemetry từng mode (`routeCacheSize`, `tableCacheSize`, requests, latencies) giữ trong `before.json`/`after-constrained.json`. Không có bằng chứng cần Redis, delta snapshot protocol hoặc Web Worker projection; chưa triển khai các kiến trúc đó.

### C5. Repetition và leak limits

`after-constrained.json`: sáu runs 10/100, ba vòng, có **96 MiB** bytearrays gây tải tổng hợp có giới hạn. Allocator tự dừng cấp thêm khi free dưới 1,85 GiB hoặc commit headroom dưới 2,5 GiB; không cố ép swapping. Hai run đầu bắt đầu ở ~1,848 / 1,832 GiB, xuống thấp nhất ~1,809 GiB; min commit ~3,43 GiB. Tất cả COMPLETED, hashes khớp baseline.

Khi 96 MiB pressure còn giữ, cold before private ~132,8 MiB, sampled peak ~198,9 MiB, after release ~152,7 MiB; warm after sáu runs khoảng 152,7–154,7 MiB, không tăng tuyến tính trong cửa sổ đó. Không trừ 96 MiB rồi gọi kết quả là exact physical consumption.

Đã thực hiện tạo run, mở cũ, seek/play/pause, đổi presentation profile, chọn xe/route, reload và fixture matrix. Chưa có chu kỳ soak định lượng đủ dài cho mọi tổ hợp dashboard→fixture→mode→selection→reload. **Chưa chứng nhận không memory leak**. Cache release và bounded history là cải thiện có đo, không thay thế leak investigation dài hạn.

### C6. Ước tính vận hành 100–1.000 xe và Docker

Không có công thức đáng tin “RAM mỗi xe” vì routing candidates, request count, route/event history, online schedule, UI snapshots và caches khác nhau. Đã đo 100 xe/20 requests peak worker khoảng 71 MiB trong process warm; fresh1.000/250 requests ở session sáng có sampled peak114,11 MiB, private102,47 MiB, wall5,62 s, 250 completed/0 unserved. Result1.000 là1.637.720 bytes, snapshot t=100 là177.982 bytes. Không suy worker RSS thành tổng RAM Windows/browser/VM hoặc extrapolate linearly. Fresh5.000 vẫn **NOT RUN** ở free3,89 GiB, dưới reserve4 GiB của profiler; reserve benchmark3/4 GiB khác API admission.

Live cần router CAR/MOTORBIKE cục bộ đã xác minh. Docker là cách đóng gói hiện có; tắt Docker khi không có OSRM tương đương đang chạy thì **không tạo Live**. Có thể dùng persisted completed job và local fixtures/Saved Replay khi router tắt, miễn API/render assets cần thiết còn sẵn. Không có native Windows OSRM setup mới được triển khai hay kiểm thử trong nhiệm vụ.

## D. Tối ưu đã thực hiện và trade-offs

| Thay đổi | Bằng chứng / tác động | Trade-off và giới hạn |
|---|---|---|
| Paused unchanged không poll snapshot | Unit timer count=0; access log snapshot GET 134→134 trong 5 s; source updates=0 | Seek/visibility/retry vẫn wake đúng epoch; health/job status là luồng riêng |
| Meeting cadence | 100 ms→250 ms snapshot; clock presentation 30→10 Hz; health 15→30 s | Giảm update overhead; chuyển động/clock hiển thị thưa hơn, không đổi scientific time/outcomes |
| Production preview cho Meeting/Benchmark | Fresh warm dev ~217,9 MiB private vs preview ~113,4 MiB | Cần build trước; source identity check chống dùng dist cũ; không có HMR |
| One-result idle cache 30 s | API entries 1→0, private giảm ~23,1 MiB sau idle | Lần đọc lại phải parse disk; trong playback active cache vẫn được giữ; allocator không chắc trả toàn bộ pages |
| Admission trước enqueue | HTTP 507 `RESOURCE_PRESSURE`, structured current/required physical+commit; ba lần reject không tạo job | Không reservation; áp lực có thể đổi trước worker bắt đầu |
| Tách startup reserve và job reserve | Owner yêu cầu cuối: Standard/Meeting startup0,5 GiB; small job0,5 physical/1 commit; lớn2/2 GiB | Lower floor là operating preference, chưa đo ở sát0,5; không gọi guard là memory consumption/reservation |
| Router selection | Hanoi-only không tự mở HCM; None chỉ kiểm tra | HCM workflow cần mở riêng; không tự stop container đang dùng |
| Benchmark bounds/raw evidence | Wall timeout, RAF/focus/raw gaps, source counts, history tối đa 100 | Không có GPU profiler; timeout không thành PASS |
| Bounded Docker diagnostic probes | Lỗi Desktop làm `docker info` treo được quan sát thật; helper có budget mặc định 8 s. Probe thử budget 2 s trả timeout sau 2,19 s | Chỉ terminate CLI con do probe tạo, không kill Desktop/WSL/container. StartRouters từ chối sớm khi Engine chưa ready; sampler vẫn ghi được Windows samples |
| Ownership receipts / stop helper | Exact workspace, PID/start/executable/child checks; không stop active job | Receipt cũ/PID tái sử dụng bị từ chối, cần kiểm tra thủ công |

GeoJSON vẫn là full replacement `setData`; selected route tải riêng, MapLibre instance giữ ổn định, native symbols/clusters giữ nguyên. Không xóa Hanoi basemap hay thay geometry bằng đường thẳng để tăng FPS. Không thay scientific engine hoặc immutable output layout. Không có bằng chứng cần rewrite backend engine trong milestone này.

## E. Development profiles và Resource Guard

### E1. Cấu hình thực tế

| Profile launcher | Frontend | Snapshot tối đa | Clock publish | Health | Startup reserve |
|---|---|---:|---:|---:|---:|
| Standard | Vite dev | 10 Hz | 30 Hz | 15 s | 0,5 GiB |
| Meeting | Production preview | 4 Hz | 10 Hz | 30 s | 0,5 GiB |
| Benchmark | Production preview | 10 Hz | 30 Hz | 15 s | 2 GiB |

Chọn profile trên UI chỉ đổi presentation; không biến một dev server đang chạy thành preview. Muốn footprint preview phải khởi động profile Meeting/Benchmark của launcher. Hidden document ngừng snapshot projection/health timer; visible wake lại. Job đang QUEUED/RUNNING vẫn poll trạng thái để biết completion/cancel; không gọi đây là ngừng mọi network khi hidden.

Các profile dùng cùng một API/worker implementation và các inputs giống nhau; test so POST bodies Standard/Meeting giống nhau. Không giảm ngầm số xe/booking, không đổi seed/online mix/demand, Voucher, ETA hay routing identity. Worker chỉ một lease trên store. Launcher xác minh workspace/store/PID/proxy/kind, **chưa xác minh code revision của process cũ**: sau thay Python phải restart dịch vụ thuộc mình; build identity chỉ kiểm tra frontend sources.

### E2. Admission policy cuối cùng

- Small chỉ khi **fleet ≤100, bookings ≤20, horizon ≤900 s, onlineSchedule rỗng, maxCandidates ≤128**: physical available ≥**0,5 GiB**, Windows commit headroom ≥**1 GiB**.
- Ngoài envelope đó: giữ physical ≥**2 GiB**, commit headroom ≥**2 GiB**. Đây là protection floor, không phải capacity guarantee; large benchmarks vẫn cần reserve cao hơn và chạy riêng.
- API kiểm tra trước `JobStore.create`; worker kiểm tra lại trước execute_live. JobStore core không phụ thuộc RAM để tests/fixtures không bị state máy ảnh hưởng.
- Windows commit thiếu thì reject dù free physical cao; physical thiếu thì reject dù pagefile lớn. Linux metrics không có commit field thì ghi unknown, vẫn kiểm tra physical.

Trong capture constrained, policy thử nghiệm khi đó là1,5 GiB, mọi run bắt đầu cũng≥1,75 GiB. Agent ban đầu chọn floor1,75; sau đó **owner trực tiếp yêu cầu hạ “1/2GB”, được hiểu là0,5 GiB**, nên floor cuối đổi theo yêu cầu đó. Không sửa raw capture hoặc coi các run>1,8 GiB là bằng chứng vận hành an toàn ở0,5. Boundary **0,50 được phép /0,49 bị chặn**, commit1/0,5 và no-enqueue-on-rejection được test; focused37 PASS sau thay đổi. Workload100xe/100bookings hoặc horizon dài vẫn dùng guard2 GiB. Không cố cấp tải để đẩy máy xuống0,5 GiB và tạo swapping chỉ để đạt acceptance.

Không có check paging-rate mới dùng để tự kill job: global paging samples không đủ attribution và có bursts từ ứng dụng khác. Admission chỉ bảo vệ snapshot thời điểm đó; không loại bỏ khả năng pressure sau admission. Low FPS/paging và `RESOURCE_PRESSURE` là các hiện tượng khác nhau; thông báo UI không gọi chúng thành backend offline chung.

### E3. Docker/WSL

Đã đọc `.wslconfig` (không tồn tại) và selected Docker settings (không thấy memory/WSL/CPU/swap override rõ; null không chứng minh default). Không thay settings, pagefile, registry; không chạy `wsl --shutdown`. Không có controlled VM reclaim benchmark, nên chưa khuyến nghị một con số memory cap như bảo đảm phù hợp máy này.

Biện pháp ít rủi ro đã áp dụng: chỉ start routers cần workflow, reuse đúng graph, tránh HCM nếu Hanoi-only, không start benchmark tools khi không dùng. Nếu muốn thử WSL cap/reclamation sau này: owner sao lưu cấu hình, đo trước/sau cùng workload, tính cả graph preprocessing và những WSL projects khác; có thể revert file rồi restart theo kế hoạch của owner. Chưa thực hiện và chưa tính savings cho hướng này.

## F. Meeting Mode acceptance

| Scenario | Đã làm | Kết quả và giới hạn |
|---|---|---|
| A: website + Hanoi, chưa job | Basemap thật 5/5 layers; video tổng hợp đang chạy | Usable trong IAB; Chrome độc lập/Meet thật NOT VERIFIED |
| B: Live 10 / 20 requests | UI POST→worker→persist→playback→CAR inspector | COMPLETED, 19 completed/1 unserved là outcome đúng seed; không ép thành 20/20 |
| C: Live 100 / 20 requests | UI tạo, chọn CAR/MOTO, seek/play/pause/profile compare | 20 completed/0 unserved; RAM/RAF/API trong capture không lỗi vô căn cứ |
| D: persisted 5.000 | Copy allowlisted immutable files vào store riêng, kiểm SHA; open/seek/select | Không chạy lại engine, cluster/source oracle PASS, chọn CAR booking/route đúng |
| E: fresh 1.000 | Sau Docker recovery, session sáng riêng, reserve3 GiB | **PASS** 250/250, 5,62 s, peakRSS114,11 MiB; geometry audit40 assignments/320 samples và HTTP→TS PASS; không phải Meet scenario |
| F: fresh 5.000 | Conditional reserve4 GiB | **NOT RUN** lần cuối free3,89<4 GiB; vẫn giữ capability/code benchmark, không nhận capacity mới |

Synthetic video dùng `canvas.captureStream` 640×360, 30 Hz, **không camera/microphone**, không RTC/Meet network/encode. Sau acceptance harness ghi 15.175 frames trong page age ~510.225 ms, tương ứng video duy trì khoảng 30 Hz trong ~8,5 phút page lifetime. Product FPS capture vẫn chỉ từng cửa sổ 5 s. Synthetic load và bounded bytearray pressure là hai phép thử khác nhau; không gộp chúng thành một cuộc họp thật.

Không xảy ra mất phản hồi trong tương tác đã thực hiện. Không có SLA “Meet ổn định” được đặt hay nghiệm thu. Video tab đã đóng cuối phiên; frontend task tab được giữ cho bàn giao persisted run. Phiên resume đọc lại run với Docker tắt cũng PASS, nhưng không coi đó là fresh Live readiness.

Sau khi phiên sáng có khoảng 7 GiB free, đã thử khôi phục Docker để chạy lại E/F riêng. Docker Desktop backend log lúc **08:43:52 ngày18/10** báo lỗi khởi tạo Inference manager, chưa khởi động Engine. Vì vậy E/F vẫn **NOT RUN**, lần này do host dependency, không phải thiếu RAM hay test engine thất bại. Lỗi được lưu `docker-start-failure.json`; không xóa socket, reset factory, đổi pagefile/WSL/Docker settings. Hai Docker CLI diagnostics bị treo được dừng bằng exact PID/parent/command identity; không dừng Desktop hoặc user containers. Đường dẫn executable cài thực tế ở user Programs/DockerDesktop; initial probe đường Program Files không tồn tại và không chạy gì.

**Cập nhật sau phản hồi owner:** Docker đã được owner khởi động lại, hai Hanoi routers chạy sẵn và API xác minh modes READY. Không nhận agent đã sửa nguyên nhân Inference manager. Fresh1.000 run **e2caced02db64a02a56300050544690b** completed lúc08:49:22, 250/250; fresh5.000 skipped theo reserve ở3,89 GiB. Không có Google Meet/video tổng hợp trong lần large benchmark sáng này. Raw `resume-large.json` và window `resume-large-processes.json` tách khỏi phiên tối. HCM receipt cũ inspect trả `no such object`; không có stop container của owner.

## G. CI và regression

### G1. Workflow

`.github/workflows/source-checks.yml`: push/pull_request vào main, feature/**, codex/**; read-only contents; concurrency cancellation; backend/frontend jobs độc lập; pip/npm cache. Không secret mới, không branch protection, không Docker/PBF/OSRM preprocessing/WebGL stress.

Backend Python 3.11 install `backend/requirements.lock.txt`, `RUN_REAL_DATA=0`, pytest `-q -rs`. Frontend Node 22, `npm ci`, Vitest maxWorkers=2, typecheck, lint (errors blocking, warnings hiện rõ), production build. Workflow YAML được parse với BaseLoader để `on` không bị YAML1.1 hiểu thành bool; kiểm cấu trúc triggers/jobs/permissions PASS. Đây không phải GitHub runner execution.

`frontend/public/replay` sealed package hiện Git-ignored, không nằm trong clean source checkout. Workflow chạy verifier khi manifest hoặc demo package hiện diện (partial package phải fail); nếu cả hai absent thì **explicit SKIP package verifier**, vẫn chạy replay contract Vitest. Local full package 9 assets có sẵn và verifier PASS. Không regenerate sealed package để ép CI PASS. Verifier đã tự build artifact validator, bỏ phụ thuộc `.replay-tools/artifact.mjs` tồn tại từ phiên trước.

### G2. Local equivalents đã chạy

| Check | Kết quả | Evidence / ý nghĩa |
|---|---|---|
| Backend clean source, no GIS/OSRM/store/.env | **195 PASS / 6 SKIP**, 25,54 s | `ci-backend-final.log`; pip install lock + pip check PASS |
| Final memory/M3/S0S1 focused | **37 PASS**, 1 warning | `backend-focused-resume.log`; sau final admission envelope |
| Backend full sau resume, trước owner floor0,5 | **195 PASS / 6 SKIP**, 65,38 s | `backend-full-resume.log`; root checkout, RUN_REAL_DATA=0, không phải fresh artifact-free copy |
| Focused sau owner floor0,5 | **37 PASS**, 1 warning | `backend-low-memory-rerun.log`; boundary0,50/0,49, commit, API no-enqueue, M3/S0S1 |
| Frontend root full | **182 PASS / 21 files**, 18,54 s | `frontend-tests.log` |
| Frontend clean source npm ci + full tests | **182 PASS**, 20,69 s | ignored ci logs; npm ci/typecheck/build PASS |
| Final frontend lifecycle/map/runtime focused | **14 PASS** | `frontend-focused-final.log` |
| Root lint | **0 errors / 39 warnings** | Existing warnings honest, không suppress |
| Typecheck / production build | PASS | Chunk-size warning MapLibre còn, không phải build failure |
| Saved Replay local | PASS 9 assets | digest `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`; browser export NOT RUN |
| M2 Hanoi + HCM smoke | PASS | 20 completed/0 unserved; repeatable, wrong-router rejection, outage isolation, HCM live route |
| S1 directed geometry | PASS CAR/MOTORBIKE | One-way forward/reverse và very short leg; standalone probe ngoài operating box không biến thành accepted M3 job |
| UI live 10/100 scientific comparison | PASS | Same config/seed/provenance/events/assignments/routes/timelines semantic hash; runId/metrics bỏ khi so |
| Current Live10, owner floor0,5 | PASS | UI→API→worker job786e10e8382540fc8de15ccbf87bff9e completed19/20, same semantic hash; actual free~4 GiB, không phải boundary stress |
| Fresh1.000 sau Docker recovery | PASS | 250/250; audit40 assignments/320 samples; HTTP→TS contracts; result copied byte-identical vào task playback store |
| Geometric audit 10/100 | PASS | 19/20 assignments, 256/184 samples, tolerance 0,02 m, seek deterministic |
| Persisted 5.000 immutable hash | PASS | Original/copy result SHA `7d4cf390d4514f28793167a70af7f322e7196109a3640c1bc7c2915ce6829312` |
| HTTP→product TS validators, 10/100/5.000 | PASS after resume | summary không full history; snapshot gate, mode routes, selected booking + both legs |
| Launcher start/reuse/stop/parser | PASS scoped | Receipts, preview identity/proxy, correct lease/store; cả 4 PowerShell scripts (thêm Docker probe helper) parse clean; broken-Engine timeout đo thật |
| S0/S1 sau bounded Docker probe | **5 PASS**, 1 warning | `s0-final-resume.log`; sampler vẫn xuất Windows samples và timeout status khi stats không trả lời |
| GitHub Actions | **NOT RUN** | Workflow chưa stage/push; không có remote status claim |

Sáu skips explicit: A1 real-data (2), A2 local OSM/OSRM, A3 real local OSM/OSRM, A4 real dataset/OSRM, M2 opt-in artifacts. Full artifact-free run trước tightening envelope; full root195 chạy ở floor1,75; focused37 rerun PASS sau yêu cầu owner đổi floor0,5. First low-floor rerun có2 failures vì fixture rejection vẫn dùng boundary0,5 cũ; đã đổi fixtures xuống0,49, giữ assertions reject/no-job, rerun37 PASS. Raw failure giữ nguyên. Python có Starlette/httpx deprecation warning; không nâng dependencies trong scope này.

Clean-source copy nằm trong ignored `build/`, nên oxlint ở nested copy từng báo không thấy file; chạy lại explicit `--no-ignore` vẫn không phải bằng chứng root lint hợp lệ. Root `frontend` lint đã chạy thật, 39 warnings/0 errors. GitHub checkout root không nằm trong ignored build ancestor. Local Node24/Windows khác Node22/Linux runner; không gọi local equivalents là GitHub PASS.

Scientific files `simulation.py`, M2 dispatch/routing core, Voucher core, sealed public assets không sửa. M3 immutable store/cancellation/worker tests và existing front contract tests tiếp tục PASS. Saved UI import/export đầy đủ và HCM toàn bộ manual UX chưa chạy lại; HCM smoke + existing unit regressions không thay thế tất cả flow checks.

## H. Raw evidence, failures và reproducibility

Tracked gọn: [`m4-performance-evidence/validation-summary.json`](m4-performance-evidence/validation-summary.json), browser raw RAF JSONs, aggregate process peaks/commit windows, live resource reports, correctness/contract results và screenshots. Hashes source và từng evidence file có trong summary. Không có credentials, meeting contents, window titles hoặc private Chrome URLs.

Các log chọn lọc được copy nguyên bytes thành **`.txt`** trong evidence vì `*.log` bị Git-ignore; `selectedLogCopies` trong summary ánh xạ tên raw→tên tracked. Raw `.log` gốc trong build không sửa. Không force-add ignored logs hoặc profiler data.

Ignored full local evidence: `build/m4-performance/` gồm process samples, CI source copy, full jobs/results, regression outputs, stdout/stderr; receipts/logs ở `build/s0-runtime/`. Không stage build jobs, `.env`, PBF/OSRM graphs, node_modules, `.replay-tools`, dist hoặc profiler per-process data. Không có native Chrome trace file vì không capture được profiler trace.

| Nhóm | Files |
|---|---|
| Browser lab | `browser-isolation-dev.json`, `browser-isolation-dev-matrix.json`, `browser-isolation-production.json`; raw RAF arrays/timer gaps/map events |
| Product | `product-meeting-10.json`, `product-meeting-100.json`, `product-standard-100.json`, `product-meeting-100-control.json`, `product-paused-100.json`, `product-meeting-persisted-5000.json`, `paused-network.json` |
| Memory | `before.json`, `after-constrained.json`, `api-cache-idle.json`, `frontend-server-{cold,warm}.json`, `windows-memory-summary.json`; raw `*-processes.json` ignored |
| Correctness | `final-correctness.json`, `contract-{10,100,5000}.json`, `m2-regression.json`, `s1-directed-summary.json` |
| Resume large/current policy | `resume-large.json`, `fresh-1000-{copy,audit}.json`, `contract-1000.json`, `low-memory-live10.json`, `contract-low-memory-10.json`, `modes-resumed.json` |
| Synthetic | `synthetic-video.json`, `synthetic-video-after-acceptance.json`; NOT real Meet |
| Images | `meeting-100-inspector.png`, `meeting-persisted-5000.png`, `resume-100-inspector.png`, `low-memory-live10.png` (current completed job + UI floor0,5) |

UI 10 run `08a6b84ce68847a398d67bb042d3ad2e`, 100 run `6c958c86abed4e4ba1faf973ebe601eb`, persisted 5.000 `088a063b0b0d46e1a8241fea277334a9`. Semantic 10 SHA `f4101a1ff235f70074cf339892a35ffeab6981c9887ac3178144e5738fedb7aa`; 100 SHA `91d3c406768af2ba8d7dcefc8541950ca2d69925f7f18a0ba281c19a4580152b`. Hàm `semantic_hash` recursively bỏ **runId và metrics**, giữ các field khoa học còn lại; không tuyên bố full JSON bytes identical giữa fresh runs.

Failures/limitations được giữ:

1. Old IAB tabs có `ERR_EMPTY_RESPONSE` lúc sửa Vite/HMR; PowerShell HTTP200 và new tabs vẫn chạy. Không có trace xác định nguyên nhân, không quy thành graph/FPS failure.
2. Stop helper lần đầu từ chối child interpreter/conhost không khớp; không mass-kill. Đã sửa kiểm child suffix/start identity và rerun stop receipt PASS; `stop-owned.log` rỗng vì lỗi được trả ở tool stream, các rerun logs còn.
3. M2 first run fail vì HCM unavailable; sau mở task-only HCM router rerun PASS. `live-regressions.log` giữ nguyên first failure.
4. Clean-source Saved verifier lúc đầu thiếu local package/validator; validator self-contained đã sửa, absent ignored sealed package được SKIP rõ; `ci-frontend-replay.log` giữ first failure.
5. Nested-copy lint discovery không hợp lệ; giữ logs và báo root lint riêng.
6. Direct CUA read-only scope không expose một số performance/video methods; đo qua harness chạy trong app rồi đọc DOM JSON, không dùng failed call như kết quả.
7. Baseline CIM window ngắn hơn yêu cầu; giữ raw, sửa duration ở lượt resume.
8. Docker/API/frontend cũ đều offline khi resume. Khi daemon chưa truy cập được, không gọi `docker stop` bằng ID cũ. Sau owner recovery, inspect HCM receipt ID trả `no such object`, chứng minh container task cũ không còn; không nhận agent đã stop container đó. Evidence `hcm-receipt-final-check.json`.
9. First Hanoi modes probe timeout5 s khi Docker lỗi; API/runtime/proxy HTTP200. Sau owner recovery đã recheck modes và cả hai READY (`modes-resumed.json`); không lấy basemap5/5 làm router readiness. Historical failure giữ `docker-start-failure.json`, bounded timeout giữ `docker-probe-bounded.json`.
10. Lượt test đầu sau đổi floor0,5 còn2 fixtures dùng0,5 làm dữ liệu reject nên fail; giữ `backend-low-memory-final.log` và rerun37 PASS sau sửa fixtures thành0,49. Không xóa rejection assertions.

## I. GO / NO-GO và hướng R1/M5

| Phạm vi | Quyết định |
|---|---|
| M4 100 vehicles + Hanoi | **GO phát triển / pilot có điều kiện**: short captures, routing inspector, paused behavior PASS; còn independent Chrome/soak |
| M4 5.000 rendering | **GO tiếp tục phát triển** với fixture và persisted measured load; **NO-GO nghiệm thu 5.000 all-moving/live SLA** |
| Lightweight/Meeting | **GO thử nhỏ trong envelope** sau readiness; **NO-GO chứng nhận Google Meet thật** |
| M3 correctness | **GO regression hiện có**; hashes/audits preserved; không có engine rewrite |
| M3 fresh large capacity | **GO có điều kiện cho1.000/250 cấu hình đã đo**; fresh5.000 NOT VERIFIED, cần stress riêng đủ reserve |
| S0 runtime | Launcher identity/proxy/receipt/stop đã kiểm, CLI probes có timeout; current API/proxy/worker/Hanoi modes READY sau owner bật Docker. Small Live readiness GO; floor0,5 chưa được stress ở boundary |
| R1 Regional Expansion | **GO chuẩn bị thiết kế/data contract**, chưa triển khai vùng mới; cần artifact/profile/basemap readiness và benchmark mỗi vùng |
| M5 pilot | **Conditional planning/pilot hạn chế** sau Chrome/Meet và soak cụ thể; chưa nghiệm thu operational pilot |
| Production | **NO-GO**: chưa có long-run capacity, host-throttling RCA, real-meeting proof, production deployment/observability/remote CI |

Ưu tiên tiếp: (1) giữ theo dõi lỗi Docker startup nếu tái xuất hiện, không reset dữ liệu tự động; (2) chạy Chrome độc lập và Meet thật được owner cho phép; (3) capture trace ngay khi1 Hz tái xuất hiện; (4) leak soak nhiều chu kỳ, quan sát paging khi dùng floor0,5; (5) stress fresh5.000 ở session riêng đủ reserve; (6) owner commit/push CI rồi kiểm GitHub statuses. Chưa cần đổi kiến trúc hoặc mở R1 implementation để xử lý RAM hiện tại.

## J. PowerShell runbook đã đối chiếu với implementation

Các lệnh HTTP/runtime/build/test dưới đây đã thực thi ở workspace này hoặc cùng tương đương với ports/store của task. `Start-Process` Chrome/Meet thật chỉ là thao tác owner chạy; **không nhận đã test Chrome độc lập**. Chọn một profile; đừng mở chồng hai stack rồi xem RAM như một stack. Root shell:

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
$py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
$api = 'http://127.0.0.1:8016'
$site = 'http://127.0.0.1:5187'
$store = 'build/m4-performance/jobs'
```

**1. Status không khởi động dịch vụ:**

```powershell
.\scripts\Start-GsmDev.ps1 -StatusOnly -Profile Meeting -Routers None -ApiPort 8016 -FrontendPort 5187 -Store $store
```

**2. Standard dev:** chọn ports riêng nếu cần; launcher không stop process khác.

```powershell
.\scripts\Start-GsmDev.ps1 -Profile Standard -Routers HanoiBoth -StartRouters -ApiPort 8013 -FrontendPort 5183 -Store build/m3/jobs
```

**3. Meeting / production preview:** mở Docker Desktop Linux Engine trước nếu muốn Live; dist phải fresh.

```powershell
Push-Location frontend
npm.cmd ci
npm.cmd run build
Pop-Location
.\scripts\Start-GsmDev.ps1 -Profile Meeting -Routers HanoiBoth -StartRouters -ApiPort 8016 -FrontendPort 5187 -Store $store
```

Nếu chỉ đọc output đã lưu: thay `-Routers HanoiBoth -StartRouters` bằng `-Routers None`. Worker hiện hành phải restart sau đổi Python source; launcher reuse không tự reload code. Frontend source đổi thì build lại trước preview.

**4. Docker/OSRM, chỉ serve graph đã chuẩn bị, không preprocessing:**

```powershell
docker info --format '{{.OSType}}'
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
docker stats --no-stream
& $py scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
& $py scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
Invoke-RestMethod "$api/api/v2/regions/nvmr-hanoi-core/modes" | ConvertTo-Json -Depth 10
# HCM smoke chỉ khi cần:
& $py scripts/pipeline.py serve --detach
```

Port listening không thay manifest validation. `MODE_NOT_READY` cần đúng region/profile/graph/URL; không trỏ MOTORBIKE vào CAR để vượt check.

**5. API/worker/proxy:**

```powershell
Invoke-RestMethod "$api/api/health"
Invoke-RestMethod "$api/api/v3/simulation/jobs/runtime" | ConvertTo-Json -Depth 8
Invoke-RestMethod "$site/__gsm_dev"
Invoke-RestMethod "$site/api/v3/simulation/jobs/runtime" | ConvertTo-Json -Depth 8
```

`backend_ready` legacy HCM khác Hanoi mode readiness. `worker=locked` đúng store chưa khẳng định worker đang tiến triển; xem job status/log nếu QUEUED lâu.

**6. Tạo Live 10/20 sau readiness:** lệnh dưới tạo một job thật, không loop tự submit.

```powershell
$body = @{regionId='nvmr-hanoi-core';seed='m4-memory-10';fleetSize=10;carCount=4;bookingCount=20;horizonSeconds=900;maxWaitSeconds=300;onlineFraction=1;workload='typical'} | ConvertTo-Json
$job = Invoke-RestMethod "$api/api/v3/simulation/jobs" -Method Post -ContentType 'application/json' -Body $body
$job.id
Invoke-RestMethod "$api/api/v3/simulation/jobs/$($job.id)"
# Sau COMPLETED:
Invoke-RestMethod "$api/api/v3/simulation/jobs/$($job.id)/result?summary=true"
```

Nếu 507 RESOURCE_PRESSURE: đọc required/current physical và commit, giải phóng workload của mình, thử lại một lần khi đủ; không tự spam tạo job, không giảm count ngầm. Current guard small floor **0,5/1 GiB** theo yêu cầu owner; chưa phải chứng nhận không paging tại boundary.

**7. Playback trong Chrome:** owner dán URL dưới vào Chrome thông thường; chọn “Mở run đã có”, ID `$job.id` hoặc run 100 đã lưu; seek 100, chọn xe active, Phát/Tạm dừng.

```powershell
Write-Output "$site/?runtime=simulation&profile=meeting"
Write-Output 'Run 100 đã lưu: 6c958c86abed4e4ba1faf973ebe601eb'
```

Trong task, cùng flow đã kiểm ở IAB. Muốn thử Meet thật phải dùng session được owner cho phép và ghi rõ Chrome/process/CPU/physical/commit cùng thời điểm; không ghi nội dung cuộc họp.

**8. Memory profiling:** chạy Windows sampler trong cửa sổ PowerShell riêng, rồi thao tác UI ở browser trong cùng cửa sổ đo. Live profiler chạy tuần tự, không chạy cùng stress/build/test.

```powershell
.\scripts\Profile-GsmMemory.ps1 -Seconds 60 -IntervalMs 1000 -Label meeting-manual -Output build/m4-performance/meeting-manual.json
& $py scripts/profile_simulation_memory.py --fleets 10 100 --repeats 3 --label manual-small --output build/m4-performance/manual-small.json
# Chỉ trong session benchmark riêng đủ headroom:
& $py scripts/profile_simulation_memory.py --fleets 1000 5000 --label manual-large --output build/m4-performance/manual-large.json
```

Mỗi label/output mới dùng isolated queue tương ứng; không tái dùng label nếu có pending job khác. `--pressure-mib` là opt-in thử tải tổng hợp, không cần cho sử dụng hàng ngày.

**9. Pagefile/commit/paging read-only:**

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory | Select-Object CommittedBytes,CommitLimit,PageReadsPersec,PagesInputPersec,PageFaultsPersec
Get-CimInstance Win32_PageFileUsage | Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage
```

Các size Win32_OperatingSystem ở KiB; PageFileUsage ở MiB. Không chỉnh pagefile từ những lệnh này.

**10. Browser benchmark:**

```powershell
Write-Output "$site/performance.html"
# Cross-language proof trên persisted job, không gọi engine:
node frontend/scripts/verify-simulation.mjs $api 6c958c86abed4e4ba1faf973ebe601eb build/m4-performance/manual-contract.json
```

Mở performance.html, chạy plain trước, giữ 5 s/stage, cùng viewport/DPR/GPU/focus; matrix tuần tự; so pan/video ON/OFF từng biến. Full product: mở Benchmark / Developer Tools, chọn pan/playback, capture, lưu JSON. Không chạy full build/tests cùng benchmark; không tắt Hanoi basemap để so FPS.

**11. CI tương đương local:**

```powershell
& $py -m pip install -r backend/requirements.lock.txt
& $py -m pip check
$env:RUN_REAL_DATA='0'
& $py -m pytest -q -rs
Remove-Item Env:RUN_REAL_DATA
Push-Location frontend
npm.cmd ci
npm.cmd test -- --maxWorkers=2
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
if ((Test-Path public/replay/manifest.json) -or (Test-Path public/replay/demo-experiment.json)) { npm.cmd run verify:replay } else { Write-Output 'SKIP sealed package absent; Vitest replay contracts still ran' }
Pop-Location
```

Nếu shell đã có RUN_REAL_DATA trước đó, owner lưu và restore giá trị thay vì xóa. Lượt task dùng isolated subprocess env; không thay owner env vĩnh viễn.

**12. Dừng/restart chỉ services thuộc task:** lấy **receipt vừa được launcher in ra**, dùng absolute path; đợi/hủy jobs trước. Không chọn “latest” mù khi có nhiều người dùng stack.

```powershell
$receipt = Join-Path (Get-Location) 'build/s0-runtime/REPLACE-WITH-EXACT-SESSION.json'
Get-Content -LiteralPath $receipt
.\scripts\Stop-GsmDev.ps1 -ReceiptPath $receipt
.\scripts\Start-GsmDev.ps1 -Profile Meeting -Routers None -ApiPort 8016 -FrontendPort 5187 -Store $store
```

Không dùng receipt của API/Vite cũ không do task tạo. Không kill theo process name; không chạy `wsl --shutdown`. Stop helper không tự stop Docker routers; để nguyên container owner đang dùng. HCM task-only cũ chỉ stop được sau inspect current ID/start trùng receipt; khi Docker offline chưa kiểm tra được thì để nguyên và báo hạn chế.

## K. Git và handoff

Không stage/commit/push/merge/rebase trong nhiệm vụ. Source/CI/test allowlist và documentation/evidence tách được thành hai commits nếu owner muốn. Trước commit cần xem `git diff --cached --stat`, `--check`, `--name-only` và **full staged diff**. Đừng `git add .`.

Đề xuất messages: `perf: add meeting profile and workload-aware resource guards`; `docs: record M4 memory evidence and Windows runbook`. CI có thể đi cùng source commit. Không stage ignored raw jobs/graphs/private profiling; toàn bộ evidence tracked ở thư mục riêng là bản chọn lọc có hashes. Danh sách file và lệnh allowlisted thực tế được nêu trong phản hồi bàn giao Codex.

Lệnh đề xuất, **chưa thực thi**:

```powershell
git add -- .github/workflows/source-checks.yml backend/app/simulation_cache.py backend/app/simulation_resources.py backend/app/simulation_jobs.py backend/app/simulation_worker.py tests/test_memory_performance.py scripts/m3_resources.py scripts/profile_simulation_memory.py scripts/Profile-GsmMemory.ps1 scripts/GsmDockerProbe.ps1 scripts/Start-GsmDev.ps1 scripts/Stop-GsmDev.ps1 frontend/package.json frontend/vite.config.ts frontend/performance.html frontend/scripts/build-identity.mjs frontend/scripts/verify-replay.mjs frontend/src/performance-lab.ts frontend/src/lib/simulation-profile.ts frontend/src/lib/fleet-clock.ts frontend/src/lib/use-simulation.ts frontend/src/components/simulation-map.tsx frontend/src/components/simulation-runtime.tsx frontend/src/components/simulation-workspace.tsx frontend/tests/use-simulation.test.ts
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git diff --cached
# Sau khi owner xem full diff:
git commit -m "perf: add meeting profile and workload-aware resource guards"

git add -- README.md docs/nvmr/M4_PERFORMANCE_MEMORY_STABILIZATION.md docs/nvmr/M4_IMPLEMENTATION.md docs/nvmr/M3_M4_INTEGRATION_REVIEW.md docs/nvmr/S0_S1_IMPLEMENTATION.md docs/nvmr/m4-performance-evidence
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git diff --cached
git commit -m "docs: record M4 memory evidence and Windows runbook"
```

Allowlist trên chính là các source/test/CI/docs paths đã thay đổi; evidence directory chỉ chứa các bản chọn lọc ghi trong validation summary. Không có lệnh push theo yêu cầu của nhiệm vụ này.
