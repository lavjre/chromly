# M0-08 — Skills runtime (6 playbook v0 + wiring)

**Status:** done
**Deliverable:** `runtime/skills/<id>/SKILL.md` cho 6 skill §4.4 — `v8-triage` · `patch-diff-review` · `repro-minimize` · `exploit-primitive` · `vrp-report` · `ida-batch` (playbook v0 bám Ch.1 + §5); `personabuilder.sh` symlink thêm `skills` → `~/.config/opencode/skills`; acceptance có live smoke: agent liệt kê đủ 6 ID + load được 1 skill.
**Files:** `runtime/skills/**`, `runtime/personabuilder.sh`, `acceptance/M0-skills.sh`, `docs/opencode-paths.md`, `TOOLS.md`
**Acceptance:** `bash acceptance/M0-skills.sh` → 6 file đủ frontmatter + symlink đúng + live: đủ 6 ID trong list, load 1 skill thành công.
**Evidence:** output acceptance + session id của live run.
**Out of scope:** nội dung final từng skill theo milestone (refine M2/M3/M5); từ M4 mọi thay đổi qua Prompt CI (G3).
**Phụ thuộc:** M0-05.
