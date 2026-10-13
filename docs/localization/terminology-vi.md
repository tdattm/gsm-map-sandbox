# Thuật ngữ giao diện tiếng Việt

Áp dụng cho lớp hiển thị GSM Map Sandbox. Không đổi identifiers, enum values, schema, mã lỗi, JSON/CSV keys, file protocol hoặc artifact. Các nhãn lặp lại và định dạng nằm trong `frontend/src/lib/vi.ts`. Không có dịch vụ dịch thuật hoặc nút đổi ngôn ngữ.

| Original English | Nhãn ưu tiên | Giữ English | Viết tắt | Ngữ cảnh / cách dịch cần tránh |
|---|---|---|---|---|
| Single Trip | Một hành trình | Không | A1 | Một xe đi từ A đến B |
| Fleet Simulation | Mô phỏng đội xe | Không | A2 | Không gọi là theo dõi GPS trực tiếp |
| Booking & Dispatch | Đặt xe và điều phối | Không | A3 | Không dùng đặt phòng |
| Voucher Experiment Studio | Phòng thí nghiệm voucher | Voucher | A4 | Giữ tên sản phẩm GSM Map Sandbox |
| Primary Navigation | Menu chính | Menu | — | Thu gọn / mở rộng / ẩn menu |
| Contextual Inspector | Cấu hình và chi tiết | Không | — | Nút ngắn: Chi tiết; accessible name: Mở hoặc ẩn bảng chi tiết |
| Map Data | Dữ liệu bản đồ | Không | — | Không đổi tên lớp hoặc đường dẫn GIS |
| Start / End | Điểm xuất phát / Điểm đến | Không | A / B | Trong đặt xe: điểm đón / điểm trả |
| Distance | Quãng đường | Không | km, m | Không thay khoảng cách OSRM bằng đường thẳng |
| Travel duration | Thời gian di chuyển dự kiến | Không | giây, phút | Không gọi là giao thông thời gian thực |
| Seed | Seed (khởi tạo ngẫu nhiên) | Có | Seed | Giải thích trên trường cấu hình; giữ nguyên giá trị |
| Demand | Nhu cầu đặt xe | Không | — | Phân bố Thấp / Vừa / Cao tương ứng Low / Medium / High |
| Potential trip | Hành trình tiềm năng | Không | — | Chưa phải yêu cầu đặt xe được chấp nhận |
| Booking | Yêu cầu đặt xe | Không | — | Hành động: đặt xe; không dịch đặt phòng |
| Dispatch | Điều phối xe | Không | — | Không đổi chính sách FIFO / ETA |
| Scheduled | Chưa bắt đầu | Không | — | Đội xe/yêu cầu chưa tới thời điểm bắt đầu |
| Idle | Đang rảnh | Không | — | Trạng thái xe; clock idle là trạng thái chưa phát, không phải di chuyển |
| Moving / En route | Đang di chuyển | Không | — | A2 |
| En route to pickup | Đang đến đón khách | Không | — | Trạng thái xe A3/A4 |
| On trip | Đang chở khách | Không | — | Trạng thái xe |
| Waiting | Đang chờ xe | Không | — | Trạng thái yêu cầu |
| Assigned | Đã phân công xe | Không | — | Không đồng nhất với đã đón khách |
| Picked up | Đã đón khách | Không | — | Xe đang chở khách được thể hiện riêng |
| Completed | Hoàn tất | Không | — | KPI: Số chuyến hoàn tất; không xen kẽ Hoàn thành/Chuyến kết thúc |
| Unserved | Không được phục vụ | Không | — | Giữ lý do gốc trong export |
| Pickup ETA | Thời gian dự kiến đến đón | ETA | ETA | Nhãn ngắn: ETA đón; chỉ là dự kiến |
| Average waiting time | Thời gian chờ trung bình | Không | TB | Chỉ tính khách đã đón theo định nghĩa hiện tại |
| Fleet utilization | Mức sử dụng đội xe | Không | % | Thời gian bận / tổng thời gian xe; không suy ra ROI |
| Play / Pause / Resume | Phát / Tạm dừng / Tiếp tục | Không | — | Không thay clock semantics |
| Seek / Reset | Đến thời điểm / Về đầu | Không | — | Reset phát lại, không xóa artifact |
| Custom Speed | Tốc độ tùy chỉnh | Không | x | Giá trị chuẩn hóa 1x–64x được giữ nguyên |
| Observed | Tại thời điểm hiện tại | Không | — | Theo thời gian mô phỏng; không phải quan sát thực địa |
| Planned / Final | Kết quả cuối kịch bản | Không | — | Toàn bộ kế hoạch đã chuẩn bị; khác tiến độ phát lại |
| Baseline | Baseline — kịch bản không voucher | Có | Baseline | Nhãn ngắn Baseline sau phần giải thích đầu khu vực |
| Treatment | Treatment — kịch bản áp dụng voucher | Có | Treatment | Không dịch thành chữa trị |
| Difference | Chênh lệch Treatment − Baseline | Baseline, Treatment | Δ | Không đảo dấu |
| Voucher | Voucher | Có | — | Không bắt buộc dịch Phiếu giảm giá ở mọi nhãn |
| Voucher Policy | Chính sách voucher | Voucher | — | Giữ fixed/percentage trong contract |
| Campaign budget | Ngân sách voucher | Voucher | VND | Tổng ngân sách, khác khoản đã sử dụng |
| Offered | Đã đề xuất | Không | OFFERED trong contract | Chưa phải chi phí |
| Reserved Budget | Ngân sách đang giữ trước | Không | RESERVED trong contract | Chưa thanh toán; tránh dịch thành đã sử dụng |
| Voucher Spend / Settled | Chi phí voucher đã sử dụng | Voucher | SETTLED trong contract | Chỉ chi phí đã ghi nhận theo ledger; không phải tổng ngân sách |
| Released | Đã giải phóng | Không | RELEASED trong contract | Khoản giữ trước được hoàn về ngân sách khả dụng |
| Available Budget | Ngân sách còn khả dụng | Không | — | Giữ công thức tổng − giữ trước − đã sử dụng |
| Gross Fare Value | Tổng giá trị cước trước ưu đãi (GFV) | GFV | GFV | Nhãn chart ngắn: Giá trị cước trước ưu đãi (VND); chỉ chuyến hoàn tất |
| Rider Payments | Tổng tiền hành khách thanh toán | Không | — | Có thể bỏ Tổng trong legend ngắn; không đồng nhất với GFV |
| Conversion rate | Tỷ lệ đặt xe | Không | % | Chấp nhận / tiềm năng hợp lệ |
| Completion rate | Tỷ lệ hoàn tất | Không | % | Hoàn tất / chấp nhận |
| Incremental completed trips | Số chuyến hoàn tất tăng thêm | Không | Δ | Có thể âm hoặc 0 |
| Cost per incremental completed trip | Chi phí voucher mỗi chuyến hoàn tất tăng thêm | CPIC | CPIC | Không áp dụng khi mẫu số ≤0; không thay null bằng 0 |
| Fare estimation | Ước tính giá cước | Không | — | Cước cơ bản + cước/km × km OSRM |
| Logistic Regression / Sigmoid | Mô hình phản ứng với giá (Logistic/Sigmoid) | Có | — | Công thức giữ nguyên; không thêm mô hình ML |
| Alpha / Beta | Alpha (log-odds) / Beta (độ nhạy giá) | Có | α, β | Giữ đúng ý nghĩa tham số |
| Bernoulli / Common random numbers | Bernoulli / mẫu ngẫu nhiên chung | Có khi giải thích nghiên cứu | — | Hai kịch bản giữ cùng mẫu ngẫu nhiên |
| Live Local Experiment | Thí nghiệm trực tiếp (Live) | Live | — | Backend/OSRM cục bộ; không phải dữ liệu vận hành trực tiếp |
| Saved Replay | Phát lại đã lưu (Saved Replay) | Saved Replay | — | Không cần backend hoặc tính tuyến mới |
| Import / Export | Nhập / Xuất | Không | JSON, CSV | Portable v1 giữ tên định dạng; giữ toàn bộ keys/headers export |
| Artifact / Checksum | Thí nghiệm hoặc tài nguyên đã lưu / SHA-256 đã kiểm chứng | SHA-256 | — | Không sửa dữ liệu lịch sử để đổi ngôn ngữ |
| Batch Analysis | Phân tích nhiều lượt chạy | Không | — | Thành công/thất bại/bị hủy được báo cáo riêng |
| Sensitivity Analysis | Phân tích độ nhạy | Không | OFAT | Thay từng yếu tố; cùng danh sách Seed giữa nhóm |
| Mean / Median / Sample SD | Trung bình / Trung vị / Độ lệch chuẩn mẫu | Không | SD nếu tài liệu gốc | Không đổi công thức n−1 |
| Improvement Rate | Tỷ lệ lượt có cải thiện | Không | % | Chỉ mức tăng dương / cặp thành công; không phải xác suất thực địa |
| Pooled CPIC | CPIC gộp | CPIC | CPIC | Khác trung bình CPIC của từng lượt |
| Not applicable | Không áp dụng | Không | null trong dữ liệu | Không biến thành 0; trường chưa có dữ liệu có thể dùng — |
| OpenStreetMap / OSM | OpenStreetMap / OSM | Có | OSM | Tên riêng; attribution/giấy phép giữ nguyên |
| OSRM / MapLibre / GeoJSON / PBF | OSRM / MapLibre / GeoJSON / PBF | Có | — | Không tự tạo tên công nghệ tiếng Việt |
| API / JSON / CSV / Docker | API / JSON / CSV / Docker | Có | — | Giữ endpoints, extensions và câu lệnh |
| SHA-256 / WGS84 | SHA-256 / WGS84 | Có | — | Tọa độ kỹ thuật [lon, lat] giữ dấu chấm để không nhầm cặp tọa độ |
| KPI / VND / ROI / PoC / FIFO / RAF / FPS / MLD / ODbL | Giữ nguyên | Có | Tương ứng | Thuật ngữ/chữ viết tắt kỹ thuật; nội dung giải thích quanh chúng dùng tiếng Việt |

## Định dạng

- Tiền VND theo `vi-VN`: `200.000 ₫`; số nguyên `1.234`; tỷ lệ `12,5%`; quãng đường `3,14 km`; thời lượng `179,5 giây`. Giữ số chữ số thập phân đang dùng ở từng chỉ số.
- Timestamp chuẩn bị được hiển thị theo giờ Việt Nam (`Asia/Ho_Chi_Minh`); timestamp trong JSON không đổi. Simulation time là thời lượng, không phải ngày giờ.
- Chart dùng `phút`, `giây`, `%`, VND; hậu tố `k` trên trục tiền là nghìn VND. Tooltip dùng số/tiền định dạng `vi-VN`.
- Diagnostics chưa biết, tên đường OSM, ID xe/yêu cầu/Seed, phiên bản mô hình và fingerprint giữ nguyên để không đoán sai ý nghĩa hoặc sửa provenance.
