# M3 — Scalable Simulation implementation

Ngày thực hiện: 17/10/2026. M3 là đường API/engine **v3 riêng**, tích hợp với M4 qua snapshot v1; không nới giới hạn Saved Replay/Booking/Voucher v1 hay sửa behavior/ledger Voucher. CAR/MOTORBIKE tiếp tục sử dụng profile/graph M2 riêng. Demand và benchmark là dữ liệu tổng hợp nghiên cứu; OSRM ETA là ước lượng mô hình tĩnh.

## Phạm vi và trạng thái bằng chứng

Đã triển khai engine heap, index idle theo mode/grid, bounded spatial shortlist, online schedules, worker process riêng, atomic local store, job API, final playback snapshots và route store theo reference. Không có Redis/Kafka/database/cluster. Không có streaming snapshot trong lúc worker chạy: frontend đọc playback **sau khi COMPLETED**.

Kết quả focused tests tại worktree M3: `tests/test_m3.py`: **25 PASS**, 2.33 s ở lần chạy cuối trước tích hợp. Đây là fixture tests, không chứng minh routing thật hay khả năng 5.000 xe. Kết quả full suite và benchmark tại checkout tích hợp phải đọc bảng kết quả bên dưới và integration review; số M2 lịch sử 164/159 không được dùng thay cho lần chạy hiện tại.

## Kiến trúc

| Module | Trách nhiệm |
|---|---|
| `backend/app/simulation.py` | Pydantic immutable inputs, hash-counter demand, repeated depot anchors, event heap, spatial grid, route-reference storage, timeline projection, independent lifecycle audit |
| `backend/app/simulation_jobs.py` | Bounded queue, cross-process advisory lock, atomic JSON writes, statuses/cancellation/final publication, final result/snapshot/selected-route API |
| `backend/app/simulation_worker.py` | CLI process ownership lock, interrupted-run recovery, mode readiness, nearest/Table/Route adapter, graph identity checks, bounded caches, telemetry |
| `backend/app/main.py` | Register v3 router, v3-specific validation errors; old endpoints unchanged |
| `scripts/benchmark_simulation.py` | Sequential domain-only workload matrix, five seeds, RAM guard, correctness checks, sampled exhaustive oracle |
| `scripts/benchmark_simulation_live.py` | Separate live local OSRM benchmark; prepared input/full result stay ignored |
| `scripts/m3_fixture_travel.py`, `m3_resources.py` | Explicit recorded fixture adapter; stdlib Windows/Linux memory/CPU sampling |
| `tests/test_m3.py`, `tests/fixtures/m3/*` | Lifecycle/boundary/determinism/jobs/cancel/process lock tests, frozen legacy golden and directed ring matrix |

`booking.py`, `voucher.py`, `multimodal.py`, `modes.py`, v1 schemas/limits và graph manifests không bị sửa bởi M3. Frontend M4 và reports được tích hợp tại main checkout; Git worktrees không chứa bản sao GIS.

## Immutable inputs và service model

`SimulationConfig` v3: `regionId=nvmr-hanoi-core`, seed string, fleet 1–5.000, `carCount<=fleetSize`, bookings 0–20.000, request horizon 1–86.400 s, pickup wait 0–3.600 s. `onlineFraction` 0–1; `onlineSchedule:[{timeSeconds,onlineFraction}]` sorted/unique/within horizon. Config cấm unknown fields, URL/router/path từ client, NaN/Infinity và integer bool.

CAR được tạo trước, sau đó MOTORBIKE, ID `GSM-00001` ổn định. Có thể đặt nhiều xe tại cùng verified depot/anchor; số anchor không giới hạn tổng fleet. Tỷ lệ online chính xác theo từng mode bằng `round(modeCount*fraction)`. Lịch online/offline dùng cùng offset identity theo mode. Ví dụ 5.000 xe gồm 2.000 CAR + 3.000 MOTORBIKE, online .5 = 2.500 online; schedule .8 = 4.000 desired online.

Hash-counter demand `m3-demand/v1` độc lập dispatch outcomes/response order. Request service type rõ; chỉ cùng vehicle type được xem xét, không substitution. Các request đến trong horizon; engine **drain** toàn bộ accepted requests và trips, nên kết thúc có thể sau horizon. `counts.completed/unserved` là final outcomes; không phải KPI ở playback time.

