# M3 + M4 — Integration, validation và resource envelope

> **Latest follow-up18/10:** [M4_FPS_RESOURCE_FOLLOWUP.md](M4_FPS_RESOURCE_FOLLOWUP.md) cập nhật current state: ordinary1.000/5.000 admission0,5/0,75 GiB thay small-only floor; cả hai fresh runs completed, hashes/audits/contracts giữ correctness. Các checkpoint bên dưới là lịch sử trước follow-up. FPS1 root cause còn mở; chưa đạt điều kiện commit/push mới của owner.

> **Current review 18/10/2026:** xem [M4 performance/memory stabilization](M4_PERFORMANCE_MEMORY_STABILIZATION.md) và [validation summary](m4-performance-evidence/validation-summary.json). Small Live10/100 semantic hashes, route audits và HTTP→TS contracts PASS; immutable persisted5.000 hash giữ nguyên. Sau khi owner bật Docker, Hanoi modes READY và fresh1.000/250 completed; fresh5.000 vẫn hoãn theo reserve4 GiB. Theo yêu cầu mới của owner, Standard/Meeting startup và small physical admission floor là0,5 GiB; commit1 GiB, bounded small envelope giữ nguyên. Floor0,5 được unit-test, chưa stress thực tại boundary; scientific engine không đổi. Docker Inference manager failure trước recovery giữ trong evidence.

> **Review bổ sung UX 17/10/2026:** [M4 product remediation](M4_UX_REMEDIATION.md) ghi kết quả mới từ URL gốc, live10 mix5/5, real Hanoi basemap và browser30s/zoom. Các số liệu/checkpoints dưới đây là lượt tích hợp M3/M4 trước remediation; không được dùng FPS blank-map làm FPS với Hanoi basemap. Backend engine/contracts không đổi trong lượt sửa UX.

Ngày thực hiện: **17/10/2026**, Windows PowerShell. Baseline sạch `455abebe177be42e07b88ed4f34d4fecbef29b75`, branch `feature/nvmr-m0-architecture`. Hai development agents viết trong worktree riêng `gsm-map-sandbox-m3` và `gsm-map-sandbox-m4`, cùng detached baseline; Main tích hợp file/diff có kiểm soát về `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`. Không stage/commit/push/merge; không copy GIS vào worktrees.

## Contract và phạm vi

Contract thống nhất trước code: `gsm-simulation-snapshot/v1`, run/region/sequence/simulation time, stable vehicle IDs, CAR/MOTORBIKE, WGS84 `[lon,lat]`, states OFFLINE/IDLE/ASSIGNED/ON_TRIP. `total=offline+online`, `online=idle+assigned+onTrip`; moving là xe trên leg có chuyển động, không đồng nghĩa online/onTrip. Backend là nguồn state/lifecycle; frontend chỉ chiếu và render.

Snapshot không chứa geometry. `gsm-simulation-route/v1` có run/region/routeRef/routingIdentity; route geometry đọc từ immutable result của run khi chọn xe. Chế độ mới dùng API `/api/v3/simulation/jobs`; giới hạn/schema/model/ledger/Saved của v1/v2 giữ riêng. Completed-result playback là phạm vi MVP; không tuyên bố streaming worker state trực tiếp theo wall-clock.

## Tiêu chí đo được chốt trước benchmark

- Domain core: mọi run phải qua lifecycle audit và snapshot accounting checkpoints, không overlap/wrong mode/forced completion. Đo throughput/RSS/CPU riêng, không suy ra năng lực live OSRM. Mức fleet/online/load/seed phải lưu chính xác.
- Live OSRM: phải giữ graph/profile identity từng mode, snapshot KPI khớp final events; lỗi routing/cancel không xuất partial final. Ghi request/cell/cache/latency/preparation và resource; không suy benchmark pilot thành 5000 moving vehicles.
- Frontend: WebGL thật, low/mid/high zoom; mục tiêu tham khảo >=30 FPS, frame p95 <=33,4 ms và feedback selection <=200 ms khi không chờ route network. Ghi actual value cả khi không đạt. Source `setData` enqueue và worker completion phải phân biệt.
- Integrated: snapshot identity/type/counts/route envelope đúng, seek không tạo outcomes, run/region isolation, cancellation không resurrect. Kết quả browser/backend độc lập không thay thế test end-to-end.

