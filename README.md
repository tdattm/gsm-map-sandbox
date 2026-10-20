# Mobility Scenario Lab

Môi trường mô phỏng cách khách hàng lựa chọn và đặt xe trong các kịch bản có hoặc không có ưu đãi. Bản đồ phục vụ nghiên cứu khu vực phía Bắc và vùng trung tâm Thành phố Hồ Chí Minh; kết quả mô phỏng không đại diện cho hoạt động thực tế.

## Chạy ứng dụng trên Windows

Cần Python 3.11+, Node.js 20.19+ hoặc 22.12+, và PowerShell. Từ thư mục dự án, cài dependencies lần đầu:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Set-Location frontend
npm.cmd ci
Set-Location ..
```

Khởi động API, worker và giao diện:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Start-GsmDev.ps1 -Routers None
```

Mở <http://127.0.0.1:5183>. Dừng tiến trình do launcher khởi động bằng `Ctrl+C` trong cửa sổ PowerShell.

## Sử dụng

Chọn chức năng trong giao diện. Ở **Mô phỏng quy mô lớn**, tạo kịch bản, chờ trạng thái **COMPLETED**, rồi dùng thanh phát, tua thời gian, bộ lọc và chọn xe để xem lại kết quả. Kịch bản cần routing phải có dữ liệu bản đồ và OSRM local đã cài đặt; không có fallback sang routing công cộng.

Để mở lại một job đã lưu, dùng **Mở run đã có** và nhập ID job. JobStore cùng dữ liệu bản đồ nằm trong `build/` và không được đưa lên Git.

## Phát lại Connected NVMR 5K

Bản portable gồm job nghiên cứu và runtime riêng, được lưu trong `build/d2c/` sau D2c và không nằm trong Git. Hướng dẫn restore/chạy nằm trong [báo cáo nghiệm thu D2c](docs/nvmr/D2C_FINAL_ACCEPTANCE_REPORT.md) và README bên trong runtime bundle. Replay đã hoàn tất không cần worker, Docker hoặc OSRM.
