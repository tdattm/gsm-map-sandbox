/** Presentation only: never use localized labels as contract values or CSV keys. */
export const modeLabels = { single: 'Một hành trình', fleet: 'Mô phỏng đội xe', booking: 'Đặt xe và điều phối', voucher: 'Phòng thí nghiệm voucher' } as const
export const stateLabels = {
  scheduled: 'Chưa bắt đầu', waiting: 'Đang chờ xe', assigned: 'Đã phân công xe', picked_up: 'Đã đón khách', completed: 'Hoàn tất', unserved: 'Không được phục vụ',
  idle: 'Đang rảnh', moving: 'Đang di chuyển', en_route_to_pickup: 'Đang đến đón khách', on_trip: 'Đang chở khách',
  playing: 'Đang phát', paused: 'Đã tạm dừng', ready: 'Sẵn sàng', success: 'Thành công', error: 'Thất bại', cancelled: 'Đã hủy',
  OFFERED: 'Đã đề xuất', RESERVED: 'Đang giữ trước', SETTLED: 'Đã sử dụng', RELEASED: 'Đã giải phóng',
  BOOKING_REQUESTED: 'Đã nhận yêu cầu đặt xe', BOOKING_ASSIGNED: 'Đã phân công xe', VEHICLE_ARRIVED_PICKUP: 'Xe đã đến điểm đón', TRIP_STARTED: 'Bắt đầu chở khách', TRIP_COMPLETED: 'Chuyến hoàn tất', BOOKING_UNSERVED: 'Yêu cầu không được phục vụ',
} as const
export const stateText = (value: string) => stateLabels[value as keyof typeof stateLabels] ?? value
export const presetText = (value: string | number) => typeof value === 'number' ? numberText(value, Number.isInteger(value) ? 0 : 1) : ({ Low: 'Thấp', Medium: 'Vừa', High: 'Cao', base: 'Cấu hình gốc' }[value] ?? value)
export const factorLabels = { none: 'Không thay đổi', alpha: 'Alpha (log-odds)', beta: 'Beta (độ nhạy giá)', discount: 'Mức giảm giá', budget: 'Ngân sách voucher', fleet: 'Số xe', preset: 'Phân bố nhu cầu' } as const
export const csvLabels: Record<string, string> = { summary: 'Tổng hợp', decisions: 'Quyết định đặt xe', bookings: 'Yêu cầu đặt xe', ledger: 'Sổ ngân sách', series: 'Chuỗi thời gian' }
export const numberText = (value: number | null | undefined, digits = 0): string => value == null ? 'Không áp dụng' : new Intl.NumberFormat('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
export const moneyText = (value: number | null) => value === null ? 'Không áp dụng' : new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value)
export const percentText = (value: number | null, digits = 1) => value === null ? 'Không áp dụng' : numberText(value * 100, digits) + '%'
export const dateText = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'Asia/Ho_Chi_Minh' }).format(date) }

