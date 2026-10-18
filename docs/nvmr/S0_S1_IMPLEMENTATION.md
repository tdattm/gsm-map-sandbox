# S0 + S1 — Runtime reliability, route fidelity và trip tracking

> **Latest follow-up18/10:** [FPS/resource follow-up](M4_FPS_RESOURCE_FOLLOWUP.md) ghi startup floor0,5 GiB cho mọi launcher profile, routine jobs tới5.000 xe dùng0,75 GiB physical floor, API/worker/profiler cùng policy; không sửa S1 geometry contracts.

> **Bổ sung 18/10/2026:** [Performance/memory stabilization](M4_PERFORMANCE_MEMORY_STABILIZATION.md) mở rộng launcher với Standard/Meeting/Benchmark, fresh preview identity, router selection và scoped stop receipts; tách service startup reserve khỏi simulation admission, thêm available/commit diagnostics. S1 CAR/MOTORBIKE directed route regression đã rerun PASS, không thay geometry/lifecycle contracts. Xem Current Verified State trước khi dùng readiness/FPS lịch sử bên dưới.

Ngày kiểm chứng: **17/10/2026**, Windows PowerShell, checkout `D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox`, branch `feature/nvmr-m0-architecture`. Báo cáo ghi kết quả thực thi mới; không sửa số liệu lịch sử M2/M3/M4. Demand, booking, ETA và positions là mô hình nghiên cứu, không phải vận hành/GPS/traffic GSM thực.

## A. Executive summary

S0 bổ sung launcher nhỏ, kiểm service identity/PID/proxy/shared store, worker lease và thông báo API/worker/router/domain riêng. S1 bổ sung local silhouettes ô tô/xe máy/người/pickup/flag, native symbols cho fleet lớn, selected-booking detail API hai chặng, filter/tìm ID, chọn xe trùng anchor, focus trip và progress đúng simulation time. Snapshot v1, routing graphs, scientific outcomes, dispatch và Voucher/Saved contracts được giữ nguyên.

Audit trước sửa trên completed live job5.000:12 assignments/192 active samples CAR/MOTORBIKE, maximum deviation **7.212955998842155e-10 m**, tolerance **0.02 m**, không vi phạm. Không tìm thấy lỗi backend projection trong phạm vi đo. Lỗi frontend có thật: selected ring nội suy chord giữa snapshots; đã bỏ nội suy, dùng đúng authoritative position. Không thêm chuyển động giả để làm hình ảnh mượt.

Fresh UI-created run **d944b4be727e46ae8a6a580ad66430cb**, seed **s0-s1-live-10**,10 vehicles/5 CAR/5 MOTORBIKE,20 requests,online1,horizon900s,maxWait300s,typical: **20 completed/0 unserved**. Audit20 assignments/288 active samples PASS. Existing run **088a063b0b0d46e1a8241fea277334a9**, seed `m4-ux-5000`,2.000 CAR/3.000 MOTORBIKE/1.250 requests,online.8 được reuse;40 assignments/440 samples PASS. Không chạy lại75+15 benchmark matrix vì engine/dispatch không đổi.

Backend regression mới **194 PASS**, RUN_REAL_DATA=1,43.88s, một Starlette/httpx warning. Frontend/lint/typecheck/build/replay và browser measurements cuối nằm phần G/H. Số M4 cũ189/174 giữ làm lịch sử. Chưa có production supervision/auth/retention, progress heartbeat, streaming worker state, smooth polyline animation, soak/leak certification, provincial GIS/OSRM hoặc M5 choice model.

## B. Root cause và ranh giới bằng chứng

### HTTP502 và worker

Owner báo Vite không kết nối FastAPI127.0.0.1:8013; khởi động lại đúng API làm Live hoạt động. Khi bắt đầu lượt này,8013/5183,worker và ba routers đều chạy. Không tái khẳng định Owner đang outage hoặc kết luận M3/OSRM hỏng.

Đã tái hiện **502 thật** trên môi trường riêng: launcher khởi động API8016/Vite5187/worker trên absolute store `build/s0-s1/runtime test jobs`; chỉ dừng đúng API do task tạo sau xác minh PID/command line. Vite5187 trả502; health/POST UI ghi **Backend FastAPI chưa kết nối**, bản đồ đã tải vẫn5/5. GET retry không gửi POST. Launcher restart khôi phục API/worker. Owner8013/5183/worker/store không bị dừng. Evidence `actual-api-offline.*`, `actual-api-recovered.*`, `isolated-worker-*.json`.

Chỉ dừng worker của isolated store, giữ API: runtime `worker=offline`; UI **FastAPI đã kết nối · Worker chưa chạy trên store API**. UI tạo job `b25e927802534e95a361cfeba111a72b`, QUEUED→Hủy job→CANCELLED, không final result. Đây là thử nghiệm thật, không injection. .venv wrapper+interpreter child có thể hiện hai python PIDs cùng command; OS lease chứng minh một worker giữ store, không đếm hai command lines thành hai workers độc lập.

MODE_NOT_READY thử thêm qua fault proxy: nhãn Graph/profile riêng, map vẫn hoạt động. NoRoute/NoSegment/ROUTER_UNAVAILABLE có semantic frontend tests. Không dừng router Owner để dựng physical outage; injected FAILED không phải OSRM failure của fresh job.

### Fixture và Live

Fixture có deterministic synthetic positions/motion, nhãn lớn **Fixture đồ họa — không phải hành trình OSRM**, không booking ID/route ref/pickup/passenger/dropoff nghiệp vụ. States trong fixture chỉ styling/load. Fixture mix40/60;1.833 moving trên5.000, không phải5.000 moving.

Live lấy completed immutable run; positions chiếu timeline+cumulative geodesic lengths trên stored OSRM geometry. Không fallback fixture/đường thẳng/CAR graph cho MOTORBIKE. `simulation.py` không sửa. Trước S1, selected ring RAF100ms nội suy tuyến tính có thể cắt chord qua khúc cua dù fleet positions đúng. S1 ring và selected silhouette dùng cùng authoritative point, chấp nhận bước nhảy theo snapshot cadence; không đổi routing/timing/outcomes.

### Icons/inspector và lỗi QA

Trước: circle+motorbike center dot, chỉ active route/ref. Sau: car mặt trước, motorbike hai bánh nhìn ngang, passenger người trong pin, pickup P, destination cờ; native symbols/selection ring. State badge R/P/T/× và offline opacity; không chỉ phân biệt màu. Selected silhouette riêng vẫn thấy khi cluster. Không quay side-view icon theo heading không có nghĩa; inspector chỉ ghi heading đoạn active khi có routeRef.

Browser bắt lỗi cleanup mới: parent Map đã remove style trước child passive cleanup, MapLibre.hasImage dereference style đã mất. Đã guard getStyle, abort loads và thêm regression test, kiểm navigation/style reload lại. Development console giữ HMR hook-signature errors lúc thêm hooks; normal QA sau reload ghi riêng.

Một capture fixture5.000 zoom13 có duplicate leaf giữa cluster và unclustered symbols; capture lỗi được giữ, không coi là correctness PASS. Điều tra/sửa oracle settlement và kết quả rerun nằm phần G, không nới assertion để bỏ qua vi phạm.

## C. Architecture và contracts

### Runtime

`Start-GsmDev.ps1 [-StatusOnly] [-ApiPort 8013] [-FrontendPort 5183] [-Store build/m3/jobs]`; không stop/rebuild flag. Kiểm local Python>=3.11/imports, Node phù hợp Vite/installed Vite, Docker CLI/Linux Engine và ports1024..65535 riêng. RAM>=2GiB mới start phần thiếu. Không auto start/recreate Docker; in recovery serve commands. Không kill process/preprocess/copy PBF/graph.

