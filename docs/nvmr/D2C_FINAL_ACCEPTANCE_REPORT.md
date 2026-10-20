# D2c FINAL — Portable artifact, offline replay và browser acceptance

Ngày kiểm tra: **20/10/2026**. Nhánh `feature/nvmr-m0-architecture`, baseline
`a8f9a0ec4375b14f9ff5fe40595bdef7a7e51d6b` cộng các thay đổi D2c chưa commit.

**D2_COMPLETE_WITH_LIMITATIONS.** Artifact nguyên vẹn, restore độc lập, replay
router-off, browser acceptance thiết yếu và Analytics đều **PASS**. Giới hạn
không nghiêm trọng: một laptop Windows/Chromium, mobile là viewport emulation,
benchmark ngắn; chưa chuyển sang máy vật lý thứ hai hoặc triển khai production.
Không còn blocker integrity/portability/replay được phát hiện trước D3.

## 1. Bảo toàn và inventory

Trước mọi chỉnh sửa code/runtime, đã kiểm tra `COMPLETED` và result SHA-256;
sau đó sao chép và xác minh từng file trước khi đóng ZIP v1. Job gốc giữ nguyên:
`build/r1b/jobs/660c52e17ec240b48f9c7340bd5b82da/`.

| Thành phần | Bytes | Trạng thái |
| --- | ---: | --- |
| input / prepared-input / status / event-log / result | 56.898.536 tổng | PASS, đủ cả 5 file, byte-identical |
| result.json | 54.528.521 | PASS |
| Detail MBTiles z6–13 | 136.577.024 | PASS |
| Overview MBTiles z0–5 | 1.679.360 | PASS |
| Frozen preset + manifest, Connected config | Trong research ZIP | PASS |
| Graph manifests CAR/MOTORBIKE, source/model provenance, backend source snapshot | Trong research ZIP | PASS |
| Runtime source/config + production frontend/font/icon/MapLibre-worker assets | ZIP runtime riêng | PASS |

Tất cả archive, manifests máy đọc được, logs, screenshots và dữ liệu nằm trong
**ignored `build/d2c/`**. Không đưa dataset lớn vào Git. Research manifest chứa
40 file records, per-file size/SHA-256, job/seed/schema/model, source revisions,
synthetic-data provenance và hạn chế diễn giải. Runtime manifest chứa 85 file
records, baseline revision và `dirtySource=true` để bảo toàn đúng D2c source/build.

| Artifact | SHA-256 |
| --- | --- |
| `nvmr-connected-5k-research-v1.zip`, 108.670.126 bytes | `16730517a16c96761ea2a371243b78df02bada98706ffa534f9f1ffcc4c2a523` |
| Research `manifest.json` | `8a79fcfa498b4911e75995ba3f79ae944e0a43af900306c6a6096979b3973c1a` |
| `d3-replay-runtime-v1.zip`, 2.509.490 bytes | `b7bbf611516de1433f50db7814487c0c2b5036741a60a266a243b6b396ed9726` |
| `runtime-manifest.json` | `343a88515a6a908264bf4b211ec7bcb084f5365ac5932b195c042185fa347335` |
| Original/restored `result.json` | `37812b5d55b1970c3ee57412a896002ca7418c855024b552846ba5e7c319d95a` |
| Detail MBTiles | `a27003b3bef79f2cc56d809e3874d1cbbf393962e3e986bf7fa1647056a34087` |
| Overview MBTiles | `90e4d485a9c12aaf9b02a7fb42ac982f7bdaec7684b61f2ed07c08954827ec62` |
| Frozen scenario request | `a37a44637fd829d25d7d494a520c5797e4857c996f53104d76f779decf1092df` |

Không kèm national/extracted PBF, OSRM graphs, Docker images, feature-build DB,
development caches hoặc JobStore khác. Seed vẫn
`nvmr-connected-5k-hanoi-centric-v1`, schema `gsm-nvmr-connected-scenario/v1`,
result `gsm-nvmr-connected-result/v1`, engine `heap-grid-connected/v1`.
Execution source revision D2b vẫn `292852cbbab8c05430ad6e60dc99827cce45c6ac`.

## 2. Independent restore và router-off replay

**PASS:** khôi phục ZIP vào **NEW** `build/d2c/restored/`, store
`build/d2c/restored/jobs/`; không ghi đè/move/delete job gốc. CLI từ chối destination
đã tồn tại, path traversal, duplicate ZIP members, symlinks và checksum sai.

