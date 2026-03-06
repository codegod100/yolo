# YOLO Greeter

A modern, Kirigami-based greetd login manager written in C++ and QML.

## Features

- Modern Kirigami UI with KDE integration
- Automatic detection of Wayland/X11 sessions
- User auto-discovery from system
- Full greetd protocol support
- Nix flake for easy deployment

## Building

### Using Nix

```bash
# Build the package
nix build

# Enter development shell
nix develop

# Build manually in dev shell
cmake -B build
cmake --build build
```

### Manual Build

Dependencies:
- CMake 3.20+
- Qt6 (Core, Quick, QuickControls2)
- KF6Kirigami
- extra-cmake-modules

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
sudo cmake --install build
```

## Usage with greetd

Add to your `configuration.nix`:

```nix
{
  services.greetd = {
    enable = true;
    settings = {
      default_session = {
        command = "${pkgs.yolo-greeter}/bin/yolo-greeter";
        user = "greeter";
      };
    };
  };
}
```

Or use the included NixOS module:

```nix
{
  imports = [ /path/to/yolo-greeter ];
  services.displayManager.yoloGreeter.enable = true;
}
```

## Testing

Run with mock greetd:

```bash
# Terminal 1: Start mock greetd
python mock_greetd.py --sock /tmp/greetd-test.sock

# Terminal 2: Run greeter
GREETD_SOCK=/tmp/greetd-test.sock ./build/bin/yolo-greeter
```

## License

MIT
