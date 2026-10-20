# M4 follow-up — FPS profiler và RAM admission cho 1.000–5.000 xe

## Current Verified State — 18/10/2026

Source baseline vẫn `3ef9160940e6129c911889add7d8aed0d6022bd1`, branch `feature/nvmr-m0-architecture`; các thay đổi của nhiệm vụ đang unstaged. Bản này cập nhật báo cáo stabilization trước đó, đặc biệt thay thế policy small-only và tình trạng fresh5.000 NOT RUN của lượt trước. Evidence cũ giữ nguyên timestamps/hashes.

| Yêu cầu mới | Trạng thái |
|---|---|
| Bắt lại lỗi1 FPS và chốt nguyên nhân bằng profiler | **CHƯA HOÀN THÀNH**. Owner xác nhận hiện không còn thấy lỗi. Đã bổ sung own-page JS sampling và RAF/timer/longtask timeline; không dùng capture bình thường làm bằng chứng đã sửa nguyên nhân cũ. |
| Hạ reserve thường xuống dưới1 GiB, gồm1.000/5.000 xe | **Đã implement và chạy thật** với policy chung API/worker/profiler; kết quả bên dưới. |
| Commit/push và kiểm GitHub Actions | **CHƯA THỰC HIỆN** vì owner yêu cầu chỉ làm sau khi cả hai nhiệm vụ trên hoàn thành. Không suy “hiện không thấy lỗi” thành root-cause closure. |

Không thay seed/config/dispatch/geometry/Voucher hoặc immutable result semantics. HCM và Saved Replay contracts giữ riêng.

## Policy mới và nguyên nhân ngưỡng2 GiB vẫn xuất hiện

Policy trước chỉ nhận `small` khi fleet≤100, bookings≤20, horizon≤900, schedule rỗng, candidates≤128. Vì vậy1.000 xe rơi vào nhánh2 GiB dù worker thực tế chỉ có peakRSS khoảng114 MiB. Ngoài ra profiler tự chặn1.000/5.000 ở3/4 GiB và Benchmark launcher startup yêu cầu2 GiB. Đây là ba admission/startup policies khác nhau, không phải ba phép đo RAM consumption.

Policy mới trong `backend/app/simulation_resources.py`:

| Workload | Physical available tối thiểu | Windows commit headroom tối thiểu |
|---|---:|---:|
| Light: fleet≤1.000 và bookings≤1.000 | **0,50 GiB** | 1,00 GiB |
| Routine: tới5.000 xe và bookings≤5.000 | **0,75 GiB** | 1,50 GiB |
| Extended: ngoài bounds bên dưới | 2,00 GiB | 2,00 GiB |

Light/routine cùng bounds: horizon≤3.600 s, onlineSchedule≤8 entries, maxCandidates≤128; fleet≤5.000 do existing request schema. Vượt một bound thì extended, không giảm request âm thầm. Online fraction, CAR mix, seed và workload preset giữ nguyên.

API kiểm tra trước enqueue; worker kiểm tra lại lúc bắt đầu. Profiler dùng **cùng function** thay vì thêm floor3/4 GiB. Startup tất cả launcher profiles dùng floor0,5 GiB, tách khỏi job policy. Runtime trả `admissionPolicy`; frontend đọc các values từ API để tránh hiện policy cũ. Unknown commit trên Linux được ghi unknown; physical guard vẫn áp dụng. Không reserve RAM, không tự chỉnh pagefile, không dùng commit cao để bỏ physical floor.

Tests bao gồm1.000/250,1.000/1.000,1.001/250,5.000/1.250,5.000/5.000; exact physical/commit boundary, rejection ngay dưới floor; large booking/horizon/schedule/candidate giữ extended; repeated rejection không tạo jobs. Focused resource/M3/S0S1: **45 PASS**.

## Live benchmarks thật, cùng scientific inputs

