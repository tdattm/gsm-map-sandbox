# Frontend

Giao diện React/Vite/TypeScript của GSM Map Sandbox. Xem [README của dự án](../README.md) để thiết lập backend, dữ liệu, chạy A1–A4 và dùng Saved Replay/Phân tích nhiều lượt chạy của A5. Các nhãn sử dụng tiếng Việt; Baseline, Treatment, Seed và các tên công nghệ được giữ theo [bảng thuật ngữ](../docs/localization/terminology-vi.md).

Kịch bản hiện hành **Miền Bắc liên thông (Connected NVMR v5)** dùng một MapLibre
instance, vector tiles OSM offline, global snapshot và inspector/playback đã lưu.
Chọn từ **Mô phỏng quy mô lớn → Kịch bản mô phỏng** hoặc mở
`?runtime=simulation&scenario=connected`. Xem [runbook R1b](../docs/nvmr/R1B_CONNECTED_RUNBOOK.md)
để chạy API/worker/router đúng store và [báo cáo nghiệm thu](../docs/nvmr/R1B_CONNECTED_IMPLEMENTATION.md)
để phân biệt các phần đã kiểm chứng. HCM, Hanoi v3 và regional v4 giữ luồng riêng.

```powershell
npm.cmd install
npm.cmd run dev
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Worker MapLibre được copy local bằng script postinstall/predev/prebuild. shadcn/ui và mapcn là source component trong src/components/ui. Không dùng fixture làm bản đồ thực tế.