**GET /api/v3/simulation/jobs/runtime**, trước `/{id}`, trả `gsm-dev-runtime/v1`, application/workspace/resolved absolute store/apiPid/worker. Probe actual `.worker.lock` nonblocking: locked/offline/unknown; permission-denied OPEN không coi như live worker. Đây là lease, không heartbeat/progress guarantee.

Dev-only **GET /__gsm_dev** trả Vite application/workspace/pid/proxy. Launcher đối chiếu PID response với PID thực listen; không nhận Vite proxy như API. Store/path/proxy mismatch, service lạ hoặc API cũ thiếu runtime identity→refuse start/reuse, hướng dẫn inspect PID/port và restart chính terminal mình/cổng trống. StatusOnly báo warnings, không start. Missing services chạy hidden, logs/PID receipts timestamped tại ignored `build/s0-runtime/`; environment store/proxy chỉ set cho child rồi restore. Worker locked được reuse. Isolated startup thử cả store có space.

UI health chỉ GET,15s cadence+nút kiểm tra lại. QUEUED có thể worker bận. POST mất kết nối không auto retry vì chưa có server idempotency token; kiểm job/store trước tạo lại. Same-turn double submit được guard ref và test, không tuyên bố exactly-once network delivery.

### Selected booking

**GET /api/v3/simulation/jobs/{runId}/bookings/{bookingId}** đọc completed run qua existing one-result cache. **gsm-simulation-booking-detail/v1** gồm:

- run/region/booking/vehicle IDs,vehicleType/serviceType,original routingIdentity;
- request time,inclusive pickup deadline,assignment position;
- requestedPickup/requestedDropoff và snapped pickup/dropoff của trip geometry;
- pickupLeg/tripLeg:phase/ref/start/end/distance/duration;
- provenance immutable inputs/assignments/routes, không re-routing.

Không geometry/full history/dispatchCandidates/5.000 details trong response. UI lấy tối đa hai stored geometry qua route endpoint. Stationary pickup null ref/zero duration/distance, không vẽ đường giả. Old completed run đã lưu đủ đọc được ngay, không migration/rewrite. Thiếu stored inputs/timeline/route→HISTORICAL_DETAIL_UNAVAILABLE409; unknown booking404; not assigned409; result-not-final409; identity mismatch fail-closed.

Snapshot **gsm-simulation-snapshot/v1**, route **gsm-simulation-route/v1**, result/input v1 và legacy v1/v2 giữ compatibility. Không geometry trong full-fleet snapshots. Lookup selected booking scan bounded arrays của cached run, chưa cần database mới.

### Frontend và MapLibre

Validators kiểm version/run/region/vehicle/booking/type/graph identity,finite WGS84,leg timing/phase/deadline. Abort+selected run/vehicle/booking guard bỏ response cũ. Detail/route phụ thuộc immutable booking, không fetch mỗi tick. Pickup→ON_TRIP dùng cùng two-leg cache. Seek mở snapshot epoch mới; detail retry riêng không reset clock/POST. API cũ chỉ có active route vẫn đọc validated leg kèm thông báo details unavailable, không dựng pickup/dropoff.

Năm SVG local64x64 trong `frontend/public/icons/gsm/`, canvas rasterize addImage,pixelRatio2. Legacy React markers dùng cùng SVG qua MobilityIcon. Fleet stable promoteId:id,clusters/type totals,native symbols/state/selection; chỉ một booking có hai lines/hai endpoint symbols. **0 fleet DOM markers** trong large workspace.

Pickup nét đứt,trip nét liền,active dày/đậm. ASSIGNED: passenger tại snapped pickup+trip preview. ON_TRIP: pickup pin lịch sử,không người chờ; không passenger moving entity. IDLE/OFFLINE/fixture: không booking lines/stops. Filter/search tối đa12 results; click overlap tối đa30 candidate IDs, ID input chọn được toàn snapshot, không dropdown5.000 options. Focus xe/trip chủ động, không refit mỗi tick.

Icon loading có status/error/abort/style reload. Cleanup listeners/layers/sources/images nếu style còn; parent hủy map thì không hasImage. Full snapshots vẫn setData,chưa delta/stream. Telemetry/oracle nằm ngoài scientific engine; FPS window và post-freeze correctness tách rõ.

## D. Modules, trade-offs và bảo toàn

Backend mới `simulation_details.py`; runtime/detail endpoints trong `simulation_jobs.py`. Không sửa `simulation.py`, `simulation_worker.py`, booking/voucher/modes/profile/scientific config/ledger.

Frontend sửa simulation.ts/use-simulation.ts/simulation-map.tsx/simulation-workspace.tsx/App.css; thêm mobility-icon.tsx/simulation-map-icons.ts/simulation-runtime.tsx/năm SVG. Legacy sandbox-map/fleet-map/booking-map chỉ dùng shared icons; historical pickup không còn vẽ người chờ. api.ts thêm ApiError giữ message, expose status/code. Vite thêm identity middleware.

Scripts mới Start-GsmDev.ps1/audit_route_fidelity.py/validate_s0_s1_live.py; verify-simulation.mjs thêm HTTP→TS selected booking/two-leg checks; fault proxy thêm connection/runtime injection. Tests test_s0_s1.py/s0-s1-map.test.tsx/s0-s1-contract.test.ts, same-turn POST và fixture no-business-data assertions.

Trade-offs: snapshot movement có thể bước nhảy thay RAF smooth; side-view silhouettes không xoay; only active booking, completion clear details thay vì giữ chuyến cũ như hiện tại; overlap list bounded và có ID search, chưa full virtualized history UI. Không lấy ảnh đẹp bằng thay outcomes hoặc route.

Task-start copy/hash **99 inherited dirty/untracked files** tại `build/s0-s1/before/`; clean tracked files đối chiếu HEAD. Không reset/checkout/worktree/agent/stage/commit/push/merge/rebase. Historical evidence không sửa; M4/review append S0/S1 results. Existing completed results chỉ read/audit, không rewrite. Không có pre-task hash toàn ignored job store, nên không tuyên bố forensic before/after mọi job; current run hashes được ghi trong manifest.

## E. Independent geometric validation

Oracle không gọi backend projection helper/cumulativeMeters để đo. Tính haversine lengths riêng, query-centered equirectangular metric point–segment projection, closest distance/along distance/segment fraction; so along-distance với elapsed-time fraction. WGS84[longitude,latitude]. Tolerance **0.02m** là allowance số học trên cùng full GeoJSON, không phải độ chính xác GPS/OSM/snap; không nới theo kết quả.

Mỗi assignment lấy f=0,.001,.1,.25,.5,.75,.9,.999 cho mỗi active leg; kiểm vehicle/booking/type/state/leg/ref/graph và monotonic direction. Checkpoints before assignment,assignment,pickup arrival,completion được lưu. Completion có thể lập tức assign booking kế cùng timestamp, không ép IDLE sai. Seek tiến/lùi so equality cùng thời điểm. Report giữ sampled geometries một lần/ref; UI không tải5.000 full routes.

| Case mới | Assignments / active samples | Maximum deviation | Kết quả |
|---|---:|---:|---|
| Audit-before live5.000 |12 /192|7.212955998842155e-10m|PASS trước sửa backend, không sửa projection|
| Fresh live10,5CAR/5MOTORBIKE |20 /288|7.054187833483242e-10m|PASS,CAR128/MOTORBIKE160 samples,4 stationary pickups,7 reused vehicles|
| Reused live5.000 |40 /440|7.416478559680491e-10m|PASS,CAR216/MOTORBIKE224 samples; toàn run1235 stationary pickups/332 reused vehicles|
| Directed bridge CAR |2 /24|3.5830963447453786e-10m|PASS diagnostic buffer|
| Directed bridge MOTORBIKE |2 /24|5.160189149161101e-10m|PASS diagnostic buffer|