## Máy đo và lịch tài nguyên

Intel Core i5-11320H @3.20 GHz, 8 logical processors; Windows 11 Home Single Language; 16.948.453.376 bytes physical visible RAM (~15,79 GiB). GPU được liệt kê bởi Windows: Intel Iris Xe và NVIDIA RTX 3050 Laptop; renderer browser sẽ ghi riêng, không mặc định browser dùng NVIDIA. Python 3.11.9, Node v24.18.0, npm 11.16.0.

Đầu phiên còn khoảng 3,73 GiB RAM khả dụng; disk D còn khoảng 42,14 GiB. Docker có ba router đang phục vụ, mỗi container limit 1 GiB, actual ban đầu HCM 25,17 MiB, Hanoi MOTORBIKE 58,16 MiB, Hanoi CAR 38,8 MiB. Không dừng service của người dùng, không rebuild/preprocess graph. Docker container RSS không bao gồm toàn bộ Docker Desktop/WSL/Windows overhead. Raw environment local: `build/m3-m4/environment.json`.

Hai agents chỉ chạy focused unit checks nhẹ đồng thời. Full backend, full frontend/build, domain high-load, live routing và WebGL benchmark chạy theo từng lượt. RAM khả dụng <2 GiB thì ngừng tăng quy mô; không kill process ngoài task. Các benchmark frontend phải tách khỏi workload backend đang stress. Resource snapshot trước mỗi nhóm được giữ trong evidence/ignored raw logs.

## Baseline thực chạy trước tích hợp

| Check | Kết quả mới |
|---|---|
| Backend không live | PASS: 158 passed, 6 skipped, 17,18 s |
| Backend `RUN_REAL_DATA=1` | PASS: 164 passed, 0 skipped, 39,56 s |
| Frontend `npm.cmd test -- --maxWorkers=2` | PASS: 159 tests / 15 files, 15,84 s |
| Browser HCM initial map | MapLibre canvas vẽ GeoJSON local, status OSRM kết nối; chưa coi như performance benchmark |

Raw logs `build/m3-m4/baseline-*.log`. Kết quả M2 lịch sử nằm riêng trong [M2 report](M2_IMPLEMENTATION.md); không sửa evidence cũ cho khớp số tests mới.

## Kết quả tích hợp thực chạy

Source M3/M4 đã copy có allowlist về checkout chính, kiểm target còn sạch trước overwrite. Hai agents thực sự làm song song trong worktrees; M4 có read-only cross-review M3. Khi cả hai agent gặp usage limit sau bàn giao source, Main tiếp tục sửa lỗi, chạy toàn bộ benchmarks và hoàn thiện reports. Worktrees còn giữ bản chưa commit để đối chiếu; **code chạy/kiểm thử cuối ở checkout chính**, không cần cherry-pick/merge để sử dụng.

