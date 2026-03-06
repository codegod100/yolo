#!/usr/bin/env python3
"""Minimal greetd frontend implemented in Python."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import socket
import struct
import sys
from typing import Any


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
        header = struct.pack("=I", len(body))
        self.sock.sendall(header + body)

    def recv(self) -> dict[str, Any]:
        header = self._recv_exact(4)
        (length,) = struct.unpack("=I", header)
        body = self._recv_exact(length)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GreetdProtocolError("invalid JSON response from greetd") from exc


def handle_error(msg: dict[str, Any]) -> None:
    error_type = msg.get("error_type", "error")
    description = msg.get("description", "unknown error")
    raise RuntimeError(f"{error_type}: {description}")


def auth_flow(client: GreetdClient, username: str) -> None:
    client.send({"type": "create_session", "username": username})
    while True:
        reply = client.recv()
        reply_type = reply.get("type")

        if reply_type == "success":
            return
        if reply_type == "error":
            handle_error(reply)
        if reply_type != "auth_message":
            raise GreetdProtocolError(f"unexpected response type: {reply_type!r}")

        prompt_type = reply.get("auth_message_type")
        prompt_text = reply.get("auth_message", "")
        response_payload: dict[str, Any] = {"type": "post_auth_message_response"}

        if prompt_type == "visible":
            response_payload["response"] = input(prompt_text)
        elif prompt_type == "secret":
            response_payload["response"] = getpass.getpass(prompt_text)
        elif prompt_type == "info":
            if prompt_text:
                print(prompt_text)
        elif prompt_type == "error":
            if prompt_text:
                print(prompt_text, file=sys.stderr)
        else:
            raise GreetdProtocolError(f"unknown auth message type: {prompt_type!r}")

        client.send(response_payload)


def start_session(client: GreetdClient, command: list[str], env: list[str]) -> None:
    client.send({"type": "start_session", "cmd": command, "env": env})
    reply = client.recv()
    reply_type = reply.get("type")
    if reply_type == "success":
        return
    if reply_type == "error":
        handle_error(reply)
    raise GreetdProtocolError(f"unexpected response type: {reply_type!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A small greetd frontend written in Python."
    )
    parser.add_argument(
        "-u",
        "--username",
        help="Username to authenticate. If omitted, prompts interactively.",
    )
    parser.add_argument(
        "-c",
        "--cmd",
        help="Session command to run after successful authentication.",
    )
    parser.add_argument(
        "-e",
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional env var passed to start_session. Repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sock_path = os.environ.get("GREETD_SOCK")
    if not sock_path:
        print("GREETD_SOCK is not set. Run this from greetd.", file=sys.stderr)
        return 1

    username = args.username or input("Username: ").strip()
    if not username:
        print("Username is required.", file=sys.stderr)
        return 1

    cmd_line = args.cmd or input("Session command: ").strip()
    if not cmd_line:
        print("Session command is required.", file=sys.stderr)
        return 1

    try:
        command = shlex.split(cmd_line)
    except ValueError as exc:
        print(f"Invalid session command: {exc}", file=sys.stderr)
        return 1

    if not command:
        print("Session command cannot be empty.", file=sys.stderr)
        return 1

    invalid_env = [item for item in args.env if "=" not in item or item.startswith("=")]
    if invalid_env:
        print(f"Invalid env format (expected KEY=VALUE): {invalid_env}", file=sys.stderr)
        return 1

    client = GreetdClient(sock_path)
    try:
        auth_flow(client, username)
        start_session(client, command, args.env)
    except KeyboardInterrupt:
        print("\nCanceled.", file=sys.stderr)
        try:
            client.send({"type": "cancel_session"})
            client.recv()
        except Exception:
            pass
        return 130
    except Exception as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        try:
            client.send({"type": "cancel_session"})
            client.recv()
        except Exception:
            pass
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
