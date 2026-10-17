# M4 — Product integration, Hanoi basemap và UX remediation

Ngày 17/10/2026, sau bàn giao M3/M4. Checkout tích hợp: `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`, branch `feature/nvmr-m0-architecture`, HEAD `455abebe177be42e07b88ed4f34d4fecbef29b75`. M3/M4 chưa commit khi bắt đầu. Bản báo cáo này ghi lượt kiểm chứng mới; số đo cũ trong `m3-m4-evidence/` là lịch sử, không được gộp với số đo basemap mới.

## 1. Root cause đã tái hiện

URL thực: `http://127.0.0.1:5183/?runtime=simulation`. Browser IAB/WebGL thật, cùng API8013/Vite5183 mà Owner đang chạy. Trước sửa, canvas MapLibre tồn tại, có controls/attribution và kích thước dương; screenshot `before-blank.jpg` cho thấy nền trống. Console tại lần mở đầu không có error/warning. Checkbox “Basemap Hà Nội cục bộ (cần API)” chưa chọn. Source `simulation-workspace.tsx` khởi tạo `localMap=false`, chọn `emptyStyle` (background only). Chọn checkbox qua UI, cùng map lập tức hiện đường, sông hồ và cây xanh (`before-basemap-enabled.jpg`). GET qua Vite `/api/regions/nvmr-hanoi-core/map/streets` trả HTTP200, 6.363.853 bytes. Không rebuild/copy GIS.

**Kết luận trong phiên tái hiện này:** blank style mặc định là nguyên nhân trực tiếp của bản đồ trống, không phải canvas thiếu, WebGL không khởi tạo, CSS zero-height, viewport HCM hay GeoJSON hỏng. Đây là quyết định phục vụ benchmark trước đó, nhưng là lỗi mặc định sản phẩm. Không suy diễn rằng mọi lần máy Owner gặp vùng trắng đều chỉ có nguyên nhân này: proxy, assets, GPU và RAM vẫn có thể lỗi độc lập.

Source trước sửa `App.tsx` return riêng `SimulationWorkspace` khi query `runtime=simulation`, bỏ qua shell/navigation GSM. Header legacy chỉ có link nhỏ “M3/M4 · quy mô lớn”; `PrimaryNavigation` có đúng bốn mode. Link đi/về là href nên reload trang. Đây là thiếu tích hợp/discoverability có thật, không phải user bỏ sót một tab Simulation vốn đã tồn tại.

Ở checkpoint đầu máy chỉ còn ~0,85–1,2 GiB RAM khả dụng. Các FAILED jobs có sẵn trong store có `RESOURCE_STOP` 0,89–1,68 GiB; đây là job trước lượt sửa, không phải kết quả job do lượt này tạo. Không dùng chúng như bằng chứng worker lỗi engine. Owner giải phóng RAM, các phép đo tăng tải mới bắt đầu sau khi headroom >2 GiB.

## 2. Implementation và ranh giới

- `App.tsx`: Simulation là mode thứ năm trong cùng app header/menu. Chỉ một nhánh bản đồ được mount tại một thời điểm. Các hook legacy giữ region/service behavior, không thay model hay limits. Tắt mapError legacy khi đổi mode để lỗi renderer cũ không chặn màn hình mới.
- `primary-navigation.tsx`: button **Mô phỏng quy mô lớn**, active `aria-current`, icon Layers, desktop expanded/collapsed và mobile sheet. Không còn link kỹ thuật nhỏ làm đường truy cập chính.
- `lib/navigation.ts`: parse deep links cũ Simulation/Saved, mode query cho legacy, pushState và popstate cho Back/Forward; giữ unrelated query/hash, bỏ fixture/fleet/zoom khi điều hướng chức năng. Đổi chức năng không reload document.
- `simulation-workspace.tsx`: nội dung nhúng trong shell, map trung tâm; Hanoi Core cố định và mô tả region cũ được giữ khi quay lại; không hiển thị HCM MOTORBIKE ready. Bản đồ hiện trước job, mặc định local Hanoi style. Điều khiển tổng1–5000, CAR0–total, MOTORBIKE phần còn lại, requests0–20000, online0–1, seed; tham số horizon/wait/workload đúng M3 contract. Không đổi engine.
- Progress/empty/QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED/INTERRUPTED và loading summary/snapshot có thông điệp riêng. QUEUED lâu chỉ nói worker có thể chưa chạy/bận; không giả heartbeat. Lỗi API khác lỗi assets và route. Có mở lại mã run. Rời mode dọn requests/clock/selection; job đã enqueue vẫn tồn tại, UI ghi rõ cần lưu ID/hủy chủ động.
- KPI snapshot: tổng/offline/online/idle/assigned/onTrip/moving, nhãn tiếng Việt. Final requested/assigned/completed/unserved nằm riêng, không suy ra current completed từ final.
- Inspector giữ route ref, exact immutable routingIdentity, trạng thái hiện tại, booking, WGS84, distance/duration và focus. Route geometry không nằm trong mỗi snapshot và không re-route khi chọn. Fixture không có tuyến/outcomes.
- `simulation-map-health.tsx`: kiểm tra năm sources GeoJSON thật, listen source/style/error/WebGL-context-lost, timeout20s, ResizeObserver cleanup; không đánh ready chỉ vì canvas có mặt. Error boundary bắt lỗi dựng WebGL. Retry đổi style URL version, giữ map instance khi bình thường. Không kiểm readiness qua OSRM/worker.
- Assets hiện phục vụ qua API region endpoints. Worker/router tắt không khóa assets nếu API còn chạy. Nếu toàn API tắt và asset chưa cache, không có cam kết offline Hanoi; UI báo lỗi rõ. Không thêm public tiles/router, không nhét ảnh nền hoặc copy graph.
- Benchmark developer tools thu gọn mặc định, fixture 100–5000 giữ nguyên, blank map opt-in, thời lượng5/30/60s mỗi zoom, xuất JSON gồm ON/OFF và map readiness. MapLibre vẫn full `setData`, stable IDs, clustering tới zoom 13, native layers và một tuyến chọn. Không thêm UI framework/dependency.
- Mobile390: bố cục dọc, map có chiều cao360px, form/KPI scroll trang; playback control wrap, menu sheet. Desktop1280: nav180px, controls310px, map còn lại.