| Check cuối | Trạng thái / bằng chứng |
|---|---|
| Full backend, `RUN_REAL_DATA=1 .venv/Scripts/python.exe -X utf8 -m pytest -q` | PASS **189 tests**, 47,40 s; 1 Starlette/httpx warning; 0 skipped |
| Full frontend, `npm.cmd test -- --maxWorkers=2` | PASS **167 tests / 17 files**, lần cuối 14,85 s |
| `npm.cmd run lint`, `typecheck`, `build` | PASS exit0; lint29 warnings, chunk>500kB; không warning-free |
| `npm.cmd run verify:replay` | PASS artifact integrity +9 assets; browser export roundtrip NOT RUN |
| `node scripts/verify-multimodal.mjs` | PASS typed browser M2 export/semantic comparison với evidence cũ |
| M3 focused/golden | PASS25 tests: FIFO, inclusive wait, same-time release, stationary pickup, schedules, modes, budgets, route confirmation, determinism, store, cancel, interruption, cross-process lock |
| Domain benchmark | PASS75 runs: 5 scales×3 workloads×5 seeds; max5000 fleet/5000 requests; [domain summary](m3-m4-evidence/domain-summary.json) |
| Live OSRM benchmark | PASS15 configs: 5 scales×3 workloads, **1 seed/config**; 5000/5000 burst38,360 s; [live summary](m3-m4-evidence/live-summary.json) |
| Browser independent | PASS15 final samples: 5 scales×zoom11/13/16, real WebGL, production build, 0 vehicle DOM markers; [raw](m3-m4-evidence/browser-benchmark.json) |
| API→worker→product TS validator | PASS100/20 và5000/1250; six sampled times/duplicate rejection/route envelope cả CAR/MOTORBIKE; [large proof](m3-m4-evidence/contract-verification-5000.json) |
| Running cancellation | PASS observed RUNNING, API ACK4,06 ms; 10 polls CANCELLED/result409; actual worker log CANCELLED; [proof](m3-m4-evidence/api-integration.json) |
| Live UI small | PASS100 fleet/20 completed, seek100, MOTORBIKE inspector/immutable route, Hanoi basemap; [image](m3-m4-evidence/live-motorbike-inspector.jpg) |
| Live UI large | PASS5000 fleet/1250 completed; persisted job10,644 s; selected CAR route, KPI parity; [summary](m3-m4-evidence/integration-summary.json) |
| Large API playback performance | PASS60,05 FPS, frame p9516,8 ms, source-loaded lag p9539,4 ms, ~4,6 snapshot updates/s; all5000 represented in viewport; [raw](m3-m4-evidence/browser-integrated-5000.json) |
| HCM regressions | PASS existing live route/Fleet/Booking/Voucher tests; production UI returned to HCM shell; legacy rendering/modules untouched |
| Hanoi CAR Voucher paired regression | PASS20 potentials/5CAR, repeat2 semantic equality, existing `check_experiment` lifecycle/common-input/ledger audit; Baseline14/Treatment18 completed in this synthetic seed; [proof](m3-m4-evidence/hanoi-car-voucher-regression.json) |
| Saved HCM v1 after integration | PASS production sample checksum/assets, seek500→play505,2→pause while task API8013 connection failure confirmed; [image](m3-m4-evidence/saved-api-off.jpg) |
| GIS/profile preprocessing | SKIPPED deliberately: reuse verified graphs, no rebuild/extract/download needed |
| Live oracle / live multi-seed / soak / crash whole real job / mobile390 | NOT VERIFIED in this task; fixture oracle/process-lock/restart tests are separate evidence |

Final backend code did not change after full189 suite. Subsequent map/presentation fixes were followed by full frontend167 tests/lint/typecheck/build. Saved/M2 validators were executed against their unchanged source; historical M2 evidence was not rewritten. All test services created by Main (API8013, worker, Vite preview5184 and QA tab) were stopped after verification; the three original OSRM containers were left running.

## Measured envelope và interpretation

Domain fixture: 5000 fleet=2000CAR+3000MOTORBIKE; workloads low/typical/burst use online25%/80%/60%, requests2%/25%/100% of fleet, horizon900 s, burst arrivals in first45 s, max wait300 s. 5 seeds/config. Worst5000 burst1,674 s, peak process138,60 MiB; min free3,579 GiB. Đây là synthetic recorded travel, không phải OSRM throughput.

