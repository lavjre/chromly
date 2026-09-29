#!/usr/bin/env bash
# acceptance/M0-bootstrap.sh — M0-01: bootstrap VM (cần operator chạy `sudo bash infra/bootstrap.sh` 1 lần)
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

RAN=no
[[ -f /etc/systemd/system/chromly-svc.slice ]] && RAN=yes

verdict() { # verdict <name> <yes|no>
    if [[ "$2" == yes ]]; then
        pass "$1"
    elif [[ $RAN == yes ]]; then
        fail "$1"
    else
        pend "$1 (chờ: sudo bash infra/bootstrap.sh)"
    fi
}

chk() { # chk <name> <cmd...>
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then verdict "$name" yes; else verdict "$name" no; fi
}

section "syntax"
chk "infra/bootstrap.sh syntax" bash -n "$REPO_ROOT/infra/bootstrap.sh"
ok=yes
for s in "$REPO_ROOT"/acceptance/*.sh; do
    bash -n "$s" || ok=no
done
verdict "acceptance scripts syntax" "$ok"

section "bootstrap items"
chk "uv" uv --version
chk "depot_tools" test -d "$HOME/tools/depot_tools/.git"
chk "depot_tools trong PATH (~/.bashrc)" grep -q depot_tools "$HOME/.bashrc"
chk "docker binary" docker --version
chk "docker group (config /etc/group)" bash -c 'getent group docker | grep -qw "$(id -un)"'

swap_mb="$(free -m | awk '/^Swap:/{print $2}')"
[[ "$swap_mb" -ge 16000 ]] && verdict "swap ≥16G (${swap_mb}MB)" yes || verdict "swap ≥16G (${swap_mb}MB)" no

chk "sysctl perf_event_paranoid=2" bash -c 'test "$(sysctl -n kernel.perf_event_paranoid)" = 2'
chk "sysctl max_map_count ≥262144" bash -c 'test "$(sysctl -n vm.max_map_count)" -ge 262144'
chk "apport tắt" bash -c 'test "$(systemctl is-active apport.service 2>/dev/null || true)" != active'
chk "slices files" bash -c \
    'test -f /etc/systemd/system/chromly-svc.slice && test -f /etc/systemd/system/chromly-build.slice && test -f /etc/systemd/system/chromly-fuzz.slice && test -f /etc/systemd/system/chromly-case.slice'
chk "slices loaded" bash -c 'systemctl show -p LoadState chromly-svc.slice | grep -q LoadState=loaded'
chk "earlyoom active" bash -c 'test "$(systemctl is-active earlyoom 2>/dev/null)" = active'
chk "git identity" bash -c 'test -n "$(git config --global user.name)" && test -n "$(git config --global user.email)"'

section "idempotency (M0-01)"
if [[ $RAN == yes ]]; then
    note "operator: chạy lại lần 2 'sudo bash infra/bootstrap.sh' — phải exit 0 và không đổi gì thêm"
else
    pend "idempotent run — operator chạy script 2 lần"
fi

ac_summary