## 3. Phương pháp và evidence

Thư mục mới `docs/nvmr/m4-ux-evidence/`; logs/baseline copies/raw monitor ở ignored `build/m4-ux/`. Trước chỉnh sửa đã copy 48 files hiện có vào `build/m4-ux/before/` và hash manifest, bao gồm toàn bộ dirty M3/M4. Không reset/stage/commit/push/merge. `validation-summary.json` mới sẽ ghi commands, source hashes, tests, acceptance và limits; manifest cũ không bị sửa.

Browser metrics đo trong Vite dev server mà Owner dùng, warm single page, một browser tab, desktop1280×800, DPR1. Mỗi scale100/1000/5000 đi zoom 11/13/16, mỗi zoom30s; pan nhỏ liên tục, clock chạy fixture10Hz, selected inspector, cluster oracle sau freeze. Đây là render cadence theo requestAnimationFrame, không phải GPU frame presentation profiler hay throughput backend. Zoom cao focus xe để tránh benchmark viewport rỗng. Không chạy M3 stress/pytest/build trong các cửa sổ đo. Browser memory là JS heap khi API có; không thay cho toàn process/GPU/WSL memory. SourceLoadedLag khác snapshot network latency. Cluster oracle chỉ khẳng định phạm vi viewport, zoom 11 còn kiểm full-fleet representation khi thấy đủ fleet.


## 4. Kiểm chứng regression và phạm vi bảo toàn

- Backend command `$env:RUN_REAL_DATA='1'; .\.venv\Scripts\python.exe -m pytest -q`: **189 PASS**, 45,22s, một Starlette/httpx deprecation warning. Không sửa backend engine/jobs/dispatch/modes/Voucher. Real-data opt-in bật; đây là kết quả mới, không phải số189 lấy từ báo cáo cũ.
- Frontend lượt đầu: 162 PASS / 9 FAIL. Tám failures do URL mode do test trước ghi history được giữ sang test tiếp; test setup cũ không reset URL vì navigation trước không dùng pushState. Một assertion cũ chờ bốn items. Đã thêm `beforeEach` về `/`, giữ toàn bộ legacy route/abort/stale assertions, cập nhật assertion năm mode và callback Simulation. Không thay simulation fixtures/outcome assertions.
- Sau sửa: 171 PASS; sau bổ sung ba tests map readiness/cleanup: **174 PASS /19 files**, 10,77s. Các tests mới kiểm chosen5/5/demand payload, stale open-run vs new fixture, history URL compatibility, asset readiness không bị source fleet đang cập nhật làm dao động, asset error và listener cleanup, không ready nếu thiếu năm assets. Không dùng jsdom làm bằng chứng FPS.
- Typecheck, production build, lint exit0. Lint warnings và chunk>500kB là technical debt, không bị che bằng đổi threshold. Số warnings/log hashes ghi trong manifest.
- `npm.cmd run verify:replay --prefix frontend`: packagePASS,9 assets, artifact SHA `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`. Browser file chooser import/export roundtrip vẫn NOT VERIFIED, không dùng package verifier để tuyên bố đã thử chooser.
- `node frontend/scripts/verify-multimodal.mjs`: PASS typed contract/route/lifecycle/graph identity và semantic match giữa **hai files evidence M2 có sẵn**. Script output gọi đối chiếu lịch sử là “independent API rerun”; lệnh này không tự gọi API hiện tại. Báo cáo không coi nó là live M2 pilot mới.
- Browser Saved HCM v1: chuyển qua menu Voucher → Saved → tải mẫu → checksum verified → seek500; hiển thị Baseline1/Treatment2 completed tại t500 và local map. Không gọi OSRM thay geometry của artifact.

Không chạy lại75 domain runs/15 live configs của M3 vì engine/dispatch không đổi. Không sửa graph/profile/manifests, không nâng legacy limits, không thay Saved checksum/contract. Routing identities của small live job ghi trong evidence riêng. Không có M5/M6/M7 code trong nhiệm vụ này.

## 5. Tái lập từ PowerShell

Tại root checkout, kiểm tra services hiện có trước khi chạy. Phiên QA này reuse API8013, worker store `build/m3/jobs`, Vite5183 và ba router5000/5001/5002 do Owner đang chạy; không dừng/restart chúng.

```powershell
Set-Location D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox
.\.venv\Scripts\python.exe --version
node --version
npm.cmd --version
docker version
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8013,5183,5000,5001,5002
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
Get-Item data/regions/nvmr-hanoi-core/render/manifest.json
Get-Item data/regions/nvmr-hanoi-core/routing/car/manifest.json
Get-Item data/regions/nvmr-hanoi-core/routing/motorbike/manifest.json
# Nếu router chưa chạy, dùng graph đã có, KHÔNG preprocess:
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
```

Nếu API/worker/frontend chưa chạy, dùng ba terminal:

```powershell
# Terminal API (root). Không khởi động bản thứ hai nếu8013 đã do phiên Owner giữ.
$env:GSM_SIMULATION_STORE=Join-Path (Get-Location) 'build/m3/jobs'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8013
```

```powershell
# Terminal worker (root), đúng một worker/store:
.\.venv\Scripts\python.exe -m backend.app.simulation_worker --store build/m3/jobs
```