Live direct engine: same workload matrix, seed `m3-live-0`, routers reused, new Python/hash/travel cache per process. 5000 low100 requests3,453 s, typical1250 requests10,214 s, burst5000 requests38,360 s/33,00 CPU s. Peak146,11 MiB, min free3,219 GiB. 100 burst có8 unserved, 500 burst3 unserved; các run khác served toàn bộ. PASS nghĩa lifecycle/accounting đúng và outcomes trung thực, không yêu cầu service rate100%. Chưa có live variance năm seeds hoặc 100% online/fixed-demand series. Wall direct engine không bao gồm ghi full final JSON của benchmark; persisted worker job được đo riêng.

Shortlist oracle fixture200 dispatch samples: winner recall90–95%/seed, feasible miss0, maximum regret29 s; Table cell savings59–62,6%, HTTP query savings0% hoặc -2,5% khi expansion cần query thêm. Không suy heuristic thành global minimum ETA hoặc kết luận service outcomes luôn tương đương exhaustive. Grid hiện lấy prefix ID trong occupied cells gần nhất; đây không phải true closest-K trong mỗi cell.

Frontend production: Chrome155/ANGLE Intel Iris Xe D3D11, viewport1280×800/canvas920×658/DPR1, local fonts/workers, blank basemap cho independent matrix. Warm5s capture/zoom, pan nhẹ, fixture10Hz; ở5000 có1833 moving trong fixture, không phải5000 moving. Final5000 FPS59,90/60,02/59,91, frame p95≈16,9 ms, source-loaded lag p95≤51,4 ms, JS heap end-sample max≈69,96 MiB, submit p95≤0,9 ms. Low zoom full-fleet cluster leaves/types/IDs PASS; high zoom zooms vào active vehicle và chỉ visible subset. RAF cadence không phải GPU completion, heap sample không phải RSS/VRAM hoặc leak certificate.

Integrated real5000 playback có5000 total/1000 offline/4000 online; tại100 s idle3882/onTrip118/moving118, khớp backend snapshot. 1250 requests completed là final outcome, không được hiển thị như số trips đã hoàn tất ở time100. Worker đã hoàn tất trước playback; bài đo không chứng minh simultaneous high-load worker/router/browser streaming. Live graph identity được giữ đúng và selected route từ immutable run store, không gọi re-route.

## Sửa lỗi và hạn chế còn lại

Đã sửa: progress scan history thành terminal counter incremental; thread-safe final cache; recoverable Table422 expansion; strict counts/provenance validators; failed-cancel polling restart; không tải cùng snapshot liên tục khi pause; native string feature ID promotion/fallback; numeric cluster label cast; guard không chấp nhận FPS viewport trống; xóa benchmark preview cũ khi tạo/reset session. Unit tests và browser bắt được những boundary tương ứng. Lượt browser đầu không có visible features giữ ở `browser-initial-invalid.json`, **không tính PASS**.

Chưa có in-progress durable event journal/resume: restart đánh INTERRUPTED và tạo job mới. Config pin ở enqueue; graph/generated inputs pin ở worker preparation, không phải thời điểm POST. Store thiếu auth/retention/disk quota, một worker/store. API whole-fleet polling/cached full result có thể giới hạn nhiều clients; chưa delta/stream. Graph/service không được thay trong run. Route-network/actual-inspector latency chưa có p95 SLO, mobile390 và browser chooser import/export roundtrip chưa rerun; không có soak/cold-start/leak guarantee. Lint/chunk warnings là technical debt, không phải blocker correctness cho pilot nhỏ.

## Resource report và lịch chạy

Full backend→full frontend/build→domain75→API smoke→live15→full regression→independent WebGL→integrated UI→Saved offline→final frontend checks được điều phối tuần tự, không hai stress workloads cùng lúc. Các focused agent unit checks nhẹ có chạy trong quá trình viết code. Không OSRM preprocessing. Khi browser mở làm headroom gần2 GiB, Main dừng chính API/worker của task trước tăng frontend load; không dừng containers/user processes.

