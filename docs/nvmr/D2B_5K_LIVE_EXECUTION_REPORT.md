# D2b.2 — Connected NVMR v5: UI fixes và live readiness

**Kết luận cuối: D2B_COMPLETED.** Job **`660c52e17ec240b48f9c7340bd5b82da`**
đạt persisted COMPLETED lúc **20:00:23 ngày 20/10/2026**, core integrity audit PASS.
Đúng **1 POST**, **5000 xe / 1750 requests**, **1229 completed / 521 unserved**.
API/worker đã được thay an toàn bằng current source; owner cho phép tiếp tục với
khoảng 5,02 GiB RAM thay cho mục tiêu 6 GiB. Xem mục 8–9. Phần dưới giữ nguyên
lịch sử lần dừng trước POST và checkpoint RUNNING để phân biệt với kết quả cuối.

Ngày 20/10/2026, kiểm tra runtime lúc khoảng **19:20 Việt Nam**.
Kết luận: **D2B_PRE_EXECUTION_BLOCKED**. **0 POST**, không có job ID mới.
Owner đã phê duyệt một lần chạy, nhưng điều kiện source identity của API 8022
không đạt. Dừng trước POST theo mục 4 của yêu cầu D2b.2.

## 1. Hai sửa UI đã hoàn thành

| File | Thay đổi |
| --- | --- |
| `frontend/src/components/connected-workspace.tsx` | Bỏ `setAnalytics(true)` trong callback chọn xe; giữ clearing zone/mode filters và `session.selectVehicle(id)` |
| `frontend/src/components/playback-dock.tsx` | Compact dropdown dùng `simulationSpeeds` hiện có: 1/2/4/8/16/32/64×; bỏ 0.25/0.5× |
| `frontend/tests/connected-workspace.test.tsx` | Regression gọi trực tiếp `SimulationMap.onSelect`, kiểm tra giữ State A/B, selection propagation, filter clearing, map DOM và playback time |
| `frontend/tests/compact-playback.test.tsx` | Hai test chọn 32/64× trên dropdown gắn với FleetClock thật, kiểm tra thời gian sau 1s và clamping/completion tại duration |

Analytics chỉ thay đổi qua nút Analytics hoặc Đóng Analytics. Không thêm panel,
không thay MapLibre/camera/clock, route loading hoặc simulation input. Legacy dock
giữ nguyên các controls của nó. High-speed playback dùng absolute simulation time
hiện tại của FleetClock, không thêm rerouting hay cách nội suy mới.

## 2. Tests thực thi trước mọi live execution

| Kiểm tra | Kết quả |
| --- | --- |
| Focused frontend: Connected workspace, compact playback, workspace, fleet, Connected simulation | **PASS: 69 tests / 5 files**, 8,69s |
| `npm.cmd test -- --maxWorkers=1` | **PASS: 230 tests / 29 files**, 41,58s |
| `npm.cmd run typecheck` | **PASS**, exit 0 |
| `npm.cmd run build` | **PASS**, exit 0; warning chunk lớn hiện hữu |
| D2a/Connected contract, domain, API, Analytics, worker integration tests | **PASS: 47 tests**, 9,84s; một warning Starlette/httpx deprecation |
| `git diff --check` | **PASS** |
| Browser/WebGL hoặc playback 5K | **NOT_RUN** |

Full frontend suite bao gồm HCM, Hanoi v3, Regional v4 và Saved Replay regression.
Test API backend dùng fixtures/temp stores trong process, không submit tới live API.
Không chạy test/build đồng thời với live job; không có live job active trong store.

Backend command:

```powershell
$env:RUN_REAL_DATA='0'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -rs tests/test_d2a_preflight.py tests/test_connected_domain.py tests/test_connected_api.py tests/test_connected_analytics.py tests/test_connected_integration.py
```

## 3. Frozen preset và offline preflight

**PASS**: ID/seed `nvmr-connected-5k-hanoi-centric-v1`, version 1;
request đọc trực tiếp từ `config/scenarios/nvmr-connected-5k-hanoi-centric-v1.json`.
SHA-256 giữ đúng:
`a37a44637fd829d25d7d494a520c5797e4857c996f53104d76f779decf1092df`.
Manifest provenance/config/generator hashes vẫn hợp lệ; không sửa preset/manifest.
Source revision: `292852cbbab8c05430ad6e60dc99827cce45c6ac`, cùng các UI edits chưa commit.

