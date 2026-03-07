# YOLO Greeter

A lightweight greetd login manager written in Zig with GTK4.

![Screenshot](https://github.com/codegod100/yolo/raw/main/screenshot.png)

## Features

- Fast startup, minimal dependencies (just GTK4 + gtk4-layer-shell)
- User and session selection from dropdowns
- Animated Conway's Game of Life background layer
- Catppuccin/Mocha theme support
- Works with any Wayland compositor (niri, Hyprland, Sway, etc.)

## Requirements

- `greetd` display manager
- `niri` (as greeter compositor) or another Wayland compositor
- `gtk4` and `gtk4-layer-shell`
- `zig` (for building)

## Installation

### Nix / NixOS

**Quick run:**
```bash
nix run github:codegod100/yolo
```

**One-shot install:**
```bash
nix run github:codegod100/yolo#install
```

**NixOS module:**
```nix
{
  inputs.yolo.url = "github:codegod100/yolo";

  outputs = { nixpkgs, yolo, ... }: {
    nixosConfigurations.my-machine = nixpkgs.lib.nixosSystem {
      modules = [
        yolo.nixosModules.default
        {
          services.displayManager.yoloGreeter = {
            enable = true;
            # package = yolo.packages.${pkgs.system}.default;
          };
        }
      ];
    };
  };
}
```

### Arch / CachyOS

1. Install dependencies:
```bash
sudo pacman -S --needed greetd niri seatd gtk4 gtk4-layer-shell zig python
```

2. Clone and build:
```bash
git clone https://github.com/codegod100/yolo
cd yolo/yolo-zig
zig build
```

3. Run the setup script:
```bash
cd ..
sudo ./setup-greeter.sh
```

This installs:
- `/usr/local/bin/yolo-zig` - the greeter binary
- `/usr/local/bin/yolo-conway-bg` - animated background
- `/etc/greetd/niri-greeter.kdl` - niri config for greeter session
- `/etc/greetd/config.toml` - greetd config

4. Enable greetd:
```bash
sudo systemctl enable --now greetd
```

## Customization

### GTK Theme

Edit `/etc/greetd/niri-greeter.kdl` and change `GTK_THEME`:

```kdl
spawn-sh-at-startup "HOME=/var/lib/greetd GTK_THEME=catppuccin-mocha-mauve-standard+default /usr/local/bin/yolo-zig ..."
```

Available themes are in `/usr/share/themes/`.

### Background Animation

The Conway's Game of Life background runs as a separate layer shell process. It can be disabled by removing the `yolo-conway-bg` spawn line from the niri config.

Logs: `/var/lib/greetd/yolo-conway-bg.log`

## Testing Without Installing

Use the mock greetd server to test the UI:

```bash
# Start mock server
just mock

# In another terminal, run greeter
just run
```

Password for mock server: `test123`

## Development

```bash
# Enter dev shell
nix develop

# Or with direnv
direnv allow

# Build
just build

# Run mock + greeter for testing
just dev
```

## Project Structure

```
yolo/
├── yolo-zig/           # Zig GTK4 greeter
│   └── src/
│       ├── main.zig    # GTK UI, auth flow
│       ├── greetd.zig  # greetd protocol client
│       └── models.zig  # user/session discovery
├── conway_layer_bg.py  # Animated background layer
├── setup-greeter.sh    # System installation script
├── mock_greetd.py      # Test server
└── flake.nix           # Nix packaging
```

## License

MIT