Directed script lấy OSM way9656730,Cầu Chương Dương,bridge=yes/oneway=yes từ M2 evidence nhưng query lại local validated routers trong lượt này. Thuận607.3m; ngược CAR2313.3m/MOTORBIKE2314.4m, geometry khác reversed-forward. Near-zero live leg1.3m/.1s mỗi mode và stationary pickup PASS; short samples/max deviation nằm directed summary. Đây là route direction/position fidelity, không chứng nhận pháp lý/road signs/topology toàn vùng.

**Ranh giới:** thử ban đầu qua normal LocalTravel bị INVALID_INITIAL_SNAP vì bridge ngoài operating_bbox,dù trong routing_bbox. Giữ fail-closed, không sửa config/threshold. Diagnostic adapter chỉ trong script,pin identity từ live_travels và raw local OSRM để kiểm projection trong routing buffer; không publish accepted M3 job hoặc expand regions. Fresh job trong operating box vẫn dùng nguyên runtime adapter.

Unit tests có directed L-curve CAR/MOTORBIKE, chord midpoint sai>50m bị oracle phát hiện, near-zero numeric segment, transitions/reuse/reverse seek. Snapshot API equality với projection vẫn đúng. Frontend tests xác nhận không RAF chord points,state passenger→pickup,idle clear lines/stops,native symbols,cleanup/remount/parent-remove.

Không có vi phạm Live trong sampled scope; không có backend minimal bug cần sửa. Lỗi chord frontend được xác định qua source+geometric counterexample và bỏ đúng nguyên nhân. Chưa khảo sát mọi OD/loop/self-overlap/OSM restriction hoặc mọi run lịch sử.

## F. Browser acceptance

Chrome/IAB/WebGL thật trên Windows. Root **http://127.0.0.1:5186/**→Simulation; task API8015/Vite5186,Owner8013/5183 giữ nguyên. Desktop1280x800,mobile390x844(capture raster có thể843px),Hanoi basemap ON. Screenshot không thay geometry oracle.

| Journey | Kết quả/evidence mới |
|---|---|
| Root/menu/pre-job map |PASS,5/5 Hanoi assets trước job,legacy menu còn hoạt động|
| Fresh live10 |UI POST→COMPLETED20/20,seed/job như phần A|
| CAR pickup t245 |GSM-00004/BK-000016,ASSIGNED;438.5m/57.5s,45.8%;dashed pickup+trip preview,passenger waiting|
| CAR ON_TRIP t400 |Cùng booking,pickup100%,trip47.7%,history pickup pin,không người chờ|
| MOTORBIKE pickup t330 |GSM-00008/BK-000017,ASSIGNED;1669.2m/157.2s,40.4%,motorbike identity|
| MOTORBIKE ON_TRIP t500 |Cùng booking,pickup100%,trip31.2%,flag/pickup semantics|
| Native click |CAR chọn GSM-00001/BK-000005;MOTORBIKE chọn GSM-00008/BK-000017;DOM snapshots riêng|
| Seek backwards |400→330 đổi CAR→MOTORBIKE,đúng assignment/route/progress,không stale response|
| Mobile |width390/pageWidth390,1canvas373x358,0 DOM markers;style reload giữ selected trip/icons|
| Actual worker offline |Isolated store,QUEUED→CANCELLED,banner API/worker riêng,map5/5|
| Actual API outage/recovery |Chỉ stop task API8016,Vite502 thật,FastAPI message,cached map giữ nguyên,launcher recovery PASS|
| MODE_NOT_READY |Injected FAILED,Graph/profile message riêng,map ready|
| NoRoute/router offline |Semantic unit PASS;physical Owner router outage NOT RUN|

Evidence `s0-s1-evidence/`:small-car-*,small-motorbike-*,native-*-click.txt,mobile-*,actual-api-*,worker-offline-*,injected-mode-not-ready.*. Native JPEG screenshots, không sửa pixels. Extended large/navigation/Saved proof bổ sung sau capture cuối:

QA sau khi tiếp tục phiên: native depot picking từng đưa mục `0` vào danh sách vì ID tile số của selected overlay được ưu tiên trước business ID. Đã thêm `promoteId: id`, ưu tiên `properties.id`, kiểm membership trong snapshot, deduplicate và giới hạn 30 trước callback. Browser click tại depot giữ đúng `GSM-00001`; chọn `GSM-00213` từ danh sách mở đúng idle inspector, không có booking/route giả. Test hồi quy tái hiện numeric overlay ID, unknown ID, duplicate và cap 30. Evidence `overlap-after-fix.*`; `cluster-before.jpg`/`cluster-after.jpg` ghi native click cluster mở rộng vùng hiển thị. Không suy screenshot thành chứng minh tất cả cluster leaves; oracle số liệu nằm phần G.

Source bàn giao: desktop 1280×800 mở CAR `GSM-00004`, t=245, `BK-000016`, pickup 45.8%, trip preview 0%, passenger/flag và hai nét tuyến. MOTORBIKE `GSM-00008`, t=330, `BK-000017`, pickup 40.4%, trip preview 0%, hai chặng đã load. Mobile 390×844: pageWidth=390, canvasWidth=373, inspector hiển thị hai progress bars, không tràn ngang; reload local map trở lại 5/5, selected vehicle/routes còn đúng. Evidence `handoff-car-pickup-desktop.*`, `handoff-motorbike-pickup-desktop.*`, `handoff-mobile-car.jpg`, `handoff-mobile-map.jpg`, `handoff-mobile-layout.json`. Viewport override đã reset, browser tab giữ lại cho Owner; `handoff-console-final.json` không có warn/error ở phiên clean cuối. Các lỗi development cũ vẫn được giữ.

HCM browser rerun mới:Single Trip route1.19km/119.3s,seek60;Fleet5 xe/13.59km,seek60;Booking5/20 seed hcm-booking-2026,selected BK-001 ở t100 dùng passenger.svg,t300 dùng pickup.svg sau pickup267.4s. Voucher Live5CAR/10 potentials seed s0-s1-hcm-voucher chuẩn bị cặp Baseline/Treatment và seek500 thành công; đây là regression UI/ledger model, không kết luận uplift. DOM/ảnh hcm-single.*,hcm-fleet.*,hcm-booking.*,hcm-voucher-live.* và hcm-passenger-semantics.json.

Saved HCM:task API8015 đã stop sau verify PID,proxy5186 target offline,Owner API8013/routers vẫn giữ;load sample static/checksum,seek500→play505.2→pause PASS,local map và shared car icons hiện đúng. Evidence saved-api-offline-proof.json,saved-task-api-stop.json,saved-hcm-api-offline.*. Lần click đầu trong dev session trả lại empty Saved view không alert; retry từ view ổn định load được. Chưa xác định nguyên nhân lần đầu, không quy cho backend/OSRM hoặc tuyên bố mọi transient đều được giải quyết. Browser chooser import/export roundtrip vẫn NOT VERIFIED.

## G. Performance và tài nguyên

Các capture trước khi bị gián đoạn và các capture sau khi tiếp tục phiên được phân biệt dưới đây. Không dùng kết quả cũ thay cho nghiệm thu hiệu năng source/môi trường hiện tại.

