# M0-05 — OpenCode smoke (persona + resume + paths)

**Status:** todo
**Deliverable:** `acceptance/M0-opencode.sh` — (1) `opencode --version` ≥ 2.x; (2) `opencode debug paths` ghi lại vào `docs/opencode-paths.md` (chốt mount paths cho case container M4); (3) persona agent chạy headless: prompt trả về đúng token `SMOKE-OK`; (4) resume cùng session `-s <id>` trả về đúng token `RESUME-OK`; (5) config trong repo được nạp (`agent.persona.prompt {file:}` shape hoạt động trên v2.x).
**Files:** `acceptance/M0-opencode.sh`, `docs/opencode-paths.md` (kết quả `debug paths` + ghi chú auth/mount)
**Acceptance:** script exit 0; log 2 run (session id + token) lưu `store/logs/acceptance/`.
**Evidence:** session ids + token match, version string trong commit body. (Chi phí smoke: ~vài nghìn token — trong ngân sách §11.)
**Out of scope:** plugin `chromly.ts` (M4) · `opencode serve` control plane (M4).
**Phụ thuộc:** M0-02 (không bắt buộc — chạy độc lập được).
