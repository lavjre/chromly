#!/usr/bin/env bash
# personabuilder.sh — mở opencode với persona Nini (bản Linux của personabuilder.bat)
#
#   ./personabuilder.sh            → mini interface + persona (flags verified trên opencode v2.0.18)
#   ./personabuilder.sh -t         → full TUI, persona qua default_agent trong config
#   ./personabuilder.sh -r "msg"   → headless: opencode run --agent persona
#
# Env: CHROMLY_MODEL (default: opencode-go/deepseek-v4.1-flash)
#      CHROMLY_GREETING (default: "wsg what are we building")
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
MODEL="${CHROMLY_MODEL:-opencode-go/deepseek-v4.1-flash}"
GREETING="${CHROMLY_GREETING:-wsg what are we building}"

command -v opencode >/dev/null 2>&1 || { echo "[X] opencode không có trong PATH" >&2; exit 1; }

# repo là source of truth: symlink config vào chỗ opencode đọc (~/.config/opencode)
mkdir -p "$CFG"
ln -sfn "$HERE/persona.txt"   "$CFG/persona.txt"
ln -sfn "$HERE/opencode.json" "$CFG/opencode.json"
ln -sfn "$HERE/skills"        "$CFG/skills"   # global skill source (docs V2: ~/.config/opencode/skills)

case "${1:-}" in
  -t|--tui) exec opencode ;;
  -r|--run) shift; exec opencode run --agent persona -m "$MODEL" "${*:-$GREETING}" ;;
  *)        exec opencode mini --agent persona -m "$MODEL" --prompt "${*:-$GREETING}" ;;
esac