Máy mới được ghi lại trong `browser-environment.json`:i5-11320H,4cores/8logical,16.948.453.376bytes physical visible RAM,Python3.11.9; GPU browser **ANGLE Intel Iris Xe D3D11**, không mặc định RTX3050. Chrome155/IAB,desktop1280x800,DPR1,Hanoi basemap ON. Canvas fixture764x568,Live764x543; không gộp thành phép so causal icons-vs-circles với các capture M4 canvas/duration khác.

| Capture trước gián đoạn | Zoom / thời lượng | FPS | Frame p95 ms | setData submit p95 ms | source-loaded lag p95 ms | Long tasks | Correctness |
|---|---|---:|---:|---:|---:|---:|---|
| Fixture100 |11 /5s|57.71|17.0|0.2|19.7|0|PASS|
| Fixture100 |13 /5s|59.98|16.9|0.2|11.9|0|PASS viewport|
| Fixture100 |16 /5s|59.80|16.9|0.2|12.9|0|PASS viewport|
| Fixture5.000 |11 /30s|52.92|33.4|0.6|54.5|6|PASS,5.000 represented|
| Fixture5.000 |13 /30s|56.45|33.3|0.7|58.2|3|PASS viewport1.145 represented|
| Fixture5.000 |16 /30s|55.52|33.3|0.7|57.7|4|PASS viewport22 represented|
| Live5.000 |11 /30s|55.13|33.3|0.7|74.9|8|PASS,5.000 represented|
| Live5.000 |16 /30s|55.10|33.3|0.7|76.8|10|PASS viewport668 represented|

Các window30s trên được đo trước sửa glyph badge cuối:RomanⅡ/arrow→ nằm ngoài Unicode ranges Geist đóng gói,đổi thành **R/P/T/×**. Không đổi positions/lines/silhouettes/source cadence. Smoke sau đổi glyph trên source cuối5s/zoom11,13,16: **49.67/49.17/50.52FPS**,framep95 **33.4/33.4/33.5ms**,cluster oracle PASS,10sources/20layers/0DOM. Raw `fixture-5000-ascii-badge-smoke.json`; không gọi số30s là phép đo lại sau đổi glyph. Giá trịp95=33.5ms vượt soft reference33.4ms ở một smoke,không làm tròn thành đạt. Final Live30s bổ sung bên dưới.

Các rows trước gián đoạn ở bảng trên có **10 sources/20 layers/0 DOM fleet markers**, cluster leaves/count/type/unique IDs oracle PASS. Zoom11 chứng minh full fleet trong viewport; zoom13/16 chỉ visible region, không đếm symbols nhìn thấy như toàn fleet. Native symbols overlap được allow; selected native overlay không đếm thêm vehicle vào fleet oracle. Stable source/layer counts qua run/fixture/seek; map lifetime giữ trong từng workspace/capture group, không tuyên bố một lifetime qua intentional page reload/mode unmount.

Fixture source~10Hz,301 updates/capture30s; Live123 updates/~4.1Hz/capture. Live window t100→130.729 có selected MOTORBIKE chuyển pickup→trip; harness cuối window chọn first vehicle để đo callback→RAF, nên UI selection sau capture có thể là CAR. Callback→next-frame samples1–18ms không thay actual inspector/route-fetch SLO. Selected booking+hai route HTTP/validation một large sample **135.6ms**, sau harness CAR sample37.9ms; không p95,end-to-end render latency hoặc cold-network guarantee.

JS heap end-sample max **389.420.131bytes (~371.4MiB)** trong nhóm Live trước gián đoạn; fixture trước gián đoạn max387.103.735bytes. Đây không browser process RSS/VRAM/peak transient. Heap giảm sau GC ở các sample khác; không suy thành leak-free. Sampler200ms qua broader884.1s QA/idle/capture window ghi minimum available physical **2.403.893.248bytes (~2.24GiB)**, trên guard2GiB. Sampler CPU/RSS thuộc chính sampler, không browser; Docker snapshot không gồm toàn WSL/Desktop overhead. Không full tests/build/preprocessing/M3 stress trong timed captures.

**Oracle failure và sửa kiểm chứng:** capture `fixture-5000-symbols-pre-settle-fix.json` zoom13 ghi duplicate fixture-01282 giữa visible symbol và cluster leaf. Lượt đó còn19 layers ở phiên HMR trước reload, không dùng như final acceptance. Harness cũ pause rồi fixed wait250ms, không xác minh final snapshot clock/source/render cùng revision. Sửa:freeze trả target time,chờ snapshot khớp±.001s,source loaded+quiet>=250ms,rồi MapLibre idle với timeout fail-closed. Không bỏ uniqueness assertion hoặc nới geometry tolerance. Diagnostic zoom13 sau reload PASS,post-freeze657.9ms; final3zooms PASS,post-freeze~370–565ms. Raw lỗi và diagnostic đều giữ. Không có worker revision trace ở capture lỗi nên không khẳng định exclusive cause; barrier mới loại bỏ rủi ro read giữa index/render và final scope không tái hiện vi phạm.

Raw: `fixture-100-symbols-final.json`, `fixture-5000-symbols-final.json`, `live-5000-symbols-zoom11.json`, `live-5000-symbols-zoom16.json`; first100/first5000 và diagnostic giữ riêng. RAF khi pan nhẹ liên tục không phải GPU presentation profiler. Mức52.9–56.5FPS/p95~33.4ms đạt soft reference30FPS ở scope đo, còn long tasks/jank; **CONDITIONAL GO** cho cam kết rộng hơn. Chưa cold process restart,soak30–60phút,nhiều GPU/mobile performance hoặc simultaneous heavy worker+browser. Không suy fixture rendering thành operational GSM capacity.

### Capture sau khi tiếp tục phiên — không đạt nghiệm thu hiệu năng

Sau khởi động lại API/Vite, các phép đo mới trên cùng IAB/GPU/viewport cho kết quả không ổn định. Giữ nguyên mọi capture, không chỉ chọn lần tốt nhất:

| Capture sau resume | Thời lượng / zoom | FPS | Frame p95 ms | Oracle |
|---|---|---:|---:|---|
| Live 5.000, lần đầu |30s /16|28.90|49.8|FAIL: snapshot settled, render idle timeout|
| Live 5.000, lặp |30s /16|1.00|1017.0|FAIL: render idle timeout|
| Live 5.000, thêm visibility diagnostics |30s /16|1.19|1016.7|FAIL: render idle timeout|
| Fixture 100, đối chứng |5s /11|1.05|1016.5|PASS: 100 represented, 23 clusters, unique/type counts đúng|

Raw `live-5000-handoff-first-zoom16.json`, `live-5000-handoff-repeat-zoom16.json`, `live-5000-handoff-instrumented-zoom16.json`, `fixture-100-handoff-diagnostic.json`. Capture instrumented: visibility start/end `visible`, hiddenFrames=0, max frame gap≈1016.9ms. Việc browser được hiển thị và document visible không chứng minh compositor luôn foreground/unthrottled; cũng không đủ để kết luận nguyên nhân là throttling. Đối chứng 100 xe cũng có cadence khoảng 1Hz nên chưa có bằng chứng quy toàn bộ suy giảm cho fleet size hoặc SVG icons. Chưa có profiler trace phân biệt browser host/occlusion/scheduler/GPU/application. Không sửa outcomes, nới idle barrier hoặc bỏ oracle để tạo PASS.