Chạy tuần tự, không synthetic allocation pressure, không full test/build trong timed engine window. Windows sampler chạy read-only khoảng1Hz, actual interval chậm hơn vì CIM. Các ứng dụng owner vẫn mở, đây không phải controlled idle machine hay Meet acceptance.

| Chỉ số | Fresh1.000 | Fresh5.000 |
|---|---:|---:|
| Job ID | `e4fb6f14ffb34d7fa6fc67c8df044417` | `77bae3c7611849eeac7a9ab4dd375cc6` |
| Seed | `m4-memory-1000` | `m4-memory-5000` |
| CAR / MOTORBIKE | 400 /600 | 2.000 /3.000 |
| Requests | 250 | 1.250 |
| Online fraction /horizon | 1 /900 s | 1 /900 s |
| Status | COMPLETED | COMPLETED |
| Completed /unserved | 250 /0 | 1.250 /0 |
| Policy physical floor | 0,50 GiB | 0,75 GiB |
| Physical available lúc admission | ~0,930 GiB | ~1,111 GiB |
| Minimum physical trong50ms worker samples | ~0,758 GiB | ~1,096 GiB |
| Sampled peakRSS | ~114,11 MiB | ~94,62 MiB |
| Sampled peak private | ~102,62 MiB | ~82,69 MiB |
| Process lifetime peakRSS | ~114,11 MiB | ~114,11 MiB (gồm run trước) |
| Wall time gồm worker/audit/persistence | ~15,88 s | ~20,15 s |
| CPU seconds | 14,56 | 17,58 |
| Geometric audit | PASS40 assignments/320 samples | PASS40 assignments/528 samples |

Không suy5.000 luôn dùng ít RAM hơn1.000: cùng process warm, Windows working-set trimming và samples50ms có thể bỏ đỉnh ngắn. Profiler row lưu cả sampled peak và process lifetime peak để không trộn hai đại lượng. Các route requests/caches/payload bytes và identity manifests nằm trong raw report.

Run1.000 có semantic SHA khớp run trước `e2caced02db64a02a56300050544690b`: cùng scientific inputs và outcomes. Hash bỏ runId/wall metrics nhưng giữ events/assignments/routes/timelines/config/provenance. Run5.000 được internal `validate_result`, geometric audit và HTTP→product TypeScript snapshot/selected-route/booking validator kiểm. Result copies vào task playback store giữ nguyên bytes; không stage full jobs.

## Ưu điểm, nhược điểm và mức tin cậy

**Ưu điểm đã quan sát:** run1.000 bắt đầu với freeRAM<1 GiB mà policy cũ sẽ reject; run5.000 không còn bị floor profiler4 GiB từ chối, và completed1.250/1.250. Không cần giảm counts hoặc đổi ETA/routing. Startup reserve và job reserve được phân biệt; một policy làm nguồn cho API/worker/profiler và diagnostics.

**Chi phí và rủi ro:** giảm floor không giải phóng một byte RAM và không tăng physical RAM. Ít headroom hơn làm khả năng working-set trimming/paging/latency cao hơn khi Chrome/meeting tăng tải. Admission là snapshot, app khác có thể lấy thêm RAM ngay sau đó; commit guard không ngăn mọi swapping. Low-floor không phải bảo đảm no-OOM hoặc FPS SLA. Chưa đo run5.000 bắt đầu đúng0,75 GiB và chưa ép machine xuống0,5 GiB.

Run1.000 cùng seed trước có wall5,62 s ở khoảng4 GiB available; lần này15,88 s ở~0,93 GiB, chênh~2,83 lần. Đây là khác session/cache/CPU/app load, **không thể gán toàn bộ chênh lệch cho paging**. System pageReads trong7 Windows samples khớp timed window: median7/s, max317/s, CPU max57%; run5.00010 samples: median3/s, max43/s, CPU max65%. Đây là global counters, không phải hard-fault attribution riêng GSM. Pagefile current775 MiB trong các first samples, allocated8.421 MiB; không tự điều chỉnh.

