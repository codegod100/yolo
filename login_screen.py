#!/usr/bin/env python3
"""PyQt6 login screen with greetd authentication."""

import os
from pathlib import Path
import pwd
import shlex
import subprocess
import sys
from typing import Any

# Silence noisy non-fatal Wayland textinput warnings unless user overrides.
if "QT_LOGGING_RULES" not in os.environ:
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.wayland.textinput.warning=false"

from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

# Import greetd client from existing file
from pygreet_qt import GreetdClient, GreetdProtocolError, raise_error

MOCK_SOCK = "/tmp/greetd-test.sock"


class LoginScreen(QWidget):
    """Login screen with greetd authentication."""
    
    def __init__(self):
        super().__init__()
        self.settings = self.create_settings()
        self.client: GreetdClient | None = None
        self.init_ui()

    @staticmethod
    def create_settings() -> QSettings:
        """Create a persistent settings store for both greeter and local testing."""
        preferred = Path(
            os.environ.get("YOLO_GREETER_SETTINGS", "/var/lib/greetd/yolo-login-screen.ini")
        )
        if preferred.parent.is_dir() and os.access(preferred.parent, os.W_OK):
            return QSettings(str(preferred), QSettings.Format.IniFormat)
        return QSettings("yolo", "login-screen")
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Login")
        self.setFixedSize(400, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Sign In")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # Username
        self.username_input = QComboBox()
        self.username_input.setEditable(True)
        self.username_input.addItems(self.load_login_users())
        self.username_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.username_input.lineEdit().setPlaceholderText("Username")
        self.username_input.lineEdit().returnPressed.connect(self.attempt_login)
        layout.addWidget(self.username_input)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.attempt_login)
        layout.addWidget(self.password_input)
        
        # Session selector
        session_layout = QHBoxLayout()
        session_label = QLabel("Session:")
        self.session_combo = QComboBox()
        self.session_combo.setEditable(True)
        for session_name, session_cmd in self.load_wayland_sessions():
            self.session_combo.addItem(session_name, session_cmd)
        self.restore_last_session()
        session_layout.addWidget(session_label)
        session_layout.addWidget(self.session_combo)
        layout.addLayout(session_layout)
        
        # Login button
        self.login_button = QPushButton("Sign In")
        self.login_button.clicked.connect(self.attempt_login)
        layout.addWidget(self.login_button)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.password_input.setFocus()

    @staticmethod
    def load_login_users() -> list[str]:
        """Load likely human login users from passwd."""
        users: list[str] = []
        for entry in pwd.getpwall():
            if entry.pw_uid < 1000:
                continue
            if entry.pw_shell.endswith("nologin") or entry.pw_shell.endswith("false"):
                continue
            users.append(entry.pw_name)
        return sorted(set(users))

    @staticmethod
    def load_wayland_sessions() -> list[tuple[str, str]]:
        """Load (display_name, command) pairs from installed Wayland sessions."""
        session_dirs = (
            Path("/usr/share/wayland-sessions"),
            Path("/usr/local/share/wayland-sessions"),
        )
        sessions: list[tuple[str, str]] = []
        seen_commands: set[str] = set()
        used_names: dict[str, int] = {}

        for session_dir in session_dirs:
            if not session_dir.is_dir():
                continue

            for desktop_file in sorted(session_dir.glob("*.desktop")):
                entry: dict[str, str] = {}
                in_desktop_entry = False

                try:
                    with desktop_file.open("r", encoding="utf-8") as handle:
                        for raw_line in handle:
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                in_desktop_entry = line == "[Desktop Entry]"
                                continue
                            if not in_desktop_entry or "=" not in line:
                                continue
                            key, value = line.split("=", 1)
                            entry[key.strip()] = value.strip()
                except OSError:
                    continue

                if entry.get("Type", "Application") != "Application":
                    continue
                if entry.get("Hidden", "false").lower() == "true":
                    continue
                if entry.get("NoDisplay", "false").lower() == "true":
                    continue

                exec_line = entry.get("Exec", "").strip()
                if not exec_line:
                    continue

                try:
                    parts = shlex.split(exec_line)
                except ValueError:
                    continue

                cleaned = [part for part in parts if not part.startswith("%")]
                if not cleaned:
                    continue

                command = " ".join(cleaned)
                if command in seen_commands:
                    continue
                seen_commands.add(command)

                name = entry.get("Name", cleaned[0]).strip() or cleaned[0]
                count = used_names.get(name, 0) + 1
                used_names[name] = count
                if count > 1:
                    label = f"{name} ({cleaned[0]})"
                else:
                    label = name

                sessions.append((label, command))

        if sessions:
            return sessions

        return [
            ("Sway", "sway"),
            ("Plasma Wayland", "startplasma-wayland"),
            ("X11 (startx)", "startx"),
            ("Bash", "bash"),
        ]
    
    def set_busy(self, busy: bool):
        """Enable/disable inputs during authentication."""
        self.login_button.setEnabled(not busy)
        self.username_input.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.session_combo.setEnabled(not busy)
        self.login_button.setText("Signing in..." if busy else "Sign In")

    def restore_last_session(self) -> None:
        """Restore the most recently used session command."""
        last_cmd = str(self.settings.value("last_session_cmd", "")).strip()
        if not last_cmd:
            return

        for idx in range(self.session_combo.count()):
            item_cmd = self.session_combo.itemData(idx)
            if isinstance(item_cmd, str) and item_cmd == last_cmd:
                self.session_combo.setCurrentIndex(idx)
                return

        self.session_combo.setEditText(last_cmd)

    @staticmethod
    def is_auth_failure(error_text: str) -> bool:
        lowered = error_text.lower()
        return (
            "auth_error" in lowered
            or "invalid credentials" in lowered
            or "pam_" in lowered
            or "authentication" in lowered
        )

    @staticmethod
    def pretty_error_message(error_text: str) -> str:
        """Convert greetd/PAM errors into user-friendly text."""
        lowered = error_text.lower()

        if lowered.startswith("auth_error:"):
            return "Incorrect username or password."
        if (
            "invalid credentials" in lowered
            or "pam_auth_err" in lowered
            or "authentication failure" in lowered
        ):
            return "Incorrect username or password."
        if "pam_user_unknown" in lowered or "user not known" in lowered:
            return "This user account does not exist."
        if "pam_maxtries" in lowered or "too many" in lowered:
            return "Too many failed attempts. Please wait and try again."
        if "pam_acct_expired" in lowered or "account expired" in lowered:
            return "This account has expired."
        if "pam_new_authtok_reqd" in lowered or "password expired" in lowered:
            return "Your password has expired and must be changed before login."
        if "pam_perm_denied" in lowered or "permission denied" in lowered:
            return "Permission denied for this account."
        if "session_error" in lowered:
            return "Login succeeded, but the session failed to start."
        if "pam_" in lowered:
            return "Authentication failed. Please check your credentials and try again."

        if ": " in error_text:
            _, detail = error_text.split(": ", 1)
            detail = detail.strip()
            if detail:
                return detail[:1].upper() + detail[1:]
        return error_text
    
    def attempt_login(self):
        """Handle login attempt with greetd authentication."""
        sock_path = os.environ.get("GREETD_SOCK", MOCK_SOCK)
        if not os.path.exists(sock_path):
            QMessageBox.critical(self, "Error", f"Greetd socket not found: {sock_path}")
            return
        
        username = self.username_input.currentText().strip()
        password = self.password_input.text()
        cmd_text = (self.session_combo.currentData() or self.session_combo.currentText()).strip()
        
        if not username or not password or not cmd_text:
            self.status_label.setText("Please fill in all fields")
            return
        
        try:
            cmd = shlex.split(cmd_text)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid command", str(exc))
            return
        
        if not cmd:
            QMessageBox.critical(self, "Invalid command", "Session command cannot be empty.")
            return

        # Persist selection on attempt so it sticks even if auth fails.
        self.settings.setValue("last_session_cmd", cmd_text)
        self.settings.sync()
        
        self.status_label.setText("")
        self.set_busy(True)
        QApplication.processEvents()
        auth_failed = False
        
        try:
            self.client = GreetdClient(sock_path)
            self.auth_flow(username, password)
            
            self.status_label.setText("Starting session...")
            QApplication.processEvents()
            
            self.start_session(cmd)
            self.status_label.setText("Session started.")
            QApplication.quit()
            
        except Exception as exc:
            if self.client:
                try:
                    self.client.send({"type": "cancel_session"})
                    self.client.recv()
                except Exception:
                    pass
            message = str(exc)
            pretty = self.pretty_error_message(message)
            self.status_label.setText(pretty)
            QMessageBox.warning(self, "Login failed", pretty)
            if self.is_auth_failure(message):
                auth_failed = True
        finally:
            if self.client:
                self.client.close()
                self.client = None
            self.set_busy(False)
            if auth_failed:
                # Defer focus until widgets are enabled again.
                QTimer.singleShot(0, self.password_input.setFocus)
                QTimer.singleShot(0, self.password_input.selectAll)
    
    def auth_flow(self, username: str, initial_password: str) -> None:
        """Handle greetd authentication flow."""
        self.client.send({"type": "create_session", "username": username})
        first_secret_consumed = False
        
        while True:
            reply = self.client.recv()
            reply_type = reply.get("type")
            
            if reply_type == "success":
                return
            if reply_type == "error":
                raise_error(reply)
            if reply_type != "auth_message":
                raise GreetdProtocolError(f"unexpected response type: {reply_type!r}")
            
            prompt_type = reply.get("auth_message_type")
            prompt_text = str(reply.get("auth_message", ""))
            response: dict[str, Any] = {"type": "post_auth_message_response"}
            
            if prompt_type == "secret":
                if not first_secret_consumed:
                    secret = initial_password
                    first_secret_consumed = True
                else:
                    secret = self.password_input.text()
                response["response"] = secret
            elif prompt_type == "visible":
                response["response"] = self.username_input.currentText().strip()
            elif prompt_type == "info":
                if prompt_text:
                    QMessageBox.information(self, "Info", prompt_text)
            elif prompt_type == "error":
                if prompt_text:
                    QMessageBox.warning(
                        self, "Authentication message", self.pretty_error_message(prompt_text)
                    )
            else:
                raise GreetdProtocolError(f"unknown auth message type: {prompt_type!r}")
            
            self.client.send(response)
    
    def start_session(self, cmd: list[str]) -> None:
        """Start the session via greetd."""
        self.client.send({"type": "start_session", "cmd": cmd, "env": []})
        reply = self.client.recv()
        reply_type = reply.get("type")
        
        if reply_type == "success":
            return
        if reply_type == "error":
            raise_error(reply)
        raise GreetdProtocolError(f"unexpected response type: {reply_type!r}")


def main():
    # Start mock greetd if no real greetd socket exists
    sock_path = os.environ.get("GREETD_SOCK", MOCK_SOCK)
    mock_process = None
    
    if not os.path.exists(sock_path):
        print("Starting mock greetd server...")
        mock_process = subprocess.Popen(
            [sys.executable, "mock_greetd.py", "--sock", sock_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        time.sleep(0.3)  # Wait for socket to be created
    
    app = QApplication(sys.argv)
    window = LoginScreen()
    window.show()
    
    result = app.exec()
    
    if mock_process:
        mock_process.terminate()
        mock_process.wait()
    
    return result


if __name__ == "__main__":
    sys.exit(main())