Config được hash và lưu immutable `input.json` tại enqueue. Khi worker bắt đầu, mode readiness/graph identity được kiểm tra, initial vehicle anchors nearest theo mode (deduplicate bằng mode+coordinate), exogenous fleet/demand và routing identities được lưu `prepared-input.json`. Queue chưa pin graph tại thời điểm HTTP POST: routing inputs được pin ở **worker preparation**, được nêu rõ để tránh nhầm immutable config với queued graph snapshot. Chưa hỗ trợ submit arbitrary saved prepared inputs qua HTTP.

## Event ordering, FIFO và lifecycle

Heap chứa `(simulationTime,priority,identity,counter,eventKind)`; chỉ xử lý các events tới hạn, không tìm `min` trên toàn history và không scan toàn bộ assignment/demand ở mỗi timestamp. Routing concurrency = 1 trong worker. Thứ tự HTTP/OSRM/wall-clock không được dùng để quyết định dispatch.

Same timestamp: completions → online/offline schedules → new requests → pickup transitions → FIFO dispatch → inclusive expiration. Stationary zero pickup emits arrived/start atomically sau assignment. Identity tie-break ổn định; thứ tự append event là execution order v3. v1 serializer vẫn có `EVENT_ORDER` riêng, không bị đổi để nhét v3 vào artifacts cũ.

Pending FIFO theo `(requestTimeSeconds,bookingId)`: xét booking cũ trước, booking chưa feasible không khóa mọi booking trẻ hơn, tương tự legacy policy. Retry xảy ra khi arrival/release/online/deadline thay đổi relevant mode. Không scan history để tính progress; terminal counter incremental. Event queue/peak pending/dispatch attempts và table candidates được ghi.

State model:

```text
TOTAL = OFFLINE + ONLINE
ONLINE = IDLE + ASSIGNED + ON_TRIP
OFFLINE -> IDLE (schedule online)
IDLE -> ASSIGNED (full pickup route confirmed)
ASSIGNED -> ON_TRIP (arrival at pickup)
ON_TRIP -> IDLE hoặc OFFLINE (completion, theo desired schedule)
```

Busy shift ending không bỏ hành khách: desired OFFLINE được deferred đến completion. ON_TRIP không đồng nghĩa moving: moving chỉ gồm active nonstationary pickup/trip legs. Null pickup reference chỉ khi xe đã ở validated trip pickup (<0.1 m). Pickup route phải khớp previous idle position và trip endpoint trong tolerance 1 m. Actual full-route pickup đến không muộn hơn `request+maxWait` (inclusive). Không double assignment/cross-mode/overlap. Failures giữ reason riêng; route outage/bad response làm job FAILED, không fake geometry.

Independent `validate_result` kiểm tra linear indexed assignment consumption từ IDLE, previous position/stationary pickup, route identity/continuity/times, no overlap, mode, complete booking lifecycle, unserved deadline/reason và final KPI conservation. Benchmark kiểm tra thêm snapshot accounting tại 5 checkpoints. Đây không phải formal verification cho mọi possible input.

## Spatial dispatch

`IdleGrid` chỉ index ONLINE+IDLE, partition CAR/MOTORBIKE. Occupied cells xếp theo lower-bound squared distance của cell bbox; IDs trong cell stable sorted, lấy hữu hạn candidates. Khi nhiều xe cùng depot, không sort toàn bộ fleet mỗi booking. Sampling bên trong một cell bị bounded và thiên về stable IDs: đây là heuristic, **không bảo đảm nearest coordinate hay global minimum ETA**.

Policy `grid-fifo/v1`: cell .005 degree, batch đầu 16, mở rộng gấp đôi, tối đa tổng 128 examined vehicles/attempt (config cho phép bound khác tới 512). OSRM Table chỉ cho batch; rank bằng ETA, vehicle ID tie-break. Full pickup Route xác nhận trước assignment; không dùng distance làm ETA. Trip Route được xác minh trước. Nếu batch không feasible/NoTable thì mở rộng. Mỗi lần tìm thấy feasible full route dừng ở expansion đó, không mở rộng để tìm global winner.