const errors: Record<string, string> = {
  INVALID_SAVED_ARTIFACT: 'Thí nghiệm đã lưu không hợp lệ. Kiểm tra định dạng v1, dữ liệu và tính toàn vẹn của file.',
  INVALID_ASSET_MANIFEST: 'Danh mục tài nguyên phát lại không hợp lệ hoặc không khớp SHA-256.',
  REPLAY_ASSETS_MISSING: 'Chưa có gói tài nguyên phát lại. Chuẩn bị gói theo README.', REPLAY_ASSET_MISSING: 'Thiếu tài nguyên trong gói phát lại.',
  REPLAY_ASSET_CHECKSUM: 'SHA-256 của tài nguyên phát lại không khớp.', REPLAY_ASSET_MISMATCH: 'Thí nghiệm và gói bản đồ không cùng bộ dữ liệu, vùng hiển thị hoặc danh mục tài nguyên.',
  DEMO_ARTIFACT_MISSING: 'Không tìm thấy thí nghiệm mẫu.', ARTIFACT_TOO_LARGE: 'File thí nghiệm vượt giới hạn 12 MiB.', REPLAY_ASSET_TOO_LARGE: 'Tài nguyên phát lại vượt giới hạn dung lượng.', INVALID_STATIC_GEOJSON: 'Lớp GeoJSON phát lại không hợp lệ.',
  INVALID_EXPERIMENT_PLAN: 'Kế hoạch thí nghiệm, sổ ngân sách hoặc KPI không hợp lệ.', INVALID_SCENARIO_PLAN: 'Kế hoạch mô phỏng hoặc chuỗi sự kiện không hợp lệ.',
  INVALID_BATCH_CONFIG: 'Cấu hình nhiều lượt chạy không hợp lệ. Kiểm tra Seed và các tham số.', BATCH_JOB_LIMIT: 'Cấu hình vượt giới hạn 90 lượt chạy.', BATCH_PROVENANCE_MISMATCH: 'Nguồn dữ liệu hoặc cấu hình của lượt chạy không khớp.',
  INVALID_EXPERIMENT_CONFIG: 'Giá cước, hành vi, voucher hoặc kịch bản nằm ngoài giới hạn mô phỏng.', INVALID_SCENARIO_CONFIG: 'Kiểm tra Seed, 1–10 xe, 10–30 yêu cầu, khoảng phát sinh 60–3.600 giây và giới hạn chờ 10–900 giây.',
  INVALID_COORDINATES: 'Điểm xuất phát và điểm đến phải là tọa độ WGS84 hữu hạn [kinh độ, vĩ độ].', OUTSIDE_ROUTING_REGION: 'Điểm nằm ngoài vùng tính tuyến đã cấu hình.', IDENTICAL_POINTS: 'Chọn hai điểm khác nhau.',
  DATASET_NOT_READY: 'Bản đồ hoặc OSRM cục bộ chưa sẵn sàng.', INSUFFICIENT_CANDIDATES: 'Không đủ điểm OSM hợp lệ.', CANDIDATES_UNAVAILABLE: 'Không đọc được các điểm OSM hoặc thông tin nguồn dữ liệu.', UNKNOWN_MAP_LAYER: 'Lớp bản đồ không hợp lệ.',
  NOROUTE: 'Không tìm được tuyến đường phù hợp.', NOSEGMENT: 'Không tìm được điểm phù hợp trên đường.', NOTABLE: 'Không tính được bảng ETA cho các điểm đã chọn.',
  ROUTER_TIMEOUT: 'OSRM cục bộ phản hồi quá thời gian cho phép.', ROUTER_UNAVAILABLE: 'Không kết nối được OSRM cục bộ.', ROUTER_BAD_RESPONSE: 'OSRM trả về dữ liệu tuyến hoặc ETA không hợp lệ.',
  SNAP_TOO_FAR: 'Điểm trên đường quá xa vị trí đã chọn.', INVALID_INITIAL_SNAP: 'Không xác minh được vị trí xe trên đường.', DISCONTINUOUS_LEGS: 'Các chặng đường không nối liền nhau.',
  ROUTE_OUTSIDE_REGION: 'Tuyến vượt vùng tính tuyến đã cấu hình.', ROUTE_OUTSIDE_DISPLAY: 'Tuyến vượt vùng bản đồ hiển thị hoặc có hình học không hợp lệ.',
  INVALID_FLEET_GEOMETRY: 'Hình học tuyến đường không hợp lệ.', INVALID_FLEET_ROUTE: 'Tuyến thiếu hình học, chỉ số hoặc điểm trên đường hợp lệ.', INVALID_FLEET_SNAP: 'Điểm xe trên đường không hợp lệ.',
  PICKUP_WAIT_LIMIT: 'Vượt giới hạn thời gian chờ đến đón.', PREPARATION_CANCELLED: 'Đã hủy chuẩn bị kịch bản.',
}
export function errorText(value: string): string {
  if (value === 'Không tạo được xe có tuyến hợp lệ. Xem lỗi từng request bên dưới.') return 'Không tạo được xe có tuyến hợp lệ. Xem lỗi từng yêu cầu bên dưới.'
  if (value === 'Cần 1–10 xe và ít nhất 2 candidate OSM.') return 'Cần 1–10 xe và ít nhất 2 điểm OSM hợp lệ.'
  const code = value.replace(/^Error:\s*/, '').split(':')[0].trim()
  if (code === 'INVALID_SAVED_ARTIFACT') {
    if (/12 MiB|size|lớn hơn|quá lớn/i.test(value)) return 'File thí nghiệm vượt giới hạn dung lượng. (INVALID_SAVED_ARTIFACT)'
    if (/schema|version|phiên bản/i.test(value)) return 'Phiên bản schema hoặc mô hình không được hỗ trợ. (INVALID_SAVED_ARTIFACT)'
    if (/digest|checksum|SHA-256/i.test(value)) return 'SHA-256 của thí nghiệm không khớp. (INVALID_SAVED_ARTIFACT)'
  }
  if (errors[code]) return `${errors[code]} (${code})`
  if (/Failed to fetch|NetworkError|fetch failed/i.test(value)) return 'Không kết nối được dịch vụ. Kiểm tra kết nối cục bộ.'
  // Unknown technical diagnostics remain verbatim; never guess their meaning.
  return value
}
export const batchStatusText = (value: string) => ({ 'Đang chạy sequential · local OSRM': 'Đang chạy tuần tự với OSRM cục bộ', 'Cancelled — partial results': 'Đã hủy · kết quả chưa đầy đủ', 'Complete — tất cả jobs đã có kết quả': 'Đã kết thúc · mọi lượt chạy đã có kết quả', 'Failed — partial results': 'Thất bại · kết quả chưa đầy đủ' }[value] ?? value)
export const statisticalDefinitionsVi = [
  'Chỉ tính thống kê trên các cặp chạy thành công; lượt thất bại và bị hủy vẫn được lưu trong danh sách và tổng số yêu cầu.',
  'Chênh lệch = số chuyến hoàn tất Treatment − Baseline, với cùng Seed và cấu hình.',
  'Độ lệch chuẩn mẫu dùng mẫu số n−1; không áp dụng khi có ít hơn 2 cặp thành công.',
  'Tỷ lệ lượt có cải thiện = số cặp có mức tăng dương / số cặp thành công; đây là thống kê mô phỏng.',
  'CPIC gộp = tổng chi phí voucher đã sử dụng trong Treatment / tổng mức tăng của TẤT CẢ các cặp; không áp dụng khi mẫu số ≤0.',
  'Thời gian chờ, mức sử dụng đội xe và ngân sách dùng số mẫu hợp lệ riêng; không thay null bằng 0.',
  'Biến thiên theo Seed phụ thuộc giả định PoC; không chứng minh tác động nhân quả hoặc hiệu quả thương mại.',
]
export const mapLocaleVi = {
  'Map.Title': 'Bản đồ', 'Marker.Title': 'Điểm trên bản đồ', 'LogoControl.Title': 'Logo MapLibre',
  'AttributionControl.ToggleAttribution': 'Mở hoặc ẩn thông tin nguồn bản đồ', 'AttributionControl.MapFeedback': 'Góp ý về bản đồ',
  'FullscreenControl.Enter': 'Mở toàn màn hình', 'FullscreenControl.Exit': 'Thoát toàn màn hình',
  'GeolocateControl.FindMyLocation': 'Tìm vị trí của tôi', 'GeolocateControl.LocationNotAvailable': 'Không lấy được vị trí',
  'NavigationControl.ResetBearing': 'Kéo để xoay bản đồ, nhấp để đưa hướng về phía Bắc', 'NavigationControl.ZoomIn': 'Phóng to', 'NavigationControl.ZoomOut': 'Thu nhỏ', 'Popup.Close': 'Đóng thông tin',
  'GlobeControl.Enable': 'Bật dạng địa cầu', 'GlobeControl.Disable': 'Tắt dạng địa cầu', 'TerrainControl.Enable': 'Bật địa hình', 'TerrainControl.Disable': 'Tắt địa hình',
  'CooperativeGesturesHandler.WindowsHelpText': 'Giữ Ctrl và cuộn để phóng to hoặc thu nhỏ bản đồ', 'CooperativeGesturesHandler.MacHelpText': 'Giữ ⌘ và cuộn để phóng to hoặc thu nhỏ bản đồ', 'CooperativeGesturesHandler.MobileHelpText': 'Dùng hai ngón tay để di chuyển bản đồ',
}