Đã chạy lại:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.preflight_nvmr_5k --output build/d2b/preflight.json --store build/r1b/jobs
```

**PASS** config, pinned source, hai graph, routing acceptance evidence, verified
pre-snapped anchors, map MBTiles, input generation và persisted-data readiness
trên completed artifact nhỏ có sẵn. Đây là offline preparation, không phải simulation.

| Zone kỹ thuật | CAR | MOTORBIKE | Pickup requests |
| --- | ---: | ---: | ---: |
| hanoi | 1400 | 2100 | 1050 |
| bac-ninh | 150 | 225 | 175 |
| hung-yen | 150 | 225 | 175 |
| phu-tho | 150 | 225 | 175 |
| thai-nguyen | 150 | 225 | 175 |
| Tổng | 2000 | 3000 | 1750 |

Hai lần offline generation có cùng canonical hash
`94dcfa3f3de487e4350b4f5431332fa58a31d774301dd3eaf7f9e6dbcbcce109`.
Không giảm quy mô, không đổi seed/timing, không dựng fake completed result.

## 4. Runtime readiness và blocker chính xác

| Kiểm tra | Trạng thái và bằng chứng |
| --- | --- |
| Branch/Git đầu phiên | **PASS**: `feature/nvmr-m0-architecture`, sạch |
| API workspace và absolute store | **PASS**: runtime API trỏ đúng checkout này và `build/r1b/jobs` |
| Worker store lease | **PASS**: runtime trả `locked`; inventory có một worker process tree; Windows venv launcher và interpreter child là cùng một instance |
| Queue mọi loại job | **PASS**: đọc trực tiếp JobStore, 9 jobs, không QUEUED/RUNNING; gồm v3/v4/v5 |
| Job theo frozen preset / 5000–1750 | **PASS**: không có |
| Receipt POST cũ | **PASS**: không có create-attempt/created-job receipt trong các thư mục D2b |
| Hai container Connected | **PASS hiện diện/running**, đúng 5005/5006; legacy routers đều exited |
| CAR/MOTORBIKE runtime graph identity | **PASS** bằng current `connected_readiness(config)`, gồm graph-specific runtime probes; không suy từ port/name |
| API source hiện hành | **BLOCKED**: API 8022 đang chạy source trước D1.5 Analytics endpoint |
| Worker loaded-module identity hiện hành | **NOT_RUN**: lease/process path xác minh được; chưa chứng nhận toàn bộ module đang nằm trong process là source mới |

API 8022 khởi động **15:19:49**, trong khi `connected_jobs.py` và
`connected_analytics.py` được cập nhật **17:22:10**. Bằng chứng hành vi độc lập:

```text
GET http://127.0.0.1:8022/api/v5/simulation/jobs/e001951cb0594c979c49d6d621eaace0/analytics/fleet-states
HTTP 404 {"detail":"Not Found"}
```

Current checkout đăng ký endpoint này, và current Analytics tests PASS. Vì vậy
API/store đúng đường dẫn không đủ để chứng nhận source hiện hành. API 8000 khác
cũng đang tồn tại; không đổi đích POST sang đó để bỏ qua yêu cầu 8022.
Không restart/replace stack sau khi check này fail; giữ runtime để owner xử lý
theo yêu cầu dừng trước POST. Không start frontend/browser/service/container mới.
`scripts/Start-GsmDev.ps1` là launcher đúng đã kiểm tra; không gọi launcher trong
phiên này vì stack hiện có và live source check đã fail.

Hai graph runtime dùng MLD, cùng pinned source/extract D2a; manifest SHA-256:

- CAR: `ad52e520c72f8374ebbe8add5d219f5e48c533ac72cc2b23dfb73bb8e5c2528c`.
- MOTORBIKE: `be9140840ce9293ddd747344e6b9d899d02d347ad0b1321143d5bc77eb5677f0`.

## 5. Tài nguyên trước quyết định không POST

Đo sau tests/build, khi hai router đã chạy sẵn và sau runtime routing probes:

| Số đo | Giá trị |
| --- | ---: |
| Physical RAM khả dụng | **4,929 GiB** |
| System commit headroom | **7,908 GiB** |
| Free disk | **35,928 GiB** |
| API RSS / private | 36,00 / 55,47 MiB |
| Worker RSS / private | 22,41 / 36,45 MiB |
| CAR container current memory | 4,484 MiB / 1 GiB limit |
| MOTORBIKE container current memory | 4,785 MiB / 1 GiB limit |

D2a admission policy vẫn PASS `routine`, nhưng đây không phải ước lượng đủ RAM
cho simulation. Physical RAM thấp hơn mục tiêu vận hành khoảng 6 GiB một lượng
**1,07 GiB**. Đây là điều cần chú ý trước lần kiểm tra tiếp theo, không phải bằng
chứng OOM hoặc một ngưỡng an toàn đã được stress-test. Các số memory container
chỉ là snapshot idle/probe, không phải peak khi xử lý 1750 requests. Không điều
chỉnh policy/Windows settings, không đóng ứng dụng hoặc stop container tự động.

## 6. POST, lifecycle, outcomes và artifacts

- POST attempts trong phiên: **0**; không tạo create-attempt receipt vì readiness fail.
- Job ID/lifecycle mới: **không có**. Chín jobs trước đó được giữ nguyên.
- Live execution wall time, progress và resource peaks: **NOT_RUN**.
- Completed/unserved counts, assignments và global/by-zone/by-mode KPI của run 5K: **NOT_RUN**.
- Full 5K result/config/input/route/provenance conservation audit: **NOT_RUN**.
- New 5K prepared-input/result/event-log artifacts và kích thước: **không có**, không thể báo PASS.
- Monitoring 10s và durable job-ID receipt: **NOT_RUN**, vì chưa có job để theo dõi.
- D2c portable packaging/replay/restore và browser performance: còn chờ genuine completed run.

Evidence local nằm trong **ignored `build/d2b/`**:

- `frontend-focused.txt`, `frontend-tests.txt`, `frontend-typecheck.txt`, `frontend-build.txt`.
- `backend-integrity-tests.txt`, `preflight.json`, `preflight.txt`.
- `api-readiness.json`, `runtime-readiness.json`, `source-identity.json`.
- `process-inventory.json`, `router-inspect.jsonl`, `pre-execution-outcome.json`.

Các file này chứa paths/PIDs/resource readings máy local, không đưa vào Git.
Không viết monitoring giả hoặc sửa persisted outputs cũ.

## 7. Bước nhỏ nhất để tiếp tục

Restart đúng API **8022** bằng current checkout; xác nhận worker source hiện hành
và một OS lease trên cùng store. Giữ Docker Desktop và hai Connected routers chạy.
Owner có thể giải phóng thêm ứng dụng nặng để đạt khoảng 6 GiB physical available.
Sau đó chạy lại offline preflight, runtime/source/store/queue/receipt checks và đo
tài nguyên ngay trước POST. Quyền một lần chạy chưa được sử dụng; chưa cần retry
hoặc reconcile một POST trước đó. Không đổi preset hoặc tự chuyển sang API 8000.

Trong phiên này đã hoàn thành hai UI fixes, tests/build và diagnostics. Không
stage/commit/push/merge/reset/đổi branch, không subagent/worktree. Theo điều kiện
owner đã đặt ra, source identity fail dẫn tới **D2B_PRE_EXECUTION_BLOCKED**.

## 8. Recovery và one-time execution — 20/10/2026

### Restart an toàn

Trước restart, đã xác minh lại runtime checkout/store, port owner/ancestry,
executable/command/start time và 9 persisted jobs; tất cả đều terminal. API cũ
là interpreter **28660**, venv launcher **4116**; worker cũ là interpreter
**25004**, venv launcher **21852**. Mỗi service có console riêng, không chia sẻ
với ứng dụng khác. Helper chỉ gửi Ctrl+C sau khi kiểm tra lại process identity,
queue và console membership allowlist. Không dùng force-kill.

API ghi đủ `Shutting down`, `Application shutdown complete`, `Finished server
process`; bốn PID cũ đã thoát, port 8022 trống và worker lease về `offline`.
Không xóa `.worker.lock`, không sửa jobs. API 8000 và hai router được giữ nguyên.

Khởi động trực tiếp, không launcher/frontend/browser/reload, dùng `.venv` Python,
explicit working directory là checkout này, cùng absolute `build/r1b/jobs`:

- API mới: launcher **9268**, interpreter/listener **8704**, bắt đầu **19:30:55–56**.
- Worker mới: launcher **17940**, interpreter **23192**, bắt đầu **19:30:56**.
- Một worker process tree duy nhất, đúng executable/command/store và lease `locked`.
- Source hashes ghi trước startup, mtime backend trước startup, hashes đối chiếu
  lại sau startup không đổi; working directory/arguments có trong startup receipt.

**PASS:** Analytics endpoint 8022 trả **HTTP 200**, đúng run ID, fleetSize 20,
25 checkpoints; toàn bộ response bằng output của pure persisted-data aggregator.
Không chỉ kiểm tra mã HTTP. Current `connected_readiness(config)` PASS cho hai mode,
graph identities khớp evidence trước đó. Recovered offline preflight PASS; không
QUEUED/RUNNING job, không job trùng preset và không create-attempt receipt cũ.

### Resource gate và chỉ dẫn bổ sung của owner

Sau recovery, RAM khả dụng khoảng **5,023 GiB**, dưới gate 6 GiB ban đầu; đã dừng
trước POST và yêu cầu owner giải phóng thêm RAM. Owner trả lời trực tiếp:

> Không thể giải phóng thêm RAM, hãy tiếp tục làm việc với 5.02 GiB RAM trống.

Chỉ dẫn mới thay mục tiêu vận hành 6 GiB cho lần chạy này. Không thay backend
admission policy hoặc preset. Ngay trước POST, physical available **5,024 GiB**,
commit headroom **7,450 GiB**, disk khoảng **35,93 GiB**; routine admission PASS.
Các số này không bảo đảm hoàn tất. Exclusive receipt ghi rõ chỉ dẫn mới của owner.

### Submit và theo dõi

**Đúng 1 POST** tới API 8022, body là bytes đọc trực tiếp frozen JSON; SHA-256
vẫn `a37a44637fd829d25d7d494a520c5797e4857c996f53104d76f779decf1092df`.
Source revision `292852cbbab8c05430ad6e60dc99827cce45c6ac`, dirty status chứa
các UI edits/report đã biết. Không commit/push.

`create-attempt.json` tạo bằng exclusive `open('x')`, flush + fsync. Recheck queue
mọi version, resource policy và checksum ngay trước send. Một `client.post` duy
nhất, không retry/redirect. Server trả **202**, job created lúc **19:34:55,640**:

**`660c52e17ec240b48f9c7340bd5b82da`**.

Response/job ID được lưu ngay trong receipt riêng. Đã thấy `QUEUED → RUNNING`;
worker PID **23192**. Monitor dùng status nhỏ, không tải running result; interval
khoảng 10s, Windows physical/commit, worker/API RSS/private, disk và router stats
khoảng 30s. Không chạy tests/build/browser trong execution.

Evidence bổ sung dưới ignored `build/d2b/`:

- `recovery-before-processes.json`, `recovery-before-runtime.json`.
- `graceful-api-*.json`, `graceful-worker-*.json`, `graceful-stop-confirmation.json`.
- `recovery-services.json`, `recovery-start-source.json`, `recovered-processes.json`.
- `recovered-api-proof.json`, `recovered-preflight.json`, `recovered-readiness.json`.
- `recovered-api.*.log`, `recovered-worker.*.log`.
- `create-attempt.json`, `post-dispatch.json`, `post-response.json`, `created-job.json`.
- `monitor.jsonl`, `monitor-summary.json`, local `submit_and_observe.py`.

Worker là service độc lập, tiếp tục nếu phiên Codex/monitor bị gián đoạn. Lệnh
chỉ resume quan sát, **không POST**:

```powershell
.\.venv\Scripts\python.exe -X utf8 build/d2b/submit_and_observe.py --observe 660c52e17ec240b48f9c7340bd5b82da
```

Tại checkpoint đang chạy này: result/KPI/audit và D2c **NOT_RUN**, chưa tuyên bố
completed. Trạng thái cuối của phần recovery sẽ được cập nhật từ persisted status.

## 9. Kết quả cuối, integrity và handoff D2c

### Genuine completed run

**PASS:** persisted `status.json` và API 8022 cùng xác nhận `COMPLETED`, progress 1.
Worker log ghi `RUNNING → COMPLETED`. Tạo lúc **19:34:55,640**, hoàn tất lúc
**20:00:23,453** ngày 20/10/2026: **1527,812s = 25 phút 27,812 giây** wall time.
Engine telemetry `totalMilliseconds` khoảng **1522,243s**, gồm preparation khoảng
5,947s; các mốc này có phạm vi đo khác nhau. Monitor phát hiện COMPLETED ở sample
25 phút 30,678 giây. Không dùng elapsed của lần mở lại monitor sau đó làm thời
gian chạy simulation.

Progress cuối tăng từ khoảng 31,7% lên 100% trong một interval quan sát. Nó đếm
booking terminal, không đo thời gian wall hoặc phần trăm chi phí còn lại.
Ngoại suy thô 1h40–2h đã đưa ra khi đang chạy không phản ánh thời gian hoàn tất
thực tế; bằng chứng cuối là 25 phút 28 giây. Không thay timing/seed/parameters để
làm progress hoặc KPI đẹp hơn.

| Pickup zone kỹ thuật | Requests | Assigned/completed | Unserved |
| --- | ---: | ---: | ---: |
| hanoi | 1050 | 1003 | 47 |
| bac-ninh | 175 | 101 | 74 |
| hung-yen | 175 | 49 | 126 |
| phu-tho | 175 | 50 | 125 |
| thai-nguyen | 175 | 26 | 149 |
| Tổng | 1750 | 1229 | 521 |

Theo mode: **CAR 681 requested / 495 completed / 186 unserved**;
**MOTORBIKE 1069 / 734 / 335**. Completion fraction thực đo **70,229%**,
không có KPI mục tiêu. Pending = 0, activeTrips = 0.

Unserved reasons lấy từ persisted `event.payload.failureReason`:
**488 SEARCH_BUDGET_EXHAUSTED**, **33 NOROUTE**. Shortlist budget exhaustion không
chứng minh toàn bộ fleet không có phương án khả thi. Telemetry có 8 CAR + 25
MOTORBIKE request failures; job vẫn hoàn tất với các domain outcomes này.
Không suy ra chi tiết lỗi transport khi telemetry không lưu phân loại đó.

Pickup wait của **1229 assigned/completed bookings**: mean **111,014s**, max
**299,2s**. Utilization busy/online **4,841%**, busy/fleet **3,873%**, theo toàn
`simulationDurationSeconds = 22876,774s` (khoảng **6h21m16,774s**). Horizon 900s
giới hạn thời gian sinh requests; engine tiếp tục xử lý các chuyến dài đến cuối.
Đó là thời gian mô hình, không phải wall time 25 phút 28 giây. Inputs là synthetic,
OSRM duration tĩnh; không diễn giải thành KPI vận hành GSM thực tế.

### Core integrity và Analytics

Audit đọc local full result **một lần trong một process riêng**, sau COMPLETED;
không POST, không gọi OSRM, không sửa raw output. Resource check trước parse PASS.
Audit khoảng **4,20s**, process peak RSS khoảng **409,55 MiB**, gồm parse/validators.
Không rerun frontend tests/build; giữ nguyên các UI fixes và test evidence mục 2.

**PASS**:

- Chính xác 5000 vehicle IDs riêng, CAR 2000 / MOTORBIKE 3000; exact home-zone
  fleet allocation 1400/2100 ở hanoi, 150/225 tại mỗi zone khác.
- Chính xác 1750 booking IDs riêng, pickup allocation 1050/175/175/175/175;
  mode draws 681/1069, timestamp trong horizon, pickup khác dropoff.
- Stored config bằng frozen preset sau Pydantic normalization, config hash và
  config trong input/prepared/result/status nhất quán. Request bytes SHA vẫn
  `a37a44637fd829d25d7d494a520c5797e4857c996f53104d76f779decf1092df`.
- Canonical prepared-input hash
  `94dcfa3f3de487e4350b4f5431332fa58a31d774301dd3eaf7f9e6dbcbcce109`
  khớp cả hai lần deterministic D2a generation trên verified anchors.
- Prepared input/provenance/routing identities khớp result và frozen graph
  evidence; mọi persisted route có đúng run/mode identity, geometry và distance index.
- `validate_connected_result`, existing independent KPI arithmetic audit và
  `persistence_check` đều PASS; global/by-zone/by-mode counts/numerators/ratios
  khớp. 1229 assignments = 1229 completed; completed + unserved = 1750.
- `event-log.json` bằng persisted events trong result. Initial fleet, bookings,
  1229 assignments, **7187 events**, **5000 timelines / 8687 entries**, **2344
  route geometries**, KPI, distribution quality và model/source provenance còn đủ.
- Pure fleet-state series: **120/120 selected checkpoints** khớp snapshot
  projector. API Analytics của chính run 5K cũng trả HTTP 200, fleetSize 5000,
  **3571 transition checkpoints** trước sampling, **120** điểm trả về,
  `sampled=true`; mọi điểm bảo toàn tổng 5000. Full timelines vẫn được giữ.

Khi kiểm tra API aggregate, audit process đã thoát; không giữ đồng thời nhiều
Python audit process với full world. Client chỉ nhận aggregate, không download
bulk result. Việc chọn 120 điểm cho UI không thay raw timeline hay raw KPI.

### Resource observations

154 samples trong khoảng QUEUED đến lần đầu quan sát COMPLETED; các terminal
checks sau quota không được tính thành thời gian chạy hoặc thay thế lịch sử peak.
Đã tổng hợp lại từ toàn bộ JSONL trong `execution-monitor-summary.json`.

| Số đo trong execution | Giá trị |
| --- | ---: |
| Physical available ngay trước POST | 5,024 GiB |
| Commit headroom ngay trước POST | 7,450 GiB |
| Minimum available physical RAM lấy mẫu | **3,062 GiB** |
| Minimum system commit headroom lấy mẫu | **4,880 GiB** |
| Worker peak RSS lấy mẫu / private lấy mẫu | **0,489 / 0,478 GiB** |
| Worker process lifetime peak RSS | **0,515 GiB** |
| API peak RSS lấy mẫu | **74,64 MiB** |
| CAR / MOTORBIKE container peak lấy mẫu | **77,02 / 73,93 MiB** |
| Free disk thấp nhất lấy mẫu | khoảng **35,87 GiB** |

Không thấy resource admission/OOM failure của job. 10s samples có thể bỏ lỡ peak;
process lifetime peak khác peak lấy mẫu. Docker stats không đo toàn bộ WSL/file
cache/host RAM. Không coi các số trên là minimum RAM cần thiết hoặc bảo đảm cho
mọi lần chạy; đây là bằng chứng của đúng lần execution này.

### Persisted artifact

Directory: `build/r1b/jobs/660c52e17ec240b48f9c7340bd5b82da/`.

| File | Bytes |
| --- | ---: |
| `input.json` | 1167 |
| `prepared-input.json` | 1152227 |
| `status.json` | 2274 |
| `event-log.json` | 1214347 |
| `result.json` | **54528521** |
| Tổng | **56898536** (54,263 MiB) |

Result SHA-256:
`37812b5d55b1970c3ee57412a896002ca7418c855024b552846ba5e7c319d95a`.
Checksums từng file, all KPI/raw diagnostics và evidence paths nằm trong ignored
`build/d2b/completed-audit.json`. Các evidence bổ sung:
`completed-audit.txt`, `completed-analytics-api.json`, `execution-monitor-summary.json`.
Local monitoring helper đã giữ lại history khi resume để không reset peak/min.
Không thay persisted job files khi sửa các báo cáo/diagnostics tổng hợp.

### D2c và trạng thái cuối

Còn **NOT_RUN**: portable packaging/restore sang môi trường khác, browser/WebGL
replay 5K dài và browser export/download. Core persisted data đủ để bắt đầu D2c;
giữ toàn bộ job directory cùng preset/manifest/source revision/GIS identities,
không chỉ copy summary hoặc Analytics response. Local maps/application vẫn cần
cho replay ở môi trường mới. Không tự đóng router/API/worker sau run.

**D2B_COMPLETED**: một genuine Connected v5 5000/1750 run đã COMPLETED, core
integrity và Analytics source checks PASS. Đúng 1 POST, không retry/downscale/
retune, không stage/commit/push/merge/reset/đổi branch, không subagents/worktrees.
