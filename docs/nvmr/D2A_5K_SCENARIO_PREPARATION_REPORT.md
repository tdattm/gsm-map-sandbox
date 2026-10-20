# D2a — Connected v5: 5K scenario preparation & resource preflight

Ngày 20/10/2026. **CONDITIONAL READY**. Preset và offline input preparation PASS;
runtime router/worker và tài nguyên ngay trước D2b cần kiểm tra lại sau khi owner
phê duyệt. Không có blocker artifact/contract/persistence được phát hiện.

Một agent, checkout `feature/nvmr-m0-architecture`, Git đầu phiên sạch. Không
worktree, stage, commit, push, merge hoặc reset. Không tạo live job, không chạy
simulation 5K, không gọi OSRM, không start Docker/router/worker, không sửa engine,
frontend, MapLibre hay voucher. Các test API sử dụng TestClient/temp store và
executor fixture trong process, không gửi POST tới server/JobStore local thật.

## 1. Deliverables và cách chạy lại D2a

| File | Vai trò |
| --- | --- |
| `config/scenarios/nvmr-connected-5k-hanoi-centric-v1.json` | Request đầy đủ, chỉ chứa field thuộc contract |
| `config/scenarios/nvmr-connected-5k-hanoi-centric-v1.manifest.json` | ID/version, checksum, provenance và nguyên tắc cố định preset |
| `config/scenarios/.gitattributes` | Pin LF cho request/manifest JSON, tránh autocrlf đổi preset byte checksum khi checkout |
| `scripts/preflight_nvmr_5k.py` | Offline validator, diagnostics, resource và persisted-data audit |
| `tests/test_d2a_preflight.py` | 22 focused cases, gồm input-only 5K và negative checks |
| Báo cáo này | Diễn giải kết quả và handoff D2b |
| `build/d2a/preflight.json`, `build/d2a/tests.txt` | Evidence máy local, được Git ignore; không đưa vào commit |

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.preflight_nvmr_5k
```

Chỉ ghi báo cáo tổng hợp ở `--output`; không lưu bulk generated input. Mặc định
đọc store `build/r1b/jobs`; có thể chỉ rõ `--store`. Không gọi `JobStore.runtime()`
vì probe đó mở/ghi lock file. Lease ownership được ghi **NOT_RUN**, không suy ra từ
sự hiện diện `.worker.lock`. Exit 2 cho blocker, exit 0 cho conditional readiness;
luôn đọc `conclusion` và `resources.admission.allowed`, không dùng exit 0 để tự POST.

Tái sử dụng `connected_inputs`, `stratified_positions`, `distribution_quality`,
`read_anchor_catalog`, routing proof verifier, GIS verifiers/cached digest,
resource policy, immutable replay và independent KPI audit có sẵn. Không dùng
`validate_connected_inputs.run()` vì runner cũ có nhiều scale/default allocation
khác yêu cầu và ghi bulk input. Không sửa logic input vì không thấy phân bố suy biến.

## 2. Preset cố định trước D2b

ID/seed: `nvmr-connected-5k-hanoi-centric-v1`; version **1**.
Schema `gsm-nvmr-connected-scenario/v1`; region `nvmr-connected`.

SHA-256 request bytes:
`a37a44637fd829d25d7d494a520c5797e4857c996f53104d76f779decf1092df`.

| Zone kỹ thuật | CAR | MOTORBIKE | Tổng xe | Pickup requests | demandWeight |
| --- | ---: | ---: | ---: | ---: | ---: |
| hanoi | 1400 | 2100 | 3500 | 1050 | 6 |
| bac-ninh | 150 | 225 | 375 | 175 | 1 |
| hung-yen | 150 | 225 | 375 | 175 | 1 |
| phu-tho | 150 | 225 | 375 | 175 | 1 |
| thai-nguyen | 150 | 225 | 375 | 175 | 1 |
| Tổng | 2000 | 3000 | 5000 | 1750 | 10 |

Fleet dùng explicit allocations 70/7,5/7,5/7,5/7,5%; demand độc lập dùng largest
remainder 6:1:1:1:1. Đây là **vùng kỹ thuật**, không phải ranh giới hành chính.

| Tham số | Giá trị | Cơ sở |
| --- | --- | --- |
| horizonSeconds | 900 | Giữ mặc định đã có; nhu cầu trải 15 phút, không kéo dài run để thay KPI |
| maxWaitSeconds | 300 | Giữ mặc định 5 phút; không tăng theo kết quả |
| onlineFraction / onlineSchedule | 0.8 / `[]` | Giữ mặc định; 4000 xe online ban đầu, không tạo chuyển động bằng schedule |
| workload | typical | Uniform identity-keyed arrival; không burst |
| demandCarFraction | 0.4 | Giữ mặc định, draw độc lập từng khách; không ép đúng 40% sample |
| crossZoneDemandFraction | 0.25 | Giữ mặc định, đo OD thật sau generation |
| initialCandidates / maxCandidates | 16 / 128 | Giữ shortlist mặc định; không sửa dispatch/routing |
| gridCellDegrees | 0.005 | Grid dispatch mặc định |
| distribution.cellDegrees | 0.025 | Ô stratification/diagnostics mặc định, khác grid dispatch và ô GIS 0.005 |
| maximumVehiclesPerPosition | 1 | Catalog đủ capacity cho cả hai mode với giới hạn toàn cục |
| nearestNeighborSampleSize | 128 | Diagnostic mặc định, tránh all-pairs 5000² |

PASS: Pydantic validation, exact counts/zone IDs, mọi request field đều được pin,
generated JSON Schema bằng schema checked-in. Không cài thêm JSON Schema library;
request được validate bằng chính Pydantic model sinh schema. Manifest nằm riêng,
bind checksum request, region config và generator source. Không thay seed/timing/
wait/cấu hình sau khi thấy outcomes chỉ nhằm tăng KPI. Variant nghiên cứu sau này
phải có version mới và lý do rõ ràng. Không đặt KPI mục tiêu.

## 3. Spatial và temporal evidence từ verified road inputs

PASS: đúng 5000 vehicle IDs và 1750 booking IDs duy nhất; đúng mode/home/pickup/
dropoff zone, đúng totals ở bảng trên. Mọi tọa độ nằm trong catalog pre-snapped
đúng mode. Pickup khác dropoff. Không sinh tọa độ ngoài đường hoặc gọi nearest.
Catalog CAR/MOTORBIKE chia sẻ một phần tọa độ; sampler theo thứ tự production
trừ occupancy của mode trước, không coi capacity của hai mode là độc lập.

| Zone | Unique CAR anchors | Unique MB anchors | MB slots sau CAR | MB cần | Fleet cells | Max xe/cell |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hanoi | 13101 | 13143 | 11770 | 2100 | 120 | 31 |
| bac-ninh | 3267 | 3276 | 3127 | 225 | 140 | 4 |
| hung-yen | 6853 | 6853 | 6703 | 225 | 262 | 2 |
| phu-tho | 7455 | 7455 | 7305 | 225 | 268 | 2 |
| thai-nguyen | 9001 | 9000 | 8850 | 225 | 327 | 2 |

Không thiếu anchors ở bất kỳ zone/mode. Toàn fleet: **5000 vị trí riêng**, 0 xe
trùng tọa độ, max occupancy 1, **1117 cells**, max 31 xe/cell, không cell nào vượt
ngưỡng crowded 50 của diagnostic hiện tại. Hà Nội có nhiều xe/cell hơn vì 70%
fleet ở vùng nhỏ; 10 ô đông nhất chỉ chiếm 8,86% fleet Hà Nội. Đây là đặc tính
allocation/road coverage, không phải sự dồn vào một vài điểm.

Nearest-neighbor địa lý: 128 mẫu so với toàn fleet; minimum **4,329m**, median
**211,647m**, p95 **1921,676m**. Không phải khoảng cách/thời gian đường bộ.

| Demand toàn cục | Pickup | Dropoff |
| --- | ---: | ---: |
| Unique coordinates | 1706 | 1711 |
| Duplicate occurrences ngoài lần đầu | 44 | 39 |
| Max requests/coordinate | 3 | 2 |
| Occupied cells | 661 | 732 |
| Max requests/cell | 17 | 16 |
| Share trong 10 cells đông nhất | 8,80% | 6,91% |

Pickup coverage từng zone: **118/104/144/140/155** cells theo thứ tự bảng;
max requests/cell tương ứng **17/4/3/4/3**. JSON giữ top coordinates/cells,
dropoff theo cohort pickup-zone và riêng theo destination-zone, cùng OD matrix.
Không bắt booking có tọa độ riêng tuyệt đối. Không có flag tập trung: kiểm tra
<5 cells, >10% trong một coordinate/cell theo cohort; fleet kiểm tra tương tự.
Các ngưỡng này là diagnostic heuristics, không phải kiểm định thống kê đã hiệu chuẩn
hay KPI dịch vụ. Demand uniform theo road anchors, không theo dân số hay nhu cầu GSM thật.

Mode thực tế: **681 CAR (38,914%) / 1069 MOTORBIKE**. Cross-zone **453/1750
(25,886%)**; đây là số đo input, không phải tỷ lệ completed/cross-zone dispatch.

Arrival dùng SHA-256(seed, booking ID, arrival label), round đến millisecond,
uniform trên horizon với `typical`; `low` hiện dùng cùng timing, `burst` chỉ dùng
5% horizon. Không cần sửa cơ chế này.

PASS: earliest **0,383s**, latest **899,920s**, **1748** timestamps riêng,
max **2** requests cùng timestamp. Các bucket 1 phút, từ 0–60 đến 840–900:
`109,108,128,106,100,113,100,131,121,113,113,141,127,109,131`.
Bucket 5 phút: **551 / 578 / 621**; peak **141 requests/phút**. JSON giữ cả
bucket 1/5 phút của từng pickup zone. Không có flag span <80% horizon,
>1% demand cùng timestamp, hoặc minute peak >2 lần uniform bucket mean.
Không thay timing theo outcome simulation.

PASS determinism: hai lần dựng tuần tự, giải phóng full input lần đầu trước lần
hai, cùng canonical input SHA-256:
`94dcfa3f3de487e4350b4f5431332fa58a31d774301dd3eaf7f9e6dbcbcce109`.
Catalog load + capacity/quality/input diagnostics + repeat khoảng **3,98s**;
process lifetime peak RSS **105,70MiB**, bao gồm imports/GIS verification,
không phải memory prediction của simulation. Không lưu full input D2a.

## 4. Artifact và resource preflight

Snapshot UTC `2026-10-20T11:41:50Z` (18:41:50 Việt Nam), máy Windows 16GB:

| Kiểm tra | Kết quả thực thi |
| --- | --- |
| Source/config identities | PASS, pinned national PBF checksum và region config |
| CAR + MOTORBIKE graph | PASS, MLD file sizes/checksums, profile/image/source/extract/config identity |
| Routing acceptance evidence | PASS, current validator/evidence checksum và per-mode graph identity |
| Snapped anchors/manifest | PASS, content checksum, mode identities, boundary attribution |
| Detail + overview MBTiles | PASS, existing read-only verifiers |
| RAM physical total / available | 15,784 / **3,698GiB** |
| Commit available / limit | **5,091 / 23,871GiB** |
| Free disk | **35,928GiB** |
| Admission thực tế | PASS `routine`: floor **0,75GiB physical / 1,5GiB commit** |
| Docker / WSL | Read-only inventory thành công; docker-desktop Running, Ubuntu Stopped |
| Router containers/ports | Hai container Connected đã chạy sẵn, listeners 5005/5006 hiện diện |
| API/process inventory | Listeners 8000/8022; Python/Docker/WSL working set/private memory trong JSON local |
| JobStore inventory | 9 jobs: 5 COMPLETED, 3 FAILED, 1 INTERRUPTED; không QUEUED/RUNNING |
| Worker lease / router runtime identity | NOT_RUN; không chứng nhận READY từ file/port/container |

GIS checks chạy tuần tự, dùng digest cache theo immutable file stat; không lặp
checksum file lớn không cần thiết. Không rebuild/network/Overpass/Docker start.
Admission chỉ phản ánh policy/headroom thời điểm đo, không reserve RAM, không
bảo đảm không paging/OOM hoặc hoàn tất. Disk là số đo, chưa có upper bound được
kiểm chứng cho full result 5K. Owner dự kiến giải phóng khoảng 6,4GB trước D2b;
không coi đây là RAM hiện đã có hoặc tự đổi Windows settings/stop process.

## 5. Persistence, replay và Analytics

Source review: `JobStore.create` giữ config/inputHash/model identity;
worker callback ghi `prepared-input.json` trước simulate; `finish` ghi full
`result.json` và `event-log.json` trước khi publish COMPLETED. Result giữ initial
vehicles/home zones, bookings/passenger IDs/request times, assignments, ordered
events, timelines, routes/geometry/cumulative meters/durations, global/byZone/
byMode raw KPI numerators/denominators, DistributionQuality, routing identities,
operating zones, model/assumptions và GIS source/extract/catalog provenance.

PASS trên completed run **có sẵn** `e001951cb0594c979c49d6d621eaace0`, **20 xe /
20 requests**: config hash và prepared input khớp full result; result invariants;
tính lại KPI bằng production và **independent arithmetic audit**; **25/25** fleet
state chart checkpoints khớp immutable snapshot. Không gọi API/OSRM để làm audit này.

| Nhu cầu sử dụng dữ liệu | Readiness |
| --- | --- |
| Replay completed world khi OSRM tắt | PASS cơ chế/persisted data nhỏ; full result và local map assets vẫn cần |
| Fleet state/position theo thời gian | PASS immutable timelines + geometry projector |
| Selected vehicle/booking/routes | PASS field/route invariants; existing API regression PASS |
| Kiểm chứng KPI | PASS raw fields và independent recomputation |
| Fleet-State Area Chart | PASS persisted timelines; UI giới hạn 120 checkpoint thực, dữ liệu gốc đầy đủ |
| Chuyển môi trường khác | Source data đủ; copy full job directory + compatible source/config/map assets; packaging/restore end-to-end NOT_RUN, D2c |
| Completed 5K persistence/performance | NOT_RUN, thuộc D2b; không suy từ run nhỏ |

Không phát hiện thiếu field cần sửa trước D2b. Không viết thêm persistence layer.
Khi chuyển môi trường, JobStore path là cấu hình local; không copy mỗi summary hay
analytics response. Giữ source revision/preset manifest/preflight cùng run để audit
code identity ngoài model version. Historical evidence không chứng minh mọi job cũ
có cùng completeness; script kiểm tra cụ thể artifact được chọn.

## 6. Tests và giới hạn bằng chứng

```powershell
$env:RUN_REAL_DATA='0'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -rs tests/test_d2a_preflight.py tests/test_connected_domain.py tests/test_connected_api.py tests/test_connected_analytics.py tests/test_connected_integration.py tests/test_connected_acceptance.py tests/test_connected_api_evidence.py tests/test_connected_recovery_io.py tests/test_connected_artifacts.py tests/test_m3.py tests/test_m2.py tests/test_regional_simulation.py
git diff --check
```

PASS **162 tests**, **1 SKIPPED** (`test_m2.py:184`, opt-in real local OSRM),
1 warning Starlette/httpx deprecation, **16,92s**. Skip không phải PASS.
22 D2a cases bao phủ contract/checksum/version freeze, exact totals và zone/mode
allocation, ID uniqueness, catalog membership/no fabricated coordinate, zone
attribution, distinct endpoints, global occupancy, temporal bounds/buckets,
sequential deterministic generation, capacity shortfall, corrupt input detection,
resource refusal không sửa config/store, fail-closed missing artifacts, persistence
và missing-data blockers. Fixture anchors được ghi rõ synthetic, không thay cho
verified GIS evidence. Compatibility suite gồm HCM/M2, v3/M3 và v4 regional.

Không sửa frontend/communication contract nên frontend regression NOT_RUN.
Live simulation, stress/benchmark, 5K completed replay/browser performance NOT_RUN.
`git diff --check` PASS; toàn bộ deliverables còn untracked, không có staged change.

## 7. Handoff D2b — chỉ thực thi sau phê duyệt

Các lệnh dưới **CHƯA THỰC THI**. Dùng đúng preset; không dùng CLI benchmark cũ
vì CLI đó tự tạo config/seed/allocation khác. Giải phóng RAM như dự kiến, kiểm tra
source API/worker hiện hành và workspace/store trước khi enqueue. Không tạo container
mới: nếu hai container Connected hiện có bị dừng, owner có thể start đúng hai tên
sẵn có bằng `docker start gsm-map-osrm-connected-car gsm-map-osrm-connected-motorbike`;
nếu container/graph không đúng thì dừng handoff, không rebuild hoặc fallback.

Chuẩn bị/reuse stack sau phê duyệt (không có `-StartRouters`, không tạo job):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Profile Meeting -Routers Connected -ApiPort 8022 -FrontendPort 5192 -Store build/r1b/jobs
```