Verifier GIS hiện hành dành cho build đòi cả PBF và feature DB. Đây là phụ thuộc
không cần thiết cho replay portable. D2c thêm verifier riêng cho published map:
inventory checksums, config/source identity, bbox/layers/zoom, original detail /
overview manifest và provenance chain. Build/live GIS verification giữ nguyên.

Đã xác minh 10 jobs gốc đều terminal, container IDs/mounts read-only trỏ đúng
checkout, port 5005/5006 đúng hai router Connected. Sau đó chỉ dừng:
`gsm-map-osrm-connected-car`, `gsm-map-osrm-connected-motorbike`.
Hai container ở trạng thái **exited**, TCP 5005/5006 không kết nối được khi audit.
Không xóa/recreate container, không dừng API 8000/8022 hay worker gốc.

**PASS với router thực sự tắt**:

- Completed discovery chỉ thấy run được restore; summary/global/by-zone/by-mode
  KPI bằng persisted result, selected route identity và geometry bằng dữ liệu lưu.
- Snapshot tại **0, 1, 900, 11438,387, 22876,774s** bằng phép chiếu độc lập từ
  full result; mỗi snapshot có đúng 5000 unique IDs, count/zone conservation.
- Selected vehicle `NVMR-CAR-hanoi-00007` ở 900s, booking
  `NVMR-BK-hanoi-000038`, position/routing identity và route bytes kiểm tra qua API.
- Fleet-state Analytics hoạt động từ timeline lưu; không gọi readiness/routing
  để tạo dữ liệu replay. Store restore có worker **offline**, không start worker.
- Middleware replay từ chối mọi write method trước handler (**405
  REPLAY_READ_ONLY**). Các request kiểm thử write-rejection dùng API restore,
  không tạo job; live create authorization D2b không được dùng lại.

API replay đầu tiên ở 8023 dùng existing FastAPI application. Kiểm chứng bổ sung
bằng source/runtime copy trong `build/d2c/d3-replay-runtime-v1/`, workspace khác,
không có thư mục `data` nguồn; map assets đọc từ research restore. API 8024 ở đó
trả snapshot 5000 xe, hai tile mẫu z6 và z0 có bytes khớp MBTiles. Cùng process
phục vụ static production frontend; browser đã mở run và chart trên chính origin
8024. Không cần Node/Vite, PBF, graph hoặc Docker cho setup này.

Evidence: `package-proof.json`, `router-off.json`, `offline-replay-proof.json`,
`independent-runtime-proof.json`, `runtime-package-proof.json`.

## 3. Core integrity và kết quả nghiên cứu

**PASS:** D2b result hash giữ nguyên xuyên suốt D2c; validators và các phép chiếu /
KPI độc lập khớp. Không sửa scientific outputs hoặc tái chạy simulation.

| Dữ liệu | Giá trị |
| --- | ---: |
| Unique vehicles | 5000: 2000 CAR / 3000 MOTORBIKE |
| Hanoi fleet / mỗi satellite zone | 3500 / 375 |
| Requests | 1750: Hanoi 1050, mỗi satellite 175 |
| Completed / unserved | 1229 / 521 |
| Assignments / events | 1229 / 7187 |
| Timelines / entries | 5000 / 8687 |
| Persisted route geometries | 2344 |
| Simulation duration | 22876,774s; arrivals horizon vẫn 900s |

Unserved giữ nguyên: 488 SEARCH_BUDGET_EXHAUSTED, 33 NOROUTE. Không diễn giải
bounded-search failure thành bằng chứng fleet toàn cục không thể phục vụ.
CAR requested/completed/unserved = 681/495/186, MOTORBIKE = 1069/734/335.
Mean pickup wait của assigned/completed cohort 111,014s; busy/online 4,841% trên
full simulation duration. Đây là synthetic scenario với static travel times,
không phải dữ liệu vận hành GSM thực tế hay kết quả nhân quả.

## 4. Browser acceptance với artifact thật

**PASS**, production build, foreground IAB Chromium 155, Windows / Intel Iris Xe,
DPR khoảng 1. Không dùng browser fixture. Browser chỉ nhận summary, snapshots,
aggregate chart và selected routes; không tải toàn bộ 2344 geometries.