```powershell
# Terminal frontend:
Set-Location D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox\frontend
$env:GSM_API_PROXY='http://127.0.0.1:8013'
npm.cmd run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

Từ URL gốc `http://127.0.0.1:5183/`, click menu Simulation, chờ label5/5 lớp. Có thể zoom/pan trước khi có job. Desktop1280 có menu trái; mobile390 dùng nút mở menu trên header. Điền10 xe/5 CAR/20 requests/online1/seed`m4-ux-pilot`, tạo, chờ COMPLETED, seek100, chọn xe/route. “Mở run đã có” nhận mã run từ progress; không có automatic resume sau reload. Menu quay về legacy không reload trang, nhưng Simulation session unmount và reset clock/selection có chủ đích.

Đo render: mở Developer Tools, chọn fixture 100 → tải fixture → thời lượng30s → đo3zoom. Chờ kết quả trước tăng1000 rồi5000; đảm bảo ≥2GiB available, không chạy tests/build/live stress trong cửa sổ đo. Mỗi case khoảng93s, giữ browserforeground; tự lưuJSON bằng button. Nền trống phải opt-in và output sẽ ghiOFF. Có thể đo một zoom hoặc60s nếu cần soak ngắn hơn3zoom.

```powershell
# Regression tuần tự, không chạy cùng browser benchmark:
$env:RUN_REAL_DATA='1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_REAL_DATA
npm.cmd test --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run typecheck --prefix frontend
npm.cmd run build --prefix frontend
npm.cmd run verify:replay --prefix frontend
node frontend/scripts/verify-multimodal.mjs
```

Dừng bằng Ctrl+C trong terminal của chính services mình khởi động. Giữ nguyên services của người khác. Port conflict: đổi port/proxy hoặc reuse đúng process; không kill để chiếm port. Worker QUEUED lâu: kiểm tra cùng store và terminal, không xóa lock. RESOURCE_STOP: giải phóng RAM rồi tạo run mới; không ép status thành COMPLETED. Assets lỗi: kiểm HTTP `/api/regions/nvmr-hanoi-core/map/streets`, proxyđúng8013, render manifest; nút retry không chạy lại pipeline. Route lỗi: xem graph/profile/ref trong inspector, không thay graph để “chữa” run cũ.

## 6. Acceptance journeys và định nghĩa PASS

| Journey | Thao tác/quan sát thực | Trạng thái/phạm vi |
|---|---|---|
| URL gốc → navigation → Simulation | Tới `/` ở1280×800, thấy GSM brand + menu5modes; click button “Mô phỏng quy mô lớn”, URL được push sang deep link; không nhập query trong journey này; Hanoi streets/water hiện trước job | PASS browser thật |
| Map trước job | Canvas/controls5GeoJSON, readiness5/5, attribution OSM/Geofabrik/ODbL1.0; đã dùng zoom controls và focus/pan trong capture; không cần worker tạo job | PASS |
| Small live job | UI10 fleet,5 CAR,5 MOTORBIKE,20 requests,online1,seed`m4-ux-pilot`; job`2b6e2e4e7d6a41c98360695734d2184a` COMPLETED20/20; seek100, play/pause, chọnGSM-00004CAR/GSM-00008MOTORBIKE, đọc route refs/graph identities; trở lại Single Trip bằng menu | PASS |
| Large live job | Tạo mới quaUI5.000 fleet/2.000 CAR/3.000 MOTORBIKE,1.250 requests,online.8,seed`m4-ux-5000`,typical900s/wait300; job`088a063b0b0d46e1a8241fea277334a9`; QUEUED→RUNNING→COMPLETED; snapshot và route proof lưu riêng | PASS core E2E; playback metric/interaction ghi ở phần performance |
| Legacy navigation | Từ Simulation về HCM Single, Fleet, Booking, Voucher; readiness HCM CAR giữ nguyên, MOTORBIKE HCM disabled; Savedsample checksum/seek500 hoạt động | PASS navigation và Saved playback; không gọi đây là full manual regression của mọi legacy action/export |
| History/reload | Simulation→Single→Back→Simulation→Forward→Single; URL/active mode đúng; reload deep link mount shell thống nhất; simulation display reset có chủ đích, dùng run opener để đọc lại kết quả persisted | PASS |

Small t100 snapshot: total10/offline0/online10/idle6/assigned1/onTrip3/moving4. `GSM-00004` CAR ON_TRIP/BK-000011, route`7ab94a944df557d21a05938dc8c549720834d618043db676e9c8d999779d2afc`,1518m/134,8s; `GSM-00008` MOTORBIKE ON_TRIP/BK-000002,route`6bf4dc9a5eb64140f8410758eeecb288a0dc5d237750ad2ad45d3b44a903ff19`,1468m/145,3s. CAR graph`a24d4957…`,MOTORBIKE graph`fb97489d…`,source/extract identities đúngM2; full hashes trongJSON/screenshot.

Large t100: total5000/offline1000/online4000/idle3861/assigned1/onTrip138/moving139, mix2000/3000; đúng hai đẳng thức accounting. Final counts1250requested/1250assigned/1.250 completed/0 unserved. Worker metrics3765events, peakqueue2501, peakpending1,20000tablecandidates,1250dispatchattempts,0searchbudgetexhaustion; preparation2409,65ms,total11079,53ms (worker timing, không đồng nghĩa enqueue-to-UI end-to-end latency). CAR nearest24/table142/route306,routecachehits170/tablecachehits327,p95router10,734ms; MOTORBIKE nearest24/table180/route410,cachehits379/601,p95router9,053ms; requestfailures0 cả hai. Đây là một fresh seed/config smoke, không thay thế matrix/variance benchmarkM3.