Nếu còn idle candidates chưa examined khi budget hết, failure là `SEARCH_BUDGET_EXHAUSTED`, không đổi thành NO_VEHICLE/NO_ROUTE. Nếu toàn candidate được xét không có reachable ETA thì NO_ROUTE; nếu ETA/full-route đến trễ thì PICKUP_WAIT_LIMIT; nếu không có online idle thì NO_ONLINE_IDLE_VEHICLE. Các failure code từ validated trip route được giữ ở unserved deadline. Infrastructure failures 5xx làm FAILED toàn job.

Oracle benchmark dùng default 16/128 trên static selected sample 100 vehicles/40 bookings, so Table ETA với exhaustive compatible online idle set. Ghi winner recall, feasible candidate miss, ETA regret, Table points/queries riêng. Đồng thời chạy hai full small scenarios với shortlist và exhaustive để đếm service outcome differences. Giảm số **Table points** không tự đồng nghĩa giảm số HTTP queries: expansion có thể cần nhiều queries hơn exhaustive single Table. Oracle là fixture evidence; chưa phải quality chứng minh cho mọi live OSM case.

## Worker/jobs/store và cancellation

Single-host, một worker process cho một store; queue tối đa 8 QUEUED+RUNNING. API không spawn worker ngầm. CLI giữ `.worker.lock` bằng OS advisory lock; crash tự release, không dựa stale PID file. `.store.lock` bảo vệ create/claim/cancel/progress/final publication giữa API và worker processes.

Statuses: QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED. Worker restart chuyển abandoned RUNNING sang INTERRUPTED; phải tạo job mới để rerun, **chưa resume checkpoint**. Cancel queued/running là terminal; progress chỉ tăng khi RUNNING. Kết quả late không resurrect cancelled job. Cancel completed giữ completed immutable; không xóa historical final output.

JSON writes sử dụng temporary file + flush/fsync + atomic replace. COMPLETED chỉ được publish sau `event-log.json` và `result.json` đã ghi xong trong store transaction. GET result/snapshot/route chỉ chấp nhận COMPLETED; không expose partial như final. Event log durable khi hoàn tất; chưa flush từng domain event trong lúc chạy. Interrupted run có prepared-input và status/error, chưa có đầy đủ in-progress event journal. Progress disk write throttle .25 s, cancellation kiểm tra mỗi tick/dispatch/nearest; đang chờ HTTP phải đợi bounded router timeout.

Store mặc định `build/m3/jobs`, override bằng `GSM_SIMULATION_STORE`; API và worker phải trỏ cùng absolute directory. Paths IDs cấm traversal, job ID 32 lowercase hex. Route IDs opaque immutable/run-scoped, lookup chỉ trong final run. Local store dùng trusted host filesystem, chưa có auth/quota/retention daemon; chưa phù hợp public multi-user deployment.

## API và snapshot contract

| Method/path | Kết quả |
|---|---|
| `POST /api/v3/simulation/jobs` | 202, validated config, queued job ID/status/progress |
| `GET /api/v3/simulation/jobs/{id}` | Status/progress/error; completed summary |
| `POST /api/v3/simulation/jobs/{id}/cancel` | Terminal cancellation hoặc existing terminal status |
| `GET /api/v3/simulation/jobs/{id}/result?summary=true` | Final metadata/KPI/config/identities, không tải toàn history/routes |
| `GET /api/v3/simulation/jobs/{id}/result` | Complete final result; chỉ dùng khi thật sự cần export/debug |
| `GET /api/v3/simulation/jobs/{id}/snapshot?timeSeconds=...` | Authoritative final-run playback projection |
| `GET /api/v3/simulation/jobs/{id}/routes/{routeRef}` | Selected route envelope, graph identity gốc; không re-route |

