# Frontend

Giao diện React/Vite/TypeScript của GSM Map Sandbox. Xem [README của dự án](../README.md) để thiết lập backend, dữ liệu, chạy A1–A4 và dùng Saved Replay/Phân tích nhiều lượt chạy của A5. Các nhãn sử dụng tiếng Việt; Baseline, Treatment, Seed và các tên công nghệ được giữ theo [bảng thuật ngữ](../docs/localization/terminology-vi.md).

```powershell
npm.cmd install
npm.cmd run dev
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

Worker MapLibre được copy local bằng script postinstall/predev/prebuild. shadcn/ui và mapcn là source component trong src/components/ui. Không dùng fixture làm bản đồ thực tế.