Bounded routine envelope và1–1,5 GiB commit reserve vẫn giữ guard cho phần lớn UI defaults, còn configs20.000 bookings/24h/large shortlist dùng extended. Cần bổ sung profile theo request-heavy configs nếu muốn mở rộng envelope; không dùng fleet size một mình như công thức RAM. Scientific determinism được kiểm độc lập với thời gian chạy.

## FPS và profiler: phạm vi chứng cứ

Sau khi mở thêm playback5.000 và diagnostic tab, UI từng ghi freeRAM~0,42 GiB (khác timed engine window). Điều này cho thấy RAM browser/MapLibre/API cache và ứng dụng khác có thể tiếp tục lấy headroom sau khi job completed. Lúc đó policy vẫn từ chối job mới dưới floor; không hạ tiếp floor để ép chuỗi run khi hệ thống đang áp lực. Diagnostic tab đã đóng để nhả tài nguyên của task.

| Capture30s | RAF FPS | p95/max gap | JS sampling /timeline |
|---|---:|---|---|
| Plain, trước MapLibre import | 60,0005 | 16,9 /17,2 ms | 1.700 samples,6 frames,3.302 application events |
| Hanoi fixture5.000, playback+pan | 59,9997 | 16,9 /17,2 ms | 1.439 samples,201 frames,3.303 application events |
| Product playback fresh5.000, Meeting+pan | 59,1036 | 16,8 /50,1 ms | 112 source updates,2 long tasks tổng104ms; product rawRAF, không CPU sampling |

Lab viewport1280×720, map764×543, DPR1,25; product map canvas410×279, cùng DPR nhưng dimensions khác nên không so FPS như before/after. Renderer Intel Iris Xe ANGLE/D3D11. Product cluster oracle PASS7 visible clusters, source5.000, viewport leaves2.657; không gọi đó là full-source leaf coverage hoặc5.000 moving. Tại freeze130,739s có157 moving/5.000 online. Plain/fixture profile sampleInterval thực tế16ms dù yêu cầu10ms; nhiều samples không có stack nên không diễn giải thành exact CPU busy/idle tỷ lệ. Các symbols production phần lớn minified, không có source-map attribution đầy đủ.

Tool chỉ có browser nhúng; native apps/independent Chrome controller không khả dụng. Mở Chrome tracing nội bộ bị browser policy chặn; không dùng raw CDP, flags hoặc giao diện khác để vượt chặn. Thay vào đó app diagnostic page tự thu dữ liệu của chính origin GSM bằng web APIs.

`performance.html` có checkbox JS sampling opt-in; chỉ trang này nhận `Document-Policy: js-profiling`. API được feature-detect và lỗi/unsupported được ghi rõ, không giả trace. Từng capture xuất raw JS Self-Profiling trie và application timeline (RAF intervals,20ms timer intervals, long tasks, visibility/focus), giữ scope riêng với Chrome compositor/GPU trace.