Snapshot `gsm-simulation-snapshot/v1`: runId=job.id, regionId, sequenceNumber, simulationTimeSeconds, routingIdentities, counts(total/offline/online/idle/assigned/onTrip/moving), vehicles(id/type/state/[lon,lat]/heading/activeBookingId/routeRef). Không có geometry trong mỗi vehicle snapshot. Sequence `floor(simulationTimeSeconds*1e6)` ổn định khi poll lại, có microsecond quantization; frontend seek/reset mở projection session mới để nhận lower sequence. Time clamp vào final simulation duration.

Route envelope `gsm-simulation-route/v1` có run/region/ref/routingIdentity/coordinates/distance/duration. Cumulative distance index chỉ lưu nội bộ. Snapshot projection bisect timeline mỗi vehicle, bisect route segment, không quét toàn event history theo frame. API giữ tối đa một result parsed cache/process có lock, tránh cross-run concurrent cache race. Frontend vẫn phải giữ run/region isolation, xem M4 report.

## Resource policy và reproducibility

Không rebuild/copy PBF hoặc graph; live worker chỉ dùng validated artifacts ở checkout tích hợp. Instrumented LocalTravel dùng shared HTTP client và route/Table caches bounded 2.048 entries/mode; clear cache khi chạm cap. Worker preflight yêu cầu 2 GiB physical RAM available. Benchmarks chạy serial, kiểm tra RAM trước từng case và dừng tăng tải nếu minimum sampled headroom dưới guard. Không kill user processes/containers. Chưa có memory reservation/hard OS cgroup limit.

Raw benchmark files nằm `build/m3` đã Git-ignore. Chỉ commit summary nhỏ khi đã kiểm tra. Domain fixture có SHA-256 identity và matrices cố định trong `tests/fixtures/m3/travel-matrix.json`: 32-node directed ring, CAR edges 20/25 s, MOTORBIKE 14/19 s; geometry 2-point synthetic fixture. Không phải OSM/OSRM traffic, không dùng làm runtime fallback.

Telemetry: wall/CPU seconds, CPU percent một core, sampled process RSS mỗi .05 s, process peak RSS từ OS, minimum available physical RAM, event throughput/booking throughput/simulated seconds per wall-second, queue peaks, routing operations. OS peak RSS là lifetime process high-water; sampled per-run peak có thể bỏ lỡ very short transient. Domain wall bao gồm input generation, core, validation, snapshots và semantic serialization. Metadata ghi platform/CPU/GPU/Python/Docker stats trước/sau; Docker memory không được cộng thành worker RSS.

Workloads: low = online .25, bookings .02×fleet; typical = .8/.25×fleet; burst = .6/1×fleet, arrival trong 5% request horizon; horizon900 s, wait300 s. Mỗi cấu hình 5 independent seeds. Đây là scaled demand workload, chưa phải exhaustive mọi demand/fleet/online distribution. Không suy domain throughput thành live OSRM throughput.

## Kết quả benchmark và regression tại checkout tích hợp

Thực chạy 17/10/2026 trên i5-11320H (4 cores/8 logical), Windows 11, 16 GB, Python 3.11.9. Domain 75 runs (5 seeds/config); live 15 runs (1 seed/config), routers đang chạy được reuse. Python hash/travel caches mới mỗi live process; không coi đó là OSRM cold start. Không chạy browser stress đồng thời. [Domain raw summary](m3-m4-evidence/domain-summary.json), [live summary](m3-m4-evidence/live-summary.json).

| Fleet (CAR/MOTORBIKE) | Domain median s: low / typical / burst (5 seeds) | Live s: low / typical / burst (1 seed) | Live completed/requested burst | Correctness |
|---|---|---|---|---|
| 100 (40/60) | 0.0046 / 0.0099 / 0.0351 | 2.054 / 2.349 / 4.436 | 92/100 | PASS |
| 500 (200/300) | 0.0137 / 0.0458 / 0.1262 | 2.154 / 3.620 / 12.481 | 497/500 | PASS |
| 1000 (400/600) | 0.0315 / 0.0854 / 0.2598 | 2.702 / 5.058 / 18.994 | 1000/1000 | PASS |
| 3000 (1200/1800) | 0.0901 / 0.2486 / 0.8487 | 2.914 / 8.620 / 33.099 | 3000/3000 | PASS |
| 5000 (2000/3000) | 0.1710 / 0.4839 / 1.5438 | 3.453 / 10.214 / 38.360 | 5000/5000 | PASS |