Large selected tạit100: `GSM-00001`CAR ON_TRIP/BK-001194,route`f3574e01d44cf80af44b7e31cfe96448943c37f8bfd5456d41049c7e52b05586`,2132m/213,9s; `GSM-02001`MOTORBIKE ON_TRIP/BK-000549,route`a431e661192d5a2a53e3eddb77fab37d3f180237d013d5f0eb9e68cff34a5357`,2113m/184,5s. Chọn, focus và provenance hiển thị trong browser thật. ProofJSON chỉ giữ summary/snapshot counts/2 vehicles/2 selected routes, không commit wholesnapshot 5.000/history/cache.

Console có một React HMR warning khi thay độ dài dependency array trong lúc page development đang mở. Sau hard reload, normal journeys không tái hiện warning đó. Fault-injection network errors sau đây phải phân biệt với lỗi normal product. Không xóa log hoặc gọi intentional404/503 là console sạch.

## 7. Performance với Hanoi basemap ON — số đo mới

Tất cả rows sau là **HANOI_LOCAL_ON**,8 sources (5basemap +3simulation),15 layers (9basemap +6simulation),0DOM vehicle markers. BrowserChrome155/ANGLE IrisXe/D3D11, i5-11320H4cores/8threads, RAM15,79GiB physical, máy có RTX3050 nhưng WebGL thực chọn IrisXe. Viewport desktop1280×800, mapcanvas764×543, DPR≈1. Vite dev server, worker/routers được reuse; worker idle trong phần playback capture. Không so trực tiếp với canvas920×658/blank-map5s của bàn giao trước.

| Workload | Zoom | Giây đo | RAF FPS | Frame p50/p95 ms | SourceLoaded lag p95 ms | JS heap cuối MiB | Long tasks | setData updates | Vehicles represented trong viewport | Oracle |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 100 fixture | 11 | 30.02 | 59.53 | 16.7/16.9 | 15.9 | 164.0 | 0 | 301 | 100 | PASS |
| 100 fixture | 13 | 30.01 | 59.92 | 16.7/16.9 | 14.0 | 164.2 | 0 | 301 | 19 | PASS |
| 100 fixture | 16 | 30.02 | 60.00 | 16.7/16.9 | 14.0 | 164.0 | 0 | 301 | 1 | PASS |
| 1000 fixture | 11 | 30.01 | 59.29 | 16.7/16.9 | 23.0 | 171.9 | 0 | 301 | 999 | PASS |
| 1000 fixture | 13 | 30.05 | 57.80 | 16.7/17.0 | 43.2 | 268.2 | 0 | 301 | 183 | PASS |
| 1000 fixture | 16 | 30.00 | 59.02 | 16.7/16.9 | 23.8 | 169.2 | 0 | 301 | 2 | PASS |
| 5000 trước tách clock | 11 | 30.04 | 49.86 | 16.7/33.4 | 68.3 | 422.9 | 24 | 301 | 4999 | PASS |
| 5000 trước tách clock | 13 | 30.03 | 48.88 | 16.7/49.9 | 77.5 | 207.5 | 25 | 301 | 949 | PASS |
| 5000 trước tách clock | 16 | 30.07 | 50.75 | 16.7/33.4 | 72.4 | 211.5 | 28 | 300 | 21 | PASS |
| 5000 sau tách clock | 11 | 30.05 | 48.19 | 16.7/49.9 | 71.8 | 255.6 | 58 | 302 | 5000 | PASS |
| 5000 sau tách clock | 13 | 30.01 | 49.32 | 16.7/49.9 | 79.1 | 129.1 | 50 | 301 | 1144 | PASS |
| 5000 sau tách clock | 16 | 30.03 | 54.91 | 16.7/33.3 | 58.0 | 195.4 | 6 | 302 | 21 | PASS |
| 5000 live API | 11 | 30.02 | 56.97 | 16.7/16.9 | 79.9 | 171.5 | 11 | 93 | 5000 | PASS |

Nguồn raw: `fixture-100-basemap.json`, `fixture-1000-basemap.json`, `fixture-5000-basemap.json`, `fixture-5000-tuned-basemap.json`, `live-5000-basemap-benchmark.json`. 100/1000 đo trước phần tách subscription clock;5000 có cả trước/sau trên hai page lifetimes có chủ đích reload. Không giả rằng100/1000 đã đo30s lại sau tối ưu. Các kiểm tra chức năng cuối cùng vẫn chạy trên code sau tối ưu.

### Diễn giải và giới hạn

- 100/1000: render cadence gần60FPS;5.000 fixture10Hz có jank, p95 tới 49,9 ms. Native layers vẫn xử lý đủ input5000 và full-fleet oracle ởzoom 11. Zoom13/16 chỉ phủ viewport, không gọi số1144/21 là mất xe. Full source count5000 được ghi riêng trong diagnostics.
- Sau tách clock, zoom 16 tốt hơn trong lần đo này nhưng zoom 11 không tốt hơn. Đây là before/after một lần, khác page warm state/GC; **không có bằng chứng cải thiện FPS đồng đều hoặc causal attribution**. Tối ưu có ý nghĩa cấu trúc: form/map shell không subscribe30Hz nữa; dock vẫn dùng cùng một clock. Không hạ fixture size, không giảm assertions, không tắt basemap để “đạt PASS”.
- Bottleneck khả nghi là full GeoJSON replacement/worker clustering/GC và workload basemap; đây là inference từ source update lag/long tasks, chưa phải CPU/GPU profiler chứng minh riêng từng phần. setData submission chỉ đo chi phí synchronous submit, không phải toàn bộ indexing/render.
- Live5000 playback:56,97FPS/p95 16,9 ms,93snapshot updates/30,016s≈3,10Hz,sourceLoadedLagp9579,9ms,selection→nextRAF1,5ms,age snapshot cuối147,5ms,11longtasks tổng657ms. Snapshot API/network/validation giới hạn update cadence so với fixture10Hz. Đây là completed-result playback; không worker/router stress đồng thời. Không coi FPS này là throughputM3 hoặc chứng nhận5.000 xe di chuyển cùng lúc.
- JS heap là **cuối capture**, không phải peak browser RAM. Các phép đo warm ngắn vài phút và GC dao động không chứng minh không có memory leak. Không có browser whole-process CPU/RSS/VRAM/p95HTTP-route SLO. Selection→RAF không bao gồm immutable-route network latency. SourceLoadedLag khác end-to-end snapshot network lag.
- Map lifetime `570b6b33-32a7-4618-938f-e8d35bde338c` giữ nguyên qua fixture 100→1000→5000 và chín captures; sau intentional reload để nhận code mới, lifetime `d988d1de-3a3a-4beb-a133-ba5ff09b92ff` giữ nguyên qua tuned5000→freshlive 5.000. Source/layer counts8/15 không tăng. Unit test xác nhận unregister ba health listeners, source component có cleanup listeners/layers/sources; **chưa có heap snapshot/listener leak soak certification**.
- Warm load nămassets sau reload trước tuned capture≈1887,9ms. Lần fixture 5.000 đầu ghi ready milliseconds259518 vì bug global-style readiness đã dao động theo fleet source trước sửa; **không được báo đó là map load4phút**. Sau sửa, readiness chỉ dựa nămgeographic assets +roads layer; fleet updates không làm label dao động. Missingasset404 đã được thử riêng.

