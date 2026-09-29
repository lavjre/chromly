#!/usr/bin/env bash
# infra/bootstrap.sh — idempotent VM bootstrap cho chromly M0+
# Chạy TRÊN VM Ubuntu 26.04.1:  sudo bash infra/bootstrap.sh
#
# Cài: apt build deps · uv · depot_tools (clone + PATH) · docker + user group ·
#      swap 16G · sysctl (max_map_count, perf_event_paranoid=2) · tắt apport ·
#      systemd slices chromly-{svc,build,fuzz,case} · earlyoom · git identity.
# Idempotent: chạy lần 2 phải exit 0 và không thay đổi gì thêm (task M0-01).
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "chạy bằng sudo: sudo bash infra/bootstrap.sh" >&2; exit 1; }
OPERATOR="${SUDO_USER:-lavjre}"
OPERATOR_HOME="$(getent passwd "$OPERATOR" | cut -d: -f6)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$HERE")"

say() { printf '\n=== %s ===\n' "$1"; }

say "apt build deps"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    build-essential git curl ca-certificates python3 python3-venv python3-dev \
    pkg-config ninja-build clang lld llvm lldb \
    libssl-dev libglib2.0-dev libatomic1 \
    xz-utils zip unzip file rsync \
    docker.io earlyoom
echo "apt: OK"

say "docker group cho $OPERATOR"
if id -nG "$OPERATOR" | grep -qw docker; then
    echo "đã trong group docker"
else
    usermod -aG docker "$OPERATOR"
    echo "đã thêm $OPERATOR vào group docker (cần đăng nhập lại để hiệu lực)"
fi

say "swap 16G"
SWAP_TOTAL_MB="$(free -m | awk '/^Swap:/{print $2}')"
if [[ "$SWAP_TOTAL_MB" -ge 16000 ]]; then
    echo "swap hiện tại ${SWAP_TOTAL_MB}MB ≥16G — bỏ qua"
else
    if [[ ! -f /swapfile ]]; then
        fallocate -l 16G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile >/dev/null
        echo "đã tạo /swapfile 16G"
    fi
    swapon --show | grep -q '/swapfile' || swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
    echo "swap tổng: $(free -m | awk '/^Swap:/{print $2}')MB"
fi

say "sysctl (§6.1)"
cat >/etc/sysctl.d/90-chromly.conf <<'EOF'
# chromly — PLAN §6.1
vm.max_map_count = 1048576
kernel.perf_event_paranoid = 2
EOF
sysctl --system >/dev/null
echo "max_map_count=$(sysctl -n vm.max_map_count) perf_event_paranoid=$(sysctl -n kernel.perf_event_paranoid)"

say "tắt apport"
systemctl disable --now apport.service apport-autoreport.timer 2>/dev/null || true
systemctl mask apport.service >/dev/null 2>&1 || true
if [[ -f /etc/default/apport ]]; then
    sed -i 's/^enabled=.*/enabled=0/' /etc/default/apport
fi
echo "apport: $(systemctl is-active apport.service 2>/dev/null || echo inactive)"

say "systemd slices (§6.4)"
install -m 644 "$HERE"/systemd/chromly-*.slice /etc/systemd/system/
systemctl daemon-reload
for s in svc build fuzz case; do
    systemctl start "chromly-$s.slice" 2>/dev/null || true
done
systemctl status chromly-svc.slice --no-pager >/dev/null 2>&1 && echo "slices: OK" || echo "slices: kiểm tra lại"

say "earlyoom"
cat >/etc/default/earlyoom <<'EOF'
# chromly — ưu tiên kill fuzz/build khi hết RAM (PLAN §6.1)
EARLYOOM_ARGS="-r 10 -m 5 -s 5 --avoid '(^|/)(sshd|systemd|dockerd|Xorg|gnome-shell)$' --prefer '(^|/)(d8|fuzzilli|libFuzzer|clang\+\+|ld\.lld|ninja|opencode)$'"
EOF
systemctl enable --now earlyoom >/dev/null 2>&1 || true
echo "earlyoom: $(systemctl is-active earlyoom 2>/dev/null || echo 'không chạy')"

say "depot_tools → $OPERATOR_HOME/tools/depot_tools"
if [[ ! -d "$OPERATOR_HOME/tools/depot_tools" ]]; then
    sudo -u "$OPERATOR" mkdir -p "$OPERATOR_HOME/tools"
    sudo -u "$OPERATOR" git clone -q https://chromium.googlesource.com/chromium/tools/depot_tools.git "$OPERATOR_HOME/tools/depot_tools"
    echo "đã clone"
else
    echo "đã có"
fi
RC="$OPERATOR_HOME/.bashrc"
grep -q 'tools/depot_tools' "$RC" || echo 'export PATH="$HOME/tools/depot_tools:$PATH"' >>"$RC"

say "uv"
if sudo -u "$OPERATOR" bash -lc 'command -v uv >/dev/null 2>&1'; then
    echo "uv: $(sudo -u "$OPERATOR" bash -lc 'uv --version' 2>/dev/null || true)"
else
    sudo -u "$OPERATOR" bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh' >/dev/null
    echo "đã cài uv"
fi

say "git identity"
if ! sudo -u "$OPERATOR" git config --global user.name >/dev/null 2>&1; then
    sudo -u "$OPERATOR" git config --global user.name "$OPERATOR"
fi
if ! sudo -u "$OPERATOR" git config --global user.email >/dev/null 2>&1; then
    sudo -u "$OPERATOR" git config --global user.email "$OPERATOR@users.noreply.github.com"
fi
echo "git: $(sudo -u "$OPERATOR" git config --global user.name) <$(sudo -u "$OPERATOR" git config --global user.email)>"

printf '\nbootstrap xong. Ghi chú: log out/in (hoặc newgrp docker) để group docker hiệu lực.\n'
