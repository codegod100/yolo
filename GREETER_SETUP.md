# YOLO Greeter Stack (greetd + niri + Conway Background)

This guide documents the full setup for the custom login frontend in this repo:

- `greetd` as display manager
- `niri` as greeter compositor
- `yolo-greeter` as Kirigami-based C++ login UI
- `yolo-conway-bg` as animated background layer
- Breeze theme for the login UI

## Quick Setup Script

If you want to apply the whole stack in one shot (after building the project):

```bash
# 1) Build the C++ project first
cmake -B build
cmake --build build

# 2) Run setup
sudo ./setup-greeter.sh
```

Optional environment toggles:

```bash
sudo DISABLE_LOCKOUT=1 DISABLE_OTHER_DM=1 ./setup-greeter.sh
```

## 1) Install Dependencies

On Arch/CachyOS:

```bash
sudo pacman -S --needed \
  greetd niri seatd \
  qt6-base qt6-declarative qt6-svg \
  kirigami kirigami-addons \
  python python-gobject python-cairo \
  gtk4 gtk4-layer-shell breeze-icons
```

## 2) Install Frontend Scripts

From this repo root (after building):

```bash
sudo install -m 755 ./build/yolo-greeter /usr/local/bin/yolo-greeter
sudo install -m 755 ./conway_layer_bg.py /usr/local/bin/yolo-conway-bg
```

## 3) Create Greeter State/Config Dirs

```bash
sudo install -d -m 700 -o greeter -g greeter /var/lib/greetd
sudo install -d -m 700 -o greeter -g greeter /var/lib/greetd/.config
```

## 4) niri Greeter Config (with Conway Background)

Create `/etc/greetd/niri-greeter.kdl`:

```kdl
// Minimal niri config for greetd greeter session.
layout {
    focus-ring {
        off
    }
}

window-rule {
    geometry-fixed-size width=800 height=600
}

hotkey-overlay {
    skip-at-startup
}

spawn-sh-at-startup "sleep 0.4; HOME=/var/lib/greetd XDG_CONFIG_HOME=/var/lib/greetd/.config GDK_BACKEND=wayland LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so /usr/bin/python3 /usr/local/bin/yolo-conway-bg >>/var/lib/greetd/yolo-conway-bg.log 2>&1"
spawn-sh-at-startup "HOME=/var/lib/greetd XDG_CONFIG_HOME=/var/lib/greetd/.config QT_QPA_PLATFORM=wayland /usr/local/bin/yolo-greeter; /usr/bin/pkill -TERM -x niri"
```

Validate it:

```bash
niri validate -c /etc/greetd/niri-greeter.kdl
```

## 5) greetd Config

Set `/etc/greetd/config.toml`:

```toml
[terminal]
vt = 1

[default_session]
command = "niri --session --config /etc/greetd/niri-greeter.kdl"
user = "greeter"
```

## 6) seatd Access (important)

```bash
sudo usermod -aG seat greeter
sudo systemctl enable --now seatd
```

## 7) Make greetd Default Display Manager

If another DM is enabled:

```bash
sudo systemctl disable --now plasmalogin.service 2>/dev/null || true
sudo systemctl enable --now greetd.service
```

`display-manager.service` should point to `greetd.service`.

## 8) Optional: Disable PAM Lockout for greetd Only

If you do not want login lockouts in this greeter flow:

```bash
sudo tee /etc/pam.d/greetd-auth-no-faillock >/dev/null <<'EOF'
#%PAM-1.0
-auth      [success=2 default=ignore]  pam_systemd_home.so
auth       [success=1 default=bad]     pam_unix.so          try_first_pass nullok
auth       optional                    pam_permit.so
auth       required                    pam_env.so
EOF

sudo tee /etc/pam.d/greetd >/dev/null <<'EOF'
#%PAM-1.0
auth       required     pam_securetty.so
auth       requisite    pam_nologin.so
auth       include      greetd-auth-no-faillock
account    include      system-local-login
session    include      system-local-login
EOF
```

## 9) Restart and Verify

```bash
sudo systemctl restart greetd
systemctl status greetd --no-pager -l
```

Useful checks:

```bash
cat /etc/greetd/config.toml
cat /etc/greetd/niri-greeter.kdl
id greeter
systemctl status seatd --no-pager
```

## Runtime Files

- Conway background logs:
  - `/var/lib/greetd/yolo-conway-bg.log`

## Troubleshooting

If background appears as a normal tiled window instead of full-screen layer:

1. Check preload warning:
```bash
sudo tail -n 200 /var/lib/greetd/yolo-conway-bg.log
```
Look for `GtkWindow is not a layer surface` or layer-shell linker warnings.

2. Confirm `LD_PRELOAD` path exists:
```bash
ldconfig -p | rg libgtk4-layer-shell.so
```

3. Confirm seatd and greeter groups:
```bash
systemctl status seatd --no-pager
id greeter
```

4. Restart greetd:
```bash
sudo systemctl restart greetd
```