## 8. Failure UX và responsive — evidence bổ sung

Fault QA dùng **cùng một browser tab**, Vite5185 → loopbackfaultproxy8014 → API thật8013 choGETassets. Script `scripts/serve_ux_fault_proxy.py` không forwardPOST, không tạo/mutate jobs thật. Control JSON chọn lỗi; response có `ux-fault-injection` ID. Đây là fault-injection UI test, không phải bằng chứng đã tắt process API/router/worker của Owner.

| Case | Quan sát | Trạng thái |
|---|---|---|
| Jobs API unavailable | HTTP503 cho v3; form hiển thị lỗi backend/proxy và hướng dẫn gửi lại; Hanoi map vẫn5/5ready | PASS injection; physical whole-API shutdown NOT VERIFIED |
| Missing map asset | streetsHTTP404; label/overlay chỉ rõ GeoJSON/map error, không READY; không nhầmOSRM | PASS injection |
| Retry assets | chuyển proxy về forwardGET, bấm Tải lại bản đồ; streets trở lại và5/5ready, không cần job | PASS |
| Worker chưa nhận | injectedQUEUED12s; thông báo worker có thể chưa chạy/bận, không heartbeat; map vẫn hiện | PASS UI injection; actual worker process stopped NOT VERIFIED |
| Router/graph unavailable | injectedFAILED/MODE_NOT_READY; thông báo router/graph riêng, map5/5ready | PASS UI injection; physical router outage NOT VERIFIED |
| CANCELLED | injected QUEUED→cancel→CANCELLED; không có result/snapshot | PASS UI injection |
| Real cancellation API | freshjob`788e21058ee0492783c8897bd5f6cfd5`,POSTcancel→CANCELLED,5lần resultHTTP409 | PASS actual API; không tuyên bố browser đã tự tạo và hủy cùng realjob này |
| INTERRUPTED | injectedINTERRUPTED có nhãn Bị gián đoạn, không có finalKPI | PASS UI injection; real process hard-crash NOT VERIFIED |
| Stale result/open/seek/cancel | hooktests deferred oldresponse vs fixture/reset/cancel, duplicate/stale snapshots validators; browser đổi mode/run không còn selectedID cũ | PASS tested scope; không network chaos/soak |
| Reload/Back/Forward | đúngmode/query/active menu, run opener đọc lại persistedjob | PASS browser |
| Mobile390×844 | root→menu sheet→Simulation; canvas373×358,pageWidth390; pan/zoom trướcjob; mởrealrun 5.000,seek100/focusMOTORBIKE;1canvas | PASS responsive smoke; chưa mobile performance benchmark |
| Desktop1280×800 | nav/control/map,inspector,playback nativeclusters và routes | PASS |

Raw `.txt` DOM snapshots và screenshots giữ trong evidence cho từng fault. Intentional404/503 có console errors, lưu `failure-console.json`; `normal-console.json` trong normalfinalbrowsercapture là[] saureload. Browserchooserimport/export, prolongedGPUcontext-loss/recovery và fullsystemofflinenocache NOT VERIFIED.

### Tái lập fault QA mà không tắt services Owner

```powershell
# Root, terminal QAproxy. Chỉ sử dụng cho browser fault UX, không đo performance.
New-Item -ItemType Directory -Force build/m4-ux | Out-Null
'{"mode":"api-unavailable"}' | Set-Content -Encoding utf8 build/m4-ux/fault.json
.\.venv\Scripts\python.exe scripts/serve_ux_fault_proxy.py --port 8014 --target-port 8013
```

```powershell
# Terminal ViteQA riêng:
Set-Location D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox\frontend
$env:GSM_API_PROXY='http://127.0.0.1:8014'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5185 --strictPort
```

Mở5185?runtime=simulation trong cùngtab, clickTạo mô phỏng để xem503. ĐổiJSONmode=`asset-missing` rồireload để xem404;mode=`queued` +Tải lại bản đồ khôi phụcassets;clickTạo mô phỏng,chờ>10s;Hủyjob→CANCELLED. mode=`router-unavailable`/`interrupted` +Tạo mô phỏng cho hai states còn lại. Các response đều synthetic/injection, không xuất scientific results. Ctrl+C đúng hai terminal QA khi xong. Phiên này đã dừng đúng QAproxy13580/QAfrontend28764;8013/5183 và routers5000/5001/5002 của Owner vẫn listening.

## 9. Laptop16GB và điều phối tải

