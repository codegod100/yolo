#!/usr/bin/env python3
"""PyQt6-based greetd frontend."""

from __future__ import annotations

import os
import shlex
import socket
import struct
import json
import sys
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class GreetdProtocolError(RuntimeError):
    """Raised when greetd IPC data is malformed or unexpected."""


class GreetdClient:
    def __init__(self, sock_path: str) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(sock_path)

    def close(self) -> None:
        self.sock.close()

    def _recv_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise GreetdProtocolError("unexpected EOF while receiving IPC message")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def send(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.sock.sendall(struct.pack("=I", len(body)) + body)

    def recv(self) -> dict[str, Any]:
        header = self._recv_exact(4)
        (length,) = struct.unpack("=I", header)
        body = self._recv_exact(length)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GreetdProtocolError("invalid JSON response from greetd") from exc


def raise_error(msg: dict[str, Any]) -> None:
    error_type = msg.get("error_type", "error")
    description = msg.get("description", "unknown error")
    raise RuntimeError(f"{error_type}: {description}")


class LoginWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Python greetd login")
        self.setMinimumWidth(420)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Sign In")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        form.addRow("Username", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        form.addRow("Password", self.password_input)

        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("sway")
        form.addRow("Session command", self.session_input)

        self.env_input = QLineEdit()
        self.env_input.setPlaceholderText("KEY=VALUE,KEY2=VALUE2 (optional)")
        form.addRow("Env", self.env_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.login_button = QPushButton("Log In")
        self.login_button.clicked.connect(self.login)  # type: ignore[arg-type]
        button_row.addStretch()
        button_row.addWidget(self.login_button)
        layout.addLayout(button_row)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #444;")
        layout.addWidget(self.status)

    def set_busy(self, busy: bool) -> None:
        self.login_button.setEnabled(not busy)
        self.username_input.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.session_input.setEnabled(not busy)
        self.env_input.setEnabled(not busy)

    def parse_env(self) -> list[str]:
        raw = self.env_input.text().strip()
        if not raw:
            return []
        env_vars = [item.strip() for item in raw.split(",") if item.strip()]
        invalid = [item for item in env_vars if "=" not in item or item.startswith("=")]
        if invalid:
            raise ValueError(f"Invalid env format: {', '.join(invalid)}")
        return env_vars

    def login(self) -> None:
        sock_path = os.environ.get("GREETD_SOCK")
        if not sock_path:
            QMessageBox.critical(self, "Error", "GREETD_SOCK is not set.")
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()
        cmd_text = self.session_input.text().strip()
        if not username or not password or not cmd_text:
            QMessageBox.warning(
                self, "Missing fields", "Username, password, and session command are required."
            )
            return

        try:
            cmd = shlex.split(cmd_text)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid command", str(exc))
            return
        if not cmd:
            QMessageBox.critical(self, "Invalid command", "Session command cannot be empty.")
            return

        try:
            env = self.parse_env()
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid env", str(exc))
            return

        self.set_busy(True)
        self.status.setText("Authenticating...")
        QApplication.processEvents()

        client = None
        try:
            client = GreetdClient(sock_path)
            self.auth_flow(client, username, password)
            self.status.setText("Starting session...")
            QApplication.processEvents()
            self.start_session(client, cmd, env)
            self.status.setText("Session started.")
            QApplication.processEvents()
            QApplication.quit()
        except Exception as exc:
            if client is not None:
                try:
                    client.send({"type": "cancel_session"})
                    client.recv()
                except Exception:
                    pass
            QMessageBox.critical(self, "Login failed", str(exc))
            self.status.setText("Login failed.")
        finally:
            if client is not None:
                client.close()
            self.set_busy(False)

    def auth_flow(self, client: GreetdClient, username: str, initial_password: str) -> None:
        client.send({"type": "create_session", "username": username})
        first_secret_consumed = False

        while True:
            reply = client.recv()
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
                response["response"] = self.username_input.text().strip()
            elif prompt_type == "info":
                if prompt_text:
                    QMessageBox.information(self, "Info", prompt_text)
            elif prompt_type == "error":
                if prompt_text:
                    QMessageBox.warning(self, "Authentication message", prompt_text)
            else:
                raise GreetdProtocolError(f"unknown auth message type: {prompt_type!r}")

            client.send(response)

    def start_session(self, client: GreetdClient, cmd: list[str], env: list[str]) -> None:
        client.send({"type": "start_session", "cmd": cmd, "env": env})
        reply = client.recv()
        reply_type = reply.get("type")
        if reply_type == "success":
            return
        if reply_type == "error":
            raise_error(reply)
        raise GreetdProtocolError(f"unexpected response type: {reply_type!r}")


def main() -> int:
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
