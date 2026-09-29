#!/usr/bin/env bash
# acceptance/M0-skills.sh — M0-08: skills runtime (6 playbook + wiring + live discovery)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

MODEL="${CHROMLY_MODEL:-opencode-go/deepseek-v4.1-flash}"
SKILLS=("v8-triage" "patch-diff-review" "repro-minimize" "exploit-primitive" "vrp-report" "ida-batch")
SKILL_LOG="$LOG_DIR/skills-smoke.log"

section "runtime/skills (6 playbook v0)"
missing=""
for id in "${SKILLS[@]}"; do
    f="$REPO_ROOT/runtime/skills/$id/SKILL.md"
    if [[ -f "$f" ]] && grep -q '^description:' "$f"; then
        :
    else
        missing="$missing $id"
    fi
done
if [[ -z "$missing" ]]; then
    pass "đủ 6 SKILL.md + frontmatter description"
else
    fail "thiếu/sai:$missing"
fi

section "wiring ~/.config/opencode/skills"
LINK="$HOME/.config/opencode/skills"
if [[ -L "$LINK" ]] && [[ "$(readlink -f "$LINK")" == "$REPO_ROOT/runtime/skills" ]]; then
    pass "symlink → repo runtime/skills"
else
    fail "symlink sai/thiếu — chạy: ./runtime/personabuilder.sh (hoặc ln -sfn $REPO_ROOT/runtime/skills $LINK)"
fi

section "live smoke — discovery + load (opencode run)"
OUT="$(opencode run --format json --auto --agent persona -m "$MODEL" \
    "Two things, then stop: (1) List the exact IDs of every skill that is available to you, comma-separated. (2) Load the skill with id 'v8-triage' using the skill tool, then reply on a new line exactly: SKILL-LOADED v8-triage" 2>&1)"
echo "$OUT" >>"$SKILL_LOG"
SID="$(grep -oE 'ses_[A-Za-z0-9]+' <<<"$OUT" | head -1)"
miss_id=""
for id in "${SKILLS[@]}"; do
    grep -q "$id" <<<"$OUT" || miss_id="$miss_id $id"
done
if [[ -z "$miss_id" ]]; then
    pass "6 skill ID hiện diện (session=$SID)"
else
    fail "thiếu ID:$miss_id (xem $SKILL_LOG)"
fi
if grep -q "SKILL-LOADED" <<<"$OUT"; then
    pass "load skill v8-triage OK"
else
    fail "không load được skill (xem $SKILL_LOG)"
fi

ac_summary