Ban đầu ngừng tăng tải vì RAM khả dụng~0,85–1,2GiB, chờ Owner giải phóng tab/apps. Không tự kill user processes. Sau đó tăng100→1000→5000, tất cả headroomwindow ≥2GiB. Không preprocess/OSMextract/graphcopy; reuse baOSRMcontainers. Docker routerRSS snapshots HCM25,54MiB/HanoiCAR41,36MiB/MOTORBIKE61,18MiB lúc100; không bằng DockerDesktop/WSL tổngRAM. Hardware đầy đủ trong `resource-*.json`.

| Capture window | Min availableGiB (sampler200ms) | Ý nghĩa |
|---|---:|---|
| fixture-100 | 4.399 | system available RAM; sampler RSS/CPU không phải browser RSS/CPU |
| fixture-1000 | 3.899 | system available RAM; sampler RSS/CPU không phải browser RSS/CPU |
| fixture-5000 | 3.467 | system available RAM; sampler RSS/CPU không phải browser RSS/CPU |
| fixture-5000-tuned | 3.930 | system available RAM; sampler RSS/CPU không phải browser RSS/CPU |
| live-5000 | 4.274 | system available RAM; sampler RSS/CPU không phải browser RSS/CPU |

Không có mức fleet bị resource-stop trong lượt benchmark mới. Initial Owner jobs resource-stop là lịch sử trước sửa. Không gộp benchmarkdomain/liveM3 cũ với browserbasemapmới. Có một đoạn regression orchestration đầu để frontend lint/build bắt đầu trong khi PTY backend vẫn pending; đây là overlap ngoài các cửa sổ benchmark, không lấy số tài nguyên từ đoạn này làm chuẩn. Các lượt frontenddeliverychecks sau đó chạy tuần tự, mọi cửa sổ browser performance không có fulltests/build/M3stress. Không tuyên bố tuân thủ tuyệt đối no-overlap ở checkpoint regression đầu.

## 10. GO/NO-GO và blockers còn lại

| Phạm vi | Quyết định | Evidence | Blockers / bước tiếp |
|---|---|---|---|
| M3 backend readiness | GO cho small/workload 5.000 đã kiểm; CONDITIONAL GO rộng |189tests,fresh5000/1250,cancel409,TScontract;engineunchanged|liveoracle/multiseed/retention/quota/journal/soak vẫn là việcM3 cũ |
| M4 visualization | GO MVP local ở setup đo; CONDITIONAL GO tuyên bố5.000 UI mượt ổn định |realbasemap100/1000/5000,0DOM,cluster oracle,inspector,mobile|fixture 5.000p95≈50ms,longtasks,không soak/đaGPU,whole-process memory chưa đo |
| M3/M4 product integration | GO nghiệm thu luồng MVP local đã thử |rootnavigation,bản đồ Hà Nội trước job,fresh10và5000,play/seek/select/focus/back/Saved|không worker heartbeat/automaticrunresume;assetscầnAPI;physicaloutage/crash cònNOT VERIFIED |
| M5 bắt đầu pilot | GO phát triển pilot5–10 xe |M2 rerun20/20,routing mode identity,lifecycle/Voucherlegacyprotected|chưa xâychoiceNO_BOOK/CAR/MOTORBIKE;phảipinassumptions,pairedinputs,zero-policycontrols;không được gọi là M5 hoàn thành |
| Production | NO-GO |chỉsingle-hostresearchMVP|auth,quotas,retention,supervision,backup/recovery,soak/security/observability chưađủ |

P0 trong phạm vi báo cáo trống/navigation: đã sửa và browser xác nhận. P1: tối ưu native source/indexing/React/GC với profiler, lấy latencypercentiles và soak30–60phút trênbasemap;workerhealth/queued diagnosis chính xác hơn;testcrash/outage khiOwner cho môi trường riêng. P2: lint/chunks, co-locatedvehiclepicking/inspectorsearch (hiện chọn ID chính xác, click tại anchorchồngnhiềuxe chỉ chọn topfeature), thêm điều kiện thiết bị/mobileperformance. Không cần cản M5 pilot nhỏ vì chưa có chứng nhận5.000 xe di chuyển; không triển khaiM5trongtasknày.

## 11. Bổ sung cuối và Git handoff

M2 live rerun mới: gọi `scripts.multimodal_pilot.run(write=False)` thực tế, PASS20 completed/0 unserved; không ghi đèM2 evidence. Kết quả trong `m2-live-rerun.json`. TS validator kiểm live job5000 qua HTTP: PASS duplicate/stale snapshot rejection, mode/route identities và summary không có history; `live-5000-contract.json`. Browser sau đó đã mở realCANCELLED mới và realFAILED resource-guard có sẵn: hai trạng thái rõ, không còn selection/KPI của run trước; `real-cancelled-ui.txt`/`real-failed-ui.txt`. FAILED cũ không tính là job được tạo bởi lượt này.

Đã click nativecluster 813 xe trên map → zoommởrộng → individualpoints, clickCAR `GSM-00925` mở inspectorIDLE không có route; sau đó seek100/chọnCAR đang chạy cho selectedimmutable route. Xe chung depot có overlap; không giả5.000 anchors khác nhau.

Bổ sung UI cuối sau các captures dài chỉ đổi nhãn errorfooter và thêm disclosure **Cấu hình run và seed đã lưu** (đọc immutablejob config hiện có), đổi form label thành **Thiết lập mô phỏng mới** để tránh nhầm config của run đã mở. Không đổi engine/render cadence/geometry. Frontenddeliverytests174 PASS/19 files10,28 s, lint33 warnings / 0 errors, typecheck/buildexit0 được chạy sau hai thay đổi này. Browser đã mở disclosure và xác nhận seed`m4-ux-5000`/fleet5000/car2000/requests1250, khác form khởi tạo mới100xe có chủ đích. Metrics dài không được gọi là phép đo lại sau hai nhãn/disclosure này; native rendering/kích thước map không thay.