Cả bốn giữ 10 sources/20 layers/0 DOM fleet markers. Live instrumented 31 source updates, 96 long tasks; full input source vẫn 5.000, nhưng **không chứng nhận rendered cluster correctness** ở window timeout. RAM khả dụng trước nhóm đo khoảng 3.1GiB; đây là point sample, không phải minimum theo toàn window. Không có tests/build chạy đồng thời trong các timed windows này. Visibility fields được thêm vào benchmark output; geometry, fleet cadence và layer definitions không đổi vì phép đo này.

**Quyết định cuối ghi đè kết luận performance tạm trước resume:** GO phát triển/kiểm tra chức năng trên mẫu đã ghi; **NO-GO nghiệm thu cam kết ≥30FPS ổn định hoặc cluster/render-settled ở 5.000 xe trong phiên hiện tại**. Cần profiling và chạy lại trong điều kiện foreground được kiểm soát, rồi soak. Các kết quả tốt trước resume vẫn là bằng chứng có thật với điều kiện riêng, không là bảo đảm hiệu năng hiện tại. Source không tự động được chứng nhận chỉ vì tests PASS.

## H. Regression và actual commands

Các nhóm tuần tự, không full backend/frontend build/OSRM preprocessing/M3 stress trong browser measurement window. Routers/graphs reuse. RUN_REAL_DATA bật trong full backend; không lấy số lịch sử làm kết quả mới.

```powershell
$env:RUN_REAL_DATA='1'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
Remove-Item Env:RUN_REAL_DATA
npm.cmd test --prefix frontend -- --maxWorkers=2
npm.cmd run lint --prefix frontend
npm.cmd run typecheck --prefix frontend
npm.cmd run build --prefix frontend
npm.cmd run verify:replay --prefix frontend
.\.venv\Scripts\python.exe -m pytest tests/test_s0_s1.py -q
node frontend/scripts/verify-simulation.mjs http://127.0.0.1:8015 d944b4be727e46ae8a6a580ad66430cb docs/nvmr/s0-s1-evidence/contract-small.json
node frontend/scripts/verify-simulation.mjs http://127.0.0.1:8015 088a063b0b0d46e1a8241fea277334a9 docs/nvmr/s0-s1-evidence/contract-large.json
```

Backend194PASS/1warning/43.88s bao gồm HCM/M2/live/Voucher/Saved/M3 cancellation/lifecycle/process-lock. New endpoint tests:final409,unknown booking,historical missing,immutable equality,snapshot v1 unchanged. Frontend final numbers/logs được ghi trong manifest; legacy workspace/navigation/stale responses,route provenance,fixture no-business-data,POST duplication,layers/pickup semantics/cleanup đều được test.

Saved verifier PASS:9 assets,digest `b4a87ee371f976f12f4da28791dffc66ebeb24352c1d664bf71851eb89c27433`. Không sửa checksum/artifact contract để thêm icons; Vite build đóng gói public icons riêng. HTTP→TS verifier nhỏ/lớn PASS:selected booking legs/metrics/identity/duplicate snapshot rejection/summary without history.

NOT RERUN:M2 profile58-case preprocessing,75domain/15live matrix vì graph/profile/dispatch không đổi. NOT VERIFIED:long soak,GPU context-loss torture,crash recovery actual running Owner worker,browser chooser import/export roundtrip,cold-cache whole-API-off Hanoi load. Low-RAM launcher rejection chỉ source-reviewed, không ép cạn RAM máy Owner.

Ignored logs `build/s0-s1/`:backend-tests.log,frontend-tests.log,lint.log,typecheck.log,build.log,saved-replay.log,focused-final.log,focused-frontend.log,contract-*.log,launcher-*.log. Một lần tooling log filename chứa colon verify:replay không hợp lệ Windows; verifier riêng sau đó PASS,saved-replay.log. Một lần Node version -e quoting lỗi PowerShell5,đã đổi --version/[version],rerun launcher PASS. Không che lỗi ban đầu.

### Kiểm tra bàn giao sau quota interruption

Source cuối sau sửa depot ID và thêm visibility diagnostics: **181 PASS / 21 files / 25.12s**; typecheck, lint, build và Saved verifier đều exit 0. Lint còn 39 warnings, build còn chunk >500 kB. Nhóm cuối chạy tuần tự (`frontend-final.log`, `typecheck-final.log`, `lint-final.log`, `build-final.log`, `replay-final.log`), tách khỏi timed browser captures. Lượt handoff trước đó cũng 181 PASS/75.73s nhưng có overlap tests/build; không dùng thời lượng đó làm benchmark hiệu năng hoặc tuyên bố mọi lượt kiểm thử đều tuần tự.

M2 live regression mới trước gián đoạn PASS (`m2-live-regression.json`, seed `hanoi-multimodal-m2`, 10 xe/20 bookings). Sau gián đoạn Docker Engine và toàn bộ listener cũ không còn chạy. Launcher đã khởi động lại API8015, worker đúng absolute store và Vite5186; health/lease/proxy verified, local GIS 5/5. Docker/OSRM hiện offline, được launcher báo riêng; không chạy lại full real-router suite và không tạo job Live mới để thay bằng chứng trước đó. Completed-run HTTP→TypeScript verifier nhỏ/lớn được chạy lại trên API hiện tại. `launcher-status-resumed.txt` và manifest ghi trạng thái bàn giao thực tế. Không dừng process Owner để đạt trạng thái này.

Delivery trên source gồm ASCII badges:frontend **180PASS/21files/16.82s**,lint **39warnings/0errors**,typecheck/build exit0,main chunk warning>500kB. Logs frontend-delivery.log/lint-delivery.log/typecheck-delivery.log/build-delivery.log. Source scientific/backend không đổi sau backend194 suite;focused S0/S1 sau sampled-geometry report5PASS. Saved verifier sau build PASS9assets;HTTP→TS nhỏ/lớn PASS. Các validation này tách khỏi browser performance windows.

## I. Reproducibility và hướng dẫn chạy

Seed/job/contracts phần A/C; full graph/profile/source/extract identities trong audit và HTTP contract evidence. CAR graph `a24d4957a01ceeb04a0de1ad680fe4c5dd51732a7b381d9368e249a65c1b29b5`; MOTORBIKE `fb97489d066397b11cb9178238cd56a5f52281bcf5711430bb7cf411496ca455`. OSM hash không phải traffic provenance.

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
# Chỉ khi router thiếu,kiểm named containers/ports,reuse graph,không build:
.\.venv\Scripts\python.exe scripts/pipeline.py serve --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile car --detach
.\.venv\Scripts\python.exe scripts/pipeline.py serve --region nvmr-hanoi-core --profile motorbike --detach
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -StatusOnly -ApiPort 8015 -FrontendPort 5186
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -ApiPort 8015 -FrontendPort 5186
Invoke-RestMethod http://127.0.0.1:8015/api/health
Invoke-RestMethod http://127.0.0.1:8015/api/v3/simulation/jobs/runtime
Invoke-RestMethod http://127.0.0.1:5186/__gsm_dev
```

Manual thay launcher,ba terminal tại root,không worker thứ hai trên locked store:

```powershell
# Terminal API
$env:GSM_SIMULATION_STORE=Join-Path (Get-Location) 'build/m3/jobs'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8015
# Terminal worker riêng,CHỈ khi runtime=offline trên cùng store:
.\.venv\Scripts\python.exe -m backend.app.simulation_worker --store build/m3/jobs
# Terminal frontend riêng:
Set-Location frontend
$env:GSM_API_PROXY='http://127.0.0.1:8015'
npm.cmd run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

Root5186→Simulation,10/5/20/online1/seed,chờ COMPLETED. Opener bookmark t245/GSM-00004 hoặc t330/GSM-00008. t0 xe rảnh là đúng, không coi thiếu route là lỗi. Fixture trong Developer Tools chỉ graphics; giữ basemap ON,đo5/30s,tăng tải chỉ khi RAM>=2GiB.