Launcher kiểm tra workspace/store/listener/lease, có thể start API/worker còn thiếu;
chỉ dùng ở D2b đã phê duyệt. Meeting cần existing frontend build đúng identity;
nếu báo stale, build frontend theo runbook rồi chạy lại. Không tự dùng port khác
để bỏ qua stack đang giữ cùng store. Kiểm tra source/process receipt khi reuse;
lease chỉ chứng minh single worker ownership, không chứng minh source mới.

Chạy preflight lại **sau khi routers/runtime đã sẵn có**, rồi chỉ kiểm tra readiness:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.preflight_nvmr_5k --output build/d2b/preflight.json
if ($LASTEXITCODE -ne 0) { throw 'Preflight blocked' }
$d2bPreflight = Get-Content build/d2b/preflight.json -Raw | ConvertFrom-Json
if (-not $d2bPreflight.resources.admission.allowed) { throw 'Resource admission refused' }
$d2bRuntime = Invoke-RestMethod 'http://127.0.0.1:8022/api/v3/simulation/jobs/runtime'
$d2bStore = (Resolve-Path build/r1b/jobs).Path
if ($d2bRuntime.worker -ne 'locked' -or $d2bRuntime.store -ne $d2bStore -or $d2bRuntime.workspace -ne (Get-Location).Path) { throw 'Runtime/store/lease mismatch' }
$d2bExisting = Invoke-RestMethod 'http://127.0.0.1:8022/api/v5/simulation/jobs'
if (@($d2bExisting.jobs | Where-Object status -in 'QUEUED','RUNNING').Count) { throw 'Existing active Connected job; inspect before proceeding' }
@'
import asyncio
from scripts.preflight_nvmr_5k import validate_preset
from backend.app.connected_jobs import connected_readiness
config, _ = validate_preset()
asyncio.run(connected_readiness(config))
print('Both runtime graph identities verified; no job created')
'@ | .\.venv\Scripts\python.exe -X utf8 -
if ($LASTEXITCODE -ne 0) { throw 'Runtime routing readiness failed' }
```

Lệnh readiness D2b gọi OSRM probes, không tạo job; khác với preflight D2a hoàn toàn
offline. Xem resource policy/headroom lại nếu có thay đổi ứng dụng/container sau đó.
Sau khi mọi điều kiện trên đạt và owner đã phê duyệt, **POST đúng một lần**:

```powershell
if (Test-Path build/d2b/create-attempt.json) { throw 'A POST attempt already exists; inspect jobs/receipt, do not retry blindly' }
@{preset=$d2bPreflight.config.presetId; sha256=$d2bPreflight.config.presetSha256; attemptedAt=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -Encoding utf8 build/d2b/create-attempt.json
$d2bJob = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8022/api/v5/simulation/jobs' -ContentType 'application/json' -InFile 'config/scenarios/nvmr-connected-5k-hanoi-centric-v1.json' -TimeoutSec 600
$d2bJob | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 build/d2b/created-job.json
$d2bJob.id
```

Nếu POST timeout/lỗi transport: giữ attempt receipt, GET listing/status để xác định
job đã được tạo hay chưa; không tự POST lại. Giữ job ID ngay khi nhận được. Quan sát
status/memory của chính job đó; không tạo run nhỏ hoặc run lặp để thử/tune.
Audit completed artifact bằng existing tool, chỉ với ID đã nhận:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/validate_connected_api.py --job-id $d2bJob.id --base-url http://127.0.0.1:8022 --output build/d2b/completed-audit.json
```

Không bắt buộc assignment cả hai mode để biến valid all-unserved outcome thành lỗi;
đánh giá kết quả thực tế riêng, không sửa preset để đạt KPI. Lưu toàn bộ directory
của job, preset/manifest, source revision và preflight cho replay/Analytics/D2c.

**Kết luận: CONDITIONAL READY.** Offline contract, exact inputs, artifacts,
determinism và persistence đã xác minh trong phạm vi trên. D2b còn phụ thuộc owner
phê duyệt, runtime identities/worker source và resource headroom ở thời điểm chạy.