| Kiểm tra | Kết quả |
| --- | --- |
| Desktop 1366×768 State A | PASS: 1 header, 4 cards 5000/2000/3000/1750, map và compact dock |
| Desktop State B | PASS: sidebar 546,55px / map 819,85px, khoảng 40/60; KPI strip biến mất |
| Desktop 1024×768 và 1920×1080 | PASS quick layout: 40/60, 1 header, không tràn ngang, chart 4 areas |
| Mobile 390×844 | PASS: scrollWidth 390; State A đầy đủ controls/cards; State B dùng existing 88% overlay responsive, chart 296,35×210px |
| Map lifetime/camera | PASS: một canvas lifetime trong toàn bộ captures A/B và resize; center/zoom trước/sau chuyển B→A ở zoom 6 khớp |
| Pan, zoom, các zone | PASS: pan bằng drag và instrumentation; zoom 6/11/16, toàn vùng chứa đủ 5000 xe |
| Zone/mode filters | PASS: chọn hanoi/CAR; giữ giá trị qua A/B, không đổi loaded-result KPI |
| Click icon State A | PASS: Analytics vẫn đóng; selected ID/route được giữ khi mở Analytics thủ công |
| Selected journey | PASS: browser chọn NVMR-CAR-hanoi-01053, booking NVMR-BK-hanoi-000904, trip 6965,3m / 606,1s; route nét liền và stops đã hiển thị khi router tắt |
| Seek/playback | PASS: seek 900s và gần cuối; 1/4/16/32/64×; 64× dừng đúng 22876,774s, state completed |
| Legend, attribution, tooltip | PASS: CAR/MOTORBIKE, OSM/Geofabrik/ODbL; tooltip chart ghi khoảng thời gian và xe trung bình |
| Alerts/console | PASS: không có alert hoặc console warn/error được ghi trong phiên QA |

Screenshots trong `build/d2c/`: desktop/mobile-state-a/b, desktop-selected-route,
chart-tooltip, portable-single-process-state-a/b, final-offline-5k. JSON evidence:
`browser-acceptance.json`, `additional-viewports.json`, `browser-measurements.json`.
QA instrumentation chỉ bật khi `audit=1`, nằm trong Analytics hiện có; không
thêm layout mode, không có fixtures hoặc clock mới.

## 5. Performance thực đo

Sáu captures **8s** trên cùng laptop, production build, real restored 5K,
foreground, pan nhỏ liên tục, không tests/build chạy đồng thời với capture.
Desktop browser viewport 1366×768; bảng ghi **map canvas viewport**.

| State / speed | Zoom | Map px | FPS xấp xỉ | Frame p95 ms | setData p95 ms | source-loaded lag p95 ms |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| B / 1× | 11 | 820×654 | 60,13 | 16,8 | 0,8 | 46,5 |
| B / 4× | 16 | 820×654 | 60,15 | 16,9 | 1,0 | 49,0 |
| B / 16× | 6 | 820×654 | 60,16 | 16,8 | 0,9 | 45,3 |
| A / 32× | 6 | 1366×605 | 60,12 | 16,8 | 1,0 | 47,4 |
| A / 64× | 11 | 1366×605 | 60,11 | 16,8 | 1,4 | 55,3 |
| Mobile B / 64× | 11 | 390×729 | 60,13 | 16,8 | 1,0 | 49,0 |

- 0 DOM markers, 6 sources / 19 layers, 0 long tasks trong sáu cửa sổ.
- JS heap lấy mẫu khoảng **93–176 MiB**; không phải total browser/GPU/OS memory.
- Selection-to-next-frame instrumentation khoảng 0,7–15ms; không bao gồm
  toàn bộ selected-route network latency.
- Cluster oracles đều PASS; hai captures zoom 6 kiểm tra **5000 unique leaves**
  và tổng đại diện 5000. Các zoom khác chỉ chứng nhận cluster/vehicles trong viewport.
- Initial status request → first snapshot receive complete khoảng **1719ms**.
- 189 distinct snapshot ResourceTiming entries: p50 **153,7ms**, p95 **292,5ms**,
  max **1722,6ms**. Bao gồm vài cold reload sau idle-cache eviction, không chỉ steady
  playback. Snapshot payload khoảng 1,2–1,34MB; summary khoảng 10KB.