PASS ở bảng là lifecycle/accounting tại năm checkpoints và final audit, không phải mọi request đều được phục vụ hoặc production SLO. Low/typical/burst booking counts theo tỷ lệ đã nêu: 5000 fleet tương ứng 100/1250/5000 requests; online 25%/80%/60%. Live 100 burst có 8 unserved, 500 burst có 3 unserved; các cấu hình còn lại hoàn tất mọi request. Không ép outcomes. Chưa chạy fixed-demand rate series, 100% online stress, live multi-seed variance hoặc live exhaustive oracle.

Domain peak process lifetime RSS 138,60 MiB, minimum available RAM 3,579 GiB. 5000 burst: 5000 completed, 1,493–1,674 s, worst throughput 2986,6 bookings/s (bao gồm generation/audit/projection/serialization; fixture không phải OSRM). Events/s, CPU, queue peaks và realtime factor từng run có trong JSON. Tất cả domain configs vượt realtime factor 1 trong workload đã đo.

Live 5000 burst: 38,360 s wall, 33,00 s Python CPU (~86% một core), peak process RSS 146,11 MiB; min available toàn matrix 3,219 GiB. 48 Nearest + 2479 Table + 1722 Route HTTP requests, 9187 Table-cache hits và 5347 route-cache hits, 0 request failures. Latency p50/p95 CAR 7,56/10,90 ms; MOTORBIKE 7,36/9,89 ms (aggregate service requests, không phải riêng Route). `tableCandidates` là logical ETA cells gồm cache hits, không phải số source cells thật trên HTTP. Snapshot router RAM trước/sau khoảng HCM25 MiB, CAR41 MiB, MOTORBIKE59 MiB; chưa đo continuous router peak. Wall live bao gồm prepare/core/audit/năm snapshots, chưa gồm ghi full result JSON cuối của benchmark script.

Oracle default 16/128: 200 static sampled dispatches, winner recall 90–95%/seed, feasible candidate miss 0, mean ETA regret 0,25–2,025 s/seed, maximum 29 s. Table-cell savings 59,0–62,6%; query savings 0% hoặc -2,5% ở seed phải mở rộng. Hai complete small runs mỗi seed có 0 service-outcome differences trong fixture này; không suy thành global optimum hay quality trên Hanoi live. Grid shortlist là prefix ID trong các occupied cells gần nhất, sau đó rank distance trong prefix, không phải true Euclidean closest K trong cell.

Real API + một worker: 100 fleet/20 requests, 20 completed, 2,851 s HTTP create-to-final+snapshot checks. Quan sát QUEUED→RUNNING→COMPLETED. Running-job cancel API acknowledgement 4,06 ms; 10 later polls đều CANCELLED/result409, worker log xác nhận CANCELLED. Đây là ACK latency, không phải bảo đảm mọi HTTP đang chờ kết thúc trong 4 ms. Cross-language frontend product validator kiểm sáu snapshot times và selected routes cả CAR/MOTORBIKE: PASS.

Browser còn tạo real worker job5000 fleet/1250 requests,1250 completed; enqueue→persisted final10,644 s. Product TS validator chạy lại với large result/snapshot/selected routes: PASS. Snapshot time100=5000 total/1000 offline/4000 online/3882 idle/118 onTrip/moving. Large API playback60,05 FPS trong5s, worker idle sau completion; không gộp thành chứng minh simultaneous streaming workload. [Large integration evidence](m3-m4-evidence/integration-summary.json).

**Regression tại checkout tích hợp:** `RUN_REAL_DATA=1 .venv/Scripts/python.exe -X utf8 -m pytest -q` → **189 PASS**, 47,40 s; một Starlette/httpx warning. Frontend **167 PASS**, 17 files; lint/typecheck/build/replay/mixed-export verifier exit0. Lint29 warnings, build main chunk >500kB; không warning-free. Focused25 tests kiểm golden/FIFO/inclusive deadlines/release/stationary/online schedules/mode/expansion/budget/recoverable Table/outage/determinism/mutations/queue/cancel/interruption/process lock/final API/tampering. Browser và readiness decisions: [integration review](M3_M4_INTEGRATION_REVIEW.md).