```powershell
.\.venv\Scripts\python.exe scripts/audit_route_fidelity.py --job-dir build/m3/jobs/d944b4be727e46ae8a6a580ad66430cb --limit 40 --output build/s0-s1/audit-rerun.json
.\.venv\Scripts\python.exe -X utf8 scripts/validate_s0_s1_live.py
```

Lệnh thứ hai diagnostic routing buffer,không accepted M3 bridge job và không nới operating_bbox. Clone Git không có ignored jobs/PBF/graphs; sampled routes,seed/config và hashes trong evidence hỗ trợ đối chiếu độc lập.

Terminal thủ công: hủy job nếu cần rồi Ctrl+C đúng terminal mình sở hữu. Hidden launcher: xem receipts/logs, runtime.apiPid hoặc __gsm_dev.pid, đối chiếu Get-NetTCPConnection/Get-CimInstance trước Stop-Process. .venv receipt PID có thể wrapper, listener PID mới là API thật. Không stop worker đã reuse từ Owner. Source Python cần restart API, launcher không --reload; Vite HMR không reload Python. Trong QA trước gián đoạn, API Owner8013 được giữ; sau resume8013 không còn listener và task chỉ start8015/5186. Không spawn thêm vào port đã có service.

```powershell
# Ví dụ stop CHỈ task API8015 sau xác minh,không áp dụng Owner8013:
$taskApi=Invoke-RestMethod http://127.0.0.1:8015/api/v3/simulation/jobs/runtime
Get-CimInstance Win32_Process -Filter "ProcessId=$($taskApi.apiPid)" | Select-Object ProcessId,CommandLine
Get-NetTCPConnection -LocalPort 8015 -State Listen | Select-Object OwningProcess
# Sau khi hai PID và source/store đúng:
Stop-Process -Id $taskApi.apiPid
$taskVite=Invoke-RestMethod http://127.0.0.1:5186/__gsm_dev
Get-NetTCPConnection -LocalPort 5186 -State Listen | Select-Object OwningProcess
Stop-Process -Id $taskVite.pid
```

Không stop all-python/all-node. Router chỉ dừng khi không phiên khác dùng,đúng tên đã kiểm:docker stop gsm-map-osrm-hanoi-car (motorbike/HCM riêng),không remove volumes/graphs;launcher không tự làm. QA8016/5187 dọn sau thử;final service inventory trong manifest.

## J. GO/NO-GO và remaining priorities

| Phạm vi | GO phát triển | GO nghiệm thu / giới hạn |
|---|---|---|
| S0 runtime local |GO|GO verified/reuse/fresh startup/isolated outage-recovery đã thử;không production uptime/supervisor|
| S1 route fidelity |GO|GO sampled Live+directed diagnostic;không chứng nhận mọi OSM OD/traffic/legal behavior|
| S1 inspector/icons |GO|GO small/large/desktop/mobile đã ghi,immutable two legs,no fabricated trips,bounded search/picking|
| M3/M4 MVP local |GO tiếp tục phát triển và chức năng đã kiểm|NO-GO nghiệm thu ≥30FPS ổn định/cluster settlement 5.000 ở phiên hiện tại; các capture sau resume không đạt, cần profiling/rerun/soak|
| R1 Regional Expansion |GO task thiết kế/triển khai riêng|NO-GO coi5.000 Hanoi stress là toàn NVMR/ready tỉnh mới;cần GIS/graph identity/distribution assumptions/regression theo vùng|
| M5 pilot |GO phát triển5–10 xe trong coverage hiện có,version/common-input assumptions rõ|NO-GO nghiệm thu M5/commercial/production;chưa choice/paired multimodal model/calibration|
| Production |NO-GO|Single-host research PoC,thiếu auth/quotas/retention/recovery/soak/operational data|

P0 trong scope: không còn known fabricated-route/backend-offline-as-engine-failure issue sau fixes/QA; không tuyên bố mọi bug biến mất. P1: điều tra cadence≈1Hz cả fixture100 và Live5.000 sau resume, render-idle timeout, jank/full snapshots/profiler/soak; worker progress heartbeat/supervision; idempotent POST nếu muốn auto retry; broader live geometry/dispatch oracle. Docker hiện offline là điều kiện runtime cần khôi phục trước tạo run mới. P2: lint/chunk debt, overlap paging khi cần, heading-oriented vocabulary nếu semantics đáng tin, historical completed-trip viewer (hiện active booking).

### Final acceptance status

- PASS: launcher/API/frontend/worker diagnostics và recovery commands; phân biệt FastAPI offline, worker lease và routing readiness.
- PASS: Fixture có nhãn riêng và không fabricated business trips; Live geometry độc lập đạt tolerance 0.02m trên các mẫu đã liệt kê.
- PASS: CAR/MOTORBIKE silhouettes, passenger/pickup/dropoff, active selection, immutable booking detail, hai legs và progress theo simulation clock; idle/offline không có active route giả.
- PASS trong phạm vi ghi nhận: native layers/clustering/picking, HCM/M2/M3/M4/Voucher/Saved regression, browser desktop/mobile, report/commands/Git plan; các NOT VERIFIED vẫn giữ nguyên.
- CHƯA ĐẠT nghiệm thu hiệu năng ổn định 5.000: các capture sau resume không qua FPS/render settlement. Chưa có long soak hoặc root-cause profiler trace.
- ĐIỀU KIỆN BÀN GIAO: Docker/OSRM đang offline sau gián đoạn; completed replay vẫn đọc được. Cần bật Docker Desktop và chạy lệnh serve kiểm identity trước tạo Live job mới.
- R1/M5: GO phát triển riêng trong scope nêu trên; NO-GO nghiệm thu coverage tỉnh mới, M5 model, commercial hoặc production.

Không triển khai R1/M5/M6/M7 ở đây. Đề xuất tiếp không phải approval production hoặc tự mở graph mới.

## Git handoff — chỉ đề xuất,chưa stage/commit

Phân loại cuối và SHA256 nằm trong `change-classification.json`/`validation-summary.json`; kiểm tra mọi 99 paths kế thừa còn tồn tại, scientific engine/worker/protected tests và historical evidence giữ nguyên so baseline. Danh sách dưới được tạo từ Git status cụ thể, không dùng glob staging. Index cuối rỗng.

Checkout chưa commit M3/M4. `git diff --stat` chỉ tính tracked files, không gồm hàng loạt modules/evidence untracked. Không thể xem S0/S1 như commit độc lập chỉ vài dòng vì nó sửa trên cả untracked M3/M4 modules chưa có trong HEAD. Đề xuất **hai commits tích hợp**, source trước,docs/evidence sau. Source commit chứa cả M3/M4 kế thừa+delta S0/S1, cần review toàn bộ; `build/s0-s1/before/` giúp đối chiếu riêng delta task. Không restore baseline để stage hoặc thay đổi source Owner.

Đối chiếu cuối: 99 paths kế thừa còn đủ; 13 được sửa trong task, 86 giữ nguyên, gồm 64 historical evidence files. 5 tracked paths trước task còn sạch nay có delta S0/S1. Allowlist cuối gồm 49 source paths và 163 documentation/evidence paths.

Machine-readable exact allowlists: [git-allowlists.json](s0-s1-evidence/git-allowlists.json). Classification inherited/new: [change-classification.json](s0-s1-evidence/change-classification.json). Không stage GIS/PBF/OSRM,build/cache,node_modules,.env,.agents hoặc file ngoài allowlists. Các lệnh dưới **chỉ đề xuất**, agent chưa chạy git add/commit.