**WARNING:** FPS ở đây là RAF cadence của embedded Chromium, không là bảo đảm
cho mọi browser/GPU/thiết bị. Mobile chỉ emulation trên cùng GPU. Chưa long soak,
chưa chạy toàn bộ 6h21m model time ở 1×. Initial-load metric không bao gồm thời gian
người dùng thao tác chọn run, và không đo full cold page/bootstrap. JSON parse /
validation CPU chưa được đo riêng (**NOT_RUN**). Các raw gaps có first-frame
timestamp artifact nhỏ; FPS báo xấp xỉ, không suy độ chính xác dưới một frame.
Không phát hiện vấn đề hiệu năng nghiêm trọng đòi rewrite scheduler/clustering.

Evidence: `performance-summary.json`, raw `browser-measurements.json` và bản JSON
download từ browser đã kiểm tra bằng nhau byte-content sau parse.

## 6. shadcn/ui Fleet-State Area Chart

**PASS:** sửa vấn đề stepAfter nối 120 selected instantaneous checkpoints bằng
API additive `?aggregation=time-weighted`; default checkpoint endpoint giữ nguyên.

Sweep toàn bộ persisted state transitions, tích phân từng trạng thái trên **120
khoảng thời gian bằng nhau**, chia cho độ dài khoảng để nhận số xe trung bình.
Step area hiện biểu diễn interval means; caption/tooltip ghi rõ đây là trung bình,
có thể lẻ, không phải trạng thái tức thời. Endpoint cuối lặp bucket cuối với độ
dài 0 để đóng area. Không dựng trạng thái/chuyển động trung gian giả.

| Trạng thái | Vehicle-seconds, khớp independent timeline integral |
| --- | ---: |
| OFFLINE | 22.876.774 |
| IDLE | 87.077.192,6 |
| ASSIGNED | 136.436 |
| ON_TRIP | 4.293.467,4 |

Mỗi bucket bảo toàn 5000 (floating tolerance 1e-6); integral từng state khớp
oracle trong 1e-3 vehicle-second. ASSIGNED + ON_TRIP khớp busy 4.429.903,4s.
3571 transition checkpoints và toàn bộ 8687 timeline entries vẫn nguyên trong
result gốc. Bucket means không thể hiện peak tức thời trong mỗi bucket;
nghiên cứu chi tiết dùng raw timeline. UI giữ shadcn/ui Area Chart, 4 stacked
areas, không animation; responsive desktop/mobile và MapLibre captures cùng chart PASS.

## 7. Export và regression

**PASS:** browser đã download Portable v1 JSON, legacy full JSON và 5 CSV của
existing HCM Saved Replay. Dùng chính artifact importer/canonicalizer và
experimentCsv hiện có: Portable bằng packaged demo, legacy payload bằng original,
cả 5 CSV exact. Digest `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`.
Đây là compatibility evidence, tách riêng với Connected 5K.

Connected hiện không có full-result browser export control: **NOT_APPLICABLE**;
full research artifact được xuất/restore bằng ZIP/CLI. Download JSON số đo QA PASS.
Không thêm bulk world download vào UI. Existing `npm.cmd run verify:replay` PASS
9 assets; script mặc định ghi browserExports NOT_RUN vì chỉ kiểm file. Browser
exports D2c được xác minh riêng trong `browser-export-verification.json`, không
ghi đè evidence A5 cũ.