## Lệnh chạy lại (Windows PowerShell, root checkout tích hợp)

```powershell
# Terminal worker, cùng store với API (default build/m3/jobs)
.\.venv\Scripts\python.exe -m backend.app.simulation_worker --store build/m3/jobs

# Terminal API riêng; chọn port còn trống
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Small mixed job (routers Hanoi CAR5001/MOTORBIKE5002 đã ready)
$body = @{regionId='nvmr-hanoi-core';seed='m3-small';fleetSize=10;carCount=5;bookingCount=20;horizonSeconds=900;maxWaitSeconds=300;onlineFraction=1.0} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v3/simulation/jobs -ContentType application/json -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/v3/simulation/jobs/$($job.id)"
# Sau khi COMPLETED:
Invoke-RestMethod "http://127.0.0.1:8000/api/v3/simulation/jobs/$($job.id)/result?summary=true"
Invoke-RestMethod "http://127.0.0.1:8000/api/v3/simulation/jobs/$($job.id)/snapshot?timeSeconds=30"
# Hủy job đang queue/run:
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v3/simulation/jobs/$($job.id)/cancel"

# Domain matrix, không browser/WebGL stress hoặc full test suite đồng thời
.\.venv\Scripts\python.exe scripts/benchmark_simulation.py --scales 100 500 1000 3000 5000 --seeds 5 --output build/m3/domain.json
# Oracle độc lập nhanh hơn:
.\.venv\Scripts\python.exe scripts/benchmark_simulation.py --oracle-only --seeds 5 --output build/m3/oracle.json

# Live OSRM tăng từng mức, chỉ tiếp tục khi RAM >=2GiB và case trước ổn
.\.venv\Scripts\python.exe scripts/benchmark_simulation_live.py --fleet-size 100 --booking-count 20 --output build/m3/live-100.json
.\.venv\Scripts\python.exe scripts/benchmark_simulation_live.py --fleet-size 500 --booking-count 100 --output build/m3/live-500.json
# Để tái lập matrix đã đo, dùng đúng workloads/seeds trong JSON evidence; lệnh 20/100 requests trên chỉ là small smoke khác workload.

.\.venv\Scripts\python.exe -m pytest tests/test_m3.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Đổi store bằng `$env:GSM_SIMULATION_STORE=(Join-Path (Get-Location) 'build/m3/jobs')` ở terminal API; worker `--store` dùng đúng cùng directory. Ctrl+C chỉ terminal API/worker do mình chạy. Worker Ctrl+C cooperative cancellation; worker bị crash sẽ được lần worker tiếp theo đánh INTERRUPTED. Không sửa status JSON để ép COMPLETED. Port conflict: kiểm tra `Get-NetTCPConnection`, chọn port/proxy khác, không kill process lạ. Thiếu RAM: dừng tăng workload, đóng browser/task services mình sở hữu khi phù hợp; không dừng router/user apps không được phép.

## Giới hạn và bước tối ưu

Đã kiểm chứng 5000 fleet với các workloads/graph/online fractions ở bảng; chưa phải chứng nhận 5000 moving đồng thời, mọi topology hoặc production capacity. Spatial shortlist có thể bỏ global winner/thay đổi outcomes; cần thêm live exhaustive samples ở nhiều topology/online fractions trước production claims. Occupied-cell heap được xây mỗi dispatch; large spread/high pending retries còn có thể tốn CPU. Snapshot vẫn trả whole fleet mỗi poll và per-vehicle timeline lookup, chưa delta/stream. Store local không auth/retention/quotas; worker single process không resume, không distributed ownership. Routing evidence được kiểm tra trước và sau run; không hỗ trợ thay graph trong lúc chạy. Online schedule hiện là fraction per mode, chưa arbitrary individual duty input qua HTTP. Không có M5 multimodal choice model/M6 analytics/deployment M7 trong change này.

Quyết định readiness cuối cùng phải dựa kết quả benchmark tích hợp và regression hiện tại; GO phát triển pilot nhỏ khác GO hoàn tất milestone hay GO vận hành 5.000 xe.