Min available: domain3,579 GiB; live3,219 GiB; browser exploratory/initial full matrix2,464 GiB; final repeated matrix2,566 GiB. Task không có mức fleet bị dừng do RAM. Đây không phải tuyên bố máy16GB luôn đủ cho mọi dataset/load/browser/user background apps. Docker RAM là snapshots trước/sau (~HCM25/CAR41/MOTORBIKE59 MiB), chưa đo continuous router peak/WSL overhead/swap/VRAM. CPU/Python RSS có sampler0,05 s và OS lifetime peak; browser JS heap/cadence được đo trong page. Raw logs/resources giữ trong ignored `build/m3-m4`; validation manifest giữ hashes để đối chiếu.

Một checkpoint khi mới mở browser còn khoảng2,03 GiB available (ngoài valid final capture windows); Main dừng chính API/worker trước tăng tải frontend. Docker snapshot cuối task HCM25,29/CAR41,86/MOTORBIKE60,98 MiB; không tính thành Docker Desktop tổng RAM. [Validation manifest](m3-m4-evidence/validation-summary.json) lưu21 source hashes, command/log identities, resource snapshots và45-file commit allowlists. Thay đổi cuối chỉ làm nhãn “Kết quả cuối run” rõ hơn; build/typecheck được chạy lại PASS sau nhãn này, rendering/domain logic không đổi so với measured run/full167 suite.

## Quyết định kỹ thuật

GO phát triển, GO nghiệm thu toàn milestone và GO vận hành rộng là ba phạm vi khác nhau. Bảng dưới không phải approval gate hành chính; không cản tiếp tục công việc hợp lệ.

| Milestone | Decision | Evidence | Blockers / giới hạn | Recommended Next Action |
|---|---|---|---|---|
| M3 | CONDITIONAL GO cho nghiệm thu rộng; GO MVP/workloads đã đo | engine/jobs/cancel/golden189 tests;5000 live burst PASS | live1 seed/config, oracle chỉ fixture; journal/quota/soak chưa có | thêm live exhaustive sample+5seeds, crash/restart/retention soak |
| M4 | CONDITIONAL GO cho nghiệm thu rộng; GO render5000 trong setup đã đo | final15 WebGL samples+cluster oracle+live inspector | warm5s/blank-map matrix; chưa soak/mobile390/cold/network latency SLO | soak+basemap large scene+interaction latency/mobile |
| M3+M4 | GO completed-result playback MVP100 và5000; CONDITIONAL GO vận hành nhiều clients | real UI job5000/1250, KPI/route identity/TS validators | không streaming, không concurrent worker+browser stress | lưu benchmark lặp/cancel+seek under load, API transfer profiling |
| M5 | GO bắt đầu multimodal Voucher pilot nhỏ | separate mode routing, service model, legacy paired ledger preserved | choice model/paired multimodal chưa triển khai; assumptions cần version | pilot5–10 xe/NO_BOOK–CAR–MOTORBIKE, common-input/zero-policy controls |
| M6 | CONDITIONAL GO framework; NO-GO kết luận nghiên cứu mới | reproducible inputs/metrics/event results/seed framework | chưa multi-seed multimodal outcomes/estimand/uncertainty | định nghĩa KPI/window/denominator, paired seeds và sensitivity |
| M7 | CONDITIONAL GO bắt đầu single-host packaging; NO-GO public production | CLI API/one worker/local routers chạy thật16GB | auth/quotas/retention/backup/process supervision/deploy audit còn thiếu | đóng gói pilot nội bộ có resource/health/rollback; không deploy tự động |

Ưu tiên tiếp: live dispatch oracle+multi-seed/soak nhỏ song hành thiết kế M5 pilot, không chờ5000 moving. M5 có thể dùng hai workstreams choice/pairing và frontend contract nếu contract đã chốt; chưa cần thêm nhiều agent.

## Chạy lại và Git review