### Phân loại diff

- **Đã có trước task:** toàn bộM3 backend/scripts/tests/fixtures/M2 report/M3 report và19 filesm3-m4-evidence; M4 modules/contracts/tests/entrypoint/CSS cùngREADME đã dirty/untracked. Không ghi đè bằng GitHub/main, không tạo worktree mới, không commitđểtíchhợp.
- **Sửa thêm trên files đã có:** README,App.tsx,App.css,PrimaryNavigation,simulation-workspace,simulation-map,use-simulation,simulation.ts(typeoptionaljob config),use-simulation.test,frontendtestsetup/workspace.test,M4 report/integrationreview.
- **Files source/test mới:** navigation.ts,simulation-map-health.tsx,navigation.test.ts,simulation-map-health.test.tsx,serve_ux_fault_proxy.py. ReportM4_UX và namespaceevidence mới.
- **Bảo toàn:** hash28 inherited backend/tests/M2 report/M3 report/historical evidence khớp task-start copy; trackedM2/Voucher/modes/profiles/config/contracts/m2-evidence không có diff. Không có stagedfile. Nguồn task-start copies và beforemanifest ở ignored `build/m4-ux/before/`; những file sạch lúc đầu kiểm bằng HEAD làm baseline.
- **Không stage:** `build/`,`.replay-tools/`,`frontend/dist/`,`node_modules/`,`.env`,GIS/PBF/OSRMgraphs/cache,`.agents/`,user-owned/unrelated files. Không dùng `git add .` hay `git add -A`.

`git diff --stat` chỉ đếm trackedfiles, không bao gồm các modules/evidence chưa track. VìM3/M4 chưa commit, staging lệnh dưới lấy **toàn bộ feature đã tích hợp**, không chỉ deltaUX. Owner cần review cả nguồn cũ và mới. Không thể stage riêng dòngUX trong untrackedwholemodule mà có một commitUX độc lập build được; đề xuất commitM4 hiện tại gộp implementation+remediation sauM3. Không cần checkout/commit trong worktrees cũ.

Trước staging, kiểm lại:

```powershell
git status --short
git diff --stat
git diff --check
git ls-files --others --exclude-standard
git diff --cached --name-only
```

Allowlist đọc máy được tại `m4-ux-evidence/git-allowlists.json`, từng path dưới đây là file thật sau bàn giao. Các lệnh **chỉ đề xuất**, Codex chưa chạy staging/commit. Sau mỗi `git add`, xem đầy đủ cacheddiff trước tự commit; không thực hiện cả bốn block mù quáng.

### Commit M2 — 1 files

```powershell
$m2Files = @(
  'docs/nvmr/M2_IMPLEMENTATION.md'
)
git add -- $m2Files
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached
git commit -m "docs(nvmr): complete M2 implementation report"
```

### Commit M3 — 12 files

```powershell
$m3Files = @(
  'backend/app/main.py'
  'backend/app/simulation.py'
  'backend/app/simulation_jobs.py'
  'backend/app/simulation_worker.py'
  'scripts/benchmark_simulation.py'
  'scripts/benchmark_simulation_live.py'
  'scripts/m3_fixture_travel.py'
  'scripts/m3_resources.py'
  'tests/test_m3.py'
  'tests/fixtures/m3/legacy-golden.json'
  'tests/fixtures/m3/travel-matrix.json'
  'docs/nvmr/M3_IMPLEMENTATION.md'
)
git add -- $m3Files
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached
git commit -m "feat(nvmr): implement scalable simulation engine"
```

### Commit M4 — 17 files

```powershell
$m4Files = @(
  'frontend/src/App.tsx'
  'frontend/src/App.css'
  'frontend/src/components/simulation-map.tsx'
  'frontend/src/components/simulation-workspace.tsx'
  'frontend/src/lib/simulation.ts'
  'frontend/src/lib/use-simulation.ts'
  'frontend/tests/simulation.test.ts'
  'frontend/tests/use-simulation.test.ts'
  'docs/nvmr/M4_IMPLEMENTATION.md'
  'frontend/src/components/primary-navigation.tsx'
  'frontend/src/components/simulation-map-health.tsx'
  'frontend/src/lib/navigation.ts'
  'frontend/src/test-setup.ts'
  'frontend/tests/navigation.test.ts'
  'frontend/tests/simulation-map-health.test.tsx'
  'frontend/tests/workspace.test.tsx'
  'docs/nvmr/M4_UX_REMEDIATION.md'
)
git add -- $m4Files
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached
git commit -m "feat(nvmr): integrate scalable simulation into GSM navigation"
```

### Commit integration — 69 files

