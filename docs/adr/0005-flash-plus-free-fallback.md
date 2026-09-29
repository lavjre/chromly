# ADR-005 — Flash toàn lane + fallback model free

**Trạng thái:** Accepted · **Ngày:** 2026-09-29 · **Milestone:** M0

## Bối cảnh

Ngân sách Go $10/tháng; limit `deepseek-v4.1-flash` = $60/tháng (5h = $12, tuần = $30). Hệ thống phải chạy 24/7 — chạm limit không được phép "đứng máy". Số token/case thật chưa có (hypothesis — đo lại sau M4).

## Quyết định

Mọi lane (case lead · triage · analyst · exploit-dev · intel) dùng `opencode-go/deepseek-v4.1-flash`. Caps: $2/case, $2.5/ngày, $55/tháng. Chạm cap/cửa sổ rolling → rơi về **model free của opencode-go** (`longcat-2.5-preview-free` → `space-bunny-free`), chỉ nhận case score cao; free chết → plan B `glm-5.3-flash` → `mimo-v2.6-flash`. Governor probe free tier định kỳ (§4.1).

## Phương án đã loại

- **Model mạnh riêng cho exploit ngay từ đầu** — chưa có dữ liệu để biện minh chi phí; giữ 1 biến số cho M4.
- **Chỉ chạy khi còn budget** — bỏ lỡ crash đúng lúc hết limit; ngược tinh thần 24/7.

## Hệ quả

+ Không bao giờ đứng máy vì limit; một model = dễ đo, dễ so; nâng riêng `exploit-dev` chỉ 1 dòng config khi M5–M7 cần.
− Chain sâu có thể yếu hơn model mạnh; refusal rate phải theo dõi từ M4 (metric §7.2); free tier là promotional — probe định kỳ.