| Kiểm thử | Kết quả thực thi |
| --- | --- |
| Backend focused/compatibility suite bên dưới | PASS 164; SKIPPED 1 real-OSRM opt-in; warning Starlette/httpx deprecation |
| `npm.cmd test -- --maxWorkers=1` | PASS 231 tests / 29 files |
| `npm.cmd run typecheck` | PASS |
| `npm.cmd run build` | PASS; existing large MapLibre chunk warning |
| `npm.cmd run verify:replay` | PASS 9 assets |
| `node build/d2c/verify_browser_exports.mjs` | PASS Portable + legacy JSON + 5 CSVs |
| Genuine restored 5K offline audit + browser | PASS, như mục 2–6 |
| `git diff --check` | PASS |

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -rs tests/test_d2c_replay.py tests/test_d2a_preflight.py tests/test_connected_domain.py tests/test_connected_analytics.py tests/test_connected_api.py tests/test_connected_artifacts.py tests/test_connected_acceptance.py tests/test_connected_recovery_io.py tests/test_connected_integration.py tests/test_m2.py tests/test_m3.py tests/test_regional_simulation.py
```

Tests dùng fixtures/temp stores, không tạo live job. Compatibility bao phủ HCM,
v3/M2/M3, v4 và Saved Replay; browser smoke Saved Replay PASS. Dedicated live
HCM/v3/v4 browser runs **NOT_RUN**, không bật router để làm lại simulation.

## 8. Files thay đổi

- `backend/app/replay_bundle.py`: safe paths, full inventory verification và
  portable map identity verification.
- `scripts/connected_replay.py`: verify/restore CLI, read-only existing API factory,
  optional same-origin static production frontend; không có worker/submit command.
- `backend/app/main.py`, `backend/app/connected_assets.py`: optional portable map
  root, live/build verifier mặc định giữ nguyên.
- `backend/app/connected_analytics.py`, `backend/app/connected_jobs.py`: additive
  exact time-weighted interval aggregate; checkpoint API tương thích.
- `frontend/src/lib/connected-analytics.ts`, `connected-fleet-chart.tsx`: validate
  fractional averages/interval bounds và nhãn/tooltip đúng nghĩa.
- `connected-replay-diagnostics.tsx`, `connected-workspace.tsx`: opt-in QA reuse
  existing map telemetry; presentation A/B, clock, dispatch và map lifecycle giữ nguyên.
- `tests/test_d2c_replay.py`, `tests/test_connected_analytics.py`, frontend
  `connected-analytics.test.ts`, `connected-presentation.test.tsx`: integrity,
  restore safety, write protection, integral conservation và chart semantics tests.
- Báo cáo này. Không sửa frozen preset, seed, input generation, scientific output,
  dispatch/routing semantics hoặc frontend legacy controls.

## 9. Handoff tối thiểu D3

Chuyển **cả hai ZIP** và đối chiếu checksum mục 1. Runtime ZIP đã chứa source D2c
chưa commit và frontend production build; không chỉ dùng baseline Git revision.
Restore trên máy khác chưa được thực thi trong D2c (**NOT_RUN**); việc chạy từ
workspace/runtime/store riêng trên máy này đã PASS.

Sau khi giải nén runtime ZIP vào một thư mục mới, đặt research ZIP cạnh thư mục
đó. Các lệnh PowerShell sau dành cho môi trường đích; không phải deploy đã thực thi:

```powershell
# Chạy tại root runtime đã giải nén; Python 3.11.9 đã được dùng trong acceptance.
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -X utf8 -m scripts.connected_replay restore ..\nvmr-connected-5k-research-v1.zip --destination research
.\.venv\Scripts\python.exe -X utf8 -m scripts.connected_replay verify research
$env:GSM_REPLAY_BUNDLE=(Resolve-Path research).Path
.\.venv\Scripts\python.exe -X utf8 -m uvicorn scripts.connected_replay:create_app --factory --host 127.0.0.1 --port 8024
```

Mở `http://127.0.0.1:8024/?runtime=simulation&scenario=connected&profile=meeting`,
chọn **Mở run → 5000 xe**. Demo ID **660c52e17ec240b48f9c7340bd5b82da**.
URL chọn Connected giữ nguyên; run discovery dùng restored store, không cần
hardcode một run ID mới vào frontend. Không bật `audit=1` cho bản demo thường.

D3 chỉ còn: chọn host/domain/TLS và cơ chế chạy process/backup phù hợp; chuyển
hai ZIP; verify/restore và smoke trên host đích. Static assets và `/api` cùng origin.
Có thể bỏ OSRM, worker và Docker hoàn toàn khỏi **completed replay** deployment;
Node không cần khi dùng static build đi kèm. Các chế độ live HCM/v3/v4 vẫn cần
dataset/runtime riêng nếu muốn cung cấp ở D3.

Không triển khai website trong D2c. Original API/worker được giữ nguyên; hai
Connected routers được để stopped sau router-off acceptance. Các API/Vite phụ trợ
QA đã dừng, giữ single-process portable replay 8024 để kiểm tra cục bộ.
Không stage/commit/push/merge/reset, không subagents/worktrees, không simulation mới.

**Kết luận cuối: D2_COMPLETE_WITH_LIMITATIONS.** Các điều kiện core đã được kiểm
chứng bằng artifact thật, HTTP replay router-off và browser; các giới hạn phạm vi
thiết bị/capture đã nêu không chặn bước triển khai D3.