```powershell
git status --short
git diff --stat
git diff --check
git diff --cached --name-only
$plan=Get-Content -Raw docs/nvmr/s0-s1-evidence/git-allowlists.json | ConvertFrom-Json
# Commit1: toàn bộ source tích hợp M3/M4/S0/S1 sau khi review allowlist:
git add -- $plan.source
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git diff --cached
# Chỉ sau khi tự review full staged diff:
git commit -m "feat(nvmr): integrate scalable simulation runtime and trip tracking"
# Commit2: reports+evidence,phụ thuộc commit1:
git add -- $plan.documentation
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git diff --cached
git commit -m "docs(nvmr): record M2 M4 and S0 S1 validation"
```

Không gộp index đang có file không liên quan. Kết thúc task, staged index được kiểm rỗng. Không push/merge/rebase. Nếu Owner muốn lịch sử M3/M4/S0 riêng, cần review/chọn hunks từ baseline trước; task này không tự sửa lịch sử hoặc stage partial untracked files.

### Exact paths commit1 — source

```text
backend/app/main.py
backend/app/simulation.py
backend/app/simulation_details.py
backend/app/simulation_jobs.py
backend/app/simulation_worker.py
frontend/public/icons/gsm/car.svg
frontend/public/icons/gsm/dropoff.svg
frontend/public/icons/gsm/motorbike.svg
frontend/public/icons/gsm/passenger.svg
frontend/public/icons/gsm/pickup.svg
frontend/scripts/verify-simulation.mjs
frontend/src/App.css
frontend/src/App.tsx
frontend/src/components/booking-map.tsx
frontend/src/components/fleet-map.tsx
frontend/src/components/mobility-icon.tsx
frontend/src/components/primary-navigation.tsx
frontend/src/components/sandbox-map.tsx
frontend/src/components/simulation-map-health.tsx
frontend/src/components/simulation-map.tsx
frontend/src/components/simulation-runtime.tsx
frontend/src/components/simulation-workspace.tsx
frontend/src/lib/api.ts
frontend/src/lib/navigation.ts
frontend/src/lib/simulation-map-icons.ts
frontend/src/lib/simulation.ts
frontend/src/lib/use-simulation.ts
frontend/src/test-setup.ts
frontend/tests/navigation.test.ts
frontend/tests/s0-s1-contract.test.ts
frontend/tests/s0-s1-map.test.tsx
frontend/tests/simulation-map-health.test.tsx
frontend/tests/simulation.test.ts
frontend/tests/use-simulation.test.ts
frontend/tests/workspace.test.tsx
frontend/vite.config.ts
scripts/Start-GsmDev.ps1
scripts/audit_route_fidelity.py
scripts/benchmark_simulation.py
scripts/benchmark_simulation_live.py
scripts/m3_fixture_travel.py
scripts/m3_resources.py
scripts/serve_ux_fault_proxy.py
scripts/validate_s0_s1_live.py
scripts/validate_simulation_api.py
tests/fixtures/m3/legacy-golden.json
tests/fixtures/m3/travel-matrix.json
tests/test_m3.py
tests/test_s0_s1.py
```

### Exact paths commit2 — documentation/evidence

