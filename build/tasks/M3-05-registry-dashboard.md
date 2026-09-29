# M3-05 — Prompt registry + dashboard v1 + M3 acceptance

**Status:** todo
**Deliverable:** `prompt_registry` (migration v4): hash mỗi persona/skill/plugin/agent config (`chromly prompts sync` + `list`) — chuẩn bị cho Prompt CI (M4); `chromly status` dashboard v1: farm (execs/s, uptime, RSS) + intel (pending/reviewed) + crashes (raw/triaged, top scores) + alerts + disk; `acceptance/M3.sh` tổng: triage · classify · calibration · telemetry · registry.
**Files:** `chromly/telemetry/registry.py`, `chromly/cli/app.py`, `acceptance/M3.sh`, `tests/test_registry.py`
**Acceptance:** `bash acceptance/M3.sh` → sub pass + `chromly status` in đủ mục không lỗi.
**Evidence:** status output + registry hash list.
**Phụ thuộc:** M3-01..04.
