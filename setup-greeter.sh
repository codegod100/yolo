#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Allow overriding source paths (useful for Nix)
YOLO_BIN_SRC="${YOLO_BIN_SRC:-${REPO_DIR}/yolo-zig/zig-out/bin/yolo-zig}"
CONWAY_BG_SRC="${CONWAY_BG_SRC:-${REPO_DIR}/conway_layer_bg.py}"

GTK_THEME="${GTK_THEME:-catppuccin-mocha-mauve-standard+default}"
DISABLE_LOCKOUT="${DISABLE_LOCKOUT:-1}"
DISABLE_OTHER_DM="${DISABLE_OTHER_DM:-1}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./setup-greeter.sh"
  exit 1
fi

if [[ ! -f "${YOLO_BIN_SRC}" ]]; then
  echo "Error: yolo-zig binary not found at ${YOLO_BIN_SRC}"
  echo "Build it first: cd yolo-zig && zig build"
  exit 1
fi

if [[ ! -f "${CONWAY_BG_SRC}" ]]; then
  echo "Error: conway_layer_bg.py not found at ${CONWAY_BG_SRC}"
  exit 1
fi

echo "[1/6] Installing greeter scripts..."
install -m 755 "${YOLO_BIN_SRC}" /usr/local/bin/yolo-zig
install -m 755 "${CONWAY_BG_SRC}" /usr/local/bin/yolo-conway-bg

echo "[2/6] Preparing greeter state dir..."
install -d -m 700 -o greeter -g greeter /var/lib/greetd

echo "[3/6] Writing niri greeter config..."
cat >/etc/greetd/niri-greeter.kdl <<EOF
// Minimal niri config for greetd greeter session.
layout {
    focus-ring {
        off
    }
}

window-rule {
    match app-id="org.yolo.greeter"
    default-column-width { fixed 400; }
    default-window-height { fixed 300; }
    open-floating true
}

hotkey-overlay {
    skip-at-startup
}

spawn-sh-at-startup "sleep 0.4; HOME=/var/lib/greetd XDG_CONFIG_HOME=/var/lib/greetd/.config GDK_BACKEND=wayland LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so /usr/bin/python3 /usr/local/bin/yolo-conway-bg >>/var/lib/greetd/yolo-conway-bg.log 2>&1"
spawn-sh-at-startup "HOME=/var/lib/greetd XDG_CONFIG_HOME=/var/lib/greetd/.config GDK_BACKEND=wayland GTK_THEME=${GTK_THEME} /usr/local/bin/yolo-zig >>/var/lib/greetd/yolo-zig.log 2>&1; /usr/bin/pkill -TERM -x niri"
EOF

if command -v niri >/dev/null 2>&1; then
  niri validate -c /etc/greetd/niri-greeter.kdl
else
  echo "Warning: niri not found; skipped niri config validation."
fi

echo "[4/6] Writing greetd config..."
install -d -m 755 /etc/greetd
cat >/etc/greetd/config.toml <<'EOF'
[terminal]
vt = 1

[default_session]
command = "niri --session --config /etc/greetd/niri-greeter.kdl"
user = "greeter"
EOF

echo "[5/6] Enabling seat access..."
usermod -aG seat greeter || true
systemctl enable --now seatd

if [[ "${DISABLE_LOCKOUT}" == "1" ]]; then
  echo "[6/6] Disabling PAM lockout for greetd..."
  cat >/etc/pam.d/greetd-auth-no-faillock <<'EOF'
#%PAM-1.0
-auth      [success=2 default=ignore]  pam_systemd_home.so
auth       [success=1 default=bad]     pam_unix.so          try_first_pass nullok
auth       optional                    pam_permit.so
auth       required                    pam_env.so
EOF

  cat >/etc/pam.d/greetd <<'EOF'
#%PAM-1.0
auth       required     pam_securetty.so
auth       requisite    pam_nologin.so
auth       include      greetd-auth-no-faillock
account    include      system-local-login
session    include      system-local-login
EOF
else
  echo "[6/6] Skipping PAM lockout override (DISABLE_LOCKOUT=${DISABLE_LOCKOUT})."
fi

echo "Enabling greetd..."
if [[ "${DISABLE_OTHER_DM}" == "1" ]]; then
  systemctl disable --now plasmalogin.service 2>/dev/null || true
fi
systemctl enable --now greetd.service
systemctl restart greetd

echo
echo "Greeter setup complete."
echo "Theme: ${GTK_THEME}"
echo "Lockout override: ${DISABLE_LOCKOUT}"
echo "Other DM disable attempted: ${DISABLE_OTHER_DM}"
echo
echo "Verify:"
echo "  systemctl status greetd --no-pager -l"
echo "  systemctl status seatd --no-pager -l"
echo "  tail -n 50 /var/lib/greetd/yolo-zig.log"
echo "  tail -n 50 /var/lib/greetd/yolo-conway-bg.log"