```text
README.md
docs/nvmr/M2_IMPLEMENTATION.md
docs/nvmr/M3_IMPLEMENTATION.md
docs/nvmr/M3_M4_INTEGRATION_REVIEW.md
docs/nvmr/M4_IMPLEMENTATION.md
docs/nvmr/M4_UX_REMEDIATION.md
docs/nvmr/S0_S1_IMPLEMENTATION.md
docs/nvmr/m3-m4-evidence/api-integration.json
docs/nvmr/m3-m4-evidence/browser-benchmark.json
docs/nvmr/m3-m4-evidence/browser-initial-invalid.json
docs/nvmr/m3-m4-evidence/browser-integrated-5000.json
docs/nvmr/m3-m4-evidence/browser-live-100-summary.json
docs/nvmr/m3-m4-evidence/browser-live-5000-job.json
docs/nvmr/m3-m4-evidence/browser-live-5000-summary.json
docs/nvmr/m3-m4-evidence/clusters-5000.jpg
docs/nvmr/m3-m4-evidence/contract-verification-5000.json
docs/nvmr/m3-m4-evidence/contract-verification.json
docs/nvmr/m3-m4-evidence/domain-summary.json
docs/nvmr/m3-m4-evidence/hanoi-car-voucher-regression.json
docs/nvmr/m3-m4-evidence/integration-summary.json
docs/nvmr/m3-m4-evidence/live-car-5000.jpg
docs/nvmr/m3-m4-evidence/live-motorbike-inspector.jpg
docs/nvmr/m3-m4-evidence/live-summary.json
docs/nvmr/m3-m4-evidence/native-inspector-5000.jpg
docs/nvmr/m3-m4-evidence/saved-api-off.jpg
docs/nvmr/m3-m4-evidence/validation-summary.json
docs/nvmr/m4-ux-evidence/before-basemap-enabled.jpg
docs/nvmr/m4-ux-evidence/before-blank.jpg
docs/nvmr/m4-ux-evidence/failure-api.jpg
docs/nvmr/m4-ux-evidence/failure-api.txt
docs/nvmr/m4-ux-evidence/failure-cancelled.txt
docs/nvmr/m4-ux-evidence/failure-console.json
docs/nvmr/m4-ux-evidence/failure-interrupted.txt
docs/nvmr/m4-ux-evidence/failure-map-asset.jpg
docs/nvmr/m4-ux-evidence/failure-map-asset.txt
docs/nvmr/m4-ux-evidence/failure-queued.txt
docs/nvmr/m4-ux-evidence/failure-router.txt
docs/nvmr/m4-ux-evidence/fixture-100-basemap.json
docs/nvmr/m4-ux-evidence/fixture-1000-basemap.json
docs/nvmr/m4-ux-evidence/fixture-5000-basemap.jpg
docs/nvmr/m4-ux-evidence/fixture-5000-basemap.json
docs/nvmr/m4-ux-evidence/fixture-5000-tuned-basemap.json
docs/nvmr/m4-ux-evidence/git-allowlists.json
docs/nvmr/m4-ux-evidence/hanoi-m2-navigation.txt
docs/nvmr/m4-ux-evidence/live-5000-basemap-benchmark.json
docs/nvmr/m4-ux-evidence/live-5000-car.jpg
docs/nvmr/m4-ux-evidence/live-5000-contract.json
docs/nvmr/m4-ux-evidence/live-5000-job.json
docs/nvmr/m4-ux-evidence/live-5000-motorbike.jpg
docs/nvmr/m4-ux-evidence/live-5000-proof.json
docs/nvmr/m4-ux-evidence/m2-live-rerun.json
docs/nvmr/m4-ux-evidence/mobile-390.jpg
docs/nvmr/m4-ux-evidence/mobile-layout.json
docs/nvmr/m4-ux-evidence/mobile-run-open.txt
docs/nvmr/m4-ux-evidence/navigation-default-map.jpg
docs/nvmr/m4-ux-evidence/normal-console.json
docs/nvmr/m4-ux-evidence/product-final.jpg
docs/nvmr/m4-ux-evidence/real-cancellation.json
docs/nvmr/m4-ux-evidence/real-cancelled-ui.txt
docs/nvmr/m4-ux-evidence/real-failed-ui.txt
docs/nvmr/m4-ux-evidence/resource-fixture-100.json
docs/nvmr/m4-ux-evidence/resource-fixture-1000.json
docs/nvmr/m4-ux-evidence/resource-fixture-5000-tuned.json
docs/nvmr/m4-ux-evidence/resource-fixture-5000.json
docs/nvmr/m4-ux-evidence/resource-live-5000.json
docs/nvmr/m4-ux-evidence/saved-regression.jpg
docs/nvmr/m4-ux-evidence/small-car-route.jpg
docs/nvmr/m4-ux-evidence/small-motorbike-route.jpg
docs/nvmr/m4-ux-evidence/small-result.json
docs/nvmr/m4-ux-evidence/small-snapshot.json
docs/nvmr/m4-ux-evidence/validation-summary.json
docs/nvmr/s0-s1-evidence/actual-api-offline.jpg
docs/nvmr/s0-s1-evidence/actual-api-offline.txt
docs/nvmr/s0-s1-evidence/actual-api-recovered.jpg
docs/nvmr/s0-s1-evidence/actual-api-recovered.txt
docs/nvmr/s0-s1-evidence/audit-before.json
docs/nvmr/s0-s1-evidence/audit-live-large.json
docs/nvmr/s0-s1-evidence/audit-live-small.json
docs/nvmr/s0-s1-evidence/browser-environment.json
docs/nvmr/s0-s1-evidence/browser-resource-window.json
docs/nvmr/s0-s1-evidence/change-classification.json
docs/nvmr/s0-s1-evidence/cluster-after.jpg
docs/nvmr/s0-s1-evidence/cluster-before.jpg
docs/nvmr/s0-s1-evidence/contract-large-resumed.json
docs/nvmr/s0-s1-evidence/contract-large.json
docs/nvmr/s0-s1-evidence/contract-small-resumed.json
docs/nvmr/s0-s1-evidence/contract-small.json
docs/nvmr/s0-s1-evidence/development-console.json
docs/nvmr/s0-s1-evidence/directed-live-summary.json
docs/nvmr/s0-s1-evidence/fixture-100-handoff-diagnostic.json
docs/nvmr/s0-s1-evidence/fixture-100-symbols-final.json
docs/nvmr/s0-s1-evidence/fixture-100-symbols.json
docs/nvmr/s0-s1-evidence/fixture-5000-ascii-badge-smoke.json
docs/nvmr/s0-s1-evidence/fixture-5000-ascii-badges.jpg
docs/nvmr/s0-s1-evidence/fixture-5000-settled-zoom13.json
docs/nvmr/s0-s1-evidence/fixture-5000-symbols-final.jpg
docs/nvmr/s0-s1-evidence/fixture-5000-symbols-final.json
docs/nvmr/s0-s1-evidence/fixture-5000-symbols-pre-settle-fix.json
docs/nvmr/s0-s1-evidence/fixture-5000-symbols.jpg
docs/nvmr/s0-s1-evidence/fixture-warning-final.jpg
docs/nvmr/s0-s1-evidence/fixture-warning-final.txt
docs/nvmr/s0-s1-evidence/git-allowlists.json
docs/nvmr/s0-s1-evidence/handoff-car-pickup-desktop.jpg
docs/nvmr/s0-s1-evidence/handoff-car-pickup-desktop.txt
docs/nvmr/s0-s1-evidence/handoff-console-final.json
docs/nvmr/s0-s1-evidence/handoff-console.json
docs/nvmr/s0-s1-evidence/handoff-mobile-car.jpg
docs/nvmr/s0-s1-evidence/handoff-mobile-layout.json
docs/nvmr/s0-s1-evidence/handoff-mobile-map.jpg
docs/nvmr/s0-s1-evidence/handoff-motorbike-pickup-desktop.jpg
docs/nvmr/s0-s1-evidence/handoff-motorbike-pickup-desktop.txt
docs/nvmr/s0-s1-evidence/hcm-booking.jpg
docs/nvmr/s0-s1-evidence/hcm-booking.txt
docs/nvmr/s0-s1-evidence/hcm-fleet.jpg
docs/nvmr/s0-s1-evidence/hcm-fleet.txt
docs/nvmr/s0-s1-evidence/hcm-passenger-semantics.json
docs/nvmr/s0-s1-evidence/hcm-single.jpg
docs/nvmr/s0-s1-evidence/hcm-single.txt
docs/nvmr/s0-s1-evidence/hcm-voucher-live.jpg
docs/nvmr/s0-s1-evidence/hcm-voucher-live.txt
docs/nvmr/s0-s1-evidence/injected-mode-not-ready.jpg
docs/nvmr/s0-s1-evidence/injected-mode-not-ready.txt
docs/nvmr/s0-s1-evidence/isolated-worker-cleanup.json
docs/nvmr/s0-s1-evidence/isolated-worker-offline.json
docs/nvmr/s0-s1-evidence/isolated-worker-owned.json
docs/nvmr/s0-s1-evidence/large-detail-latency.txt
docs/nvmr/s0-s1-evidence/launcher-reuse.txt
docs/nvmr/s0-s1-evidence/launcher-status-final.txt
docs/nvmr/s0-s1-evidence/launcher-status-resumed.txt
docs/nvmr/s0-s1-evidence/launcher-status.txt
docs/nvmr/s0-s1-evidence/live-5000-handoff-first-zoom16.json
docs/nvmr/s0-s1-evidence/live-5000-handoff-instrumented-zoom16.json
docs/nvmr/s0-s1-evidence/live-5000-handoff-repeat-zoom16.json
docs/nvmr/s0-s1-evidence/live-5000-motorbike-pickup.jpg
docs/nvmr/s0-s1-evidence/live-5000-motorbike-pickup.txt
docs/nvmr/s0-s1-evidence/live-5000-symbols-zoom11.json
docs/nvmr/s0-s1-evidence/live-5000-symbols-zoom16.json
docs/nvmr/s0-s1-evidence/m2-live-regression.json
docs/nvmr/s0-s1-evidence/mobile-inspector.jpg
docs/nvmr/s0-s1-evidence/mobile-layout.json
docs/nvmr/s0-s1-evidence/mobile-map-final.jpg
docs/nvmr/s0-s1-evidence/mobile-map.jpg
docs/nvmr/s0-s1-evidence/native-car-click.txt
docs/nvmr/s0-s1-evidence/native-motorbike-click.txt
docs/nvmr/s0-s1-evidence/overlap-after-fix.jpg
docs/nvmr/s0-s1-evidence/overlap-after-fix.txt
docs/nvmr/s0-s1-evidence/saved-api-offline-proof.json
docs/nvmr/s0-s1-evidence/saved-hcm-api-offline.jpg
docs/nvmr/s0-s1-evidence/saved-hcm-api-offline.txt
docs/nvmr/s0-s1-evidence/saved-task-api-stop.json
docs/nvmr/s0-s1-evidence/small-car-on-trip.jpg
docs/nvmr/s0-s1-evidence/small-car-on-trip.txt
docs/nvmr/s0-s1-evidence/small-car-pickup-final.jpg
docs/nvmr/s0-s1-evidence/small-car-pickup-final.txt
docs/nvmr/s0-s1-evidence/small-car-pickup.jpg
docs/nvmr/s0-s1-evidence/small-car-pickup.txt
docs/nvmr/s0-s1-evidence/small-motorbike-on-trip.jpg
docs/nvmr/s0-s1-evidence/small-motorbike-on-trip.txt
docs/nvmr/s0-s1-evidence/small-motorbike-pickup.jpg
docs/nvmr/s0-s1-evidence/small-motorbike-pickup.txt
docs/nvmr/s0-s1-evidence/validation-summary.json
docs/nvmr/s0-s1-evidence/worker-offline-queued.jpg
docs/nvmr/s0-s1-evidence/worker-offline-queued.txt
```