```powershell
$integrationFiles = @(
  'README.md'
  'scripts/validate_simulation_api.py'
  'frontend/scripts/verify-simulation.mjs'
  'docs/nvmr/M3_M4_INTEGRATION_REVIEW.md'
  'docs/nvmr/m3-m4-evidence/api-integration.json'
  'docs/nvmr/m3-m4-evidence/browser-benchmark.json'
  'docs/nvmr/m3-m4-evidence/browser-initial-invalid.json'
  'docs/nvmr/m3-m4-evidence/browser-integrated-5000.json'
  'docs/nvmr/m3-m4-evidence/browser-live-100-summary.json'
  'docs/nvmr/m3-m4-evidence/browser-live-5000-job.json'
  'docs/nvmr/m3-m4-evidence/browser-live-5000-summary.json'
  'docs/nvmr/m3-m4-evidence/clusters-5000.jpg'
  'docs/nvmr/m3-m4-evidence/contract-verification-5000.json'
  'docs/nvmr/m3-m4-evidence/contract-verification.json'
  'docs/nvmr/m3-m4-evidence/domain-summary.json'
  'docs/nvmr/m3-m4-evidence/hanoi-car-voucher-regression.json'
  'docs/nvmr/m3-m4-evidence/integration-summary.json'
  'docs/nvmr/m3-m4-evidence/live-car-5000.jpg'
  'docs/nvmr/m3-m4-evidence/live-motorbike-inspector.jpg'
  'docs/nvmr/m3-m4-evidence/live-summary.json'
  'docs/nvmr/m3-m4-evidence/native-inspector-5000.jpg'
  'docs/nvmr/m3-m4-evidence/saved-api-off.jpg'
  'docs/nvmr/m3-m4-evidence/validation-summary.json'
  'scripts/serve_ux_fault_proxy.py'
  'docs/nvmr/m4-ux-evidence/before-basemap-enabled.jpg'
  'docs/nvmr/m4-ux-evidence/before-blank.jpg'
  'docs/nvmr/m4-ux-evidence/failure-api.jpg'
  'docs/nvmr/m4-ux-evidence/failure-api.txt'
  'docs/nvmr/m4-ux-evidence/failure-cancelled.txt'
  'docs/nvmr/m4-ux-evidence/failure-console.json'
  'docs/nvmr/m4-ux-evidence/failure-interrupted.txt'
  'docs/nvmr/m4-ux-evidence/failure-map-asset.jpg'
  'docs/nvmr/m4-ux-evidence/failure-map-asset.txt'
  'docs/nvmr/m4-ux-evidence/failure-queued.txt'
  'docs/nvmr/m4-ux-evidence/failure-router.txt'
  'docs/nvmr/m4-ux-evidence/fixture-100-basemap.json'
  'docs/nvmr/m4-ux-evidence/fixture-1000-basemap.json'
  'docs/nvmr/m4-ux-evidence/fixture-5000-basemap.jpg'
  'docs/nvmr/m4-ux-evidence/fixture-5000-basemap.json'
  'docs/nvmr/m4-ux-evidence/fixture-5000-tuned-basemap.json'
  'docs/nvmr/m4-ux-evidence/hanoi-m2-navigation.txt'
  'docs/nvmr/m4-ux-evidence/live-5000-basemap-benchmark.json'
  'docs/nvmr/m4-ux-evidence/live-5000-car.jpg'
  'docs/nvmr/m4-ux-evidence/live-5000-contract.json'
  'docs/nvmr/m4-ux-evidence/live-5000-job.json'
  'docs/nvmr/m4-ux-evidence/live-5000-motorbike.jpg'
  'docs/nvmr/m4-ux-evidence/live-5000-proof.json'
  'docs/nvmr/m4-ux-evidence/m2-live-rerun.json'
  'docs/nvmr/m4-ux-evidence/mobile-390.jpg'
  'docs/nvmr/m4-ux-evidence/mobile-layout.json'
  'docs/nvmr/m4-ux-evidence/mobile-run-open.txt'
  'docs/nvmr/m4-ux-evidence/navigation-default-map.jpg'
  'docs/nvmr/m4-ux-evidence/normal-console.json'
  'docs/nvmr/m4-ux-evidence/product-final.jpg'
  'docs/nvmr/m4-ux-evidence/real-cancellation.json'
  'docs/nvmr/m4-ux-evidence/real-cancelled-ui.txt'
  'docs/nvmr/m4-ux-evidence/real-failed-ui.txt'
  'docs/nvmr/m4-ux-evidence/resource-fixture-100.json'
  'docs/nvmr/m4-ux-evidence/resource-fixture-1000.json'
  'docs/nvmr/m4-ux-evidence/resource-fixture-5000-tuned.json'
  'docs/nvmr/m4-ux-evidence/resource-fixture-5000.json'
  'docs/nvmr/m4-ux-evidence/resource-live-5000.json'
  'docs/nvmr/m4-ux-evidence/saved-regression.jpg'
  'docs/nvmr/m4-ux-evidence/small-car-route.jpg'
  'docs/nvmr/m4-ux-evidence/small-motorbike-route.jpg'
  'docs/nvmr/m4-ux-evidence/small-result.json'
  'docs/nvmr/m4-ux-evidence/small-snapshot.json'
  'docs/nvmr/m4-ux-evidence/git-allowlists.json'
  'docs/nvmr/m4-ux-evidence/validation-summary.json'
)
git add -- $integrationFiles
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached
git commit -m "test(nvmr): validate Hanoi basemap UX and simulation integration"
```

ReviewerM3: determinism/lifecycle/cancel/store/shortlist budget, không coi heuristic làglobalminimumETA. ReviewerM4: rootnavigation/Hà Nội mặc định/clock cleanup/out-of-order isolation, source updates và điều kiện ON/OFF, realvsinjectedfailures. Reviewerintegration: evidence seed/graph identity, metricwindows, chưatestsoak/physicaloutage và Owner services còn nguyên. Chưa có commit/push/merge do Codex thực hiện.

### Lifecycle smoke sau cùng

Trên code cuối, bật nền trống qua checkbox Developer Tools có chủ đích rồi đo5s:3 sources / 7 layers. Bỏ checkbox và đo5s: Hanoi 5/5 ready,8 sources / 15 layers. Cùng map lifetime `9a794e24-4594-43ea-b36d-8d433ab511f0`, cluster oraclePASS cả hai,0 DOM markers. Raw hai captures nằm trong `live-5000-proof.json.advancedBasemapLifecycleSmoke`. Chỉ dùng để kiểm style-switch/source cleanup/harness giữ hoạt động; không thay cho bảng performance30s. Sau smoke đã khôi phục basemap ON, đóng Developer Tools, seek100/chọnCAR và lưu lại `product-final.jpg`. Viewport override đã reset; tab sản phẩm giữ mở cho Owner. Không còn QAproxy/frontend phụ.
