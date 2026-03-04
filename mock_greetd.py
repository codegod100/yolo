#!/usr/bin/env python3
"""Small mock greetd IPC server for local no-logout testing."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import struct
import sys
from typing import Any


def recv_exact(conn: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise RuntimeError("client disconnected")
        data.extend(chunk)
    return bytes(data)


def recv_msg(conn: socket.socket) -> dict[str, Any]:
    header = recv_exact(conn, 4)
    (length,) = struct.unpack("=I", header)
    payload = recv_exact(conn, length)
    msg = json.loads(payload.decode("utf-8"))
    print("CLIENT:", json.dumps(msg, sort_keys=True))
    return msg


def send_msg(conn: socket.socket, msg: dict[str, Any]) -> None:
    print("SERVER:", json.dumps(msg, sort_keys=True))
    payload = json.dumps(msg).encode("utf-8")
    conn.sendall(struct.pack("=I", len(payload)) + payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock greetd for pygreet testing.")
    parser.add_argument(
        "--sock",
        default="/tmp/greetd-test.sock",
        help="Unix socket path to bind (default: /tmp/greetd-test.sock)",
    )
    parser.add_argument(
        "--password",
        default="test123",
        help="Password accepted by the mock server (default: test123)",
    )
    return parser.parse_args()


def cleanup_socket(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def handle_client(conn: socket.socket, accepted_password: str) -> None:
    msg = recv_msg(conn)
    if msg.get("type") != "create_session":
        send_msg(
            conn,
            {
                "type": "error",
                "error_type": "auth_error",
                "description": "expected create_session first",
            },
        )
        return

    send_msg(
        conn,
        {
            "type": "auth_message",
            "auth_message_type": "secret",
            "auth_message": "Password: ",
        },
    )

    msg = recv_msg(conn)
    if msg.get("type") != "post_auth_message_response":
        send_msg(
            conn,
            {
                "type": "error",
                "error_type": "auth_error",
                "description": "expected post_auth_message_response",
            },
        )
        return

    if msg.get("response") != accepted_password:
        send_msg(
            conn,
            {
                "type": "error",
                "error_type": "auth_error",
                "description": "invalid credentials",
            },
        )
        return

    send_msg(conn, {"type": "success"})

    msg = recv_msg(conn)
    if msg.get("type") != "start_session":
        send_msg(
            conn,
            {
                "type": "error",
                "error_type": "session_error",
                "description": "expected start_session",
            },
        )
        return

    cmd = msg.get("cmd")
    if not isinstance(cmd, list) or not cmd:
        send_msg(
            conn,
            {
                "type": "error",
                "error_type": "session_error",
                "description": "cmd must be a non-empty array",
            },
        )
        return

    send_msg(conn, {"type": "success"})
    print("Test flow completed successfully.")


def main() -> int:
    args = parse_args()
    sock_path = args.sock
    accepted_password = args.password

    cleanup_socket(sock_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)
    print(f"Mock greetd listening on {sock_path}")
    print(f"Accepted password: {accepted_password}")

    def on_signal(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    try:
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    handle_client(conn, accepted_password)
                except RuntimeError as exc:
                    print(f"Client disconnected: {exc}")
    except KeyboardInterrupt:
        print("\nShutting down mock greetd.")
        return 130
    finally:
        server.close()
        cleanup_socket(sock_path)


if __name__ == "__main__":
    sys.exit(main())
