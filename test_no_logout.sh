#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOCK_PATH="${SOCK_PATH:-/tmp/greetd-test.sock}"
USERNAME="${USERNAME:-$USER}"
SESSION_CMD="${SESSION_CMD:-echo hello-from-pygreet}"

echo "Starting mock greetd on ${SOCK_PATH} ..."
python3 "${ROOT_DIR}/mock_greetd.py" --sock "${SOCK_PATH}" &
MOCK_PID=$!
trap 'kill "${MOCK_PID}" >/dev/null 2>&1 || true' EXIT

sleep 0.2

echo "Launching pygreet client (password is: test123)"
GREETD_SOCK="${SOCK_PATH}" python3 "${ROOT_DIR}/pygreet.py" \
  --username "${USERNAME}" \
  --cmd "${SESSION_CMD}"

echo "No-logout test completed."