Hướng dẫn đầy đủ PowerShell ở [README](../../README.md#m3m4--jobs-và-bản-đồ-đội-xe-lớn) và hai reports. Các lệnh đã thực chạy gồm CLI benchmark, worker/API/preview, validators và test suites. `pipeline.py serve` là hướng dẫn reuse từ source M2; phiên này reuse containers đang chạy nên không cần thực thi lại serve hoặc preprocessing.

Live matrix đúng workload đã đo:

```powershell
foreach($n in 100,500,1000,3000,5000) {
  foreach($w in @(@{name='low';online=.25;ratio=.02},@{name='typical';online=.8;ratio=.25},@{name='burst';online=.6;ratio=1})) {
    $count=[Math]::Max(2,[int][Math]::Round($n*$w.ratio))
    .\.venv\Scripts\python.exe scripts/benchmark_simulation_live.py --fleet-size $n --booking-count $count --online-fraction $w.online --workload $w.name --seed m3-live-0 --output "build/m3/live-rerun-$n-$($w.name).json"
    if($LASTEXITCODE -ne 0) { throw 'Dừng benchmark, kiểm tra log/RAM; không tăng tải' }
    $r=Get-Content -Raw "build/m3/live-rerun-$n-$($w.name).json" | ConvertFrom-Json
    if($r.resources.minimumAvailablePhysicalBytes -lt 2GB) { throw 'RAM guard: không tăng tải' }
  }
}
```

Đề xuất4 commits theo thứ tự: M2 report; M3 backend/scripts/tests/report; M4 frontend/tests/report; integration validators/README/evidence/review. M3 build/test độc lập; M4 cần API contract từ commitM3 trước. Không stage/commit trong worktree agents: main checkout đã có mọi file. Không stage build/data/graphs/node_modules/.agents hoặc artifacts cache; không có user-owned tracked diff từ lúc bắt đầu. Chưa có staging/commit/push/merge do Codex thực hiện. Kiểm `git status --short`, `git diff --stat`, `git diff --check`, `git ls-files --others --exclude-standard` trước allowlisted add; sau mỗi add xem cached check/stat/name-only/**full diff** trước Owner tự commit.

## Kiểm chứng product integration và Hanoi basemap — lượt remediation 17/10/2026

Luồng hiện tại: URL gốc → menu **Mô phỏng quy mô lớn**, cùng header/navigation GSM; deep link vẫn tương thích, Back/Forward không reload trang. Hanoi basemap local mặc định bật trước job; readiness kiểm năm geographic assets, lỗi assets khác lỗi jobs/OSRM. Form có mix tùy chọn (kể cả10 xe5 CAR/5 MOTORBIKE), demand/seed, run opener và metadata immutable; KPI playback tách khỏi final run. Developer tools thu gọn, blank background opt-in. Clock subscription30Hz chỉ ở dock; map instance được giữ qua run/fixture/seek.

Backend regression mới **189 PASS**, frontend cuối **174 PASS/19 files**, lint33 warnings / 0 errors, typecheck/buildPASS; Saved checksum9 assets và browser sample seek500PASS. LiveM2run(write=False)20/20 PASS, không ghi đèevidenceM2. FreshM3small 10 xe/20 requests20 completed; fresh5.000 xe (2.000 CAR/3.000 MOTORBIKE)/1.250 requests1.250 completed, worker 11,080 s, không có routing request failures. Snapshot tại giây 100: total5000/offline1000/online4000/idle3861/assigned1/onTrip138/moving139. Current/provenance/TSvalidator/cancel409 được kiểm riêng.

**Browser mới có Hanoi basemap ON:**100 fixture59,53–60,00FPS;1.000 fixture57,80–59,29FPS (mỗizoom30s);5.000 fixture sau táchclock48,19–54,91FPS,p95 tới 49,9 ms;API thật5000playbackzoom 11/30s56,97FPS,p95 16,9 ms.8 sources / 15 layers/0 DOM fleet markers; cluster oraclePASS,zoom 11đủ 5.000 xerepresented. Canvas764×543 trên1280×800Chrome155/IrisXeANGLE-D3D11. Không so ngang FPSblank/canvas920×658/5s trước đó. Táchclock chưa chứng minh cải thiện đồng đều; giữ cảraw metrics trước/sau.

Root/navigation/pre-job map/live 10/live 5.000/play-seek-selection-focus/Back-Forward/mobile390 đều cóbrowser evidence. MobilepageWidth390/canvas373×358, mộtcanvas; mở lạirun 5.000 vàfocusMOTORBIKE. Faultproxy riêng kiểm503jobsAPI,404assets+retry,QUEUED12s,FAILEDrouter,INTERRUPTED,CANCELLED; **physical whole API/worker/routershutdown và real hard crash vẫnNOT VERIFIED**, không dừng Owner services để tạo lỗi. RealcancelAPIvàrealCANCELLED/FAILED UI mở từstore đã kiểm riêng. QAports8014/5185 đã dừng; Owner8013/5183/router5000–5002 giữ nguyên.

Quyết định: **GO MVP local cho luồng sản phẩm đã thử**, **CONDITIONAL GO M4 ở quy mô5000 nếu yêu cầu frame/soak ổn định hơn**, **GO bắt đầu M5 pilot nhỏ**, **NO-GO production**. P0blankmap/navigation đã xử lý; cònP1framejank/profiling/soak/worker heartbeat/physicaloutages, P2chunks/lint/co-locatedpicking. Không triển khaiM5model và không thay backendM3/routing/Voucher/Saved.

Chi tiết không rút gọn (RCA,actions,rawmetrics,limits,commands,Gitallowlists): [M4_UX_REMEDIATION.md](M4_UX_REMEDIATION.md). [Manifest evidence mới](m4-ux-evidence/validation-summary.json). Số liệu các sections bàn giao trước được giữ nguyên như lịch sử.

## S0/S1 — runtime và selected-trip integration, 17/10/2026

Kết quả mới ở [S0_S1_IMPLEMENTATION.md](S0_S1_IMPLEMENTATION.md), evidence namespace `s0-s1-evidence/`. Không sửa các con số/claims lịch sử bên trên. Audit Live nhỏ/lớn không phát hiện lỗi backend projection trong phạm vi sampled geometry; đã bỏ chord interpolation của selected ring frontend. Thêm endpoint selected booking versioned, runtime/store/lease identity và launcher an toàn, local silhouettes/native symbols, pickup/trip routes và markers đúng lifecycle. Snapshot v1/M3 dispatch/M2 graphs/Voucher/Saved giữ compatibility.

Đã thử actual API502/worker offline/recovery trên store/process riêng; không dừng Owner8013/5183/worker/routers. Bản mới dùng8015/5186 vì API Owner đang chạy chưa reload source Python. Hanoi Core5.000 là stress scenario, không đại diện NVMR distribution. GO phát triển R1/M5 nhỏ khác GO nghiệm thu regional coverage, research claims hoặc production; xem bảng quyết định S0/S1 mới và các NOT VERIFIED.

### Bổ sung sau tiếp tục phiên — 17/10/2026

Xem phần G/H/J của [S0_S1_IMPLEMENTATION.md](S0_S1_IMPLEMENTATION.md) cho kết quả cuối: 181 frontend PASS và fix depot identity; backend194/M2 live PASS trước interruption. API8015, shared-store worker, Vite5186 đã được launcher start lại; Docker/OSRM hiện offline và cần khôi phục trước run mới. Các kết quả runtime Owner đang chạy trong đoạn trên mô tả thời điểm QA trước interruption, không là trạng thái hiện tại.

Performance cuối chưa đạt nghiệm thu ổn định: Live5.000 có render-idle timeout và cadence thấp; fixture100 cùng phiên cũng≈1FPS dù document visible. Giữ raw captures và không khẳng định root cause. NO-GO cam kết ≥30FPS/5.000 hoặc soak hiện tại; GO phát triển chức năng/mẫu geometry đã kiểm và R1/M5 scope riêng. Không thay đổi con số lịch sử trong report.
