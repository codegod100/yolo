# pygreet

Small `greetd` frontend implemented in Python.

For the full greeter stack used on this machine (greetd + niri + Qt login UI + Conway background), see:

- [`GREETER_SETUP.md`](./GREETER_SETUP.md)

## What it does

- Talks to `greetd` through `GREETD_SOCK`.
- Runs authentication prompts (`visible`, `secret`, `info`, `error`).
- Starts a session with `start_session`.

## Requirements

- Python 3.10+
- `greetd` already installed/configured
- For GUI frontend: PyQt6 (`pip install PyQt6`)

## Usage

Interactive:

```bash
python3 /path/to/pygreet.py
```

With defaults:

```bash
python3 /path/to/pygreet.py --username nandi --cmd "sway"
```

Add environment variables for session launch:

```bash
python3 /path/to/pygreet.py --cmd "Hyprland" --env XKB_DEFAULT_LAYOUT=us --env GTK_THEME=Adwaita
```

GUI greeter:

```bash
python3 /path/to/pygreet_qt.py
```

## Test Without Logging Out

You can verify the IPC/auth/session flow with a local mock socket.

Terminal 1:

```bash
python3 /path/to/mock_greetd.py
```

Terminal 2:

```bash
GREETD_SOCK=/tmp/greetd-test.sock python3 /path/to/pygreet.py --username "$USER" --cmd "echo test"
```

Use password `test123` in this mock test.

Or run the helper script:

```bash
./test_no_logout.sh
```

## Configure greetd

Use your `greetd` config file (often `/etc/greetd/config.toml`) and set:

```toml
[default_session]
command = "python3 /path/to/pygreet.py --cmd sway"
user = "greeter"
```

Or use the GUI frontend:

```toml
[default_session]
command = "python3 /path/to/pygreet_qt.py"
user = "greeter"
```

Then restart greetd:

```bash
sudo systemctl restart greetd
```

## Notes

- `pygreet.py` is text-based and similar in spirit to `agreety`.
- `pygreet_qt.py` provides a PyQt6 login window.
- Mock testing validates protocol handling only. Real PAM/session behavior must be tested under actual `greetd`.