Tham chiếu API: [WICG JS Self-Profiling proposal](https://github.com/WICG/js-self-profiling). Sampling best-effort không phải exact CPU accounting; không thêm thư viện hay gửi profile tới server ngoài. Header chỉ áp dụng diagnostic page; trang sản phẩm không tự bật profiler. Raw traces có thể chứa code resource paths nên giữ local ignored build; bản chọn lọc chỉ dùng origin app, không browser history hoặc meeting contents.

Owner trả lời “Hiện không còn thấy lỗi”. Không cố tạo busy-loop hoặc giảmRAF xuống1Hz rồi nhận đó là lỗi gốc. Nếu chỉ có trace60FPS, kết luận là **không tái lập trong cửa sổ đo**, không phải chốt browser/MapLibre đã được sửa. Điều kiện commit/push của owner vẫn chưa đạt khi nguyên nhân1FPS còn mở.

## Runbook hiện tại

```powershell
Set-Location 'D:\ThS\VinAI\Phase3_VRIC\gsm-map-sandbox'
.\scripts\Start-GsmDev.ps1 -StatusOnly -Profile Meeting -Routers None -ApiPort 8016 -FrontendPort 5187 -Store build/m4-performance/jobs
Invoke-RestMethod http://127.0.0.1:8016/api/v3/simulation/jobs/runtime | ConvertTo-Json -Depth 8
.\.venv\Scripts\python.exe scripts/profile_simulation_memory.py --fleets 1000 5000 --label unique-manual-label --output build/m4-performance/unique-manual-profile.json
```

Profilling labels phải mới, không dùng chung queue đang active. Muốn lấy FPS trace: mở `http://127.0.0.1:5187/performance.html`, chọn plain trước khi MapLibre import; tick JS sampling, chọn30s và Đo. Sau đó Hanoi5000+pan, cùng dimensions. Khi lỗi thật tái xuất hiện, capture ngay trong session đó trước reload và lưu JSON. Raw JS samples không thay thế trace GPU/compositor nếu cần chốt driver/host issue.

Không commit/push chỉ vì RAM task đã xong. Không chạy GitHub Actions bằng cách push trước điều kiện owner; workflow vẫn là source chưa publish.

## Verification cuối lượt và evidence

- Full backend sau policy mới: **203 PASS /6 SKIP /1 warning**,72,70s; RUN_REAL_DATA=0. Sáu integration skips yêu cầu artifacts/opt-in giữ nguyên. Focused guards/M3/S0S1:45 PASS.
- Frontend: **182 PASS /21 files**,134,89s, maxWorkers=1 để giảm peak memory; không so duration này với benchmark browser/engine. Lint **39 warnings /0 errors**; typecheck + production build PASS, existing MapLibre chunk warning còn.
- Fresh5.000 HTTP→product TypeScript validators PASS; snapshot gate, CAR/MOTORBIKE routing identity, selected booking và pickup/trip contracts. Audit1.000/5.000 PASS và hash1.000 khớp baseline cùng seed.
- Production build identity kiểm fresh; parser PowerShell và diff whitespace được kiểm. Không thay sealed Saved Replay artifacts hoặc scientific core files. Historical full Saved verifier/M2/HCM/S1 kết quả giữ trong stabilization evidence; không gọi đó là rerun tất cả manual flows trong follow-up này.
- Runtime hiện tại API8016/preview5187/worker cùng task store, Hanoi modes READY. Receipt task hiện tại: `build/s0-runtime/session-20261018-091422-578.json`; dừng/restart dùng exact receipt theo Stop-GsmDev.ps1, không stop user routers.
- Tracked selected evidence: [`m4-followup-evidence/validation-summary.json`](m4-followup-evidence/validation-summary.json), profiler summaries, raw own-page JS sampling `.selfprofile.json`, application `.timeline.json`, job resource/audit/contract JSONs, selected logs `.txt`, screenshot. TXT copies chỉ chuẩn hóa newline/trailing whitespace để Git whitespace check; original `.log` bytes giữ nguyên trong ignored build và có `rawLogSha256` đối chiếu. Full result/jobs/per-PID samples giữ ignored `build/m4-performance/`.
- Traces chỉ có localhost app asset URLs, đã kiểm resources; không browser history, user Chrome contents hoặc meeting data. JS symbol stack chủ yếu minified; không có source maps hoặc GPU trace để chốt driver/compositor cause.

**Kết luận handoff:** RAM task đạt phạm vi triển khai + live proof thông thường dưới1GiB floor, với trade-offs nêu trên. FPS task mới có instrumentation và normal-cadence profiles, chưa bắt được lỗi lịch sử để chốt root cause. Vì điều kiện owner là hoàn thành cả hai trước commit/push, Git mutation và GitHub Actions remote vẫn **NOT RUN**, không báo milestone hoàn thành toàn bộ.
